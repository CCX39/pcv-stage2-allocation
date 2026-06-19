语言：[English](manual_review_checklist.md) | 中文

# 人工验收清单

本清单用于审查阶段0A至阶段0C输出，并确认 Stage2 契约没有越过本轮允许范围。

## 1. 项目边界理解

- [ ] 我能否用自己的话解释 Stage1 和 Stage2 的职责区别？
- [ ] 我能否说明当前项目为什么不等于完整播放器？
- [ ] 我能否说明距离标定项目为什么不等于 Stage2 分配器？
- [ ] 我能否列出截至阶段0C仍明确没有实现的功能？

## 2. 数学模型理解

- [ ] 我能否解释为什么原问题是 MCKP？
- [ ] 我能否说明每个分块“恰好选择一个档位”的含义？
- [ ] 我能否解释总预算约束？
- [ ] 我能否解释净效用中每个因子的作用？
- [ ] 我能否说明 `eta` 增大时算法行为可能如何变化？
- [ ] 我能否解释固定 `lambda` 后为什么分块可以独立选择？
- [ ] 我能否说明为什么算法不能声称严格全局最优？

## 3. Lookup 理解

- [ ] 我能否解释 lookup 作为候选上界的含义？
- [ ] 我能否举例说明 `lookup_level=3` 时允许哪些档位？
- [ ] 我能否解释为什么 near-field level 5 表示不裁剪，而不是强制选择 level 5？
- [ ] 我能否说明 normalized distance 不是物理米？
- [ ] 我能否说明当前 lookup 不能直接推广到所有点云内容？

## 4. 预算不可行理解

- [ ] 我能否计算最低可行预算的概念？
- [ ] 我能否解释为什么预算可能不可行？
- [ ] 我能否说明为什么不能静默超预算？
- [ ] 我能否说明为什么不能通过漏选分块伪造可行结果？
- [ ] 我能否说明为什么 `INFEASIBLE_BUDGET` 表示硬约束不兼容，而不是算法失败？
- [ ] 我能否列出 `INFEASIBLE_BUDGET` 输出中应包含的 `budget_total`、`b_min_feasible` 和 `budget_gap`？
- [ ] D0-2 当前是否为 `RESOLVED_USER_CONFIRMED` 状态？

## 5. 乘子搜索规则理解

- [ ] 我能否说明为什么未来求解器必须在进入 `lambda` 搜索前检查 `B_min_feasible`？
- [ ] 我能否解释自适应 `lambda_high` 括区间，以及它为什么不依赖人工固定上界？
- [ ] 我能否说明二分搜索每次迭代应记录哪些信息？
- [ ] 我能否解释当前最佳可行解如何选择？
- [ ] 我能否解释固定 `lambda` 下单个分块选档的确定性平局规则？
- [ ] 我能否说明为什么搜索终止不能产生超预算输出？
- [ ] D0-3 当前是否为 `RESOLVED_USER_CONFIRMED` 状态？

## 6. 数据来源理解

- [ ] 我能否区分 `measured`、`calibrated`、`derived`、`proxy` 和 `synthetic`？
- [ ] 我能否指出未来哪些字段可能先使用代理值？
- [ ] 我能否解释为什么代理值不能被描述成真实解码数据？
- [ ] 我能否说明 lookup 属于哪一种数据来源？
- [ ] 我能否说明为什么阶段0C后 D0-4 仍保持 `DRAFT`？

## 7. Schema 审查

- [ ] 我能否解释 `stage2_input.schema.json`、`distance_lookup.schema.json` 和 `stage2_result.schema.json` 分别负责什么？
- [ ] 我能否区分输入数据、lookup 数据和求解器结果数据？
- [ ] 我能否说明 Schema 只约束格式，不等于求解器已经实现？
- [ ] 我能否说明为什么 lookup Schema 使用 `semantics = cap`？
- [ ] 我能否说明归一化渲染距离不是物理米？
- [ ] 我能否说明为什么 `reference_docs/` 虽然提供依据，但不能提交到仓库？

## 8. 手算 Fixture 审查

- [ ] 我能否说明 `handcheck_3x3` fixture 用于验证什么？
- [ ] 我能否说明为什么该 fixture 采用 `G(d_i) = 1.0`，但不冻结未来的距离函数？
- [ ] 我能否手动复核 success 结果 `T1L3 + T2L1 + T3L1`？
- [ ] 我能否说明为什么 infeasible 输入返回 `INFEASIBLE_BUDGET`？
- [ ] 我能否说明该 fixture 是合成数据，而不是真实 Longdress 实验？

## 9. Codex 输出审查

- [ ] 文档中是否出现未经确认的新算法假设？
- [ ] D0-1 是否被正确记录为已确认？
- [ ] D0-2、D0-3 是否被正确记录为已解决？
- [ ] D0-4 是否仍保持 `DRAFT`？
- [ ] 中英文文档技术含义是否一致？
- [ ] 中文版是否自然，而不是逐句机械翻译？
- [ ] 中文版是否避免为普通概念保留过多英文词汇？
- [ ] 是否错误创建了算法代码、计划外 Schema 或计划外 fixture？
- [ ] 是否修改了 `reference_docs/`？
- [ ] 是否出现超出阶段0C范围的工作？

## 10. 文件与范围检查

- [ ] `.gitignore` 是否包含 `/reference_docs/`？
- [ ] `src/` 中是否没有算法源文件？
- [ ] `schemas/` 中是否只有 Schema 草案和 `.gitkeep`，没有校验器代码或 fixture 数据？
- [ ] `tests/fixtures/` 中是否只有计划内的 `handcheck_3x3` fixture，没有生成实验输出？
- [ ] 文档是否声明本轮没有实现 Stage2 求解器？
- [ ] 文档是否说明 near-field lookup level 5 不强制最终选择 level 5？
