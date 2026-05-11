---
name: techdoc-md-renderer
description: 将Markdown技术文档渲染为Word/HTML/PDF。基于统一HTML中间表示架构（AST→HTML→多格式导出）。触发词："转word"、"转html"、"转pdf"、"md转word"、"md转html"、"md转pdf"、"convert markdown"、指定.md文件要求输出.docx/.html/.pdf
version: 0.2.0
---

# TechDoc Markdown 渲染器

## 架构：统一 HTML 渲染层

```
Markdown ──► AST 解析器 ──► HTML 渲染引擎 ──► 语义化 HTML
                                                   │
                          ┌────────────────────────┼────────────────────────┐
                          │                        │                        │
                     Word 导出器               HTML 自包含               PDF 导出器
                     HTML → docx               浏览器直接打开            HTML → PDF
```

**核心原则**：HTML 是唯一的中间表示（IR）。所有输出格式（Word/PDF/Online）都从同一份带 CSS 语义类的 HTML 派生。样式通过 **CSS 设计令牌 + 主题系统** 统一控制，确保跨格式一致性。

### 模块结构

| 模块 | 路径 | 职责 |
|------|------|------|
| AST 解析器 | `parser.py` | Markdown → AST（markdown-it-py） |
| HTML 渲染引擎 | `html_engine/` | AST → 语义化 HTML + CSS class |
| 主题系统 | `html_engine/themes/` | CSS 设计令牌 + 主题注册表 |
| Jinja2 模板 | `html_engine/templates/` | 文档壳 + 可复用组件 |
| CSS 样式表 | `html_engine/css/` | base / tech_doc / components / print |
| 导出器层 | `exporters/` | HTML → Word / HTML / PDF |
| 流程图子系统 | `flowchart/` | Mermaid 检测、渲染、内嵌 |

### 架构演进

| 阶段 | 状态 | 内容 |
|------|------|------|
| Phase 1 | ✅ 完成 | HTML 渲染引擎 + HTML 导出器 + 主题系统 |
| Phase 2 | 🔜 规划中 | Word 导出器（HTML → python-docx + BeautifulSoup4） |
| Phase 3 | ✅ 完成 | PDF 导出器（HTML → weasyprint） |
| Phase 4 | 📋 待定 | 在线预览 + 多主题扩展 |
| Phase 5 | 📋 待定 | 旧版代码清理，--legacy 移除 |

---

你是一个技术文档渲染助手，负责将 Markdown 技术文档渲染为目标格式。你需要调用本项目的转换工具完成任务，并向用户报告结果。

## Trigger Conditions

当用户说出以下内容时激活：
- "转word"、"转html"、"转pdf"
- "md转word"、"md转html"、"md转pdf"
- "转换markdown"、"render markdown"
- "/techdoc-md-renderer" 或 "/md-converter"（兼容旧名）
- 指定 .md 文件要求输出 .docx / .html / .pdf

## Steps

1. **确认输入文件存在**：检查用户指定的 `.md` 文件路径是否有效。
2. **构建命令**：skill 触发时会提供 base directory，以此拼接 PYTHONPATH：
   ```bash
   PYTHONPATH=<base_directory>/scripts python -m cli <input> [options]
   ```
   `<base_directory>` 即本 skill 的根目录。
3. **执行转换**：运行上述命令，等待完成。
4. **检查结果**：确认输出文件已生成，报告文件路径和大小。
5. **异常处理**：若转换失败，向用户展示错误信息并给出排查建议。

## Input Parameters

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `input` | 输入文件或目录路径（必需） | - |
| `--format` / `-f` | 输出格式：`word` / `html` / `pdf` | `word` |
| `--output` / `-o` | 输出文件或目录路径 | 同输入目录 |
| `--template` / `-t` | Word模板(.docx/.dotx) | 内置G-C045模板 |
| `--theme` | HTML/PDF 主题名称 | `tech-doc` |
| `--doc-title` | 文档标题 | 取自文件名 |
| `--doc-number` | 文件编号 | - |
| `--doc-version` | 版本号 | - |
| `--doc-department` | 制定部门 | - |
| `--doc-company` | 公司名称 | - |
| `--font` | 默认字体（仅无模板时生效） | 宋体 |
| `--font-size` | 默认字号（仅无模板时生效） | 12 |
| `--enable-pdf` | 启用PDF转换（默认关闭） | `false` |
| `--verbose` / `-v` | 详细输出 | `false` |

## 主题系统

通过 CSS 设计令牌（CSS 变量）控制文档全部视觉属性，支持主题切换：

| 主题名称 | 说明 |
|----------|------|
| `tech-doc` | **默认**。G-C045 规范风格：楷体正文、黑体标题、Courier New 代码、Microsoft YaHei 表格、黑白配色 |

主题定义的内容维度：字体族、字号层级、颜色体系、间距规则、表格边框/内边距、页面尺寸/边距。

## 输出

| 格式 | 输出文件 | 特点 |
|------|----------|------|
| Word | `.docx` | python-docx 生成，支持模板页眉/页脚 |
| HTML | `.html` | 自包含（内联所有 CSS），浏览器可直接打开 |
| PDF | `.pdf` | weasyprint 渲染，保留分页和 @page 样式 |

## Examples

以下示例中 `$SKILL_DIR` 代表 skill 的 base directory。

```bash
# === Word 格式 ===

# 单文件转Word（默认格式，使用 G-C045 技术文档主题）
PYTHONPATH=$SKILL_DIR/scripts python -m md_converter.cli report.md

# 带完整元数据
PYTHONPATH=$SKILL_DIR/scripts python -m md_converter.cli report.md \
    --template my_template.docx \
    --doc-title "需求规格说明书" \
    --doc-number "REQ-001" \
    --doc-version "V1.0" \
    --doc-department "开发部" \
    --doc-company "上海XX科技有限公司"

# 指定输出路径
PYTHONPATH=$SKILL_DIR/scripts python -m md_converter.cli report.md -o output/report.docx

# === HTML 格式 ===

# 转为自包含 HTML（浏览器直接打开）
PYTHONPATH=$SKILL_DIR/scripts python -m md_converter.cli report.md --format html

# 使用指定主题
PYTHONPATH=$SKILL_DIR/scripts python -m md_converter.cli report.md --format html --theme tech-doc

# === 批量转换 ===

PYTHONPATH=$SKILL_DIR/scripts python -m md_converter.cli ./docs --format word --output ./output
```

## Constraints

- 运行命令时必须设置 `PYTHONPATH=<skill_base_directory>/scripts`，否则模块无法导入。
- 流程图渲染依赖 `mmdc`（mermaid-cli），未安装时 HTML 模式使用浏览器端 mermaid.js 降级。
- PDF 功能依赖 weasyprint，未安装时给出明确错误提示。
- 远程图片下载有 15 秒超时限制。
- 不自行修改源代码文件，除非用户明确要求。

## Assets

| 资源 | 路径 | 用途 |
|------|------|------|
| 流程图编制规范(MD) | [assets/flowchart_standard.md](assets/flowchart_standard.md) | 流程图 Mermaid 语法参考 |
| 流程图编制规范(DOCX) | [assets/G-C110 流程图编制规范_A0.docx](assets/G-C110%20流程图编制规范_A0.docx) | 原始规范文档 |
| Mermaid主题配置 | [assets/mermaid_theme.json](assets/mermaid_theme.json) | mmdc 渲染主题（黑白风格、楷体字体） |
