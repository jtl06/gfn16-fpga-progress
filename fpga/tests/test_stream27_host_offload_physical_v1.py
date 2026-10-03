import unittest
from fpga.reference import stream27_host_offload_physical_v1 as physical
from fpga.reference import stream27_host_offload_chip_v1 as chip


class PhysicalSource(unittest.TestCase):
    def test_exact_chip_and_parameter_virtual_controls(self):
        b=chip.prepare(65536,host_offload=1)
        m,files,spec=physical.build()
        self.assertEqual(m['source_sha256'],b['generated_sha256'])
        self.assertEqual(m['core_parameters']['HOST_OFFLOAD'],1)
        self.assertEqual(m['clock_period_ns'],12.0)
        self.assertEqual(len(spec['transfers']),30)
        self.assertEqual(m['host_offload']['cold_residue_storage_bits'],10616832)
        self.assertTrue(m['host_offload']['matched_equivalence_REQUIRED'])
        qsf=files['probe.qsf'].decode()
        self.assertIn('set_parameter -name HOST_OFFLOAD 1',qsf)
        for port in ('off_raw_ready','off_boundary_ready','off_error','off_index[*]','off_limit[*]','off_raw_owner[*]'):
            self.assertIn('VIRTUAL_PIN ON -to {'+port+'}',qsf)
        self.assertEqual(qsf.count('SYSTEMVERILOG_FILE'),66)
        self.assertIn(b'-period 12.000',files['probe.sdc'])

    def test_raw_boundary_not_old_shadow_and_settings_closed(self):
        m,files,spec=physical.build(period=11.5,seed=2)
        ids={t['id'] for t in spec['transfers']}
        self.assertTrue({'B_cold_registered_packet','B_profile_binding','B_final_packet'}<=ids)
        self.assertNotIn('copy_to_shadow_publication',ids)
        self.assertEqual(m['seed'],2)
        self.assertIn(b'-period 11.500',files['probe.sdc'])
        with self.assertRaises(ValueError):physical.build(period=10.0)


if __name__=='__main__':unittest.main()
