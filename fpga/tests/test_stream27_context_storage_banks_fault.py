import unittest
from fpga.reference import stream27_context_storage_banks_fault as fault


class StorageFaultTests(unittest.TestCase):
    def test_exact_production_for_ports_reset_owner_oracle(self):
        for mode in ('external','reset','owner','oracle'):
            manifest, files = fault.role(mode)
            self.assertTrue(manifest['storage2_fault']['production_rtl_unchanged'])
            self.assertEqual(len(manifest['build']['sv_sources']), 53)
            self.assertFalse(manifest['storage2_fault']['shared_fault_peer_recovery'])
            self.assertEqual(manifest['build']['parameters']['EPOCH_SEED0'], 65534)
            self.assertEqual(manifest['probe']['expected_json']['expected_threads'], 1)

    def test_source_bound_actual_generated_abi_and_reset_events(self):
        manifest, files = fault.role('reset')
        cpp = files[fault.CPP].decode()
        self.assertIn('STORAGE(term_producer__DOT__product_slot)', cpp)
        self.assertIn('STORAGE(protocol_pw_row)==T-1', cpp)
        self.assertIn('run(d); // Every reset recovers', cpp)
        self.assertIn('recovered_reads=3072', manifest['steps'][0]['expected_stdout'])
        self.assertIn('___024root.h', files[fault.HEADER].decode())

    def test_early_cache_only_two_source_sites(self):
        manifest, files = fault.role('early-cache')
        self.assertEqual(len(manifest['storage2_fault']['diagnostic_rtl_delta']), 2)
        term = next(data.decode() for name, data in files.items() if name.endswith('_earlycache_probe.sv'))
        self.assertIn('seed_slot && seed_start && !stop', term)
        self.assertIn('cache_owner=(seed_slot && seed_start) ? seed_owner : product_owner', term)
        self.assertIn('bank_owner[prod_bank]==product_owner', term)
        self.assertFalse(manifest['storage2_fault']['promotion_allowed'])

    def test_oracle_actual_negative_and_invalid_modes(self):
        manifest, _ = fault.role('oracle')
        self.assertEqual(manifest['steps'][0]['expected_returncode'], 1)
        self.assertEqual(manifest['steps'][0]['expected_stdout'], '')
        for mode in ('normal', 0, True, 'full'):
            with self.assertRaises(ValueError):fault.role(mode)

    def test_external_successor_reaches_actual_feed_ingress(self):
        from fpga.reference import stream27_context_storage_banks_external as external
        manifest, files = external.role()
        cpp=files[external.CPP].decode()
        self.assertIn('d.start_contexts=d.batch_mode=d.feed_mode=3',cpp)
        self.assertIn('d.command_ready&&!d.command_accept&&!d.error',cpp)
        self.assertTrue(manifest['storage2_fault']['production_rtl_unchanged'])
        self.assertTrue(manifest['storage2_fault']['actual_feed_ingress'])

    def test_early_successor_retains_shared_parent_leaf(self):
        from fpga.reference import stream27_context_storage_banks_early_v2 as early
        manifest, files=early.role()
        old='rtl/genefer_stream27_term_context_param_v1_contexts_v1_storage2_v1.sv'
        self.assertIn(old,manifest['build']['sv_sources'])
        self.assertEqual(len(manifest['build']['sv_sources']),54)
        self.assertIn('observed&&failed',files[fault.CPP].decode())
        self.assertIn('premature_cache_rejected=1',manifest['steps'][0]['expected_stdout'])
        for name in ('f1','f2'):
            field=next(data.decode() for key,data in files.items() if '_'+name+'_' in key and key.endswith('_storage2_v1.sv'))
            self.assertNotIn('_earlycache_probe #',field)


if __name__ == '__main__':unittest.main()
