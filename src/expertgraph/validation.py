"""Post-pilot diagnostics using frozen models; never train on these outcomes."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx
import numpy as np

from .benchmark import validate_queries
from .data import digest
from .evaluate import load_pilot, retrieval_metrics
from .retrieval import EXPERTS, fuse
from .server import load_system

METHODS = (*EXPERTS, "fixed_hybrid", "bm25_semantic", "routed_hybrid")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_challenge(root: Path, docs: list[dict], split: dict) -> tuple[dict, list[dict]]:
    spec = json.loads((root / "data/benchmark.challenge.v1.json").read_text())
    by_id = {d["id"]: d for d in docs}
    corpus_text = "\n".join(d["title"] + "\n" + d["body"] for d in docs).casefold()
    queries = []
    for q in spec["questions"]:
        q = {**q, "split": "test", "review_status": spec["status"]}
        if q["relevant_ids"]:
            if set(q.get("anchors", {})) != set(q["relevant_ids"]):
                raise ValueError(f"Each relevant source needs an anchor: {q['id']}")
            for ref, anchor in q["anchors"].items():
                if ref not in by_id or anchor not in by_id[ref]["body"]:
                    raise ValueError(f"Supporting source anchor missing: {q['id']} / {ref}")
        elif not q.get("reason"):
            raise ValueError(f"Negative label needs a rationale: {q['id']}")
        if q.get("absent_marker") and q["absent_marker"].casefold() in corpus_text:
            raise ValueError(f"Supposedly absent marker occurs in corpus: {q['id']}")
        queries.append(q)
    validate_queries(queries, docs, split)
    return spec, queries


def rank_method(method: str, query: str, result: dict, router) -> list[tuple]:
    if method in EXPERTS:
        return result["ranks"][method]
    if method == "fixed_hybrid":
        weights = [1 / 3] * 3
    elif method == "bm25_semantic":
        weights = [.5, .5, 0]
    elif method == "routed_hybrid":
        weights = router.weights(query, result)
    else:
        raise ValueError("Unknown comparison method")
    return fuse(result["ranks"], weights)


def score(queries, engine, router, calibrator):
    rows = []
    for q in queries:
        result = engine.experts(q["query"])
        for method in METHODS:
            ranked = rank_method(method, q["query"], result, router)
            confidence = calibrator.predict(q["query"], result, ranked) if method == "routed_hybrid" else None
            rows.append({"query_id": q["id"], "query": q["query"], "kind": q["kind"], "method": method,
                         "relevant_ids": q["relevant_ids"], "retrieved_ids": [d for d, _ in ranked[:5]],
                         "metrics": retrieval_metrics(ranked, q["relevant_ids"]), "confidence": confidence,
                         "accepted": confidence is not None and confidence >= calibrator.threshold})
    return rows


def summarize(rows):
    summary = {}
    for method in METHODS:
        positive = [r for r in rows if r["method"] == method and r["metrics"]]
        summary[method] = {k: float(np.mean([r["metrics"][k] for r in positive])) for k in positive[0]["metrics"]} if positive else {}
        summary[method]["positive_queries"] = len(positive)
    routed = [r for r in rows if r["method"] == "routed_hybrid"]
    accepted = [r for r in routed if r["accepted"]]
    negatives = [r for r in routed if not r["relevant_ids"]]
    available = [r for r in routed if r["confidence"] is not None]
    summary["selective"] = {
        "queries": len(routed), "coverage": len(accepted) / len(routed) if routed else None,
        "accepted_top1_precision": float(np.mean([r["metrics"].get("hit_at_1", 0) for r in accepted])) if accepted else None,
        "accepted_labelled_errors": sum(not r["metrics"].get("hit_at_1", 0) for r in accepted),
        "negative_queries": len(negatives), "negatives_accepted": sum(r["accepted"] for r in negatives),
        "brier_score": float(np.mean([(r["confidence"] - r["metrics"].get("hit_at_1", 0)) ** 2 for r in available])) if available else None,
        "threshold": .8,
        "confidence_scope": "Raw frozen-model estimates; not correctness guarantees or policy-guard scores",
    }
    return summary


def clustered_mrr_interval(rows, queries, reference_graph, left, right, samples=2000):
    """Exploratory paired resampling of explicit-reference components."""
    component = {doc_id: min(group) for group in nx.connected_components(reference_graph) for doc_id in group}
    lookup = {(r["query_id"], r["method"]): r for r in rows}
    groups = defaultdict(list)
    for q in queries:
        if q["relevant_ids"]:
            keys = {component[d] for d in q["relevant_ids"]}
            if len(keys) != 1:
                raise ValueError("A positive query spans reference components")
            groups[next(iter(keys))].append(lookup[(q["id"], left)]["metrics"]["mrr"] - lookup[(q["id"], right)]["metrics"]["mrr"])
    arrays = [np.asarray(groups[k]) for k in sorted(groups)]
    if not arrays:
        return None
    rng = np.random.default_rng(42)
    draws = [float(np.concatenate([arrays[i] for i in rng.integers(0, len(arrays), len(arrays))]).mean()) for _ in range(samples)]
    low, high = np.quantile(draws, [.025, .975])
    return {"left": left, "right": right, "mrr_delta": float(np.concatenate(arrays).mean()),
            "lower_95": float(low), "upper_95": float(high), "components": len(arrays), "resamples": samples,
            "scope": "Exploratory component bootstrap on incomplete assistant-authored labels; not a generalization guarantee"}


def run(root: Path):
    protected = [p for folder in ("artifacts/results", "artifacts/models") for p in (root / folder).rglob("*") if p.is_file()]
    protected += [root / "data" / name for name in ("corpus.jsonl", "manifest.json", "splits.json", "benchmark.draft.json", "annotation_review.csv")]
    before = {str(p.relative_to(root)): file_hash(p) for p in protected}
    engine, router, calibrator = load_system(root)
    split = json.loads((root / "data/splits.json").read_text())["assignments"]
    spec, challenge = load_challenge(root, engine.docs, split)
    output = root / "artifacts/validation-v1"
    output.mkdir(parents=True, exist_ok=True)
    identity = {"benchmark_sha256": digest(spec), "corpus_sha256": digest(engine.docs),
                "model_sha256": file_hash(root / "artifacts/models/routing.joblib")}
    frozen = output / "protocol.json"
    if frozen.exists() and json.loads(frozen.read_text()) != identity:
        raise ValueError("Validation inputs changed; create a new experiment version instead of overwriting it")
    frozen.write_text(json.dumps(identity, indent=2))
    print("Stress-suite inputs frozen; no fitting or threshold selection.", flush=True)
    original = load_pilot(root, engine.docs, split)
    pilot_rows = score(original, engine, router, calibrator)
    challenge_rows = score(challenge, engine, router, calibrator)
    routed_rows = {r["query_id"]: r for r in challenge_rows if r["method"] == "routed_hybrid"}
    policy_rows = [{"query_id": q["id"], "kind": q["kind"], "relevant_ids": q["relevant_ids"],
                    "raw_model_accepted": routed_rows[q["id"]]["accepted"], "scope_checks": engine.scope.check(q["query"]),
                    "accepted_with_scope_guard": routed_rows[q["id"]]["accepted"] and not engine.scope.check(q["query"])} for q in challenge]
    policy_summary = {"scope": "Post-observation regression check of explicit corpus-scope rules, not independent guard validation",
                      "negative_queries": sum(not r["relevant_ids"] for r in policy_rows),
                      "negatives_accepted_raw": sum(r["raw_model_accepted"] for r in policy_rows if not r["relevant_ids"]),
                      "negatives_accepted_with_guard": sum(r["accepted_with_scope_guard"] for r in policy_rows if not r["relevant_ids"]),
                      "positive_queries_blocked_by_guard": sum(bool(r["scope_checks"]) for r in policy_rows if r["relevant_ids"])}
    pairs = [("routed_hybrid", "fixed_hybrid"), ("routed_hybrid", "bm25"), ("bm25_semantic", "fixed_hybrid")]
    results = {"experiment": "Post-pilot diagnostic validation v1", **identity, "annotation_status": spec["status"],
               "protocol": spec["protocol"], "model_revision": engine.semantic.revision,
               "models_retrained": False, "threshold_changed": False, "methods": list(METHODS),
               "query_counts": dict(Counter(q["kind"] for q in challenge)),
               "scope_guard_regression": policy_summary,
               "original_pilot_extended_comparison": summarize(pilot_rows), "challenge": summarize(challenge_rows),
               "by_query_type": {kind: summarize([r for r in challenge_rows if r["kind"] == kind]) for kind in sorted({q["kind"] for q in challenge})},
               "exploratory_intervals": {name: [clustered_mrr_interval(rows, qs, engine.graph.reference_graph, a, b) for a, b in pairs]
                    for name, rows, qs in (("original_pilot", pilot_rows, original), ("challenge", challenge_rows, challenge))},
               "limitations": ["Diagnostic queries reuse original test incident components; not new incident generalization.",
                               "Questions and negative rationales are assistant-authored; independent human review pending.",
                               "Labels are incomplete and the missing-identifier query distribution is synthetic.",
                               "Bootstrap intervals cover only this query/component sample, not annotation bias.",
                               "Sixth-method ablation was added after seeing pilot results and is explicitly exploratory."]}
    (output / "results.json").write_text(json.dumps(results, indent=2))
    (output / "per_query.json").write_text(json.dumps(challenge_rows, indent=2))
    (output / "original_pilot_extended.json").write_text(json.dumps(pilot_rows, indent=2))
    (output / "scope_guard_regression.json").write_text(json.dumps(policy_rows, indent=2))
    annotation = output / "annotation_review.csv"
    if not annotation.exists():
        with annotation.open("w") as fh:
            writer = csv.writer(fh)
            writer.writerow(["query_id", "query", "expected_incidents", "source_urls", "negative_rationale", "reviewer", "decision", "corrections"])
            for q in challenge:
                writer.writerow([q["id"], q["query"], ";".join(q["relevant_ids"]),
                                 ";".join(engine.by_id[d]["url"] for d in q["relevant_ids"]), q.get("reason", ""), "", "pending", ""])
    after = {str(p.relative_to(root)): file_hash(p) for p in protected}
    if before != after:
        raise RuntimeError("A protected pilot/model artifact changed during validation")
    (output / "preservation.json").write_text(json.dumps({"unchanged": True, "protected_sha256": before}, indent=2))
    write_report(output, results, challenge_rows)
    return results


def write_report(output, results, rows):
    lines = ["# ExpertGraph: next-stage diagnostic validation", "", "## Protocol", "", results["protocol"],
             "", "The original pilot artifacts and fitted model remain byte-identical. No model retraining or threshold change was performed.",
             "", "## Six-method comparison", ""]
    for section in ("original_pilot_extended_comparison", "challenge"):
        lines += ["### " + section.replace("_", " "), ""]
        for method in METHODS:
            m = results[section][method]
            lines.append(f"- {method}: recall@5 {m['recall_at_5']:.3f}; MRR {m['mrr']:.3f}; nDCG@5 {m['ndcg_at_5']:.3f}.")
        s = results[section]["selective"]
        precision = f"{s['accepted_top1_precision']:.3f}" if s["accepted_top1_precision"] is not None else "undefined"
        lines += ["", f"Raw frozen routed-model coverage: {s['coverage']:.3f}; accepted top1 precision against draft labels: {precision}; accepted labelled errors: {s['accepted_labelled_errors']}; accepted negatives: {s['negatives_accepted']}/{s['negative_queries']}.", ""]
    lines += ["## Exploratory uncertainty", ""]
    for suite, intervals in results["exploratory_intervals"].items():
        for item in intervals:
            lines.append(f"- {suite}: {item['left']} minus {item['right']} MRR {item['mrr_delta']:+.3f}, component-bootstrap 95% interval [{item['lower_95']:+.3f}, {item['upper_95']:+.3f}], {item['components']} components.")
    lines += ["", "These intervals are exploratory, not proof of superiority. They do not address incomplete relevance labels or assistant-authored query bias.", "", "## Accepted labelled failures to inspect", ""]
    for row in rows:
        if row["method"] == "routed_hybrid" and row["accepted"] and not row["metrics"].get("hit_at_1", 0):
            lines.append(f"- {row['query_id']}: {row['query']} Top result: {row['retrieved_ids'][0]}; raw model estimate {row['confidence']:.3f}; expected: {', '.join(row['relevant_ids']) or 'no supported result'}.")
    policy = results["scope_guard_regression"]
    lines += ["", "## Scope-guard regression check", "",
              f"On the same diagnostic suite, accepted negatives changed from {policy['negatives_accepted_raw']} to {policy['negatives_accepted_with_guard']}/{policy['negative_queries']}; {policy['positive_queries_blocked_by_guard']} positive queries were blocked by scope rules.",
              "Rules were added after inspecting this suite. This is a regression check, not independent validation or a claim that all unknown queries are detected. Raw model scores and the 0.8 threshold are unchanged. See results.raw.json and per_query.raw.json for the first stress run.",
              "", "Some labelled mismatches may be genuinely relevant unlabelled reports; see SOURCE_REVIEW.md before interpreting the draft precision as true accuracy."]
    lines += ["", "## Limitations", ""] + ["- " + x for x in results["limitations"]]
    lines += ["", "## Reproduce and review", "", "Run `.venv/bin/python run_expertgraph.py validate` from the project root. Review annotation_review.csv; no scores establish clinical, robot, telecom or causal diagnosis competence."]
    (output / "REPORT.md").write_text("\n".join(lines) + "\n")
