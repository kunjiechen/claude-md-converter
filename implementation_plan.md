# Markdown转Word/PDF Skill 实现计划

## 项目概述
基于需求文档，实现一个完整的Markdown转Word/PDF转换工具。

## 技术栈选择
- **Python**：主要开发语言
- **markdown-it-py**：Markdown解析
- **python-docx**：Word文档生成
- **weasyprint/reportlab**：PDF生成（推荐weasyprint，样式保真度高）

## 流程图/图表实现方案

### 技术选型
1. **Mermaid**：JavaScript图表库，支持流程图、时序图、甘特图等
2. **PlantUML**：Java图表库，支持UML图、架构图等

### 实现方式
#### 方案A：本地渲染（推荐）
- 安装mermaid-cli（Node.js）
- 调用命令行工具渲染为PNG/SVG
- 优点：离线可用，速度快
- 缺点：需要安装Node.js

#### 方案B：在线API渲染
- 使用Mermaid Live Editor API
- 优点：无需本地安装
- 缺点：依赖网络，有调用限制

#### 方案C：Python库渲染
- 使用pydyf + mermaid-py
- 优点：纯Python实现
- 缺点：功能可能不完整

### 推荐方案
**方案A：本地渲染**
- 安装mermaid-cli：`npm install -g @mermaid-js/mermaid-cli`
- 解析Mermaid语法块
- 调用mmdc命令渲染为PNG
- 插入Word/PDF文档

### 支持的图表类型
```mermaid
graph TD    # 流程图
sequenceDiagram  # 时序图
gantt       # 甘特图
classDiagram # 类图
stateDiagram # 状态图
pie         # 饼图
```

### 公司规范要求（G-C110）
**符号规范**：
- 数据符号：平行四边形
- 处理符号：矩形
- 判断：菱形
- 循环界限：去角矩形
- 流线：带箭头线
- 连接符：圆形
- 端点符：圆角矩形

**样式规范**：
- 字体：楷体，10号
- 流向：从左到右，从上到下
- 流线：必须有箭头
- 符号：保持水平，不能镜像
- 布局：避免流线交叉，并行流程同高

**判断框出线规范**：
- 入口：上方顶点
- 成立出口：正下方顶点
- 不成立出口：右中方顶点

**循环表示**：
- For循环：初始化→判断→循环体→增量→判断
- While循环：初始化→判断→循环体→判断
- Do-while循环：循环体→判断→循环体

**页面控制**：
- 流程图不能垮页
- 使用连接符拆分大图
- 合理安排符号位置，避免过长流线

## 实现阶段

### 第一阶段：基础框架搭建（1-2天）
1. **项目结构初始化**
   - 创建Python包结构
   - 设置依赖管理（requirements.txt/pyproject.toml）
   - 配置开发环境

2. **核心模块设计**
   - `parser.py`：Markdown解析器
   - `converter.py`：格式转换器基类
   - `word_converter.py`：Word转换器
   - `pdf_converter.py`：PDF转换器
   - `cli.py`：命令行接口

### 第二阶段：Markdown解析实现（2-3天）
1. **解析器实现**
   - 集成markdown-it-py
   - 支持扩展语法（表格、代码块、公式等）
   - AST遍历和节点处理

2. **元素映射**
   - 标题 → Word样式/PDF样式
   - 段落 → 普通文本
   - 列表 → 列表样式
   - 表格 → 表格对象
   - 代码块 → 代码样式
   - 图片 → 图片插入

### 第三阶段：Word转换实现（3-4天）
1. **python-docx集成**
   - 文档创建和样式设置
   - 模板支持
   - 样式覆盖机制

2. **元素转换**
   - 标题样式映射
   - 段落格式化
   - 列表处理
   - 表格生成
   - 图片插入
   - 代码块样式

### 第四阶段：PDF转换实现（2-3天）
1. **方案选择**
   - 方案A：Word → PDF（通过python-docx + comtypes）
   - 方案B：直接PDF生成（weasyprint）
   - 推荐方案B，跨平台兼容性好

2. **样式保真**
   - CSS样式定义
   - 字体嵌入
   - 分页控制
   - 页眉页脚

### 第五阶段：批量处理和日志（1-2天）
1. **批量处理**
   - 文件夹遍历
   - 文件过滤
   - 并行处理

2. **日志系统**
   - 转换日志记录
   - 错误处理
   - 进度显示

### 第六阶段：测试和优化（2-3天）
1. **单元测试**
   - 解析器测试
   - 转换器测试
   - 集成测试

2. **性能优化**
   - 内存优化
   - 处理速度优化
   - 大文件处理

