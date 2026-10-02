from pathlib import Path
import unittest
from fpga.reference.stream27_probe_prefit_inventory_v2 import inventory,validate_ports
from fpga.tools.prefit_structural_guard_v1 import evaluate


class Ports(unittest.TestCase):
    def test_all_ports_mapped_and_no_native_claim(self):
        for name in ('stream27-p16c-aw16-p16-f0-prepared-v2','stream27-p8b-aw16-p8-f0-prepared-v1'):
            project=Path(__file__).resolve().parents[1]/'artifacts'/name/'project'
            spec=inventory(project)
            self.assertEqual(spec['source_port_count'],45)
            self.assertEqual(len(spec['transfers']),10)
            self.assertFalse(evaluate(project,spec)['fit_allowed'])
            spec['source_port_groups'].pop()
            with self.assertRaises(AssertionError):validate_ports(spec,(project/'rtl'/(spec['identity']['top']+'.sv')).read_text())


if __name__=='__main__':unittest.main()
