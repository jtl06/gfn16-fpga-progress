import unittest
from fpga.reference.anext_control_fault_source_v1 import verify,sources,CORE
from fpga.reference.anext_control_fault_output_v1 import validate,CASES
class ControlFault(unittest.TestCase):
    def test_closed_source_and_physical_observers(self):
        self.assertEqual(verify()['arithmetic_changes'],0)
        self.assertIn('engine.data_we',sources()[CORE]);self.assertNotIn('engine.child.data_we',sources()[CORE])
    def test_exact_finite_outputs(self):
        for case in CASES:
            text=f'ANEXT_CONTROL_PASS case={case} injected=1 errors={int(not case.startswith("reset-"))} recovered=1 words=32 quiet=12 ticks=1000\n';cfg=dict(case=case)
            validate(text,'',0,cfg,{})
            for bad in (text+'extra\n',text.replace('recovered=1','recovered=0'),text.replace('quiet=12','quiet=0')):
                with self.assertRaises(ValueError):validate(bad,'',0,cfg,{})
if __name__=='__main__':unittest.main()
