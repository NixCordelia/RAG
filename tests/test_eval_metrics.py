from __future__ import annotations

import unittest

from rag.evaluate import keypoint_coverage
from rag.synonyms import extra_queries


class KeypointTest(unittest.TestCase):
    def test_or_variants(self):
        self.assertEqual(keypoint_coverage("组件是 shared library", ["shared library|共享库"]), 1.0)
        self.assertEqual(keypoint_coverage("由容器加载的共享库", ["shared library|共享库"]), 1.0)
        self.assertEqual(keypoint_coverage("无关回答", ["shared library|共享库"]), 0.0)


class SynonymFileTest(unittest.TestCase):
    def test_qos_and_tf_are_thematic(self):
        self.assertTrue(extra_queries("通信质量用哪种可靠性"))
        self.assertTrue(any("TF" in e or "lookup" in e for e in extra_queries("坐标 lookup 失败")))


if __name__ == "__main__":
    unittest.main()
