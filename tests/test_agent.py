from __future__ import annotations

import unittest

from rag.agent import run_agent, should_refuse_expired
from rag.embed import hashed_embed
from rag.index import Index
from rag.models import Chunk, User


class HashLLM:
    can_chat = False

    def embed(self, texts):
        return hashed_embed(texts)


def C(cid, doc, text, acl, **kw) -> Chunk:
    return Chunk(
        id=cid,
        doc_id=doc,
        title=doc,
        heading="h",
        text=text,
        parent_text=text,
        dept="engineering",
        acl=acl,
        classification=kw.get("classification", "internal"),
        version="1",
        expires=kw.get("expires"),
        source="t.md",
    )


class ExtractiveAgentTest(unittest.TestCase):
    def setUp(self):
        chunks = [
            C("q#0", "qos", "BEST_EFFORT for lidar IMU camera high rate", ["engineer"]),
            C("e#0", "old", "use ros1_bridge forever", ["engineer"], expires="2020-01-01"),
            C("s#0", "sec", "prod key 7412", ["ops"], classification="confidential"),
        ]
        self.index = Index(chunks, hashed_embed([c.text for c in chunks]))
        self.llm = HashLLM()

    def test_answers_with_citation(self):
        ans = run_agent("lidar BEST_EFFORT", User("e", "eng", ["engineer"]), self.index, self.llm)
        self.assertFalse(ans.refused)
        self.assertTrue(ans.citations)
        self.assertEqual(ans.mode, "extractive")

    def test_expired_only(self):
        ans = run_agent("ros1_bridge forever", User("e", "eng", ["engineer"]), self.index, self.llm)
        self.assertTrue(ans.refused)
        self.assertEqual(ans.refuse_reason, "expired")

    def test_acl_looks_like_no_evidence(self):
        ans = run_agent("prod key 7412", User("e", "eng", ["engineer"]), self.index, self.llm)
        self.assertTrue(ans.refused)
        self.assertEqual(ans.refuse_reason, "no_evidence")
        self.assertFalse(any(h.chunk.doc_id == "sec" for h in ans.hits))


class ScriptLLM:
    can_chat = True

    def __init__(self, replies: list[str]):
        self.replies = replies
        self.i = 0

    def embed(self, texts):
        return hashed_embed(texts)

    def chat(self, messages, temperature=0.0):
        r = self.replies[min(self.i, len(self.replies) - 1)]
        self.i += 1
        return r


class AgentGuardTest(unittest.TestCase):
    def setUp(self):
        chunks = [
            C("q#0", "qos", "BEST_EFFORT for lidar IMU camera high rate", ["engineer"]),
            C("e#0", "old", "use ros1_bridge forever", ["engineer"], expires="2020-01-01"),
        ]
        self.index = Index(chunks, hashed_embed([c.text for c in chunks]))
        self.user = User("e", "eng", ["engineer"])

    def test_chat_cannot_answer_expired_as_current(self):
        llm = ScriptLLM(
            [
                '{"tool":"search","query":"ros1_bridge forever"}',
                '{"tool":"answer","text":"现在仍可用 ros1_bridge 过渡","citations":["e#0"]}',
            ]
        )
        ans = run_agent("现在还可以用 ros1_bridge forever 做过渡吗", self.user, self.index, llm)
        self.assertTrue(ans.refused)
        self.assertEqual(ans.refuse_reason, "expired")

    def test_ungrounded_answer_rewritten(self):
        llm = ScriptLLM(
            [
                '{"tool":"search","query":"lidar BEST_EFFORT"}',
                '{"tool":"answer","text":"应当先重启交换机并升级固件","citations":["q#0"]}',
            ]
        )
        ans = run_agent("lidar BEST_EFFORT", self.user, self.index, llm)
        self.assertFalse(ans.refused)
        self.assertIn("BEST_EFFORT", ans.text)
        self.assertNotIn("交换机", ans.text)

    def test_chat_no_evidence_falls_back_to_extractive(self):
        llm = ScriptLLM(
            [
                '{"tool":"search","query":"lidar BEST_EFFORT"}',
                '{"tool":"refuse","reason":"no_evidence","detail":"随便拒"}',
            ]
        )
        ans = run_agent("lidar BEST_EFFORT", self.user, self.index, llm)
        self.assertFalse(ans.refused)
        self.assertEqual(ans.mode, "extractive_fallback")
        self.assertIn("BEST_EFFORT", ans.text)

    def test_constrain_drops_invented_checklist_item(self):
        from rag.agent import constrain_to_evidence
        from rag.embed import hashed_embed
        from rag.index import Index
        from rag.models import Hit

        ts = C(
            "t#0",
            "ts",
            "依次检查是否 source 对应 workspace、ROS_DOMAIN_ID 是否一致、防火墙是否丢组播、QoS 是否兼容",
            ["engineer"],
        )
        hit = Hit(chunk=ts, score=1.0, expired=False)
        text = "应检查 source、ROS_DOMAIN_ID、防火墙，以及先重启交换机再升级固件。"
        out = constrain_to_evidence(text, [hit])
        self.assertIn("source", out)
        self.assertNotIn("交换机", out)

    def test_should_refuse_expired_when_best_hit_expired(self):
        from rag.models import Hit

        old = self.index.chunks[1]
        self.assertTrue(should_refuse_expired("ros1_bridge forever", [Hit(chunk=old, score=1.0, expired=True)]))

    def test_fallback_does_not_unmask_secret(self):
        secret = C("s#0", "sec", "prod key 7412", ["ops"], classification="confidential")
        chunks = self.index.chunks + [secret]
        index = Index(chunks, hashed_embed([c.text for c in chunks]))
        llm = ScriptLLM(['{"tool":"refuse","reason":"no_evidence"}'])
        ans = run_agent("prod key 7412", self.user, index, llm)
        self.assertTrue(ans.refused)
        self.assertEqual(ans.refuse_reason, "no_evidence")
        self.assertFalse(any(h.chunk.doc_id == "sec" for h in ans.hits))


if __name__ == "__main__":
    unittest.main()
