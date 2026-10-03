import unittest
from fpga.reference import stream27_context_storage_combo_registerederror_bind as candidate
from fpga.reference import stream27_context_storage_combo_directbound_bind as direct


class RegisteredErrorSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parents={n:candidate.prepare(n) for n in (256,65536)}
        cls.candidates={n:candidate.bind(parent,enabled=1) for n,parent in cls.parents.items()}

    def test_default_exact_and_every_transformed_byte_reverse(self):
        for n,parent in self.parents.items():
            self.assertEqual(candidate.bind(parent),parent)
            out=self.candidates[n];db=direct.bind(parent,enabled=1)
            meta=out['context_registered_error']
            for name,ops in meta['reversal_records'].items():
                original=candidate.restore(out['files'][name],ops)
                old_name=next(key for key,value in db['files'].items() if value==original)
                self.assertEqual(original,db['files'][old_name])
            self.assertEqual(len(out['files']),55)
            self.assertEqual(out['geometry'],parent['geometry'])
            self.assertEqual(out['two_context_schedule'],parent['two_context_schedule'])
            self.assertEqual(out['parameters'],dict(parent['parameters'],CANONICAL_C0_DIRECT=1,ERROR_AGGREGATION_REGISTERED=1))

    def test_registered_fault_sources_and_publication_fence(self):
        for out in self.candidates.values():
            host=out['files'][out['top']+'.sv']
            self.assertIn(candidate.PUB_DRAIN,host)
            self.assertIn('assign safety_error=local_error || child_error_barrier || canon_error;',host)
            self.assertIn(candidate.PUBLIC_ERROR,host)
            self.assertIn('output logic error,',host)
            self.assertIn('assign read_valid=shadow_scalar_valid && canonical_ready[shadow_scalar_context] && !safety_error;',host)
            arith=next(body for name,body in out['files'].items() if name.startswith('genefer_stream27_threefield_carry_aw'))
            self.assertIn(candidate.ARITH_SUMMARY,arith)
            self.assertIn(candidate.LOCAL_FF,arith)
            self.assertIn('if(fault_pending)out_error<=1;',arith)
            self.assertNotIn('!out_error',arith)
            self.assertEqual(out['context_registered_error']['joint_publication_delta'],[1,2])
            self.assertTrue(out['context_registered_error']['full56_publication_owner_count_lease_check'])


if __name__=='__main__':
    unittest.main()
