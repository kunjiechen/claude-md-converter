"""
测试配置
"""

import pytest
import tempfile
import os
from pathlib import Path


@pytest.fixture
def temp_dir():
    """创建临时目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_markdown():
    """示例Markdown文本"""
    return '''# 测试文档

## 功能说明

这是一个测试段落。

### 列表示例

- 无序列表项1
- 无序列表项2

1. 有序列表项1
2. 有序列表项2

### 表格示例

| 序号 | 名称 | 说明 |
|------|------|------|
| 1 | 功能1 | 描述1 |
| 2 | 功能2 | 描述2 |

### 代码块示例

```python
def hello():
    print("Hello World")
```

### 引用示例

> 这是一段引用文本

---

结束
'''


@pytest.fixture
def sample_markdown_file(temp_dir, sample_markdown):
    """创建示例Markdown文件"""
    file_path = temp_dir / "test.md"
    file_path.write_text(sample_markdown, encoding='utf-8')
    return file_path


@pytest.fixture
def sample_markdown_files(temp_dir):
    """创建多个示例Markdown文件"""
    files = []

    # 文件1
    file1 = temp_dir / "test1.md"
    file1.write_text("# 测试1\n\n内容1", encoding='utf-8')
    files.append(file1)

    # 文件2
    file2 = temp_dir / "test2.md"
    file2.write_text("# 测试2\n\n内容2", encoding='utf-8')
    files.append(file2)

    # 子目录文件
    sub_dir = temp_dir / "subdir"
    sub_dir.mkdir()
    file3 = sub_dir / "test3.md"
    file3.write_text("# 测试3\n\n内容3", encoding='utf-8')
    files.append(file3)

    return files