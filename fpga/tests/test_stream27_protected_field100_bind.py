import unittest
from reference import stream27_protected_field100_bind as candidate
from reference import stream27_context_storage_combo_timing10_bind as parent


class ProtectedFieldSource(unittest.TestCase):
    def test_disabled_is_exact_protected_R9(self):
        for n in (256,65536):self.assertEqual(candidate.prepare(n),parent.capture(n))

    def test_full_batch_reversal_and_immediate_fast(self):
        for n,interval in ((256,215),(65536,8461)):
            baseline=parent.prepare(n,enabled=1,lean_production=0)
            b=candidate.prepare(n,enabled=1,**{k.lower():1 for k in candidate.FLAGS})
            self.assertEqual(len(b['files']),58)
            self.assertEqual(b['geometry']['warm_interval'],interval)
            self.assertNotIn('LEAN_PRODUCTION',b['parameters'])
            for name,row in b['context_protected_field100']['source_edits'].items():
                self.assertEqual(candidate.reverse(b['files'][row['new_file']],row['edits']),baseline['files'][name])
            fields=[text for name,text in b['files'].items() if name.startswith('genefer_stream27_shared_warm_aw')]
            self.assertEqual(len(fields),3)
            for text in fields:
                self.assertIn('wire stop=out_error_fast;',text)
                self.assertIn('assign out_error_fast=protocol_error;',text)
                self.assertIn('controller_error<=out_error_fast;',text)
                self.assertIn('FIELD100_REPORT_COPY_ALIGNMENT_NOT_FAST_ORIGIN',text)
                self.assertNotIn('if(!stop && (admission_bad || join_bad || (|child_pending)',text)
            arith=next(t for name,t in b['files'].items() if name.startswith('genefer_stream27_threefield_carry_aw'))
            self.assertIn('error_barrier=out_error || (|field_fast) || local_fault_q;',arith)
            self.assertIn('if((|field_error) || local_fault_q)out_error<=1;',arith)
            self.assertIn('.in_valid(doubled_valid && !carry_quarantine_q)',arith)
            warm=next(t for name,t in b['files'].items() if name.startswith('genefer_stream27_warm_contexts_aw'))
            self.assertIn('if(child_barrier || collision || count_bad || command_bad || cold_request_bad)local_error<=1;',warm)
            host=b['files'][b['top']+'.sv']
            oldhost=baseline['files'][baseline['top']+'.sv']
            for marker in ('   // Hold the scratch lease','   if(publish_pending)begin'):
                self.assertIn(marker,host)
            # Full56 proposal/drain and one-shot are literal parent sections.
            for begin,end in (('   if(publish_pending)begin','   if(shadow_commit_ack'),
                              (' wire second_cold_due',' wire cold_correction')):
                if begin in oldhost and end in oldhost:
                    self.assertEqual(host.split(begin,1)[1].split(end,1)[0],oldhost.split(begin,1)[1].split(end,1)[0])

    def test_no_partial_or_lean_switch(self):
        with self.assertRaisesRegex(ValueError,'ONE_CLOSED_BATCH'):candidate.prepare(256,enabled=1)
        with self.assertRaisesRegex(ValueError,'CLOSED_FLAG'):candidate.prepare(256,enabled=1,lean_production=1)


if __name__=='__main__':unittest.main()
