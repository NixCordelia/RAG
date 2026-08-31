# 评测快照（26 篇 / 241 块，hybrid_rerank，M3E，Chroma，金标 38 题）

检索数字与是否 Chat 无关。生成路径见下表。同义词表：`rag/synonyms.py`。改写集：`data/goldenset_paraphrase.jsonl`。

## 端到端（Chat，本次）

| 指标 | 值 |
|---|---:|
| Hit@5 | 1.0000 |
| MRR | 0.9423 |
| ACL leak | 0.0 |
| E2E | 1.0（过期硬拒；可答题误拒回退抽取式） |
| groundedness | 0.8206 |
| 要点覆盖 | 0.9615 |
| retrieve p50 / p95 | 33.9 / 55.3 ms |
| e2e p50 / p95 | 3.2 s / 9.4 s |
| tokens | 70953 |

抽取式对照（更早一次、同一检索口径）：E2E 1.0、groundedness 0.9931、e2e 约 26 ms、tokens 0。Chat 更慢、词面重叠更低，但行为指标已对齐。

## Ragas（Chat + 裁判，优化后检索口径）

| 指标 | 值 |
|---|---:|
| ID Precision | 0.5827 |
| ID Recall | 1.0000 |
| Non-LLM Precision | 0.8153 |
| Non-LLM Recall | 0.7423 |
| Faithfulness | 0.7868 |
| LLM Context Recall | 0.7885 |

## 改写题检索（只测检索）

| 集合 | Hit@5 | MRR |
|---|---:|---:|
| 原金标可答题 26 | 1.0000 | 0.9423 |
| 改写题 26 | 1.0000 | 0.9423 |

改写后仍为 1.0，说明这批改写还不够「换皮」：仍是领域词，不是开放域对抗。它能排除「完全背原句」，不能证明换一种完全不同的说法仍满分。

## 检索消融（可答题，240 块时）

| mode | Hit@5 | MRR | p50 ms |
|---|---:|---:|---:|
| dense | 1.0000 | 0.8397 | 26.5 |
| bm25 | 0.9615 | 0.9167 | 25.8 |
| hybrid | 1.0000 | 0.9231 | 25.8 |
| hybrid_rerank | 1.0000 | 0.9231 | 24.9 |

哈希旧基线（仅内部 14 篇）见 [eval-hash-baseline.md](eval-hash-baseline.md)，不要和本表混用。
