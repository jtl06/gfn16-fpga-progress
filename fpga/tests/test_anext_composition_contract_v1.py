import unittest
from fpga.reference.anext_composition_contract_v1 import root_contract,schedule,compatible_host_protocol


class Composition(unittest.TestCase):
    def test_root_domains_and_f2_incompatibility(self):
        c=root_contract()
        self.assertEqual(c['profile_format'],3)
        self.assertTrue(c['final_upper_normalizer'])
        self.assertFalse(c['seed_recurrence_present'])
        with self.assertRaisesRegex(ValueError,'NO_RECURRENCE'):
            root_contract(recurrence_f2=True)

    def test_full_size_is_event_only(self):
        c=schedule(16)
        self.assertEqual((c['ntt_controller_cycles'],c['warm_backend'],c['warm_host']),(17709,21872,21874))
        self.assertEqual((c['cold_cached_backend'],c['cold_loaded_backend']),(25980,25989))
        self.assertEqual(c['ram_to_ram_displacement'],52)
        self.assertEqual(c['same_address_collisions'],0)
        self.assertFalse(c['native_measured'])

    def test_small_budgets_and_port_change_refusal(self):
        self.assertEqual(schedule(5)['ntt_controller_cycles'],114)
        self.assertEqual(schedule(8)['ntt_controller_cycles'],193)
        with self.assertRaises(ValueError):schedule(16,block_response_edges=2)
        with self.assertRaises(ValueError):schedule(16,independent_read_write=False)

    def test_host_abi_is_not_silently_inherited(self):
        self.assertFalse(compatible_host_protocol('T5b_pulse_load_read_start','A4b_cmd_ready_rsp_valid')['drop_in'])


if __name__=='__main__':unittest.main()
