# Lambda 上界括区间契约

本文说明 lambda 上界括区间内核的当前语义。该内核早期在 Phase 1C 引入，Phase 2B.1 已迁移为 generic-candidate trace。Phase 2B.2 只整理文档，不修改实现。

## 目的

bracketing 从 `lambda = 0` 开始探测 fixed-lambda candidate。如果该 candidate 已满足预算，则直接返回 feasible-at-zero。否则按配置扩大 lambda 上界，直到找到第一个预算可行 candidate，或达到最大括区间步数。

## 硬约束

调用前会检查：

```text
Budget_total >= B_min_feasible
```

如果预算低于最低可行预算，bracketing 不应继续执行；最终 `solve_stage2(...)` 会把该条件映射为 `INFEASIBLE_BUDGET`。

## Trace

trace 记录每次 probe 的：

- lambda；
- total bytes；
- total net utility；
- total decode ms；
- 是否预算可行；
- 每个 tile 的 `selected_candidate_id`。

trace 只描述 lambda probe 过程，不包含 local repair 后处理。

## 边界

bracketing 不实现二分搜索、不排序多个 best-feasible candidate、不执行 local repair，也不组装最终 result。
