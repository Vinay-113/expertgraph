"""Transparent evidence-scope checks, not a learned relevance classifier."""
import re

ISSUE_ID = r"[\w.-]+/[\w.-]+#\d+\b"
CODE_ID = r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b"


class CorpusScope:
    def __init__(self, docs):
        self.ids = {d["id"].casefold() for d in docs}
        text = "\n".join(d["title"] + "\n" + d["body"] for d in docs)
        self.codes = {t.casefold() for t in re.findall(CODE_ID, text)}

    def check(self, query):
        findings = []
        def add(kind, detail):
            findings.append({"kind": kind, "detail": detail})
        missing_ids = sorted({t for t in re.findall(ISSUE_ID, query) if t.casefold() not in self.ids})
        if missing_ids:
            add("absent_issue_id", "These exact incident IDs are absent from the local snapshot: " + ", ".join(missing_ids))
        missing_codes = sorted({t for t in re.findall(CODE_ID, query) if len(t) >= 10 and t.casefold() not in self.codes})
        if missing_codes:
            add("absent_exact_identifier", "No indexed report contains these exact code identifiers: " + ", ".join(missing_codes) + ". Related-looking reports do not verify them.")
        q = query.casefold()
        seeking_similar = bool(re.search(r"\b(?:similar|related|comparable)\b.*\b(?:report|issue|incident)s?\b|\b(?:public reports|reported examples)\b", q))
        missing_input = bool(re.search(r"\b(?:not uploaded|have not uploaded|haven't uploaded|not supplied|not provided)\b", q))
        private = bool(re.search(r"\b(?:private|internal|unpublished)\b", q))
        private_detail = private and bool(re.search(r"\b(?:exact|read|look inside|api token|secret|commit)\b", q))
        live = bool(re.search(r"\b(?:live|right now|current)\b", q)) and bool(re.search(r"\b(?:my|our|private|internal)\b", q)) and bool(re.search(r"\b(?:status|server|network|telemetry)\b", q))
        if not seeking_similar and (missing_input or private_detail or live):
            add("unavailable_context", "This static public corpus has no access to private logs, unpublished code, secrets or live telemetry. Similar reports cannot establish the requested facts.")
        action = re.search(r"^(?:please\s+)?(?:patch|deploy|modify|restart|fix|update)\s+(?:my|our|the production)\b", q)
        execute = re.search(r"^(?:please\s+)?run\b.*\b(?:my|our|private)\b", q)
        if action or execute:
            add("unsupported_action", "This explorer retrieves evidence only; it cannot execute tests, patch production or verify that a live incident is resolved.")
        return findings
