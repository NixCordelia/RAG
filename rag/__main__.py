from __future__ import annotations

import argparse

from rag.users import parse_user


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m rag", description="WikiRAG：内部 Wiki 检索与问答")
    sub = p.add_subparsers(dest="cmd", required=True)
    ing = sub.add_parser("ingest", help="切分、向量化、写索引")
    ing.add_argument("--strategy", choices=("section", "sent_pack", "sent_only"), default=None)
    ev = sub.add_parser("eval", help="在评测集上跑检索与端到端")
    ev.add_argument("--ablation", action="store_true")
    ev.add_argument("--chunks", action="store_true")
    ev.add_argument("--paraphrase", action="store_true", help="改写题 vs 原题检索对照")
    ev.add_argument("--ragas", action="store_true", help="Ragas：检索 precision/recall 与 faithfulness")
    ev.add_argument("--mode", default="hybrid_rerank")
    sub.add_parser("serve", help="启动 Web 界面")
    sub.add_parser("sync-public", help="拉取 ROS 2 官方文档摘录（CC-BY）")
    ask = sub.add_parser("ask", help="命令行问答")
    ask.add_argument("question")
    ask.add_argument("--user", default="engineer")
    args = p.parse_args()

    from rag.settings import warn_missing_env

    warn_missing_env()

    if args.cmd == "ingest":
        from rag.ingest import ingest

        ingest(args.strategy)
    elif args.cmd == "eval":
        from rag.evaluate import ablation, chunk_ablation, evaluate, paraphrase_eval
        from rag.ragas_eval import run_ragas

        if args.chunks:
            chunk_ablation()
        elif args.ablation:
            ablation()
        elif args.paraphrase:
            paraphrase_eval(args.mode)
        elif args.ragas:
            run_ragas(args.mode)
        else:
            evaluate(args.mode)
    elif args.cmd == "serve":
        from rag.app import serve

        serve()
    elif args.cmd == "sync-public":
        from rag.sync_public import sync

        sync()
    elif args.cmd == "ask":
        from rag.agent import run_agent
        from rag.index import load_index
        from rag.llm import LLM

        ans = run_agent(args.question, parse_user(args.user), load_index(), LLM())
        from rag.trace import write_ask

        write_ask(args.user, args.question, ans)
        print(ans.text)
        if ans.citations:
            print("citations:", ", ".join(ans.citations))
        if ans.refused:
            print("refused:", ans.refuse_reason)


if __name__ == "__main__":
    main()
