# Application and interview notes

## One-line explanation

ExpertGraph finds relevant software failure reports and shows how they are connected, with original sources you can check.

## Classification and CV entry

Independent research prototype / evidence-grounded retrieval system. Not a chatbot, published paper or production platform.

**ExpertGraph — Evidence-Grounded Incident Retrieval | Independent Project**  
Python · scikit-learn · Sentence Transformers · NetworkX

- Built a source-grounded retrieval prototype combining BM25, MiniLM embeddings and issue-reference graphs over 109 public software reports; exposed original excerpts and edge provenance through a local explorer.
- Implemented learned expert fusion, inspectable graph paths and explicit evidence-scope abstention; compared six configurations using component-held-out splits and reproducible pilot/stress diagnostics.

Use this after running and understanding the system yourself. Once publication is verified, use the repository and recorded-demo links at the top of the README. The hosted demo is a replay, not live inference. No invented supervision, publication or team credits. Describe the implementation as AI-assisted if the application asks.

Optional measured wording, after reviewing labels: “On a 27-question source-checked pilot, routed fusion achieved 0.944 recall@5 and 0.868 MRR versus 0.839 for fixed fusion; BM25 remained strongest.” Never shorten it to “94.4% accurate AI.” The implementation-based entry above is safer until independent review.

The follow-up 36-query suite exposes weaker routing and misleading high estimates. Semantic retrieval leads that diagnostic set, while BM25 leads the original pilot. Do not cherry-pick the original percentage or claim the learned router is generally superior. Some apparent errors are unlabelled related reports; labels and abstention rules are still independently unvalidated.

An additional defensible implementation detail is the frozen-model stress test, BM25+semantic ablation, source-level failure review and component-bootstrap uncertainty analysis. Describe these as research practice, not a novel algorithm or independently verified accuracy.

## SOP paragraph to adapt

“To explore evidence-grounded AI, I developed ExpertGraph, an independent prototype combining lexical search, semantic embeddings and a source-supported issue graph. I investigated query-dependent expert fusion through held-out comparisons and exposed evidence paths and abstention in the interface. The pilot showed that adding experts does not automatically improve retrieval: BM25 remained stronger than the hybrid. This motivated my interest in better graph construction, representative evaluation and reliable language-based systems, which I hope to study further during the exchange.”

This demonstrates transferable skills in knowledge-graph retrieval, interpretable decision support and expert selection. It does not establish telecom, clinical, robot-navigation or macroeconomic expertise. Tailor its connection to the actual host description once selected. It may strengthen evidence of your skills; no admissions-odds improvement can be guaranteed or quantified.

## Interview preparation

**Why not just BM25?** It wins this pilot. The question is when other signals help; a sparse graph can hurt. Preserve that finding.

**What is learned?** Ridge predicts three expert utilities from 12 query/result features; softmax weights the fusion. MiniLM is pretrained, not fine-tuned here.

**Who labelled the data?** Title-derived train/dev questions are automatic silver supervision; the pilot is assistant-authored and source-checked with independent review pending.

**What prevents leakage?** Linked components stay within one split; test labels do not train/select the gate. Full unsupervised document indexing is allowed. Unlinked duplicates remain a limitation.

**Do paths prove causes?** No; they show mentions or documented associations.

**Is confidence reliable?** It is a preliminary estimate under an artificial development distribution. Accepted errors still occur.

**What is original?** The traceable incident corpus, expert-gated retrieval, source paths, frozen comparisons and explorer form an independently built applied prototype. It does not claim a novel algorithm or copy the host proposal.

**What next?** Independent labels, harder negatives, more reliable graph evidence and a new untouched test set. A BM25+semantic ablation is already included in the diagnostic study.
