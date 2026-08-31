# WikiRAG

查内部 Wiki 太散：QoS、组网、过期迁移说明各写在不同页里，关键字对不上就只能全文翻。这个仓库是为此做的本地知识库——把文档切块、建索引，按问题检索，并带上文档本身的阅读权限。

语料分两层，详见 [data/NOTICE.md](data/NOTICE.md)：

- `data/corpus/internal/`：内部规程（权限、过期、密钥、入职）。公开手册没有这些字段。
- `data/corpus/public/`：ROS 2 官方文档（Humble）摘录，[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)，每页有 `upstream` 链接。不是 docs.ros.org 整站镜像。

Python 3.10+。`requirements.txt` 含 Chroma；本地中文向量再装 `requirements-m3e.txt`；Ragas 评测再装 `requirements-eval.txt`。

## 有没有 Chat API 有何不同

检索（切分、M3E / 哈希向量、BM25、Chroma、权限过滤）不依赖大模型密钥。

| | 未配置 `OPENAI_API_KEY` | 配置了 OpenAI 兼容 Chat（生成网关） |
|---|---|---|
| 回答 | 抽取式：把命中段落拼起来 | 模型按 JSON 调用 `search` / `read` / `answer` / `refuse`（最多 4 步） |
| 多跳、改写问法 | 不做，只检索原句 | 可以多次 search、读父段落再组织答案 |
| 文风 | 像摘抄 | 可以写成连贯答复，仍要求带 citations |

配 API 改善的是**生成**，不是检索是否可用。Embedding 用本地 M3E 即可，不必走远程向量接口。

Ragas 的 Faithfulness / LLM Context Recall 走**另一套**评测网关：`EVAL_API_KEY`、`EVAL_BASE_URL`、`EVAL_CHAT_MODEL`。不填则复用 `OPENAI_*` / `CHAT_MODEL`。只配 `EVAL_*`、不配生成密钥时，问答仍是抽取式，但评测裁判仍可调用。

## 流程

```
提问（附带角色）
    │
    ▼
权限过滤后再打分（无权块不进 Prompt；越权看起来像资料不足）
    │
    ├─ 无 Chat：一次检索 → 摘录 Top 块 或 拒答
    └─ 有 Chat：循环 search / read，直到 answer 或 refuse
    │
    ▼
引用 chunk id；`ask` 与 Web 都会把请求写入 `data/traces/ask.jsonl`
```

| 层 | 实现 |
|---|---|
| 切分 | 默认按标题段再滑窗（`section`）；另有 `sent_pack`、`sent_only` |
| 稠密向量 | 本地 M3E / OpenAI 兼容 Embedding / 特征哈希；写入 Chroma（HNSW + cosine）。正文与 ACL 在 `chunks.jsonl` |
| 稀疏 | Okapi BM25，与稠密结果做 RRF，再分数融合 |
| 查询扩展 | 并列问句拆分 + ROS 领域同义词，多路 RRF |
| 收束 | 按文档去重，丢掉相对头名过弱的近邻 |
| 生成 | 有密钥走 Chat；过期块禁止当现行依据；答案词面重叠过低则回退摘录 |
| 界面 | FastAPI 单页 |

查询时只对当前角色允许的块计分。过期文档仍可检索到，但标 EXPIRED，不能当现行依据。

## 运行

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-m3e.txt
Copy-Item .env.example .env
```

`.env` 程序只读这一份（已 gitignore）。本地向量示例：

```
EMBED_BACKEND=m3e
EMBED_MODEL=moka-ai/m3e-small
```

国内拉模型慢或超时（WinError 10060）时：

```powershell
$env:HF_ENDPOINT="https://hf-mirror.com"
$env:HF_HUB_OFFLINE="1"   # 模型已下载过、只想用本地缓存
```

公开文档已在 `data/corpus/public/`，一般不必再拉。然后：

```powershell
python -m rag ingest
python -m unittest discover -s tests -v
python -m rag serve
```

浏览器打开 `http://127.0.0.1:8000`。命令行：

