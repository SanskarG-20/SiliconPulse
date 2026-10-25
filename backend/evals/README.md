# Report trust benchmark

Run from `backend/` with `GEMINI_API_KEY` configured:

```powershell
$env:PYTHONPATH = "."
python -m evals.report_trust_eval --output evals/results/baseline.json
```

The frozen 50-query set is in `golden_queries.json`. The default corpus is the
checked-in `data/stream.jsonl`; pass `--corpus` to evaluate another fixed corpus.
Each run records the corpus SHA-256 and Git revision, plus aggregate and per-query
metrics. Keep baseline and step result files when comparing changes.

`recall_at_k` is the mean of expected-entity, expected-source-domain, and key-fact
recall among the top `k` retrieved evidence items. `citation_accuracy` is the share
of report references that exactly resolve to a retrieved source/timestamp/title.
`hallucination_rate` is the share of factual report claims whose informative tokens
have less than 30% overlap (at least two matching tokens) with their cited retrieved
evidence. This is a reproducible heuristic; it does not replace human review or
independent fact checking. Golden facts are selected from the frozen local corpus,
so the benchmark measures grounding and retrieval against that corpus, not whether
the corpus itself is true.

The harness asks Gemini for JSON matching the report schema and validates locally.
The provider adapter removes Gemini's unsupported `additionalProperties` keyword,
then the backend applies strict Pydantic validation and verifies cited spans. The
recorded baseline ran retrieval-only after the configured Gemini free-tier quota
was exhausted; its citation and hallucination metrics are `null` until generated
reports are available.
