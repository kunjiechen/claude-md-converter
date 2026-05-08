# Markdown转Word/PDF转换器

将Markdown文件转换为格式规范的Word (.docx) 或 PDF (.pdf) 文档，支持流程图、表格、脚注、任务列表等丰富元素。

## 功能特性

- 完整的Markdown元素支持：标题、段落、列表、表格、代码块、引用、图片、分割线、脚注、任务列表
- 内联格式：粗体、斜体、删除线、行内代码、超链接
- 流程图渲染：Mermaid/PlantUML语法自动转为图片（支持G-C110规范）
- 批量处理：支持目录级别的并行转换
- 字体可配置：默认宋体12号，可自定义

## 安装

```bash
# 安装依赖
pip install -r requirements.txt

# 可选：安装mermaid-cli以支持流程图渲染
npm install -g @mermaid-js/mermaid-cli
```

## 使用方法

```bash
# 单文件转Word（推荐方式）
PYTHONPATH=src python -m md_converter.cli input.md --format word

# 指定输出路径
PYTHONPATH=src python -m md_converter.cli input.md -o output/report.docx

# 批量转换目录下所有md文件
PYTHONPATH=src python -m md_converter.cli ./docs --format word --output ./output

# 自定义字体和字号
PYTHONPATH=src python -m md_converter.cli input.md --font "微软雅黑" --font-size 14

# 启用PDF转换（默认关闭）
PYTHONPATH=src python -m md_converter.cli input.md --format pdf --enable-pdf
```

## 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `input` | 输入文件或目录路径（必需） | - |
| `--format` / `-f` | 输出格式：`word` / `pdf` | `word` |
| `--output` / `-o` | 输出文件或目录路径 | 同输入目录 |
| `--template` / `-t` | Word模板(.dotx) 或 CSS模板(.css) | 无 |
| `--font` | 默认字体 | 宋体 |
| `--font-size` | 默认字号 | 12 |
| `--enable-pdf` | 启用PDF转换 | `false` |
| `--verbose` / `-v` | 详细输出 | `false` |

## 项目结构

```
claude-md-converter/
├── src/md_converter/
│   ├── __init__.py
│   ├── parser.py            # Markdown解析器
│   ├── converter.py         # 格式转换器基类
│   ├── word_converter.py    # Word转换器
│   ├── pdf_converter.py     # PDF转换器（weasyprint）
│   ├── pdf_converter_reportlab.py  # PDF转换器（reportlab）
│   ├── flowchart_renderer.py       # 流程图渲染器（mermaid-cli）
│   ├── flowchart_painter.py        # 流程图渲染器（纯Python/Pillow）
│   ├── batch_processor.py  # 批量处理
│   └── cli.py              # 命令行接口
├── verification/            # 验证测试文档
├── templates/               # 模板文件
├── reference/               # 参考规范文档
└── requirements.txt
```

## 依赖

- Python >= 3.9
- markdown-it-py >= 2.0.0
- python-docx >= 0.8.11
- Pillow >= 9.0.0
- weasyprint >= 59.0（PDF功能可选）

## 已知限制

- 流程图渲染需要安装 `mmdc`（mermaid-cli），未安装时降级为代码块显示
- PDF功能默认关闭，需使用 `--enable-pdf` 启用
- 远程图片下载有15秒超时
