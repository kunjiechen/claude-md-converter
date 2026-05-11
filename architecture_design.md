# 架构重构设计文档

## 版本信息

| 版本 | 日期 | 修订人 | 修订内容 |
|------|------|--------|----------|
| A/0 | 2026.05.11 | kunjiechen | 初版：统一HTML渲染层架构设计 |

---

## 1. 目标架构

```
                      ┌─────────────────┐
                      │   Markdown 输入  │
                      └────────┬────────┘
                               │ (保持不变)
                      ┌────────▼────────┐
                      │   AST 解析器     │  parser.py (复用)
                      └────────┬────────┘
                               │
              ┌────────────────▼────────────────┐
              │         HTML 渲染引擎            │  ★ 新增核心层
              │  ┌──────┐ ┌──────┐ ┌────────┐  │
              │  │主题系统│ │CSS引擎│ │Jinja2  │  │
              │  └──────┘ └──────┘ └────────┘  │
              └────────────────┬────────────────┘
                               │ 输出语义化 HTML
          ┌────────────────────┼────────────────────┐
          │                    │                    │
  ┌───────▼──────┐   ┌────────▼───────┐   ┌───────▼──────┐
  │ Word 导出器  │   │  PDF 导出器     │   │ 在线预览     │
  │ HTML→docx   │   │  HTML→PDF      │   │ 纯 HTML      │
  └──────────────┘   └────────────────┘   └──────────────┘
```

**核心原则**：HTML 是唯一的中间表示（IR），所有样式通过 CSS 统一控制，所有输出格式都从同一份 HTML 派生。

---

## 2. 模块划分

```
md_converter/
├── __init__.py                     # 包声明
├── cli.py                          # CLI 入口 (简化，瘦身)
├── parser.py                       # Markdown → AST (复用，微调)
│
├── ast_nodes.py                    # ★ 新增：AST 节点类型定义（从 parser 抽出）
│
├── html_engine/                    # ★ 新增：HTML 渲染引擎（核心中间层）
│   ├── __init__.py
│   ├── renderer.py                 # AST → HTML 主渲染器
│   ├── inline_renderer.py          # 内联格式段 → HTML
│   ├── context.py                  # 渲染上下文（主题、CSS、元数据）
│   │
│   ├── themes/                     # 主题子系统
│   │   ├── __init__.py
│   │   ├── base.py                 # 抽象主题基类
│   │   ├── tech_doc.py             # 技术文档主题（G-C045/G-C110 风格）
│   │   ├── modern.py               # 现代风格主题
│   │   └── registry.py             # 主题注册表
│   │
│   ├── templates/                  # Jinja2 模板
│   │   ├── base.html.j2            # 基础壳：<head> + CSS + 元数据
│   │   ├── document.html.j2        # 完整文档模板
│   │   ├── components/             # 可复用 HTML 组件
│   │   │   ├── heading.html.j2
│   │   │   ├── table.html.j2
│   │   │   ├── code_block.html.j2
│   │   │   ├── flowchart.html.j2
│   │   │   └── admonition.html.j2
│   │   └── layouts/                # 页面布局
│   │       ├── cover.html.j2       # 封面
│   │       ├── toc.html.j2         # 目录页
│   │       └── revision.html.j2    # 修订记录页
│   │
│   └── css/                        # CSS 样式表
│       ├── tokens.css              # 设计令牌（CSS 变量：颜色/字体/间距）
│       ├── base.css                # 基础重置 + 排版
│       ├── tech_doc.css            # 技术文档风格
│       ├── components.css          # 组件样式（表格/代码块/流程图/引用）
│       └── print.css               # 打印/PDF 专用样式
│
├── exporters/                      # ★ 新增：导出器层（HTML → 目标格式）
│   ├── __init__.py
│   ├── base.py                     # BaseExporter 抽象类
│   ├── word/                       # Word 导出
│   │   ├── __init__.py
│   │   ├── exporter.py             # HTML → python-docx
│   │   ├── style_mapper.py         # CSS类 → Word样式 映射
│   │   └── table_builder.py        # HTML表格 → docx表格
│   ├── pdf/                        # PDF 导出
│   │   ├── __init__.py
│   │   └── exporter.py             # HTML → weasyprint → PDF
│   └── html/                       # 在线 HTML
│       ├── __init__.py
│       └── exporter.py             # 生成自包含 HTML（内联CSS/图片base64）
│
├── flowchart/                      # 流程图子系统（从 word_converter 抽出）
│   ├── __init__.py
│   ├── detector.py                 # 流程图检测
│   ├── renderer.py                 # 渲染编排（mmdc/Kroki/PlantUML/Python）
│   ├── painter.py                  # Python 原生绘制
│   └── html_embed.py               # ★ 新增：Mermaid HTML 内嵌渲染
│
├── [legacy] word_converter.py      # 旧版直连Word (渐进废弃)
├── [legacy] pdf_converter.py       # 旧版 PDF
├── [legacy] pdf_converter_reportlab.py  # 旧版 PDF
├── batch_processor.py              # 批量处理 (复用)
└── default_template.docx           # [兼容] 旧模板
```

