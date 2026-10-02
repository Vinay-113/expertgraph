# Contributing

Use Python 3.11 and run `python -m pytest -q` before proposing a change.
Lightweight tests need numpy, scikit-learn, networkx, matplotlib and pytest;
they do not download MiniLM. Corpus-dependent tests skip when local data is absent.

Do not commit credentials, raw issue archives, private logs or model pickle files.
Treat retrieved issue text as untrusted data, not instructions.

Preserve the measured pilot and validation artifacts. Model improvements need
a new experiment directory, development-only selection and a new untouched
test set. Do not tune on the published diagnostic suite and call it held-out.

Independent annotation is especially welcome. Follow [the review protocol](docs/ANNOTATION.md).
Version proposed label corrections; never silently rewrite original results.
