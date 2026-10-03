import unittest
from fpga.reference import stream27_r15_shell_application_v4_native as own


class R15AppV4NormalTests(unittest.TestCase):
    def test_both_literal_components_actual_v8_and_passive_observers(self):
        for stage in own.ROLES:
            with self.subTest(stage=stage):
                m,f,b,r=own.role(stage)
                self.assertEqual(len(b['files']),70)
                self.assertEqual(len(m['build']['sv_sources']),71)
                self.assertIn('external_fault_valid',f['rtl/'+r['top']+'.sv'].decode())
                self.assertIn('d.external_fault_valid=0;',f[m['build']['cpp_source']].decode())
                self.assertEqual(m['build']['parameters']['EPOCH_SEED0'],0 if stage=='full' else 65534)
                self.assertFalse(m['r15_shell_application_native']['host_GL_implemented'])
                self.assertEqual(m['sources'],{n:own.sha(v) for n,v in f.items()})

    def test_typed_contract_rejects_old_version_config(self):
        for stage in own.ROLES:
            cfg=own.config(stage);self.assertEqual(own.validate(own.FOOTERS[stage],'',0,cfg,{})['status'],'PASS_expected_contracts')
            cfg['application_version']=2
            with self.assertRaises(ValueError):own.validate(own.FOOTERS[stage],'',0,cfg,{})


if __name__=='__main__':unittest.main()
