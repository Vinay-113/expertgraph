"""Frozen split evaluation and research artifact generation."""
from __future__ import annotations

import csv
import json
import math
import platform
import time
from collections import Counter
from pathlib import Path

import joblib
import numpy as np

from .benchmark import TEST_NEGATIVES, prepare, validate_queries
from .data import digest, load_jsonl
from .retrieval import EXPERTS, MODEL, Engine, fuse
from .routing import Calibrator, FEATURE_NAMES, Router, reciprocal_rank

METHODS = (*EXPERTS, "fixed_hybrid", "routed_hybrid")


def write_annotation_review(path: Path, questions: list[dict]) -> bool:
    """Never overwrite a review worksheet that may contain user annotations."""
    if path.exists():
        return False
    with path.open("w") as fh:
        writer = csv.writer(fh)
        writer.writerow(["query_id", "query", "expected_incidents", "source_urls", "reviewer", "decision", "corrections"])
        for q in questions:
            writer.writerow([q["id"], q["query"], ";".join(q["relevant_ids"]), ";".join(q.get("evidence_urls", [])), "", "pending", ""])
    return True


def retrieval_metrics(ranked: list[tuple], relevant: list[str], k: int = 5) -> dict:
    if not relevant:
        return {}
    selected = [doc_id for doc_id, _ in ranked[:k]]
    hits = [int(doc_id in relevant) for doc_id in selected]
    ideal = sum(1 / math.log2(i + 2) for i in range(min(k, len(relevant))))
    return {"recall_at_5": len(set(selected) & set(relevant)) / len(set(relevant)),
            "precision_at_5": sum(hits) / k,
            "mrr": reciprocal_rank(ranked, relevant),
            "ndcg_at_5": sum(hit / math.log2(i + 2) for i, hit in enumerate(hits)) / ideal,
            "hit_at_1": int(bool(selected) and selected[0] in relevant)}


def load_pilot(root: Path, docs: list[dict], split: dict) -> list[dict]:
    spec = json.loads((root / "data/benchmark.draft.json").read_text())
    by_id = {doc["id"]: doc for doc in docs}
    questions = []
    for item in spec["questions"]:
        if not any(item["anchor"] in by_id[ref]["body"] for ref in item["relevant_ids"]):
            raise ValueError(f"Supporting excerpt missing for {item['id']}")
        item = {**item, "split": "test", "review_status": spec["status"],
                "evidence_urls": [by_id[ref]["url"] for ref in item["relevant_ids"]]}
        questions.append(item)
    for i, query in enumerate(TEST_NEGATIVES):
        questions.append({"id": f"pilot-ood-{i}", "query": query, "relevant_ids": [], "split": "test",
                          "kind": "out_of_domain", "review_status": "author_constructed"})
    validate_queries(questions, docs, split)
    return questions


def config_ranking(method: str, query: str, result: dict, router: Router) -> list[tuple]:
    if method in EXPERTS:
        return result["ranks"][method]
    return fuse(result["ranks"], [1 / 3] * 3 if method == "fixed_hybrid" else router.weights(query, result))


def score_queries(queries: list[dict], engine: Engine, router: Router, calibrator: Calibrator) -> list[dict]:
    rows = []
    for q in queries:
        result = engine.experts(q["query"])
        for method in METHODS:
            start = time.perf_counter()
            ranked = config_ranking(method, q["query"], result, router)
            overhead = (time.perf_counter() - start) * 1000
            # Graph reuses BM25 seeds; fusion methods execute all experts.
            latency = result["timings_ms"][method] if method in EXPERTS else (
                result["timings_ms"]["semantic"] + result["timings_ms"]["graph"] + overhead)
            metrics = retrieval_metrics(ranked, q["relevant_ids"])
            confidence = calibrator.predict(q["query"], result, ranked) if method == "routed_hybrid" else None
            rows.append({"query_id": q["id"], "query": q["query"], "kind": q["kind"], "method": method,
                         "relevant_ids": q["relevant_ids"], "retrieved_ids": [doc_id for doc_id, _ in ranked[:5]],
                         "metrics": metrics, "latency_ms": latency, "confidence": confidence,
                         "accepted": confidence is not None and confidence >= calibrator.threshold})
    return rows


def aggregate(rows: list[dict]) -> dict:
    results = {}
    for method in METHODS:
        subset = [row for row in rows if row["method"] == method and row["metrics"]]
        results[method] = {key: float(np.mean([r["metrics"][key] for r in subset])) for key in subset[0]["metrics"]} if subset else {}
        results[method]["median_latency_ms"] = float(np.median([r["latency_ms"] for r in rows if r["method"] == method]))
        results[method]["positive_queries"] = len(subset)
    routed = [r for r in rows if r["method"] == "routed_hybrid" and r["confidence"] is not None]
    if routed:
        truth = [r["metrics"].get("hit_at_1", 0) for r in routed]
        accepted = [r for r in routed if r["accepted"]]
        results["selective_retrieval"] = {
            "brier_score": float(np.mean([(r["confidence"] - y) ** 2 for r, y in zip(routed, truth)])),
            "coverage": len(accepted) / len(routed),
            "accepted_top1_precision": float(np.mean([r["metrics"].get("hit_at_1", 0) for r in accepted])) if accepted else None,
            "negative_queries": sum(not r["relevant_ids"] for r in routed),
            "negatives_abstained": sum(not r["accepted"] for r in routed if not r["relevant_ids"]),
            "threshold": .8,
        }
    return results


