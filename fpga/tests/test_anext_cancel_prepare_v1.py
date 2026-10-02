import copy
import unittest
from fpga.reference import anext_cancel_prepare_v1 as prep


class CancelFiniteRole(unittest.TestCase):
    def test_closed_source_exact_paired_RTL_and_bounded_geometry(self):
        for aw in (5,8):
            manifest,files=prep.role(aw)
            self.assertEqual(manifest['build']['parameters'],dict(AW=aw))
            self.assertEqual(len(manifest['build']['sv_sources']),13)
            self.assertTrue(set(manifest['build']['sv_sources']+[manifest['build']['cpp_source']])<=files.keys())
            self.assertTrue(manifest['cancel_distribution']['ledger']['preserved_recovery_failure'])
        for bad in (4,16,True):
            with self.assertRaisesRegex(ValueError,'GEOMETRY'):prep.native.counts(bad)

    def test_exact_derived_counter_calendar_contracts(self):
        for aw,commands,reads,ticks,maximum in ((5,253,44,3293,100),(8,1821,268,18371,524)):
            counts=prep.native.counts(aw)
            self.assertEqual((counts['commands'],counts['readbacks'],counts['ticks'],counts['max_latency']),
                (commands,reads,ticks,maximum))
            for negative in (False,True):
                c=prep.native.contracts(aw)['negative' if negative else 'normal']
                self.assertEqual(prep.native.validate(c['stdout'],c['stderr'],c['returncode'],dict(aw=aw,negative=negative),{})['status'],
                    'PASS_expected_contracts')

    def test_counter_mutant_and_wrong_nonzero_contract_rejected(self):
        c=prep.native.contracts(5)['normal']
        with self.assertRaisesRegex(ValueError,'TYPED_OUTPUT'):
            prep.native.validate(c['stdout'].replace('cancel_seams=4','cancel_seams=0'),'',0,dict(aw=5,negative=False),{})
        with self.assertRaisesRegex(ValueError,'TYPED_OUTPUT'):
            prep.native.validate('','arbitrary failure\n',1,dict(aw=5,negative=True),{})

    def test_no_square_no_cancel_reset_and_compiler_dependency_header(self):
        prep.native.verify();cpp=(prep.ROOT/prep.native.CPP).read_text()
        self.assertIn('ANEXT_CANCEL_NO_SQUARE_ENGINE',cpp);self.assertIn('ANEXT_CANCEL_HOST_E2',cpp)
        self.assertNotIn('boost/',cpp)
        for marker in ('ANEXT_CANCEL_NO_HOST_FALLBACK_OR_COMMIT','ANEXT_CANCEL_LATER_FAULT_HELD_SUCCESS',
            'ANEXT_CANCEL_IMAGE_SAME_EDGE_KILL','ANEXT_CANCEL_PRIOR_COMMIT_NOT_ROLLED_BACK','ANEXT_CANCEL_RESET_ELIGIBILITY'):
            self.assertIn(marker,cpp)


if __name__=='__main__':unittest.main()
