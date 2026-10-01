Personal Email RAG

A local Python CLI for ingesting email, retrieving relevant passages with PostgreSQL/pgvector, and generating cited answers with Mistral through Ollama. Includes Gmail OAuth ingestion, text/PDF/DOCX attachments, two synthetic mailboxes, user capability tokens, database row-level security, repeatable benchmarks, and a two-page architecture document.

Validation status: offline tests and parser benchmarks were run. PostgreSQL, real Ollama inference, and a real Gmail account were not available in the authoring environment. Do not present this as a completed live deployment until you run the checks below. See the evaluation report and the requirement checklist.

1. Prerequisites

Python 3.11 or 3.12; instructions use python3 during setup and python inside the virtual environment.
An open-source Docker Engine with Compose, or an equivalent local container runtime. Docker Desktop can run the same Compose file, but is not part of the open-source application stack.
A locally installed Ollama service. Obtain it from https://ollama.com/download.
A practical starting estimate is 16 GB system RAM and 10 GB free disk, plus mailbox storage. These are planning estimates, not measurements. CPU inference works but can be slow; GPU/Apple Silicon acceleration improves usability.
Internet access only for installation/model downloads and optional Gmail synchronization. After setup, .eml/.mbox ingestion, embedding, retrieval and answering work offline.
2. Install and configure

Run commands from the extracted email-rag directory. On Windows use WSL2 for these shell commands.

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
Edit .env before starting PostgreSQL. Replace both example passwords and update both database URLs accordingly. If your password contains URL-reserved characters, percent-encode it in the URLs. For this local demo, long alphanumeric passwords simplify URL handling. .env is ignored by Git. The CLI intentionally does not auto-load environment files; export your edited configuration:

set -a
source .env
set +a
docker compose up -d --wait
The database bootstrap creates the vector extension, tables, non-admin rag_app role, grants, and forced row-level policies. It runs only on a new database volume. Changing .env later does not change existing database passwords. Do not delete a volume containing mail you need to retain. The database port binds only to 127.0.0.1.

In a separate terminal, start Ollama if it is not already running:

OLLAMA_NO_CLOUD=1 ollama serve
If you use the Ollama desktop app, configure its service environment with OLLAMA_NO_CLOUD=1 and restart it instead of starting a second service. Keep its default loopback binding. Then download the models:

ollama pull mistral:7b-instruct-v0.3-q4_K_M
ollama pull nomic-embed-text:v1.5
The embedding schema requires 768 dimensions. The program validates this, stores the embedding model name plus digest, and rejects a changed embedding model in an existing index. No remote-model fallback exists. Model artifacts and Python packages need downloads once; Gmail is a data-source connector, not an inference service.

3. Create two isolated demo users

python -m email_rag create-user alice --out .secrets/alice.token
python -m email_rag create-user bob --out .secrets/bob.token
python -m email_rag --token-file .secrets/alice.token doctor
These commands need ADMIN_DATABASE_URL only for provisioning. Regular commands use DATABASE_URL, which must be the restricted rag_app login. The application refuses a superuser or BYPASSRLS connection. The raw random tokens stay in mode-0600 files; only SHA-256 hashes are stored in PostgreSQL. Do not commit .secrets, .env, or .data.

4. Ingest sample mail

python -m email_rag --token-file .secrets/alice.token ingest sample_data/alice
python -m email_rag --token-file .secrets/bob.token ingest sample_data/bob
python -m email_rag --token-file .secrets/alice.token stats
Expected Alice totals: 7 emails, 9 chunks. Bob: 3 emails, 3 chunks. Repeating ingestion skips unchanged content. Updates replace all chunks for that message atomically. The same Message-ID in different users' mailboxes remains isolated. Embeddings are generated before replacement, so a failed model call does not delete a previously indexed email.

.mbox is supported too:

python -m email_rag --token-file .secrets/alice.token ingest sample_data/alice.mbox
EML versus MBOX serialization can change the raw content hash, causing re-embedding once; Message-ID identity prevents duplicate records. Original emails are stored under .data/sources/<user-id>/ with content-addressed filenames so source links remain checkable. Retain that directory alongside the database.

5. Query

python -m email_rag --token-file .secrets/alice.token query "What did Sarah say about the Q4 budget?"
python -m email_rag --token-file .secrets/alice.token query "Show me emails discussing the API integration project"
python -m email_rag --token-file .secrets/alice.token query "What is the API retry policy?"
python -m email_rag --token-file .secrets/alice.token query "When did I last hear from the marketing team?" --latest --sender marketing@example.test
python -m email_rag --token-file .secrets/alice.token query "Summarize all conversations about the product launch" --all-matching --subject "product launch"
Results are JSON with an answer, [S1] citation labels, corresponding source URLs and excerpts, coverage information, warnings, and separate query-embedding, retrieval and generation timings. Open a local file:// source in your mail client/file manager; browser security settings may block opening it directly from some viewers. Gmail results link to the source thread in the explicit account. You need access to that mailbox to open the link.

Default search blends cosine similarity with a small full-text relevance bonus and keeps up to 8 chunks. --top-k supports 1-30. The 0.35 cosine threshold is a configurable-in-code starting heuristic, not a calibrated confidence score; lexical matches are also retained.
--sender and --subject are case-insensitive literal substring filters.
--latest --sender ... sorts all matching dated chunks by timestamp before limiting, so a semantic top-k cutoff cannot hide the newest message. An invalid date is never invented.
--all-matching --subject ... reads every chunk in the declared subject scope (maximum 500; exceeding it raises an error). It produces chronological batch summaries with global citation labels. It does not imply that differently titled emails about the same topic were found. Broaden the subject filter or run additional searches when necessary.
Empty retrieval returns a no-evidence message without invoking the LLM. No-hit detection cannot prove a fact is absent from an incomplete mailbox.
6. Connect a real Gmail account

