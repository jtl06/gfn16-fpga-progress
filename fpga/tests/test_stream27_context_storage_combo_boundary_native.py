"""R95 normal-first metadata/source proof; no local HDL/full-N arithmetic."""
import unittest
from fpga.reference import stream27_context_storage_combo_boundary_native as n


class BoundaryNormalTests(unittest.TestCase):
    def test_small_counted_calendar_not_forced_parent(self):
        m,files,b=n.role('aw8')
        self.assertEqual(len(b['files']),54)
        self.assertEqual([b['geometry'][k] for k in ('warm_interval','first_digit','carry_done','correction_cache_latency')],[213,194,213,78])
        self.assertIn(b'INTERVAL=213,FIRST_DIGIT=194,CARRY_DONE=213',files['rtl/tb/s4_host_contexts_config_v1.h'])
        old,donor=n.capture('aw8')
        self.assertEqual(files[m['build']['cpp_source']],donor[old['build']['cpp_source']])
        self.assertEqual(m['steps'],old['steps'])
        self.assertEqual(m['build']['parameters'],dict(old['build']['parameters'],BOUNDARY_INPUTREG=1))

    def test_full_observer_parameter_forwarding_zero_edges(self):
        m,files,b=n.role('full')
        self.assertEqual(len(m['build']['sv_sources']),55)
        self.assertEqual([b['geometry'][k] for k in ('warm_interval','first_digit','carry_done','correction_cache_latency')],[8459,8458,12557,78])
        text=files['rtl/'+m['build']['top']+'.sv'].decode()
        self.assertIn('BOUNDARY_INPUTREG=1,',text)
        self.assertIn('.BOUNDARY_INPUTREG(BOUNDARY_INPUTREG)',text)
        self.assertNotIn('always',text)
        old,donor=n.capture('full')
        self.assertEqual(files['rtl/tb/s4_p16_two_context_full_config.h'],donor['rtl/tb/s4_p16_two_context_full_config.h'])
        self.assertEqual(m['steps'],old['steps'])

    def test_sources_roster_authority_and_real_seed_overrides(self):
        for stage in ('aw8','full'):
            m,files,b=n.role(stage)
            self.assertTrue(all('lineage/'+p in files for p in b['source_dependencies']))
            contract=m['context_storage_combo_boundary']['contract']
            self.assertEqual(contract['roster'],['BOUNDARY_INPUTREG'])
            self.assertTrue(contract['sticky_controller_and_global_authority_edges_unchanged'])
            self.assertTrue(contract['accepted_origin_tail_preserved'])
            self.assertEqual(m['build']['parameters']['EPOCH_SEED0'],65534)
            self.assertEqual(m['build']['parameters']['EPOCH_SEED1'],42)
            self.assertEqual(m['rtl_readiness']['rtl_ready_at_utc'],'2026-10-02T10:11:42Z')
            self.assertFalse(m['context_storage_combo_boundary']['promotion_allowed'])


if __name__=='__main__':unittest.main()
