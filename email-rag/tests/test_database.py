"""Run against a fresh local database with RUN_DB_TESTS=1. No LLM needed.

Requires DATABASE_URL (rag_app) and ADMIN_DATABASE_URL (postgres).
Creates only uniquely named test tenants and removes them afterward.
"""
import os
import unittest
import uuid
from email_rag.parsing import parse_email, chunks_for
from email_rag.store import Store, provision_user

VECTOR = [1.0] + [0.0] * 767


@unittest.skipUnless(os.getenv('RUN_DB_TESTS') == '1', 'requires local PostgreSQL + pgvector')
class DatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.alice = Store(provision_user('test-a-' + uuid.uuid4().hex))
        cls.bob = Store(provision_user('test-b-' + uuid.uuid4().hex))
        cls.a = parse_email(b'Message-ID: <same-id>\nFrom: Marketing <marketing@example.test>\nSubject: Product launch\nDate: Mon, 21 Sep 2026 10:00:00 +0000\n\nAlice public launch.')
        cls.b = parse_email(b'Message-ID: <same-id>\nFrom: Finance <finance@example.test>\nSubject: Private secret\nDate: Mon, 21 Sep 2026 10:00:00 +0000\n\nCOBALT-731 Bob only.')
        for store,record in [(cls.alice,cls.a),(cls.bob,cls.b)]:
            pieces=chunks_for(record);store.replace(record,pieces,[VECTOR]*len(pieces))

    @classmethod
    def tearDownClass(cls):
        import psycopg
        for store in (cls.alice,cls.bob):
            with store.scoped() as conn:
                conn.execute('DELETE FROM emails')
            with psycopg.connect(os.environ['ADMIN_DATABASE_URL']) as conn:
                conn.execute('DELETE FROM users WHERE user_id=%s',(store.user_id,))
            store.close()

    def test_rls_unfiltered_select(self):
        with self.alice.scoped() as conn:
            rows=conn.execute('SELECT user_id,content FROM chunks').fetchall()
        self.assertTrue(rows)
        self.assertTrue(all(str(x['user_id'])==self.alice.user_id for x in rows))
        self.assertFalse(any('COBALT-731' in x['content'] for x in rows))

    def test_explicit_other_user_query_empty(self):
        with self.alice.scoped() as conn:
            rows=conn.execute('SELECT * FROM chunks WHERE user_id=%s',(self.bob.user_id,)).fetchall()
        self.assertEqual(rows,[])

    def test_no_scope_empty(self):
        self.assertEqual(self.alice.conn.execute('SELECT * FROM chunks').fetchall(),[])

    def test_cross_user_insert_denied(self):
        import psycopg
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.alice.scoped() as conn:
                conn.execute("INSERT INTO emails(user_id,email_id,content_hash,sender,recipient,subject,source_url) VALUES (%s,'intrusion','x','','','','')",(self.bob.user_id,))

    def test_invalid_token_denied(self):
        with self.assertRaises(PermissionError):Store('not-a-valid-token')

    def test_vector_retrieval_scoped(self):
        rows=self.alice.search(VECTOR,'COBALT-731')
        self.assertFalse(any('COBALT-731' in x['content'] for x in rows))
        self.assertTrue(any('COBALT-731' in x['content'] for x in self.bob.search(VECTOR,'COBALT-731')))

    def test_idempotent_replace_and_latest(self):
        pieces=chunks_for(self.a)
        self.alice.replace(self.a,pieces,[VECTOR]*len(pieces))
        self.alice.replace(self.a,pieces,[VECTOR]*len(pieces))
        self.assertEqual(self.alice.stats()['emails'],1)
        self.assertEqual(self.alice.stats()['chunks'],len(pieces))
        rows=self.alice.search(VECTOR,'last marketing update',sender='marketing',latest=True)
        self.assertEqual(rows[0]['email_id'],self.a.email_id)

    def test_summary_filter(self):
        self.assertEqual(len(self.alice.all_matching('Product launch')),1)
        self.assertEqual(self.alice.all_matching('Private secret'),[])


if __name__=='__main__':unittest.main()
