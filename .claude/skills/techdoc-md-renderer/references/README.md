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
- **表格场景识别**：识别修订履历、术语表、接口字段表、BNF、寄存器/位域/参数/错误码表，并为 Word 选择固定列宽策略
- **表格规范化**：自动合并被空行/重复分隔线拆开的 Markdown 表格，Word 单元格保留基础内联格式和 `<br>` 多段落
- **宽表横向分节**：寄存器/位域/7 列参考表等高密度表格在 Word 中自动使用横向连续分节
- **长串换行**：接口字段、语法定义等长代码单元格自动插入显示换行，避免撑坏列宽
- **HTML 表格兼容**：Markdown 中的原生 `<table>` 会转为内部表格，保留单元格内段落、列表、代码块和本地/base64/远程缓存图片
- **HTML 自包含**：所有 CSS 内联，浏览器可直接打开
- 批量处理：目录级别并行转换

## 安装

```bash
pip install -r requirements.txt

# 可选：安装 mermaid-cli 以支持 Word/PDF 流程图渲染
npm install -g @mermaid-js/mermaid-cli
```

## 使用方法

以下示例中 `SCRIPTS` 指 `.claude/skills/techdoc-md-renderer/scripts`：

```bash
SCRIPTS=.claude/skills/techdoc-md-renderer/scripts
```

```bash
# === Word 格式（默认） ===

# 单文件转 Word（使用 G-C045 技术文档主题）
PYTHONPATH=$SCRIPTS python -m cli input.md

# 带完整元数据
PYTHONPATH=$SCRIPTS python -m cli input.md \
    --doc-title "需求规格说明书" \
    --doc-number "REQ-001" \
    --doc-version "V1.0" \
    --doc-department "开发部" \
    --doc-company "上海XX科技有限公司"

# 指定输出路径
PYTHONPATH=$SCRIPTS python -m cli input.md -o output/report.docx

# === HTML 格式 ===

# 转为自包含 HTML（浏览器直接打开）
PYTHONPATH=$SCRIPTS python -m cli input.md --format html

# 使用指定主题
PYTHONPATH=$SCRIPTS python -m cli input.md --format html --theme tech-doc

# === PDF 格式 ===

# 生成 PDF
PYTHONPATH=$SCRIPTS python -m cli input.md --format pdf

# === 批量转换 ===

PYTHONPATH=$SCRIPTS python -m cli ./docs --format word --output ./output

# 单文件可直接指定完整输出文件路径
PYTHONPATH=$SCRIPTS python -m cli input.md --format word --output ./output/input.docx
```

PDF 生成使用多后端降级链：

| 后端 | 触发条件 | 保真度 |
|------|----------|--------|
| WeasyPrint | 默认优先，系统 GTK/Pango 可用 | 高 |
| Chromium/Edge headless | WeasyPrint 缺系统库或渲染失败，且本机有 Chrome/Edge | 较高 |
| wkhtmltopdf | 本机安装 wkhtmltopdf | 中 |
| LibreOffice | 本机安装 LibreOffice | 中/偏低 |
| ReportLab text fallback | 以上后端均不可用，且安装 reportlab | 低，仅保证文本可阅读 |

使用降级后端时会在 PDF 旁生成 `.backend.json`，质量报告会标记 `pdf_backend` warning，提示保真度下降。

## 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `input` | 输入文件或目录路径（必需） | - |
| `--format` / `-f` | 输出格式：`word` / `html` / `pdf` | `word` |
| `--output` / `-o` | 输出目录；单文件转换时可指定完整输出文件路径 | 同输入目录 |
| `--template` / `-t` | Word模板(.docx/.dotx) 或 CSS模板(.css) | 内置模板 |
| `--doc-title` | 文档标题（替换模板页眉占位） | 取自文件名 |
| `--doc-number` | 文件编号（替换模板页眉占位） | - |
| `--doc-version` | 版本号（替换模板页眉占位） | - |
| `--doc-department` | 制定部门（替换模板页眉占位） | - |
| `--doc-company` | 公司名称（替换模板页眉占位） | - |
| `--theme` | HTML/PDF 主题名称 | `tech-doc` |
| `--max-workers` | 并行处理数 | `4` |
| `--verbose` / `-v` | 详细输出 | `false` |
| `--include-cover` | HTML/PDF 输出封面页；默认关闭以对齐 Word 结构 | `false` |
| `--quality-report` | 转换后生成 `.quality.json` 和 `.quality.html` 质量报告 | `false` |
| `--pipeline` | 单文件启用 preflight→convert→postflight→polish→quality gate 闭环 | `false` |
| `--max-retries` | pipeline 模式下严重问题的最大重试次数 | `2` |
| `--regression` | 目录输入时执行多格式回归转换并生成 `regression_summary.json` | `false` |
| `--regression-formats` | 回归模式输出格式，逗号分隔 | `word,html,pdf` |

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

## 表格标记

转换器会自动识别常见技术表格，也支持在表格前显式指定类型：

