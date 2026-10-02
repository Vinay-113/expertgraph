"""Three retrieval experts and rank fusion, with inspectable evidence paths."""
from __future__ import annotations

import json
import math
import re
import time
from collections import Counter
from pathlib import Path

import numpy as np

from .data import digest, document_text, validate_documents
from .graph import IncidentGraph, entities
from .scope import CorpusScope, ISSUE_ID

EXPERTS = ("bm25", "semantic", "graph")
MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+(?:[.\-/][a-z0-9_]+)*", text.lower())


def ranking(scores: np.ndarray, ids: list[str]) -> list[tuple[str, float]]:
    return [(ids[i], float(scores[i])) for i in sorted(range(len(ids)), key=lambda i: (-scores[i], ids[i])) if scores[i] > 0]


class BM25:
    def __init__(self, texts: list[str]):
        self.counts = [Counter(tokens(text)) for text in texts]
        self.lengths = np.array([sum(count.values()) for count in self.counts])
        self.avg = max(float(self.lengths.mean()), 1)
        df = Counter(term for counts in self.counts for term in counts)
        self.idf = {term: math.log(1 + (len(texts) - count + .5) / (count + .5)) for term, count in df.items()}

    def scores(self, query: str) -> np.ndarray:
        result = np.zeros(len(self.counts))
        norm = 1.5 * (1 - .75 + .75 * self.lengths / self.avg)
        for term in set(tokens(query)):
            frequency = np.array([counts[term] for counts in self.counts], dtype=float)
            result += self.idf.get(term, 0) * frequency * 2.5 / (frequency + norm)
        return result


class Semantic:
    def __init__(self, docs: list[dict], cache: Path):
        from sentence_transformers import SentenceTransformer
        import torch
        torch.set_num_threads(4)
        cache.mkdir(parents=True, exist_ok=True)
        snapshots = cache / "model/models--sentence-transformers--all-MiniLM-L6-v2/snapshots"
        manifest = cache.parent / "results/results.json"
        revision = (json.loads(manifest.read_text()).get("model_revision") if manifest.exists() else None) or MODEL_REVISION
        local = snapshots.exists() and any(snapshots.iterdir())
        self.model = SentenceTransformer(MODEL, cache_folder=str(cache / "model"), device="cpu",
                                        trust_remote_code=False, local_files_only=local, revision=revision)
        self.revision = revision
        self.model.max_seq_length = 256
        self.cache = cache
        self.query_cache = {}
        # Always include title; chunk the body so long logs do not silently truncate the report.
        texts, self.doc_indices = [], []
        for i, doc in enumerate(docs):
            body = doc["body"][:24000]
            chunks = [body[j:j + 900] for j in range(0, max(len(body), 1), 750)]
            for chunk in chunks:
                texts.append(doc["title"] + "\n" + chunk)
                self.doc_indices.append(i)
        key = digest({"texts": texts, "model": MODEL, "revision": self.revision, "max_tokens": 256})
        path = cache / f"chunks-{key}.npy"
        if path.exists():
            self.embeddings = np.load(path, allow_pickle=False)
        else:
            self.embeddings = self.model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=True)
            np.save(path, self.embeddings)
        self.n = len(docs)

    def scores(self, query: str) -> np.ndarray:
        if query not in self.query_cache:
            self.query_cache[query] = self.model.encode([query], normalize_embeddings=True)[0]
        similarities = self.embeddings @ self.query_cache[query]
        result = np.full(self.n, -1.0)
        np.maximum.at(result, self.doc_indices, similarities)
        return np.maximum(result, 0)


def fuse(ranks: dict[str, list[tuple[str, float]]], weights: list[float], depth: int = 30, constant: int = 60) -> list[tuple[str, float]]:
    if len(weights) != len(EXPERTS) or any(not math.isfinite(float(w)) or w < 0 for w in weights):
        raise ValueError("Fusion needs three finite, non-negative weights")
    scores = Counter()
    for name, weight in zip(EXPERTS, weights):
        if weight == 0:
            continue
        for rank, (doc_id, _) in enumerate(ranks[name][:depth], 1):
            scores[doc_id] += float(weight) / (constant + rank)
    return sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))


