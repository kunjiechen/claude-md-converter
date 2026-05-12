# 架构设计文档

## 版本信息

| 版本 | 日期 | 修订人 | 修订内容 |
|------|------|--------|----------|
| A/0 | 2026.05.11 | kunjiechen | 初版：统一HTML渲染层架构设计 |
| A/1 | 2026.05.12 | kunjiechen | 同步实际代码结构，移除未实现模块的引用 |

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
├── cli.py                           # CLI 入口（薄层，委托 BatchProcessor）
├── parser.py                        # Markdown → AST（markdown-it-py + 插件）
├── batch_processor.py               # 批量处理 + 线程池
├── index_generator.py               # 索引页生成（Jinja2）
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
│   │   ├── exporter.py              # HTML → python-docx（~1400 行）
│   │   └── style_mapper.py          # CSS class → Word 样式映射
│   └── pdf/
│       └── exporter.py              # HTML → weasyprint → PDF
│
└── flowchart/                       # 流程图子系统
    ├── renderer.py                  # 渲染编排（Python/Kroki/mmdc 三路降级）
    ├── painter.py                   # Python Pillow 原生绘制
    ├── chart_renderers.py           # 非 flowchart 类型（时序图/甘特图/饼图）
    └── html_embed.py                # Mermaid.js CDN 浏览器端渲染
```

> 与初版设计相比，以下模块因实际实现中已整合而未单独创建：
> - `ast_nodes.py` — AST 节点仍为 dict，类型常量定义在 parser.py
> - `table_builder.py` — 表格逻辑内联在 word/exporter.py 中
> - `flowchart/detector.py` — 检测逻辑已集成到 flowchart/renderer.py
> - `templates/layouts/` — 封面/目录/修订记录均直接在 renderer.py 中生成 HTML 片段

---

## 3. 数据流

```
阶段 1: 解析
  Markdown ──► markdown-it-py ──► AST (List[Dict])

阶段 2: HTML 渲染
  AST ──► HtmlRenderer ──► RenderContext（含 body/toc/revision/flowcharts）

阶段 3: 导出
  RenderContext + Jinja2 模板 ──► 完整 HTML 文档
      ├── Word:  BeautifulSoup4 解析 → python-docx 构建 .docx
      ├── HTML:  直接写入 .html
      └── PDF:   weasyprint 渲染 .pdf
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

---

## 7. 技术选型

| 层面 | 技术 | 选型理由 |
|------|------|----------|
| Markdown 解析 | `markdown-it-py` >=2.0 | 成熟 AST，插件丰富（表格/脚注/公式/定义列表） |
| HTML 模板 | **Jinja2** >=3.0 | Python 最成熟模板引擎，继承/宏/过滤器 |
| HTML 解析 | **BeautifulSoup4** >=4.12 | Word 导出时解析 HTML DOM，提取 CSS class |
| HTML→Word | **python-docx** >=0.8.11 | 深度使用，表格/页眉/样式/脚注均可通过 OXML 控制 |
| HTML→PDF | **weasyprint** >=59.0 | CSS 打印支持好，@page 规则，与 HTML 导出共享样式 |
| CSS 主题 | CSS 变量 (Custom Properties) | 设计令牌统一管理，主题切换零成本 |

**为什么不选 pandoc**：外部二进制依赖，不利于 Agent 化部署；python-docx 已深度集成，可精确控制 OXML 细节满足企业文档格式要求。

---

## 8. 风险管理

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 非 flowchart 图表无 Python 渲染 | 时序图/甘特图依赖外部工具 | 三路降级：Python → Kroki → mmdc |
| weasyprint 未安装 | PDF 不可用 | 引导用户使用 HTML 格式 |
| Word exporter 单体文件过大 | 维护困难 | 后续拆分为 footnotes/table/image 模块 |
| 旧版代码残留 | 新用户困惑 | SKILL.md 明确使用 api.py Converter |
