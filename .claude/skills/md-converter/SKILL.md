---
name: md-converter
description: 将Markdown文件转换为Word/PDF文档。触发词："转word"、"转pdf"、"md转word"、"md转pdf"、"convert markdown"、"md-converter"、指定.md文件要求输出.docx/.pdf
version: 0.1.0
---

# Markdown转Word/PDF转换器

## Overview

你是一个文档转换助手，负责将Markdown文件转换为格式规范的Word (.docx) 或 PDF (.pdf) 文档。你需要调用本项目的转换工具完成任务，并向用户报告转换结果。

## Trigger Conditions

当用户说出以下内容时激活：
- "转word"、"转pdf"、"md转word"、"md转pdf"
- "转换markdown"、"convert markdown"
- "/md-converter"
- 指定 .md 文件要求输出 .docx 或 .pdf

## Steps

1. **确认输入文件存在**：检查用户指定的 `.md` 文件路径是否有效，不存在则报错退出。
2. **构建命令**：skill 触发时会提供 base directory，以此拼接 PYTHONPATH：
   ```bash
   PYTHONPATH=<base_directory>/scripts python -m md_converter.cli <input> [options]
   ```
   其中 `<base_directory>` 即本 skill 的根目录（即包含 SKILL.md 的目录）。
3. **执行转换**：运行上述命令，等待完成。
4. **检查结果**：确认输出文件已生成，报告文件路径和大小。
5. **异常处理**：若转换失败，向用户展示错误信息并给出排查建议。

## Input Parameters

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `input` | 输入文件或目录路径（必需） | - |
| `--format` / `-f` | 输出格式：`word` / `pdf` | `word` |
| `--output` / `-o` | 输出文件或目录路径 | 同输入目录 |
| `--template` / `-t` | Word模板(.docx/.dotx) 或 CSS模板(.css) | 内置G-C045模板 |
| `--doc-title` | 文档标题（替换页眉） | - |
| `--doc-number` | 文件编号（替换页眉） | - |
| `--doc-version` | 版本号（替换页眉） | - |
| `--doc-department` | 制定部门（替换页眉） | - |
| `--doc-company` | 公司名称（替换页眉） | - |
| `--font` | 默认字体（仅无模板时生效） | 宋体 |
| `--font-size` | 默认字号（仅无模板时生效） | 12 |
| `--enable-pdf` | 启用PDF转换（默认关闭） | `false` |
| `--verbose` / `-v` | 详细输出 | `false` |

## Output

- Word文档（.docx）或 PDF文档（.pdf）
- 控制台输出转换结果（成功/失败、文件路径）

## Examples

以下示例中 `$SKILL_DIR` 代表 skill 的 base directory，实际执行时替换为触发时提供的路径。

```bash
# 单文件转Word（自动使用内置G-C045公司模板）
PYTHONPATH=$SKILL_DIR/scripts python -m md_converter.cli report.md --format word

# 使用自定义模板并替换页眉字段
PYTHONPATH=$SKILL_DIR/scripts python -m md_converter.cli report.md \
    --template my_template.docx \
    --doc-title "需求规格说明书" \
    --doc-number "REQ-001" \
    --doc-version "V1.0" \
    --doc-department "开发部" \
    --doc-company "上海XX科技有限公司"

# 指定输出路径
PYTHONPATH=$SKILL_DIR/scripts python -m md_converter.cli report.md -o output/report.docx

# 批量转换目录
PYTHONPATH=$SKILL_DIR/scripts python -m md_converter.cli ./docs --format word --output ./output

# 使用自定义字体（仅无模板时生效）
PYTHONPATH=$SKILL_DIR/scripts python -m md_converter.cli report.md --font "微软雅黑" --font-size 14
```

### 模板加载优先级
1. CLI `--template` 显式指定
2. `templates/` 目录下第一个 `.docx` 文件
3. 内置默认模板（G-C045 公司模板）
4. 无模板时回退硬编码格式（向后兼容）

## Constraints

- 运行命令时必须设置 `PYTHONPATH=<skill_base_directory>/scripts`，否则模块无法导入。skill 触发时会提供 base directory，直接使用即可。
- PDF功能默认关闭，需显式添加 `--enable-pdf` 参数。
- 流程图渲染依赖 `mmdc`（mermaid-cli），未安装时降级为代码块显示。
- 远程图片下载有15秒超时限制。
- 不要自行修改源代码文件，除非用户明确要求。

## Assets

| 资源 | 路径 | 用途 |
|------|------|------|
| 流程图编制规范(MD) | [assets/flowchart_standard.md](assets/flowchart_standard.md) | 流程图 Mermaid 语法参考 |
| 流程图编制规范(DOCX) | [assets/G-C110 流程图编制规范_A0.docx](assets/G-C110%20流程图编制规范_A0.docx) | 原始规范文档 |
| Mermaid主题配置 | [assets/mermaid_theme.json](assets/mermaid_theme.json) | mmdc 渲染主题（黑白风格、楷体字体） |
