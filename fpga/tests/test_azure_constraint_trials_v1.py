import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('trials',ROOT/'cloud/azure_constraint_trials_v1.py');t=importlib.util.module_from_spec(s);s.loader.exec_module(t)
class Trials(unittest.TestCase):
 def test_seed_roles_source_and_compilation(self):
  raw=(ROOT/'cloud/azure_c1_fit_v3.py').read_bytes()
  for seed in (2,3):
   source=t.derive(raw,seed);compile(source,'trial','exec')
   self.assertIn(t.ROLES[seed]['unit'],source);self.assertIn("runner.launch(PROBE, '"+t.ROLES[seed]['slot']+"'",source)
 def test_unknown_seed_and_tamper_rejected(self):
  raw=(ROOT/'cloud/azure_c1_fit_v3.py').read_bytes()
  for data,seed in ((raw,1),(raw,4),(raw+b'\n',2)):
   with self.assertRaises(ValueError):t.derive(data,seed)
 def test_exact_flow_and_mutation(self):
  text=(ROOT/'artifacts/t5b-seed2-95ns-azure-v1/project/run.tcl').read_text();t.exact_tcl(text)
  with self.assertRaises(ValueError):t.exact_tcl(text.replace('execute_module -tool fit','execute_module -tool asm'))
if __name__=='__main__':unittest.main()
