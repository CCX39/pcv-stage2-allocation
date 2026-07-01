# pcv-stage2-allocation

本仓库实现 Work1 Stage2 allocation 的低复杂度运行时路径。当前阶段为 **Phase 2B.5：frame 1051 处理耗时代理敏感性验证**。

Phase 2B.1 已完成从连续 PDL 质量档位迁移到通用传输版本候选（generic transmission candidate）。Phase 2B.3 已新增 frame 1051 真实候选元数据只读桥接。Phase 2B.4 已验证真实候选目录、真实文件本体 `r_bytes`、PDL lookup、派生预算和现有 solver 可以稳定贯通。Phase 2B.5 在同一基础上加入严格标注为 proxy 的候选处理耗时 `d_ms` 与 eta 组，做小规模敏感性验证。

本阶段只回答一个行为问题：当相同 PDL 的 PLY 和 DRC 候选具有不同的处理耗时代理值时，generic-candidate solver 是否会在预算代价 `R` 与处理代价 `eta * D` 之间产生可追溯、确定性的候选切换。它不是目标端 benchmark，不是实际 PLY/DRC 性能结论，不是 QoE 或格式优劣实验。

## 当前运行时语义

Stage2 运行时输入使用 `candidates[]` 表示通用传输版本候选。`candidate_id` 只表示 tile 内候选身份，用于引用和最后稳定平局处理；它不表示质量、数据量、处理耗时或视觉收益顺序。`pdl_ratio` 只用于当前 PDL lookup 投影，不代表最终视觉质量全序。PLY 与 DRC 可以在同一 tile、同一 PDL 下作为并列候选存在。

`R`、`D`、`q` 的比较必须依赖显式数值，不依赖候选数组顺序、`candidate_id`、`qp`、`codec` 或 `file_format`。

## Lookup

当前 lookup 使用 `semantics = cap`，cap 对象是候选的 PDL metadata：

```text
allowed_candidate_ids = {candidate | candidate.pdl_ratio <= pdl_max_dist}
```

当前 PDL lookup 来自 PLY nested-PDL calibration，不是 DRC-aware quality measurement，也不是最终 QoE 结论。`normalized_render_distance` 是归一化渲染距离，不是物理米。非空 `target_id` 的 target-aware lookup 仍会被拒绝。

## Solver

当前 runtime solver 是：

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

local repair 只考虑：

```text
Delta_R > 0
Delta_Uhat > 0
Delta_R <= residual_budget
```

## Frame 1051 Metadata Bridge

Phase 2B.3 的只读桥接从本机 `pcv-stage2-data-prep` root 读取 frame 1051 轻量 JSON metadata，生成 metadata-only catalog：

```powershell
python scripts\build_frame1051_candidate_catalog.py `
  --data-prep-root <pcv-stage2-data-prep-root> `
  --output outputs\frame1051_candidate_metadata_catalog.json
```

桥接只读取 profile config、artifact manifest、tile index 与 validation report 等 JSON，并用 `Path.stat()` 检查 manifest 引用文件的存在性和 file body size。它不读取 PLY/DRC 文件内容，不运行 Draco，不重算大文件 SHA-256，不复制真实 assets。

catalog 记录 8i Longdress frame 1051、G128、40 个 non-empty tile、200 个 source PLY 候选与 600 个 DRC delivery 候选。`r_bytes` 是候选文件本体字节数，provenance 为 `measured`；它不是端到端网络总开销。catalog 中 `d_ms_status` 与 `q_base_status` 保持 `pending`，catalog 不是正式 `Stage2Input`，不能直接求解。

## Behavior Pilot 与 Dms Sensitivity

Phase 2B.4 profile：

```text
configs/frame1051_fullbody_proxy_behavior_v1.json
```

Phase 2B.5 profile：

```text
configs/frame1051_fullbody_proxy_dms_sensitivity_v1.json
```

通用 runner：

```powershell
python scripts\run_frame1051_behavior_pilot.py `
  --data-prep-root <pcv-stage2-data-prep-root> `
  --profile configs\frame1051_fullbody_proxy_dms_sensitivity_v1.json `
  --output-dir outputs\frame1051_dms_sensitivity_pilot
```

两个 profile 均使用：

- `fullbody_d1`：`distance_norm = 1.0`，`pdl_max_dist = 1.0`。
- `fullbody_d3`：`distance_norm = 3.0`，`pdl_max_dist = 0.6`。
- `p_sal = visibility = screen_area = 1.0`，provenance 为 `proxy`。
- `q_base = pdl_ratio`，provenance 为 `proxy`。
- `Budget_total` 派生自 `min_feasible`、`midpoint`、`reference_max` 三个预算点，provenance 为 `derived`。

Phase 2B.5 额外固定：

- `ply_source`: `d_ms = 80.0`
- `drc_delivery`: `d_ms = 100.0`
- `eta0 = 0.0`
- `eta_moderate = 0.0025`
- `eta_stronger = 0.005`

这些 `d_ms` 与 eta 只服务于当前 proxy 尺度下的敏感性验证。它们不是逐 tile measured target-side `d_ms`，不是完整帧加载耗时，也不是真实设备、网络、用户或播放器参数。所有 DRC `qp` 共用同一 `100.0 ms` proxy；本轮不引入 `qp` 质量或处理耗时顺序。

## 测试资产

- `tests/fixtures/handcheck_3x3/`
- `tests/fixtures/calibration_informed_proxy/`
- `tests/helpers/exhaustive_oracle.py`
- `tests/test_frame1051_metadata_bridge.py`
- `tests/test_frame1051_behavior_pilot.py`
- `tests/test_frame1051_dms_sensitivity_pilot.py`

## 阶段边界

本仓库当前未测 target-side `D`，未构建 DRC-aware 或 format-aware `q`，未接入真实 saliency/visibility/projection pipeline，未接入 Stage1 `Budget_total` 在线接口，未实现 target-aware lookup、Pareto pruning、baseline、batch runner、plotting、播放器接入、网络仿真或目标端 benchmark。
