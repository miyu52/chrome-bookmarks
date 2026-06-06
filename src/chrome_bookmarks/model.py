"""Data model for Chrome bookmarks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chrome_bookmarks.filter import Filter


@dataclass
class BookmarkNode:
    """A single bookmark."""

    title: str
    url: str
    add_date: int = 0
    last_modified: int = 0
    icon: str = ""
    folder_path: str = ""
    depth: int = 0

    def __post_init__(self) -> None:
        self._type: str = "bookmark"

    @property
    def type(self) -> str:
        return self._type


@dataclass
class SeparatorNode:
    """A separator line."""

    folder_path: str = ""
    depth: int = 0
    _type: str = field(default="separator", init=False)

    @property
    def type(self) -> str:
        return self._type


@dataclass
class FolderNode:
    """A folder containing children (bookmarks, separators, or sub-folders)."""

    name: str
    add_date: int = 0
    last_modified: int = 0
    children: list[FolderOrBookmark] = field(default_factory=list)
    folder_path: str = ""
    depth: int = 0

    def __post_init__(self) -> None:
        self._type: str = "folder"

    @property
    def type(self) -> str:
        return self._type

    def iter_nodes(self):
        """Yield self and all descendants depth-first."""
        yield self
        for child in self.children:
            if isinstance(child, FolderNode):
                yield from child.iter_nodes()
            else:
                yield child

    def flatten(self) -> list[FolderOrBookmark]:
        """Return a flat list of all descendant nodes in pre-order (parent before children)."""
        result: list[FolderOrBookmark] = []
        for child in self.children:
            result.append(child)
            if isinstance(child, FolderNode):
                result.extend(child.flatten())
        return result

    def __repr__(self) -> str:
        return f"FolderNode(name={self.name!r}, children={len(self.children)})"


# Union type for any node that can appear inside a folder
FolderOrBookmark = BookmarkNode | FolderNode | SeparatorNode


@dataclass
class Root:
    """Top-level result of parsing a bookmarks file."""

    roots: list[FolderNode]
    source: str | None = None
    total: int = 0
    parsed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def filter(self, filter_spec: str | None = None, **kwargs) -> Root:
        """Apply a filter, returning a new Root.

        Accepts either a filter string spec or keyword args.
        Keyword args are forwarded to Filter.apply() directly.
        """
        from chrome_bookmarks.filter import Filter  # late import to avoid circular

        f = Filter(filter_spec)
        # Merge keyword args into the filter
        for key, value in kwargs.items():
            setattr(f, key, value)
        return f.apply(self)

    def to_json(self, flatten: bool = False, utc: bool = False) -> str:
        from chrome_bookmarks.output import format_json

        return format_json(self, flatten=flatten, utc=utc)

    def to_markdown(
        self, verbose: bool = False, compact: bool = False
    ) -> str:
        from chrome_bookmarks.output import format_markdown

        return format_markdown(self, verbose=verbose, compact=compact)

    def to_tree(self, ascii: bool = False) -> str:
        from chrome_bookmarks.output import format_tree

        return format_tree(self, ascii=ascii)

    def to_fields(self, template: str, utc: bool = False) -> str:
        from chrome_bookmarks.output import format_fields

        return format_fields(self, template=template, utc=utc)

    def to_template(self, template_spec: str) -> str:
        """Render with a Jinja2 template.

        Args:
            template_spec: Template name (e.g. "markdown-table") or file path.

        Returns:
            Rendered string.
        """
        from chrome_bookmarks.output import format_template

        return format_template(self, template_spec)

    def iter_nodes(self):
        """Yield all nodes in all roots, depth-first."""
        for root_folder in self.roots:
            yield from root_folder.iter_nodes()

    def __repr__(self) -> str:
        return f"Root(roots={len(self.roots)}, total={self.total})"
