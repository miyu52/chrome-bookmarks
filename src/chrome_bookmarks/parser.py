"""Parse Chrome/Netscape bookmark HTML files using BeautifulSoup."""

from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup, Tag

from chrome_bookmarks.model import BookmarkNode, FolderNode, Root, SeparatorNode


class BookmarkParseError(Exception):
    """Raised when the input is not a valid Chrome/Netscape bookmark file."""


def _parse_folder(dl: Tag, parent_path: str = "", depth: int = 0) -> list[FolderNode | BookmarkNode | SeparatorNode]:
    """Parse a <DL> element's children into a list of nodes."""
    nodes: list[FolderNode | BookmarkNode | SeparatorNode] = []

    for dt in dl.find_all("dt", recursive=False):
        # Find the first meaningful child element
        child = dt.find(["h3", "a", "hr"], recursive=False)

        if child is None:
            continue

        tag = child.name

        if tag == "h3":
            # Folder
            name = child.get_text(strip=True)
            folder_path = f"{parent_path}/{name}" if parent_path else name
            add_date = _parse_int(child.get("add_date", "0"))
            last_modified = _parse_int(child.get("last_modified", "0"))

            # The folder's contents are in the next <DL> sibling
            sub_dl = dt.find("dl", recursive=False)
            children: list[FolderNode | BookmarkNode | SeparatorNode] = []
            if sub_dl:
                children = _parse_folder(sub_dl, folder_path, depth + 1)

            nodes.append(
                FolderNode(
                    name=name,
                    add_date=add_date,
                    last_modified=last_modified,
                    children=children,
                    folder_path=folder_path,
                    depth=depth,
                )
            )

        elif tag == "a":
            # Bookmark
            title = child.get_text(strip=True)
            url = child.get("href", "")
            add_date = _parse_int(child.get("add_date", "0"))
            last_modified = _parse_int(child.get("last_modified", "0"))
            icon = child.get("icon", "")

            nodes.append(
                BookmarkNode(
                    title=title,
                    url=url,
                    add_date=add_date,
                    last_modified=last_modified,
                    icon=icon,
                    folder_path=parent_path,
                    depth=depth,
                )
            )

        elif tag == "hr":
            # Separator
            nodes.append(
                SeparatorNode(
                    folder_path=parent_path,
                    depth=depth,
                )
            )

    return nodes


def _parse_int(value: str) -> int:
    """Parse a string to int, returning 0 on failure."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def parse(filepath: str) -> Root:
    """Parse a Chrome/Netscape bookmarks HTML file.

    Args:
        filepath: Path to the bookmarks.html file.

    Returns:
        Root object containing all parsed bookmark data.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        BookmarkParseError: If the file isn't a valid bookmarks file.
    """
    try:
        with open(filepath, "rb") as f:
            raw = f.read()
    except FileNotFoundError:
        raise

    # Let bs4 auto-detect encoding. Try html5lib (best for nested DT/DL),
    # fall back to html.parser.
    for parser_name in ("html5lib", "html.parser"):
        try:
            soup = BeautifulSoup(raw, parser_name)
            break
        except Exception:
            continue
    else:
        soup = BeautifulSoup(raw, "html.parser")

    # Check for the DOCTYPE marker (bs4 stores it as a Doctype object in soup.contents)
    from bs4 import Doctype
    doctype = None
    for item in soup.contents:
        if isinstance(item, Doctype):
            doctype = item
            break

    if doctype is None or "NETSCAPE" not in str(doctype).upper():
        raise BookmarkParseError(
            "输入不是有效的 Chrome/Netscape bookmarks 文件：缺少 DOCTYPE 声明"
        )

    # Find all top-level folders (direct children of the root <DL>)
    root_dl = soup.find("dl")
    if root_dl is None:
        raise BookmarkParseError(
            "输入不是有效的 bookmarks 文件：缺少 <DL> 根结构"
        )

    roots = _parse_folder(root_dl, parent_path="", depth=0)

    # Count total bookmarks
    total = 0

    def count_bookmarks(node):
        nonlocal total
        if isinstance(node, BookmarkNode):
            total += 1
        elif isinstance(node, FolderNode):
            for child in node.children:
                count_bookmarks(child)

    for root_folder in roots:
        count_bookmarks(root_folder)

    return Root(
        roots=roots,
        source=filepath,
        total=total,
        parsed_at=datetime.now(timezone.utc),
    )