```markdown
<!-- table: register -->
| Offset | Bits | Field | Access | Reset | Description |
|---|---|---|---|---|---|
| 0x00 | [31:0] | CTRL | RW | 0x0 | Control register |
```

支持类型：`revision`、`glossary`、`interface`、`bnf`、`register`、`bitfield`、`parameter`、`error_code`、`reference`。

## 质量报告

CLI 可加 `--quality-report` 生成同名 `.quality.json` 和 `.quality.html`：

```bash
PYTHONPATH=$SCRIPTS python -m cli input.md --format word --quality-report
```

JSON 报告适合自动化集成；HTML 报告适合人工快速浏览。报告包含文档类型识别、表格分类与布局策略、Markdown 规范化记录、preflight/postflight 检查结果、最终产物校验和质量门禁。

报告内置 `quality_gate`，将检查结果汇总为：

- `pass`：可作为可阅读产物交付。
- `review`：转换成功，但建议人工复核后交付。
- `fail`：存在阻断性问题，不建议交付。

`review` 会继续细分 `review_level`：

| review_level | 含义 |
|--------------|------|
| `readable_needs_review` | 产物大概率可读，主要是源文件警告、自动规范化、低置信度分类或本机缺少视觉渲染依赖 |
| `format_risk` | 产物已生成，但页面、表格、图片、目录等格式风险较高 |
| `blocked` | 存在阻断问题，不建议交付 |

单文件建议使用 pipeline 闭环模式生成最终产物报告：

```bash
PYTHONPATH=$SCRIPTS python -m cli input.md --format word --quality-report --pipeline
```

pipeline 顺序为：Markdown normalize/preflight → convert → postflight → polish → artifact validation → final quality report。质量报告基于 polish 后的最终文件生成。

产物校验覆盖三种输出格式：

| 格式 | 校验重点 |
|------|----------|
| Word | 正文/表格/图片/标题分页属性、空目录风险 |
| HTML | 文档结构、表格、图片引用、占位符残留 |
| PDF | 页数、正文可提取性、表格/图片基础指标 |
| DOCX/PDF 视觉页检 | 检测 LibreOffice/Poppler 能力；可用时渲染页面图片并识别空白页/内容过少页 |

## 回归校验

目录级样例可执行多格式回归：

```bash
PYTHONPATH=$SCRIPTS python -m cli ./samples \
  --regression \
  --regression-formats word,html,pdf \
  --output ./regression_output
```

回归会为每个 Markdown 样例生成指定格式产物和质量报告，并写出 `regression_summary.json`。其中任一产物转换失败或 `quality_gate=fail` 时，命令以失败码退出。

仓库内置基础回归样例：

```bash
PYTHONPATH=$SCRIPTS python -m cli samples/regression \
  --regression \
  --regression-formats word,html \
  --output /tmp/techdoc-regression
```

## 项目结构

```
claude-md-converter/
├── .claude/skills/techdoc-md-renderer/
│   ├── SKILL.md                     # Skill 定义
│   └── scripts/
│       ├── cli.py                   # 命令行接口
│       ├── api.py                   # SDK Converter
│       ├── parser.py                # Markdown → AST 解析器
│       ├── pipeline.py              # 单文件质量闭环
│       ├── preflight.py             # 源 Markdown 预检
│       ├── postflight.py            # 输出产物检查
│       ├── polisher.py              # 输出格式修正
│       ├── regression_runner.py     # 多格式回归
│       ├── batch_processor.py       # 批量处理
│       ├── analyzers/               # 规范化、表格/文档识别、质量报告/门禁
│       ├── flowchart/               # 流程图子系统
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
│       │   ├── word/                # Word 导出器 ✅（table/list/image/section builder）
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
| Phase 4 | ✅ 完成 | 表格场景识别、Markdown 规范化、Word 原生表格策略 |
| Phase 5 | ✅ 完成 | 质量报告、最终产物校验、质量门禁、回归入口 |
| Phase 6 | 📋 待定 | 页面级视觉校验、样例库扩充、在线预览 |

## 依赖

- Python >= 3.9
- markdown-it-py >= 2.0.0
- python-docx >= 0.8.11
- Jinja2 >= 3.0
- Pillow >= 9.0.0
- weasyprint >= 59.0（PDF 功能可选）
- reportlab >= 4.0.0（PDF 低保真兜底，可选但建议）

## 已知限制

- Word/PDF 流程图渲染依赖 `mmdc`（mermaid-cli），未安装时降级为代码块显示
- HTML 模式流程图使用浏览器端 mermaid.js，无需 mmdc
- 远程图片下载有 15 秒超时
- WeasyPrint 需要系统依赖；缺系统库时会自动尝试 Chrome/Edge、wkhtmltopdf、LibreOffice、ReportLab 文本 PDF 兜底
- 当前 DOCX 空白页/视觉分页主要通过 OOXML 属性校验，完整页面级视觉校验需要 LibreOffice 渲染能力