## 文件结构
```
claude-md-converter/
├── .claude/
│   └── skills/
│       └── md-converter.md
├── src/
│   └── md_converter/
│       ├── __init__.py
│       ├── parser.py
│       ├── converter.py
│       ├── word_converter.py
│       ├── pdf_converter.py
│       ├── flowchart_renderer.py
│       ├── flowchart_painter.py
│       ├── batch_processor.py
│       └── cli.py
├── verification/
│   ├── verification_full.md    # 完整验证测试文档
│   ├── verification_plan.md    # 验证计划和清单
│   └── output/                 # 验证输出目录
├── templates/
├── reference/
│   ├── G-C110 流程图编制规范_A0.docx
│   └── flowchart_standard.md
├── requirements.txt
└── README.md
```

## 依赖管理
```txt
# requirements.txt
markdown-it-py>=2.0.0
mdit-py-plugins>=0.3.0
python-docx>=0.8.11
weasyprint>=59.0
Pillow>=9.0.0
click>=8.0.0
```

## 使用方式
```bash
# 安装
pip install -e .

# 使用
md-converter input.md --format=word
md-converter ./docs --format=pdf --output=./output
```

## 预计总时间：10-15天

## 优先级
1. **高优先级**：基础Markdown解析 + Word转换
2. **中优先级**：PDF转换 + 批量处理
3. **低优先级**：模板支持 + 高级样式

## 风险评估

### 高风险项（当前）

1. **流程图非graph类型依赖外部工具**
   - 风险：时序图(sequenceDiagram)、甘特图(gantt)、类图(classDiagram)等非flowchart类型，Python渲染器无法处理
   - 影响：无Chrome/mmdc环境下这些图表类型无法渲染
   - 缓解方案：降级为代码块显示；后续扩展Python渲染器

2. **PDF内联格式缺失**
   - 风险：PDF转换器未处理内联格式段（segments），粗体/斜体/代码/链接/脚注全部丢失
   - 影响：PDF输出质量差，不适合正式交付
   - 缓解方案：重构PDF转换器支持segments

3. **LaTeX/数学公式不支持**
   - 风险：`$...$` 和 `$$...$$` 公式未被解析和渲染
   - 影响：技术文档中的数学公式丢失
   - 缓解方案：启用markdown-it-py math插件

### 中风险项

4. **HTML内联元素不支持**
   - 风险：`<kbd>`、`<sub>`、`<sup>`、`==highlight==` 被静默丢弃
   - 影响：扩展语法内容丢失
   - 缓解方案：处理html_inline token类型

5. **表格单元格无内联格式**
   - 风险：表格单元格以纯文本写入，单元格内格式丢失
   - 影响：富文本表格转换后格式错误
   - 缓解方案：parser提取cell segments + word_converter逐段添加

6. **模板支持未实现**
   - 风险：模板功能仅为接口预留
   - 影响：无法满足企业定制需求
   - 缓解方案：后续版本实现

### 低风险项

7. **嵌套引用块无渐进缩进** — 多层嵌套引用块渲染为同级
8. **定义列表无特殊格式** — `term\n: definition` 渲染为普通段落
9. **Word原生脚注未使用** — 当前为模拟实现，非Word原生`w:footnoteReference`
10. **高级Word功能缺失** — 页眉/页脚、目录(TOC)、硬分页符、页码未实现
11. **依赖兼容性** — 跨平台字体和渲染差异
12. **Kroki API稳定性** — 在线API响应慢/超时

### 已知限制（当前）

1. **PDF功能默认关闭**，需 `--enable-pdf` 参数启用；两个PDF转换器均无内联格式支持
2. **模板支持**仅预留接口，样式覆盖机制未实现
3. **PlantUML**需依赖plantuml CLI或Kroki API，Python渲染器不支持
4. **非flowchart图表**（时序图/甘特图/类图/状态图/饼图）仅支持mmdc CLI或Kroki API

## 进度跟踪

### 第一阶段：基础框架搭建 ✅ 已完成
- [x] 创建Python包结构
- [x] 设置依赖管理（requirements.txt）
- [x] 配置开发环境
- [x] 创建核心模块骨架代码
  - parser.py：Markdown解析器
  - converter.py：格式转换器基类
  - word_converter.py：Word转换器
  - pdf_converter.py：PDF转换器
  - cli.py：命令行接口

### 第二阶段：Markdown解析实现 ✅ 已完成
- [x] 集成markdown-it-py
- [x] 支持扩展语法（表格、代码块、公式等）
- [x] AST遍历和节点处理

