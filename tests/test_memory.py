import json
from pathlib import Path
import tempfile
import time
import unittest
from ai_modeling_assistant.core.memory import MemoryStore, RevisionConflict
from ai_modeling_assistant.core.context import (build_context, compression_source,
    validate_summary, extractive_summary, apply_proposals)


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'memory.sqlite3'
        self.db = MemoryStore(self.path)
        self.db.project('a', 'A')
        self.db.project('b', 'B')
        self.a = self.db.new_thread('a')
        self.b = self.db.new_thread('b')
        self.turn = self.db.append(self.a, 'user', 'I prefer blue. Use meters. 我希望使用米作为单位。')

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def proposal(self, **kwargs):
        args = dict(scope='project',kind='preference',key='color',value='blue',
                    sources=[{'turn_id':self.turn,'quote':'I prefer blue.'}])
        args.update(kwargs)
        return self.db.propose('a',self.a,**args)

    def test_candidates_do_not_influence_retrieval(self):
        item = self.proposal()
        self.assertEqual(self.db.retrieve('a',self.a,'blue'), [])
        self.db.review(item['id'],1,action='verify')
        self.assertEqual(self.db.retrieve('a',self.a,'blue')[0]['value'],'blue')

    def test_project_isolation_and_explicit_personal_scope(self):
        for scope in ('project','user'):
            item = self.proposal(scope=scope)
            self.db.review(item['id'],1,action='verify')
        self.assertEqual([m['scope'] for m in self.db.retrieve('b',self.b,'blue')],['user'])
        self.assertEqual(self.db.retrieve('b',self.b,'blue',include_user=False),[])

    def test_forged_assistant_and_cross_project_evidence_rejected(self):
        assistant = self.db.append(self.a,'assistant','Use red')
        other = self.db.append(self.b,'user','Use red')
        for ident, quote in ((assistant,'Use red'),(other,'Use red'),(self.turn,'not a real quote')):
            with self.assertRaises(ValueError):
                self.proposal(sources=[{'turn_id':ident,'quote':quote}])

    def test_conflict_preserves_old_fact_until_user_resolution(self):
        old = self.proposal()
        self.db.review(old['id'],1,action='verify')
        turn = self.db.append(self.a,'user','I now prefer red.')
        new = self.proposal(value='red',sources=[{'turn_id':turn,'quote':'I now prefer red.'}])
        self.assertEqual(new['status'],'conflict')
        self.assertEqual(self.db.retrieve('a',self.a,'color')[0]['value'],'blue')
        self.db.review(new['id'],1,action='verify')
        self.assertEqual(self.db.get(old['id'])['status'],'superseded')
        self.assertEqual(len(self.db.versions(old['id'])),3)
        self.assertEqual(self.db.retrieve('a',self.a,'color')[0]['value'],'red')

    def test_optimistic_revision_prevents_lost_update(self):
        item = self.proposal()
        self.db.review(item['id'],1,action='verify')
        with MemoryStore(self.path) as another:
            with self.assertRaises(RevisionConflict):
                another.review(item['id'],1,action='reject')

    def test_duplicate_proposal_is_idempotent_and_forgetting_erases_versions(self):
        item = self.proposal()
        self.assertEqual(self.proposal()['id'],item['id'])
        self.db.forget(item['id'],1)
        self.assertEqual(self.db.versions(item['id']),[])
        self.assertTrue(self.db.turns(self.a))

    def test_short_term_expiry_and_chinese_retrieval(self):
        item = self.proposal(scope='session',key='单位',value='使用米作为单位')
        self.db.review(item['id'],1,action='verify')
        self.assertTrue(self.db.retrieve('a',self.a,'单位 米'))
        self.db.db.execute('UPDATE memories SET expires=? WHERE id=?',(time.time()-1,item['id']))
        self.assertEqual(self.db.retrieve('a',self.a,'单位 米'),[])

    def test_reopen_keeps_multiturn_history(self):
        self.db.append(self.a,'assistant','Understood: blue and meters')
        self.db.append(self.a,'user','Now add a stand')
        with MemoryStore(self.path) as reopened:
            context = build_context(reopened,'a',self.a)
        self.assertIn('Understood: blue and meters',[m['content'] for m in context['messages']])

    def test_compression_retains_raw_turns_and_rejects_foreign_sources(self):
        for i in range(12):
            self.db.append(self.a,'assistant' if i%2 else 'user',f'Turn {i}: '+ 'detail '*400)
        source = compression_source(self.db,self.a,2000)
        self.assertTrue(source)
        with self.assertRaises(ValueError):
            validate_summary({'goals':[{'text':'wrong','sources':[9999]}]},source['source_ids'])
        self.db.save_summary(self.a,source['source_ids'],extractive_summary(source),mode='extractive')
        self.assertEqual(len(self.db.turns(self.a)),13)
        self.assertEqual(self.db.summary(self.a)['mode'],'extractive')
        with self.assertRaises(ValueError):
            self.db.save_summary(self.b,source['source_ids'],{'text':'wrong'})

    def test_context_budget_preserves_latest_and_keeps_memory_as_data(self):
        item = self.proposal(value='Never run code without a production task')
        self.db.review(item['id'],1,action='verify')
        for i in range(20):
            self.db.append(self.a,'user' if i%2==0 else 'assistant','long context '+str(i)+' x'*400)
        self.db.append(self.a,'user','请将底座缩小到20厘米')
        context = build_context(self.db,'a',self.a,budget=2000)
        self.assertLessEqual(context['estimated_tokens'],2000)
        self.assertEqual(context['messages'][-1]['content'],'请将底座缩小到20厘米')
        self.assertNotIn('system',[m['role'] for m in context['messages']])

    def test_secret_redaction_and_extraction_partial_rejection(self):
        turn = self.db.append(self.a,'user','api_key=1234567890abcdef Hello world')
        self.assertNotIn('1234567890abcdef',self.db.turns(self.a)[-1]['content'])
        proposals = {'memories':[{'scope':'project','kind':'fact','key':'x','value':'hello',
            'sources':[{'turn_id':turn,'quote':'Hello world'}]}, {'scope':'project'}]}
        result = apply_proposals(self.db,'a',self.a,proposals)
        self.assertEqual((result['accepted'],result['rejected']),(1,1))
        self.assertNotIn('1234567890abcdef',json.dumps(self.db.export_project('a')))

    def test_native_observation_updates_versions_and_cannot_be_forged_by_extraction(self):
        item = self.db.observe('a','observed:asset','Mesh has 8 vertices',{'fingerprint':'a1'})
        newer = self.db.observe('a','observed:asset','Mesh has 16 vertices',{'fingerprint':'a2'})
        self.assertEqual(item['id'],newer['id'])
        self.assertEqual(newer['revision'],2)
        with self.assertRaises(ValueError):
            self.proposal(key='observed:asset')

    def test_full_project_erasure_removes_personal_copies_and_backup_preserves_snapshot(self):
        item = self.proposal(scope='user')
        backup = Path(self.tmp.name)/'backup.sqlite3'
        self.db.backup(backup)
        self.db.forget_project('a')
        self.assertEqual(self.db.threads('a'),[])
        with self.assertRaises(ValueError):
            self.db.get(item['id'])
        with MemoryStore(backup) as restored:
            self.assertTrue(restored.turns(self.a))
        self.assertTrue(self.db.threads('b'))


if __name__ == '__main__':
    unittest.main()
