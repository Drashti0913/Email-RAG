import base64
from pathlib import Path
import mailbox
import unittest
from unittest.mock import MagicMock
from email_rag.gmail import messages
from email_rag.parsing import parse_email
from email_rag.pipeline import summarize_all
from test_core import hit


class GmailTests(unittest.TestCase):
    def service(self):
        service=MagicMock()
        service.users.return_value.getProfile.return_value.execute.return_value={'emailAddress':'alice@example.test'}
        return service

    def test_wrong_account_rejected(self):
        with self.assertRaises(ValueError):list(messages(self.service(),'bob@example.test'))

    def test_pagination_and_raw_attachment_preservation(self):
        service=self.service()
        raw=(Path(__file__).resolve().parents[1]/'sample_data/alice/a02-api.eml').read_bytes()
        service.users.return_value.messages.return_value.list.return_value.execute.side_effect=[
            {'messages':[{'id':'m1'}],'nextPageToken':'next'}, {'messages':[{'id':'m2'}]}]
        service.users.return_value.messages.return_value.get.return_value.execute.side_effect=[
            {'raw':base64.urlsafe_b64encode(raw).decode().rstrip('='),'threadId':'thread1'},
            {'raw':base64.urlsafe_b64encode(raw).decode(),'threadId':'thread2'}]
        values=list(messages(service,'alice@example.test',limit=2))
        self.assertEqual(len(values),2)
        self.assertEqual(values[0][0],raw)
        self.assertIn('alice%40example.test',values[0][2])
        self.assertIn('5 retries',parse_email(values[0][0]).parts[-1][1])

    def test_mbox_sample_count(self):
        path=Path(__file__).resolve().parents[1]/'sample_data/alice.mbox'
        box=mailbox.mbox(path,create=False)
        try:
            records=[parse_email(box.get_bytes(k,from_=False)) for k in box.iterkeys()]
        finally:box.close()
        self.assertEqual(len(records),7)
        self.assertEqual(len({x.email_id for x in records}),7)


class SummaryTests(unittest.TestCase):
    def test_all_chunks_covered_across_batches(self):
        hits=[]
        for i in range(40):
            h=hit();h['chunk_no']=i;h['content']='evidence '*180;hits.append(h)
        store=MagicMock();store.all_matching.return_value=hits
        models=MagicMock();models.generate.return_value={'response':'Summary without citations'}
        result=summarize_all(store,models,'Summarize all launches','launch')
        self.assertEqual(result['coverage']['chunks'],40)
        self.assertEqual(len(result['sources']),40)
        self.assertGreater(result['coverage']['batches'],1)
        self.assertEqual(result['sources'][-1]['label'],'S40')
        self.assertTrue(result['warnings'])

    def test_empty_all_matching_no_model_call(self):
        store=MagicMock();store.all_matching.return_value=[];models=MagicMock()
        result=summarize_all(store,models,'Summarize launch','launch')
        models.generate.assert_not_called()
        self.assertEqual(result['sources'],[])


if __name__=='__main__':unittest.main()
