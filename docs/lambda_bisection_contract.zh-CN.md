# Lambda 二分搜索契约

本文说明 bracket 之后的 lambda 二分搜索语义。该内核早期在 Phase 1D 引入，Phase 2B.1 已迁移为 generic-candidate 选择与 trace。Phase 2B.2 只整理文档，不修改实现。

## 搜索流程

二分搜索接收 bracketing 产生的 lower/upper lambda 边界，并在边界内继续 probe fixed-lambda candidate。

每个 probe 仍按当前 lookup 后的 `allowed_candidate_ids` 逐 tile 选择候选。

## best-feasible candidate

搜索过程中记录观察到的最佳预算可行 candidate。比较规则为：

1. `total_net_utility` 更高；
2. 若在 `score_epsilon` 内近似相同，预算利用率更高；
3. 若仍相同，`total_decode_ms` 更低；
4. 若仍相同，按排序后的 `(tile_id, selected_candidate_id)` 序列稳定决胜。

该记录是 lambda search 的 seed candidate，不是 exact MCKP 全局最优声明。

## 终止原因

当前支持的终止原因包括：

- `feasible_at_zero`
- `lambda_epsilon`
- `max_iterations`
- `bracket_failure`
- `floating_point_stall`

## 边界

二分搜索不执行 residual-budget local repair，不改变 lookup cap，不引入 baseline，也不输出违反预算的 candidate。
