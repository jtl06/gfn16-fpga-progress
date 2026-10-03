import copy
import json
import unittest

from fpga.reference.stream27_r15_host_window_gmp_native import BASE,PARENT,CPP,VALIDATOR,sha
from fpga.reference.stream27_r15_host_window_gmp_output import expected,validate,values
from fpga.tools.native_class_package_v4 import source_identity


def captured_role(mode='normal'):
    """The final admission guard deliberately accepts only frozen identities.

    Do not re-emit the historical fixture through mutable admission helpers.
    """
    role = BASE / mode
    manifest = json.loads((role/'manifest.json').read_bytes())
    files = {name:(role/'source/fpga'/name).read_bytes()
             for name in manifest['sources']}
    if any(sha(files[name]) != pin for name,pin in manifest['sources'].items()):
        raise ValueError('captured fixture bytes changed')
    return manifest,files,json.loads((role/'production-bundle.json').read_bytes())


class SourceFixture(unittest.TestCase):
    def test_literal65_parent_and_runtime_before_only_DUT(self):
        m,files,bundle=captured_role()
        original=json.loads((PARENT/'manifest.json').read_bytes())
        self.assertEqual(m['build']['parameters'],original['build']['parameters'])
        self.assertEqual(m['probe'],original['probe'])
        self.assertEqual(m['build']['sv_sources'],original['build']['sv_sources'])
        self.assertEqual(m['build']['ldflags'],['-lgmpxx','-lgmp'])
        for n,t in bundle['files'].items():self.assertEqual(files['rtl/'+n],t.encode())
        cpp=files[CPP].decode()
        self.assertEqual(cpp.count('DUT d(&context)'),1)
        self.assertLess(cpp.index('gfn16_runtime::configure(context,argc,argv)'),cpp.index('DUT d(&context)'))
        self.assertIn('d.read_data[2]==upper',cpp)
        self.assertIn('d.dc_applied==i+1',cpp)
        self.assertNotIn('PROFILE_ACK',cpp)

    def test_existing_identity_binds_every_source_step_probe_and_ldflags(self):
        m,_,_=captured_role()
        self.assertEqual(source_identity(m),m['metadata']['r15_native_gmp']['fixture_sha256'])
        for key in ('build','steps','probe','sources'):
            bad=copy.deepcopy(m)
            if key=='sources':bad[key][CPP]='0'*64
            elif key=='steps':bad[key][0]['expected_returncode']=1
            elif key=='build':bad[key]['ldflags']=['-lgmp']
            else:bad[key]['requires_model_threads']=2
            # The hardened compiler can reject a changed fixture earlier than
            # digest comparison; either outcome proves no silently bound drift.
            try:
                changed = source_identity(bad)
            except ValueError:
                continue
            self.assertNotEqual(changed,source_identity(m))

    def test_independent_closed_form_cases_and_strict_output(self):
        for value,base,initial,chunk in zip(values(2),(1009,2017),(1,7),(11,6),strict=True):
            mod=base**256+1
            self.assertEqual(value,(pow(initial,256,mod)*pow(2,16*chunk+chunk,mod))%mod)
        self.assertFalse(validate(expected(),'',0)['board'])
        for changed in (expected().replace('board=0','board=1'),expected()+'x'):
            with self.assertRaises(ValueError):validate(changed,'',0)
        with self.assertRaises(ValueError):validate(expected(),'',True)

    def test_faults_are_separate_with_healthy_baseline_and_common_reset_limits(self):
        normal,_,_=captured_role('normal');faults,_,_=captured_role('faults')
        self.assertEqual(len(normal['steps']),1)
        self.assertEqual(len(faults['steps']),2)
        self.assertNotEqual(source_identity(normal),source_identity(faults))
        self.assertTrue(expected('rollback').startswith(expected()))
        self.assertFalse(validate(expected('rollback'),'',0,mode='rollback')['CDC'])
        self.assertFalse(validate(expected(),'R15_WINDOW_SIGNED96_ORACLE_WITNESS\n',1,
                                  mode='oracle-negative')['promotion'])
        self.assertFalse(faults['r15_host_window_gmp']['physical_reset_delivery'])


if __name__=='__main__':unittest.main()
