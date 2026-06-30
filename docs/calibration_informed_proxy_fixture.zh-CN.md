# Calibration-informed proxy fixture 说明

本文只说明 `tests/fixtures/calibration_informed_proxy/` 的来源、映射方式、代理边界和复现方式，不是新的算法 contract。

Phase 2B.1 已将该 fixture 迁移为 generic-candidate JSON。Phase 2B.2 只整理本文档语言，不修改 fixture 内容。

## 目的

该 fixture 用于验证当前 loader、PDL lookup cap 预处理、`solve_stage2(...)`、结构化 result 和 tests-only exhaustive oracle 可以处理一份非 handcheck 的 Stage2 输入。

统一名称为：calibration-informed proxy fixture。

## 为什么它不是实际 Longdress tile 输入

三个 tile ID 是 proxy 名称，不是从 Longdress 几何或真实 tile center 推导得到的空间切块。`p_sal`、`visibility`、`screen_area`、`r_bytes`、`d_ms`、`q_base`、`eta` 和预算均为 proxy。

`distance_norm = 1.0, 3.0, 6.0` 选自 calibrated lookup 的支持点，但在本 fixture 中不是由真实 Longdress tile center 推导得到的几何距离。`normalized_render_distance` 是归一化渲染距离，不是物理米。

本 fixture 不包含 measured tile-level 文件大小、真实 target-side decode benchmark、真实用户 viewport trace 或播放器 QoE。

## Calibrated / proxy 映射

calibrated 字段：

| 字段 | 来源 |
|---|---|
| full-body strict PDL lookup support | `20260602_161531_longdress_full10` |
| source run ID | `20260602_161531_longdress_full10` |
| threshold profile | strict `p10 SSIM >= 0.98` |
| normalized-distance support points | `1.0`, `3.0`, `6.0` |
| PDL support grid | `0.2`, `0.4`, `0.6`, `0.8`, `1.0` |

proxy 字段：

| 字段 | 含义 |
|---|---|
| tile spatial identity | `T_near_core`, `T_mid_visible`, `T_far_peripheral` |
| `p_sal` | proxy 显著性权重 |
| `visibility` | proxy 可见性权重 |
| `screen_area` | proxy 屏幕面积占比 |
| `r_base_bytes` | proxy 基础字节规模 |
| `d_base_ms` | proxy 基础处理耗时规模 |
| `q_base` | proxy 基础质量收益，设为 `pdl_ratio` |
| `eta` | proxy 处理耗时惩罚 |
| `Budget_total` | proxy Stage2 预算 |
| `asset_ref` | proxy 逻辑引用，不检查真实文件存在 |

## 固定公式和数值

候选 PDL：

| candidate_id pattern | pdl_ratio | q_base |
|---|---:|---:|
| `ply_pdl_0_2` | 0.2 | 0.2 |
| `ply_pdl_0_4` | 0.4 | 0.4 |
| `ply_pdl_0_6` | 0.6 | 0.6 |
| `ply_pdl_0_8` | 0.8 | 0.8 |
| `ply_pdl_1_0` | 1.0 | 1.0 |

tile 基础数值：

| tile_id | p_sal | visibility | screen_area | distance_norm | r_base_bytes | d_base_ms |
|---|---:|---:|---:|---:|---:|---:|
| `T_near_core` | 1.00 | 1.00 | 0.30 | 1.0 | 500 | 5.0 |
| `T_mid_visible` | 0.60 | 0.80 | 0.18 | 3.0 | 350 | 3.5 |
| `T_far_peripheral` | 0.25 | 0.40 | 0.08 | 6.0 | 250 | 2.5 |

每个 tile、每个候选使用：

```text
r_bytes = r_base_bytes * pdl_ratio
d_ms = d_base_ms * pdl_ratio
q_base = pdl_ratio
G(d) = 1.0
net_utility = p_sal * visibility * screen_area * q_base - eta * d_ms
```

## Full-body strict lookup 来源

lookup 文件：

```text
tests/fixtures/calibration_informed_proxy/distance_lookup_fullbody_strict.json
```

固定来源与语义：

```text
semantics = cap
target_id = null
threshold = strict p10 SSIM >= 0.98
source run = 20260602_161531_longdress_full10
distance unit = normalized_render_distance
view_context = full_body_calibration_informed_proxy
```

lookup cap 映射：

| normalized distance | pdl_max_dist | allowed candidate PDL |
|---:|---:|---|
| 1.0 | 1.0 | `0.2`, `0.4`, `0.6`, `0.8`, `1.0` |
| 3.0 | 0.6 | `0.2`, `0.4`, `0.6` |
| 6.0 | 0.4 | `0.2`, `0.4` |

本 fixture 不加入 near-field rule，也不使用 target-aware lookup。

## 两个输入的预算差异

`input_feasible.json`：

```text
eta = 0.01
budget_total_bytes = 600.0
```

`input_infeasible.json` 除预算外与可行输入完全一致：

```text
budget_total_bytes = 219.0
```

lookup cap 后的最低可行预算：

```text
500*0.2 + 350*0.2 + 250*0.2 = 220.0
```

因此不可行输入必须返回：

```text
status = INFEASIBLE_BUDGET
budget_gap = 1.0
```

## 可复现测试命令

```powershell
python -m pip install -r requirements.txt
python -m pytest tests/test_calibration_informed_proxy_fixture.py
python -m pytest
python scripts/validate_handcheck_fixtures.py
```

## 明确禁止的实验结论

该 fixture 只验证 solver 的输入映射、lookup cap、预算状态和可审查输出。

它不能用于声明 Longdress tile-level 传输收益、真实解码开销、真实播放器 QoE、真实用户视口行为、baseline 性能或算法性能提升。

它不是实际 Longdress tile input，不是 Stage1 在线输出，不是播放器集成，也不是正式实验 baseline。

## 阶段边界

Phase 2B.3 的真实候选元数据只读桥接尚未开始；Phase 2B.4 的 frame 1051 求解器行为验证也尚未开始。
