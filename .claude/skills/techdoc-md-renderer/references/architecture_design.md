# 架构设计文档

## 版本信息

| 版本 | 日期 | 修订人 | 修订内容 |
|------|------|--------|----------|
| A/0 | 2026.05.11 | kunjiechen | 初版：统一HTML渲染层架构设计 |
| A/1 | 2026.05.12 | kunjiechen | 同步实际代码结构，移除未实现模块的引用 |
| A/2 | 2026.05.13 | Codex | 同步产品级质量闭环、表格策略层、三格式一致性和清理后的模块边界 |

---

## 1. 目标架构

```
                      ┌─────────────────┐
                      │   Markdown 输入  │
                      └────────┬────────┘
                               │
                      ┌────────▼────────┐
                      │   AST 解析器     │  parser.py
                      └────────┬────────┘
                               │
              ┌────────────────▼────────────────┐
              │         HTML 渲染引擎            │  html_engine/
              │  ┌──────┐ ┌──────┐ ┌────────┐  │
              │  │主题系统│ │CSS引擎│ │Jinja2  │  │
              │  └──────┘ └──────┘ └────────┘  │
              └────────────────┬────────────────┘
                               │ 输出语义化 HTML
          ┌────────────────────┼────────────────────┐
          │                    │                    │
  ┌───────▼──────┐   ┌────────▼───────┐   ┌───────▼──────┐
  │ Word 导出器  │   │  HTML 导出器    │   │  PDF 导出器   │
  │ HTML→docx   │   │  自包含 HTML    │   │  HTML→PDF    │
  └──────────────┘   └────────────────┘   └──────────────┘
```

**核心原则**：HTML 是唯一的中间表示（IR），所有样式通过 CSS 统一控制，所有输出格式都从同一份 HTML 派生。

---

## 2. 模块划分（与实际代码一致）

```
scripts/
├── api.py                           # 统一 SDK：Converter 类
├── cli.py                           # CLI 入口：单文件/目录/质量报告/回归
├── parser.py                        # Markdown → AST（markdown-it-py + 插件）
├── batch_processor.py               # 批量处理 + 线程池
├── index_generator.py               # 索引页生成（Jinja2）
├── pipeline.py                      # 单文件质量闭环管线
├── preflight.py                     # 源文件预检与可修复项修正
├── postflight.py                    # 输出产物崩溃级检查
├── polisher.py                      # 输出产物格式修正
├── regression_runner.py             # 多格式回归入口
│
├── analyzers/                       # 文档/表格识别与质量报告
│   ├── markdown_normalizer.py       # Markdown 拆表合并等规范化
│   ├── table_classifier.py          # 表格场景识别 + 布局策略
│   ├── document_classifier.py       # 文档类型识别
│   ├── artifact_validator.py        # 最终产物校验
│   ├── quality_report.py            # JSON/HTML 质量报告
│   ├── quality_gate.py              # pass/review/fail 门禁
│   └── suggester.py                 # 低置信度建议层
│
├── html_engine/                     # HTML 渲染引擎（核心中间层）
│   ├── renderer.py                  # AST → 语义化 HTML 主渲染器
│   ├── inline_renderer.py           # 内联格式段 → HTML
│   ├── context.py                   # RenderContext dataclass（模板变量容器）
│   ├── themes/                      # 主题子系统
│   │   ├── base.py                  # 抽象主题基类
│   │   └── tech_doc.py              # G-C045 技术文档主题
│   ├── templates/                   # Jinja2 模板
│   │   ├── base.html.j2             # 基础壳：<head> + CSS + 元数据
│   │   ├── document.html.j2         # 完整文档模板（extends base）
│   │   ├── index.html.j2            # 索引页模板（独立，内联 CSS）
│   │   └── components/              # 可复用 HTML 组件
│   │       ├── heading.html.j2
│   │       ├── table.html.j2
│   │       ├── code_block.html.j2
│   │       └── flowchart.html.j2
│   └── css/                         # CSS 样式表
│       ├── base.css                 # 基础重置 + 排版
│       ├── components.css           # 组件样式（表格/代码块/流程图/引用）
│       ├── tech_doc.css             # G-C045 技术文档风格
│       └── print.css                # 打印/PDF 专用样式（@page 规则）
│
├── exporters/                       # 导出器层（HTML → 目标格式）
│   ├── html/
│   │   └── exporter.py              # 自包含 HTML 导出（mermaid CDN）
│   ├── word/
│   │   ├── exporter.py              # HTML → python-docx 主编排
│   │   ├── table_builder.py         # Word 原生表格构建与策略列宽
│   │   ├── list_builder.py          # 列表项目符号/缩进/任务项
│   │   ├── image_builder.py         # 图片加载、DPI 尺寸和占位降级
│   │   ├── section_builder.py       # TOC、修订记录、硬分页
│   │   ├── inline_processor.py      # 内联格式处理
│   │   ├── footnote_injector.py     # Word 脚注注入
│   │   ├── style_config.py          # Word 样式配置
│   │   └── style_mapper.py          # CSS class → Word 样式映射
│   └── pdf/
│       └── exporter.py              # HTML → PDF 多后端降级链
│
└── flowchart/                       # 流程图子系统
    ├── renderer.py                  # 渲染编排（Python/Kroki/mmdc 三路降级）
    ├── painter.py                   # Python Pillow 原生绘制
    ├── chart_renderers.py           # 非 flowchart 类型（时序图/甘特图/饼图）
    └── html_embed.py                # Mermaid.js CDN 浏览器端渲染
```