**实现细节：**
- 使用markdown-it-py作为解析引擎
- 实现TokenConverter类，将token流转换为自定义AST
- 支持元素：标题、段落、列表、表格、代码块、引用、图片、分割线、脚注、任务列表
- 表格支持通过md.enable('table')启用，支持列对齐信息提取
- 删除线通过md.enable('strikethrough')启用
- 脚注通过mdit-py-plugins的footnote_plugin启用
- 内联格式解析：粗体、斜体、删除线、行内代码、超链接、脚注引用
- 任务列表检测：自动识别[x]/[ ]标记
- 图片解析支持本地和远程URL

### 第三阶段：Word转换实现 ✅ 已完成
- [x] python-docx集成
- [x] 元素转换实现
- [x] 内联格式支持（粗体、斜体、删除线、行内代码）
- [x] 超链接支持（蓝色+下划线可点击链接）
- [ ] 模板支持（设计预留，后续实现）

**实现细节：**
- 使用python-docx库生成Word文档
- 支持元素：标题、段落、列表、表格、代码块、引用、图片、分割线、脚注、任务列表
- 字体设置：默认宋体，12号
- 中文字体支持：使用qn('w:eastAsia')设置
- 内联格式：粗体、斜体、删除线、行内代码（Courier New + 灰底）、超链接（蓝色下划线可点击）
- 列表支持：有序列表、无序列表、嵌套列表、任务列表（☑/☐复选框）
- 表格支持：自动创建表格，设置边框样式，支持列对齐（左/中/右）
- 代码块：Courier New等宽字体 + 浅灰背景底纹
- 引用块：左侧灰色竖线 + 缩进
- 分割线：段落底部边框实现
- 脚注：正文上标编号 + 文档末尾脚注列表
- 图片插入：支持本地图片、相对路径解析、远程图片下载
- 内联格式：`**粗体**`、`*斜体*`、`~~删除线~~`、`` `行内代码` `` 均正确映射到Word格式
- 超链接：`[text](url)` 转为蓝色下划线可点击链接
- 删除线：通过markdown-it-py的strikethrough插件启用

### 第四阶段：PDF转换实现 ✅ 已完成（暂时关闭）
- [x] 方案选择和实现
- [x] 样式保真
- [ ] 模板支持（设计预留，后续实现）

**实现细节：**
- 提供两种PDF生成方案：
  1. weasyprint版本：需要系统依赖pango，样式灵活
  2. reportlab版本：纯Python实现，无系统依赖
- 支持元素：标题、段落、列表、表格、代码块、引用、图片、分割线
- 默认样式：宋体，12号，A4页面
- 中文字体支持：自动检测系统字体
- 预留模板接口：支持自定义CSS模板（weasyprint）或样式配置（reportlab）

**当前状态：PDF功能默认关闭**
- **关闭原因**：等待Word功能调试完成后再开启
- **启用方式**：使用 `--enable-pdf` 参数启用
- **示例**：`md-converter input.md --format pdf --enable-pdf`
- **配置位置**：cli.py 中的 `--enable-pdf` 参数

### 第四阶段补充：流程图/图表支持 ✅ 已完成
- [x] Mermaid语法解析
- [x] PlantUML语法解析
- [x] 图表渲染为图片
- [x] 插入Word/PDF文档
- [x] 遵循公司规范：G-C110 流程图编制规范_A0（需要安装mmdc）
- [x] Python纯绘图渲染器（Pillow）- 无需Chrome依赖
- [x] For循环流程图支持 - 完全遵循G-C110规范

**实现细节：**
- 创建FlowchartProcessor类，支持流程图检测和渲染
- 创建MermaidRenderer类，支持Mermaid语法渲染（需要mmdc）
- 创建PlantUMLRenderer类，支持PlantUML语法渲染（需要plantuml）
- 创建FlowchartPythonRenderer类，使用Pillow纯Python渲染（无需Chrome）
- 更新WordConverter，自动检测并渲染流程图
- 更新PDFConverter，自动检测并渲染流程图
- 流程图渲染失败时，降级为代码块显示
- 添加14个流程图测试用例，全部通过

**For循环实现细节：**
- 实现For循环自动检测（_detect_for_loop方法）
- 实现For循环专用布局（_layout_for_loop方法）
- 实现For循环专用走线（_draw_for_loop_edge方法）

**Switch Case实现细节：**
- 实现Switch Case自动检测（_detect_switch_case方法）
- 实现Switch Case专用布局（_layout_switch_case方法）
- 实现Switch Case专用走线（_draw_switch_case_edge方法）
- 布局规范：
  - 开始→初始化→判断→循环体→增量→结束
  - 初始化在判断正上方，循环体在判断正下方，增量在判断右侧
  - left_margin = 判断节点宽度（为左侧出线留出空间）
