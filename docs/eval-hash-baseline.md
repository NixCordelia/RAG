# 特征哈希评测记录

命令：`python -m rag ingest`，再分别跑 `python -m rag eval --ablation`、`python -m rag eval --chunks`、`python -m rag eval`。

记录时语料为内部 Wiki 14 篇（尚未加入 `data/corpus/public/`），评测集 33 题；向量为 384 维特征哈希；回答为抽取式。稠密相似度用内存 numpy 点积（尚未走 Chroma），表中毫秒数只反映那一次路径。第二次 `ingest` 在 backend 与切分策略不变时应打印 `reused=38`。

## 检索（可答题）

| mode | Hit@5 | MRR | p50 ms | p95 ms |
|---|---:|---:|---:|---:|
| dense | 1.0000 | 0.9444 | 0.24 | 0.34 |
| bm25 | 1.0000 | 0.9365 | 0.23 | 0.28 |
| hybrid (RRF) | 1.0000 | 0.9683 | 0.25 | 0.30 |
| hybrid_rerank | 1.0000 | 0.9683 | 0.27 | 0.33 |

## 切分（hybrid_rerank，只建内存索引，不改磁盘）

| strategy | chunks | Hit@5 | MRR | p50 ms |
|---|---:|---:|---:|---:|
| section（默认） | 38 | 1.0000 | 0.9683 | 0.30 |
| sent_pack | 38 | 1.0000 | 0.9683 | 0.28 |
| sent_only | 104 | 1.0000 | 0.9206 | 0.46 |

本批 Wiki 段落较短，`section` 与 `sent_pack` 块数相同；单句切分块数变多，MRR 下降。

## 端到端

| 指标 | 值 |
|---|---:|
| ACL leak rate | 0.0 |
| E2E behavior | 1.0 |
| groundedness | 0.9931 |
| retrieve p50 / p95 | 0.27 / 0.45 ms |
| e2e p50 / p95 | 0.5 / 0.7 ms |
| tokens | 0（抽取式） |
