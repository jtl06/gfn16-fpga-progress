from pathlib import Path
import unittest
from fpga.reference.stream27_probe_prefit_inventory_v1 import inventory
from fpga.tools.prefit_structural_guard_v1 import evaluate


class ProbePrefit(unittest.TestCase):
    def test_exact_component_source_inventory_stays_native_blocked(self):
        for name in ('stream27-p16c-aw16-p16-f0-prepared-v2','stream27-p8b-aw16-p8-f0-prepared-v1'):
            root=Path(__file__).resolve().parents[1]/'artifacts'/name/'project'
            spec=inventory(root);result=evaluate(root,spec)
            self.assertFalse(result['fit_allowed'])
            self.assertEqual(result['blockers'],[{'reason':'missing_native_cross_block_and_design_assistant_evidence'}])
            self.assertEqual(len(spec['transfers']),8)
            self.assertEqual(spec['scope'],'component_probe')
            spec['identity']['parameters']['CONTEXTS']=2
            with self.assertRaises(ValueError):evaluate(root,spec)


if __name__=='__main__':unittest.main()
