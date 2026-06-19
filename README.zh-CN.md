语言：[English](README.md) | 中文

# pcv-stage2-allocation

`pcv-stage2-allocation` 是硕士课题《轻量级视口感知点云体积视频传输与渲染协同优化》中 Work1 Stage2 的项目工作区。它的目标是在给定视频组总数据预算的前提下，定义、审查并后续实现空间分块质量分配机制。

当前仓库处于**阶段0A：项目骨架与 Stage2 MVP 算法契约草案**。阶段0A只建立文档、目录和可追溯的工程边界，不实现 Stage2 求解器。

## Work1 结构

Work1 采用两阶段决策结构：

- Stage1 根据网络状态、缓冲区状态和视口内容规模估计当前视频组的总数据预算 `Budget_total`。
- Stage2 在该总预算约束下，为每个参与决策的空间分块选择一个离散质量档位。

本仓库只负责 Stage2 空间质量分配。未来 Stage1 可以提供 `Budget_total`，但第一版 Stage2 也可以先从配置文件或离线实验输入中读取该预算。

## 与距离标定项目的关系

独立的 `PCV-Distance-Quality-Calibration` 项目提供 Longdress 在当前 Web/Three.js 渲染管线下的离线视距到质量查表依据。该项目不是 Stage2 分配器。

在本仓库中，lookup 资产被视为外部标定输入。当前已经确认的运行时语义是：

```text
lookup_level = 当前距离条件下最高有必要选择的候选质量档位
allowed_levels = {1, 2, ..., lookup_level}
```

near-field lookup level 5 表示候选上界不裁剪高质量档位，并不表示最终必须选择 level 5。

## 当前目录结构

```text
pcv-stage2-allocation/
├─ README.md
├─ README.zh-CN.md
├─ .gitignore
├─ docs/
│  ├─ stage2_mvp_contract.md
│  ├─ stage2_mvp_contract.zh-CN.md
│  ├─ decision_log.md
│  ├─ decision_log.zh-CN.md
│  ├─ manual_review_checklist.md
│  └─ manual_review_checklist.zh-CN.md
├─ schemas/
│  └─ .gitkeep
├─ data/
│  └─ lookups/
│     └─ .gitkeep
├─ tests/
│  └─ fixtures/
│     └─ .gitkeep
├─ src/
│  └─ .gitkeep
├─ outputs/
│  └─ .gitkeep
└─ reference_docs/
   └─ 本地只读参考文档
```

`reference_docs/` 仅作为本地上下文使用，已加入 Git 忽略规则。

## 当前已有文档

- [Stage2 MVP Contract](docs/stage2_mvp_contract.md)：计划中的算法契约、模型边界、输入输出概念、不变量和待决事项。
- [Decision Log](docs/decision_log.md)：lookup 语义、预算不可行行为、乘子搜索规则和数据来源词汇的决策闸门。
- [Manual Review Checklist](docs/manual_review_checklist.md)：供研究者本人审查阶段0A输出的检查问题。
- [中文 Stage2 MVP 契约](docs/stage2_mvp_contract.zh-CN.md)
- [中文决策记录](docs/decision_log.zh-CN.md)
- [中文人工验收清单](docs/manual_review_checklist.zh-CN.md)

## 当前尚未实现

本仓库当前没有：

- Stage2 求解器；
- JSON Schema；
- 测试 fixture；
- 正式实验结果；
- Web 播放器集成；
- Stage1 在线接口。

因此，不能将本仓库描述为已经完成或已经验证的 Stage2 分配器。

## 后续计划

阶段0A经人工审查后，后续阶段可以再定义 Schema、准备受控 fixture、实现求解器、加入校验并运行正式实验。这些工作均不属于本轮范围。
