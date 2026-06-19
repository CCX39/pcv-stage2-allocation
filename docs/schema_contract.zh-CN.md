语言：[English](schema_contract.md) | 中文

# Stage2 MVP Schema 契约

状态：阶段0C草案。本文档说明 Stage2 MVP JSON Schema 草案，以及合成手算 fixture 如何使用这些 Schema。Schema 只描述数据格式，不实现校验器、求解器或实验。

## 1. 目的

阶段0B新增三个基于 JSON Schema Draft 2020-12 的文件，用于在后续阶段统一描述 Stage2 输入、距离 lookup 和未来求解器输出：

- `schemas/stage2_input.schema.json`
- `schemas/distance_lookup.schema.json`
- `schemas/stage2_result.schema.json`

这些 Schema 用于辅助审查、后续校验、手算 fixture 和可复现实验准备，但不表示 Stage2 分配器已经可以运行。

## 2. 三个 Schema 的职责

`stage2_input.schema.json` 描述一次 Stage2 决策场景输入，记录总预算、求解系数 `eta`、lookup profile 引用、参与决策的分块、质量档位和字段数据来源。

`distance_lookup.schema.json` 描述离线视距到质量 lookup，记录质量档位、标定来源信息，以及从归一化渲染距离映射到最高允许候选档位的规则。

`stage2_result.schema.json` 描述未来求解器的输出格式，包括状态、最终选档、预算统计、lookup 解析、乘子搜索过程、配置快照、警告和错误。

## 3. 输入 Schema

输入 Schema 要求包含：

- `schema_version`
- `scenario_id`
- `budget_total_bytes`
- `eta`
- `lookup_profile_id`
- `tiles`
- `provenance_summary`

可选的 `description` 可用于记录人工可读的场景说明。

每个分块记录：

- `tile_id`
- `p_sal`
- `visibility`
- `screen_area`
- `distance_norm`
- `view_context`
- `levels`
- `provenance`

每个质量档位记录：

- `level_id`
- `quality_label`
- `pdl_ratio`
- `q_base`
- `r_bytes`
- `d_ms`
- `provenance`

Schema 会检查基本数值范围，例如预算和耗时非负、`0 <= visibility <= 1`、`0 <= screen_area <= 1`、`distance_norm >= 0`、`0 < pdl_ratio <= 1`。

Schema 不强制 `R_i,j` 或 `D_i,j` 随 `level_id` 严格单调。真实编码数据可能不满足严格单调，因此后续校验器可以给出单调性警告，但不应在当前 JSON Schema 中硬性规定。

## 4. Lookup Schema

lookup Schema 固定：

```json
"semantics": "cap"
```

以及：

```json
"distance_unit": "normalized_render_distance"
```

`quality_levels[]` 记录可用质量档位编号、点密度比例和标签。

`source` 记录标定上下文：

- `dataset`
- `renderer`
- `metric`
- `threshold_profile`
- `source_runs`
- `notes`

`rules[]` 记录 lookup 规则。每条规则包含 `rule_id`、`view_context`、可选的 `target_id`、`distance_match`、`lookup_level` 和 `threshold_profile`。

`distance_match` 支持 `exact_distance`，也支持 `distance_min` / `distance_max` 区间。阶段0B只定义结构，不实现匹配算法。

## 5. Result Schema

result Schema 描述未来求解器输出。`status` 枚举包括：

```text
SUCCESS
INFEASIBLE_BUDGET
INVALID_INPUT
INVALID_LOOKUP
NO_ALLOWED_LEVEL
NUMERICAL_ERROR
INTERNAL_CONSTRAINT_VIOLATION
```

`selected_tiles[]` 记录每个分块的最终档位、数据量、解码耗时、净效用、空间视觉效用和允许候选档位。

`lookup_resolution[]` 记录每个分块对应的 lookup profile、匹配规则、lookup level 和最终允许候选集合。

`lambda_search` 记录未来乘子搜索配置和过程：

- `enabled`
- `lambda_initial_high`
- `lambda_max_bracket_steps`
- `score_epsilon`
- `lambda_epsilon`
- `max_iterations`
- `iterations`
- `best_feasible_iteration`

每次迭代可记录 `lambda`、`total_bytes`、`total_net_utility`、`is_budget_feasible` 和迭代编号。

## 6. 数据来源词汇

Schema 使用当前 D0-4 草案词汇：

```text
measured
calibrated
derived
proxy
synthetic
```

D0-4 仍保持 `DRAFT`。这些词汇足以支撑阶段0B的 Schema 草案和阶段0C手算 fixture，但还不是最终的字段级数据来源设计。

## 7. Lookup 的 cap 语义

lookup 继续使用 D0-1 已确认的 `cap` 语义：

```text
allowed_levels = {1, ..., lookup_level}
```

如果 `lookup_level = 3`，允许档位为 `{1, 2, 3}`。

当共有 5 个档位时，near-field `lookup_level = 5` 表示不裁剪高质量候选，并不表示最终必须选择 level 5。

## 8. 归一化距离边界

`distance_norm` 和 lookup 距离都表示归一化渲染距离，不能写成物理米。当前 lookup 依据依赖 Longdress 数据、记录的 source run 和 Web/Three.js 渲染管线。

## 9. 预算不可行输出

D0-2 已确认使用显式预算不可行响应。如果：

```text
Budget_total < B_min_feasible
```

未来输出应使用：

```text
status = INFEASIBLE_BUDGET
budget_total_bytes = ...
b_min_feasible = ...
budget_gap = b_min_feasible - budget_total_bytes
```

这表示输入预算与硬约束不兼容，不是求解器崩溃。

## 10. 乘子搜索记录

D0-3 要求未来实现记录乘子搜索配置和过程。因此 result Schema 包含 `lambda_initial_high`、`lambda_max_bracket_steps`、`score_epsilon`、`lambda_epsilon`、`max_iterations`、`iterations` 和 `best_feasible_iteration`。

如果在 `B_min_feasible <= Budget_total` 的情况下仍无法恢复预算可行解，结果应使用明确异常状态，并保留搜索过程以便排查。

## 11. 手算 Fixture 使用方式

阶段0C新增 `tests/fixtures/handcheck_3x3/`，这是一组合成的 3 分块、3 档位手算 fixture。它使用 Stage2 输入 Schema、距离 lookup Schema 和结果 Schema 记录：

- 预算可行的 success 输入；
- 预算不可行的 infeasible 输入；
- 使用 `cap` 语义的合成 lookup profile；
- success 和 infeasible 的预期结果；
- 中英文手算说明。

该 fixture 用于检查 Schema 形状、lookup cap 行为、`B_min_feasible`、`INFEASIBLE_BUDGET` 和简单效用计算。它不是真实 Longdress 数据，不是正式实验结果，也不是由求解器生成的输出。

## 12. 截至阶段0C未实现内容

阶段0C不实现：

- JSON 校验器封装；
- Stage2 求解器；
- lookup 匹配代码；
- 正式实验；
- Web 播放器集成。

## 13. 后续使用方式

后续阶段可以使用这些 Schema 校验手写输入、lookup profile、fixture 文件和求解器输出。进入实现后，可以根据真实样例继续细化 Schema；但任何涉及 D0-1、D0-2 或 D0-3 的语义变化，都必须同步记录到决策日志。
