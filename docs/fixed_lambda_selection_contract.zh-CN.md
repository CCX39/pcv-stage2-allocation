# 固定 lambda 选择契约

本文说明固定 lambda 选择内核的当前语义。该内核早期在 Phase 1B 引入，Phase 2B.1 已随 runtime 一起迁移为 generic-candidate 语义。Phase 2B.2 只整理文档，不修改实现。

## 输入边界

`select_fixed_lambda(stage2_input, lookup, lambda_value, score_epsilon=...)` 接收已经可由当前模型表达的 `Stage2Input` 与 `DistanceLookup`。

调用时会先执行 lookup 解析，得到每个 tile 的 `allowed_candidate_ids`。当前 lookup 只支持：

```text
candidate.pdl_ratio <= pdl_max_dist
```

启用 PDL lookup 时，候选缺少 `pdl_ratio` 会被拒绝。

## 选择规则

对每个 tile 独立选择：

```text
argmax_j [Uhat_i,j - lambda * R_i,j]
```

其中：

```text
Uhat_i,j = p_sal_i * visibility_i * screen_area_i * q_base_i,j - eta * d_ms_i,j
```

当前 `G(d) = 1.0`。

## 平局规则

固定 lambda 下同分时：

1. penalized score 更高；
2. 若近似相同，`R` 更小；
3. 若仍相同，`D` 更小；
4. 最后按 `candidate_id` 稳定决胜。

`candidate_id` 只用于最后稳定排序，不表示质量顺序。

## 输出边界

输出是 fixed-lambda candidate，不是最终 `solve_stage2(...)` result。它只描述在给定 lambda 下的 per-tile 选择和总量，不负责 lambda search、local repair 或状态码组装。
