# Demonstration script

Run everything from `email-rag/`. Do not claim a successful step unless it succeeds on your machine.

## A. Environment setup

Complete README sections 1-2: install dependencies, edit `.env`, export variables, start
PostgreSQL and local Ollama, and pull both models. Exact setup commands are in README so there
is only one configuration to maintain. Then:

```bash
source .venv/bin/activate
set -a
source .env
set +a
docker compose up -d --wait
python -m email_rag create-user alice --out .secrets/alice.token
python -m email_rag create-user bob --out .secrets/bob.token
python -m email_rag --token-file .secrets/alice.token doctor
```

If you already created these users, reuse their token files and skip `create-user`.
Show that `doctor` reports 768 embedding dimensions and locally installed model identities.
Explain that Python calls only local Ollama for model inference.

## B. Ingestion and re-ingestion

```bash
python -m email_rag --token-file .secrets/alice.token ingest sample_data/alice
python -m email_rag --token-file .secrets/bob.token ingest sample_data/bob
python -m email_rag --token-file .secrets/alice.token ingest sample_data/alice
```

First pass: Alice indexes 7 messages and 9 chunks; Bob indexes 3 and 3. Second Alice pass:
all 7 messages report `unchanged`. Show embedding and storage timing fields. Source files
are retained locally and attachment text becomes separate chunks with the original email link.

## C. Core queries and expected evidence

```bash
python -m email_rag --token-file .secrets/alice.token query "What did Sarah say about the Q4 budget?"
python -m email_rag --token-file .secrets/alice.token query "Show me emails discussing the API integration project"
python -m email_rag --token-file .secrets/alice.token query "What is the API retry policy?"
python -m email_rag --token-file .secrets/alice.token query "When did I last hear from the marketing team?" --latest --sender marketing@example.test
python -m email_rag --token-file .secrets/alice.token query "Summarize all conversations about the product launch" --all-matching --subject "product launch"
```

| Query | Ground truth in synthetic data |
|---|---|
| Sarah's Q4 budget | $120,000 total; $70,000 engineering; $50,000 marketing |
| API project | Priya owns connector; OAuth 2.0; staging due October 8 |
| Attachment-only detail | Up to 5 retries; exponential backoff with jitter; retry 429/503 |
| Latest marketing email | September 30, 2026, 16:30 Eastern / 20:30 UTC |
| Product launch | Originally October 15; changed to October 22 because of security review |

For each answer, inspect `[S#]`, check source excerpts, and open the associated `.eml` or Gmail
thread. Do not promise identical wording from the model. For the summary, show the explicit
subject scope and chunk/message coverage, including the distinction from semantic topic-wide completeness.

## D. Multi-user isolation

```bash
python -m email_rag --token-file .secrets/alice.token query "What is Bob's private Orion acquisition code?" --subject "Orion"
python -m email_rag --token-file .secrets/bob.token query "What is the private Orion acquisition code?" --subject "Orion"
python -m email_rag --token-file .secrets/bob.token query "What did Sarah say about the Q4 budget?"
RUN_DB_TESTS=1 python -m unittest discover -s tests -p 'test_database.py' -v
```

Alice's filtered Orion query must return no sources and invoke no generation. Bob must retrieve
his own Orion email containing COBALT-731 and $9,300,000. Bob's Q4 amount is $42,000, distinct
from Alice's $120,000. Run actual DB tests to prove explicit other-user filtering yields empty
rows and attempted cross-user insertion raises an error. Explain the trusted-local-operator
boundary instead of describing this as production-grade hostile-user isolation.

## E. Real-account live ingestion

Follow README Gmail OAuth setup once. Then, using your separately created real-mail user:

```bash
python -m email_rag --token-file .secrets/real-mail.token gmail-sync \
  --credentials .secrets/gmail-client.json --account YOUR_EMAIL@gmail.com \
  --query 'newer_than:1d -in:spam -in:trash' --limit 100
python -m email_rag --token-file .secrets/real-mail.token query "What did the evaluator ask me to do?"
```

For an evaluator-sent email, re-run `gmail-sync` after receiving it. Query a unique fact in
its body and a unique fact in a supported attachment. Open the real Gmail source link. Show
warnings if extraction was partial; resolve them before claiming all attachments were indexed.
No message is sent by this project.

## F. Benchmarks and presentation

```bash
python scripts/benchmark.py --alice-token .secrets/alice.token --bob-token .secrets/bob.token --runs 3
```

Show `reports/local_benchmark.json`: hardware/OS, model digests, embedding throughput,
query-embedding/retrieval/generation latency, expected-source recall and isolation evidence.
Read several generated answers aloud while checking their source claims. Record actual results
in EVALUATION.md; do not turn keyword matching into a factual-accuracy claim.

## G. Submission

Create a **private** GitHub repository and upload project code, synthetic data, documentation,
and reviewed synthetic-only benchmark results. Exclude `.env`, `.secrets`, `.data`, real emails,
and unreviewed outputs containing real mail. Share the repository with the evaluator, or arrange
the alternative live demo allowed by the brief. Only after the live checks succeed, contact
Rebecca Hurd at the address in the assignment to arrange evaluation. This package does not send
that email or create/share a repository automatically.
