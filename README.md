# TechDoc Markdown 渲染器

将 Markdown 技术文档渲染为格式规范的 **Word (.docx)**、**HTML** 或 **PDF (.pdf)** 文档。

## 架构：统一 HTML 渲染层

```
Markdown ──► AST 解析器 ──► HTML 渲染引擎 ──► 语义化 HTML
                                                   │
                          ┌────────────────────────┼────────────────────────┐
                          │                        │                        │
                     Word 导出器               HTML 自包含               PDF 导出器
                     HTML → docx               浏览器直接打开            HTML → PDF
```

HTML 是唯一的中间表示（IR）。所有输出格式从同一份带 CSS 语义类的 HTML 派生，样式通过 **CSS 设计令牌 + 主题系统** 统一控制。

## 功能特性

- 完整的 Markdown 元素支持：标题、段落、列表、表格、代码块、引用、图片、分割线、脚注、任务列表
- 内联格式：粗体、斜体、删除线、下划线、行内代码、超链接、kbd、sub/sup、高亮
- 数学公式：LaTeX 块级公式 `$$` 和内联公式 `$`
- 定义列表：`term\n: definition` 语法
- 流程图渲染：Mermaid 语法支持（HTML 模式浏览器端渲染，Word/PDF 模式 mmdc 渲染）
- **主题系统**：CSS 设计令牌（变量）控制字体/字号/颜色/间距/表格，支持主题切换
- **Word 模板**：三级加载优先级，页眉字段动态替换
- **HTML 自包含**：所有 CSS 内联，浏览器可直接打开
- 批量处理：目录级别并行转换

## 安装

```bash
pip install -r requirements.txt

# 可选：安装 mermaid-cli 以支持 Word/PDF 流程图渲染
npm install -g @mermaid-js/mermaid-cli
```

## 使用方法

以下示例中 `SCRIPTS` 指 `.claude/skills/techdoc-md-renderer/scripts`。

```bash
# === Word 格式（默认） ===

# 单文件转 Word（使用 G-C045 技术文档主题）
PYTHONPATH=scripts python -m cli input.md

# 带完整元数据
PYTHONPATH=scripts python -m cli input.md \
    --doc-title "需求规格说明书" \
    --doc-number "REQ-001" \
    --doc-version "V1.0" \
    --doc-department "开发部" \
    --doc-company "上海XX科技有限公司"

# 指定输出路径
PYTHONPATH=scripts python -m cli input.md -o output/report.docx

# === HTML 格式 ===

# 转为自包含 HTML（浏览器直接打开）
PYTHONPATH=scripts python -m cli input.md --format html

# 使用指定主题
PYTHONPATH=scripts python -m cli input.md --format html --theme tech-doc

# === PDF 格式 ===

# 启用 PDF 转换（默认关闭）
PYTHONPATH=scripts python -m cli input.md --format pdf --enable-pdf

# === 批量转换 ===

PYTHONPATH=scripts python -m cli ./docs --format word --output ./output
```

## 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `input` | 输入文件或目录路径（必需） | - |
| `--format` / `-f` | 输出格式：`word` / `html` / `pdf` | `word` |
| `--output` / `-o` | 输出目录 | 同输入目录 |
| `--template` / `-t` | Word模板(.docx/.dotx) 或 CSS模板(.css) | 内置模板 |
| `--doc-title` | 文档标题（替换模板页眉占位） | 取自文件名 |
| `--doc-number` | 文件编号（替换模板页眉占位） | - |
| `--doc-version` | 版本号（替换模板页眉占位） | - |
| `--doc-department` | 制定部门（替换模板页眉占位） | - |
| `--doc-company` | 公司名称（替换模板页眉占位） | - |
| `--theme` | HTML/PDF 主题名称 | `tech-doc` |
| `--max-workers` | 并行处理数 | `4` |
| `--verbose` / `-v` | 详细输出 | `false` |

### 模板加载优先级

1. CLI 参数 `--template` 显式指定
2. `templates/` 目录下第一个 `.docx` 文件
3. 内置默认模板（G-C045 公司模板）

未找到任何模板时，回退为硬编码格式（宋体 12pt），保持向后兼容。

## 主题系统

| 主题 | 说明 |
|------|------|
| `tech-doc` | **默认**。G-C045 规范风格：楷体正文、黑体标题、Courier New 代码、Microsoft YaHei 表格 |

主题通过 CSS 设计令牌统一控制：字体族、字号层级、颜色体系、间距、表格边框/内边距、页面尺寸/边距。

## 项目结构

```
claude-md-converter/
├── .claude/skills/techdoc-md-renderer/
│   ├── SKILL.md                     # Skill 定义
│   └── scripts/
│       ├── cli.py                   # 命令行接口
│       ├── parser.py                # Markdown → AST 解析器
│       ├── converter.py             # 格式转换器基类
│       ├── batch_processor.py       # 批量处理
│       ├── flowcharts/              # 流程图子系统
│       ├── default_template.docx    # 内置 Word 模板
│       │
│       ├── html_engine/             # ★ HTML 渲染引擎（核心中间层）
│       │   ├── renderer.py          # AST → HTML 主渲染器
│       │   ├── inline_renderer.py   # 内联格式渲染
│       │   ├── context.py           # 渲染上下文（元数据+CSS+TOC）
│       │   ├── themes/              # 主题子系统
│       │   ├── templates/           # Jinja2 模板
│       │   └── css/                 # CSS 样式表
│       │
│       ├── exporters/               # ★ 导出器层（HTML → 目标格式）
│       │   ├── html/                # HTML 导出器 ✅
│       │   ├── word/                # Word 导出器 ✅
│       │   └── pdf/                 # PDF 导出器 ✅
│       │
│
├── reference/                       # 参考规范文档
├── architecture_design.md           # 架构设计文档
├── implementation_plan.md           # 实施计划
└── requirements.txt
```

## 架构演进

| 阶段 | 状态 | 内容 |
|------|------|------|
| Phase 1 | ✅ 完成 | HTML 渲染引擎 + HTML 导出器 + 主题系统 |
| Phase 2 | ✅ 完成 | Word 导出器（HTML → python-docx + BeautifulSoup4） |
| Phase 3 | ✅ 完成 | PDF 导出器（HTML → weasyprint） |
| Phase 4 | 📋 待定 | 在线预览 + 多主题扩展 |
| Phase 5 | 📋 待定 | 旧版代码清理 |

## 依赖

- Python >= 3.9
- markdown-it-py >= 2.0.0
- python-docx >= 0.8.11
- Jinja2 >= 3.0
- Pillow >= 9.0.0
- weasyprint >= 59.0（PDF 功能可选）

## 已知限制

- Word/PDF 流程图渲染依赖 `mmdc`（mermaid-cli），未安装时降级为代码块显示
- HTML 模式流程图使用浏览器端 mermaid.js，无需 mmdc
- 远程图片下载有 15 秒超时
- weasyprint 需要系统依赖（macOS: `brew install pango`），未安装时 PDF 功能不可用