def run(root: Path) -> dict:
    docs = load_jsonl(root / "data/corpus.jsonl")
    split = prepare(root, docs)
    silver = load_jsonl(root / "data/queries.silver.jsonl")
    validate_queries(silver, docs, split)
    pilot = load_pilot(root, docs, split)
    engine = Engine(docs, root / "artifacts/cache")
    train = [q for q in silver if q["split"] == "train"]
    dev = [q for q in silver if q["split"] == "dev"]
    candidates = []
    for alpha in (1, 10, 100):
        router = Router(alpha=alpha).fit(train, engine)
        for temperature in (.15, .35, 1.0):
            router.temperature = temperature
            scores = []
            for q in dev:
                if q["relevant_ids"]:
                    result = engine.experts(q["query"])
                    scores.append(reciprocal_rank(fuse(result["ranks"], router.weights(q["query"], result)), q["relevant_ids"]))
            candidates.append({"alpha": alpha, "temperature": temperature, "dev_mrr": float(np.mean(scores))})
    selected = max(candidates, key=lambda c: (c["dev_mrr"], c["alpha"], c["temperature"]))
    router = Router(alpha=selected["alpha"], temperature=selected["temperature"]).fit(train, engine)
    calibrator = Calibrator().fit(dev, engine, router)
    best_expert = max(EXPERTS, key=lambda name: np.mean([
        reciprocal_rank(engine.experts(q["query"])["ranks"][name], q["relevant_ids"]) for q in dev if q["relevant_ids"]]))
    model_dir = root / "artifacts/models"
    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump({"router": router, "calibrator": calibrator, "corpus_sha256": digest(docs)}, model_dir / "routing.joblib")
    print("Router configuration fixed using development data:", selected, flush=True)
    # Test labels are accessed only after model selection and calibration are complete.
    pilot_rows = score_queries(pilot, engine, router, calibrator)
    silver_rows = score_queries([q for q in silver if q["split"] == "test"], engine, router, calibrator)
    results = {
        "project": "ExpertGraph", "experiment": "v0.1 pilot", "seed": 42,
        "annotation_status": "agent-source-checked; independent human review pending",
        "corpus": {"documents": len(docs), "sha256": digest(docs), "repositories": sorted({d["repo"] for d in docs}),
                   "reference_edges": engine.graph.reference_graph.number_of_edges(), "graph_nodes": engine.graph.graph.number_of_nodes(),
                   "split_counts": dict(Counter(split.values()))},
        "benchmark_sha256": digest(pilot), "router": {"selected": selected, "candidates": candidates, "features": FEATURE_NAMES},
        "model": MODEL, "model_revision": engine.semantic.revision, "best_single_expert_selected_on_dev": best_expert,
        "pilot": aggregate(pilot_rows), "silver_title_queries": aggregate(silver_rows),
        "by_query_type": {kind: aggregate([r for r in pilot_rows if r["kind"] == kind]) for kind in sorted({q["kind"] for q in pilot if q["relevant_ids"]})},
        "latency_scope": "First retrieval for each query in this process, document embeddings already indexed; timings include query encoding, graph seeding, and fusion. Excludes indexing, startup, and network.",
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "limitations": [
            "27 positive pilot questions and 6 obvious out-of-domain negatives; not a representative production benchmark.",
            "Pilot queries authored and source-checked by the coding assistant; no independent human or maintainer annotation.",
            "Training and calibration use automatic title-derived questions, making silver scores easier than real operator queries.",
            "Only one or two known relevant issues are labelled; other relevant reports may be counted as non-relevant.",
            "Graph expert depends on BM25 seeds. Graph-only is not independent lexical-free retrieval.",
            "Explicit references mean association, not causality. Shared entities are not dependency edges.",
            "Extractive evidence explorer has no generative LLM, root-cause validation, or answer-quality evaluation.",
            "Confidence estimates are preliminary relevance calibration under a small artificial benchmark, not deployment guarantees.",
        ],
    }
    output = root / "artifacts/results"
    output.mkdir(parents=True, exist_ok=True)
    (output / "results.json").write_text(json.dumps(results, indent=2))
    (output / "per_query.json").write_text(json.dumps(pilot_rows, indent=2))
    (output / "graph.json").write_text(json.dumps(engine.graph.export(), indent=2))
    (output / "corpus_manifest.json").write_text((root / "data/manifest.json").read_text())
    with (output / "metrics.csv").open("w") as fh:
        writer = csv.DictWriter(fh, fieldnames=["method", *next(iter(results["pilot"].values())).keys()])
        writer.writeheader()
        for method in METHODS:
            writer.writerow({"method": method, **results["pilot"][method]})
    write_annotation_review(root / "data/annotation_review.csv", pilot)
    write_report(root, results)
    plot_results(root, results)
    return results


