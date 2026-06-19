语言：[English](stage2_mvp_contract.md) | 中文

# Stage2 MVP 契约

状态：阶段0C草案。本文档定义计划中的 Stage2 MVP 契约、已冻结的 MVP 默认决策、JSON Schema 草案和手算 fixture 边界，不实现任何计算。

## 1. 项目目的

本项目的目的不是立即搭建完整流媒体系统，而是先为 Stage2 空间质量分配器建立一份可执行前的契约。后续第一版实现应当具备：

- 可运行；
- 可复现；
- 可批量测试；
- 可解释；
- 可逐步移植到 Web 端。

阶段0A、阶段0A.1、阶段0B和阶段0C只记录实现前必须明确的契约、已冻结默认决策、Schema 草案和手算 fixture。

## 2. MVP 范围

第一版 MVP 计划支持：

- 读取一个 GoF 或一个决策时刻的分块与质量档位数据；
- 接收 `Budget_total`；
- 为每个分块表达多个离散质量档位；
- 将距离 lookup 解析为允许质量档位的上界；
- 计算空间感知与算力感知净效用；
- 执行后续拉格朗日乘子搜索；
- 恢复预算可行的整数解；
- 使用剩余预算做局部增量升级；
- 输出结构化结果和过程追踪信息。

这些都是计划中的求解器能力，截至阶段0C均未实现。

## 3. 明确不做的内容

第一版 MVP 暂不包括：

- 完整 Stage1 Meta-BOLA 在线实现；
- 真实 HTTP 下载；
- 完整播放器集成；
- 遮挡检测；
- Work2 点尺寸自适应渲染；
- 空间平滑联合优化；
- LPIPS；
- 大规模用户实验；
- 大规模精确 MCKP 求解；
- 端到端网络 QoE 验证。

## 4. 输入概念定义

未来输入需要表达以下概念。阶段0B新增输入 Schema 草案，但不实现校验器或求解器。

### 场景级字段

- 场景标识；
- GoF 或决策时刻标识；
- `Budget_total`；
- `eta`；
- lookup profile；
- 数据来源与版本。

### 分块级字段

- `tile_id`；
- `P_sal_i`，显著性权重；
- `V_i`，视口可见性；
- `A_i`，屏幕投影面积占比；
- `d_i`，归一化渲染距离；
- 场景上下文，例如 full-body 或 near-field；
- 字段数据来源标记。

### 质量档位字段

- `level_id`；
- 显式质量顺序；
- `R_i,j`，数据大小；
- `D_i,j`，预计解码耗时；
- `q_i,j`，基础质量收益；
- 点密度比例或其他质量标识；
- 字段数据来源标记。

## 5. 输出概念定义

未来输出至少需要表达：

- 状态码；
- 每个分块最终选择的质量档位；
- 每个选择的数据量；
- 每个选择的净效用；
- 总数据量；
- 总净效用；
- 总空间视觉效用；
- 总预计解码耗时；
- 预算利用率；
- 最低可行预算；
- lookup 解析结果；
- 乘子搜索过程；
- 搜索迭代次数；
- 算法运行时间；
- 输入与算法配置快照；
- 数据来源摘要；
- 警告和异常信息。

阶段0B新增结果 Schema 草案来描述这些输出概念，但不实现输出代码。

## 6. 数学模型与符号

计划中的 Stage2 问题是带单一总预算约束的多选一背包问题（Multiple-Choice Knapsack Problem, MCKP）。原问题使用二进制变量，不是凸优化问题。只有在连续松弛之后，才可以按线性规划讨论。

目标函数：

```text
maximize:
sum_i sum_j Uhat_i,j * x_i,j
```

预算约束：

```text
sum_i sum_j R_i,j * x_i,j <= Budget_total
```

多选一约束：

```text
sum_j x_i,j = 1
```

整数约束：

```text
x_i,j in {0, 1}
```

净效用：

```text
Uhat_i,j =
(P_sal_i * V_i * A_i * G(d_i)) * q_i,j
- eta * D_i,j
```

距离感知候选集合：

```text
M_i(d_i) = {1, ..., j_max_dist(d_i)}
```

固定 `lambda` 后的选择规则：

```text
argmax_j [
    Uhat_i,j - lambda * R_i,j
]
```

`G(d_i)` 是距离敏感度调制项。当前参考文档支持“实验查表为主，`G(d_i)` 辅助解释”的口径，但没有确定唯一解析形式。

lookup 语义已经确认为候选上界：

```text
lookup_level = j_max_dist
allowed_levels = {1, 2, ..., j_max_dist}
```

对于 near-field lookup level 5，上界保留 `{1, 2, 3, 4, 5}` 全部档位。这不表示最终必须选择 level 5。

