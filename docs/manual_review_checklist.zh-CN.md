# 人工审查清单

本清单用于人工确认 Stage2 allocation 的文档、契约和测试资产没有越过当前阶段边界。Phase 2B.2 只做中文文档收口与英文 Markdown 清理，不修改实现。

## 项目边界

- Stage2 当前解决的是预算约束下的空间 tile 候选选择问题。
- 当前 runtime 已使用通用传输版本候选，不再依赖连续质量档位语义。
- 当前 solver 是低复杂度近似路径，不是 exact MCKP、动态规划、branch-and-bound 或 baseline。

## Lookup 边界

- lookup 语义是 `candidate.pdl_ratio <= pdl_max_dist`。
- 当前 PDL lookup 来自 PLY nested-PDL calibration。
- 不得把当前 lookup 写成 DRC-aware quality measurement。
- `normalized_render_distance` 不是物理米。
- 非空 `target_id` 的 target-aware lookup 仍应拒绝。

## Candidate 边界

- `candidate_id` 只表示身份和最后稳定平局处理，不代表质量顺序。
- PDL、QP、codec、file format 不代表天然优劣。
- PLY 与 DRC 可以在同一 tile、同一 PDL 下并列存在。
- `R`、`D`、`q` 的比较必须依赖显式数值。

## Provenance 边界

- provenance 受控词汇为 `measured`、`calibrated`、`derived`、`proxy`、`synthetic`。
- proxy `D` 或 proxy `q` 不能写成 measured。
- calibration-informed proxy fixture 的 tile metadata、`R`、`D`、`q`、预算和 `asset_ref` 均为 proxy。
- DRC `file_size_bytes` 不得写成端到端网络开销。

## Solver 边界

- `Budget_total < B_min_feasible` 必须返回 `INFEASIBLE_BUDGET`。
- fixed-lambda 选择不得依赖数组顺序或候选编号大小。
- local repair 只能做满足 `Delta_R > 0`、`Delta_Uhat > 0`、`Delta_R <= residual_budget` 的候选切换。
- tests-only exhaustive oracle 不得进入 runtime solver。

## 阶段边界

- Phase 2B.1：通用候选语义迁移已完成。
- Phase 2B.2：当前阶段，只整理中文文档并删除英文镜像 Markdown。
- Phase 2B.3：真实候选元数据只读桥接，尚未开始。
- Phase 2B.4：frame 1051 求解器行为验证，尚未开始。

当前仍未接入真实 artifact root，未生成 frame 1051 正式 Stage2Input，未测 target-side `D`，未构建 DRC-aware 或 format-aware `q`，未实现 Pareto pruning、baseline、batch runner、plotting 或播放器接入。
