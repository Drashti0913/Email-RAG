# Evaluation report

## Evidence and current status

This report distinguishes real measurements from checks that require a local database, model
runtime, and Gmail authorization. There are **no invented end-to-end benchmark results**.
The authoring environment had Python 3.12.14 on Linux x86_64, but no Docker, PostgreSQL server,
or Ollama executable. No real mailbox was accessed. No generated model answer was evaluated.

## Measured offline results

See `reports/test_results.txt` for exact test names and `reports/offline_benchmark.json` for raw
measurements. The parser benchmark reads 10 synthetic emails (12 chunks, including 2 text
attachments) for 100 rounds. It measures MIME parsing plus chunking only, not embeddings.

| Measurement | Result |
|---|---|
| Offline automated tests | 30 passed |
| Actual database tests | 8 skipped; opt-in live suite provided |
| Parse + chunk median, 10-message batch | 15.35 ms |
| Parse + chunk p95, 10-message batch | 22.51 ms |
| Median parse + chunk per message | 1.53 ms |
| Real embedding time | Not measured |
| Real database retrieval latency | Not measured |
| Real answer generation time | Not measured |
| Semantic source recall / answer accuracy | Not measured |
| Real Gmail integration | Not exercised |

Tests cover metadata, Unicode and malformed dates, MIME alternatives, text/HTML/CSV/DOCX/PDF
extraction, unsupported attachment warnings, chunk coverage, duplicate handling, local-model URL
restrictions, no-evidence behavior, citation warnings, Gmail pagination/account checks with a
mock transport, MBOX parsing, and multi-batch summary coverage. Fake vectors and fake model
responses exercise orchestration only; they are not semantic or performance validation.

## Repeatable full evaluation

Use a fresh sample-only database and ingest both synthetic users as described in DEMO.md.
Run `RUN_DB_TESTS=1 python -m unittest discover -s tests -p 'test_database.py' -v`, then
`python scripts/benchmark.py --alice-token .secrets/alice.token --bob-token .secrets/bob.token --runs 3`.

The benchmark measures a real document-embedding batch plus each query's embedding, SQL retrieval,
generation and total time. It reports medians, maximums and nearest-rank p95 across repeated
cases, and saves the individual measurements. Run 0 may include cold model loading; report it
separately from subsequent runs when assessing warm latency. A tiny sample of 15 requests does
not establish production p95 performance. The file records model digests and system details;
also record your CPU, GPU, available RAM and Ollama version manually.

Expected-source recall is computed against fixture message IDs. Keyword coverage is saved only
as a quick diagnostic: correct paraphrases may fail it and unsupported assertions may pass it.
For a defensible answer-quality observation, manually mark each factual claim supported,
contradicted, or unsupported by its cited source, and report the numerator and denominator.

| Human check | Expected result | Observed result after local run |
|---|---|---|
| Alice's Q4 budget | $120k; engineering $70k; marketing $50k | Pending |
| Bob's Q4 budget | $42k; research $30k; operations $12k | Pending |
| API ownership/deadline | Priya; October 8 | Pending |
| Attachment-only retry rule | Up to 5; exponential backoff+jitter; 429/503 | Pending |
| Latest marketing timestamp | 2026-09-30 20:30 UTC | Pending |
| Launch plan revision | Oct 15 superseded by Oct 22; security review | Pending |
| Alice filtered Orion query | Empty sources, no generation | Pending |
| Bob Orion query | His source with COBALT-731 | Pending |
| Every generated factual claim cited correctly | Manual source-level review | Pending |
| New evaluator email + attachment | Fresh sync retrieves both facts | Pending |

## Challenges and design responses

- **Duplicated MIME content:** select a plain-text alternative when present; index attachments
  separately. Decode declared charsets with a safe fallback, preserving warnings for malformed data.
- **Incremental processing:** stable message identity plus raw-content hash avoids duplicate
  records and skips unchanged messages. Transactional replacement avoids stale attachment chunks.
  Gmail uses account + message ID; local formats use Message-ID or content hash if absent.
- **Latest-date versus semantic similarity:** sender/date ordering is explicit, so the newest
  email is selected across the matching indexed mailbox rather than only a relevance candidate set.
- **Broad summaries exceeding a prompt:** process all chunks within a declared subject filter
  in chronological batches with globally unique citation labels. State scope rather than pretending
  a relevance top-k search necessarily covers every conversation.
- **Cross-user leakage:** token-derived identity, parameterized predicates and forced database
  RLS provide multiple guards. Real RLS tests are supplied, but their result is still pending.
- **Reproducibility:** pin named model variants and store the embedding digest. Reject mixed
  embedding spaces. After successful local installation, capture a dependency lockfile and image digest.

## Limitations

- Full local inference, database integration, retrieval thresholds and generated-answer quality
  need validation on the target machine. The 0.35 similarity floor is an uncalibrated heuristic.
- Synthetic data is small, English-language, and deliberately simple. It cannot establish quality
  on a large, multilingual or noisy inbox. Character-based chunk sizing is an approximation;
  unusual Unicode can inflate token counts. Ollama input overflow is an explicit error for embeddings.
- Attachment support is format-bounded. OCR, images, spreadsheets, archives, encrypted files and
  legacy Office formats require conversion or additional extractors. PDF/DOCX parsers are not
  sandboxed processes and should not be exposed to arbitrary hostile uploads in production.
- Subject-filter completeness is not semantic topic completeness. Relevance mode can miss email;
  summaries spanning many batches are presented in batches rather than an aggressively compressed
  final synthesis. A single long message may dominate a relevance top-k result.
- Missing/invalid message dates are excluded from latest queries. Sender substring matching is
  literal, not entity resolution or proof of sender authenticity.
- Gmail sync is bounded and does not mirror remote deletions. Database deletion and local-file
  retention are not yet automated. Orphan source files can remain after a failed DB write.
- RLS relies on a trusted local process selecting the session identity. Users with shared DB
  credentials, admin credentials or access to other users' local secret files are outside the
  hostile-user boundary. This is not ready for a public multi-tenant deployment.
- Model output can hallucinate, ignore citation instructions or obey malicious email text.
  A citation label check cannot prove factual entailment. No model tools or mail-writing APIs
  are exposed, limiting action risk but not eliminating incorrect-answer risk.
- Gmail/API OAuth setup and model downloads require network access. Model inference itself is
  entirely local. Google Drive bonus ingestion and a graphical interface are not implemented.

## Prioritized improvements

1. Finish the real database/model/Gmail checks and calibrate retrieval against a labeled corpus.
2. Add tokenizer-aware chunking, reranking, per-message diversity and query-intent/entity handling.
3. Add local OCR and sandboxed document extraction with process-level time and memory limits.
4. Add Gmail history-ID sync, deletion handling, source retention policies and token revocation.
5. For hosted multi-user use, move credentials behind a trusted service, add real sessions/OAuth2,
   enforce identity outside client-controlled settings, encrypt data, and add audit/rate controls.
6. Profile exact vector scans on realistic mailbox sizes before considering HNSW or partitioning;
   measure recall under tenant filters. Add Drive conversion only after core acceptance passes.
