# ExpertGraph pilot research report

## Question and scope

Can a small query router combine lexical, semantic, and graph retrieval to improve incident evidence discovery?

Corpus: 109 public issue reports across three repositories. The graph contains 12 explicit issue-reference edges.

## Data and experimental protocol

BM25 uses the report title and body. MiniLM encodes overlapping body chunks with the title prepended. Graph retrieval traverses explicit reference edges up to two hops and adds entity-mention matches. Equal-weight reciprocal-rank fusion is the hybrid baseline. A standardized ridge regressor predicts each expert's reciprocal-rank utility; softmax converts predictions to fusion weights.

Incident reference components are split into training, development, and test partitions. The entire corpus is available as the retrieval index, as in normal document retrieval; test relevance labels never fit the router. Development data selects ridge regularization and softmax temperature. Separate development outcomes fit a relevance calibrator. The test pilot contains 27 paraphrased or exact-error questions plus 6 out-of-domain negatives. These were source-checked by the assistant and still need independent human review.

## Results

- bm25: recall@5 0.981, MRR 0.957, nDCG@5 0.955, median retrieval latency 0.3 ms.
- semantic: recall@5 0.963, MRR 0.927, nDCG@5 0.925, median retrieval latency 5.4 ms.
- graph: recall@5 0.537, MRR 0.372, nDCG@5 0.384, median retrieval latency 0.5 ms.
- fixed_hybrid: recall@5 0.944, MRR 0.839, nDCG@5 0.855, median retrieval latency 5.9 ms.
- routed_hybrid: recall@5 0.944, MRR 0.868, nDCG@5 0.876, median retrieval latency 6.2 ms.

The single expert selected on development data was bm25. Routed fusion changed pilot MRR by -0.089 against that baseline. This is an exploratory result; no statistical superiority or production generalization is established.

## What the demonstration establishes

A working retrieval research system, evidence paths, a learned expert gate, separate relevance calibration, a routing ablation against fixed fusion, and a fully traceable pilot evaluation. It does not establish automated incident diagnosis or causal risk prediction.

## Limitations

- 27 positive pilot questions and 6 obvious out-of-domain negatives; not a representative production benchmark.
- Pilot queries authored and source-checked by the coding assistant; no independent human or maintainer annotation.
- Training and calibration use automatic title-derived questions, making silver scores easier than real operator queries.
- Only one or two known relevant issues are labelled; other relevant reports may be counted as non-relevant.
- Graph expert depends on BM25 seeds. Graph-only is not independent lexical-free retrieval.
- Explicit references mean association, not causality. Shared entities are not dependency edges.
- Extractive evidence explorer has no generative LLM, root-cause validation, or answer-quality evaluation.
- Confidence estimates are preliminary relevance calibration under a small artificial benchmark, not deployment guarantees.

## Reproduce

Run `expertgraph evaluate` from the project directory. Keep the frozen corpus and data/splits.json unchanged. results.json and per_query.json are the canonical measured artifacts.

## Next research step

Review annotation_review.csv, add hard in-domain negative queries and independently labelled relevance, then evaluate a new held-out set without tuning on this pilot. Expand graph coverage with documented maintainer comments and source-supported dependency edges.