```powershell
python -m rag ask "激光该用 BEST_EFFORT 还是 RELIABLE？" --user engineer
python -m rag ask "生产环境 DDS 端口和密钥放在哪？" --user intern
```

`ingest` 应打印 `backend=m3e` 和 `vector_store=chroma`。8000 被占用时：`$env:PORT="8001"`。

Chat（可选）在 `.env` 里加 OpenAI 兼容网关后重启 `serve`：

```
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
CHAT_MODEL=gpt-4o-mini
```

评测裁判可换成另一家（例如生成用 DeepSeek、裁判用更便宜的模型）：

```
EVAL_API_KEY=...
EVAL_BASE_URL=https://api.openai.com/v1
EVAL_CHAT_MODEL=gpt-4o-mini
```

只配 Chat、向量仍用 M3E 时，不要把 `EMBED_BACKEND` 改成 `openai`，也无需为向量再跑远程 Embedding。

## 评测

`data/goldenset.jsonl` 共 38 题（内部规程 + 公开文档；含单跳 / 多跳 / 库中没有 / 越权 / 过期）。

```powershell
python -m rag eval
python -m rag eval --ablation
python -m rag eval --chunks
python -m rag eval --paraphrase
pip install -r requirements-eval.txt
python -m rag eval --ragas
```

`--ragas` 用 [Ragas](https://docs.ragas.io/) 算检索准确和回答是否贴着证据。无评测密钥时跑 **ID Context Precision/Recall@5**（去重文档 id vs `expected_doc_ids`，弱分文档不计入）和 **Non-LLM Context Precision/Recall**（命中块 vs 与问句有重叠的参考块）。配了 `EVAL_*` 或 `OPENAI_*` 再跑 **Faithfulness**、**LLM Context Recall**。报告：`data/eval/ragas_report.md`。

报告写到 `data/eval/`（默认不提交）。指标含义：

| 指标 | 含义 |
|---|---|
| Hit@5 / MRR | 只统计期望为「作答」的题 |
| groundedness | 答案词与引用块（子块+父段）重叠率；拒答记 1 |
| retrieve / e2e p50·p95 | 检索与端到端时延 |
| tokens | Chat usage；抽取式为 0 |
| ACL leak rate | 无权块出现在命中或引用中的比例，目标 0 |
| E2E | 能答的给出引用；不能答/越权拒答且不泄密；过期题 `refuse_reason=expired` |
| 要点覆盖 | 可答题答案是否命中 `expected_keypoints`（中英用 `\|` 表示同义） |
| 改写 Hit@5 | `eval --paraphrase`，同一金标文档、不同问法 |
| ID Context P/R@5 | Ragas，Top-5 去重文档 id vs goldenset；只统计可答题 |
| Non-LLM Context P/R | Ragas，命中子块 vs 参考文档子块（RapidFuzz，阈值 0.4） |
| Faithfulness | Ragas，回答中的断言能否被检索上下文支持（需 `EVAL_*` 或 `OPENAI_*` 裁判） |

当前 38 题 / M3E 对照见 [docs/eval-m3e-n38.md](docs/eval-m3e-n38.md)。更早的哈希基线（仅内部 14 篇）见 [docs/eval-hash-baseline.md](docs/eval-hash-baseline.md)，不要和现在的块数、时延混用。

## 目录

```
rag/                 切分、索引、检索、问答、评测、Web
data/corpus/internal 内部规程 Wiki
data/corpus/public   ROS 2 文档摘录（CC-BY）
data/NOTICE.md       语料来源与许可证
data/goldenset.jsonl
data/goldenset_paraphrase.jsonl
tests/               不依赖 Chat API
```

未做账号登录和生产部署；角色通过 `--user` 或页面下拉选择。

MIT License.
