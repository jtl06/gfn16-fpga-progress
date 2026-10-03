"""Scalar algebra and prefreeze guards only, not R11 qualification."""
import itertools
import json
from pathlib import Path
import unittest
from fpga.reference import stream27_context_transport11_model as model
from fpga.reference import stream27_context_storage_combo_transport11_native as native


class Transport11ModelTests(unittest.TestCase):
    def test_chosen_primary_geometry_and_all_switch_models(self):
        root=Path(__file__).resolve().parents[1]
        base=root/'results/throughput-20260929/trackS-c2-storage-combo-timing10-native-v1'
        for stage,expected in [('aw8',(217,198,217,18)),('full',(8463,8462,12561,0))]:
            before=json.loads((base/(stage+'-normal')/'production-bundle.json').read_bytes())['geometry']
            self.assertEqual(model.geometry(before),before)
            primary=model.geometry(before,crt_transport_reg=1,inverse_ingress_reg=1,term_join_transport_reg=1)
            self.assertEqual(tuple(primary[k] for k in ('warm_interval','first_digit','carry_done','feedback_delay')),expected)
            self.assertEqual(primary['sink_accept'],before['sink_accept']+2)
            self.assertEqual(primary['crt_accept'],before['crt_accept']+3)
            self.assertEqual(primary['correction_cache_latency'],78)
            self.assertEqual((primary['term_seed_first'],primary['term_seed_last']),(71,74))
            for flags in itertools.product((0,1),repeat=4):
                g=model.geometry(before,**dict(zip(('crt_transport_reg','inverse_ingress_reg',
                    'term_join_transport_reg','ntt_compare_reg'),flags)))
                proof=model.prove_schedule(g)
                self.assertFalse(proof['native_qualified'])
                self.assertLessEqual(max(w['logical_peak'] for w in proof['storage2_lifetime']),4)
                self.assertGreater(min(w['minimum_gap'] for w in proof['storage2_lifetime']),0)

    def test_calendar_is_conditional_and_not_inherited(self):
        hypothetical = dict(n=64, rows=4, warm_interval=50, carry_done=80)
        result = model.publication_calendar(hypothetical, 3, [20, 45])
        self.assertEqual(result['warm_edges'], [201, 226])
        self.assertEqual(result['publication_edges'], [854, 1506])
        self.assertEqual(result['full_read_completion_cycles'], 1570)
        self.assertFalse(result['source_ready'])
        self.assertFalse(result['measured_or_inherited_sample_cycles'])
        self.assertEqual(model.publication_calendar(hypothetical, 3, [20, 45],
                         special=(True, False))['publication_edges'], [918, 1570])

    def test_model_historical_guard_not_native_source_authority(self):
        with self.assertRaisesRegex(ValueError, 'SOURCE_NOT_FROZEN'):
            model.require_frozen()
        root=Path(__file__).resolve().parents[1]
        self.assertEqual(native.sha((root/native.BINDER).read_bytes()), native.BINDER_PIN)
        for stage in ('aw8', 'full'):
            manifest, files, production = native.role(stage)
            contract=production['context_transport11']
            self.assertTrue(contract['source_ready'])
            self.assertTrue(contract['captured_watchdog_json_dependencies_explicit'])
            self.assertEqual(manifest['rtl_readiness']['rtl_ready_at_utc'],native.READY)
            self.assertEqual(len(production['files']),58)
            self.assertEqual(len(manifest['build']['sv_sources']),58+(stage=='full'))
            self.assertTrue(all(files['lineage/'+p] for p in production['source_dependencies']))


if __name__ == '__main__': unittest.main()
