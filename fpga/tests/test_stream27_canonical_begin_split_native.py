import unittest
from fpga.reference import stream27_canonical_begin_split_native as n


class BeginSplitNative(unittest.TestCase):
    def test_closed_normal_source_and_reverse(self):
        m,f=n.role()
        self.assertEqual(m['test_role'],'normal')
        self.assertEqual(len(m['build']['sv_sources']),4)
        self.assertEqual(n.bind.reverse_leaf(f['rtl/'+n.bind.NEW+'.sv'].decode()),
                         f['rtl/'+n.bind.OLD+'.sv'].decode())
        self.assertEqual(m['sources'],{k:n.sha(v) for k,v in f.items()})

    def test_live_base_and_actual_runtime_contract(self):
        m,f=n.role();cpp=f[n.CPP].decode()
        self.assertIn('h.d.base=base;h.d.begin_canonical=1;h.edge();',cpp)
        self.assertIn('h.d.base=0;h.run();h.all(x);',cpp)
        self.assertIn('live_base_images=2 live_base_reads=512',m['steps'][0]['expected_stdout'])
        self.assertIn('need(count==1,',cpp)
        self.assertTrue(m['begin_split']['host_owner_publication_barrier_not_instantiated'])


if __name__=='__main__':
    unittest.main()
