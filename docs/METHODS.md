# ExpertGraph: methods

## Task and data

Retrieve public software reports supporting a failure query and preserve evidence behind their connections. Output is investigative context, not verified diagnosis. The corpus contains 109 reports, obtained through GitHub REST search and explicit-reference lookups. Titles, bodies, labels, URLs and timestamps are preserved; comments are not collected. Closed status is not proof of a correct diagnosis. Selected spam/documentation titles are filtered, but the filter is not a comprehensive incident classifier.

Corpus SHA256, incident IDs, model snapshot revision and benchmark hash are recorded. Explicit-reference connected components are split with seed 42. Shared Python or Windows mentions are not split components, since these broad hubs would collapse most of the corpus. Unlinked duplicates can still leak related information: the split mitigates one leakage source rather than proving its absence.

## Experts

1. BM25: identifier-aware tokens, k1=1.5, b=0.75; title plus first 24,000 body characters.
2. Semantic: sentence-transformers/all-MiniLM-L6-v2, normalized embeddings, CPU, 256-token maximum; overlapping 900-character chunks, stride 750, title prepended. Document similarity is the maximum chunk dot product. Tokenizer truncation still applies within each chunk.
3. Graph: inverse-square-root-frequency entity matches and two-hop explicit-reference traversal from the top three BM25 seeds. Exact incident IDs also seed traversal. This expert depends on BM25; it is not an independent lexical-free baseline.

Fenced code is removed before extracting references, and bare issue numbers require contextual phrases. Ambiguous natural-language references remain a limitation. Undirected links preserve the originating source URL but do not imply directed dependencies or causal effects. The full corpus is indexed by every method; supervised labels, not unsupervised documents, are held out.

## Learning

Fixed fusion uses reciprocal-rank fusion with equal weights, constant 60 and depth 30. A standardized ridge regressor predicts three reciprocal-rank utilities from 12 features: log query length, identifier fraction, entity count, error/relationship indicators, each expert's top score and margin, and top-result agreement. Softmax converts predictions to sum-to-one fusion weights.

Two title-derived questions per training document provide automatic silver supervision. Development MRR selects alpha in {1,10,100} and temperature in {0.15,0.35,1.0}; selected alpha=100, temperature=1.0. All experts run before routing, so the gate does not reduce retrieval computation. The single-expert baseline is also selected on development MRR.

A logistic relevance calibrator uses development top-result outcomes, including eight obvious unrelated negatives. The same development partition serves selection and calibration, limiting independence. A fixed 0.8 abstention threshold is not tuned on test. If calibration sees only one class, confidence is unavailable rather than fabricated. Confidence is not root-cause certainty.

## Evaluation and limitations

The test pilot has 24 single-report queries, three two-report queries and six obvious unrelated negatives. Questions were authored and source-checked by the coding assistant; independent human annotation is pending. One anchor phrase was corrected from the original body before evaluation, without changing its query or relevance target. Questions were not rewritten based on test outcomes.

Recall@5 uses known relevant incidents; precision@5 always divides by five; MRR considers the first known relevant result across the full returned ranking; nDCG@5 uses binary relevance. Incomplete labels can count other relevant reports as misses. Unrelated negatives enter abstention/Brier metrics, not positive retrieval metrics. Coverage includes all 33 queries; accepted precision is undefined when none are accepted.

Latency covers first-query retrieval with embeddings already indexed. It excludes startup, indexing and network. Graph includes lexical seeding; hybrid includes semantic, graph/lexical and gate/fusion costs. These are exploratory timings, not load-tested SLAs.

Pilot MRR: routed 0.868 versus fixed 0.839 (+0.028 absolute); BM25 remains stronger at 0.957. Sparse reference coverage and broad entity noise likely contribute to weaker graph scores—an interpretation, not a verified cause. No statistical superiority or generalization is established. All six obvious negatives abstain, but accepted top1 precision is only approximately 0.808; confidence is not a guarantee.

The important next experiment is an independently labelled set with hard software-related negatives and new incident components. Preserve this pilot instead of repeatedly tuning against it. A post-pilot BM25+semantic ablation is now included in the diagnostic artifacts; it does not retroactively become a preregistered pilot comparison.

## References and scope

- [GitHub issue search](https://docs.github.com/en/rest/search/search#search-issues-and-pull-requests)
- [SentenceTransformer API](https://www.sbert.net/docs/package_reference/sentence_transformer/SentenceTransformer.html)
- [MiniLM model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)

No MCP agent, generative answer module or causal risk model is implemented. The gate is conceptually related to expert selection but is not a neural mixture-of-experts architecture.
