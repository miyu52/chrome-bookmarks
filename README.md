# chrome-bookmarks

## 安装

```bash
git clone <repo>
cd chrome-bookmarks
uv venv && uv pip install -e .
```

依赖：Python ≥3.10、beautifulsoup4 ≥4.12、html5lib。

## CLI 用法

```bash
# 浏览书签树
chrome-bookmarks parse bookmarks.html

# JSON 输出
chrome-bookmarks parse bookmarks.html -o json
chrome-bookmarks parse bookmarks.html -o json --flatten   # 扁平化
chrome-bookmarks parse bookmarks.html -o json --utc       # 日期用 UTC

# Markdown 输出
chrome-bookmarks parse bookmarks.html -o markdown
chrome-bookmarks parse bookmarks.html -o markdown -v      # 详细信息
chrome-bookmarks parse bookmarks.html -o markdown -q      # 精简模式

# 自定义字段
chrome-bookmarks parse bookmarks.html -o 'fields=$folder,${title,name},$url'

# Tree 视图
chrome-bookmarks parse bookmarks.html -o tree              # 默认 emoji
chrome-bookmarks parse bookmarks.html -o tree --ascii      # 纯 ASCII
```

### 过滤

```bash
# 按域名
chrome-bookmarks parse bookmarks.html --filter domain=github.com

# 搜索标题（大小写不敏感）
chrome-bookmarks parse bookmarks.html --filter 'search=*python*'

# 按文件夹（glob）
chrome-bookmarks parse bookmarks.html --filter 'folder=书签栏/开发/*'

# 正则搜索
chrome-bookmarks parse bookmarks.html --filter 'search=~python\d+'

# 只要书签，不要文件夹
chrome-bookmarks parse bookmarks.html --filter type=bookmark

# 组合条件（AND）
chrome-bookmarks parse bookmarks.html --filter 'domain=github.com,type=bookmark'

# 多次 --filter（AND）
chrome-bookmarks parse bookmarks.html \
  --filter 'domain=github.com' \
  --filter 'type=bookmark'

# 剪掉空文件夹
chrome-bookmarks parse bookmarks.html --filter 'domain=github.com,prune_empty=true'
```

**过滤键：** `folder`（glob/~正则）、`domain`（精确域名+子域名）、`search`（glob/~正则，不区分大小写）、`type`（bookmark/folder/separator）、`url`（glob/~正则）、`prune_empty`（true/false）。

### 输出前缀

```bash
chrome-bookmarks parse bookmarks.html \
  --filter type=bookmark \
  -o 'fields=$folder,${title,name},$url' \
  --prefix 'folder,title,url'
```

`--prefix` 支持与 `fields` 相同的 `$变量` 语法，`\n` 表示换行。

## 模板变量

| 变量 | 说明 |
|------|------|
| `$title` | 书签标题（仅 bookmark 有值） |
| `$name` | 文件夹名（仅 folder 有值） |
| `${title,name}` | fallback——取第一个非空值 |
| `$folder` | 完整文件夹路径 |
| `$url` | 链接地址 |
| `$type` | bookmark / folder / separator |
| `$add_date` | Unix 时间戳（秒） |
| `$add_date_iso` | ISO 8601（本地时区） |
| `$add_date_utc` | ISO 8601（UTC） |
| `$depth` | 树深度 |

## Python API

```python
from chrome_bookmarks import parse

tree = parse("bookmarks.html")
print(tree.total)           # 书签总数
print(tree.roots[0].name)   # 第一个根文件夹名

# 过滤
filtered = tree.filter("domain=github.com,type=bookmark")

# 输出
print(filtered.to_json())
print(filtered.to_markdown())
print(filtered.to_tree())
print(filtered.to_fields("$folder,${title,name},$url"))
```

## 项目结构

```
src/chrome_bookmarks/
├── model.py        数据模型
├── parser.py       HTML 解析
├── template.py     模板引擎
├── filter.py       树筛选
├── output.py       输出格式化
└── cli.py          CLI 入口
```

## 许可

MIT
