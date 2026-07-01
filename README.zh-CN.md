# pcv-stage2-allocation

本仓库实现 Work1 Stage2 allocation 的低复杂度运行时路径。当前阶段为 **Phase 2B.4：frame 1051 求解器行为验证**。

Phase 2B.1 已完成从连续 PDL 质量档位迁移到通用传输版本候选（generic transmission candidate）。Phase 2B.3 已新增 frame 1051 真实候选元数据只读桥接。Phase 2B.4 在此基础上构造严格标注为行为验证的临时 `Stage2Input`，调用现有 solver 运行 2 个 lookup context × 3 个派生预算点的可复现场景。

本阶段验证的是真实候选身份、真实文件本体 `r_bytes`、PDL lookup、预算约束、lambda search、local repair、输出 trace 和 provenance 是否能在 generic-candidate solver 中稳定贯通。它不是视觉质量、端侧性能、QoE、网络吞吐或格式优劣实验。

## 当前运行时语义

Stage2 运行时输入不再使用连续 `level_id` 档位。每个 tile 包含一组 `candidates[]`，候选记录包括：

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

`candidate_id` 只表示 tile 内候选身份，用于引用和最后稳定平局处理；它不表示质量、数据量、处理耗时或视觉收益顺序。`pdl_ratio` 只用于当前 PDL lookup 投影，不代表最终视觉质量全序。PLY 与 DRC 可以在同一 tile、同一 PDL 下作为并列候选存在。`R`、`D`、`q` 的比较必须依赖显式数值，不依赖候选数组顺序、`candidate_id`、`qp`、`codec` 或 `file_format`。

## Lookup

当前 lookup 仍使用 `semantics = cap`，cap 对象是候选的 PDL metadata：

```text
allowed_candidate_ids = {candidate | candidate.pdl_ratio <= pdl_max_dist}
```

启用 PDL lookup 时，参与 lookup 的候选必须显式提供合法 `pdl_ratio`。当前 PDL lookup 来自 PLY nested-PDL calibration，不是 DRC-aware quality measurement，也不是最终 QoE 结论。`normalized_render_distance` 是归一化渲染距离，不是物理米。

非空 `target_id` 的 target-aware lookup 仍会被拒绝。

## Solver

当前 runtime solver 是低复杂度近似路径：

```text
lookup 解析
-> B_min_feasible 检查
-> fixed-lambda per-tile argmax
-> lambda 上界扩展与二分搜索
-> 最佳预算可行 seed candidate
-> residual-budget local repair
-> 结构化 result
```

固定 lambda 下每个 tile 独立选择：

```text
argmax_j [Uhat_i,j - lambda * R_i,j]
```

同分时依次比较 penalized score、较小 `R`、较小 `D`，最后才按 `candidate_id` 稳定决胜。

残余预算局部修正（local repair）已经从旧的“档位升级”改为候选切换（candidate switch）。它只考虑：

```text
Delta_R > 0
Delta_Uhat > 0
Delta_R <= residual_budget
```

## Frame 1051 Metadata Bridge

Phase 2B.3 新增只读桥接，用于从本机 `pcv-stage2-data-prep` root 读取 frame 1051 的轻量 JSON metadata，生成 metadata-only catalog：

```powershell
python scripts\build_frame1051_candidate_catalog.py `
  --data-prep-root <pcv-stage2-data-prep-root> `
  --output outputs\frame1051_candidate_metadata_catalog.json
```

该脚本只读取 profile config、artifact manifest、tile index 与 validation report 等 JSON，并用 `Path.stat()` 检查 manifest 引用文件的存在性和 file body size。它不读取 PLY/DRC 文件内容，不运行 Draco，不重算大文件 SHA-256，不复制真实 assets。

catalog 记录 8i Longdress frame 1051、G128、40 个 non-empty tile、200 个 source PLY 候选与 600 个 DRC delivery 候选。`r_bytes` 是候选文件本体字节数，来源为 manifest 与 stat size 的一致性检查，provenance 为 `measured`。它不是端到端网络总开销。

catalog 中 `d_ms_status` 与 `q_base_status` 必须保持 `pending`。catalog 不是正式 `Stage2Input`，不能直接传入 `solve_stage2(...)`。

## Frame 1051 Behavior Pilot

Phase 2B.4 新增行为验证 profile：

```text
configs/frame1051_fullbody_proxy_behavior_v1.json
```

运行命令：

```powershell
python scripts\run_frame1051_behavior_pilot.py `
  --data-prep-root <pcv-stage2-data-prep-root> `
  --output-dir outputs\frame1051_behavior_pilot
```

runner 会先调用 Phase 2B.3 read-only bridge，再把 catalog 显式映射为临时 generic-candidate `Stage2Input`。真实输出只写入 Git ignored 的 `outputs/`，包括 catalog snapshot、lookup snapshot、每个 scenario 的 input/result JSON 和总 report。

本轮固定两个 full-body context：

- `fullbody_d1`：`distance_norm = 1.0`，预期 `pdl_max_dist = 1.0`。
- `fullbody_d3`：`distance_norm = 3.0`，预期 `pdl_max_dist = 0.6`。

这两个距离是离线 PLY calibration 支持点引用，不是每个 tile 的真实几何距离、真实视点、真实 viewport 或物理米。所有 tile 的 `p_sal`、`visibility`、`screen_area` 均为 `1.0` proxy。`q_base = pdl_ratio` 是 proxy scoring rule；同一 PDL 下 PLY 与不同 `qp` 的 DRC 使用相同 `q_base`。`d_ms = 0.0` 且 `eta = 0`，因此本轮不比较端侧处理开销；该值不是目标端处理耗时为零的测量结论。

每个 context 派生三个预算点：

- `min_feasible`：`B_min = sum_i min_j R_i,j`。
- `midpoint`：`B_mid = floor((B_min + B_reference_max) / 2)`。
- `reference_max`：`B_reference_max = sum_i max_j R_i,j`。

这些预算为 `derived`，只用于覆盖低、中、高预算占用状态，不代表 Stage1 输出、真实带宽或真实网络可下载字节数。

## 测试资产

- `tests/fixtures/handcheck_3x3/`：合成 3 tile generic-candidate 手算 fixture。
- `tests/fixtures/calibration_informed_proxy/`：calibration-informed proxy fixture。
- `tests/helpers/exhaustive_oracle.py`：仅供测试使用的小规模 exhaustive oracle。
- `tests/test_frame1051_metadata_bridge.py`：synthetic metadata bridge 测试。
- `tests/test_frame1051_behavior_pilot.py`：synthetic behavior pilot 测试，覆盖 lookup cap、预算推导、proxy provenance、pending 边界、solver invariants、排序稳定性和 non-claims。

## 阶段边界

- Phase 2B.1：已完成通用候选语义迁移。
- Phase 2B.2：已完成中文文档收口与英文 Markdown 清理。
- Phase 2B.3：已完成 frame 1051 真实候选元数据只读桥接。
- Phase 2B.4：当前阶段，新增 frame 1051 求解器行为验证。

本仓库当前未测 target-side `D`，未构建 DRC-aware 或 format-aware `q`，未接入真实 saliency/visibility/projection pipeline，未接入 Stage1 `Budget_total` 在线接口，未实现 target-aware lookup、Pareto pruning、baseline、batch runner、plotting、播放器接入或目标端 benchmark。
