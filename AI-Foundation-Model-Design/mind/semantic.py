"""
semantic  —  Vio's meaning layer (understand, don't just keyword-match).

The old retrieval matched the WORDS of a question against stored sentences. That is
why "I want to give you data to learn" pulled back machine-learning definitions: it
shares the words "data/learn", even though the *meaning* is completely different.

This module gives every sentence a dense vector that captures its MEANING, so Vio
retrieves by what a sentence is *about*, not which tokens it happens to contain.
"powered off" ≈ "shut down", "car" ≈ "vehicle", even with no shared words.

Two backends behind ONE interface, best-available wins — and it always runs locally:

  1. TRANSFORMER  (best).  A small sentence-transformer (all-MiniLM-L6-v2, ~90 MB,
     CPU-only). Real neural sentence embeddings. Enabled the moment the user runs
     `pip install sentence-transformers` — the model self-downloads once and caches.

  2. LSA  (always available, no download).  Latent Semantic Analysis: TruncatedSVD
     over the TF-IDF space folds together words that co-occur ("firewall"↔"traffic",
     "ram"↔"memory"), giving genuine — if lighter — semantic vectors from sklearn
     alone. This is what runs out of the box with zero new dependencies.

If neither can build (e.g. too few documents), `.ready` stays False and the caller
falls back to lexical TF-IDF, so Vio never breaks.
"""

from __future__ import annotations

import numpy as np


class SemanticIndex:
    """Encodes documents and queries into meaning-vectors and ranks by cosine.

    backend == "transformer"  → neural sentence embeddings (if the package is present)
    backend == "lsa"          → SVD-reduced TF-IDF (always works, no download)
    backend is None           → not ready; caller uses lexical retrieval instead
    """

    def __init__(self, dims=192, neural_only=False):
        self.dims = dims
        self.neural_only = neural_only   # if True, only the transformer backend counts
        self.backend = None
        self.ready = False
        self._model = None          # transformer model, when used
        self._svd = None            # (vectorizer, svd) for LSA, when used
        self.mat = None             # (n_docs, d) unit-normalised doc vectors
        self.docs = []

    # ---- build ----
    def fit(self, docs):
        self.docs = list(docs)
        if len(self.docs) < 3:
            self.ready = False
            return self
        if self._try_transformer():
            self.mat = self._encode_transformer(self.docs)
            self.backend, self.ready = "transformer", True
        elif not self.neural_only and self._try_lsa(self.docs):
            # LSA is genuine but coarse; on a small mixed corpus it conflates distant
            # topics, so callers that feed it into ranking ask for neural_only. The
            # standalone demo still uses it to illustrate meaning matching.
            self.mat = self._encode_lsa(self.docs)
            self.backend, self.ready = "lsa", True
        else:
            self.ready = False
        return self

    # ---- transformer backend ----
    def _try_transformer(self):
        try:
            from sentence_transformers import SentenceTransformer
        except Exception:
            return False
        try:
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            return True
        except BaseException:
            # package present but the model can't be fetched/loaded — fall back to LSA
            self._model = None
            return False

    def _encode_transformer(self, texts):
        v = self._model.encode(list(texts), normalize_embeddings=True,
                               convert_to_numpy=True, show_progress_bar=False)
        return np.asarray(v, dtype=np.float32)

    # ---- LSA backend (offline default) ----
    def _try_lsa(self, docs):
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.decomposition import TruncatedSVD
        except Exception:
            return False
        try:
            vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1)
            X = vec.fit_transform(docs)
            comps = int(max(2, min(self.dims, X.shape[1] - 1, X.shape[0] - 1)))
            if comps < 2:
                return False
            svd = TruncatedSVD(n_components=comps, random_state=0)
            svd.fit(X)
            self._svd = (vec, svd)
            return True
        except Exception:
            return False

    def _encode_lsa(self, texts):
        vec, svd = self._svd
        Z = svd.transform(vec.transform(list(texts))).astype(np.float32)
        n = np.linalg.norm(Z, axis=1, keepdims=True)
        n[n == 0] = 1.0
        return Z / n

    # ---- encode / search ----
    def encode(self, texts):
        if not self.ready:
            return None
        if self.backend == "transformer":
            return self._encode_transformer(texts)
        return self._encode_lsa(texts)

    def search(self, q, k=6):
        """Return [(doc, cosine_similarity)] most similar in MEANING to q."""
        if not self.ready or self.mat is None or not len(self.docs):
            return []
        qv = self.encode([q])
        if qv is None:
            return []
        sims = (self.mat @ qv[0])
        idx = np.argsort(-sims)[:k]
        return [(self.docs[i], float(sims[i])) for i in idx]


if __name__ == "__main__":
    docs = [
        "A firewall filters network traffic based on rules.",
        "Powering off a computer erases everything in RAM.",
        "Shutting down a computer closes all programs and cuts power.",
        "A neural network learns patterns from data.",
        "The Moon is Earth's only natural satellite.",
    ]
    si = SemanticIndex().fit(docs)
    print("backend:", si.backend, "ready:", si.ready)
    for q in ["what happens when you turn a computer off?", "block bad traffic"]:
        print("\nQ:", q)
        for d, s in si.search(q, k=3):
            print(f"  {s:.3f}  {d}")
