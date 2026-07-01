# Schema 契约

本文记录当前 JSON Schema 的运行时边界。Phase 2B.1 已完成 generic-candidate 迁移。Phase 2B.3 的 metadata catalog、Phase 2B.4 的 behavior pilot report 和 Phase 2B.5 的 d_ms sensitivity report 都是 JSON-compatible 输出，但没有修改正式 Stage2 Schema。

旧的 `level_id` / `lookup_level` 运行时 JSON 结构不再作为兼容输入解析。

## Stage2 Input

`schemas/stage2_input.schema.json` 描述一次 Stage2 allocation 决策输入。每个 tile 使用：

```text
tiles[].candidates[]
```

候选字段包括 `candidate_id`、`pdl_ratio`、`file_format`、`codec`、`codec_params`、`asset_ref`、`r_bytes`、`d_ms`、`q_base` 和 `provenance`。

`candidate_id` 在 tile 内唯一，不要求连续，也不携带质量顺序。`pdl_ratio` 允许为空或缺失，以保留未来非 PDL profile 的扩展空间；但当前 PDL lookup 启用时，预处理必须拒绝缺少 `pdl_ratio` 的候选。

数据来源标记（provenance）使用受控词汇：

```text
measured
calibrated
derived
proxy
synthetic
```

## Metadata Catalog

Phase 2B.3 的 frame 1051 candidate metadata catalog 是 JSON-compatible 输出，但不是正式 `Stage2Input` Schema，也不是 solver result Schema。它记录真实候选身份、相对 asset ref、manifest integrity、`r_bytes`、source PLY linkage、DRC basic decode-integrity 摘要和 pending 状态。

catalog 必须保留：

- `solver_ready = false`
- `d_ms_status = pending`
- `q_base_status = pending`
- `r_bytes_provenance = measured`
- 明确 non-claims：不是 `Stage2Input`，`r_bytes` 不是端到端网络总开销，DRC validation 不是 target-side latency 或视觉质量证据。

catalog 不能直接传入 `solve_stage2(...)`。

## Behavior Pilot JSON

Phase 2B.4 / 2B.5 的 pilot profile、临时 Stage2Input snapshot、solver result snapshot 和 report 都写入 ignored `outputs/` 或版本控制内 config。它们不扩展正式 Schema。

临时 Stage2Input 仍使用当前 `schemas/stage2_input.schema.json`：

- `r_bytes` 来自 catalog 中 measured 文件本体字节数；
- `q_base = pdl_ratio`，provenance 为 `proxy`；
- `d_ms` 来自 profile proxy mapping，provenance 为 `proxy`；
- `p_sal`、`visibility`、`screen_area` 为 `1.0` proxy；
- `distance_norm = 1.0 / 3.0` 来自 calibrated lookup context；
- `budget_total_bytes` 由 allowed candidate 的 `R` 派生，provenance 为 `derived`。

Phase 2B.5 report 额外记录：

- eta scenario id 与 eta 数值；
- `d_ms_by_candidate_kind` mapping；
- `total_selected_d_ms`；
- 相对 eta0 的 selected candidate change count；
- 明确 non-claims。

## Provenance 边界

Phase 2B.5 pilot 中，只有候选身份、metadata、`pdl_ratio`、`asset_ref` 和 `r_bytes` 来自真实 catalog；`q_base`、`d_ms`、空间因子、统一 distance assignment、eta 和预算均不是真实测量。

DRC file body size 不得写成端到端网络开销。proxy `D` 或 proxy `q` 不是 target-side measured 数据，也不是 DRC-aware 或 format-aware 质量测量。