### 2.1 智能自检查与表格场景层

为支持标准文件、软件接口规范、芯片手册、寄存器表等高密度表格文档，在解析和导出之间增加轻量分析层：

```
Markdown/AST/HTML Table
    │
    ▼
analyzers/
├── table_classifier.py              # 表格场景识别 + 布局建议
├── document_classifier.py           # 文档类型识别
├── markdown_normalizer.py           # Markdown 表格规范化
├── artifact_validator.py            # 最终产物结构校验
├── visual_validator.py              # DOCX/PDF 页面级视觉校验
├── quality_gate.py                  # pass/review/fail 门禁
└── quality_report.py                # JSON/HTML 质量报告
    │
    ▼
TableAnalysis(kind, confidence, layout, issues)
    │
    ├── HTML: 追加 table--{kind} class / data-table-kind
    ├── Word: 选择固定列宽、表头重复、紧凑字体、代码列字体
    └── Postflight: 输出可读性风险
```

设计原则：

| 原则 | 说明 |
|------|------|
| 规则优先 | 默认使用确定性规则识别，保证批量转换可复现 |
| AI 辅助 | 仅在规则置信度不足、表格语义模糊、疑似拆表时作为建议层 |
| 策略注册 | 新增寄存器表、DTC 表、信号表时添加策略，不污染通用表格逻辑 |
| Word-native | 表格、目录、修订履历、页眉页脚等 Word 特有对象走原生 OOXML 控制 |

质量报告输出 `.quality.json` 和 `.quality.html`，包含：

- 文档类型：`standard_spec`、`chip_manual`、`register_doc`、`api_spec`、`coding_standard`、`generic_techdoc`。
- 表格清单：类型、置信度、行列数、布局策略、横向分节、代码列。
- Markdown 规范化记录：自动合并的拆表位置。
- preflight/postflight：转换前和转换后的结构化问题列表。
- artifact validation：HTML/Word/PDF 最终产物结构校验、页数/正文/表格/图片等指标。
- visual validation：依赖 LibreOffice/Poppler 时渲染 DOCX/PDF 页面，检测空白页和内容过少页；依赖缺失时输出 warning。
- quality gate：汇总为 `pass` / `review` / `fail`、质量分数、`review_categories`、`review_level` 和是否建议交付。

> 与初版设计相比，以下模块因实际实现中已整合而未单独创建：
> - `ast_nodes.py` — AST 节点仍为 dict，类型常量定义在 parser.py
> - `flowchart/detector.py` — 检测逻辑已集成到 flowchart/renderer.py
> - `templates/layouts/` — 封面/目录/修订记录均直接在 renderer.py 中生成 HTML 片段

---

## 3. 数据流

```
阶段 1: 规范化与解析
  Markdown ──► MarkdownNormalizer(拆表合并/短分隔线识别) ──► markdown-it-py ──► AST (List[Dict])

阶段 2: 语义分析
  AST 表格节点 / HTML table ──► TableClassifier ──► TableAnalysis

阶段 3: HTML 渲染
  AST ──► HtmlRenderer ──► RenderContext（含 body/toc/revision/flowcharts）
                 │
                 └── 表格追加 table--{kind} / data-table-kind
                 └── 标题清理手动编号后统一生成章节号，与 Word 标题规则对齐

阶段 4: 导出
  RenderContext + Jinja2 模板 ──► 完整 HTML 文档
      ├── Word:  BeautifulSoup4 解析 → python-docx 构建 .docx
      ├── HTML:  直接写入 .html（默认无封面，目录→修订→正文）
      └── PDF:   WeasyPrint 优先；失败后降级到 Chrome/Edge、wkhtmltopdf、LibreOffice、ReportLab
阶段 5: 质量闭环
  输出文件 ──► PostflightChecker ──► Polisher ──► ArtifactValidator(+VisualValidator) ──► QualityReport
                                                                   │
                                                                   └── QualityGate(pass/review/fail)
阶段 6: 回归校验
  样例目录 × 输出格式(html/word/pdf) ──► ConversionPipeline ──► regression_summary.json
```

