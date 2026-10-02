import copy
import json
import unittest
from fpga.reference import stream27_p16_diet_whole_fit as candidate
from fpga.tools.prefit_structural_guard_v1 import source_inventory


class WholeP16FitSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=candidate.ROOT/'artifacts/s4-p16-diet-whole-full-flow-v1/project'
        cls.manifest=json.loads((cls.root/'manifest.json').read_text())
        cls.spec=json.loads((cls.root.parent/'inventory.json').read_text())

    def test_source_exactly_matches_actual_synthesis(self):
        parent=json.loads((candidate.ROOT/'artifacts/s4-p16-diet-whole-syn-screen-v1/project/manifest.json').read_text())
        self.assertEqual(self.manifest['source_sha256'],parent['source_sha256'])
        self.assertEqual(self.manifest['core_parameters'],parent['core_parameters'])
        self.assertEqual(len(self.manifest['source_sha256']),58)
        tcl=(self.root/'run.tcl').read_text()
        self.assertEqual(tcl,candidate.FULL_TCL)
        self.assertEqual(tcl.count('execute_module -tool syn'),1)
        self.assertEqual(tcl.count('execute_module -tool fit'),1)
        self.assertEqual(tcl.count('execute_module -tool sta'),1)
        self.assertNotIn('execute_module -tool asm',tcl)

    def test_current_declared_stages_and_companions(self):
        spec,result,count=candidate.inventory(self.root,self.manifest)
        self.assertEqual(spec,self.spec);self.assertEqual(result['findings'],[])
        self.assertEqual(len(spec['transfers']),27);self.assertEqual(count,30)
        self.assertEqual(spec['identity']['parameters']['P'],16)

    def test_scope_identity_and_anchor_tampering_rejected(self):
        changes=[('identity',None),('anchor',None),('source',None)]
        for kind,_ in changes:
            spec=copy.deepcopy(self.spec)
            if kind=='identity':spec['identity']['parameters']['P']=8
            elif kind=='anchor':spec['transfers'][0]['registered_stages'][0]['anchors'][0]+='WRONG'
            else:spec['transfers'][0]['registered_stages'][0]['source']='rtl/missing.sv'
            with self.assertRaises(ValueError):source_inventory(self.root,spec)


if __name__=='__main__':unittest.main()
