from __future__ import annotations

import unittest

from rag.ingest import build_chunks, load_documents
from rag.text import is_expired, parse_front_matter, tokenize


class TextTest(unittest.TestCase):
    def test_front_matter_list(self):
        raw = "---\nacl: [ops, security]\nexpires: null\n---\nbody"
        meta, body = parse_front_matter(raw)
        self.assertEqual(meta["acl"], ["ops", "security"])
        self.assertIsNone(meta["expires"])
        self.assertEqual(body, "body")

    def test_tokenize_mixed(self):
        toks = tokenize("ROS_DOMAIN_ID 组播")
        self.assertIn("ros_domain_id", toks)
        self.assertTrue(any("组" in t or t == "组播" or "播" in t for t in toks))

    def test_expired(self):
        self.assertTrue(is_expired("2020-01-01"))
        self.assertFalse(is_expired(None))


class CorpusContractTest(unittest.TestCase):
    def test_confidential_is_ops_only(self):
        chunks = build_chunks(load_documents())
        conf = [c for c in chunks if c.classification == "confidential"]
        self.assertTrue(conf)
        for c in conf:
            self.assertIn("ops", c.acl)
            self.assertNotIn("engineer", c.acl)
            self.assertNotIn("intern", c.acl)

    def test_intern_can_read_onboarding_docs(self):
        chunks = build_chunks(load_documents())
        intern_ok = {c.doc_id for c in chunks if "intern" in c.acl}
        self.assertIn("colcon", intern_ok)
        self.assertIn("ros2-doc-actions", intern_ok)
        self.assertNotIn("prod-deploy", intern_ok)

    def test_public_docs_are_attributed(self):
        docs = load_documents()
        public = [m for m, _, p in docs if "public" in str(p).replace("\\", "/")]
        self.assertGreaterEqual(len(public), 10)
        for meta in public:
            self.assertEqual(meta.get("classification"), "public")
            self.assertEqual(meta.get("license"), "CC-BY-4.0")
            self.assertTrue(str(meta.get("upstream") or "").startswith("https://"))
            self.assertIn("intern", meta.get("acl") or [])

    def test_chunk_source_uses_subdir(self):
        chunks = build_chunks(load_documents())
        sources = {c.source.split("/")[0] for c in chunks}
        self.assertTrue({"internal", "public"} <= sources)

    def test_archive_expired(self):
        chunks = build_chunks(load_documents())
        old = [c for c in chunks if c.doc_id == "ros1-migration"]
        self.assertTrue(old)
        self.assertTrue(all(c.expired for c in old))


if __name__ == "__main__":
    unittest.main()
