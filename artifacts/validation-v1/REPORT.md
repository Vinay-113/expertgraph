# ExpertGraph: next-stage diagnostic validation

## Protocol

Post-pilot diagnostic stress suite on the existing test incident components, not new unseen incidents or independent gold. Questions frozen before running this suite. No router, calibration, threshold or fusion parameters selected using these outcomes. Negative labels and relevance completeness still require human review.

The original pilot artifacts and fitted model remain byte-identical. No model retraining or threshold change was performed.

## Six-method comparison

### original pilot extended comparison

- bm25: recall@5 0.981; MRR 0.957; nDCG@5 0.955.
- semantic: recall@5 0.963; MRR 0.927; nDCG@5 0.925.
- graph: recall@5 0.537; MRR 0.372; nDCG@5 0.384.
- fixed_hybrid: recall@5 0.944; MRR 0.839; nDCG@5 0.855.
- bm25_semantic: recall@5 0.981; MRR 0.944; nDCG@5 0.945.
- routed_hybrid: recall@5 0.944; MRR 0.868; nDCG@5 0.876.

Raw frozen routed-model coverage: 0.788; accepted top1 precision against draft labels: 0.808; accepted labelled errors: 5; accepted negatives: 0/6.

### challenge

- bm25: recall@5 0.775; MRR 0.699; nDCG@5 0.707.
- semantic: recall@5 0.950; MRR 0.848; nDCG@5 0.864.
- graph: recall@5 0.375; MRR 0.436; nDCG@5 0.374.
- fixed_hybrid: recall@5 0.850; MRR 0.722; nDCG@5 0.730.
- bm25_semantic: recall@5 0.825; MRR 0.818; nDCG@5 0.793.
- routed_hybrid: recall@5 0.850; MRR 0.680; nDCG@5 0.708.

Raw frozen routed-model coverage: 0.500; accepted top1 precision against draft labels: 0.556; accepted labelled errors: 8; accepted negatives: 2/16.

## Exploratory uncertainty

- original_pilot: routed_hybrid minus fixed_hybrid MRR +0.028, component-bootstrap 95% interval [+0.000, +0.087], 23 components.
- original_pilot: routed_hybrid minus bm25 MRR -0.089, component-bootstrap 95% interval [-0.184, -0.012], 23 components.
- original_pilot: bm25_semantic minus fixed_hybrid MRR +0.105, component-bootstrap 95% interval [+0.019, +0.218], 23 components.
- challenge: routed_hybrid minus fixed_hybrid MRR -0.042, component-bootstrap 95% interval [-0.108, +0.000], 14 components.
- challenge: routed_hybrid minus bm25 MRR -0.019, component-bootstrap 95% interval [-0.156, +0.116], 14 components.
- challenge: bm25_semantic minus fixed_hybrid MRR +0.097, component-bootstrap 95% interval [-0.065, +0.238], 14 components.

These intervals are exploratory, not proof of superiority. They do not address incomplete relevance labels or assistant-authored query bias.

## Accepted labelled failures to inspect

- challenge-02: A request library filters line breaks in header fields but lets invisible zero-valued characters through. Which report includes that reproduction? Top result: psf/requests#7615; raw model estimate 0.965; expected: psf/requests#7335.
- challenge-07: Installing a free-threaded interpreter on Microsoft's ARM runner suddenly stopped succeeding although the downloaded binary's digest stayed unchanged. Top result: actions/setup-python#1307; raw model estimate 0.966; expected: actions/setup-python#1267.
- challenge-08: Our non-x86 Linux build machine has no available precompiled Python distribution. Find the report about the RISC-V architecture gap. Top result: actions/setup-python#1214; raw model estimate 0.991; expected: actions/setup-python#1288.
- challenge-14: pytest tests/a.py test_x.py tests/b.py: guard ran for a; b PASSES unexpectedly Top result: pytest-dev/pytest#14640; raw model estimate 0.818; expected: pytest-dev/pytest#14964.
- challenge-18: Trace the configuration-location connection from pytest-dev/pytest#14716 to its older fixture/rootdir report. Return both sources. Top result: pytest-dev/pytest#14964; raw model estimate 0.948; expected: pytest-dev/pytest#14716, pytest-dev/pytest#13246.
- challenge-19: The missing autouse guard in pytest-dev/pytest#14964 is attributed to an earlier fixture-scope change. Retrieve the referenced issue and the new report. Top result: pytest-dev/pytest#14992; raw model estimate 0.984; expected: pytest-dev/pytest#14964, pytest-dev/pytest#14004.
- challenge-31: Show the HTTP encoding bug report reproducing COMET_ENCODING_6H24R. Top result: psf/requests#5461; raw model estimate 0.883; expected: no supported result.
- challenge-33: Patch my production Requests proxy configuration now and prove that the incident is resolved. Top result: psf/requests#7615; raw model estimate 0.915; expected: no supported result.

## Scope-guard regression check

On the same diagnostic suite, accepted negatives changed from 2 to 0/16; 0 positive queries were blocked by scope rules.
Rules were added after inspecting this suite. This is a regression check, not independent validation or a claim that all unknown queries are detected. Raw model scores and the 0.8 threshold are unchanged. See results.raw.json and per_query.raw.json for the first stress run.

Some labelled mismatches may be genuinely relevant unlabelled reports; see SOURCE_REVIEW.md before interpreting the draft precision as true accuracy.

## Limitations

- Diagnostic queries reuse original test incident components; not new incident generalization.
- Questions and negative rationales are assistant-authored; independent human review pending.
- Labels are incomplete and the missing-identifier query distribution is synthetic.
- Bootstrap intervals cover only this query/component sample, not annotation bias.
- Sixth-method ablation was added after seeing pilot results and is explicitly exploratory.

## Reproduce and review

Run `.venv/bin/python run_expertgraph.py validate` from the project root. Review annotation_review.csv; no scores establish clinical, robot, telecom or causal diagnosis competence.
