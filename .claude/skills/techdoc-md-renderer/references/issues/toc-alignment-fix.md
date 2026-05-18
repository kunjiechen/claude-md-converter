# TOC 目录对齐问题分析与修复

## 问题概述

生成的 DOCX 文档中目录 (TOC) 对齐方式异常，具体表现为：
1. 目录标题及条目出现预期外的右偏/缩进
2. 部分条目的页码未靠右对齐
3. 页面前导点 (dot leader) 位置异常

## 根因分析

### 根因 #1：`firstLineChars` 缺失导致样式缩进回退

**问题链路**：

```
Normal 样式定义: firstLineChars="200" (2字符缩进), firstLine="480"
      │
      ▼
TOC 样式: basedOn="Normal", firstLine="0" (仅 firstLine, 无 firstLineChars)
      │
      ▼
部分渲染器 (WPS) 遇到仅 firstLine="0" 时：
  → 将 0 视为「未设置」而非「零缩进」
  → 回退到基础样式 Normal 的 firstLineChars="200"
  → TOC 条目产生 2 字符意外缩进
```

**代码位置**：`docx_adapter.py:180` — `style.paragraph_format.first_line_indent = Cm(0)`

python-docx 的 `first_line_indent = Cm(0)` 仅写入 `w:firstLine="0"`，不写入 `w:firstLineChars="0"`。部分 OOXML 渲染器（尤其是 WPS Office）要求 `firstLineChars` 显式归零才能正确覆盖基础样式。

**修复**：新增 `_zero_style_indent()` 方法，通过直接 XML 操作同时设置 `w:firstLine="0"` 和 `w:firstLineChars="0"`。应用于所有 TOC 样式 (`toc 1/2/3/4`、`TOC Title`)。

### 根因 #2：Tab 制表位数量与条目 Tab 字符数不匹配

**问题链路**：

```
TOC 样式定义: 2 个制表位 (LEFT@480 + RIGHT+DOTS@9600)
      │
      ▼
TOC 条目生成:
  ├── 有编号条目: "1\t目的\t5"      → 2个tab → 正确命中两个制表位
  └── 无编号条目: "文件修订履历表\t3" → 1个tab → 仅命中 LEFT@480
                                                      │
                                                      ▼
                                            页码 "3" 出现在 0.85cm 处
                                            而非右边缘 16.93cm 处
```

**代码位置**：`docx_adapter.py:435-440`

原始代码对「有编号」和「无编号」条目使用不同的 tab 结构：
- 有编号：`{number}\t{label}\t{page}` → 2 tabs → 使用 LEFT + RIGHT 两个制表位
- 无编号：`{label}\t{page}` → 1 tab → 仅使用 LEFT 制表位，页码错位

**修复**：
1. **简化制表位模型**：TOC 样式仅保留一个 `RIGHT+DOTS@9600` 制表位（移除 LEFT@480）
2. **统一条目结构**：所有条目采用 `{display}\t{page}` 结构，有编号时 display = `"1  目的"`（编号+空格+标题合为一个 run）
3. **子层级缩进**：toc 2/3/4 通过 `left_indent` (0.5cm/1.0cm/1.5cm) 实现视觉层级，而非依赖制表位

### 根因 #3：段落级制表位覆盖样式级制表位

**问题链路**：

```
TOC 样式: tabs@style-level ✅
      │
      ▼
_insert_toc_if_required(): 对每个条目调用 _apply_toc_tab_stops()
      │
      ▼
段落级 <w:tabs> 覆盖样式级 <w:tabs>
      │
      ▼
制表位定义散落在每个段落上，与 Original 文档结构不一致
```

**修复**：移除段落级 `_apply_toc_tab_stops()` 调用，制表位仅定义在样式级，段落通过样式继承获取。

## 解决方案汇总

| # | 问题 | 根因 | 修复方法 | 影响文件 |
|---|------|------|----------|----------|
| 1 | TOC 条目意外缩进 | `firstLineChars` 未显式归零 | `_zero_style_indent()` 直接 XML 设置双零值 | `docx_adapter.py` |
| 2 | 页码未靠右/前导点异常 | tab 数量 ≠ 制表位数量 | 统一单 tab 结构 + 单制表位模型 | `docx_adapter.py` |
| 3 | 段落级制表位冗余 | 段落 tabs 覆盖样式 tabs | 移除段落级制表位调用 | `docx_adapter.py` |
| 4 | TOC 无超链接 | 目录条目为纯文本，无 w:hyperlink 包裹，点击无法跳转到对应章节 | 预计算锚点映射 + 标题插入书签 + TOC 条目包裹超链接 | `docx_adapter.py` |

