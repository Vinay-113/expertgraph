"""Graph edges preserve the exact source that justifies the connection."""
from __future__ import annotations

import re
from collections import defaultdict
import networkx as nx

from .data import references

ENTITIES = {
    "python": r"\bpython\b", "windows": r"\bwindows\b", "linux": r"\b(?:linux|ubuntu)\b",
    "macos": r"\b(?:macos|mac os|darwin)\b", "ssl": r"\b(?:ssl|tls|certificate)\b",
    "proxy": r"\bprox(?:y|ies)\b", "cache": r"\bcach(?:e|ing)\b",
    "timeout": r"\b(?:timeout|timed out)\b", "dependency": r"\b(?:dependencies|dependency)\b",
    "pip": r"\bpip\b", "pytest": r"\bpytest\b", "authentication": r"\b(?:auth|authentication|credentials)\b",
    "encoding": r"\b(?:encoding|unicode|utf-?8)\b", "redirect": r"\bredirects?\b",
    "collection": r"\b(?:collection|collecting|collect)\b", "fixture": r"\bfixtures?\b",
    "ci": r"\b(?:ci|github actions|workflow)\b", "network": r"\b(?:network|connection|http|https)\b",
}


def entities(text: str) -> set[str]:
    found = {name for name, pattern in ENTITIES.items() if re.search(pattern, text, re.I)}
    # Identifiers keep exact errors and versions separate from broad topic hubs.
    found |= set(re.findall(r"\b[A-Z][A-Za-z]+(?:Error|Exception)\b", text))
    found |= {"python:" + v for v in re.findall(r"\b(?:[Pp]ython\s*|python-version[\s:'\"]+)(3\.\d{1,2})\b", text)}
    return found


class IncidentGraph:
    def __init__(self, docs: list[dict]):
        self.graph = nx.Graph()
        self.reference_graph = nx.Graph()
        self.by_id = {d["id"]: d for d in docs}
        self.entity_docs = defaultdict(set)
        for doc in docs:
            self.reference_graph.add_node(doc["id"])
            self.graph.add_node(doc["id"], kind="incident", url=doc["url"])
            for entity in entities(doc["title"] + "\n" + doc["body"]):
                node = "entity:" + entity
                self.graph.add_node(node, kind="entity")
                self.graph.add_edge(doc["id"], node, relation="mentions", source=doc["url"])
                self.entity_docs[entity].add(doc["id"])
            for ref in references(doc):
                if ref in self.by_id:
                    self.graph.add_edge(doc["id"], ref, relation="explicit_reference", source=doc["url"])
                    self.reference_graph.add_edge(doc["id"], ref)

    def component_split(self, seed: int = 42) -> dict[str, str]:
        import random
        groups = [sorted(c) for c in nx.connected_components(self.reference_graph)]
        random.Random(seed).shuffle(groups)
        assigned = {}
        # Splits are by explicit-reference components, never by query.
        targets = {"train": 0.5 * len(self.by_id), "dev": 0.25 * len(self.by_id), "test": 0.25 * len(self.by_id)}
        counts = {key: 0 for key in targets}
        for group in sorted(groups, key=len, reverse=True):
            split = min(counts, key=lambda k: counts[k] / max(targets[k], 1))
            counts[split] += len(group)
            assigned.update({key: split for key in group})
        return assigned

    def paths(self, query: str, seeds: list[tuple[str, float]], limit: int = 2) -> dict[str, dict]:
        scores: dict[str, dict] = {}
        query_entities = entities(query)
        for entity in sorted(query_entities):
            members = self.entity_docs.get(entity, set())
            specificity = 1.0 / max(len(members), 1) ** 0.5
            for doc_id in sorted(members):
                self._add(scores, doc_id, specificity, ["entity:" + entity, doc_id], "mentions")
        seed_strengths = {}
        for seed_id, strength in seeds:
            seed_strengths[seed_id] = max(seed_strengths.get(seed_id, 0), strength)
        for seed_id, strength in seed_strengths.items():
            if seed_id not in self.reference_graph:
                continue
            for target, path in nx.single_source_shortest_path(self.reference_graph, seed_id, cutoff=limit).items():
                if target != seed_id:
                    self._add(scores, target, strength / len(path), path, "explicit_reference")
        return scores

    def _add(self, scores: dict, doc_id: str, score: float, path: list[str], relation: str) -> None:
        item = scores.setdefault(doc_id, {"score": 0.0, "paths": []})
        item["score"] += score
        evidence = [self.graph.edges[a, b]["source"] for a, b in zip(path, path[1:])]
        item["paths"].append({"nodes": path, "relation": relation, "sources": evidence})

    def export(self) -> dict:
        return nx.node_link_data(self.graph, edges="edges")
