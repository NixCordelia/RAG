from __future__ import annotations

import math

import numpy as np


class BM25:
    """Okapi BM25 (k1=1.5, b=0.75) over an in-memory tokenized corpus."""

    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.n = len(docs)
        self.doc_len = np.array([len(d) or 1 for d in docs], dtype=np.float32)
        self.avgdl = float(self.doc_len.mean()) if self.n else 1.0
        df: dict[str, int] = {}
        self.tf: list[dict[str, int]] = []
        for d in docs:
            counts: dict[str, int] = {}
            for t in d:
                counts[t] = counts.get(t, 0) + 1
            self.tf.append(counts)
            for t in counts:
                df[t] = df.get(t, 0) + 1
        self.idf = {t: math.log((self.n - c + 0.5) / (c + 0.5) + 1.0) for t, c in df.items()}

    def scores(self, query: list[str]) -> np.ndarray:
        scores = np.zeros(self.n, dtype=np.float32)
        if not self.n:
            return scores
        for q in query:
            idf = self.idf.get(q)
            if idf is None:
                continue
            for i, tf in enumerate(self.tf):
                f = tf.get(q)
                if not f:
                    continue
                denom = f + self.k1 * (1 - self.b + self.b * self.doc_len[i] / self.avgdl)
                scores[i] += idf * f * (self.k1 + 1) / denom
        return scores
