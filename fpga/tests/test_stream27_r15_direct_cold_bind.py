import json
from pathlib import Path
import unittest
from fpga.reference.stream27_r15_direct_cold_bind import bind

ROOT=Path(__file__).resolve().parents[1]


class BindTests(unittest.TestCase):
    def test_loader_fences_session_and_conflicting_commands(self):
        source=(ROOT/'rtl/kernel/genefer_stream27_r15_raw_loader_v1.sv').read_text()
        self.assertIn('session_seen && current_session!=reset_session',source)
        self.assertIn('session_seen && (!link_drained || current_session!=reset_session)',source)
        self.assertIn('(cancel && (!cancel_ok || begin_valid || word_valid || commit_valid))',source)
        self.assertIn('.link_drained(link_drained && !stop && !command_bad',source)
        self.assertIn('ack_count==(AW+1)\'(N) && !image_ack_expected',source)
        self.assertIn('profile[255:64]==0',source)

    def test_literal_off_both_geometries_and_private_source_roles(self):
        for role in ('aw8-normal','full-normal-v2'):
            b=json.loads((ROOT/'results/throughput-20260929/trackS-c2-protected-field100-native-v1'/role/'production-bundle.json').read_text())
            self.assertEqual(bind(b),b)
            out=bind(b,direct_cold=1)
            self.assertEqual(len(out['files']),63)
            self.assertTrue(all(out['files'][k]==v for k,v in b['files'].items()))
            self.assertTrue(out['r15_host_port_instrumentation']['literal_reversal'])
            top=out['files'][out['top']+'.sv']
            self.assertIn('DIRECT_COLD=0',top)
            self.assertIn('.load_we(image_write)',top)
            self.assertIn('.start_contexts(admitted_start)',top)
            self.assertIn('.initial_c0(saved_c0)',top)
            self.assertIn('dc_link_drained && !dc_error',top)
            self.assertFalse(out['r15_host_link']['real_pcie_ip_ready'])
            with self.assertRaisesRegex(ValueError,'PCIE_NOT_READY'):bind(b,direct_cold=1,pcie_shell=1)


if __name__=='__main__': unittest.main()
