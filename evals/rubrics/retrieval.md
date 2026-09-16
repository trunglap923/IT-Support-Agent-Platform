# Retrieval baseline rubric v1

- **Recall@5**: answerable cases whose expected `document_key + version_label` appears in
  the first five hits, divided only by the number of answerable cases.
- **MRR@5**: reciprocal rank of the first expected document in the first five hits, averaged
  over the same answerable denominator. A miss contributes zero.
- **No-answer accuracy**: no-answer cases where the evidence builder abstains, divided by
  all no-answer cases. These cases are not included in Recall@5.
- **Scope leakage**: scope cases where any `forbidden_document_keys` appears in any returned
  hit. The required result is zero leaks; filtered hits must never reach citation building.

This M2 baseline uses deterministic fake embeddings and PostgreSQL full-text search. It
validates retrieval wiring, version filtering, ACL behavior and reproducibility; it is not a
claim about semantic quality of the paid OpenAI embedding model.
