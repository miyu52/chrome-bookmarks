"""Output formatters: json, markdown, tree, fields."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from chrome_bookmarks.model import BookmarkNode, FolderNode, Root, SeparatorNode
from chrome_bookmarks.template import render as render_template


def _node_to_dict(node: object, utc: bool = False) -> dict:
    """Convert a single node to a dictionary for JSON serialization."""
    d: dict = {"type": node.type}

    if isinstance(node, BookmarkNode):
        d.update({
            "title": node.title,
            "url": node.url,
            "folder": node.folder_path,
            "depth": node.depth,
        })
        if node.add_date:
            d["add_date"] = node.add_date
            d["add_date_iso"] = _ts_to_iso(node.add_date, utc)
        if node.last_modified:
            d["last_modified"] = node.last_modified
        if node.icon:
            d["icon"] = node.icon
    elif isinstance(node, FolderNode):
        d["name"] = node.name
        d["folder"] = node.folder_path
        d["depth"] = node.depth
        if node.add_date:
            d["add_date"] = node.add_date
            d["add_date_iso"] = _ts_to_iso(node.add_date, utc)
        if node.last_modified:
            d["last_modified"] = node.last_modified
        d["children"] = [_node_to_dict(c, utc) for c in node.children]
    elif isinstance(node, SeparatorNode):
        d["folder"] = node.folder_path
        d["depth"] = node.depth

    return d


def _ts_to_iso(ts: int, utc: bool = False) -> str:
    """Convert a Unix timestamp to ISO 8601 string."""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    if not utc:
        dt = dt.astimezone()
    return dt.isoformat()


def format_json(root: Root, flatten: bool = False, utc: bool = False) -> str:
    """Format a Root as JSON.

    Args:
        flatten: If True, output a flat array of all nodes.
        utc: If True, output dates in UTC instead of local time.
    """
    if flatten:
        nodes = []
        for rf in root.roots:
            nodes.extend(_flatten_to_dicts(rf, utc))
        return json.dumps(nodes, ensure_ascii=False, indent=2)

    data = {
        "version": "1.0",
        "source": root.source,
        "total": root.total,
    }
    data["roots"] = [_node_to_dict(rf, utc) for rf in root.roots]
    return json.dumps(data, ensure_ascii=False, indent=2)


def _flatten_to_dicts(folder: FolderNode, utc: bool = False) -> list[dict]:
    """Flatten a folder tree to a list of node dicts."""
    result: list[dict] = []
    for child in folder.children:
        d = _node_to_dict(child, utc)
        if isinstance(child, FolderNode):
            # Remove children from flattened output, add children_count instead
            children_count = len(child.children)
            d.pop("children", None)
            if children_count == 0:
                d["name"] = f"{child.name} (空)"
            d["children_count"] = children_count
        result.append(d)
        if isinstance(child, FolderNode):
            result.extend(_flatten_to_dicts(child, utc))
    return result


def format_markdown(root: Root, verbose: bool = False, compact: bool = False) -> str:
    """Format a Root as Markdown.

    Args:
        verbose: Show extra metadata (dates, paths).
        compact: Minimal output — just title + link, no separators, no dates.
    """
    lines: list[str] = []
    for i, rf in enumerate(root.roots):
        if i > 0:
            lines.append("")
        _format_markdown_folder(rf, lines, depth=0, verbose=verbose, compact=compact)
    return "\n".join(lines)


def _format_markdown_folder(
    folder: FolderNode,
    lines: list[str],
    depth: int,
    verbose: bool = False,
    compact: bool = False,
) -> None:
    """Recursively format a folder as Markdown list items."""
    is_empty = len(folder.children) == 0

    if depth == 0:
        lines.append(f"# {folder.name}")
    else:
        prefix = "  " * (depth - 1) + "- "
        name = folder.name
        if is_empty:
            name += " *(空)*"
        lines.append(f"{prefix}{name}")

    for child in folder.children:
        if isinstance(child, BookmarkNode):
            prefix = "  " * depth + "- "
            if verbose:
                lines.append(f"{prefix}[{child.title}]({child.url})")
                lines.append(f"{'  ' * (depth + 1)}`{child.folder_path}`")
                if child.add_date:
                    lines.append(f"{'  ' * (depth + 1)}添加: {_ts_to_iso(child.add_date)}")
            else:
                line = f"{prefix}[{child.title}]({child.url})"
                if not compact and child.add_date:
                    line += f" `{_ts_to_date_short(child.add_date)}`"
                lines.append(line)

        elif isinstance(child, SeparatorNode):
            if not compact:
                prefix = "  " * depth + "- "
                lines.append(f"{prefix}* * *")

        elif isinstance(child, FolderNode):
            _format_markdown_folder(child, lines, depth + 1, verbose, compact)


def _ts_to_date_short(ts: int) -> str:
    """Convert timestamp to short date string YYYY-MM-DD."""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone()
    return dt.strftime("%Y-%m-%d")


def format_tree(root: Root, ascii: bool = False) -> str:
    """Format a Root as an ASCII/emoji tree."""
    if ascii:
        folder_icon = "[+]"
        bookmark_icon = "[*]"
        sep_icon = "---"
        pipe = "|"
        tee = "+"
        last = "\\"
        indent_pipe = "|   "
        indent_blank = "    "
    else:
        folder_icon = "📁"
        bookmark_icon = "🔖"
        sep_icon = "───"
        pipe = "│"
        tee = "├──"
        last = "└──"
        indent_pipe = "│   "
        indent_blank = "    "

    lines: list[str] = []
    for i, rf in enumerate(root.roots):
        is_last = i == len(root.roots) - 1
        _format_tree_folder(rf, lines, "", is_last, ascii, folder_icon,
                           bookmark_icon, sep_icon, pipe, tee, last,
                           indent_pipe, indent_blank)
    return "\n".join(lines)


def _format_tree_folder(
    folder: FolderNode,
    lines: list[str],
    prefix: str,
    is_last: bool,
    ascii: bool,
    folder_icon: str,
    bookmark_icon: str,
    sep_icon: str,
    pipe: str,
    tee: str,
    last_char: str,
    indent_pipe: str,
    indent_blank: str,
) -> None:
    """Recursively format a folder node for tree output."""
    branch = last_char if is_last else tee
    label = folder.name
    if len(folder.children) == 0:
        label += " (空)"

    lines.append(f"{prefix}{branch} {folder_icon} {label}")

    child_prefix = prefix + (indent_blank if is_last else indent_pipe)

    children = list(folder.children)
    for i, child in enumerate(children):
        child_is_last = i == len(children) - 1

        if isinstance(child, BookmarkNode):
            branch = last_char if child_is_last else tee
            url = child.url
            if len(url) > 60:
                url = url[:57] + "..."
            lines.append(
                f"{child_prefix}{branch} {bookmark_icon} {child.title}  {url}"
            )

        elif isinstance(child, SeparatorNode):
            branch = last_char if child_is_last else tee
            lines.append(f"{child_prefix}{branch} {sep_icon}")

        elif isinstance(child, FolderNode):
            _format_tree_folder(
                child, lines, child_prefix, child_is_last, ascii,
                folder_icon, bookmark_icon, sep_icon, pipe, tee, last_char,
                indent_pipe, indent_blank,
            )


def format_fields(root: Root, template: str, utc: bool = False) -> str:
    """Format all nodes using a template string.

    Each node becomes one line. Nodes are traversed depth-first across all roots.
    """
    lines: list[str] = []
    for rf in root.roots:
        for node in rf.iter_nodes():
            # Skip the root folder itself in iter_nodes
            # iter_nodes yields all descendants
            pass
        for node in rf.flatten():
            rendered = render_template(node, template, utc)
            lines.append(rendered)
    return "\n".join(lines)


def format_template(root: Root, template_spec: str) -> str:
    """Render the bookmark tree with a Jinja2 template.

    Args:
        root: Parsed bookmark tree.
        template_spec: Template name (e.g. "markdown-table") or path
                       (e.g. "~/my-template.j2").

    Returns:
        Rendered string.
    """
    from chrome_bookmarks.template_engine import render_template as render_j2

    return render_j2(root, template_spec)
