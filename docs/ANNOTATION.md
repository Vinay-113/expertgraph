# Benchmark review and release checklist

Do not relabel the draft human-validated because an assistant checked sources.

Open data/annotation_review.csv. For each question, read the original reports, accept/revise/reject the expected incidents, record your reviewer name and corrections, and look for additional relevant reports. Separate symptoms, allegations and proposed fixes; this corpus contains reporter statements, not maintainer comments.

Ask a second reviewer to label a blinded sample without seeing retrieval ranks. Record agreement and disagreements. Corrections after inspecting rankings are not a new untouched test set: version the benchmark and retain original outcomes. Do not repeatedly tune against this pilot and call it held-out.

Before application submission:

- Reproduce the tests and evaluation using the frozen corpus.
- Personally inspect at least ten source-backed examples, an explicit-reference path and abstention behavior.
- Understand the 12-feature ridge gate and why BM25 wins this pilot.
- Record a 90-second demonstration, including one source link and one path.
- Use implementation-based CV wording until independent evaluation is complete.

For a stronger follow-up, independently author queries before testing: terse logs, vague paraphrases, linked reports, hard in-domain unanswerable questions and absent-information cases. Use new incident components and frozen test labels. This is a research prototype, not published or production-validated work.
