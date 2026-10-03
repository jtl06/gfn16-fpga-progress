import hashlib
import json
import unittest
from fpga.reference import stream27_context_storage_combo_directbound_liveprobe as old
from fpga.reference import stream27_context_storage_combo_directbound_liveprobe_v2 as new


class RuntimeFixedLiveProbeTests(unittest.TestCase):
    def test_old_failed_witness_and_RTL_unchanged(self):
        before, f0 = old.role()
        after, f1 = new.role('bounds')
        for path in before['build']['sv_sources']:
            self.assertEqual(f0[path], f1[path])
        failed = new.ROOT / 'queue/evidence/s4-p16-c2-combo-r8-livebound-fault-q1-v1/attempt-0/collected/output/native/report.json'
        report = json.loads(failed.read_text())
        self.assertEqual(hashlib.sha256((old.ROOT/old.CPP).read_bytes()).hexdigest(), report['sources'][old.CPP])
        self.assertEqual(report['error'], "ValueError('command timeout')")
        s0, s1 = f0[old.CPP].decode(), f1[new.CPP].decode()
        # Exact scalar and native live-bound/accepted-BEGIN comparisons retained.
        start, end = 'void bounds(H& h){', ' H negative;'
        self.assertEqual(s0[s0.index(start):s0.index(end)], s1[s1.index(start):s1.index(end)])
        self.assertEqual(after['livebound']['source_bundle_sha256'], before['livebound']['source_bundle_sha256'])

    def test_runtime_config_precedes_each_model(self):
        m, files = new.role('normal')
        cpp = files[new.CPP].decode()
        self.assertIn('struct RuntimeContext:VerilatedContext', cpp)
        self.assertIn('gfn16_runtime::configure(*this,argc,argv);', cpp)
        self.assertLess(cpp.index(' RuntimeContext context;'), cpp.index(' Vgenefer_stream27_canonical_directbound_pair_v1 d;'))
        self.assertIn(':context(argc,argv),d(&context)', cpp)
        self.assertIn('gfn16_runtime::probe(h.context,h.d)', cpp)
        self.assertIn('gfn16_runtime::matches(context,d)', cpp)
        self.assertIn('directory_iterator("/proc/self/task")', cpp)
        self.assertIn('need(count==1', cpp)
        self.assertEqual(hashlib.sha256(files[new.RUNTIME]).hexdigest(), new.RUNTIME_PIN)
        self.assertIn('-DGFN16_RUNTIME_THREADS=1', m['build']['cflags'])

    def test_normal_then_separate_bounds_and_oracle(self):
        for mode in new.IDS:
            m, files = new.role(mode)
            self.assertEqual(m['test_role'], 'normal' if mode=='normal' else 'deliberate_fault')
            self.assertNotIn('\\n', m['steps'][0]['expected_stdout'])
            if mode=='oracle':
                self.assertEqual(m['steps'][0]['expected_returncode'], 1)
                self.assertEqual(m['steps'][0]['expected_stderr'], 'R8_DIRECTBOUND_WRONG_WORD\n')
            else:
                self.assertIn('os_threads_peak=1', m['steps'][0]['expected_stdout'])


if __name__=='__main__':
    unittest.main()
