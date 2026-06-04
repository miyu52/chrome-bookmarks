"""CLI entry point for chrome-bookmarks."""

from __future__ import annotations

import argparse
import sys

from chrome_bookmarks.filter import BookmarkFilterError
from chrome_bookmarks.parser import BookmarkParseError, parse


def _ensure_utf8() -> None:
    """Reconfigure stdout/stderr to UTF-8 on Windows to avoid garbled output.

    On Windows git-bash/mintty, the terminal uses UTF-8 but Python defaults
    to the system code page (e.g. cp936), causing Chinese text to appear
    garbled. This forces UTF-8 for interactive terminals.
    """
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def main() -> None:
    _ensure_utf8()

    parser = argparse.ArgumentParser(
        prog="chrome-bookmarks",
        description="解析 Chrome/Netscape 导出的 bookmarks.html 文件",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # parse 子命令
    parse_cmd = subparsers.add_parser("parse", help="解析书签文件")
    parse_cmd.add_argument("file", help="bookmarks.html 文件路径")
    parse_cmd.add_argument(
        "-o", "--output",
        default="tree",
        help=(
            "输出格式: json, markdown, tree, fields=<模板>。"
            "fields 模板示例: '$folder,${title,name},$url'"
        ),
    )
    parse_cmd.add_argument(
        "--flatten",
        action="store_true",
        help="JSON 输出扁平化（仅 -o json 时有效）",
    )
    parse_cmd.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Markdown 输出详细信息",
    )
    parse_cmd.add_argument(
        "--compact", "-q",
        action="store_true",
        help="Markdown 输出精简模式",
    )
    parse_cmd.add_argument(
        "--ascii",
        action="store_true",
        help="Tree 输出纯 ASCII 字符",
    )
    parse_cmd.add_argument(
        "--utc",
        action="store_true",
        help="日期时间使用 UTC",
    )
    parse_cmd.add_argument(
        "--prefix",
        default=None,
        help="输出前缀文本，支持 $变量 语法",
    )
    parse_cmd.add_argument(
        "--filter",
        action="append",
        default=None,
        dest="filters",
        help=(
            "过滤条件（可多次使用）。格式: key=value[,key=value]。"
            "键: folder (glob/~regex), domain (精确域名), search (glob/~regex, 不区分大小写), "
            "type (bookmark/folder/separator), url (glob/~regex), prune_empty (true/false)。"
            "多条件为 AND 逻辑。"
        ),
    )

    args = parser.parse_args()

    # Parse output format
    output_fmt = args.output
    fields_template = ""
    if output_fmt.startswith("fields="):
        fields_template = output_fmt[len("fields="):]
        output_fmt = "fields"
    if output_fmt not in ("json", "markdown", "tree", "fields"):
        print(f"错误: 不支持的输出格式 — {output_fmt}", file=sys.stderr)
        sys.exit(1)

    # Parse the file
    try:
        tree = parse(args.file)
    except FileNotFoundError:
        print(f"错误: 文件不存在 — {args.file}", file=sys.stderr)
        sys.exit(1)
    except BookmarkParseError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)

    # Apply filters
    if args.filters:
        merged_spec = ",".join(args.filters)
        try:
            tree = tree.filter(merged_spec)
        except BookmarkFilterError as e:
            print(f"错误: {e}", file=sys.stderr)
            sys.exit(1)

    # Print prefix if specified
    if args.prefix:
        from chrome_bookmarks.template import render
        from chrome_bookmarks.model import BookmarkNode
        dummy = BookmarkNode(title="", url="", folder_path="")
        # Handle \n, \t escape sequences in prefix
        prefix_text = args.prefix.replace("\\n", "\n").replace("\\t", "\t")
        prefix_text = render(dummy, prefix_text, utc=args.utc)
        print(prefix_text)

    # Generate output
    try:
        output = _format_output(tree, output_fmt, fields_template, args)
    except Exception as e:
        print(f"错误: 输出生成失败 — {e}", file=sys.stderr)
        sys.exit(1)

    print(output)


def _format_output(tree, fmt: str, fields_template: str, args) -> str:
    """Format the tree according to CLI args."""
    if fmt == "json":
        return tree.to_json(flatten=args.flatten, utc=args.utc)
    elif fmt == "markdown":
        return tree.to_markdown(verbose=args.verbose, compact=args.compact)
    elif fmt == "tree":
        return tree.to_tree(ascii=args.ascii)
    elif fmt == "fields":
        if not fields_template:
            print("错误: -o fields 需要指定模板，例如: -o 'fields=$folder,${title,name},$url'", file=sys.stderr)
            sys.exit(1)
        return tree.to_fields(template=fields_template, utc=args.utc)

    return tree.to_tree()


if __name__ == "__main__":
    main()