### RenderContext 结构

```python
@dataclass
class RenderContext:
    title: str              # 文档标题
    number: str = ""        # 文件编号
    version: str = ""       # 版本号
    department: str = ""    # 制定部门
    company: str = ""       # 公司名称
    date: str = ""          # 日期
    theme_css: str = ""     # 内联CSS（所有CSS文件合并后的内容）
    toc_html: str = ""      # 目录HTML片段
    body_html: str = ""     # 正文HTML片段
    revision_html: str = "" # 修订记录HTML片段
    cover_html: str = ""    # 封面HTML片段（预留）
    flowcharts: list = []   # 流程图数据 [{"id":1, "mime":"...", "data":"..."}]
    mermaid_js_cdn: str = ""# Mermaid.js CDN 脚本（html 导出 browser 模式）
    inline_images: bool = False
```

---

## 4. HTML 语义化 class 规范

| AST 节点 | HTML 标签 | CSS class |
|----------|-----------|-----------|
| heading(level=1-6) | `<h1>-<h6>` | `heading heading--{level}` |
| paragraph | `<p>` | `paragraph` |
| list(ordered=false) | `<ul>` | `list list--bullet` |
| list(ordered=true) | `<ol>` | `list list--ordered` |
| table | `<table>` | `table table--data` / `table--revision` |
| code_block | `<div>` + `<pre><code>` | `code-block` |
| blockquote | `<blockquote>` | `blockquote` [blockquote--level-{n}] |
| image | `<figure>` + `<img>` | `image` |
| math_block | `<div>` | `math math--block` |
| math_inline | `<span>` | `math math--inline` |
| hr | `<hr>` | `hr` |
| definition_list | `<dl>` | `definition-list` |

表格会额外追加场景 class 和 data 属性：

| 表格场景 | CSS class | 识别依据 |
|----------|-----------|----------|
| 修订履历 | `table--revision` | 版次/修订内容/修订日期/修订人/备注 |
| 术语定义 | `table--glossary` | 定义/缩写/描述，常见 2 列短词 + 长描述 |
| 接口字段 | `table--interface` | 元素名字/字段/描述/示例 |
| BNF 语法 | `table--bnf` | Symbol/Meaning/Example/Explanation |
| 寄存器表 | `table--register` | Address/Offset/Bits/Field/Access/Reset/Description |
| 位域表 | `table--bitfield` | Bit/Bits/Field/Access/Reset/Description |
| 参数表 | `table--parameter` | Name/Type/Range/Default/Description |
| 错误码表 | `table--error_code` | Code/Error/Meaning/Action |
| 参考表 | `table--reference` | 短代码列 + Long-Name/中文释义列 |

Markdown 中可使用显式标记覆盖自动分类：

```markdown
<!-- table: register -->
| Offset | Bits | Field | Access | Reset | Description |
|---|---|---|---|---|---|
```

---

## 5. Mermaid 双模式策略

```
Mermaid 代码块
      │
      ├─── browser 模式 (HTML 导出，默认)
      │    输出: <pre class="mermaid"> ... </pre>
      │          + <script src="mermaid.js CDN">
      │    浏览器端实时渲染为 SVG，交互式
      │
      └─── server 模式 (Word/PDF 导出)
           渲染链: Python Pillow → Kroki API → mmdc CLI（三路降级）
           输出: <figure><img src="data:image/png;base64,..."></figure>
```

---

## 6. Word 导出流程

```
完整 HTML 文档
    │
    ▼
┌──────────────────────┐
│  BeautifulSoup4      │  解析 HTML DOM，遍历 body 子元素
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  StyleMapper         │  根据元素 tag + CSS class 查找 Word 样式
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  python-docx 构建    │  逐元素：标题/段落/列表/表格/代码块/图片/公式
│  - 模板样式映射      │
│  - 内联格式嵌套渲染  │
│  - 表格场景策略      │
│  - 原生脚注注入      │
│  - TOC 字段生成      │
└──────────┬───────────┘
           │
           ▼
        .docx 文件
```

### CSS → Word 样式映射（style_mapper.py）

