语言：[English](calibration_informed_proxy_fixture.md) | 中文

# Calibration-Informed Proxy Fixture 说明

状态：Phase 2A fixture 映射说明。本文不是新的算法 contract。

## 1. Fixture 目的

`tests/fixtures/calibration_informed_proxy/` 用于验证当前 typed loader、lookup cap 预处理、`solve_stage2(...)`、结构化 result 组装和 tests-only exhaustive oracle，已经可以处理一份非 handcheck 的 Stage2 输入，并且该输入具有明确的数据来源边界。

这是一份 calibration-informed proxy fixture。它把 calibrated Longdress full-body strict lookup cap 与 proxy tile metadata 放在同一条 solver 路径中，用于验证输入映射、lookup cap、预算状态和可审查输出。

## 2. 为什么它不是实际 Longdress Tile 输入

该 fixture 不是真实 Longdress 空间切块输入。三个 tile ID 是 proxy 名称，不是从 Longdress 几何中解析出的 cell 或 tile。tile 空间因子也是 proxy 数值，不是显著性实测、真实视口轨迹、真实相机投影面积、真实编码文件大小或真实解码 benchmark。

`distance_norm = 1.0, 3.0, 6.0` 选自 calibrated lookup 的支持点。但在本 fixture 中，它们不是由真实 Longdress tile center 推导得到的几何距离。

## 3. Calibrated / Proxy 字段映射

calibrated 字段：

| 字段 | 来源 |
|---|---|
| full-body strict lookup cap | `20260602_161531_longdress_full10` |
| source run ID | `20260602_161531_longdress_full10` |
| threshold profile | strict `p10 SSIM >= 0.98` |
| normalized-distance support points | `1.0`, `3.0`, `6.0` |
| PDL support grid | `0.2`, `0.4`, `0.6`, `0.8`, `1.0` |

proxy 字段：

| 字段 | 含义 |
|---|---|
| tile spatial identity | `T_near_core`, `T_mid_visible`, `T_far_peripheral` 是 proxy tile ID |
| `p_sal` | proxy 显著性权重 |
| `visibility` | proxy 可见性权重 |
| `screen_area` | proxy 屏幕面积占比 |
| `r_base_bytes` | proxy 基础字节规模 |
| `d_base_ms` | proxy 基础解码耗时规模 |
| `q_base` | proxy 基础质量收益，设为 `pdl_ratio` |
| `eta` | proxy 解码耗时惩罚 |
| `Budget_total` | proxy Stage2 预算 |

## 4. 固定公式和数值表

质量档位：

| level_id | pdl_ratio | q_base |
|---:|---:|---:|
| 1 | 0.2 | 0.2 |
| 2 | 0.4 | 0.4 |
| 3 | 0.6 | 0.6 |
| 4 | 0.8 | 0.8 |
| 5 | 1.0 | 1.0 |

tile 基础数值：

| tile_id | p_sal | visibility | screen_area | distance_norm | r_base_bytes | d_base_ms |
|---|---:|---:|---:|---:|---:|---:|
| `T_near_core` | 1.00 | 1.00 | 0.30 | 1.0 | 500 | 5.0 |
| `T_mid_visible` | 0.60 | 0.80 | 0.18 | 3.0 | 350 | 3.5 |
| `T_far_peripheral` | 0.25 | 0.40 | 0.08 | 6.0 | 250 | 2.5 |

每个 tile、每个 level 使用：

```text
r_bytes = r_base_bytes * pdl_ratio
d_ms = d_base_ms * pdl_ratio
q_base = pdl_ratio
G(d) = 1.0
net_utility = p_sal * visibility * screen_area * q_base - eta * d_ms
```

## 5. Full-Body Strict Lookup 来源

lookup 文件为：

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

| normalized distance | strict density | lookup cap level | allowed levels |
|---:|---:|---:|---|
| 1.0 | 1.0 | 5 | `{1,2,3,4,5}` |
| 3.0 | 0.6 | 3 | `{1,2,3}` |
| 6.0 | 0.4 | 2 | `{1,2}` |

本 fixture 不加入 near-field rule，也不使用 target-aware lookup。

## 6. 两个输入的预算差异

`input_feasible.json` 使用：

```text
eta = 0.01
budget_total_bytes = 600.0
```

`input_infeasible.json` 除预算外与可行输入完全一致：

```text
budget_total_bytes = 219.0
```

lookup cap 后的最低可行预算为：

```text
500*0.2 + 350*0.2 + 250*0.2 = 220.0
```

因此不可行输入必须返回：

```text
status = INFEASIBLE_BUDGET
budget_gap = 1.0
```

## 7. 可复现测试命令

在仓库根目录运行：

```powershell
python -m pip install -r requirements.txt
python -m pytest tests/test_calibration_informed_proxy_fixture.py
python -m pytest
python scripts/validate_handcheck_fixtures.py
```

## 8. 明确禁止的实验结论

该 fixture 只验证 solver 的输入映射、lookup cap、预算状态和可审查输出。

它不能用于声明 Longdress tile-level 传输收益、真实解码开销、真实播放器 QoE、真实用户视口行为、baseline 性能或基于 measured Longdress tiles 的算法性能提升。

它不是从实际 Longdress 空间 tile 或 tile-level measurement 推导得到的输入，不是 Stage1 在线输出，不是播放器集成，也不是正式实验 baseline。