class Engine:
    def __init__(self, docs: list[dict], cache: Path, semantic: bool = True):
        validate_documents(docs)
        self.docs = docs
        self.ids = [doc["id"] for doc in docs]
        self.by_id = {doc["id"]: doc for doc in docs}
        self.lexical = BM25([document_text(doc) for doc in docs])
        self.semantic = Semantic(docs, cache) if semantic else None
        self.graph = IncidentGraph(docs)
        self.scope = CorpusScope(docs)
        self.results_cache = {}

    def experts(self, query: str, use_cache: bool = True) -> dict:
        if use_cache and query in self.results_cache:
            return self.results_cache[query]
        ranks, timings = {}, {}
        start = time.perf_counter()
        lexical = self.lexical.scores(query)
        ranks["bm25"] = ranking(lexical, self.ids)
        timings["bm25"] = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        semantic = self.semantic.scores(query) if self.semantic else np.zeros(len(self.ids))
        ranks["semantic"] = ranking(semantic, self.ids)
        timings["semantic"] = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        # Graph expert is seeded by lexical retrieval and explicitly mentioned issue IDs.
        seeds = [(doc_id, 1 / (rank + 1)) for rank, (doc_id, _) in enumerate(ranks["bm25"][:3])]
        mentioned_ids = {ref.casefold() for ref in re.findall(ISSUE_ID, query)}
        for doc_id in self.ids:
            if doc_id.casefold() in mentioned_ids:
                seeds.insert(0, (doc_id, 2.0))
        path_scores = self.graph.paths(query, seeds)
        graph_scores = np.array([path_scores.get(doc_id, {}).get("score", 0) for doc_id in self.ids])
        ranks["graph"] = ranking(graph_scores, self.ids)
        timings["graph"] = (time.perf_counter() - start) * 1000 + timings["bm25"]
        result = {"ranks": ranks, "timings_ms": timings, "paths": path_scores, "raw_scores": [lexical.tolist(), semantic.tolist(), graph_scores.tolist()]}
        self.results_cache[query] = result
        return result

    def report(self, query: str, router=None, calibrator=None, k: int = 5, method: str = "routed_hybrid") -> dict:
        if method not in (*EXPERTS, "fixed_hybrid", "bm25_semantic", "routed_hybrid"):
            raise ValueError("Unknown retrieval method")
        if not isinstance(query, str) or not query.strip() or len(query) > 2000:
            raise ValueError("Query must contain 1-2000 characters")
        result = self.experts(query)
        if method in EXPERTS:
            weights = [float(name == method) for name in EXPERTS]
            ranked = result["ranks"][method]
        else:
            weights = [.5, .5, 0] if method == "bm25_semantic" else ([1 / 3] * 3 if method == "fixed_hybrid" or router is None else router.weights(query, result))
            ranked = fuse(result["ranks"], weights)
        confidence = calibrator.predict(query, result, ranked) if calibrator and method == "routed_hybrid" else None
        threshold = calibrator.threshold if calibrator and method == "routed_hybrid" else None
        scope_checks = self.scope.check(query)
        model_abstain = not ranked or (confidence is not None and confidence < threshold)
        abstain = model_abstain or bool(scope_checks)
        evidence = []
        query_tokens = set(tokens(query))
        def evidence_item(doc_id, score):
            doc = self.by_id[doc_id]
            paragraphs = [s.strip() for s in re.split(r"\n\s*\n", doc["body"])
                          if len(s.strip()) > 45 and not s.strip().startswith("<!--")]
            paragraphs.sort(key=lambda s: -sum(self.lexical.idf.get(t, 0) for t in query_tokens & set(tokens(s))))
            excerpt = (paragraphs[0] if paragraphs else doc["body"])[:1100]
            return {"id": doc_id, "title": doc["title"], "url": doc["url"], "score": score,
                             "quote": excerpt, "evidence_status": "reporter_statement",
                             "paths": result["paths"].get(doc_id, {}).get("paths", [])[:3]}
        evidence = [evidence_item(doc_id, score) for doc_id, score in ranked[:k]]
        # Reference neighbours remain inspectable even if fusion places them outside the top five.
        neighbours = [evidence_item(doc_id, score) for doc_id, score in result["ranks"]["graph"]
                      if any(p["relation"] == "explicit_reference" for p in result["paths"][doc_id]["paths"])][:3]
        return {"query": query, "method": method, "status": "abstained" if abstain else "evidence_found",
                "expert_weights": dict(zip(EXPERTS, [float(w) for w in weights])),
                "confidence": confidence, "confidence_scope": "Unvalidated routed-model relevance estimate, not a correctness probability or root-cause certainty" if method == "routed_hybrid" else "The routed-model calibrator does not apply to this comparison method",
                "warnings": ["All retrieved reports require source review; high model estimates can still rank the wrong report first."],
                "scope_checks": scope_checks, "model_abstained": model_abstain,
                "abstention_reason": "scope_guard" if scope_checks else ("low_model_estimate_or_no_results" if model_abstain else None),
                "threshold": threshold, "evidence": evidence, "graph_neighbors": neighbours,
                "summary": "Requested facts or actions exceed the available corpus; displayed reports are unendorsed candidates." if scope_checks else ("Insufficient retrieval confidence; inspect sources before drawing a conclusion." if abstain else "Candidate reports and source excerpts, not a validated answer. Causes and downstream impacts require source review."),
                "timings_ms": result["timings_ms"]}
