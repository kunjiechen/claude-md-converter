# 寄存器表样例

## 控制寄存器

<!-- table: register -->
| Offset | Bits | Field | Access | Reset | Description |
| ------ | ---- | ----- | ------ | ----- | ----------- |
| 0x00 | [31:16] | RESERVED | RO | 0x0000 | Reserved bits |
| 0x00 | [15:8] | MODE_SELECT | RW | 0x01 | Selects operation mode, including normal, sleep and diagnostics |
| 0x00 | [7:0] | ENABLE | RW | 0x00 | Module enable control |

## 位域定义

<!-- table: bitfield -->
| Bits | Name | Access | Reset | Description |
| ---- | ---- | ------ | ----- | ----------- |
| [3:0] | CLK_DIV | RW | 0x0 | Clock divider setting |
| [4] | IRQ_EN | RW | 0x0 | Interrupt enable |

