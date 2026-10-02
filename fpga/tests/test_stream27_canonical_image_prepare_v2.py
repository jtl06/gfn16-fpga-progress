"""Dependency-only source delta and independent small oracle corpus gate."""
import unittest
from fpga.reference import stream27_canonical_image_native_v1 as old
from fpga.reference import stream27_canonical_image_native_v2 as native
from fpga.reference import stream27_canonical_image_prepare_v1 as parent
from fpga.reference import stream27_canonical_image_prepare_v2 as prep


class OracleSuccessor(unittest.TestCase):
    def test_source_delta_and_retained_failure_sources(self):
        pins=native.verify()
        self.assertEqual(pins[old.CPP],old.PINS[old.CPP])
        self.assertEqual(pins[native.SV],old.PINS[old.SV])
        self.assertEqual(pins[native.RAM],old.PINS[old.RAM])

    def test_all_independent_corpus_checksums(self):
        for key,value in {(5,8):367782048,(5,16):225397866,(8,8):733474707,(8,16):163006797}.items():
            self.assertEqual(native.corpus.checksum(*key),value)
        with self.assertRaisesRegex(ValueError,'SMALL_ONLY'):native.corpus.checksum(16,8)

    def test_role_only_cpp_checksum_and_validator_source_delta(self):
        for aw in (5,8):
            for p in (8,16):
                a,_=parent.role(aw,p);b,files=prep.role(aw,p)
                self.assertEqual(a['build']['sv_sources'],b['build']['sv_sources'])
                self.assertEqual(a['build']['parameters'],b['build']['parameters'])
                self.assertEqual(a['build']['cflags'],b['build']['cflags'][:-1])
                self.assertEqual(b['build']['cflags'][-1],f'-DCANON_ORACLE_CHECKSUM={native.corpus.checksum(aw,p)}')
                self.assertEqual(b['build']['cpp_source'],native.CPP)
                self.assertIn(old.CPP,files)
                self.assertEqual(a['probe'],b['probe'])
                for x,y in zip(a['steps'],b['steps']):
                    self.assertEqual({k:v for k,v in x.items() if k!='validator'}, {k:v for k,v in y.items() if k!='validator'})
                    self.assertEqual(x['validator']['config'],y['validator']['config'])
                self.assertEqual(old.contracts(aw,p)['normal'],native.contracts(aw,p)['normal'])
                self.assertEqual(old.contracts(aw,p)['counts'],native.contracts(aw,p)['counts'])
                self.assertEqual(old.contracts(aw,p)['negative']['stderr'].replace('actual=','actual=0:0:'),
                                 native.contracts(aw,p)['negative']['stderr'])

    def test_exact_normal_and_negative_contracts_unchanged(self):
        for aw,p in ((5,8),(5,16),(8,8),(8,16)):
            for negative in (False,True):
                expected=native.contracts(aw,p)['negative' if negative else 'normal']
                config=dict(aw=aw,p=p,negative=negative)
                self.assertEqual(native.validate(expected['stdout'],expected['stderr'],expected['returncode'],config,{})['status'],'PASS_expected_contracts')
                with self.assertRaisesRegex(ValueError,'TYPED_OUTPUT'):
                    native.validate(expected['stdout']+'wrong\n',expected['stderr'],expected['returncode'],config,{})


if __name__=='__main__':unittest.main()