未来求解器定位为低复杂度整数近似解框架，不能声称严格求得原始 MCKP 的全局最优解。

## 7. 质量档位顺序约定

- `level_id` 越大表示质量越高。
- 按正常点密度档位解释时，PDL 越大，质量档位越高。
- lookup level 表示当前 cap 语义下最高允许候选档位。
- 输入不应只依赖数组位置隐式表达质量顺序。
- 后续输入必须显式记录档位标识。
- 真实编码数据中，`R_i,j` 或 `D_i,j` 可能受编码细节影响，不一定严格单调。
- 如果后续算法依赖单调性，必须先验证该条件，或在契约中明确写出适用条件。

## 8. 后续求解流程

后续实现预计采用以下流程：

```text
输入校验
-> lookup 匹配
-> 生成每个分块的允许候选集合
-> 计算每个分块、每个档位的净效用
-> 检查最低可行预算
-> 固定 lambda 下独立选档
-> 一维乘子搜索
-> 记录预算可行整数解
-> 剩余预算局部升级
-> 约束复核
-> 输出结果
```

截至阶段0C仍没有实现这些模块。

## 9. 必须满足的不变量

1. 每个参与决策的分块恰好选择一个质量档位。
2. 最终总数据量不得超过 `Budget_total`。
3. 只能选择该分块允许候选集合中的档位。
4. lookup 必须按照候选上界语义执行。
5. 相同输入和相同配置必须得到确定性结果。
6. 输出必须记录输入来源和算法配置。
7. 代理数据实验和真实数据实验必须明确区分。
8. 不能将 normalized distance 写成物理米。
9. 原始问题是整数 MCKP，不是凸优化。
10. 算法结果是近似整数解，不声称严格全局最优。
11. 不可行预算不能被静默忽略。
12. 不得通过漏选分块的方式伪造预算可行。
13. 不得在未记录的情况下放宽 lookup 约束。
14. 所有最终实验结论必须能够回溯到具体输入、配置和输出。

## 10. 决策闸门

```text
D0-1 lookup semantics       RESOLVED_USER_CONFIRMED
D0-2 infeasible budget      RESOLVED_USER_CONFIRMED
D0-3 lambda search rules    RESOLVED_USER_CONFIRMED
D0-4 provenance vocabulary  DRAFT
```

### D0-2 最低可行预算

对于允许集合 `allowed_levels_i`，最低可行数据量为：

```text
B_min_feasible =
sum over i [
    min R_i,j
    for j in allowed_levels_i
]
```

如果：

```text
Budget_total < B_min_feasible
```

MVP 默认行为是显式返回结构化不可行状态：

```text
status = INFEASIBLE_BUDGET
budget_total = ...
b_min_feasible = ...
budget_gap = b_min_feasible - budget_total
```

这不是算法失败，而是输入预算与当前硬约束不兼容。

未来求解器必须保持以下约束：

- 每个参与决策的分块仍必须恰好选择一个质量档位；
- 不允许静默超预算；
- 不允许通过漏选参与决策的分块伪造预算可行；
- 不允许自动放宽 lookup 候选集合；
- 不允许自动请求 Stage1 修改预算，也不允许自动修改 `Budget_total`；
- MVP 不引入空档位或跳过档位。

### D0-3 乘子搜索规则

MVP 默认乘子搜索规则已经冻结。

进入 `lambda` 搜索前，未来求解器必须先完成：

```text
输入校验
lookup 解析
allowed_levels 构造
B_min_feasible 检查
```

如果预算不可行，求解器直接返回 `INFEASIBLE_BUDGET`，不进入乘子搜索。

搜索采用自适应上界：

```text
lambda_low = 0
lambda_high = initial positive value
```

如果 `lambda_high` 下的选择仍超预算，则持续加倍上界：

```text
lambda_high *= 2
```

直到出现预算可行解，或达到最大括区间次数。后续实现必须记录配置字段，例如：

```text
lambda_initial_high
lambda_max_bracket_steps
```

完成括区间后，在 `[lambda_low, lambda_high]` 上执行一维二分搜索。每次迭代应记录：

```text
lambda
total_bytes
total_net_utility
is_budget_feasible
selected_levels
```

只要某次迭代得到预算可行解，就更新当前最佳可行解。

当存在多个可行解时，MVP 默认按以下顺序选择：

1. 总净效用更高；
2. 若近似相同，预算利用率更高；
3. 若仍相同，总预计解码耗时更低；
4. 若仍相同，按 `tile_id` 和 `level_id` 的确定性顺序比较。

固定 `lambda` 下单个分块选档也必须确定性处理平局：

