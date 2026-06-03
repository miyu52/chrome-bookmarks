"""Tests for chrome-bookmarks parser, filter, template, and output."""

import json
import pytest

from chrome_bookmarks.parser import parse, BookmarkParseError
from chrome_bookmarks.model import BookmarkNode, FolderNode, SeparatorNode, Root
from chrome_bookmarks.template import render
from chrome_bookmarks.filter import Filter, BookmarkFilterError


FIXTURE = "tests/fixtures/sample.html"


# ── Parser ──────────────────────────────────────────────

def test_parse_returns_root():
    tree = parse(FIXTURE)
    assert isinstance(tree, Root)
    assert tree.total == 7
    assert len(tree.roots) == 2
    assert tree.roots[0].name == "书签栏"
    assert tree.roots[1].name == "其他书签"


def test_parse_folder_structure():
    tree = parse(FIXTURE)
    书签栏 = tree.roots[0]
    assert len(书签栏.children) == 3  # 编程, 工具, 闲置项目
    编程 = 书签栏.children[0]
    assert 编程.name == "编程"
    assert len(编程.children) == 4  # 3 bookmarks + 1 separator


def test_parse_bookmark_fields():
    tree = parse(FIXTURE)
    bm = tree.roots[0].children[0].children[0]  # Python 官方文档
    assert isinstance(bm, BookmarkNode)
    assert bm.title == "Python 官方文档"
    assert bm.url == "https://docs.python.org/3/"
    assert bm.add_date == 1705478400
    assert bm.icon == "data:image/png;base64,xxx"
    assert bm.folder_path == "书签栏/编程"
    assert bm.depth == 2


def test_parse_separator():
    tree = parse(FIXTURE)
    sep = tree.roots[0].children[0].children[2]  # separator
    assert isinstance(sep, SeparatorNode)
    assert sep.type == "separator"


def test_parse_empty_folder():
    tree = parse(FIXTURE)
    empty = tree.roots[0].children[2]  # 闲置项目
    assert empty.name == "闲置项目"
    assert len(empty.children) == 0


def test_parse_non_bookmark_file():
    import tempfile, os
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
        f.write("<html><body>Not a bookmark file</body></html>")
        path = f.name
    try:
        with pytest.raises(BookmarkParseError):
            parse(path)
    finally:
        os.unlink(path)


def test_parse_nonexistent_file():
    with pytest.raises(FileNotFoundError):
        parse("/nonexistent/file.html")


# ── Template ────────────────────────────────────────────

def test_template_bookmark_title():
    bm = BookmarkNode(title="Test", url="http://x.com", folder_path="A/B")
    assert render(bm, "$title") == "Test"
    assert render(bm, "$name") == ""
    assert render(bm, "${title,name}") == "Test"


def test_template_folder_name():
    f = FolderNode(name="MyFolder", folder_path="A")
    assert render(f, "$name") == "MyFolder"
    assert render(f, "$title") == ""
    assert render(f, "${title,name}") == "MyFolder"


def test_template_fallback_chain():
    bm = BookmarkNode(title="T", url="http://x.com", folder_path="A")
    assert render(bm, "${name,title}") == "T"  # name empty, fallback to title


def test_template_date_iso():
    bm = BookmarkNode(title="T", url="http://x.com", add_date=1705478400, folder_path="A")
    iso = render(bm, "$add_date_iso")
    assert "2024-01-17" in iso


def test_template_with_literals():
    bm = BookmarkNode(title="T", url="http://x.com", folder_path="A/B")
    result = render(bm, "| $folder | ${title,name} | $url |")
    assert result == "| A/B | T | http://x.com |"


# ── Filter ──────────────────────────────────────────────

def test_filter_domain():
    tree = parse(FIXTURE)
    f = Filter("domain=github.com")
    r = f.apply(tree)
    assert r.total == 2

    # Collect all bookmarks
    bookmarks = []
    for root in r.roots:
        for node in root.flatten():
            if isinstance(node, BookmarkNode):
                bookmarks.append(node)
    assert len(bookmarks) == 2
    assert all("github.com" in bm.url for bm in bookmarks)


def test_filter_type_bookmark():
    tree = parse(FIXTURE)
    r = tree.filter("type=bookmark")
    # All bookmarks should be present (folder structure dissolved)
    assert r.total == 7


def test_filter_search_case_insensitive():
    tree = parse(FIXTURE)
    r = tree.filter("search=*python*")
    bookmarks = []
    for root in r.roots:
        for node in root.flatten():
            if isinstance(node, BookmarkNode):
                bookmarks.append(node)
    assert len(bookmarks) == 2
    titles = {bm.title for bm in bookmarks}
    assert "Python 官方文档" in titles
    assert "Python Docs (dup)" in titles


def test_filter_regex():
    tree = parse(FIXTURE)
    r = tree.filter("search=~(?i)python")
    bookmarks = []
    for root in r.roots:
        for node in root.flatten():
            if isinstance(node, BookmarkNode):
                bookmarks.append(node)
    assert len(bookmarks) == 2


def test_filter_folder_glob():
    tree = parse(FIXTURE)
    r = tree.filter("folder=书签栏/工具")
    bookmarks = []
    for root in r.roots:
        for node in root.flatten():
            if isinstance(node, BookmarkNode):
                bookmarks.append(node)
    assert len(bookmarks) == 2  # 工具 A, Mozilla on GitHub


def test_filter_prune_empty():
    tree = parse(FIXTURE)
    r = tree.filter("folder=书签栏/工具,prune_empty=true")
    # Should only have the 工具 folder (no 编程 or 闲置项目)
    assert len(r.roots) == 1
    assert r.roots[0].name == "书签栏"
    assert len(r.roots[0].children) == 1
    assert r.roots[0].children[0].name == "工具"


def test_filter_invalid_key():
    with pytest.raises(BookmarkFilterError):
        Filter("invalid_key=foo")


# ── Output ──────────────────────────────────────────────

def test_output_json():
    tree = parse(FIXTURE)
    j = tree.to_json()
    data = json.loads(j)
    assert data["version"] == "1.0"
    assert data["total"] == 7
    assert len(data["roots"]) == 2


def test_output_json_flatten():
    tree = parse(FIXTURE)
    j = tree.to_json(flatten=True)
    data = json.loads(j)
    assert isinstance(data, list)
    assert len(data) > 0
    # bookmark should have folder field
    bookmarks = [d for d in data if d["type"] == "bookmark"]
    assert len(bookmarks) == 7
    assert "folder" in bookmarks[0]


def test_output_markdown():
    tree = parse(FIXTURE)
    md = tree.to_markdown()
    assert "# 书签栏" in md
    assert "[Python 官方文档]" in md
    assert "https://docs.python.org/3/" in md


def test_output_markdown_compact():
    tree = parse(FIXTURE)
    md = tree.to_markdown(compact=True)
    assert "[Python 官方文档](https://docs.python.org/3/)" in md
    # No separator in compact mode
    assert "* * *" not in md


def test_output_tree():
    tree = parse(FIXTURE)
    t = tree.to_tree()
    assert "📁 书签栏" in t
    assert "🔖 Python 官方文档" in t
    assert "───" in t


def test_output_tree_ascii():
    tree = parse(FIXTURE)
    t = tree.to_tree(ascii=True)
    assert "[+] 书签栏" in t
    assert "[*] Python 官方文档" in t
    assert "📁" not in t


def test_output_fields():
    tree = parse(FIXTURE)
    fields = tree.to_fields("${title,name}")
    lines = fields.split("\n")
    assert len(lines) > 0
    assert "Python 官方文档" in lines
