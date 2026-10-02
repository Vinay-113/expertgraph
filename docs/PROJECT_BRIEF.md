# ExpertGraph — project brief

**In one sentence:** finds relevant software failure reports and shows their
connections with original sources you can check.

## Why build it?

Exact error messages favor lexical search; paraphrases can favor embeddings;
explicit cross-references can reveal related reports. Combining these signals
is useful only if measured against strong individual baselines.

## What is implemented?

- A scoped collector and hashed manifest for 109 public GitHub issue reports.
- BM25, pinned MiniLM embeddings and a provenance-preserving issue-reference graph.
- Equal-weight rank fusion, a learned ridge-based expert router and a no-graph ablation.
- A local explorer with source excerpts, graph paths and explicit scope abstention.
- Component-separated supervision, draft relevance labels, frozen-model stress tests
  and per-query failure analysis.

## What did the experiments teach?

BM25 leads the original 27-positive-question pilot (MRR 0.957). Semantic retrieval
leads the later 20-positive-question stress suite (MRR 0.848). The router does not
beat the strongest individual expert on either set. Sparse graph signals and
weak supervision are possible explanations, not established causes.

The stress suite also exposed high-score accepted errors. Transparent scope
rules now block specific absent identifiers and unsupported actions, but that
same-suite regression check is not independent safety validation.

## Research connections

The implementation demonstrates skills transferable to knowledge-graph retrieval,
expert selection, evidence-grounded decision support and inspectable memory.
It does not reproduce a host proposal or claim expertise in clinical reasoning,
telecom, robot control or macroeconomic modeling. No robotics hardware or
physics experiments are involved.

## Research status and ownership

Independent project by Vinay Patil, developed with AI-assisted implementation
and assistant-authored/source-checked benchmark questions. Independent human
review is pending. This is a working prototype with preliminary experiments,
not a publication, novel algorithm or production incident-response system.

Next priority: independent labels and a representative, untouched test set.
