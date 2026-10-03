import importlib.util
from pathlib import Path
import tempfile
import unittest
import json
from unittest.mock import patch

P=Path(__file__).resolve().parents[1]/'tools/fit_dispatch.py'
spec=importlib.util.spec_from_file_location('shared_fit',P);d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)

class SharedScratchTests(unittest.TestCase):
    def test_current_launch_not_double_counted_and_captured_models_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();(root/'queue/hosts').mkdir(parents=True);(root/'queue/running').mkdir()
            (root/'queue/hosts/azure-f16-q2.json').write_text(json.dumps(dict(campaign='r15-overnight',enabled=True,eligible_profiles=['one'])))
            for i in range(2):
                (root/f'queue/running/{i}.json').write_text(json.dumps(dict(allowed_hosts=['gfn16-azure-f16'],resources=dict(scratch_gib=4))))
            current={'same':dict(phase='launch_attempt',handle=dict(host='gfn16-azure-f16'))}
            with patch.object(d,'FPGA',root),patch.object(d,'Journal') as journal:
                journal.return_value.current.return_value=current
                plan=d.azure_shared_scratch_plan('same')
                self.assertEqual(plan['fit_bytes'],3<<30)
                self.assertEqual(plan['model_bytes'],8<<30)
                self.assertEqual(d.azure_shared_scratch_plan()['fit_bytes'],6<<30)

    def test_shared_floor_and_exact_incoming(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);target=root/'retained-record-backups-20261003-v1/aws/record-originals-and-audit-deltas.tar.gz.partial'
            target.parent.mkdir(parents=True);target.write_bytes(b'x'*100)
            plan=dict(model_bytes=4<<30,fit_bytes=3<<30,incoming=dict(target=str(target),maximum_bytes=1000))
            bound=(27<<30)+900
            for free,passes in ((bound,True),(bound-1,False)):
                ns=dict(Path=Path,need=d.need,scratch_admission=lambda root:dict(free_bytes=free))
                exec(d.shared_scratch_source(plan),ns)
                if passes:self.assertEqual(ns['scratch_admission'](root)['shared_projected_bytes'],(7<<30)+900)
                else:
                    with self.assertRaisesRegex(ValueError,'projected scratch'):ns['scratch_admission'](root)
            target.unlink()
            with self.assertRaises(FileNotFoundError):ns['scratch_admission'](root)

    def test_no_incoming_still_counts_models_and_fit_growth(self):
        plan=dict(model_bytes=8<<30,fit_bytes=6<<30,incoming=None)
        ns=dict(Path=Path,need=d.need,scratch_admission=lambda root:dict(free_bytes=33<<30))
        exec(d.shared_scratch_source(plan),ns)
        with self.assertRaisesRegex(ValueError,'projected scratch'):ns['scratch_admission'](Path('/worker'))

if __name__=='__main__':unittest.main()
