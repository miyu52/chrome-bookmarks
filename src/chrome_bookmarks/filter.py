"""Filter and prune the bookmark tree."""

from __future__ import annotations

import fnmatch
import re
from copy import deepcopy
from urllib.parse import urlparse

from chrome_bookmarks.model import (
    BookmarkNode,
    FolderNode,
    Root,
    SeparatorNode,
    FolderOrBookmark,
)


class BookmarkFilterError(Exception):
    """Raised when a filter expression is invalid."""


class Filter:
    """Filter that applies conditions to a Root and returns a filtered copy.

    Supports:
        filter_spec="key=value,key2=value2"
        Keywords: folder, domain, search, type, url
        Matching: glob by default, ~prefix for regex, domain uses exact+subdomain
    """

    def __init__(self, spec: str | None = None):
        self.folder: str | None = None
        self.domain: str | None = None
        self.search: str | None = None
        self.type: str | None = None
        self.url: str | None = None
        self.prune_empty: bool = False

        if spec:
            self._parse(spec)

    def _parse(self, spec: str) -> None:
        """Parse a comma-separated filter string: 'key=value,key2=value2'"""
        # Simple split on commas, but be careful with commas in regex patterns
        pairs = _split_filter_pairs(spec)
        for key, value in pairs:
            key = key.strip().lower()
            value = value.strip()
            if key == "folder":
                self.folder = value
            elif key == "domain":
                self.domain = value
            elif key == "search":
                self.search = value
            elif key == "type":
                self.type = value
            elif key == "url":
                self.url = value
            elif key == "prune_empty" or key == "prune-empty":
                self.prune_empty = value.lower() in ("true", "1", "yes")
            else:
                raise BookmarkFilterError(
                    f"不支持的过滤键: '{key}'。支持的键: folder, domain, search, type, url, prune_empty"
                )

    def apply(self, root: Root) -> Root:
        """Apply this filter to a Root, returning a new filtered Root."""
        filtered_roots: list[FolderNode] = []
        total = 0
        orphan_bookmarks: list[BookmarkNode] = []

        for root_folder in root.roots:
            result = self._filter_folder(root_folder)
            if result is not None:
                if isinstance(result, list):
                    # Folder was dissolved — collect bookmarks and sub-folders
                    for item in result:
                        if isinstance(item, FolderNode):
                            filtered_roots.append(item)
                            total += self._count_bookmarks(item)
                        elif isinstance(item, BookmarkNode):
                            orphan_bookmarks.append(item)
                            total += 1
                elif isinstance(result, FolderNode):
                    filtered_roots.append(result)
                    total += self._count_bookmarks(result)

        # If all folders were dissolved but we have orphan bookmarks,
        # wrap them in a synthetic folder so the Root model stays valid
        if orphan_bookmarks and not filtered_roots:
            filtered_roots.append(
                FolderNode(
                    name="(全部书签)",
                    children=list(orphan_bookmarks),
                    folder_path="",
                    depth=0,
                )
            )

        return Root(
            roots=filtered_roots,
            source=root.source,
            total=total,
        )

    def _filter_folder(self, folder: FolderNode) -> FolderNode | list[FolderOrBookmark] | None:
        """Filter a folder's children.

        Returns:
            FolderNode if folder is kept (with filtered children).
            list if folder is dissolved — children promoted upward.
            None if folder and all children are pruned.
        """
        # If type filter explicitly excludes folders, dissolve: promote children up
        if not self._match_type("folder"):
            dissolved: list[FolderOrBookmark] = []
            for child in folder.children:
                if isinstance(child, FolderNode):
                    sub = self._filter_folder(child)
                    if isinstance(sub, FolderNode):
                        dissolved.append(sub)
                    elif isinstance(sub, list):
                        dissolved.extend(sub)
                    # None → skip
                elif isinstance(child, BookmarkNode):
                    if self._match_bookmark(child):
                        dissolved.append(deepcopy(child))
                elif isinstance(child, SeparatorNode):
                    pass  # Separators are meaningless without folder structure
            return dissolved if dissolved else None

        # Folder type is allowed — keep folder structure, filter children
        filtered_children: list[FolderOrBookmark] = []

        for child in folder.children:
            if isinstance(child, FolderNode):
                sub = self._filter_folder(child)
                if sub is not None:
                    filtered_children.append(sub)
            elif isinstance(child, BookmarkNode):
                if self._match_bookmark(child):
                    filtered_children.append(deepcopy(child))
            elif isinstance(child, SeparatorNode):
                # Only keep separators if no active content filter (domain/search/url)
                # Separators are structural; they stay only in unfiltered tree views
                if not self._has_content_filter():
                    filtered_children.append(deepcopy(child))

        # Prune empty folders if requested
        if self.prune_empty and not filtered_children:
            return None

        # Check if folder itself matches type filter
        if not self._match_type("folder") and not self.prune_empty:
            # Folder type is excluded, but we might still need it as container
            # For type=bookmark, we still keep folder structure
            pass

        # Create filtered folder
        new_folder = FolderNode(
            name=folder.name,
            add_date=getattr(folder, "add_date", 0),
            last_modified=getattr(folder, "last_modified", 0),
            children=filtered_children,
            folder_path=folder.folder_path,
            depth=folder.depth,
        )
        return new_folder

    def _match_bookmark(self, bookmark: BookmarkNode) -> bool:
        """Check if a bookmark matches all active filters."""
        if not self._match_type("bookmark"):
            return False
        if self.search and not self._match_pattern(self.search, bookmark.title, case_insensitive=True):
            return False
        if self.url and not self._match_pattern(self.url, bookmark.url):
            return False
        if self.folder and not self._match_pattern(self.folder, bookmark.folder_path):
            return False
        if self.domain and not self._match_domain(self.domain, bookmark.url):
            return False
        return True

    def _match_type(self, expected: str) -> bool:
        """Check if the expected type passes the type filter."""
        if self.type is None:
            return True
        allowed = [t.strip() for t in self.type.split(",")]
        return expected in allowed

    def _has_content_filter(self) -> bool:
        """Check if any content-based filter is active (domain, search, url, folder).
        Content filters should remove non-matching items including separators."""
        return bool(self.domain or self.search or self.url or self.folder)

    def _match_pattern(self, pattern: str, text: str, case_insensitive: bool = False) -> bool:
        """Match a pattern against text. ~prefix = regex, default = glob."""
        if pattern.startswith("~"):
            try:
                flags = re.IGNORECASE if case_insensitive else 0
                return bool(re.search(pattern[1:], text, flags))
            except re.error as e:
                raise BookmarkFilterError(f"无效的正则表达式: '{pattern}' — {e}")
        # fnmatch with case-insensitive support
        if case_insensitive:
            return fnmatch.fnmatch(text.lower(), pattern.lower())
        return fnmatch.fnmatch(text, pattern)

    def _match_domain(self, pattern: str, url: str) -> bool:
        """Match a domain pattern. Exact match or subdomain suffix match."""
        if not url:
            return False
        try:
            hostname = urlparse(url).hostname or ""
        except Exception:
            return False
        if not hostname:
            return False

        # Exact match
        if hostname == pattern:
            return True
        # Subdomain match: *.domain
        if hostname.endswith("." + pattern):
            return True
        return False

    def _count_bookmarks(self, folder: FolderNode) -> int:
        """Count bookmarks in a folder tree."""
        count = 0
        for child in folder.children:
            if isinstance(child, BookmarkNode):
                count += 1
            elif isinstance(child, FolderNode):
                count += self._count_bookmarks(child)
        return count


