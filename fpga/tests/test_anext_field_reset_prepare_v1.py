import unittest
from fpga.reference import anext_field_reset_prepare_v1 as prep


class FieldResetFiniteRole(unittest.TestCase):
    def test_closed_sevenSV_role_all_fields_no_wholeengine(self):
        for aw in (5,8):
            m,files=prep.role(aw)
            self.assertEqual(len(m['build']['sv_sources']),7)
            self.assertTrue(set(m['build']['sv_sources']+[m['build']['cpp_source']])<=files.keys())
            self.assertEqual(m['build']['parameters'],dict(AW=aw));self.assertEqual(len(m['steps']),4)
            self.assertFalse(m['field_reset']['native_executed'])
            self.assertNotIn('genefer_anext_upper_block_engine_v1.sv',m['build']['sv_sources'])

    def test_exact_normal_and_three_nonzero_typed_contracts(self):
        for aw in (5,8):
            for c in prep.native.probe.role_config(aw)['cases']:
                result=prep.native.validate(c['expected_stdout'],c['expected_stderr'],c['expected_exit'],dict(aw=aw,case=c['name']),{})
                self.assertEqual(result['status'],'PASS_expected_contracts');self.assertFalse(result['promotion_allowed'])

    def test_counter_mutant_untyped_failure_and_missing_baseline_rejected(self):
        c=prep.native.probe.role_config(5)['cases'][0]
        for text,err,rc in ((c['expected_stdout'].replace('release_edges=2','release_edges=1'),'',0),
                            ('','arbitrary failure\n',41)):
            with self.assertRaisesRegex(ValueError,'TYPED_OUTPUT'):
                prep.native.validate(text,err,rc,dict(aw=5,case='positive'),{})
        c=prep.native.probe.role_config(5)['cases'][1]
        with self.assertRaisesRegex(ValueError,'TYPED_OUTPUT'):
            prep.native.validate('',c['expected_stderr'],41,dict(aw=5,case=c['name']),{})


if __name__=='__main__':unittest.main()