---

## 3. 数据流设计

### 3.1 整体流程

```
阶段 1: 解析
  Markdown ──► markdown-it-py ──► AST (List[Dict])
  输出同现有 parser.py，无变化

阶段 2: HTML 渲染
  AST ──► RenderContext ──► Jinja2 ──► 语义化 HTML + CSS class
  输出: HTML 字符串

阶段 3: 导出
  HTML ──► Word/PDF/Online 导出器 ──► 目标格式文件
```

### 3.2 RenderContext 结构

```python
@dataclass
class RenderContext:
    """HTML渲染上下文"""
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
    cover_html: str = ""    # 封面HTML片段（可选）
    flowcharts: list = []   # 流程图数据 [{"id":1, "svg":"..."}]
```

### 3.3 HTML 渲染器输出规范

HTML 渲染器输出的 HTML 元素必须携带语义化 CSS class：

| AST 节点 | HTML 标签 | CSS class |
|----------|-----------|-----------|
| heading(level=1) | `<h1>` | `heading heading--1` |
| heading(level=2) | `<h2>` | `heading heading--2` |
| heading(level=3) | `<h3>` | `heading heading--3` |
| paragraph | `<p>` | `paragraph` |
| list(ordered=false) | `<ul>` | `list list--bullet` |
| list(ordered=true) | `<ol>` | `list list--ordered` |
| table | `<table>` | `table table--data` / `table--revision` |
| code_block | `<pre>` + `<code>` | `code-block` |
| blockquote | `<blockquote>` | `blockquote` |
| image | `<figure>` + `<img>` | `image` |
| math_block | `<div>` | `math math--block` |
| math_inline | `<span>` | `math math--inline` |
| hr | `<hr>` | `hr` |
| definition_list | `<dl>` | `definition-list` |

---

## 4. 技术选型

| 层面 | 技术 | 版本 | 选型理由 |
|------|------|------|----------|
| Markdown 解析 | `markdown-it-py` | >=2.0 | 已有成熟 AST，支持插件扩展 |
| HTML 模板引擎 | **Jinja2** | >=3.0 | Python 最成熟模板引擎，继承/宏/过滤器 |
| HTML 解析 (Word导出) | **BeautifulSoup4** | >=4.12 | HTML 元素遍历 + CSS class 提取 |
| HTML→Word | **python-docx** | >=0.8.11 | 已有深度使用，表格/页眉/样式逻辑可复用 |
| HTML→PDF | **weasyprint** | >=59.0 | 已有成熟实现，CSS 打印支持好 |
| CSS 主题 | CSS 变量 (Custom Properties) | - | 设计令牌统一管理，主题切换零成本 |

**为什么不选 pandoc 做 HTML→Word**：

1. pandoc 是外部二进制依赖，需系统安装，不利于 Agent 化部署
2. python-docx 已在项目中深度使用，表格/页眉/样式逻辑可直接迁移
3. BeautifulSoup4 提供精确 HTML 解析，CSS class 映射可精确控制
4. pandoc 的 Word 样式控制是黑盒，无法满足企业文档格式要求
5. 符合"渐进式重构"——现有 Word 表格逻辑逐步迁移到 style_mapper