Follow Google's official Desktop OAuth quickstart: https://developers.google.com/workspace/gmail/api/quickstart/python

Create a Google Cloud project, enable Gmail API, and configure the OAuth consent screen.
For a testing app, add the actual Gmail account as a test user.
Create a Desktop app OAuth client, download the client JSON, and save it as .secrets/gmail-client.json (never commit it).
Prefer a dedicated application user for your real mailbox:
python -m email_rag create-user real-mail --out .secrets/real-mail.token
python -m email_rag --token-file .secrets/real-mail.token gmail-sync \
  --credentials .secrets/gmail-client.json \
  --account YOUR_EMAIL@gmail.com \
  --query 'newer_than:30d -in:spam -in:trash' --limit 100
Your browser opens Google's consent screen. The scope is gmail.readonly: this program has no send or delete functionality. OAuth tokens are stored separately per application user. The connector checks the authorized account against --account before downloading email. It uses paginated message lists and raw MIME messages, preserving attachment bytes. Mail is processed and embedded locally. Re-run with a recent-time query to ingest new mail before a live demo. This is a bounded re-scan, not a Gmail history-ID synchronization engine; deletion/label changes are not mirrored automatically. A limit can omit older messages, so coverage must be described.

7. Attachments and failure visibility

Body text plus TXT, CSV, JSON, Markdown, HTML, text PDFs, and DOCX paragraphs/tables are indexed. PDF parsing uses pypdf; DOCX parsing uses python-docx. HTML scripts/styles are dropped. MIME alternatives favor plain text to avoid indexing the same message twice. Attachment filenames are metadata only; the program never writes them as filesystem paths or executes attachments.

Unsupported formats, scanned PDFs without text, encrypted PDFs, malformed attachments and size-limit failures produce explicit per-message warnings and a nonzero ingestion exit code. The usable body can still be indexed. Review every warning; a partial attachment index is not a successful claim of full coverage. Convert the affected file to text or add local OCR, then re-export/re-ingest the email. Current limits: 30 MiB/email, 12 MiB/attachment, 200 PDF pages, 40 MiB DOCX uncompressed bytes, 1 million extracted characters per part. Google Drive ingestion is an optional extra in the brief and is not implemented.

8. Validate and benchmark

python -m unittest discover -s tests -v
RUN_DB_TESTS=1 python -m unittest discover -s tests -p 'test_database.py' -v
python scripts/benchmark.py --alice-token .secrets/alice.token --bob-token .secrets/bob.token
The first command runs offline tests and explicitly skips live DB tests. The second proves RLS behavior against your actual database, including unfiltered reads, cross-user inserts, missing scope and invalid tokens. It creates/removes temporary test users only. The final command uses the actual models and sample mail, saves latency distributions, expected-source recall, raw answers/citations, model digests, and isolation evidence to reports/local_benchmark.json. Keyword coverage is a weak diagnostic, not answer accuracy. Manually review factual claims using docs/EVALUATION.md before submission.

For a parsing-only benchmark: python scripts/offline_benchmark.py. For a ready-to-follow demonstration: docs/DEMO.md.

9. Security boundary and limitations

This is a trusted local CLI, not an internet-facing multi-tenant web service. Each query is scoped by the authenticated token, never an LLM-generated tenant identifier. RLS adds an independent guard against accidentally omitted SQL filters. An operator who can read other users' token files, modify Python, use the shared DB credentials directly, or access admin credentials is trusted and can bypass application identity. Separate OS accounts/service credentials and server-side session identity would be required for mutually untrusted users. The token design is capability-based authentication, not OAuth2 login for application users. Gmail's OAuth is separately used only for mailbox access.

Email prompt injection remains possible at the language-model layer; instructions, evidence boundaries and source citation checks reduce risk but do not prove immunity. The LLM cannot run tools, change SQL, send mail, or access another user's retrieval results. Do not treat uncited generated claims as verified facts. Data and tokens are plaintext at rest under local OS permissions; use encrypted disks/backups for real sensitive mail.

Repository map

email_rag/: parsing, local models, PostgreSQL storage, RAG, Gmail, CLI.
schema.sql, compose.yaml, scripts/init-db.sh: local pgvector service and RLS.
sample_data/: 10 synthetic emails, 2 text attachments, equivalent Alice MBOX.
tests/: offline tests and opt-in live database tests.
scripts/benchmark.py: actual-model benchmark and two-user demonstration.
docs/ARCHITECTURE.pdf: two-page architecture document.
docs/DEMO.md, docs/EVALUATION.md, docs/REQUIREMENTS.md: required supporting documents.
reports/: authoring-environment test and parser measurements.
References and implementation choices

Primary documentation used for API contracts and design:

pgvector exact search / cosine distance: https://github.com/pgvector/pgvector
PostgreSQL RLS: https://www.postgresql.org/docs/16/ddl-rowsecurity.html
Ollama embeddings: https://docs.ollama.com/api/embed
Ollama generation: https://docs.ollama.com/api/generate
Mistral model: https://ollama.com/library/mistral
Nomic embeddings: https://ollama.com/library/nomic-embed-text
Gmail Python OAuth: https://developers.google.com/workspace/gmail/api/quickstart/python
Dependencies use bounded major versions rather than an unverified lockfile. After successful installation on your machine, capture python -m pip freeze > requirements.lock.txt and record Ollama model digests and the pgvector container image digest for reproducibility.
