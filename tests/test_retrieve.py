from __future__ import annotations

import unittest

from rag.embed import hashed_embed
from rag.index import Index
from rag.models import Chunk, User
from rag.retrieve import expand_queries, retrieve, unique_by_doc


class HashLLM:
    def embed(self, texts):
        return hashed_embed(texts)


def C(**kw) -> Chunk:
    text = kw.get("text", "x")
    return Chunk(
        id=kw["id"],
        doc_id=kw["doc_id"],
        title=kw.get("title", kw["doc_id"]),
        heading=kw.get("heading", "h"),
        text=text,
        parent_text=kw.get("parent_text", text),
        dept=kw.get("dept", "engineering"),
        acl=kw["acl"],
        classification=kw.get("classification", "internal"),
        version="1",
        expires=kw.get("expires"),
        source="t.md",
    )


class RetrieveAclTest(unittest.TestCase):
    def setUp(self):
        self.chunks = [
            C(id="pub#0", doc_id="pub", text="colcon build symlink-install source setup.bash", acl=["engineer", "intern"]),
            C(
                id="sec#0",
                doc_id="secret",
                text="production keystore /opt/fleet/pki/prod discovery port 7412",
                acl=["ops"],
                classification="confidential",
            ),
            C(id="old#0", doc_id="old", text="ros1_bridge noetic transition still recommended", acl=["engineer"], expires="2020-01-01"),
        ]
        self.index = Index(self.chunks, hashed_embed([c.text for c in self.chunks]))
        self.llm = HashLLM()

    def test_intern_never_sees_secret(self):
        hits = retrieve("keystore production 7412", User("i", "eng", ["intern"]), self.index, k=8, llm=self.llm)
        self.assertFalse(any(h.chunk.doc_id == "secret" for h in hits))

    def test_ops_sees_secret(self):
        hits = retrieve("keystore production 7412", User("o", "ops", ["ops"]), self.index, k=8, llm=self.llm)
        self.assertTrue(any(h.chunk.doc_id == "secret" for h in hits))

    def test_acl_fail_closed_empty(self):
        hits = retrieve("keystore 7412", User("h", "hr", ["hr"]), self.index, k=8, llm=self.llm)
        self.assertEqual(hits, [])

    def test_expired_still_retrievable_but_flagged(self):
        hits = retrieve("ros1_bridge noetic", User("e", "eng", ["engineer"]), self.index, k=8, llm=self.llm)
        self.assertTrue(any(h.chunk.doc_id == "old" and h.expired for h in hits))


class QueryExpandTest(unittest.TestCase):
    def test_splits_and_glossary(self):
        qs = expand_queries("长时间任务为什么不要写在服务回调里而要用 Action？")
        self.assertGreaterEqual(len(qs), 2)
        self.assertTrue(any("Action" in q or "action" in q.lower() for q in qs))

    def test_logging_synonym_not_gold_regex(self):
        from rag.synonyms import extra_queries

        extra = extra_queries("日志默认发到哪条 topic")
        self.assertTrue(any("rosout" in e.lower() or "/rosout" in e for e in extra))

    def test_unique_keeps_first_doc(self):
        from rag.models import Hit

        a = C(id="a#0", doc_id="qos", text="BEST_EFFORT", acl=["engineer"])
        b = C(id="a#1", doc_id="qos", text="RELIABLE", acl=["engineer"])
        c = C(id="b#0", doc_id="tf", text="map odom", acl=["engineer"])
        hits = [
            Hit(chunk=a, score=1.0, expired=False),
            Hit(chunk=b, score=0.9, expired=False),
            Hit(chunk=c, score=0.8, expired=False),
        ]
        uniq = unique_by_doc(hits)
        self.assertEqual([h.chunk.doc_id for h in uniq], ["qos", "tf"])


class Bm25PrefersLexical(unittest.TestCase):
    def test_exact_term(self):
        chunks = [
            C(id="a#0", doc_id="a", text="deadline liveliness sensor timeout", acl=["engineer"]),
            C(id="b#0", doc_id="b", text="unrelated banana picnic", acl=["engineer"]),
        ]
        index = Index(chunks, hashed_embed([c.text for c in chunks]))
        hits = retrieve("deadline liveliness", User("e", "eng", ["engineer"]), index, k=1, mode="bm25", llm=HashLLM())
        self.assertEqual(hits[0].chunk.doc_id, "a")


if __name__ == "__main__":
    unittest.main()
