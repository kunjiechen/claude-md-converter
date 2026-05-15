# TechDoc Markdown 渲染器 — 项目文档

## 项目概述

将 Markdown 技术文档渲染为 Word/HTML/PDF，遵循 G-C045（技术文档）和 G-C110（流程图）公司规范，并提供质量报告、最终产物校验和回归入口。

**技术栈**：Python + markdown-it-py（解析）+ Jinja2（模板）+ python-docx（Word）+ weasyprint（PDF）+ Pillow（流程图）

## 当前架构

```
Markdown ─► normalize/preflight ─► AST(parser.py) ─► HTML 引擎 ─► 语义化 HTML
                 │                                      │
                 │                                      ├─► Word 导出器(bs4→docx)
                 │                                      ├─► HTML 导出器(自包含HTML)
                 │                                      └─► PDF 导出器(weasyprint)
                 │
                 └─► postflight ─► polish ─► artifact validation ─► quality gate
```

统一 HTML 中间表示架构，所有格式从同一份语义化 HTML 派生。CSS 设计令牌 + 主题系统统一控制样式。

## 文件结构

```
./
├── SKILL.md                        # Skill 定义（Agent 行为）
├── architecture_design.md          # 架构设计文档
├── implementation_plan.md          # 本文件
├── requirements.txt
│
└── scripts/
    ├── api.py                      # 统一 SDK（Converter 类）
    ├── cli.py                      # CLI 入口
    ├── pipeline.py                 # 单文件质量闭环
    ├── preflight.py                # 源 Markdown 预检
    ├── postflight.py               # 输出产物检查
    ├── polisher.py                 # 输出格式修正
    ├── regression_runner.py        # 多格式回归
    ├── parser.py                   # Markdown → AST（markdown-it-py）
    ├── batch_processor.py          # 批量处理
    ├── index_generator.py          # 索引页生成
    ├── analyzers/                  # 规范化、表格/文档识别、质量报告/门禁
    │
    ├── html_engine/                # AST → HTML 渲染引擎
    │   ├── renderer.py             #   主渲染器
    │   ├── inline_renderer.py      #   内联格式 → HTML
    │   ├── context.py              #   渲染上下文 dataclass
    │   ├── themes/                 #   主题系统（base + tech_doc）
    │   ├── templates/              #   Jinja2 模板（base/document/index + components）
    │   └── css/                    #   样式表（base/components/tech_doc/print）
    │
    ├── exporters/                  # 导出器层
    │   ├── html/exporter.py        #   HTML 导出（自包含，mermaid CDN）
    │   ├── word/exporter.py        #   HTML → docx（bs4 + python-docx）
    │   ├── word/table_builder.py   #   Word 原生表格策略
    │   ├── word/style_config.py    #   Word 样式配置
    │   ├── word/style_mapper.py    #   CSS class → Word 样式映射
    │   └── pdf/exporter.py         #   HTML → PDF（weasyprint）
    │
    └── flowchart/                  # 流程图子系统
        ├── renderer.py             #   渲染编排（Python/Kroki/mmdc 三路降级）
        ├── painter.py              #   Python Pillow 原生绘制
        ├── chart_renderers.py      #   非 flowchart 类型渲染
        └── html_embed.py           #   Mermaid.js 浏览器端渲染
```

## 完成状态

| 阶段 | 内容 | 状态 |
|------|------|------|
| 1-6 | 基础框架、解析、Word/PDF 转换、批量处理、测试 | ✅ |
| 7 | Word 格式元素调试（内联格式/超链接/分割线/代码块/引用/表格/图片/脚注/任务列表） | ✅ |
| 8 | 剩余格式元素（表格内联/LaTeX/HTML元素/PDF内联/定义列表/页眉页脚/TOC） | ✅ |
| 9 | 模板功能（三级加载/页眉替换/样式降级） | ✅ |
| 10 | 架构重构—统一 HTML 渲染层 | ✅ |
| 11 | 产品化质量闭环—规范化/校验/门禁/回归 | ✅ |

