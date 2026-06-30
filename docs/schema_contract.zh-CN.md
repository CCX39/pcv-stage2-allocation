# Schema 契约

本文记录当前 JSON Schema 的运行时边界。Phase 2B.1 已完成 generic-candidate 迁移；Phase 2B.3 新增 metadata-only catalog，但没有修改正式 Stage2 Schema。

旧的 `level_id` / `lookup_level` 运行时 JSON 结构不再作为兼容输入解析。

## Stage2 Input

`schemas/stage2_input.schema.json` 描述一次 Stage2 allocation 决策输入。每个 tile 使用：

```text
tiles[].candidates[]
```

候选字段：

- `candidate_id`
- `pdl_ratio`
- `file_format`
- `codec`
- `codec_params`
- `asset_ref`
- `r_bytes`
- `d_ms`
- `q_base`
- `provenance`

`candidate_id` 在 tile 内唯一，不要求连续，也不携带质量顺序。`pdl_ratio` 允许为空或缺失，以保留未来非 PDL profile 的扩展空间；但当前 PDL lookup 启用时，预处理必须拒绝缺少 `pdl_ratio` 的候选。

数据来源标记（provenance）使用受控词汇：

```text
measured
calibrated
derived
proxy
synthetic
```

候选 provenance 至少覆盖 `r_bytes`、`d_ms`、`q_base`、`pdl_ratio` 和 `asset_ref`。

## Distance Lookup

`schemas/distance_lookup.schema.json` 描述 PDL metadata cap lookup。当前规则字段为：

- `rule_id`
- `view_context`
- `target_id`
- `distance_match`
- `pdl_max_dist`
- `threshold_profile`

运行时语义：

```text
allowed_candidate_ids = {candidate | candidate.pdl_ratio <= pdl_max_dist}
```

lookup 不按 `candidate_id`、数组位置、`qp`、`codec` 或 `file_format` 筛选。相同 PDL 下的 PLY、DRC 或不同 codec 参数候选会同时保留。

非空 `target_id` 仍是明确拒绝路径，本仓库尚未实现 target-aware lookup。

## Stage2 Result

`schemas/stage2_result.schema.json` 已迁移为 candidate-aware 输出。`selected_tiles[]` 至少包含：

- `selected_candidate_id`
- `selected_candidate_snapshot`
- `allowed_candidate_ids`
- `rejected_candidate_ids`
- `lookup_pdl_max_dist`
- `r_bytes`
- `d_ms`
- `spatial_utility`
- `net_utility`

`selected_candidate_snapshot` 保留候选解释信息，不只输出 ID。

`lookup_resolution[]` 记录每个 tile 的匹配规则、`pdl_max_dist`、允许候选和被剔除候选。`lambda_search.iterations[]` 记录 selected candidates。`local_upgrade.steps[]` 记录 candidate switch trace。

## Metadata Catalog

Phase 2B.3 的 frame 1051 candidate metadata catalog 是 JSON-compatible 输出，但不是正式 `Stage2Input` Schema，也不是 solver result Schema。它记录真实候选身份、相对 asset ref、manifest integrity、`r_bytes`、source PLY linkage、DRC basic decode-integrity 摘要和 pending 状态。

catalog 必须保留：

- `solver_ready = false`
- `d_ms_status = pending`
- `q_base_status = pending`
- `r_bytes_provenance = measured`
- 明确 non-claims：不是 `Stage2Input`，`r_bytes` 不是端到端网络总开销，DRC validation 不是 target-side latency 或视觉质量证据。

catalog 不能直接传入 `solve_stage2(...)`。Phase 2B.4 若需要行为验证，必须通过独立、显式标注为 proxy 的 scoring/profile 层补齐 `d_ms`、`q_base`、预算和 tile 空间因子后，再生成正式 Stage2 input。

## 旧结构拒绝

旧输入字段不再是合法运行时 Schema：

- `levels[]`
- `lookup_level`
- 以连续质量档位为中心的 selected result 字段

这些词可能只在迁移说明或负向测试样例中出现，不能作为 active runtime 语义继续使用。

## Provenance 边界

Schema 只记录字段来源，不证明物理测量真实性。handcheck fixture 使用 `synthetic`；calibration-informed proxy fixture 的 lookup support 为 `calibrated`，tile metadata、`R`、`D`、`q`、预算和 `asset_ref` 为 `proxy`。

Phase 2B.3 catalog 中 `r_bytes` 来自 manifest size 与 stat size 的一致性检查，标记为 `measured`。proxy `D` 或 proxy `q` 不是 target-side measured 数据；DRC file body size 也不得写成端到端网络开销。
