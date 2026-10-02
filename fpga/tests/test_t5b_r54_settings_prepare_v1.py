import json,tempfile,unittest
from pathlib import Path
from fpga.reference.t5b_r54_settings_prepare_v1 import prepare,assess,ALLOWED

class SettingsAlternatives(unittest.TestCase):
    def test_all_three_and_exact_delta_negatives(self):
        for seed,period in ALLOWED:
            with tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp)/'project';r=prepare(p,seed,period)
                self.assertEqual(len(r['source_sha256']),16);self.assertFalse(r['launch_authority_conferred'])
                self.assertEqual(r['design_prescreen_exemption'],'constraint_seed_only')
                for filename,suffix in [('probe.sdc','\nset_false_path -from [all_registers]\n'),('probe.qsf','\nset_parameter -name AW 8\n'),('run.tcl','\nexecute_module -tool asm\n')]:
                    path=p/filename;raw=path.read_bytes();path.write_bytes(raw+suffix.encode())
                    with self.assertRaises(ValueError):assess(p)
                    path.write_bytes(raw)
                name=next(iter(r['source_sha256']));path=p/'rtl'/name;raw=path.read_bytes();path.write_bytes(raw+b'\n')
                with self.assertRaises(ValueError):assess(p)
                path.write_bytes(raw)
                m=json.loads((p/'manifest.json').read_text());m['seed']=9;(p/'manifest.json').write_text(json.dumps(m))
                with self.assertRaises(ValueError):assess(p)
    def test_unrequested_setting_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):prepare(Path(tmp)/'project',4,9.3)

if __name__=='__main__':unittest.main()