def write_report(root: Path, results: dict) -> None:
    p = results["pilot"]
    lines = ["# ExpertGraph pilot research report", "", "## Question and scope", "",
             "Can a small query router combine lexical, semantic, and graph retrieval to improve incident evidence discovery?",
             "", f"Corpus: {results['corpus']['documents']} public issue reports across three repositories. "
             f"The graph contains {results['corpus']['reference_edges']} explicit issue-reference edges.",
             "", "## Data and experimental protocol", "",
             "BM25 uses the report title and body. MiniLM encodes overlapping body chunks with the title prepended. "
             "Graph retrieval traverses explicit reference edges up to two hops and adds entity-mention matches. "
             "Equal-weight reciprocal-rank fusion is the hybrid baseline. A standardized ridge regressor predicts each expert's reciprocal-rank utility; softmax converts predictions to fusion weights.",
             "", "Incident reference components are split into training, development, and test partitions. "
             "The entire corpus is available as the retrieval index, as in normal document retrieval; test relevance labels never fit the router. "
             "Development data selects ridge regularization and softmax temperature. Separate development outcomes fit a relevance calibrator. "
             "The test pilot contains 27 paraphrased or exact-error questions plus 6 out-of-domain negatives. These were source-checked by the assistant and still need independent human review.",
             "", "## Results", ""]
    for method in METHODS:
        m = p[method]
        lines.append(f"- {method}: recall@5 {m['recall_at_5']:.3f}, MRR {m['mrr']:.3f}, nDCG@5 {m['ndcg_at_5']:.3f}, median retrieval latency {m['median_latency_ms']:.1f} ms.")
    baseline = p[results["best_single_expert_selected_on_dev"]]
    delta = p["routed_hybrid"]["mrr"] - baseline["mrr"]
    lines += ["", f"The single expert selected on development data was {results['best_single_expert_selected_on_dev']}. "
              f"Routed fusion changed pilot MRR by {delta:+.3f} against that baseline. "
              "This is an exploratory result; no statistical superiority or production generalization is established.",
              "", "## What the demonstration establishes", "",
              "A working retrieval research system, evidence paths, a learned expert gate, separate relevance calibration, "
              "a routing ablation against fixed fusion, and a fully traceable pilot evaluation. It does not establish automated incident diagnosis or causal risk prediction.",
              "", "## Limitations", ""]
    lines += ["- " + limitation for limitation in results["limitations"]]
    lines += ["", "## Reproduce", "", "Run `expertgraph evaluate` from the project directory. "
              "Keep the frozen corpus and data/splits.json unchanged. results.json and per_query.json are the canonical measured artifacts.",
              "", "## Next research step", "", "Review annotation_review.csv, add hard in-domain negative queries and independently labelled relevance, "
              "then evaluate a new held-out set without tuning on this pilot. Expand graph coverage with documented maintainer comments and source-supported dependency edges."]
    (root / "artifacts/results/REPORT.md").write_text("\n".join(lines) + "\n")


def plot_results(root: Path, results: dict) -> None:
    import os
    config = root / "artifacts/cache/matplotlib"
    config.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(config))
    os.environ.setdefault("XDG_CACHE_HOME", str(root / "artifacts/cache/system"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    names = ["BM25", "Semantic", "Graph", "Fixed hybrid", "Routed hybrid"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.7))
    for ax, metric, title in zip(axes, ["recall_at_5", "mrr"], ["Evidence recall@5", "Mean reciprocal rank"]):
        values = [results["pilot"][name][metric] for name in METHODS]
        ax.bar(names, values, color=["#94a3b8"] * 4 + ["#2563eb"])
        ax.set_ylim(0, 1.08)
        ax.set_ylabel(title + " (0–1)")
        ax.set_xlabel("Retrieval configuration")
        ax.tick_params(axis="x", labelrotation=25)
        ax.set_title(title)
        for i, value in enumerate(values):
            ax.text(i, value + .02, f"{value:.3f}", ha="center", fontsize=9)
    fig.suptitle("ExpertGraph • 27 source-checked pilot questions", fontsize=14)
    fig.text(.5, .01, "Sources: public GitHub issues • small pilot • independent human annotation pending", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, .07, 1, .92))
    fig.savefig(root / "artifacts/results/retrieval_comparison.png", dpi=180)
    plt.close(fig)
