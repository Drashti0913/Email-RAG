"""Parameterized SQL, transactional replacement, and database-enforced tenant scope."""
from contextlib import contextmanager
from hashlib import sha256
import json
import math
import os
import secrets
import uuid


def vector_literal(values):
    if len(values) != 768 or not all(math.isfinite(x) for x in values) or not any(values):
        raise ValueError('invalid embedding')
    return '[' + ','.join(str(float(x)) for x in values) + ']'


def provision_user(name):
    import psycopg
    token = secrets.token_urlsafe(32)
    with psycopg.connect(os.environ['ADMIN_DATABASE_URL']) as conn:
        conn.execute('INSERT INTO users(user_id,display_name,token_hash) VALUES (%s,%s,%s)',
                     (str(uuid.uuid4()), name, sha256(token.encode()).hexdigest()))
    return token


class Store:
    def __init__(self, token):
        import psycopg
        from psycopg.rows import dict_row
        self.conn = psycopg.connect(os.environ['DATABASE_URL'], autocommit=True, row_factory=dict_row)
        try:
            role = self.conn.execute('SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone()
            if role['rolsuper'] or role['rolbypassrls']:
                raise PermissionError('Application refuses superuser/BYPASSRLS database credentials')
            row = self.conn.execute('SELECT user_id FROM users WHERE token_hash=%s',
                                    (sha256(token.strip().encode()).hexdigest(),)).fetchone()
            if not row:
                raise PermissionError('Invalid user token')
            self.user_id = str(row['user_id'])
        except Exception:
            self.conn.close()
            raise

    def close(self):
        self.conn.close()

    @contextmanager
    def scoped(self):
        with self.conn.transaction():
            self.conn.execute("SELECT set_config('app.user_id', %s, true)", (self.user_id,))
            yield self.conn

    def ensure_model(self, identity):
        with self.scoped() as conn:
            conn.execute('INSERT INTO model_config(singleton,embedding_identity) VALUES (true,%s) ON CONFLICT DO NOTHING', (identity,))
            stored = conn.execute('SELECT embedding_identity FROM model_config').fetchone()['embedding_identity']
            if stored != identity:
                raise ValueError('Embedding model/digest changed. Use a fresh database and re-ingest; do not mix vector spaces.')

    def unchanged(self, record):
        with self.scoped() as conn:
            row = conn.execute('SELECT content_hash FROM emails WHERE user_id=%s AND email_id=%s',
                               (self.user_id, record.email_id)).fetchone()
            return bool(row and row['content_hash'] == record.content_hash)

    def replace(self, record, chunks, vectors):
        if len(chunks) != len(vectors):
            raise ValueError('chunk/vector count mismatch')
        literals = [vector_literal(v) for v in vectors]
        with self.scoped() as conn:
            # Serializes concurrent re-ingestion of the same identity (including first insert).
            conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                         (self.user_id + record.email_id,))
            conn.execute('DELETE FROM emails WHERE user_id=%s AND email_id=%s', (self.user_id, record.email_id))
            conn.execute('INSERT INTO emails VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)',
                         (self.user_id, record.email_id, record.content_hash, record.sender,
                          record.recipient, record.subject, record.sent_at, record.source_url,
                          json.dumps(record.warnings)))
            with conn.cursor() as cur:
                cur.executemany('INSERT INTO chunks VALUES (%s,%s,%s,%s,%s,%s::vector)',
                                [(self.user_id, record.email_id, i, part, content, literals[i])
                                 for i, (part, content) in enumerate(chunks)])

    def search(self, vector, question, limit=8, sender=None, subject=None, latest=False):
        """Cosine + full-text candidates; all filtering happens before ranking."""
        if latest and not sender:
            raise ValueError('Latest mode requires an explicit --sender filter')
        params = {'uid': self.user_id, 'v': vector_literal(vector), 'q': question,
                  'limit': max(1, min(limit, 30))}
        filters = ['e.user_id=%(uid)s']
        if sender:
            filters.append('position(lower(%(sender)s) in lower(e.sender)) > 0')
            params['sender'] = sender
        if subject:
            filters.append('position(lower(%(subject)s) in lower(e.subject)) > 0')
            params['subject'] = subject
        if latest:
            filters.append('e.sent_at IS NOT NULL')
        where = ' AND '.join(filters)
        # A static SQL fragment chosen by code, never interpolated user SQL.
        order = 'sent_at DESC, email_id, chunk_no' if latest else 'score DESC, email_id, chunk_no'
        query = f'''
        WITH candidates AS (
          SELECT c.email_id,c.chunk_no,c.part_name,c.content,e.sender,e.recipient,
                 e.subject,e.sent_at,e.source_url,
                 1 - (c.embedding <=> %(v)s::vector) AS similarity,
                 ts_rank_cd(to_tsvector('english',c.content),plainto_tsquery('english',%(q)s)) AS lexical
          FROM chunks c JOIN emails e ON e.user_id=c.user_id AND e.email_id=c.email_id
          WHERE {where}
        ), ranked AS (
          SELECT *, similarity + LEAST(lexical,1.0)*0.15 AS score FROM candidates
          WHERE similarity >= 0.35 OR lexical > 0 {'OR true' if latest else ''}
        ) SELECT * FROM ranked ORDER BY {order} LIMIT %(limit)s
        '''
        with self.scoped() as conn:
            return conn.execute(query, params).fetchall()

    def all_matching(self, subject):
        """Read every chunk for a literal subject filter, with an explicit safety cap."""
        if not subject or len(subject.strip()) < 3:
            raise ValueError('All-matching summary requires a subject filter of at least 3 characters')
        with self.scoped() as conn:
            rows = conn.execute("""
              SELECT c.email_id,c.chunk_no,c.part_name,c.content,e.sender,e.recipient,
                     e.subject,e.sent_at,e.source_url, 1.0 AS similarity
              FROM chunks c JOIN emails e ON e.user_id=c.user_id AND e.email_id=c.email_id
              WHERE e.user_id=%s AND position(lower(%s) in lower(e.subject)) > 0
              ORDER BY e.sent_at NULLS LAST,c.email_id,c.chunk_no LIMIT 501
            """, (self.user_id, subject)).fetchall()
        if len(rows) > 500:
            raise ValueError('More than 500 matching chunks; narrow --subject. No partial summary generated.')
        return rows

    def stats(self):
        with self.scoped() as conn:
            return conn.execute('SELECT (SELECT count(*) FROM emails) AS emails, (SELECT count(*) FROM chunks) AS chunks').fetchone()
