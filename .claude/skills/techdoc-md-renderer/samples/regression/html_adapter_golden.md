# HTML Adapter Golden

## Inline Runs

请参考 **加粗**、*斜体*、`CODE`、[链接](https://example.com) 和 ![缺失内联图](missing-inline.png)。

## Raw HTML

<div class="warning">禁止带电插拔。</div>

## Pipe Table

| 名称 | 说明 |
| ---- | ---- |
| ENABLE | 使能控制 |

## Register Table

<!-- table: register -->
| Address | Register | Bits | Access | Reset | Description |
| ------- | -------- | ---- | ------ | ----- | ----------- |
| 0x00 | CTRL | [3:0] | RW | 0x0 | Control register |

## Wide Table

<!-- table: register -->
| Address | Register | Bits | Access | Reset | Clock | Domain | Description |
| ------- | -------- | ---- | ------ | ----- | ----- | ------ | ----------- |
| 0x10 | STATUS | [15:0] | RO | 0x0000 | APB | SYS | Very long status register description for overflow wrapper intent. |

## Code

```c
uint8_t value = read_reg(0x00);
```

## Mermaid

```mermaid
graph TD
A --> B
```

## Missing Block Image

![缺失块图](missing-block.png)

<!-- pagebreak -->

## Nested List

- 一级
  - 二级

> 引用段落