## 当前风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| 非 flowchart Mermaid 图表仅支持 mmdc/Kroki | 时序图/甘特图等无 Python 渲染 | 降级到 mmdc CLI 或 Kroki API |
| weasyprint 系统依赖 | PDF 不可用 | 引导用户使用 HTML 格式或安装系统依赖 |
| DOCX 缺少页面级视觉渲染 | 空白页/孤立标题只能做 OOXML 级校验 | 下一步引入 LibreOffice 渲染截图校验 |
| 复杂表格规则误判 | 标准文件/芯片手册/寄存器表可读性下降 | 显式表格标记 + suggester 建议层 + 回归样例 |
| Word exporter 仍偏大 | 维护成本较高 | 继续拆分 image/section/list 等子模块 |

## 表格与智能自检查升级计划

### 目标

当前工程继续保留“Markdown → AST → HTML IR → Word/HTML/PDF”的主架构，但对表格、目录、修订履历、寄存器/位域表等高保真对象增加结构化分析层和 Word 原生渲染策略。

### 已落地

| 项目 | 状态 | 说明 |
|------|------|------|
| 表格场景分类器 | ✅ | `scripts/analyzers/table_classifier.py`，规则识别 revision/glossary/interface/bnf/register/bitfield/parameter/error_code/reference/generic |
| 正文段落分类器 | ✅ | `scripts/analyzers/paragraph_classifier.py`，识别短段落、连续紧凑段组、说明备注和条款短句 |
| HTML table 场景标注 | ✅ | `HtmlRenderer._render_table()` 追加 `table--{kind}` 和 `data-table-kind` |
| HTML prose 场景标注 | ✅ | `HtmlRenderer._render_paragraph()` 追加 `paragraph--{kind}`，连续短段落包裹 `prose-group--compact` |
| Word 表格固定布局 | ✅ | `TableBuilder` 写入 `tblLayout=fixed`，同步 `tblGrid` 和 `tcW` |
| Word 表格策略列宽 | ✅ | 根据 `TableAnalysis.layout.widths` 设置列宽 |
| 表头跨页重复 | ✅ | thead 行写入 `w:tblHeader` |
| 紧凑表格字体/代码列 | ✅ | 寄存器/位域等表格支持小字号，语法/字段列使用等宽字体 |
| Preflight 表格增强 | ✅ | 检查疑似拆表、裸尖括号占位符 |
| Postflight 表格增强 | ✅ | 检查空目录风险、超长单元格 |
| Markdown 表格规范化 | ✅ | 转换前自动合并被空行/重复分隔线拆开的连续表格 |
| 表格内联格式保真 | ✅ | Word 表格单元格直接渲染 HTML 内联节点，保留代码/强调，`<br>`/软换行提升为多段落 |
| 表格复杂块基础保真 | ✅ | 支持单元格内直接子级 `p`、`ul/ol`、`pre` 的 Word 渲染 |
| 原生 HTML 表格兼容 | ✅ | Markdown 中 `<table>` 转为内部 AST，保留单元格 `raw_html` |
| 表格单元格图片基础保真 | ✅ | Word 单元格支持本地图片和 data URI 图片插入，远程图片降级占位 |
| 显式表格标记 | ✅ | 支持 `<!-- table: register -->` 等标记覆盖自动分类 |
| 宽表横向分节 | ✅ | 寄存器/位域/7 列参考表自动使用 Word 横向连续分节 |
| 超长单元格换行策略 | ✅ | 语法/接口字段长串自动插入显示换行，postflight 按最长连续片段判断风险 |
| 文档类型识别 | ✅ | 识别 `standard_spec`、`chip_manual`、`register_doc`、`api_spec`、`coding_standard`、`generic_techdoc` |
| 质量报告输出 | ✅ | `--quality-report` / API `quality_report=True` 生成 `.quality.json` 和 `.quality.html` |
| 正文排版质量报告 | ✅ | 质量报告包含短段落数、紧凑段组、平均段落长度和正文排版风险 |
| 质量门禁 | ✅ | 质量报告内置 `quality_gate`，输出 `pass/review/fail`、分数和交付建议 |
| 单文件闭环管线 | ✅ | `--pipeline` 执行 preflight→convert→postflight→polish→final quality report |
| 最终产物校验 | ✅ | `ArtifactValidator` 对 HTML/Word/PDF 做结构、内容、表格、图片、页数等校验 |
| 回归校验入口 | ✅ | `--regression` 批量跑样例目录和多输出格式，生成 `regression_summary.json` |
| HTML/PDF 标题同步 | ✅ | 标题先清理手动编号，再按 Word 章节规则生成 `1 / 1.1 / 1.1.1` |
| HTML/PDF 基本结构同步 | ✅ | 默认关闭封面，按 Word 的目录→修订记录→正文顺序输出 |
| PDF 表格分页修正 | ✅ | 打印样式允许长表跨页，并重复 thead，避免大表导致 PDF 内容不全 |
| 拆表合并增强 | ✅ | 识别 `:-` 这类短分隔线，合并 Word/PDF 导出的分段表格，避免数据行被误判为表头 |
| 质量门禁阈值修正 | ✅ | 仅 warning/自动规范化不再判 fail，而进入 review |
| Word 标题分页修正 | ✅ | 后处理不再给每个 H1 默认段前分页，改为清理强制分页并设置标题与下段同页 |
| 回归样例库 | ✅ | `samples/regression/` 覆盖标准表格、寄存器/位域、接口/BNF、复杂单元格 |
| 短段落回归样例 | ✅ | `short_paragraphs.md` 覆盖单句段落、显式 `prose: compact/preserve` 标记 |
| DOCX/PDF 视觉页检 | ✅ | `VisualValidator` 检测 LibreOffice/Poppler，支持渲染页面并识别空白/内容稀疏页 |
| Word exporter 拆分 | ✅ | 新增 `list_builder.py`、`image_builder.py`、`section_builder.py`，主导出器继续瘦身 |
| Review 原因分类 | ✅ | `quality_gate.review_categories` 区分 blocking/source/output/visual/table/normalization/confidence，并输出 `review_level` |
| PDF 多后端降级 | ✅ | WeasyPrint 失败后尝试 Chrome/Edge、wkhtmltopdf、LibreOffice，最终用 ReportLab 文本 PDF 兜底 |

