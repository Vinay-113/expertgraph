# Local verification — 2026-10-02

- 14 pytest tests passed; Python source compilation passed.
- 10 live API checks passed: health, retrieval, expert-weight normalization, source-backed excerpts, explicit-reference neighbours, abstention, invalid input rejection, cross-origin rejection and restricted file routes.
- Browser checks confirmed configuration retrieval, source excerpts, expandable paths and out-of-domain abstention. Browser warning/error log was empty at the final check.
- pip check reported no broken requirements.
- restore verified the existing 109-document frozen corpus hash.
- Evaluation rerun preserved positive retrieval metrics and selected router settings. Latencies vary per run; use results.json for the final observed values.
- MiniLM revision pinned to 1110a243fdf4706b3f48f1d95db1a4f5529b4d41.

The browser/server checks are local smoke tests, not production security, load or accessibility certification. No public repository or hosted deployment was created. Independent benchmark review remains pending.
