# Repository packaging checks — 3 October 2026

The repository is isolated in `expertgraph/`; no unrelated Playground projects
are included. This document records local checks, not a remote CI success.

- Existing author installation: 29 tests passed.
- Full local explorer: 24 API smoke checks passed.
- Recorded-demo contract: 36 saved responses, source identities and embedded
  result hashes verified against the unchanged measured artifacts.
- Browser: all six methods exercised for all six examples; after the final
  graph-example refinement, its explicit source-backed edge was rechecked.
- Graph walkthrough: `psf/requests#7601 → psf/requests#5842`, with the source
  supporting the reference visible in the page.
- Unsupported execution and absent exact identifier: scope abstention shown.
- Method switching: the routed calibrator is not applied to individual experts.
- Browser warning/error logs: none observed.
- Original and public-demo JavaScript: syntax checks passed.
- Replay script: refuses an existing output directory before writing anything.
- Ignore rules exclude raw corpus, API cache, virtual environments, models,
  secret files and local replay directories.

The recorded page is not live model execution. Its example outputs and the
preliminary metrics are independently unvalidated. Source-only CI intentionally
skips the corpus-dependent test; model replay is not a CI claim.
