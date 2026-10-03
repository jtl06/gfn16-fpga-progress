import unittest
from fpga.reference import stream27_context_storage_combo_directbound_liveprobe as failed
from fpga.reference import stream27_context_storage_combo_directbound_liveprobe_v3 as new


class SingleContextLiveProbeTests(unittest.TestCase):
    def test_exact_comparisons_and_RTL_from_failed_witness(self):
        before, f0 = failed.role()
        after, f1 = new.role('bounds')
        for path in before['build']['sv_sources']:
            self.assertEqual(f0[path], f1[path])
        s0, s1 = f0[failed.CPP].decode(), f1[new.CPP].decode()
        start='void bounds(H& h){'
        self.assertEqual(s0[s0.index(start):s0.index(' H negative;')],
                         s1[s1.index(start):s1.index(' h.reads=h.images=0;')])
        for name,end in [('void faults(H& h){','void bounds(H& h){'),
                         ('void normal(H& h){','void faults(H& h){')]:
            self.assertEqual(s0[s0.index(name):s0.index(end)], s1[s1.index(name):s1.index(end)])
        self.assertIn('h.reads=h.images=0;faults(h);h.sample();h.reads=h.images=0;normal(h);h.sample();',s1)
        self.assertNotIn('H negative',s1)
        self.assertNotIn('H regular',s1)
        self.assertEqual(s1.count(' H h(argc,argv);'),1)
        self.assertIn('runtime_contexts=1',after['steps'][0]['expected_stdout'])

    def test_real_runtime_and_control_oracle(self):
        for mode in new.IDS:
            m,files=new.role(mode)
            text=files[new.CPP].decode()
            self.assertIn(':context(argc,argv),d(&context)',text)
            self.assertIn('gfn16_runtime::configure(*this,argc,argv)',text)
            self.assertIn('directory_iterator("/proc/self/task")',text)
            self.assertIn('gfn16_runtime::probe(h.context,h.d)',text)
            self.assertNotIn('\\n',m['steps'][0]['expected_stdout'])
            self.assertEqual(m['steps'][0]['expected_returncode'],1 if mode=='oracle' else 0)


if __name__=='__main__':
    unittest.main()
