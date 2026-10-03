import json
import unittest
from fpga.reference import stream27_context_storage_combo_directbound_full_fault as fault
from fpga.reference import stream27_context_storage_combo_directbound_full_wrap as wrap


class R8FullControlsTests(unittest.TestCase):
    def capture(self):
        raw=(fault.DONOR/'manifest.json').read_bytes()
        self.assertEqual(fault.sha(raw),fault.MANIFEST_PIN)
        m=json.loads(raw)
        return m,{n:(fault.DONOR/'source/fpga'/n).read_bytes() for n in m['sources']}

    def test_full_fault_exact_own_source_and_runtime(self):
        old,files=self.capture()
        m,new=fault.role('contracts')
        self.assertEqual(m['build']['parameters'],old['build']['parameters'])
        self.assertEqual(m['build']['parameters']['CANONICAL_C0_DIRECT'],1)
        self.assertEqual(m['build']['parameters']['COLD_SECOND_ONESHOT'],1)
        for n in old['build']['sv_sources']:
            self.assertEqual(new[n],files[n])
        cpp=new[fault.CPP].decode()
        self.assertIn('gfn16_runtime::configure(context,argc,argv);DUT d{&context}',cpp)
        self.assertIn('gfn16_runtime::probe(context,d)',cpp)
        self.assertEqual([s['argv'][-1] for s in m['steps']],['--external','--owner','--reset','--ordinal','--oracle'])
        self.assertEqual(m['steps'][-1]['expected_returncode'],1)
        self.assertIn('epoch_wrap=0',m['steps'][2]['expected_stdout'])

    def test_wrap_production_unchanged_monitor_only(self):
        old,files=self.capture()
        m,new=wrap.role()
        observer='rtl/'+old['build']['top']+'.sv'
        for n in old['build']['sv_sources']:
            if n!=observer:
                self.assertEqual(new[n],files[n])
        self.assertNotRegex(new[observer].decode(),r'\b(always|always_ff|always_comb|initial)\b')
        self.assertEqual(m['build']['parameters'],old['build']['parameters'])
        self.assertIn('gfn16_runtime::configure(context,argc,argv);DUT d{&context}',new[wrap.CPP].decode())
        meta=m['directbound_full_wrap']
        self.assertTrue(meta['protocol_arithmetic_payload_owner_time_unchanged'])
        self.assertFalse(meta['billions_of_edges_simulated'])
        self.assertTrue(meta['no_R7_wrap_execution_inherited'])


if __name__=='__main__':
    unittest.main()