- 走线规范：
  - 开始→初始化：垂直线
  - 初始化→判断：垂直线
  - 判断→循环体（是）：垂直线
  - 循环体→增量：右侧出横线，向上折到增量节点下方边框中点
  - 增量→判断：上方出线，上竖后左横到判断框正上方的线上
  - 判断→结束（否）：左侧出线，先左横半个框长度，再下竖，再右横到结束框上方，最后下连接到结束框
- 遵循G-C110规范：
  - 不允许斜线，只使用水平线和垂直线
  - 判断框入口在上方顶点
  - 判断成立出口在下方顶点
  - 判断不成立出口在左中方顶点（For循环专用）

**环境配置：**
- 安装mermaid-cli：`npm install -g @mermaid-js/mermaid-cli`
- 配置Chrome路径：`export PUPPETEER_EXECUTABLE_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"`
- Python渲染器依赖：Pillow（已包含在requirements.txt）

### 第五阶段：批量处理和日志 ✅ 已完成
- [x] 批量处理实现
- [x] 日志系统

**实现细节：**
- 创建BatchProcessor类，支持批量转换
- 使用ThreadPoolExecutor实现并行处理
- 支持目录遍历和文件过滤
- 实现JSON格式日志记录
- 支持进度显示和错误统计
- 更新cli.py支持批量处理命令

### 第六阶段：测试和优化 ✅ 已完成
- [x] 单元测试
- [x] 性能优化

**实现细节：**
- 创建完整的测试套件：
  - 解析器测试：12个测试用例
  - 转换器测试：14个测试用例
  - 集成测试：12个测试用例
- 测试覆盖：标题、段落、列表、表格、代码块、引用、图片、分割线
- 批量处理测试：目录遍历、并行处理、日志记录
- 端到端测试：完整的转换流程验证
- 所有测试通过：38个测试用例，1.51秒完成

### 第七阶段：Word格式元素调试（当前进行中）

流程图已完成调试，以下是剩余需要调试的Markdown元素，按优先级排列：

#### 调试总览

| 序号 | 元素 | 优先级 | 当前状态 | 涉及文件 | 复杂度 |
|------|------|--------|----------|----------|--------|
| 1 | 内联格式（粗体/斜体/删除线/行内代码） | 高 | ✅ 已完成 | parser.py + word_converter.py | 中 |
| 2 | 超链接 | 高 | ✅ 已完成 | parser.py + word_converter.py | 低 |
| 3 | 分割线样式 | 中 | ✅ 已完成 | word_converter.py | 低 |
| 4 | 代码块背景色 | 中 | ✅ 已完成 | word_converter.py | 低 |
| 5 | 引用块左边框 | 中 | ✅ 已完成 | word_converter.py | 低 |
| 6 | 表格列对齐 | 中 | ✅ 已完成 | parser.py + word_converter.py | 低 |
| 7 | 远程图片下载 | 低 | ✅ 已完成 | word_converter.py | 低 |
| 8 | 图片相对路径 | 低 | ✅ 已完成 | word_converter.py | 低 |
| 9 | 脚注 | 低 | ✅ 已完成 | parser.py + word_converter.py | 中 |
| 10 | 任务列表 | 低 | ✅ 已完成 | parser.py + word_converter.py | 低 |

---

#### 调试项1：内联格式（高优先级）✅ 已完成

**问题描述**：`_process_inline_content()` 方法当前直接将整段文本作为纯文本添加，`**粗体**`、`*斜体*`、`~~删除线~~`、`` `行内代码` `` 等格式全部丢失。

**根本原因**：parser.py 的 `_handle_paragraph_open()` 仅提取 `token.content`（纯文本），未解析 inline token 的 children（`strong_open`/`strong_close`、`em_open`/`em_close`、`code_inline`、`s_open`/`s_close`）。

**实现方案**：
1. **parser.py**：
   - 新增 `_parse_inline_segments()` 方法，解析 inline token 的 children 为结构化段列表
   - 新增 `_merge_link_segments()` 方法，合并 link_start/link_end 为完整 link 节点
   - 修改 `_handle_paragraph_open()`、`_handle_heading_open()`、`_process_list_item()` 使用 segments
   - 启用 `strikethrough` 插件支持 `~~删除线~~` 语法
2. **word_converter.py**：
   - 重写 `_process_inline_content()` 支持 segments 参数，为每段创建独立 Run 并设置格式
   - 行内代码使用 Courier New 字体 + 浅灰底纹（`w:shd`）

