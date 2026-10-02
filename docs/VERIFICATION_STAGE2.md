# Next-stage verification — 2026-10-03

- 29 unit/integrity tests passed, including scope rules, comparison calibration isolation, zero-weight expert exclusion, all challenge source anchors, deterministic component-bootstrap resampling and preservation of user annotations.
- 24 loopback API checks passed for the restarted demo: original retrieval checks, six comparison methods, four scope cases, validation artifacts, invalid methods, restricted routes and external-script CSP.
- Source-tree launcher verified; it bypasses the macOS hidden editable-install .pth issue without changing the user's Python installation.
- Browser confirmed original example retrieval, semantic-only comparison with no inappropriate calibrated score, unknown-identifier abstention, unsupported-action abstention despite a raw 0.915 model estimate, and separate pilot/stress comparison panels. Final browser warning/error log was empty.
- Source compilation passed. JavaScript is served from a dedicated file under script-src 'self'; inline script execution is no longer allowed by the demo CSP.
- Original pilot results, source corpus, split, annotation worksheet and fitted model remained byte-identical. See artifacts/validation-v1/preservation.json for checksums.
- A frozen 36-query diagnostic suite was run with the existing model and unchanged threshold. Initial raw outcomes are separately retained. Scope rules were added after those outcomes and therefore checked as regressions, not independently validated on unseen data.
- Source excerpts now skip HTML issue-template comment paragraphs and prefer rare matching query terms while remaining contiguous excerpts from the original body.

No public deployment, repository publication or admissions submission occurred. There is still no independent human annotation, production security/load certification or evidence that the learned router generalizes better than its baselines.
