# Supplemental source review — not independent annotation

The assistant inspected the top report bodies after seeing stress outcomes. These notes do not change the frozen draft labels or scores. A human reviewer should make the final relevance decisions; corrected labels need a separately versioned benchmark.

- challenge-02: retrieved psf/requests#7615 discusses Proxy-Authorization being stripped on initial requests. Target #7335 discusses null/control bytes passing header validation. Shared header vocabulary does not support the specific null-byte question.
- challenge-07: #1307 describes Windows ARM free-threaded interpreter failures and broken symlinks, making it genuinely related. However, the question's unchanged-download-digest detail is documented in #1267, not established by #1307. Relevance may be graded rather than binary.
- challenge-08: #1214 discusses Linux distribution support, while #1288 is the RISC-V architecture gap. Both relate to unavailable binaries, but the specific architecture evidence is missing from the top report.
- challenge-14: #14640 and target #14964 both describe fixture loss from discontinuous file argument ordering. The retrieved report may be an additional relevant report. This is a concrete incomplete-label concern, not a confirmed wrong answer.
- challenge-18: #14964 concerns missing fixtures during recollection, not the explicit #14716–#13246 configuration-location association requested. The supplied issue-ID pair is more specific than the shared fixture vocabulary.
- challenge-19: #14992 describes changed ordering between usefixtures and autouse dependencies; target #14964 describes missing fixtures caused by directory recollection and cites #14004. Related guard vocabulary alone does not establish the requested source pair.
- challenge-31: psf/requests#5461 documents invalid percent encoding, but contains no invented COMET_ENCODING_6H24R identifier. It cannot establish the requested exact error reproduction.
- challenge-33: psf/requests#7615 is a proposed proxy-auth patch report. Retrieval of this report does not patch the user's production system or prove live resolution.

These observations explain why accepted_top1_precision against the draft is not the same as true semantic accuracy. Preserve both the failure examples and the annotation ambiguity.
