# TechDoc Markdown 渲染器 — 项目文档

## 项目概述

将 Markdown 技术文档渲染为 Word/HTML/PDF，遵循 G-C045（技术文档）和 G-C110（流程图）公司规范。

**技术栈**：Python + markdown-it-py（解析）+ Jinja2（模板）+ python-docx（Word）+ weasyprint（PDF）+ Pillow（流程图）

## 当前架构

```
Markdown ──► AST (parser.py) ──► HTML 引擎 (html_engine/) ──► 语义化 HTML
                                        │
                   ┌────────────────────┼────────────────────┐
                   │                    │                    │
              Word 导出器           HTML 导出器           PDF 导出器
              (bs4→docx)          (自包含HTML)        (weasyprint)
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
    ├── parser.py                   # Markdown → AST（markdown-it-py）
    ├── batch_processor.py          # 批量处理
    ├── index_generator.py          # 索引页生成
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
    │   │   └── style_mapper.py     #   CSS class → Word 样式映射
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

## 当前风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| 非 flowchart Mermaid 图表仅支持 mmdc/Kroki | 时序图/甘特图等无 Python 渲染 | 降级到 mmdc CLI 或 Kroki API |
| weasyprint 系统依赖 | PDF 不可用 | 引导用户使用 HTML 格式 |
| Word exporter 1405 行单体文件 | 维护困难 | 后续拆分为 footnotes/table/image 独立模块 |

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
