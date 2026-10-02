import pytest
from expertgraph.data import references, validate_documents
from expertgraph.graph import IncidentGraph
from expertgraph.retrieval import BM25, fuse
from expertgraph.benchmark import validate_queries


def doc(n, body="", title="Python problem"):
    return dict(id=f"psf/requests#{n}", repo="psf/requests", number=n,
                url=f"https://github.com/psf/requests/issues/{n}", body=body, title=title, labels=[])


def test_code_numbers_are_not_reference_edges():
    assert references(doc(10, "```python\n#1 example\n```\nSee #20")) == {"psf/requests#20"}


def test_linked_components_cannot_leak():
    docs = [doc(1, "See #2"), doc(2), doc(3), doc(4), doc(5), doc(6)]
    graph = IncidentGraph(docs)
    split = graph.component_split()
    assert split["psf/requests#1"] == split["psf/requests#2"]
    assert graph.component_split() == split


def test_duplicate_and_mismatched_source_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        validate_documents([doc(1), doc(1)])
    wrong = doc(1)
    wrong["url"] = "https://example.com/"
    with pytest.raises(ValueError, match="Source URL"):
        validate_documents([wrong])


def test_graph_path_preserves_original_edge_source():
    graph = IncidentGraph([doc(1, "See #2"), doc(2)])
    results = graph.paths("related incident", [("psf/requests#1", 1)])
    path = results["psf/requests#2"]["paths"][0]
    assert path["sources"] == ["https://github.com/psf/requests/issues/1"]
    assert path["relation"] == "explicit_reference"


def test_duplicate_seeds_do_not_double_count_reference():
    graph = IncidentGraph([doc(1, "See #2"), doc(2)])
    single = graph.paths("related incident", [("psf/requests#1", 2)])
    duplicate = graph.paths("related incident", [("psf/requests#1", 2), ("psf/requests#1", 1)])
    assert single == duplicate


def test_bm25_exact_error_beats_unrelated_text():
    scores = BM25(["TLS SSLError certificate verify failed", "pytest collection fixtures missing"]).scores("SSLError")
    assert scores[0] > scores[1] == 0


def test_rrf_honors_weights_and_empty_expert():
    ranks = {"bm25": [("a", 4), ("b", 1)], "semantic": [("b", .9)], "graph": []}
    assert fuse(ranks, [1, 0, 0])[0][0] == "a"
    assert fuse(ranks, [0, 1, 0])[0][0] == "b"


def test_query_split_integrity():
    docs = [doc(1)]
    with pytest.raises(ValueError, match="leaked"):
        validate_queries([{"id": "q", "query": "why", "relevant_ids": ["psf/requests#1"], "split": "test"}], docs, {"psf/requests#1": "train"})