1. 拉格朗日得分更高；
2. 若得分在容差内近似相同，选择数据量更小的档位；
3. 若仍相同，选择解码耗时更小的档位；
4. 若仍相同，选择 `level_id` 更小的档位。

后续实现必须记录浮点和搜索配置，包括：

```text
score_epsilon
lambda_epsilon
max_iterations
```

主要停止条件为 `max_iterations`，也可以辅以 `lambda_epsilon` 和 `no_change_rounds`。但不得因为搜索未完全收敛而输出违反预算的结果。如果在 `B_min_feasible <= Budget_total` 的情况下仍无法获得可行解，应返回明确异常状态，例如 `NUMERICAL_ERROR` 或 `INTERNAL_CONSTRAINT_VIOLATION`，并记录搜索轨迹。

乘子搜索得到预算可行解后，后续 MVP 求解器可以使用剩余预算做局部增量升级。升级必须限制在 `allowed_levels` 内，满足 `delta_R > 0`、`delta_U > 0`，并保证升级后不超预算。局部升级规则将在求解器实现阶段细化，但不得违反预算和 lookup 约束。

## 11. 预期状态码与错误类别

以下状态码只定义概念，尚未实现。

```text
SUCCESS
```

正常完成并得到预算可行整数解。

```text
INFEASIBLE_BUDGET
```

`Budget_total` 低于最低可行数据量。MVP 默认返回该显式状态，并记录 `budget_total`、`b_min_feasible` 和 `budget_gap`。

```text
INVALID_INPUT
```

输入字段缺失、数值越界、档位重复或类型不合法。

```text
INVALID_LOOKUP
```

lookup 缺失、距离范围无法匹配、档位超过可用范围或语义不一致。

```text
NO_ALLOWED_LEVEL
```

某个分块经过 lookup 和其他约束后没有任何允许档位。

```text
NUMERICAL_ERROR
```

出现非有限数值、浮点异常或搜索无法稳定结束。

```text
INTERNAL_CONSTRAINT_VIOLATION
```

输出结果违反每分块多选一、预算或候选集合约束。

## 12. 数据来源要求

每个关键数据字段应记录来源类型：

- `measured`：通过真实文件、解码器、浏览器或实验管线直接测量的数据。
- `calibrated`：由离线标定实验得到的数据，例如距离 lookup。
- `derived`：由真实几何、相机或其他已知数据计算得到的数据，例如距离、视口相交和投影面积。
- `proxy`：有物理或工程解释、但尚未真实测量的代理值。
- `synthetic`：为单元测试或受控算法检查构造的合成数据。

代理值必须说明公式或构造依据。合成值不能与真实实验结论混用。lookup 记录应保留来源 run ID、阈值、数据集和渲染管线。

## 13. 阶段0B Schema 草案

阶段0B新增 JSON Schema Draft 2020-12 文件：

```text
schemas/stage2_input.schema.json
schemas/distance_lookup.schema.json
schemas/stage2_result.schema.json
```

这些 Schema 草案分别定义 Stage2 输入场景、距离 lookup profile 和未来求解器输出的数据结构。它们保持 D0-1 已确认的 cap 语义、D0-2 已冻结的 `INFEASIBLE_BUDGET` 行为，以及 D0-3 已冻结的乘子搜索记录要求。D0-4 数据来源词汇仍保持 `DRAFT`。

这些 Schema 不实现校验器、lookup 匹配、Stage2 求解器或实验。

字段细节见：

```text
docs/schema_contract.md
docs/schema_contract.zh-CN.md
```

## 14. 阶段0A至0C完成判据

阶段0A至阶段0C完成仅表示：

- 项目骨架创建完成；
- 中英文 README 创建完成；
- 中英文算法契约草案创建完成；
- 中英文决策记录创建完成；
- 中英文人工验收清单创建完成；
- D0-1 已按用户确认语义记录；
- D0-2 和 D0-3 已冻结为 MVP 默认策略；
- Stage2 输入、距离 lookup 和结果 JSON Schema 草案创建完成；
- 中英文 Schema 契约文档创建完成；
- 计划内的 3 分块、3 档位手算 fixture 创建完成；
- 没有实现求解器、校验器或实验。

## 15. 当前尚未实现的模块

以下模块均未实现：

- Schema 驱动的校验器；
- 输入校验器；
- 净效用计算器；
- 固定 `lambda` 选择器；
- 乘子搜索；
- 预算不可行处理；
- 可行解恢复；
- 剩余预算升级；
- 基线算法；
- 批量运行器；
- 图表与实验统计；
- Longdress 分块输入生成；
- Python 参考实现；
- TypeScript 移植；
- 播放器接口；
- 正式实验。