def _split_filter_pairs(spec: str) -> list[tuple[str, str]]:
    """Split a filter spec string into key=value pairs.

    Commas separate top-level pairs only when followed by a key= pattern.
    Values can contain commas (e.g. type=bookmark,folder).
    """
    pairs: list[tuple[str, str]] = []
    i = 0
    n = len(spec)
    current_start = 0
    in_quotes: str | None = None

    while i < n:
        ch = spec[i]
        if in_quotes:
            if ch == in_quotes:
                in_quotes = None
        elif ch == '"' or ch == "'":
            in_quotes = ch
        elif ch == ",":
            # Only split if what follows looks like a new key=value pair
            rest = spec[i + 1:].lstrip()
            if "=" in rest:
                # Check if there's a = before the next comma (or end)
                next_comma = rest.find(",")
                eq_pos = rest.find("=")
                if eq_pos != -1 and (next_comma == -1 or eq_pos < next_comma):
                    # This comma separates two key=value pairs
                    pair = spec[current_start:i].strip()
                    if pair and "=" in pair:
                        key, val = pair.split("=", 1)
                        pairs.append((key.strip(), val.strip().strip('"').strip("'")))
                    current_start = i + 1
        i += 1

    # Last pair
    pair = spec[current_start:].strip()
    if pair and "=" in pair:
        key, val = pair.split("=", 1)
        pairs.append((key.strip(), val.strip().strip('"').strip("'")))

    return pairs