```python
ELEMENT_MAP = {
    ('h1',): 'Heading 1', ('h2',): 'Heading 2', ('h3',): 'Heading 3',
    ('h4',): 'Heading 4', ('h5',): 'Heading 5', ('h6',): 'Heading 6',
    ('p',):  'Normal',    ('pre', 'code'): 'CodeBlock',
    ('blockquote',): 'Quote',
}

TABLE_CLASS_MAP = {
    'table--data':     'Table Grid',
    'table--revision': 'Revision Table',
}
```

### 6.1 表格策略化渲染

Word 表格不再只依赖通用等宽表格。`TableBuilder` 在构建时再次调用 `TableClassifier`，并根据 `TableAnalysis.layout` 执行：

- 源头规范化：`MarkdownNormalizer` 在解析前合并被空行/重复分隔线拆开的连续 Markdown 表格，兼容 `:-` 这类短分隔线。
- 固定布局：写入 `w:tblLayout type="fixed"`，关闭 Word 自动适配。
- 列宽同步：同时写入 `w:tblGrid/w:gridCol` 和每个单元格 `w:tcW`。
- 表头重复：对 thead 行写入 `w:tblHeader`，跨页可读。
- 场景列宽：寄存器/位域/BNF/接口字段/术语表等分别使用不同列宽权重。
- 紧凑模式：寄存器、位域等高密度表可使用较小字号。
- 横向分节：寄存器、位域和 7 列参考表等宽表自动使用连续横向 section，后续内容恢复竖向。
- 代码列：地址、字段、语法示例等列使用等宽字体。
- 内联保真：Word 表格单元格直接渲染 HTML 内联节点，保留内联代码、强调；`<br>`/软换行提升为单元格多段落。
- 长串换行：接口字段/语法定义等长代码单元格按语义分隔符插入显示换行，避免撑坏列宽。
- HTML 表格兼容：Markdown 原生 `<table>` 在 parser 阶段转为内部表格 AST，单元格 `raw_html` 继续交由 HTML/Word 导出器渲染。
- 单元格图片：Word 表格单元格支持本地图片和 data URI 图片插入，远程图片仍降级为占位文本。

后续增强方向：

- 建立表格回归样例库：寄存器、位域、接口字段、代码/列表/图片混合单元格。
- 扩展 DOCX/PDF 页面级视觉校验，进一步识别孤立标题和表格截断。
- 将 visual validation 的 warning 分类并显示在 quality gate 的 `review_categories.visual` 中。
- 对超宽表自动拆分为“基础字段 + 描述字段”两张表或附录表。
- 低置信度表格引入建议层，只输出建议，不直接改变可重复的规则结果。

---

## 7. 技术选型

| 层面 | 技术 | 选型理由 |
|------|------|----------|
| Markdown 解析 | `markdown-it-py` >=2.0 | 成熟 AST，插件丰富（表格/脚注/公式/定义列表） |
| HTML 模板 | **Jinja2** >=3.0 | Python 最成熟模板引擎，继承/宏/过滤器 |
| HTML 解析 | **BeautifulSoup4** >=4.12 | Word 导出时解析 HTML DOM，提取 CSS class |
| HTML→Word | **python-docx** >=0.8.11 | 深度使用，表格/页眉/样式/脚注均可通过 OXML 控制 |
| HTML→PDF | **weasyprint** >=59.0 + Chrome/Edge/wkhtmltopdf/LibreOffice/ReportLab 降级 | 优先高保真 CSS 打印；缺系统库时仍尽量生成可阅读 PDF |
| CSS 主题 | CSS 变量 (Custom Properties) | 设计令牌统一管理，主题切换零成本 |

**为什么不选 pandoc**：外部二进制依赖，不利于 Agent 化部署；python-docx 已深度集成，可精确控制 OXML 细节满足企业文档格式要求。

---

## 8. 风险管理

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 非 flowchart 图表无 Python 渲染 | 时序图/甘特图依赖外部工具 | 三路降级：Python → Kroki → mmdc |
| weasyprint 未安装 | 高保真 PDF 不可用 | 自动尝试 Chrome/Edge、wkhtmltopdf、LibreOffice、ReportLab 文本 PDF |
| weasyprint 系统依赖缺失 | 高保真 PDF 不可用 | 自动降级并在质量报告中标记 `pdf_backend` warning |
| Word 视觉分页无法纯 OOXML 完全判断 | 空白页/孤立标题漏检 | 已接入 LibreOffice 渲染钩子；环境缺依赖时输出 warning |
| 规则误判复杂表格 | 列宽/表头不符合语义 | 显式表格标记 + suggester 建议层 + 回归样例 |
| 旧版缓存/产物污染仓库 | 状态噪音、误提交 | 清理 `__pycache__`/质量产物并加入 `.gitignore` |
