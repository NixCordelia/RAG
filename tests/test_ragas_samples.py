from __future__ import annotations

import importlib.util
import unittest

from rag.embed import hashed_embed
from rag.index import Index
from rag.models import Chunk, Hit, User
from rag.ragas_eval import pack_sample, reference_contexts


def C(**kw) -> Chunk:
    text = kw.get("text", "x")
    return Chunk(
        id=kw["id"],
        doc_id=kw["doc_id"],
        title=kw.get("title", kw["doc_id"]),
        heading=kw.get("heading", "h"),
        text=text,
        parent_text=kw.get("parent_text", text),
        dept="engineering",
        acl=kw.get("acl", ["engineer"]),
        classification="internal",
        version="1",
        expires=None,
        source="t.md",
    )


class PackSampleTest(unittest.TestCase):
    def setUp(self):
        self.chunks = [
            C(id="qos#0", doc_id="ros2-qos", text="BEST_EFFORT lidar high rate", acl=["engineer"]),
            C(id="sec#0", doc_id="secret", text="keystore path", acl=["ops"]),
        ]
        self.index = Index(self.chunks, hashed_embed([c.text for c in self.chunks]))
        self.eng = User("e", "eng", ["engineer"])

    def test_reference_skips_unauthorized_docs(self):
        texts = reference_contexts(self.index, self.eng, ["ros2-qos", "secret"])
        self.assertEqual(len(texts), 1)
        self.assertIn("BEST_EFFORT", texts[0])

    def test_reference_keeps_question_overlap_chunks(self):
        extra = C(id="qos#1", doc_id="ros2-qos", text="unrelated banana picnic", acl=["engineer"])
        chunks = self.chunks + [extra]
        index = Index(chunks, hashed_embed([c.text for c in chunks]))
        texts = reference_contexts(index, self.eng, ["ros2-qos"], "lidar BEST_EFFORT")
        self.assertTrue(any("BEST_EFFORT" in t for t in texts))
        self.assertFalse(any("banana" in t for t in texts))

    def test_pack_uses_doc_ids(self):
        hits = [Hit(chunk=self.chunks[0], score=1.0, expired=False)]
        item = {
            "id": "s01",
            "type": "single",
            "expected_behavior": "answer",
            "expected_doc_ids": ["ros2-qos"],
            "question": "lidar qos?",
        }
        sample = pack_sample(item, self.eng, hits, "use BEST_EFFORT", self.index)
        self.assertEqual(sample["retrieved_context_ids"], ["ros2-qos"])
        self.assertEqual(sample["reference_context_ids"], ["ros2-qos"])
        self.assertTrue(sample["retrieved_contexts"])
        self.assertTrue(sample["reference"])

    def test_pack_keeps_top5_unique_doc_ids(self):
        extra = [
            C(id=f"d{i}#0", doc_id=f"doc-{i}", text=f"body {i}", acl=["engineer"])
            for i in range(8)
        ]
        chunks = extra
        index = Index(chunks, hashed_embed([c.text for c in chunks]))
        hits = [Hit(chunk=c, score=1.0 - i * 0.01, expired=False) for i, c in enumerate(chunks)]
        item = {
            "id": "x",
            "type": "single",
            "expected_behavior": "answer",
            "expected_doc_ids": ["doc-0"],
            "question": "q",
        }
        sample = pack_sample(item, self.eng, hits, "a", index)
        self.assertEqual(sample["retrieved_context_ids"], [f"doc-{i}" for i in range(5)])
        self.assertEqual(len(sample["retrieved_contexts"]), 5)


@unittest.skipUnless(importlib.util.find_spec("ragas") is not None, "ragas extra not installed")
class RagasIdMetricTest(unittest.TestCase):
    def test_id_precision_recall(self):
        import asyncio

        from ragas.dataset_schema import SingleTurnSample
        from ragas.metrics import IDBasedContextPrecision, IDBasedContextRecall

        sample = SingleTurnSample(
            retrieved_context_ids=["ros2-qos", "ros2-tf"],
            reference_context_ids=["ros2-qos"],
        )

        async def run():
            p = await IDBasedContextPrecision().single_turn_ascore(sample)
            r = await IDBasedContextRecall().single_turn_ascore(sample)
            return p, r

        prec, rec = asyncio.run(run())
        self.assertAlmostEqual(prec, 0.5)
        self.assertAlmostEqual(rec, 1.0)


if __name__ == "__main__":
    unittest.main()
