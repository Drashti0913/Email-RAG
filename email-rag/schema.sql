CREATE EXTENSION IF NOT EXISTS vector;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
CREATE TABLE users (
  user_id uuid PRIMARY KEY,
  display_name text NOT NULL UNIQUE,
  token_hash text NOT NULL UNIQUE
);
CREATE TABLE model_config (
  singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
  embedding_identity text NOT NULL
);
CREATE TABLE emails (
  user_id uuid NOT NULL REFERENCES users(user_id),
  email_id text NOT NULL,
  content_hash text NOT NULL,
  sender text NOT NULL,
  recipient text NOT NULL,
  subject text NOT NULL,
  sent_at timestamptz,
  source_url text NOT NULL,
  warnings jsonb NOT NULL DEFAULT '[]',
  PRIMARY KEY(user_id, email_id)
);
CREATE TABLE chunks (
  user_id uuid NOT NULL,
  email_id text NOT NULL,
  chunk_no integer NOT NULL,
  part_name text NOT NULL,
  content text NOT NULL,
  embedding vector(768) NOT NULL,
  PRIMARY KEY(user_id, email_id, chunk_no),
  FOREIGN KEY(user_id, email_id) REFERENCES emails(user_id, email_id) ON DELETE CASCADE
);
CREATE INDEX emails_user_date ON emails(user_id, sent_at DESC);
-- Exact vector scan is intentional for a small mailbox: no ANN recall loss after filtering.
ALTER TABLE emails ENABLE ROW LEVEL SECURITY;
ALTER TABLE emails FORCE ROW LEVEL SECURITY;
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks FORCE ROW LEVEL SECURITY;
CREATE POLICY email_owner ON emails USING (user_id = NULLIF(current_setting('app.user_id',true),'')::uuid)
  WITH CHECK (user_id = NULLIF(current_setting('app.user_id',true),'')::uuid);
CREATE POLICY chunk_owner ON chunks USING (user_id = NULLIF(current_setting('app.user_id',true),'')::uuid)
  WITH CHECK (user_id = NULLIF(current_setting('app.user_id',true),'')::uuid);
GRANT USAGE ON SCHEMA public TO rag_app;
GRANT SELECT(user_id, token_hash) ON users TO rag_app;
GRANT SELECT, INSERT ON model_config TO rag_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON emails, chunks TO rag_app;
