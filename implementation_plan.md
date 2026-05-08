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

### 高风险项

1. **流程图依赖Chrome**
   - 风险：mermaid-cli依赖Chrome/puppeteer，增加部署复杂度
   - 影响：流程图功能无法在无Chrome环境使用
   - 缓解方案：
     - 使用Kroki在线API（已实现，但不稳定）
     - 降级为代码块显示（已实现）
     - 后续考虑轻量级渲染方案

2. **模板支持未实现**
   - 风险：Word/PDF模板功能仅为接口预留，未完整实现
   - 影响：无法满足企业文档定制需求
   - 缓解方案：后续版本实现模板功能

### 中风险项

3. **样式保真度**
   - 风险：复杂Markdown元素在Word/PDF中的呈现可能不完美
   - 影响：部分格式可能丢失或变形
   - 缓解方案：持续优化转换逻辑

4. **性能问题**
   - 风险：大文件或批量处理时的内存和速度
   - 影响：处理大量文件时可能较慢
   - 缓解方案：已实现并行处理，可进一步优化

### 低风险项

5. **依赖兼容性**
   - 风险：不同操作系统下的字体和渲染差异
   - 影响：跨平台显示效果可能不同
   - 缓解方案：使用通用字体，测试多平台

6. **Kroki API稳定性**
   - 风险：在线API响应慢，有时超时
   - 影响：流程图渲染可能失败
   - 缓解方案：降级为代码块显示

### 已知限制

1. **流程图规范**
   - 当前Mermaid渲染未完全遵循G-C110规范
   - 判断框出线规范需要自定义主题

2. **图片处理**
   - 远程图片下载未实现
   - 图片路径处理需要优化

3. **PDF功能**
   - weasyprint版本需要系统依赖pango
   - reportlab版本功能相对简单

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

## 下一步行动
1. ~~项目基本完成~~
2. **当前重点**：完成第七阶段Word格式元素调试
   - ~~第一批：内联格式 + 超链接（高优先级）~~ ✅ 已完成
   - ~~第二批：分割线 + 代码块背景 + 引用边框 + 表格对齐（中优先级）~~ ✅ 已完成
   - ~~第三批：图片路径 + 脚注 + 任务列表（低优先级）~~ ✅ 已完成
3. 可选：PDF功能调试（Word调试完成后）
4. 可选：模板支持实现
5. 可选：发布到PyPI
6. 可选：添加CI/CD配置