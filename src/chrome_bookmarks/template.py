"""Template engine for $variable and ${var1,var2,...} substitution."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from chrome_bookmarks.model import BookmarkNode, FolderNode, SeparatorNode


class BookmarkTemplateError(Exception):
    """Raised when a template references an undefined variable."""


def _resolve_field(node: object, field_name: str) -> Any:
    """Get a field value from any node type, returning None if not present."""
    if isinstance(node, BookmarkNode):
        mapping = {
            "title": node.title,
            "url": node.url,
            "add_date": node.add_date,
            "last_modified": node.last_modified,
            "icon": node.icon,
            "folder": node.folder_path,
            "folder_path": node.folder_path,
            "type": node.type,
            "depth": node.depth,
            "name": None,  # bookmark has no name field
        }
    elif isinstance(node, FolderNode):
        mapping = {
            "name": node.name,
            "folder": node.folder_path,
            "folder_path": node.folder_path,
            "type": node.type,
            "depth": node.depth,
            "add_date": getattr(node, "add_date", 0),
            "last_modified": getattr(node, "last_modified", 0),
            "title": None,  # folder has no title field
            "url": None,
            "icon": None,
        }
    elif isinstance(node, SeparatorNode):
        mapping = {
            "folder": node.folder_path,
            "folder_path": node.folder_path,
            "type": node.type,
            "depth": node.depth,
            "name": None,
            "title": None,
            "url": None,
            "add_date": None,
            "last_modified": None,
            "icon": None,
        }
    else:
        return None

    return mapping.get(field_name)


def render(node: object, template: str, utc: bool = False) -> str:
    """Render a template string against a node.

    Supports:
        $var           — single variable reference
        ${var1,var2,...} — fallback: returns the first non-empty value

    Special computed variables:
        $add_date_iso  — ISO 8601 in local time
        $add_date_utc  — ISO 8601 in UTC
    """
    result = []  # type: list[str]
    i = 0
    n = len(template)

    while i < n:
        ch = template[i]

        if ch == "$":
            # Consume the $
            i += 1
            if i >= n:
                result.append("$")
                break

            if template[i] == "{":
                # ${var1,var2,...} — fallback syntax
                i += 1  # skip '{'
                brace_end = template.find("}", i)
                if brace_end == -1:
                    # Unclosed brace, treat as literal
                    result.append("${" + template[i:])
                    break
                inner = template[i:brace_end]
                fields = [f.strip() for f in inner.split(",")]
                value = _resolve_fallback(node, fields, utc)
                result.append(str(value) if value is not None else "")
                i = brace_end + 1  # skip '}'
            else:
                # $var — single variable
                start = i
                while i < n and (template[i].isalnum() or template[i] == "_"):
                    i += 1
                var_name = template[start:i]
                value = _resolve_single(node, var_name, utc)
                result.append(str(value) if value is not None else "")
        else:
            result.append(ch)
            i += 1

    return "".join(result)


def _resolve_fallback(node: object, fields: list[str], utc: bool = False) -> str:
    """Try each field in order, return the first non-None, non-empty value."""
    for field in fields:
        if field in ("add_date_iso", "add_date_utc"):
            val = _resolve_single(node, field, utc)
            if val:
                return str(val)
        else:
            val = _resolve_field(node, field)
            if val is not None and val != "":
                return str(val)
    return ""


def _resolve_single(node: object, name: str, utc: bool = False) -> Any:
    """Resolve a single variable name, including computed ones."""
    # Computed: date format variables
    if name == "add_date_iso":
        ts = _resolve_field(node, "add_date")
        if ts and ts > 0:
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            if not utc:
                dt = dt.astimezone()
            return dt.isoformat()
        return ""
    elif name == "add_date_utc":
        ts = _resolve_field(node, "add_date")
        if ts and ts > 0:
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            return dt.isoformat()
        return ""

    # Standard fields
    return _resolve_field(node, name)
