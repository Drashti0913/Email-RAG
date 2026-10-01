# Line-by-line requirement coverage

Source: the four supplied pages of “Technical Assessment: Personal Email RAG System.”
“Implemented” describes code, not a claim that an unavailable external service was tested.

| Assignment requirement | Implementation / evidence | Validation status |
|---|---|---|
| Local open-source LLM | Ollama + Mistral 7B Instruct v0.3 Q4_K_M | Live inference pending |
| Vector database, pgvector preferred | PostgreSQL 16 + pgvector; 768-dimensional vectors | Live DB checks pending |
| Standard email format | `.eml`, `.mbox`, recursive EML directory | Offline fixtures tested |
| Real account, Gmail preferred | Desktop OAuth, readonly Gmail API, pagination, account check | Mocked transport tested; real consent/sync pending |
| Attachments indexed with emails | TXT/CSV/JSON/MD/HTML/PDF/DOCX to separate chunks | Text, DOCX, PDF extraction tested; unsupported/scanned types explicitly flagged |
| Sender, recipient, subject, body, timestamp | MIME policy parser and UTC-aware dates | Offline tested |
| Convert content to embeddings | Local Nomic embed text v1.5, document/query prefixes | Live embeddings pending |
| Persist vectors with metadata | Transactional replacement; composite tenant/message key; original source retained | DB tests provided |
| Natural-language questions | CLI query, semantic + lexical retrieval | Orchestration tested; semantic quality pending |
| Prompt augmentation | Bounded JSON evidence, global source labels, untrusted-data instructions | Offline tested; prompt injection not claimed solved |
| Contextual answers + referenceable links | `[S#]`, source excerpts, local EML URI or account-specific Gmail thread link | Structure tested; model grounding pending |
| Sarah / Q4 example | Synthetic Alice budget + distinct Bob budget | Expected evidence documented |
| API integration example | Body plus retry-policy attachment | Parsing tested; live retrieval pending |
| Latest marketing example | Explicit sender filter + database date ordering | Offline CLI guard tested; DB test provided |
| Summarize all product-launch conversations | Every chunk in an explicit subject scope, batched when needed | Batch coverage tested; semantic topic exhaustiveness not implied |
| Bonus: each user only their mail | Capability token maps to UUID; SQL filters + forced RLS | Real DB isolation tests pending |
| Bonus: separate collections or metadata filter | Tenant UUID in both tables and policies | SQL provided |
| Bonus: identity/auth mechanism | Random 256-bit capability token; hash stored in DB | Token path implemented; real DB authentication test provided |
| Bonus: 2 datasets | Alice: 7 emails; Bob: 3 emails; separate secrets | Fixtures included |
| Bonus: cross-user query empty/error | Orion subject-filter example, explicit RLS cross-user query test | Live DB test pending |
| Bonus: robust namespace separation | Composite keys, scoped transactions, non-BYPASSRLS role | Shared local operator remains trusted |
| Extra bonus: Google Drive files | Not implemented | Optional extra omitted |
| Everything local; no OpenAI/Claude inference | Loopback-only Ollama, no redirects/proxies, cloud-tag rejection | URL guards tested; configure server with OLLAMA_NO_CLOUD=1 |
| Open-source tools | Python, PostgreSQL/pgvector, Ollama, Mistral/Nomic, extraction/OAuth libraries | Gmail itself is the explicitly requested external data source |
| Explain model choices | ARCHITECTURE.pdf | Included, 2 pages |
| Embedding time, retrieval latency, generation time | Stage timers + live benchmark, raw measurements | Only parser measurements available here; no fabricated model metrics |
| Clean documented Python | Modular package + CLI + tests | Compilation and offline tests pass |
| requirements.txt/environment.yml | requirements.txt with bounded dependency versions | Fresh local dependency installation still required |
| README setup | README.md | Included |
| Example email dataset | sample_data/ with generator and MBOX | Included and parsed |
| Architecture 1-2 pages | docs/ARCHITECTURE.pdf | Two pages, rendered and inspected |
| DB choice/config, model quantization, isolation design | ARCHITECTURE.pdf + schema.sql | Included |
| Demo setup, ingest, queries, switch users | docs/DEMO.md | Exact commands and expected evidence |
| Evaluation performance/accuracy observations | docs/EVALUATION.md + reports/ | Measured vs pending explicitly separated |
| Challenges, limitations, improvements | docs/EVALUATION.md | Included |
| Private GitHub repo or live demo | Source package ready for private upload; live demo commands included | User must create/share repo or arrange demo |
| Email Rebecca after completion | Submission checklist in DEMO.md | Not sent; wait for live verification |

## Before calling the assessment complete

1. Install dependencies and pull models on your machine; `doctor` must succeed.
2. Run all eight real database tests and the actual-model benchmark.
3. Verify each expected fact against its cited source and record observed quality/latency.
4. Ingest mail from your real Gmail account, including a supported attachment; verify its link.
5. Resolve extraction warnings relevant to the evaluator's test emails.
6. Review the code and be ready to explain parsing, cosine distance, RLS and context limits.
7. Upload only safe project artifacts to a private repo or demonstrate locally; arrange evaluation.