**验收标准**：`verification/verification_full.md` 第1.2/1.3节中 `**粗体**`→Word粗体、`*斜体*`→Word斜体、`~~删除线~~`→Word删除线、`` `code` ``→等宽字体

---

#### 调试项2：超链接（高优先级）✅ 已完成

**问题描述**：`[text](url)` 在Word中不生成可点击链接。parser 定义了 `NODE_LINK` 常量但无 handler，word_converter 无链接处理逻辑。

**实现方案**：
1. **parser.py**：在 `_parse_inline_segments()` 中检测 `link_open`/`link_close` token，通过 `_merge_link_segments()` 合并为 `{"type": "link", "content": "显示文本", "href": "url", "title": "..."}` 节点
2. **word_converter.py**：
   - 新增 `_add_hyperlink()` 方法，通过 OXML 创建 `w:hyperlink` 元素
   - 链接样式：蓝色字体（`#0563C1`）+ 单下划线
   - 在 `_process_inline_content()` 中处理 `link` 类型段

**验收标准**：`verification/verification_full.md` 第6节中 `[GitHub](https://github.com)` 在Word中显示为蓝色可点击链接

---

#### 调试项3：分割线样式（中优先级）✅ 已完成

**问题描述**：`_add_hr()` 当前使用50个下划线字符 `_____` 作为占位，非真正分割线。

**实现方案**：使用 OXML 段落底部边框（`w:pBdr` + `w:bottom`），单线、6pt宽、灰色 #BFBFBF

**验收标准**：`---` 在Word中显示为一条水平灰色分隔线

---

#### 调试项4：代码块背景色（中优先级）✅ 已完成

**问题描述**：代码块仅有等宽字体和缩进，无背景色区分。

**实现方案**：使用 OXML 段落底纹（`w:shd`），填充色 `#F5F5F5` 浅灰

**验收标准**：代码块区域有浅灰色背景，与普通段落明显区分

---

#### 调试项5：引用块左边框（中优先级）✅ 已完成

**问题描述**：引用块仅有缩进和斜体，无左侧竖线标识。

**实现方案**：使用 OXML 段落左边框（`w:pBdr` + `w:left`），单线、18pt宽、灰色 #BFBFBF

**验收标准**：引用块左侧有灰色竖线，视觉上与普通段落区分

---

#### 调试项6：表格列对齐（中优先级）✅ 已完成

**问题描述**：Markdown表格的 `:---:`（居中）、`---:`（右对齐）对齐方式被忽略，所有单元格默认左对齐。

**实现方案**：
1. **parser.py**：`_process_table_cell()` 从 `th_open`/`td_open` token 的 `attrs['style']` 中提取 `text-align` 值，存入 `attributes.align`
2. **word_converter.py**：`_add_table()` 中根据 `align` 设置单元段落对齐（`WD_ALIGN_PARAGRAPH.CENTER`/`RIGHT`）

**验收标准**：`verification/verification_full.md` 第3.3节对齐表格中，居中列文本居中，右对齐列文本右对齐

---

#### 调试项7-8：图片路径处理（低优先级）✅ 已完成

**问题描述**：
- 远程图片（http/https URL）未实现下载
- 相对路径图片未基于输入文件路径解析

**实现方案**：
- **远程图片**：新增 `_download_remote_image()` 方法，使用 `urllib.request.urlopen()` 下载到临时目录（15秒超时），自动推断文件扩展名
- **相对路径**：`convert_file()` 中记录 `input_dir`，`_add_image()` 中先尝试绝对路径，再尝试 `input_dir / src` 相对路径

**验收标准**：本地相对路径图片正确插入，远程图片下载后插入（网络可用时）

---

#### 调试项9：脚注（低优先级）✅ 已完成

**问题描述**：`[^1]` 和 `[^1]: content` 语法未解析和转换。

**实现方案**：
1. **parser.py**：安装并启用 `mdit-py-plugins` 的 `footnote_plugin`；新增 `_handle_footnote_block_open()` 和 `_process_footnote()` 处理脚注块；在 `_parse_inline_segments()` 中处理 `footnote_ref` token
2. **word_converter.py**：
   - `_process_inline_content()` 中处理 `footnote_ref`，渲染为蓝色上标编号 `[N]`
   - 新增 `_add_footnote_block()` 方法，在文档末尾渲染脚注列表（分隔线 + 编号 + 内容）

**验收标准**：脚注文本有上标编号，注释内容在文档末尾

---

#### 调试项10：任务列表（低优先级）✅ 已完成

**问题描述**：`- [x]` 和 `- [ ]` 语法未特殊处理。

