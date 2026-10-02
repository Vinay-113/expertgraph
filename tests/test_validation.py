import json
from pathlib import Path

import networkx as nx
import pytest

from expertgraph.data import load_jsonl
from expertgraph.evaluate import write_annotation_review
from expertgraph.retrieval import Engine, fuse
from expertgraph.scope import CorpusScope
from expertgraph.validation import clustered_mrr_interval, load_challenge, summarize
from test_integrity import doc

ROOT = Path(__file__).resolve().parents[1]


def test_zero_weight_expert_does_not_create_results():
    ranks = {"bm25": [], "semantic": [], "graph": [("noise", 1)]}
    assert fuse(ranks, [.5, .5, 0]) == []


@pytest.mark.parametrize("weights", [[1, 0], [1, -1, 1], [float("nan"), 0, 0]])
def test_invalid_fusion_weights_rejected(weights):
    with pytest.raises(ValueError):
        fuse({"bm25": [], "semantic": [], "graph": []}, weights)


def test_comparison_calibrator_is_not_applied_to_other_rankings():
    class ForbiddenCalibrator:
        def predict(self, *args):
            raise AssertionError("Wrong calibrator used")
    engine = Engine([doc(1, "SSL certificate failed")], None, semantic=False)
    result = engine.report("certificate", calibrator=ForbiddenCalibrator(), method="bm25")
    assert result["confidence"] is None
    assert result["threshold"] is None
    assert result["expert_weights"] == {"bm25": 1.0, "semantic": 0.0, "graph": 0.0}
    with pytest.raises(ValueError):
        engine.report("certificate", method="invented")


def test_scope_does_not_claim_unknown_exact_identifier_is_supported():
    scope = CorpusScope([doc(1, "PIP_REQUIRE_VIRTUALENV=true causes a missing virtualenv report")])
    assert scope.check("Find PIP_REQUIRE_VIRTUALENV reports") == []
    assert scope.check("Find ORBIT_INSTALL_8X41V reports")[0]["kind"] == "absent_exact_identifier"


def test_scope_allows_public_similarity_but_rejects_missing_private_facts():
    scope = CorpusScope([doc(1)])
    assert scope.check("Find similar public reports about my private CI pipeline failing") == []
    assert scope.check("Which exact commit caused my private CI pipeline to fail?")[0]["kind"] == "unavailable_context"
    assert scope.check("Read my log that I have not uploaded")[0]["kind"] == "unavailable_context"


def test_scope_rejects_actions_without_blocking_reports_about_actions():
    scope = CorpusScope([doc(1)])
    assert scope.check("Patch my production proxy now")[0]["kind"] == "unsupported_action"
    assert scope.check("Find a report about a proposed proxy patch") == []


def test_scope_overrides_high_raw_model_estimate_transparently():
    class Calibrator:
        threshold = .8
        def predict(self, *args):
            return .99
    engine = Engine([doc(1, "HTTP encoding proxy problem")], None, semantic=False)
    report = engine.report("Show COMET_ENCODING_6H24R HTTP error", calibrator=Calibrator())
    assert report["status"] == "abstained"
    assert report["confidence"] == .99
    assert report["abstention_reason"] == "scope_guard"
    assert not report["model_abstained"]


def test_exact_issue_id_has_no_prefix_match():
    engine = Engine([doc(1, "See #2"), doc(2)], None, semantic=False)
    result = engine.experts("psf/requests#1000")
    assert result["paths"] == {}
    assert engine.report("psf/requests#1000")["scope_checks"][0]["kind"] == "absent_issue_id"


def test_challenge_contract_and_all_supporting_anchors():
    corpus = ROOT / "data/corpus.jsonl"
    if not corpus.exists():
        pytest.skip("Local frozen corpus is not distributed with source")
    docs = load_jsonl(corpus)
    split = json.loads((ROOT / "data/splits.json").read_text())["assignments"]
    _, queries = load_challenge(ROOT, docs, split)
    assert len(queries) == 36
    assert sum(bool(q["relevant_ids"]) for q in queries) == 20


def test_bootstrap_uses_reference_components_and_is_deterministic():
    graph = nx.Graph([("a", "b")])
    graph.add_node("c")
    queries = [{"id": "q1", "relevant_ids": ["a", "b"]}, {"id": "q2", "relevant_ids": ["c"]}]
    rows = [{"query_id": q, "method": m, "metrics": {"mrr": value}}
            for q, a, b in (("q1", 1, .5), ("q2", .5, .5)) for m, value in (("left", a), ("right", b))]
    first = clustered_mrr_interval(rows, queries, graph, "left", "right", samples=100)
    assert first == clustered_mrr_interval(rows, queries, graph, "left", "right", samples=100)
    assert first["components"] == 2
    assert first["mrr_delta"] == .25
    assert first["lower_95"] <= .25 <= first["upper_95"]


def test_no_accepted_query_means_undefined_precision_not_zero():
    row = {"method": "routed_hybrid", "metrics": {}, "relevant_ids": [], "accepted": False, "confidence": .1}
    summary = summarize([row])
    assert summary["selective"]["accepted_top1_precision"] is None
    assert summary["selective"]["coverage"] == 0


def test_rerun_does_not_erase_user_annotations(tmp_path):
    path = tmp_path / "review.csv"
    path.write_text("reviewer,decision\nVinay,accept\n")
    previous = path.read_bytes()
    assert not write_annotation_review(path, [])
    assert path.read_bytes() == previous


def test_excerpt_skips_issue_template_comments_and_preserves_source():
    text = "<!-- Before opening a bug report please check the community report guidelines -->\n\nActual behavior: certificate validation failed with an SSLError in the connection."
    engine = Engine([doc(1, text)], None, semantic=False)
    quote = engine.report("bug report certificate SSLError", method="bm25")["evidence"][0]["quote"]
    assert quote.startswith("Actual behavior:")
    assert quote in text
