---
name: md-converter
description: 将Markdown文件转换为Word/PDF文档，支持批量处理、模板和样式配置
trigger: 当用户要求转换Markdown文件为Word或PDF时触发
---

# Markdown转Word/PDF Skill

## 功能概述
将Markdown文件转换为Word (.docx) 或 PDF (.pdf) 文档，保留格式和结构。

## 触发条件
- 用户要求转换Markdown文件
- 用户提到"md转word"、"md转pdf"、"markdown转换"等关键词
- 用户指定输入文件或文件夹，要求输出Word/PDF格式

## 输入参数
- `input`: 输入文件或文件夹路径（必需）
- `format`: 输出格式，word或pdf（默认：word）
- `output_dir`: 输出目录（默认：与输入相同目录）
- `template`: 模板文件路径（可选）
- `style`: 样式配置（可选）

## 支持的Markdown元素
- 标题（H1-H6）
- 段落文本
- 强调（粗体、斜体）
- 列表（有序、无序、嵌套）
- 表格
- 图片（本地、远程）
- 代码块
- 链接
- 引用
- 分割线
- 内联公式（LaTeX）
- 脚注

## 输出
- Word文档（.docx）
- PDF文档（.pdf）
- 转换日志

## 使用示例
```
/md-converter input.md --format=word
/md-converter ./docs --format=pdf --output_dir=./output
/md-converter report.md --template=template.dotx
```

## 实现状态
✅ 核心功能已完成，支持完整Markdown元素转换