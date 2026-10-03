import json
import unittest
from fpga.reference import stream27_context_lean_long_native as own
from fpga.reference import stream27_context_lean_physical as physical


class LeanPilotTests(unittest.TestCase):
    def test_captured_source_inputs_and_single_label(self):
        m, files = own.role()
        base = own.read(own.BASE/'manifest.json')
        self.assertEqual(m['build']['sv_sources'], base['build']['sv_sources'])
        for name in m['build']['sv_sources']:
            self.assertEqual(m['sources'][name], base['sources'][name])
        self.assertEqual(m['build']['runtime_threads'], 1)
        self.assertEqual(m['probe'], base['probe'])
        self.assertEqual(files[own.CPP].decode().count(own.LABEL), 1)
        self.assertIn('return gfn16_runtime::probe(context,d);std::cout', files[own.CPP].decode())
        self.assertEqual(files[own.HEADER], (own.TWIN/'source/fpga'/own.HEADER).read_bytes())
        self.assertFalse(m['lean_production']['host_gl_implemented'])

    def test_unlabeled_output_refused(self):
        m, _ = own.role()
        with self.assertRaisesRegex(ValueError, 'LABEL_AND_CAPTURED'):
            own.validate('R84_C2_THREAD100_PASS {}\n', '', 0,
                         m['steps'][0]['validator']['config'], {})

    def test_physical_exact_own_full_source_and_honest_scope(self):
        manifest, files, spec = physical.build()
        native = own.read(own.BASE/'manifest.json')
        self.assertEqual(len(spec['sources']), 55)
        self.assertEqual(len(spec['transfers']), 20)
        self.assertEqual(manifest['label'], own.LABEL)
        for name, pin in spec['sources'].items():
            self.assertEqual(own.sha(files[name]), native['sources'][name])
            self.assertEqual(own.sha(files[name]), pin)
        self.assertEqual(spec['identity']['clock_period_ns'], 13.0)
        self.assertEqual(spec['coverage_claim'], 'declared_source_inventory_not_netlist_completeness')
        self.assertFalse(manifest['lean_production']['clock_claim'])


if __name__ == '__main__':
    unittest.main()