### 下一阶段

| 优先级 | 任务 | 说明 |
|--------|------|------|
| P1 | 安装/封装视觉依赖 | 本机/CI 安装 LibreOffice + Poppler，让 DOCX/PDF 视觉页检从 warning 变成真实渲染 |
| P1 | 视觉规则增强 | 在已渲染页面上继续识别孤立标题、表格截断、页眉页脚重叠 |
| P1 | 回归样例扩充 | 增加真实标准文件、芯片手册、超宽寄存器表和图片样例 |
| P2 | AI 辅助自检查 | 规则置信度不足时输出建议，不直接改变版式 |

### 设计边界

- 规则识别是默认路径，保证批量转换可重复。
- AI 只作为低置信度场景的建议层，不作为唯一判断源。
- HTML 仍是统一 IR，但 Word 导出器允许对表格等对象走专用 OOXML 策略。
- `polisher.py` 只做转换后修正，不再承担所有表格智能；主要策略前移到 `analyzers` 和 `TableBuilder`。

## 依赖

```
markdown-it-py>=2.0.0
mdit-py-plugins>=0.3.0    # 脚注/公式/定义列表
python-docx>=0.8.11
weasyprint>=59.0          # PDF（可选）
Pillow>=9.0.0
Jinja2>=3.0
beautifulsoup4>=4.12
```
