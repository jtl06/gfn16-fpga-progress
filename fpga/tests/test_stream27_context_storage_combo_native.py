"""Bounded source/manifest checks; normal is already publicly submitted."""
import re
import unittest
from fpga.reference import stream27_context_storage_combo_native as n


class ComboNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.roles={s:n.role(s) for s in ('aw8','full')}

    def test_real_original_calendar_not_timing58(self):
        for stage,expected in [('aw8',(212,193,212)),('full',(8459,8458,12557))]:
            m,f,b=self.roles[stage];g=b['geometry']
            self.assertEqual(tuple(g[k] for k in ('warm_interval','first_digit','carry_done')),expected)
            self.assertEqual(len(b['files']),53)
            self.assertEqual(m['rtl_readiness']['rtl_ready_at_utc'],'2026-10-02T09:13:02Z')
            self.assertEqual(m['build']['parameters']['EPOCH_SEED0'],65534)
            self.assertEqual(m['build']['parameters']['EPOCH_SEED1'],42)

    def test_original_reference_cpp_probe_steps_exact(self):
        for stage,(m,files,b) in self.roles.items():
            old,donor=n.capture(stage)
            self.assertEqual(m['steps'],old['steps']);self.assertEqual(m['probe'],old['probe'])
            self.assertEqual(m['build']['parameters'],old['build']['parameters'])
            self.assertEqual(files[m['build']['cpp_source']],donor[old['build']['cpp_source']])
            for name,data in donor.items():
                if name.endswith('reference_v1.h') or name.endswith('reference_ntt_v1.h'):
                    self.assertEqual(files[name],data)

    def test_all_source_dependencies_including_two_json_captures(self):
        for stage,(m,files,b) in self.roles.items():
            self.assertTrue(all('lineage/'+name in files for name in b['source_dependencies']))
            captured=[name for name in b['source_dependencies'] if name.endswith('/production-bundle.json')]
            self.assertEqual(len(captured),2)
            self.assertEqual(m['sources'],{name:n.sha(data) for name,data in files.items()})

    def test_new_graph_not_old_qualification(self):
        for stage,(m,files,b) in self.roles.items():
            old,unused=n.capture(stage)
            self.assertNotEqual(m['context_storage_combo']['production_generated_sha256'],old['storage2']['production_generated_sha256'])
            self.assertTrue(m['context_storage_combo']['donor_PASS_clock_pilot_not_inherited'])
            self.assertEqual(m['build']['runtime_threads'],1)
            self.assertEqual(m['test_role'],'normal')

    def test_full_observer_is_transparent_and_unfitted(self):
        m,files,b=self.roles['full'];observer=files['rtl/'+m['build']['top']+'.sv'].decode()
        self.assertIn(b['top']+' #(',observer)
        self.assertIsNone(re.search(r'\b(always|always_ff|always_comb|initial)\b',observer))
        self.assertEqual(len(m['build']['sv_sources']),54)
        self.assertLess(len(m['build']['top']),128)

    def test_AW5_rejected_and_frozen_binder_drift_rejected(self):
        with self.assertRaisesRegex(ValueError,'AW8_FULL_ONLY_NO_AW5'):n.capture('aw5')
        old=n.BINDER_PIN
        try:
            n.BINDER_PIN='0'*64
            with self.assertRaisesRegex(ValueError,'EXACT_CORE_FREEZE'):n.role('aw8')
        finally:n.BINDER_PIN=old


if __name__=='__main__':unittest.main()
