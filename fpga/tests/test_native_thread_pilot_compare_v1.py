"""Pure comparison mock tests; no native/model/HDL/full-N work."""
import copy
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from fpga.reference import core27_t5b_thread_pilot_v1 as pilot
from fpga.tools import native_threaded_class_v1 as runtime
from fpga.tools import native_thread_pilot_compare_v1 as compare


class PilotComparisonTests(unittest.TestCase):
    def data(self, root, count):
        _, manifest = pilot.recipe(count)
        selected = runtime.profile('gcp-c4d-static01-v1')
        manifest.update(host=selected['host'], cpu_profile=selected['profile_id'])
        identity = runtime.load('build_identity_v2.py', runtime.IDENTITY_SHA).build_identity(manifest, selected)
        report = dict(model_threads=count, context_threads=count, exact_build_identity=identity,
            executable_sha256='1'*64, tool_sha256=selected['hashes'],
            limits=dict(affinity=selected['cpus'], physical_cores=selected['runtime_allocation']['physical_cores'],
                        memory_max_bytes=selected['memory_bytes'], swap_max_bytes=0, cpu_max=['200000','100000']),
            steps=[dict(name='build', seconds=5), dict(name='t5b-cold-warm', returncode=0, error=None,
                sha256=compare.STDOUT_SHA, seconds=10 if count==1 else 6,
                native_child_usage=dict(schema='native-wait4-child-usage-v1', pid=123, returncode=0,
                    user_seconds=9 if count==1 else 10, system_seconds=1, peak_rss_kib=1024))])
        paths = root/f'm{count}.json', root/f'r{count}.json'
        for path, value in zip(paths, (manifest, report)):
            path.write_text(json.dumps(value))
        return paths

    def modules(self):
        gate = types.SimpleNamespace(make_contract=lambda name,path: {},
                                     validate_result=lambda *args,**kwargs: {'status':'PASS_expected_contracts'})
        return lambda name: runtime if name=='native_threaded_class_v1.py' else gate

    def test_observed_ratios_scope_and_both_finite_samples(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            a, b = self.data(root, 1), self.data(root, 2)
            with patch.object(compare, 'load', side_effect=self.modules()):
                result = compare.compare(*a, *b)
            self.assertEqual(result['status'], 'PASS_matched_native_one_two_sample')
            self.assertAlmostEqual(result['one_over_two_wall_ratio'], 10/6)
            self.assertEqual(result['two_over_one_cpu_ratio'], 1.1)
            self.assertEqual(result['cycle_counts'], [41674, 28826])
            self.assertFalse(result['higher_thread_admission'])

    def test_wrong_cycles_identity_physical_caps_or_nonfinite_usage_fail(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            a, b = self.data(root, 1), self.data(root, 2)
            good = json.loads(b[1].read_text())
            for mutation in ('cycles', 'identity', 'physical', 'memory', 'nan'):
                report = copy.deepcopy(good)
                if mutation=='cycles': report['steps'][1]['sha256']='0'*64
                if mutation=='identity': report['exact_build_identity']['build_key']='0'*64
                if mutation=='physical': report['limits']['physical_cores']=[[0,0],[0,0]]
                if mutation=='memory': report['limits']['memory_max_bytes']*=2
                if mutation=='nan': report['steps'][1]['native_child_usage']['user_seconds']=float('nan')
                b[1].write_text(json.dumps(report))
                with patch.object(compare, 'load', side_effect=self.modules()), self.assertRaises(ValueError):
                    compare.compare(*a, *b)

    def test_cross_host_pair_and_source_changes_not_matched_evidence(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            a, b = self.data(root, 1), self.data(root, 2)
            original = compare.sample
            for mutation in ('host', 'profile', 'sources'):
                def sample(*args):
                    values = original(*args)
                    if args[-1]==2:
                        manifest = copy.deepcopy(values[0])
                        if mutation=='sources': manifest['sources']['tests/mock.py']='0'*64
                        else: manifest['host' if mutation=='host' else 'cpu_profile']='different'
                        values=(manifest, *values[1:])
                    return values
                with patch.object(compare, 'load', side_effect=self.modules()), patch.object(compare, 'sample', side_effect=sample), self.assertRaisesRegex(ValueError, 'same actual'):
                    compare.compare(*a, *b)


if __name__ == '__main__':
    unittest.main()
