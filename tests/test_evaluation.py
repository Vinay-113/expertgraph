import numpy as np
import pytest
from expertgraph.evaluate import aggregate, retrieval_metrics
from expertgraph.retrieval import Engine
from expertgraph.routing import Calibrator, Router, features
from test_integrity import doc


def test_known_retrieval_metrics():
    m = retrieval_metrics([("x", 2), ("a", 1)], ["a", "b"])
    assert m["recall_at_5"] == .5
    assert m["precision_at_5"] == .2
    assert m["mrr"] == .5
    assert m["hit_at_1"] == 0
    assert m["ndcg_at_5"] == pytest.approx((1 / np.log2(3)) / (1 + 1 / np.log2(3)))


def test_empty_and_negative_metrics():
    assert retrieval_metrics([], ["a"])["mrr"] == 0
    assert retrieval_metrics([], ["a"])["recall_at_5"] == 0
    assert retrieval_metrics([("a", 1)], []) == {}


def test_query_validation_and_excerpt_provenance():
    engine = Engine([doc(1, "An SSLError occurred during certificate verification.")], None, semantic=False)
    for query in ("", "  ", "a" * 2001):
        with pytest.raises(ValueError):
            engine.report(query)
    report = engine.report("SSLError")
    assert report["evidence"][0]["quote"] in engine.docs[0]["body"]
    assert report["confidence"] is None
    assert report["evidence"][0]["evidence_status"] == "reporter_statement"


def test_router_probability_simplex_and_feature_shape():
    engine = Engine([doc(1, "SSL certificate failed"), doc(2, "pytest fixture failed")], None, semantic=False)
    queries = [{"query": "SSL certificate", "relevant_ids": ["psf/requests#1"]},
               {"query": "pytest fixture", "relevant_ids": ["psf/requests#2"]}]
    router = Router().fit(queries, engine)
    result = engine.experts("certificate")
    w = router.weights("certificate", result)
    assert len(features("certificate", result)) == 12
    assert sum(w) == pytest.approx(1)
    assert all(0 <= x <= 1 for x in w)


def test_single_class_calibration_is_unavailable_not_fabricated():
    engine = Engine([doc(1, "certificate failed")], None, semantic=False)
    queries = [{"query": "certificate", "relevant_ids": ["psf/requests#1"]}]
    router = Router().fit(queries, engine)
    calibrator = Calibrator().fit(queries, engine, router)
    assert not calibrator.available
    assert calibrator.predict("certificate", engine.experts("certificate"), []) is None


def test_graph_neighbours_visible_without_claiming_causality():
    engine = Engine([doc(1, "Retry adapter: see #2"), doc(2, "Retry behaviour report")], None, semantic=False)
    report = engine.report("psf/requests#1 adapter")
    assert any(e["id"] == "psf/requests#2" for e in report["graph_neighbors"])
    assert report["graph_neighbors"][0]["paths"][0]["relation"] == "explicit_reference"
