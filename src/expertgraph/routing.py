"""Small supervised gate plus separately calibrated top-result relevance."""
from __future__ import annotations

import re
import numpy as np
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .graph import entities
from .retrieval import EXPERTS, tokens


FEATURE_NAMES = ["log_length", "identifier_fraction", "entity_count", "error_present", "relationship_query",
                 "bm25_top", "bm25_margin", "semantic_top", "semantic_margin", "graph_top", "graph_margin", "expert_top_agreement"]


def features(query: str, result: dict) -> np.ndarray:
    words = tokens(query)
    base = [np.log1p(len(words)), sum(any(c.isdigit() or c in "_.-/" for c in w) for w in words) / max(len(words), 1),
            len(entities(query)), bool(re.search(r"error|exception|failed", query, re.I)),
            bool(re.search(r"linked|related|reference|downstream|depend|connected", query, re.I))]
    for name in EXPERTS:
        scores = [score for _, score in result["ranks"][name][:2]] + [0, 0]
        base += [scores[0], scores[0] - scores[1]]
    tops = [rank[0][0] for rank in result["ranks"].values() if rank]
    base += [len(tops) - len(set(tops))]
    return np.asarray(base, dtype=float)


def reciprocal_rank(rank: list[tuple], relevant: list[str]) -> float:
    return next((1 / i for i, (doc_id, _) in enumerate(rank, 1) if doc_id in relevant), 0.0)


class Router:
    def __init__(self, alpha: float = 10.0, temperature: float = .25):
        self.model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
        self.temperature = temperature

    def fit(self, queries: list[dict], engine) -> Router:
        if not queries:
            raise ValueError("Router needs training queries")
        rows = [engine.experts(q["query"]) for q in queries]
        x = np.array([features(q["query"], r) for q, r in zip(queries, rows)])
        y = np.array([[reciprocal_rank(r["ranks"][name], q["relevant_ids"]) for name in EXPERTS] for q, r in zip(queries, rows)])
        self.model.fit(x, y)
        return self

    def weights(self, query: str, result: dict) -> list[float]:
        predicted = self.model.predict(features(query, result)[None, :])[0]
        logits = (predicted - np.max(predicted)) / self.temperature
        weights = np.exp(logits)
        return (weights / weights.sum()).tolist()


class Calibrator:
    def __init__(self):
        self.model = make_pipeline(StandardScaler(), LogisticRegression(C=.5, random_state=42, max_iter=1000))
        self.available = False
        self.threshold = .8

    def fit(self, queries: list[dict], engine, router) -> Calibrator:
        from .retrieval import fuse
        x, y = [], []
        for q in queries:
            result = engine.experts(q["query"])
            ranked = fuse(result["ranks"], router.weights(q["query"], result))
            x.append(features(q["query"], result))
            y.append(int(bool(ranked) and ranked[0][0] in q["relevant_ids"]))
        if len(set(y)) == 2:
            self.model.fit(x, y)
            self.available = True
        return self

    def predict(self, query: str, result: dict, ranked: list) -> float | None:
        if not self.available:
            return None
        if not ranked:
            return 0.0
        return float(self.model.predict_proba(features(query, result)[None, :])[0, 1])
