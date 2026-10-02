"""Public issue collection and strict data contracts."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPOS = ("actions/setup-python", "pytest-dev/pytest", "psf/requests")


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def load_jsonl(path: str | Path) -> list[dict]:
    with Path(path).open() as fh:
        return [json.loads(line) for line in fh if line.strip()]


def save_jsonl(path: str | Path, rows: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))


def validate_documents(docs: list[dict]) -> None:
    seen = set()
    for doc in docs:
        for key in ("id", "title", "body", "url", "repo", "number", "labels"):
            if key not in doc:
                raise ValueError(f"Missing {key} in document")
        if doc["id"] in seen:
            raise ValueError(f"Duplicate incident {doc['id']}")
        if doc["id"] != f"{doc['repo']}#{doc['number']}":
            raise ValueError("Invalid incident ID")
        if doc["url"] != f"https://github.com/{doc['repo']}/issues/{doc['number']}":
            raise ValueError("Source URL must match the incident identity")
        seen.add(doc["id"])


class GitHubCollector:
    """Fetch only unauthenticated, public GitHub REST data; never execute its text."""

    def __init__(self, root: Path):
        self.raw = root / "data/raw"
        self.raw.mkdir(parents=True, exist_ok=True)
        self.calls = 0

    def get(self, route: str) -> dict:
        cache = self.raw / (hashlib.sha256(route.encode()).hexdigest() + ".json")
        if cache.exists():
            return json.loads(cache.read_text())
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "ExpertGraph-research/0.1"}
        token = os.getenv("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request("https://api.github.com" + route, headers=headers)
        for attempt in range(3):
            try:
                with urlopen(request, timeout=45) as response:
                    data = json.load(response)
                cache.write_text(json.dumps(data, ensure_ascii=False))
                self.calls += 1
                return data
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        raise RuntimeError("Unreachable")

    def collect(self, per_repo: int = 40) -> list[dict]:
        if (self.raw.parent / "splits.json").exists():
            raise ValueError("This experiment is frozen. Collect into a new project root instead of overwriting it.")
        if not 1 <= per_repo <= 100:
            raise ValueError("per_repo must be in [1, 100]")
        all_docs = {}
        queries = []
        for repo in REPOS:
            q = f"repo:{repo} is:issue is:closed -label:question -label:documentation"
            route = "/search/issues?" + urlencode({"q": q, "sort": "created", "order": "desc", "per_page": per_repo})
            queries.append(q)
            items = self.get(route)["items"]
            for item in items:
                if item.get("body") and "pull_request" not in item and usable_issue(item):
                    doc = normalize_issue(item, repo)
                    all_docs[doc["id"]] = doc
            # Search API is limited; avoid a burst against its public endpoint.
            time.sleep(2)
        # Resolve a small number of explicitly referenced issues for real graph paths.
        pending = sorted({ref for d in all_docs.values() for ref in references(d) if ref not in all_docs})[:15]
        for ref in pending:
            repo, number = ref.rsplit("#", 1)
            try:
                item = self.get(f"/repos/{repo}/issues/{number}")
                if "pull_request" not in item and item.get("body"):
                    all_docs[ref] = normalize_issue(item, repo)
            except Exception as exc:
                print(f"Skipped public reference {ref}: {type(exc).__name__}", flush=True)
        docs = sorted(all_docs.values(), key=lambda d: d["id"])
        validate_documents(docs)
        save_jsonl(self.raw.parent / "corpus.jsonl", docs)
        manifest = {
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "sources": list(REPOS), "queries": queries, "documents": len(docs),
            "corpus_sha256": digest(docs), "network_requests": self.calls,
            "incident_ids": sorted(all_docs),
            "scope": "Public issue titles/bodies/labels only; no account profiling or private run logs",
            "rights": "Source text retains original authorship. Raw corpus is excluded from Git. Regenerate via collector.",
            "limitations": "Closed issues are incident reports, not expert-confirmed root causes; no maintainer comments fetched.",
        }
        (self.raw.parent / "manifest.json").write_text(json.dumps(manifest, indent=2))
        return docs

    def restore(self, manifest_path: Path) -> list[dict]:
        """Fetch the exact public incident IDs, refusing changed source snapshots."""
        manifest = json.loads(manifest_path.read_text())
        target = self.raw.parent / "corpus.jsonl"
        if target.exists():
            docs = load_jsonl(target)
            if digest(docs) != manifest["corpus_sha256"]:
                raise ValueError("Existing corpus differs from the frozen manifest; use a new directory")
            return docs
        docs = []
        for ref in manifest["incident_ids"]:
            repo, number = ref.rsplit("#", 1)
            if repo not in REPOS or not number.isdigit():
                raise ValueError("Manifest contains an out-of-scope incident")
            docs.append(normalize_issue(self.get(f"/repos/{repo}/issues/{number}"), repo))
        docs.sort(key=lambda d: d["id"])
        validate_documents(docs)
        if digest(docs) != manifest["corpus_sha256"]:
            raise ValueError("Public issues changed since collection. Exact replay requires the original local snapshot; do not reuse old metrics.")
        save_jsonl(target, docs)
        (self.raw.parent / "manifest.json").write_text(json.dumps(manifest, indent=2))
        return docs


def normalize_issue(item: dict, repo: str) -> dict:
    return {
        "id": f"{repo}#{item['number']}", "repo": repo, "number": int(item["number"]),
        "url": item["html_url"], "title": item["title"], "body": item.get("body") or "",
        "labels": sorted(label["name"] for label in item.get("labels", [])),
        "created_at": item["created_at"], "updated_at": item["updated_at"],
        "source_type": "github_issue", "evidence_status": "reporter_statement",
    }


def references(doc: dict) -> set[str]:
    refs = set()
    # Numbered examples inside code blocks are not issue references.
    body = re.sub(r"```.*?```", "", doc["body"], flags=re.S)
    for repo, number in re.findall(r"https://github\.com/([\w.-]+/[\w.-]+)/issues/(\d+)", body):
        if repo in REPOS:
            refs.add(f"{repo}#{number}")
    for number in re.findall(r"(?:issue|fixes|closes|related to|see|regression from|duplicate of|from|following|in|by)\s+#(\d{1,7})\b", body + "\n" + doc["title"], re.I):
        refs.add(f"{doc['repo']}#{number}")
    return refs - {doc["id"]}


def usable_issue(item: dict) -> bool:
    title = item["title"].strip().lower()
    return len(item.get("body") or "") >= 80 and not re.search(
        r"^<spam>|^\[docs\]|^docs |^test issue$|^tok perm|^\.$|^eduardo$|"
        r"^code review submission|^embed agent-friendly|^wafid\.com|^clarify contributor|"
        r"^introduce --receptor|^endorse |^add async test fixture|^link to commit diffs", title
    )


def document_text(doc: dict) -> str:
    return doc["title"] + "\n" + doc["body"][:24000]