---

## 根因 #4：TOC 缺失超链接关系

### 问题链路

```
TOC 条目生成: 纯文本 paragraph + run("1  目的") + tab + run("5")
      │
      ▼
标题渲染: paragraph + run("1 目的")  (无书签/锚点标记)
      │
      ▼
结果: TOC 条目与标题之间无任何 OOXML 链接机制
      ├── 无 w:hyperlink 包裹 TOC 文本
      └── 无 w:bookmarkStart/End 标记标题位置
      │
      ▼
用户在 Word/WPS 中点击目录无法跳转到对应章节
```

### 修复方案

采用**预计算锚点映射**策略（避免两遍渲染）：

1. **`_build_heading_anchor_map()`** — 渲染前遍历 DocumentModel 中所有 Heading 块，按与 `_toc_entries` 完全一致的计数器逻辑生成锚点 ID（格式：`_Toc_{编号}`），以 block_index 为键存入映射表

2. **`_insert_toc_if_required()`** — 每个 TOC 条目调用 `_add_toc_hyperlink()`，创建 `<w:hyperlink w:anchor="_Toc_X">` 包裹显示文本、制表符、页码。该 XML 结构确保整个 TOC 条目（包括页码）都是可点击的链接区域

3. **`_add_heading_bookmark()`** — 标题渲染时查找 `_heading_anchor_map[block_index]`，在标题段落 `<w:pPr>` 之后插入 `<w:bookmarkStart w:name="_Toc_X"/>`，段尾追加 `<w:bookmarkEnd/>`

4. **修订历史表** — 使用特殊锚点 `_Toc_RevHist`，在修订表标题段落上调用 `_add_bookmark()`

### 关键代码变更

```python
# 预计算锚点（与 _toc_entries 共享编号逻辑）
def _build_heading_anchor_map(self, context):
    anchors = {}
    counters = [0] * 4
    for index, block in enumerate(context.document.blocks):
        if not isinstance(block, Heading): continue
        # ... 与 _toc_entries 相同的计数器逻辑 ...
        anchors[index] = f"_Toc_{number}"
    return anchors

# TOC 超链接条目
def _add_toc_hyperlink(self, paragraph, display, page, anchor):
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("w:anchor"), anchor)
    # display_run + tab_run + page_run → hyperlink → paragraph._element

# 标题书签
def _add_heading_bookmark(self, paragraph, block_index):
    anchor = self._heading_anchor_map.get(block_index)
    if anchor:
        self._add_bookmark(paragraph, anchor)
```

## 验证结果

### G-C045 (有 Original 参考)

```
FIDELITY SCORE: 100%
├── TOC format fidelity: 10/10
├── Table cell formatting: 10/10
├── Normal font settings: 10/10
├── TOC hyperlinks: 56/56 (全部可点击跳转)
├── Heading bookmarks: 56/56 (全部有锚点)
└── All 9 dimensions ≥ 9/10
```

### G-C110 (无参考，postflight 验证)

```
DOCX: 0 critical / 0 warning
 PDF: 0 critical / 0 warning
HTML: 0 critical / 0 warning
├── TOC entries: 42, hyperlinks: 42, bookmarks: 42 (全部匹配)
├── TOC alignment: 1 tab → 1 tab stop (0 不匹配)
└── Tables: 17 张表, 0 空表头
```

## 关键代码变更

### 1. `_zero_style_indent()` — 新增方法

```python
@staticmethod
def _zero_style_indent(style) -> None:
    """同时设置 firstLine 和 firstLineChars 为 0"""
    pPr = style.element.find(qn("w:pPr"))
    if pPr is None:
        pPr = OxmlElement("w:pPr")
        style.element.insert(0, pPr)
    ind = pPr.find(qn("w:ind"))
    if ind is None:
        ind = OxmlElement("w:ind")
        pPr.append(ind)
    ind.set(qn("w:firstLine"), "0")
    ind.set(qn("w:firstLineChars"), "0")
```

### 2. `_add_toc_style_tab_stops()` — 简化为单制表位

```python
# 旧: LEFT@480 + RIGHT+DOTS@9600 (2个制表位)
# 新: RIGHT+DOTS@9600 (1个制表位)
```

### 3. TOC 条目生成 — 统一结构

```python
# 旧 (有编号):  number\tlabel\tpage  (2 tabs)
# 旧 (无编号):  label\tpage         (1 tab → BUG)
# 新 (统一):    "1  目的"\t5         (1 tab, 编号和标题合并)
```

## 日期

2026-05-17
