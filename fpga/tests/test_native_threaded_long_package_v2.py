"""Actual intrinsic-deadline successor archive and loader regression."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from fpga.tools import native_threaded_long_package_v2 as package
from fpga.tools import native_threaded_long_stage_v2 as stage
from fpga.tools import native_threaded_long_class_v2 as runtime

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'results/throughput-20260929/threaded-long-package-v1'


class IntrinsicPackageTests(unittest.TestCase):
    def test_actual_archive_and_preserved_donor(self):
        p=DATA/'packet-v2';r=json.loads((p/'preparation.json').read_text())
        _,t,m,_=stage.worker().inspect_archive(p/'package.tar.gz',r['archive_sha256'],r['ticket_sha256'])
        old=json.loads((DATA/'packet/manifest.json').read_text())
        for field in ('build','probe','steps','runtime_duration','budget_source_members'):
            self.assertEqual(m[field],old[field])
        self.assertEqual((t['max_seconds'],t['budget']['max_seconds']),(5000,5015))
        self.assertEqual(m['sources']['tools/native_threaded_long_class_v2.py'],package.EXECUTOR_SHA)
        prior=json.loads((DATA/'packet/preparation.json').read_text())
        with self.assertRaises(ValueError):stage.worker().inspect_archive(DATA/'packet/package.tar.gz',prior['archive_sha256'],prior['ticket_sha256'])

    def test_actual_fullsource_loader_and_intrinsic_deadline(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp).resolve();root=base/'capture/source/fpga';shutil.copytree(DATA/'packet-v2/capture/source/fpga',root)
            output=base/'output';output.mkdir();m=json.loads((DATA/'packet-v2/manifest.json').read_text())
            m.update(source_root=str(root),output_parent=str(output));path=base/'manifest.json';path.write_text(json.dumps(m))
            value=runtime.parent(m['cpu_profile']);selected=dict(runtime.profile(m['cpu_profile']),base=str(base))
            value.PROFILES={package.duration.HOST:selected};value.__file__=str(root/value.SELF)
            value.LEASE_FDS=(93,94);self.assertEqual(value.execute.__globals__['LEASE_FDS'],(93,94))
            self.assertIs(value.load_manifest.__globals__,value.__dict__)
            with patch.object(value.socket,'gethostname',return_value=package.duration.HOST):
                self.assertEqual(value.load_manifest(path,hashlib.sha256(path.read_bytes()).hexdigest())[0],m)
            for remaining in (4000,12214,12215):
                with patch.object(runtime.time,'time',return_value=runtime.DEADLINE-remaining):
                    with self.assertRaises(ValueError):runtime.guard_runtime_deadline(selected)
            with patch.object(runtime.time,'time',return_value=runtime.DEADLINE-12216):runtime.guard_runtime_deadline(selected)


if __name__=='__main__':unittest.main()
