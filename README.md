# Markdown转Word/PDF转换器

将Markdown文件转换为格式规范的Word (.docx) 或 PDF (.pdf) 文档，支持流程图、表格、脚注、任务列表等丰富元素。

## 功能特性

- 完整的Markdown元素支持：标题、段落、列表、表格、代码块、引用、图片、分割线、脚注、任务列表
- 内联格式：粗体、斜体、删除线、下划线、行内代码、超链接、kbd、sub/sup、高亮
- 数学公式：LaTeX 块级公式 `$$` 和内联公式 `$` 支持
- 定义列表：`term\n: definition` 语法支持
- 流程图渲染：Mermaid/PlantUML 语法自动转为图片（支持 G-C110 规范）
- **Word 模板**：三级加载优先级，页眉字段动态替换，样式自动降级
- 批量处理：支持目录级别的并行转换
- 字体可配置：默认宋体 12 号（无模板时），模板模式使用模板样式

## 安装

```bash
# 安装依赖
pip install -r requirements.txt

# 可选：安装mermaid-cli以支持流程图渲染
npm install -g @mermaid-js/mermaid-cli
```

## 使用方法

```bash
# 单文件转Word（自动使用内置G-C045公司模板）
PYTHONPATH=src python -m md_converter.cli input.md --format word

# 指定自己的模板
PYTHONPATH=src python -m md_converter.cli input.md --template my_template.docx

# 替换模板页眉字段
PYTHONPATH=src python -m md_converter.cli input.md \
    --doc-title "需求规格说明书" \
    --doc-number "REQ-001" \
    --doc-version "V1.0" \
    --doc-department "开发部" \
    --doc-company "上海XX科技有限公司"

# 放模板到 templates/ 目录，自动选用
mkdir templates && cp my_template.docx templates/

# 指定输出路径
PYTHONPATH=src python -m md_converter.cli input.md -o output/report.docx

# 批量转换目录下所有md文件
PYTHONPATH=src python -m md_converter.cli ./docs --format word --output ./output

# 自定义字体和字号（仅无模板时生效）
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
| `--template` / `-t` | Word模板(.docx/.dotx) 或 CSS模板(.css) | 内置G-C045模板 |
| `--doc-title` | 文档标题（替换模板页眉标题位） | - |
| `--doc-number` | 文件编号（替换模板页眉编号位） | - |
| `--doc-version` | 版本号（替换模板页眉版本位） | - |
| `--doc-department` | 制定部门（替换模板页眉部门位） | - |
| `--doc-company` | 公司名称（替换模板页眉公司名位） | - |
| `--font` | 默认字体（仅无模板时生效） | 宋体 |
| `--font-size` | 默认字号（仅无模板时生效） | 12 |
| `--enable-pdf` | 启用PDF转换 | `false` |
| `--verbose` / `-v` | 详细输出 | `false` |

### 模板加载优先级

1. CLI 参数 `--template` 显式指定
2. `templates/` 目录下第一个 `.docx` 文件
3. 内置默认模板（G-C045 公司模板）

未找到任何模板时，回退为硬编码格式（宋体 12pt），保持向后兼容。

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