---

## 5. Mermaid 处理方案

### 5.1 双模式策略

```
Mermaid 代码块
      │
      ├─── 构建时渲染 (Word/PDF 输出)
      │    ├── mmdc --outputFormat svg → 矢量图 (推荐)
      │    ├── Kroki API → PNG
      │    └── Python Pillow → PNG
      │    输出: <figure><img src="data:..."></figure>
      │
      └─── 浏览器时渲染 (Online HTML 输出)
           └── <pre class="mermaid"> ... </pre>
                + <script src="mermaid.min.js">
                浏览器端实时渲染为 SVG
```

### 5.2 HTML 输出示例

```html
<!-- Word/PDF: 构建时已渲染为内嵌图片 -->
<figure class="flowchart" data-flowchart-id="1">
  <img src="data:image/svg+xml;base64,..." alt="图 1 用户登录流程">
  <figcaption>图 1 用户登录流程</figcaption>
</figure>

<!-- Online: 浏览器端 mermaid.js 渲染 -->
<pre class="mermaid">
graph TD
    A[开始] --&gt; B[结束]
</pre>
```

---

## 6. 表格样式方案

### 6.1 CSS 设计令牌

```css
:root {
  --table-border-color: #808080;
  --table-border-width: 0.5px;
  --table-header-bg: #D9D9D9;
  --table-cell-padding: 4px 8px;
  --table-font-size: 10pt;
  --table-font: "Microsoft YaHei", sans-serif;
  --table-text-indent: 0;
  --table-align-default: left;
}
```

### 6.2 表格语义化 class

| CSS class | 用途 | 特征 |
|-----------|------|------|
| `.table--data` | 普通数据表 | 全边框 + 表头灰底 |
| `.table--revision` | 修订记录表 | 6列标准布局 |
| `.table--params` | 参数表 | 窄列名 + 宽描述列 |
| `.table--defs` | 定义表 | 术语 + 定义两列 |

### 6.3 CSS → Word 样式映射

```python
# exporters/word/style_mapper.py

ELEMENT_MAP = {
    ('h1',):           'Heading 1',
    ('h2',):           'Heading 2',
    ('h3',):           'Heading 3',
    ('p',):            'Normal',
    ('pre', 'code'):   'CodeBlock',
    ('blockquote',):   'Quote',
}

TABLE_CLASS_MAP = {
    'table--data':     'Table Grid',
    'table--revision': 'Revision Table',
    'table--params':   'Table Grid',
    'table--defs':     'Table Grid',
}
```

---

## 7. HTML 模板方案

采用 **Jinja2 模板继承 + 组件化** 结构：

```
base.html.j2                          # 根模板
├── <head>
│   ├── <meta> 元数据
│   ├── <style> CSS 变量 + 主题 CSS
│   └── <title>
├── <body>
│   ├── {% block cover %}            # 封面（可选）
│   ├── {% block toc %}              # 目录
│   ├── {% block revision %}         # 修订记录
│   └── {% block body %}             # 正文内容
│
document.html.j2                      # extends "base.html.j2"
├── 填充 cover / toc / revision / body
│
tech_doc.html.j2                      # extends "document.html.j2"
├── 额外: 页眉/页脚占位 + 技术文档专用样式
```

---

## 8. Word 导出方案

### 8.1 处理流程

```
HTML 字符串
    │
    ▼
┌──────────────────────┐
│  BeautifulSoup4      │  解析 HTML DOM
│  soup.find_all(...)  │  遍历 body 子元素
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  StyleMapper         │  根据 CSS class 查找映射表
│  .map_element(el)    │  返回 (word_style, format_overrides)
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  DocxBuilder         │  构建 python-docx 对象
│  - add_heading()     │
│  - add_paragraph()   │
│  - add_table()       │
│  - add_image()       │
└──────────┬───────────┘
           │
           ▼
        .docx 文件
```

### 8.2 StyleMapper 核心方法

