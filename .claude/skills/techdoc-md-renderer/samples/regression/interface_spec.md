# 软件接口规范样例

## 接口定义

| 字段 | 类型 | 必填 | 说明 | 示例 |
| ---- | ---- | ---- | ---- | ---- |
| serviceName | string | 是 | 服务名称，应采用模块名前缀 | BodyDomain.Power.GetStatus |
| requestId | uint32 | 是 | 请求序列号 | 1024 |
| payload.vehicle.chassis.brakePressure.value | float | 否 | 长字段路径换行测试 | 10.5 |

## BNF 语法

<!-- table: bnf -->
| Symbol | Meaning | Example |
| ------ | ------- | ------- |
| `<module>` | 模块名 | `BodyDomain` |
| `<action>` | 操作名 | `GetStatus` |