**实现方案**：
1. **parser.py**：`_process_list_item()` 中检测 inline content 是否以 `[x]`/`[X]`/`[ ]` 开头，设置 `task_checked` 属性并从内容中移除标记
2. **word_converter.py**：`_add_list()` 中检测 `task_checked` 属性，在内容前添加 `☑`（已完成）或 `☐`（未完成）复选框字符

**验收标准**：已完成任务显示 `☑` 勾选标记，未完成任务显示 `☐` 空白框

---

### 调试执行顺序建议

```
第一批（核心格式）✅ 已完成：
  ├── 调试项1：内联格式 → parser.py + word_converter.py
  └── 调试项2：超链接   → parser.py + word_converter.py

第二批（样式优化）✅ 已完成：
  ├── 调试项3：分割线   → word_converter.py
  ├── 调试项4：代码块背景 → word_converter.py
  ├── 调试项5：引用块边框 → word_converter.py
  └── 调试项6：表格对齐  → parser.py + word_converter.py

第三批（可选增强）✅ 已完成：
  ├── 调试项7：远程图片  → word_converter.py
  ├── 调试项8：相对路径  → word_converter.py + cli.py
  ├── 调试项9：脚注     → parser.py + word_converter.py
  └── 调试项10：任务列表 → parser.py + word_converter.py
```

每完成一个调试项后，使用 `verification/verification_full.md` 中对应的测试章节进行验证。

---

### 第八阶段：剩余格式元素调试（当前进行中）

Phase 7 的10个调试项已全部完成，以下是新识别出的待实现/待修复项，按优先级排列：

#### 调试总览

| 序号 | 元素 | 优先级 | 当前状态 | 涉及文件 | 复杂度 |
|------|------|--------|----------|----------|--------|
| 1 | 表格单元格内联格式 | 高 | ✅ 已完成 | parser.py + word_converter.py | 中 |
| 2 | LaTeX/数学公式 | 高 | ✅ 已完成 | parser.py + word_converter.py + pdf_converter.py | 高 |
| 3 | HTML内联元素（kbd/sub/sup/mark） | 中 | ✅ 已完成 | parser.py + word_converter.py + pdf_converter.py | 中 |
| 4 | PDF内联格式支持 | 中 | ✅ 已完成 | pdf_converter.py + pdf_converter_reportlab.py | 高 |
| 5 | 定义列表支持 | 中 | ✅ 已完成 | parser.py + word_converter.py + pdf_converter.py | 中 |
| 6 | 嵌套引用块渐进缩进 | 低 | ❌ 未实现 | word_converter.py | 低 |
| 7 | ==highlight== 高亮语法 | 低 | ❌ 未实现 | parser.py + word_converter.py | 低 |
| 8 | Word原生脚注 | 低 | ❌ 未实现 | word_converter.py | 中 |
| 9 | 非flowchart图表Python渲染 | 低 | ❌ 未实现 | flowchart_painter.py | 高 |
| 10 | 页眉/页脚/页码 | 低 | ❌ 未实现 | word_converter.py | 中 |
| 11 | 目录(TOC) | 低 | ❌ 未实现 | word_converter.py | 低 |
| 12 | 硬分页符 | 低 | ❌ 未实现 | word_converter.py + parser.py | 低 |

---

#### 调试项1：表格单元格内联格式（高优先级）

**问题描述**：`_add_table()` 中通过 `cell.text = cell_node.get('content', '')` 写入纯文本，单元格内的 `**粗体**`、`*斜体*`、`` `代码` ``、`[链接](url)` 等格式全部丢失。

**根本原因**：
1. **parser.py** `_process_table_cell()`：从 inline token 仅提取 `content`（纯文本），未调用 `_parse_inline_segments()` 提取结构化段
2. **word_converter.py** `_add_table()`：使用 `cell.text` 一次性写入纯文本，未逐段添加 Run

**实现方案**：
1. **parser.py**：修改 `_process_table_cell()`，调用 `self._parse_inline_segments(inline_token)` 提取 segments，存入 `children`
2. **word_converter.py**：修改 `_add_table()`，当 `cell_node` 有 `children`（segments）时，清除默认段落，逐段调用 `_process_inline_content()` 添加格式化 Run

**验收标准**：表格单元格中 `**粗体**`→Word粗体、`*斜体*`→Word斜体、`` `代码` ``→等宽字体

---

#### 调试项2：LaTeX/数学公式（高优先级）

**问题描述**：`$a^2 + b^2 = c^2$` 内联公式和 `$$\sum$$` 块级公式被当作普通文本渲染，公式完全丢失。

**根本原因**：
1. markdown-it-py 未启用 math 插件
2. parser 未处理 `math_inline` / `math_block` token 类型
3. word_converter 无公式插入逻辑

