"""Benchmark contracts: hold out connected incidents and never invent human review."""
from __future__ import annotations

import re
from pathlib import Path

from .data import digest, save_jsonl
from .graph import IncidentGraph

DEV_NEGATIVES = [
    "How long should I bake a sourdough loaf?", "What causes lunar eclipses?",
    "Find the winning goal in the football final", "Explain mitosis in plant cells",
    "Where should I book a hotel in Venice?", "What is the best fertilizer for tomatoes?",
    "Calculate a mortgage repayment for a house", "Who painted the Mona Lisa?",
]
TEST_NEGATIVES = [
    "What ingredients are used in a chocolate cake?", "How do whales migrate across oceans?",
    "What is the capital city of Peru?", "Suggest exercises for training a marathon",
    "How many moons does Jupiter have?", "Which trees grow in a tropical rainforest?",
]


def prepare(root: Path, docs: list[dict]) -> dict:
    import json
    split = IncidentGraph(docs).component_split()
    split_path = root / "data/splits.json"
    if split_path.exists():
        stored = json.loads(split_path.read_text())
        if stored["corpus_sha256"] != digest(docs):
            raise ValueError("Corpus changed after split creation; use a new experiment directory")
        split = stored["assignments"]
    else:
        split_path.write_text(json.dumps({"seed": 42, "corpus_sha256": digest(docs), "assignments": split}, indent=2))
    rows = []
    for doc in docs:
        title = doc["title"].strip()
        # Weak supervision uses known titles; it must be reported as automatic, not independent gold.
        cleaned = re.sub(r"[`\[\]]", "", title)
        for variant, query in enumerate(["Find a report about " + cleaned, "Which incident describes " + cleaned + "?"]):
            rows.append({"id": f"auto-{doc['id']}-{variant}", "query": query,
                         "relevant_ids": [doc["id"]], "split": split[doc["id"]],
                         "kind": "title_derived", "review_status": "automatic_silver",
                         "evidence_urls": [doc["url"]]})
    for subset, negatives in (("dev", DEV_NEGATIVES), ("test", TEST_NEGATIVES)):
        for i, text in enumerate(negatives):
            rows.append({"id": f"ood-{subset}-{i}", "query": text, "relevant_ids": [], "split": subset,
                         "kind": "out_of_domain", "review_status": "author_constructed"})
    save_jsonl(root / "data/queries.silver.jsonl", rows)
    return split


def validate_queries(queries: list[dict], docs: list[dict], split: dict) -> None:
    ids = {d["id"] for d in docs}
    seen = set()
    for q in queries:
        if q["id"] in seen:
            raise ValueError("Duplicate query ID")
        seen.add(q["id"])
        if not q["query"].strip():
            raise ValueError("Empty benchmark question")
        for relevant in q["relevant_ids"]:
            if relevant not in ids:
                raise ValueError(f"Unknown evidence {relevant}")
            if split[relevant] != q["split"]:
                raise ValueError(f"Incident leaked across splits: {relevant}")

