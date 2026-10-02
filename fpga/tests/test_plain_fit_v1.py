import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('plain',ROOT/'cloud/plain_fit_v1.py');p=importlib.util.module_from_spec(s);s.loader.exec_module(p)
class Plain(unittest.TestCase):
 def test_flows_are_compute_only(self):
  self.assertEqual(p.FULL_TCL.count('execute_module -tool'),3)
  self.assertEqual(p.CONTINUE_TCL.count('execute_module -tool'),2)
  self.assertNotIn('execute_module -tool syn',p.CONTINUE_TCL)
  for text in (p.FULL_TCL,p.CONTINUE_TCL):self.assertNotIn('exec ',text);self.assertNotIn('-tool asm',text)
 def test_physical_static_resources(self):
  for host,row in p.HOSTS.items():
   cpus=[c for values in row['slots'].values() for c in values]
   self.assertEqual(len(cpus),len(set(cpus)));self.assertTrue(all(len(v)==row['workers'] for v in row['slots'].values()))
 def test_existing_host_only(self):
  self.assertEqual(set(p.HOSTS),{'gfn16-azure-f16','gfn16-aws-m8i'})
if __name__=='__main__':unittest.main()