**实现方案**：
1. 安装 `markdown-it-math` 或使用 `mdit-py-plugins` 的 `texmath` 插件
2. **parser.py**：启用 math 插件；新增 `_handle_math_inline()` / `_handle_math_block()` 处理公式 token
3. **word_converter.py**：两种方案可选：
   - 方案A（高保真）：使用 OMML (Office Math Markup Language) 插入 Word 公式对象
   - 方案B（降级）：渲染为图片（使用 matplotlib mathtext）插入
   - 方案C（占位）：插入 `[公式]` 占位文本

**验收标准**：`verification/verification_full.md` 第11节中 `$a^2 + b^2 = c^2$` 在 Word 中显示为公式

---

#### 调试项3：HTML内联元素（中优先级）

**问题描述**：`<kbd>Ctrl</kbd>`、`<sub>`、`<sup>`、`<mark>` 等 HTML 内联标签被 markdown-it-py 解析为 `html_inline` token，但 `_parse_inline_segments()` 未处理此类型，内容被静默丢弃。

**根本原因**：`_parse_inline_segments()` 的 child token 类型处理列表中缺少 `html_inline` 分支。

**实现方案**：
1. **parser.py**：在 `_parse_inline_segments()` 中新增 `html_inline` 处理分支：
   - `<kbd>` → `{"type": "kbd", "content": "..."}`
   - `<sub>` → `{"type": "sub", "content": "..."}`
   - `<sup>` → `{"type": "sup", "content": "..."}`
   - `<mark>` → `{"type": "highlight", "content": "..."}`
   - 其他 → 提取 innerText 作为纯文本
2. **word_converter.py**：在 `_process_inline_content()` 中处理新类型：
   - `kbd` → Courier New + 边框底纹模拟按键样式
   - `sub` → `run.font.subscript = True`
   - `sup` → `run.font.superscript = True`
   - `highlight` → 黄色背景底纹

**验收标准**：`<kbd>Ctrl</kbd>` 显示为按键样式，`<sub>`/`<sup>` 正确上下标

---

#### 调试项4：PDF内联格式支持（中优先级）

**问题描述**：weasyprint 和 reportlab 两种 PDF 转换器均未处理内联格式段（segments），所有段落仅使用 `node.get('content', '')` 纯文本。粗体、斜体、行内代码、超链接、脚注引用在 PDF 中全部丢失。

**根本原因**：
1. `pdf_converter.py` `_process_paragraph()` / `_process_heading()` 仅输出 `node.get('content')` 纯文本
2. `pdf_converter_reportlab.py` 同样未使用 segments

**实现方案**：
1. **pdf_converter.py (weasyprint)**：修改 `_process_paragraph()`，遍历 `segments` 生成对应 HTML 标签（`<strong>`、`<em>`、`<code>`、`<a href>`、`<sup>` 等）
2. **pdf_converter_reportlab.py**：修改相应方法，为每种 segment 类型使用 reportlab 的对应样式

**验收标准**：PDF 中 `**粗体**` 显示为粗体，`[链接](url)` 可点击

---

#### 调试项5：嵌套引用块渐进缩进（低优先级）

**问题描述**：多层嵌套引用块（`> > > 三层引用`）渲染为同级引用块，视觉上无层级区分。

**根本原因**：`_handle_blockquote_open()` 未记录嵌套深度，`_add_blockquote()` 使用固定 `left_indent = Cm(2)`。

**实现方案**：
1. **parser.py**：在 blockquote 节点的 `attributes` 中记录嵌套深度 `level`
2. **word_converter.py**：`_add_blockquote()` 根据 `level` 递增 `left_indent`（基准 `Cm(2)`，每级 `+ Cm(1)`）

**验收标准**：三层嵌套引用块呈现三级递进缩进

---

#### 调试项6：定义列表支持（低优先级）

**问题描述**：Markdown 定义列表语法（`term\n: definition`）未被识别为独立元素，渲染为普通段落。

**根本原因**：markdown-it-py 未启用 `deflist` 插件。

**实现方案**：
1. **parser.py**：启用 `md.enable('deflist')`；新增 `_handle_dl_open()` / `_handle_dt_open()` / `_handle_dd_open()` handler
2. **word_converter.py**：新增 `_add_definition_list()` 方法，术语使用粗体+缩进，定义使用进一步缩进

**验收标准**：`术语\n: 定义` 呈现术语（粗体）和定义（缩进）的视觉层次

---

#### 调试项7：==highlight== 高亮语法（低优先级）

**问题描述**：`==高亮文本==` 语法未识别，渲染为普通文本（包含 `==` 符号）。

