# Retrieval baseline rubric v1

- **Recall@5**: answerable cases whose expected `document_key + version_label` appears in
  the first five hits, divided only by the number of answerable cases.
- **MRR@5**: reciprocal rank of the first expected document in the first five hits, averaged
  over the same answerable denominator. A miss contributes zero.
- **Precision@5**: relevant unique document-version pairs divided by five, averaged over
  answerable cases. Repeated chunks from one document-version are counted once.
- **nDCG@5**: graded relevance of unique document-version pairs, normalized against the
  ideal ordering for each answerable case.
- **Duplicate rate@5**: repeated document-version pairs divided by returned items. This
  exposes context waste when several chunks from one source occupy the result window.
- **No-answer accuracy**: no-answer cases where the evidence builder abstains, divided by
  all no-answer cases. These cases are not included in Recall@5.
- **Scope leakage**: scope cases where any `forbidden_document_keys` appears in any returned
  hit. The required result is zero leaks; filtered hits must never reach citation building.

This M2 baseline uses deterministic fake embeddings and PostgreSQL full-text search. It
validates retrieval wiring, version filtering, ACL behavior and reproducibility; it is not a
claim about semantic quality of the paid OpenAI embedding model. Historical-version queries
are recorded as a known gap and excluded from the release recall gate.
