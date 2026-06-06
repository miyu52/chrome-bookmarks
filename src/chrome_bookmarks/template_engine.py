"""Jinja2 template rendering for bookmark output.

Lazy-loads jinja2 so it's only imported when template output is used.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from chrome_bookmarks.model import Root

if TYPE_CHECKING:
    pass


# Map of built-in template names to their source strings.
# Templates live as files under templates/ but we also keep them
# as inline strings here for zero-config package data loading.
_BUILTIN_TEMPLATES: dict[str, str] = {}


def _load_builtins() -> None:
    """Load built-in .j2 templates from the package directory."""
    if _BUILTIN_TEMPLATES:
        return
    tmpl_dir = Path(__file__).parent / "templates"
    if tmpl_dir.is_dir():
        for f in sorted(tmpl_dir.glob("*.j2")):
            name = f.stem  # e.g. "markdown-table"
            _BUILTIN_TEMPLATES[name] = f.read_text(encoding="utf-8")


def list_builtin_templates() -> list[str]:
    """Return names of available built-in templates."""
    _load_builtins()
    return list(_BUILTIN_TEMPLATES.keys())


def _get_template_source(name_or_path: str) -> str:
    """Resolve a template specifier to source text.

    Priority: built-in name match → file path.
    """
    _load_builtins()
    if name_or_path in _BUILTIN_TEMPLATES:
        return _BUILTIN_TEMPLATES[name_or_path]
    return Path(name_or_path).read_text(encoding="utf-8")


def _date_fmt(ts: int, fmt: str = "%Y%m%d") -> str:
    """Jinja2 filter: format a Unix timestamp as a date string."""
    if ts and ts > 0:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone()
        return dt.strftime(fmt)
    return ""


def render_template(root: Root, template_spec: str) -> str:
    """Render a Root with a Jinja2 template.

    Args:
        root: Parsed bookmark tree.
        template_spec: Template name (e.g. "markdown-table") or file path
                       (e.g. "~/my-template.j2").

    Returns:
        Rendered string.

    Raises:
        ImportError: If jinja2 is not installed.
        FileNotFoundError: If the template file doesn't exist.
        jinja2.TemplateError: If the template syntax is invalid.
    """
    try:
        from jinja2 import Environment, TemplateError  # noqa: F811
    except ImportError:
        raise ImportError(
            "模板功能需要 jinja2 库。请运行: pip install jinja2\n"
            "或: uv pip install chrome-bookmarks"
        ) from None

    source = _get_template_source(template_spec)

    env = Environment(
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["date_fmt"] = _date_fmt

    try:
        tmpl = env.from_string(source)
        return tmpl.render(root=root)
    except TemplateError:
        raise


def render_template_debug(root: Root, template_spec: str) -> str:
    """Same as render_template but prints friendly error details on failure."""
    try:
        return render_template(root, template_spec)
    except ImportError as e:
        return f"错误: {e}"
    except FileNotFoundError:
        return f"错误: 模板文件不存在 — {template_spec}"
    except Exception as e:
        return f"错误: 模板渲染失败 — {e}"
