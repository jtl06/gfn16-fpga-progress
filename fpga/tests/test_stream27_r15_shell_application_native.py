import unittest
from fpga.reference import stream27_r15_shell_application_native as own


class R15ApplicationNativeTests(unittest.TestCase):
    def test_own_literal_component_domain_reset_and_passive_observer(self):
        manifest,files,bundle=own.role()
        self.assertEqual(len(bundle['files']),70)
        self.assertEqual(len(manifest['build']['sv_sources']),71)
        self.assertEqual(manifest['build']['parameters']['PCIE_SHELL'],1)
        self.assertEqual(manifest['build']['parameters']['EPOCH_SEED0'],65534)
        self.assertIn('.EPOCH_SEED0(EPOCH_SEED0)',files['rtl/'+own.TOP+'.sv'].decode())
        self.assertIn('candidate.compute.direct_cold.admitted_start',files['rtl/'+own.TOP+'.sv'].decode())
        self.assertFalse(manifest['r15_shell_application_native']['vendor_HIP_PLL_simulated'])
        self.assertEqual(manifest['sources'],{n:own.sha(v) for n,v in files.items()})

    def test_driver_uses_bus_authority_and_one_explicit_runtime_context(self):
        cpp=(own.ROOT/own.CPP).read_text()
        self.assertEqual(cpp.count('DUT d(&context)'),1)
        self.assertLess(cpp.index('gfn16_runtime::configure'),cpp.index('DUT d(&context)'))
        for text in ('!d.ctrl_waitrequest','!d.cold_waitrequest','!d.export_waitrequest',
          'd.ctrl_readdatavalid','d.export_readdatavalid','0x52315000u','0x52314100u',
          'R15_APPLICATION_FRESH_ERROR_FENCE','R15_APPLICATION_GLOBAL_LATEST_BEGIN_LEASE'):
            self.assertIn(text,cpp)
        self.assertNotIn('d.dc_',cpp)

    def test_typed_normal_is_exact_and_scope_bounded(self):
        value=own.validate(own.FOOTER,'',0,own.config(),{})
        self.assertEqual(value['status'],'PASS_expected_contracts')
        self.assertFalse(value['promotion_allowed'])
        with self.assertRaises(ValueError):own.validate(own.FOOTER,'',1,own.config(),{})


if __name__=='__main__':unittest.main()