```python
class StyleMapper:
    def map_element(self, bs4_el) -> tuple[str, dict]:
        """返回 (Word样式名, 额外格式属性)"""

    def map_table_cell(self, bs4_td) -> dict:
        """从 CSS class 推断: align, col_type, is_header"""

    def map_table_class(self, bs4_table) -> str:
        """从 class 推断 Word 表格样式名"""
```

---

## 9. 渐进式重构步骤

### 阶段 1: HTML 渲染引擎（不影响现有功能）

| # | 内容 | 产出物 | 风险 |
|---|------|--------|------|
| 1.1 | 新建 `html_engine/` 目录结构 | 模块骨架 | 无 |
| 1.2 | 实现 AST → HTML 主渲染器 | `renderer.py`：每个 AST 节点→语义化 HTML | 低 |
| 1.3 | 实现内联格式段渲染 | `inline_renderer.py`：粗体/斜体/代码/链接/公式 | 低 |
| 1.4 | 实现基础 CSS 样式表 | `tokens.css` + `base.css` + `components.css` | 低 |
| 1.5 | 实现 Jinja2 模板 | `base.html.j2` + `document.html.j2` | 低 |
| 1.6 | 实现主题基类 + TechDoc 主题 | `themes/base.py` + `themes/tech_doc.py` | 低 |
| 1.7 | 新增 CLI `--format html` | `python -m md_converter.cli doc.md -f html` | 低 |
| 1.8 | 实现 Mermaid 双模式输出 | `flowchart/html_embed.py` | 低 |

**验收**：`--format html` 输出在浏览器中渲染正确，样式美观。

### 阶段 2: Word 通过 HTML 导出

| # | 内容 | 产出物 | 风险 |
|---|------|--------|------|
| 2.1 | BeautifulSoup4 HTML 解析 | `exporters/word/exporter.py` | 中 |
| 2.2 | CSS class → Word 样式映射 | `exporters/word/style_mapper.py` | 中 |
| 2.3 | HTML 表格 → docx 表格构建 | `exporters/word/table_builder.py` | 高 |
| 2.4 | 页眉/页脚从 meta 注入 | 复用旧版 `_replace_header_fields` | 中 |
| 2.5 | TOC & 修订记录 | 复用旧版逻辑 | 中 |
| 2.6 | CLI `-f word` 走新链路，`--legacy` 回退 | 双链路并存 | 低 |

**验收**：新链路 Word 输出与旧版视觉一致或更优。

### 阶段 3: PDF 统一

| # | 内容 | 产出物 | 风险 |
|---|------|--------|------|
| 3.1 | HTML → weasyprint PDF | `exporters/pdf/exporter.py` | 低 |
| 3.2 | print.css PDF 专用样式 | 分页/页边距/字体嵌入 | 低 |

**验收**：PDF 输出质量不低于旧版。

### 阶段 4: 主题系统 & 清理

| # | 内容 | 产出物 |
|---|------|--------|
| 4.1 | 主题切换 CLI `--theme` | 多主题支持 |
| 4.2 | 自定义主题目录 `--theme-dir` | 外部主题 |
| 4.3 | 流程图子系统独立 | 解耦 |
| 4.4 | 旧版代码标记 deprecated | 兼容保留 |

### 阶段 5: 在线预览 & 知识库

| # | 内容 | 产出物 |
|---|------|--------|
| 5.1 | 自包含 HTML（内联资源） | 单文件分发 |
| 5.2 | 目录索引生成 | 多文件站点 |
| 5.3 | Agent 批量接口 | SDK/API |

---

## 10. 风险管理

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 表格 CSS→Word 映射不精确 | Word 输出劣化 | 保留 `--legacy` 回退，A/B 对比测试 |
| Jinja2 模板性能 | 大文档渲染慢 | 按需加载模板，缓存编译结果 |
| weasyprint 字体嵌入 | PDF 中文乱码 | 复用现有字体注册方案 |
| 流程图 HTML 渲染不一致 | 在线/离线显示差异 | 统一 SVG 输出，浏览器端用 mermaid.js |
| 旧版代码维护成本 | 双链路代码膨胀 | 阶段 4 正式废弃旧版，设定时间节点 |
