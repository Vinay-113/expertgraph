# ExpertGraph: a 90-second demonstration you can explain

1. **0–15 seconds:** “This is an evidence-retrieval research prototype using 109 public software reports. It combines lexical search, pretrained sentence embeddings and documented issue links; it does not diagnose my private infrastructure.”
2. **15–35 seconds:** Click Configuration error. Open the first source and show where its body supports the question. Expand a graph path; distinguish an entity mention from an explicit issue reference.
3. **35–50 seconds:** Change the retrieval dropdown to BM25, then semantic, then learned hybrid. Explain that the ranking changes while the source corpus remains fixed. The learned gate runs all three experts; it does not save inference cost.
4. **50–65 seconds:** Click Unknown exact error or Unsupported action. Explain the scope guard: the corpus cannot prove an absent exact identifier or execute a production patch. The raw learned estimate stays visible but does not override the guard.
5. **65–90 seconds:** Show original and diagnostic comparisons. “BM25 led the original pilot, but semantic retrieval led harder paraphrases and terse logs. Learned routing did not generalize well. Labels are assistant-authored drafts awaiting independent review, so these are exploratory findings rather than established accuracy.”

Before recording, run the source-tree launcher and try the examples yourself. Read METHODS.md, the validation report and SOURCE_REVIEW.md. Keep the scope limitations in the demo instead of presenting every confidence estimate as trustworthy.

## Your review task

Open artifacts/validation-v1/annotation_review.csv and review at least the first eight positive rows against their original sources. Mark accept/revise/reject, record your name, and add additional relevant reports. Ask a second person to review a blinded subset if possible. Do not change frozen benchmark labels just to improve the score. Corrections need a new version with original outcomes retained.
