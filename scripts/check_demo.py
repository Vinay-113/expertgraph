"""Run against an already-started local demo: python scripts/check_demo.py."""
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8765"


def request(path, payload=None, origin=None):
    headers = {"Content-Type": "application/json"}
    if origin:
        headers["Origin"] = origin
    req = Request(BASE + path, data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
    try:
        with urlopen(req, timeout=20) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        return exc.code, json.load(exc)


def main():
    checks = 0
    status, health = request("/api/health")
    assert status == 200 and health["documents"] == 109
    checks += 1
    status, report = request("/api/query", {"query": "pytest config file extension causes FileNotFoundError"})
    assert status == 200 and report["evidence"] and abs(sum(report["expert_weights"].values()) - 1) < 1e-8
    assert all(e["url"].startswith("https://github.com/") and e["quote"] for e in report["evidence"])
    checks += 1
    status, report = request("/api/query", {"query": "psf/requests#7601 retry adapter linked reports"})
    assert status == 200 and any(e["id"] == "psf/requests#5842" for e in report["graph_neighbors"])
    checks += 1
    status, report = request("/api/query", {"query": "What ingredients are used in a chocolate cake?"})
    assert status == 200 and report["status"] == "abstained"
    checks += 1
    for payload in ({"query": ""}, {"query": 12}, {"query": "x" * 2001}, ["not an object"]):
        assert request("/api/query", payload)[0] == 400
        checks += 1
    assert request("/api/query", {"query": "pytest"}, "https://untrusted.example")[0] == 403
    checks += 1
    assert request("/../data/corpus.jsonl")[0] == 404
    checks += 1
    for method in ("bm25", "semantic", "graph", "fixed_hybrid", "bm25_semantic", "routed_hybrid"):
        status, report = request("/api/query", {"query": "pytest config FileNotFoundError", "method": method})
        assert status == 200 and report["method"] == method and report["evidence"]
        if method != "routed_hybrid":
            assert report["confidence"] is None and report["threshold"] is None
        checks += 1
    for query, kind in (("Find the HTTP error GALAXY_HTTP_5K82P", "absent_exact_identifier"),
                        ("Which exact commit broke my private CI?", "unavailable_context"),
                        ("Patch my production Requests proxy configuration now", "unsupported_action"),
                        ("Find psf/requests#99999999", "absent_issue_id")):
        status, report = request("/api/query", {"query": query})
        assert status == 200 and report["status"] == "abstained" and report["abstention_reason"] == "scope_guard"
        assert any(f["kind"] == kind for f in report["scope_checks"])
        checks += 1
    status, result = request("/api/validation")
    assert status == 200 and result["models_retrained"] is False and result["challenge"]["selective"]["queries"] == 36
    checks += 1
    for method in ("not_a_method", 123):
        assert request("/api/query", {"query": "pytest", "method": method})[0] == 400
        checks += 1
    with urlopen(BASE + "/app.js", timeout=10) as response:
        assert response.status == 200 and "script-src 'self';" in response.headers["Content-Security-Policy"]
        assert "unsafe-inline" not in response.headers["Content-Security-Policy"].split("script-src")[1].split(";")[0]
        checks += 1
    print(f"{checks} local API checks passed")


if __name__ == "__main__":
    main()