**根本原因**：未启用 markdown-it-py 的 mark 插件。

**实现方案**：
1. 安装并启用 `markdown-it-py` 的 mark 插件（或自定义实现）
2. **parser.py**：在 `_parse_inline_segments()` 中处理 `mark_open` / `mark_close` token，生成 `{"type": "highlight", ...}` 段
3. **word_converter.py**：在 `_process_inline_content()` 中处理 `highlight` 类型，使用黄色底纹（`FFFF00`）

**验收标准**：`==高亮文本==` 显示为黄色背景高亮

---

#### 调试项8：Word原生脚注（低优先级）

**问题描述**：当前脚注使用上标文本 `[N]` + 文档末尾列表模拟，非 Word 原生 `w:footnoteReference`。无法使用 Word 的脚注导航、自动页面底部分页等功能。

**根本原因**：python-docx 对原生脚注的 API 支持有限，需要直接操作 OXML。

**实现方案**：
- 使用 python-docx 的 OXML 操作创建 `w:footnoteReference` 和 `w:footnote`
- 在 `word/footnotes.xml` 中添加脚注内容
- 在正文中使用 `w:footnoteReference` 引用

**验收标准**：Word 中脚注显示在页面底部，可点击导航

---

#### 调试项9：非flowchart图表Python渲染（低优先级）

**问题描述**：时序图(sequenceDiagram)、甘特图(gantt)、类图(classDiagram)、状态图(stateDiagram)、饼图(pie) 等非 flowhchart 类型的 Mermaid 图表，Python/Pillow 渲染器无法处理，只能降级到 mmdc CLI 或 Kroki API。

**根本原因**：`flowchart_painter.py` 的 `MermaidParser` 仅解析 `graph`/`flowchart` 语法。

**实现方案**：
- 按图表类型逐步扩展 Python 渲染器：
  1. 时序图（sequenceDiagram）：使用 Pillow 绘制 lifeline 和消息箭头
  2. 类图（classDiagram）：绘制 UML 类框和关系线
  3. 甘特图（gantt）：绘制时间条和依赖箭头

**验收标准**：至少支持时序图和甘特图的 Python 渲染

---

#### 调试项10-12：高级Word功能（低优先级）

**10. 页眉/页脚**：在 `_create_document()` 中通过 `doc.sections[0].header` 添加页眉，`doc.sections[0].footer` 添加页脚。支持从配置读取页眉/页脚文本。

**11. 目录(TOC)**：在文档开头通过 OXML 插入 `w:sdt` 结构化文档标签（TOC 域代码）。Word 打开时自动更新目录。

**12. 硬分页符**：在 `parser.py` 中支持识别 `===` 或 HTML `<!-- pagebreak -->` 标记；在 `word_converter.py` 中通过 `run.add_break(docx.enum.text.WD_BREAK.PAGE)` 或 `OxmlElement('w:br')` 插入分页符。

---

### 调试执行顺序建议

```
第一批（核心缺陷 - 影响富文本保真度）：
  ├── 调试项1：表格单元格内联格式 → parser.py + word_converter.py
  └── 调试项2：LaTeX/数学公式      → parser.py + word_converter.py

第二批（扩展语法 - 补充格式覆盖）：
  ├── 调试项3：HTML内联元素        → parser.py + word_converter.py
  ├── 调试项4：PDF内联格式支持     → pdf_converter.py
  └── 调试项6：定义列表            → parser.py + word_converter.py

第三批（样式增强 - 改善视觉效果）：
  ├── 调试项5：嵌套引用块缩进      → word_converter.py
  └── 调试项7：==highlight== 高亮   → parser.py + word_converter.py

第四批（高级特性 - 锦上添花）：
  ├── 调试项8：Word原生脚注        → word_converter.py
  ├── 调试项9：非flowchart图表      → flowchart_painter.py
  ├── 调试项10：页眉/页脚/页码     → word_converter.py
  ├── 调试项11：目录(TOC)          → word_converter.py
  └── 调试项12：硬分页符           → word_converter.py + parser.py
```

## 下一步行动
1. **当前重点**：完成第八阶段剩余格式元素调试
   - ~~第七阶段（10项全部完成）~~ ✅
   - 第一批：表格单元格内联格式 + LaTeX/数学公式（高优先级）
   - 第二批：HTML内联元素 + PDF内联格式 + 定义列表
   - 第三批：嵌套引用块缩进 + highlight高亮
   - 第四批：Word原生脚注 + 非flowchart图表 + 高级Word功能
2. 可选：模板支持完整实现
3. 可选：发布到PyPI
4. 可选：添加CI/CD配置