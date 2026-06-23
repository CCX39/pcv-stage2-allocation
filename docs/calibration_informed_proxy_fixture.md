# Calibration-Informed Proxy Fixture

Status: Phase 2A fixture mapping note. This document is not an algorithm contract.

## 1. Purpose

The `tests/fixtures/calibration_informed_proxy/` fixture checks that the current typed loader, lookup cap preprocessing, `solve_stage2(...)`, structured result assembly, and tests-only exhaustive oracle can process a non-handcheck Stage2 input with explicit provenance boundaries.

This is a calibration-informed proxy fixture. It combines calibrated Longdress full-body strict lookup caps with proxy tile metadata. Its role is to validate input mapping, lookup cap behavior, budget status handling, and auditable solver output.

## 2. Why This Is Not Actual Longdress Tile Input

The fixture is not real Longdress spatial tiling. The tile IDs are proxy names, not cells parsed from Longdress geometry. The tile spatial factors are proxy values, not saliency measurements, viewport traces, projected areas from a real camera, encoded file sizes, or decoder benchmarks.

The values `distance_norm = 1.0, 3.0, 6.0` are selected from calibrated lookup support points. In this fixture they are not geometric distances derived from real Longdress tile centers.

## 3. Calibrated And Proxy Mapping

Calibrated fields:

| Field | Source |
|---|---|
| full-body strict lookup cap | `20260602_161531_longdress_full10` |
| source run ID | `20260602_161531_longdress_full10` |
| threshold profile | strict `p10 SSIM >= 0.98` |
| normalized-distance support points | `1.0`, `3.0`, `6.0` |
| PDL support grid | `0.2`, `0.4`, `0.6`, `0.8`, `1.0` |

Proxy fields:

| Field | Meaning |
|---|---|
| tile spatial identity | `T_near_core`, `T_mid_visible`, `T_far_peripheral` are proxy tile IDs |
| `p_sal` | proxy saliency weight |
| `visibility` | proxy visibility weight |
| `screen_area` | proxy screen-area share |
| `r_base_bytes` | proxy base byte scale |
| `d_base_ms` | proxy base decode-time scale |
| `q_base` | proxy base utility, set equal to `pdl_ratio` |
| `eta` | proxy decode penalty |
| `Budget_total` | proxy Stage2 budget |

## 4. Fixed Formulas And Values

Quality levels:

| level_id | pdl_ratio | q_base |
|---:|---:|---:|
| 1 | 0.2 | 0.2 |
| 2 | 0.4 | 0.4 |
| 3 | 0.6 | 0.6 |
| 4 | 0.8 | 0.8 |
| 5 | 1.0 | 1.0 |

Tile bases:

| tile_id | p_sal | visibility | screen_area | distance_norm | r_base_bytes | d_base_ms |
|---|---:|---:|---:|---:|---:|---:|
| `T_near_core` | 1.00 | 1.00 | 0.30 | 1.0 | 500 | 5.0 |
| `T_mid_visible` | 0.60 | 0.80 | 0.18 | 3.0 | 350 | 3.5 |
| `T_far_peripheral` | 0.25 | 0.40 | 0.08 | 6.0 | 250 | 2.5 |

Per tile and level:

```text
r_bytes = r_base_bytes * pdl_ratio
d_ms = d_base_ms * pdl_ratio
q_base = pdl_ratio
G(d) = 1.0
net_utility = p_sal * visibility * screen_area * q_base - eta * d_ms
```

## 5. Full-Body Strict Lookup Source

The lookup file is `tests/fixtures/calibration_informed_proxy/distance_lookup_fullbody_strict.json`.

It uses:

```text
semantics = cap
target_id = null
threshold = strict p10 SSIM >= 0.98
source run = 20260602_161531_longdress_full10
distance unit = normalized_render_distance
view_context = full_body_calibration_informed_proxy
```

Lookup cap mapping:

| normalized distance | strict density | lookup cap level | allowed levels |
|---:|---:|---:|---|
| 1.0 | 1.0 | 5 | `{1,2,3,4,5}` |
| 3.0 | 0.6 | 3 | `{1,2,3}` |
| 6.0 | 0.4 | 2 | `{1,2}` |

No near-field rule and no target-aware lookup rule are included.

## 6. Budget Variants

`input_feasible.json` uses:

```text
eta = 0.01
budget_total_bytes = 600.0
```

`input_infeasible.json` is identical except:

```text
budget_total_bytes = 219.0
```

The minimum feasible budget under the cap is:

```text
500*0.2 + 350*0.2 + 250*0.2 = 220.0
```

Therefore the infeasible input must return:

```text
status = INFEASIBLE_BUDGET
budget_gap = 1.0
```

## 7. Reproducible Test Commands

Run from the repository root:

```powershell
python -m pip install -r requirements.txt
python -m pytest tests/test_calibration_informed_proxy_fixture.py
python -m pytest
python scripts/validate_handcheck_fixtures.py
```

## 8. Explicit Non-Claims

This fixture only validates solver input mapping, lookup cap resolution, budget status handling, and auditable structured output.

It must not be used to claim Longdress tile-level transmission gains, real decoder cost, real player QoE, real viewport behavior, baseline performance, or algorithmic improvement on measured Longdress tiles.

It is not derived from actual Longdress spatial tiles, tile-level measurements, Stage1 online output, player integration, or a formal experiment baseline.
