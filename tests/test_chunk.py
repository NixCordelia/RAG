from __future__ import annotations

import unittest

from rag.agent import run_agent
from rag.embed import hashed_embed
from rag.evaluate import groundedness
from rag.index import Index
from rag.ingest import STRATEGIES, build_chunks, load_documents
from rag.models import Answer, Chunk, User
from rag.text import child_parts, pack_units, split_sentences


class SentenceSplitTest(unittest.TestCase):
    def test_zh_sentences(self):
        s = split_sentences("第一句。第二句！第三句？")
        self.assertEqual(s, ["第一句。", "第二句！", "第三句？"])

    def test_pack_merges_short(self):
        packs = pack_units(["短。", "也短。", "这是一句比较长的内容用来撑满窗口。"], 20)
        self.assertGreaterEqual(len(packs), 1)
        self.assertLess(len(packs), 3)

    def test_sent_only_parent_is_self(self):
        parts = child_parts("甲。乙。", "sent_only", 500, 80, 220)
        self.assertEqual(parts[0][0], parts[0][1])


class StrategyCountTest(unittest.TestCase):
    def test_counts_increase(self):
        docs = load_documents()
        n = {s: len(build_chunks(docs, s)) for s in STRATEGIES}
        self.assertGreaterEqual(n["sent_pack"], n["section"])
        self.assertGreaterEqual(n["sent_only"], n["sent_pack"])
        self.assertTrue(n["section"] > 0)

    def test_sent_pack_keeps_parent(self):
        import re

        docs = load_documents()
        chunks = build_chunks(docs, "sent_pack")
        self.assertTrue(chunks)

        def compact(s: str) -> str:
            return re.sub(r"\s+", "", s)

        self.assertTrue(all(compact(c.text) in compact(c.parent_text) for c in chunks))


class GroundednessTest(unittest.TestCase):
    def test_extractive_high(self):
        text = "BEST_EFFORT for lidar IMU camera high rate extra context here"
        ch = Chunk(
            id="q#0",
            doc_id="qos",
            title="qos",
            heading="h",
            text=text,
            parent_text=text,
            dept="engineering",
            acl=["engineer"],
            classification="internal",
            version="1",
            expires=None,
            source="t.md",
        )
        idx = Index([ch], hashed_embed([ch.text]))

        class HashLLM:
            can_chat = False

            def embed(self, texts):
                return hashed_embed(texts)

        ans = run_agent("lidar BEST_EFFORT", User("e", "eng", ["engineer"]), idx, HashLLM())
        self.assertFalse(ans.refused)
        self.assertGreaterEqual(groundedness(ans, idx), 0.6)
        self.assertGreaterEqual(ans.latency_ms, 0)
        refuse = Answer(text="x", refused=True, refuse_reason="no_evidence")
        self.assertEqual(groundedness(refuse, idx), 1.0)


if __name__ == "__main__":
    unittest.main()
