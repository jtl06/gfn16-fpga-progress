"""Pure actual-package closure, measured shape and source-bound Azure negatives."""
import copy
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from fpga.tools import native_threaded_long_package_v1 as package
from fpga.tools import native_threaded_long_stage_v1 as stage
from fpga.tools import native_threaded_long_class_v1 as runtime

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'results/throughput-20260929/threaded-long-package-v1'


class ThreadedLongPackageTests(unittest.TestCase):
    def setUp(self):
        # Replay the immutable quote at its observed time; production remains
        # live-clock/freshness checked. This avoids tests aging after900s.
        meter=package.meter();original=meter.validate_budget
        stamp=json.loads((DATA/'provider-inputs-v1.json').read_text())['observed_at_utc']
        fixed=datetime.fromisoformat(stamp)+timedelta(seconds=1)
        def validate(*args,**kwargs):
            kwargs.setdefault('now',fixed)
            return original(*args,**kwargs)
        meter.validate_budget=validate
        patcher=patch.dict(package.base.worker.__globals__,meter=lambda:meter)
        patcher.start();self.addCleanup(patcher.stop)

    def test_actual_archive_and_exact_budget_window(self):
        p=DATA/'packet'; receipt=json.loads((p/'preparation.json').read_text())
        _,ticket,manifest,_=stage.worker().inspect_archive(p/'package.tar.gz',receipt['archive_sha256'],receipt['ticket_sha256'])
        self.assertEqual(ticket['max_seconds'],5000)
        self.assertEqual(ticket['budget']['max_seconds'],5015)
        self.assertEqual(ticket['runtime_duration'],package.duration.SHAPE)
        self.assertEqual(manifest['build']['runtime_threads'],2)
        self.assertEqual(manifest['sources']['tools/native_threaded_long_class_v1.py'],package.EXECUTOR_SHA)
        self.assertEqual(manifest['sources']['tools/build_identity_v2.py'],'d59fcd49049107ceeb7b3f832a7da9b664363fb3a4b94664ec236502448a1329')

    def test_budget_source_host_duration_refused_before_destination(self):
        role=DATA/'bound-role'; original=json.loads((DATA/'budget.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            for field,value in [('provider','gcp'),('host','gfn16-azure-f16'),('max_seconds',3715),
                                ('max_seconds',float('inf')),('source_sha256','x'*64),('source_sha256','0'*64)]:
                budget=copy.deepcopy(original);budget[field]=value
                path=root/'budget.json';path.write_text(json.dumps(budget))
                out=root/'must-not-exist'
                with self.subTest(field=field,value=value),self.assertRaises((ValueError,TypeError)):
                    package.prepare(role/'manifest.json',role/'source/fpga',package.duration.PROFILE,'test-threaded-long','run',out,path)
                self.assertFalse(out.exists())

    def test_actual_unpacked_live_namespace_and_all_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary).resolve();source=base/'capture/source/fpga'
            shutil.copytree(DATA/'packet/capture/source/fpga',source)
            output=base/'output';output.mkdir()
            manifest=json.loads((DATA/'packet/manifest.json').read_text())
            manifest.update(source_root=str(source),output_parent=str(output))
            path=base/'manifest.json';path.write_text(json.dumps(manifest))
            value=runtime.parent(package.duration.PROFILE)
            value.PROFILES={package.duration.HOST:dict(runtime.profile(package.duration.PROFILE),base=str(base))}
            value.__file__=str(source/value.SELF)
            pin=hashlib.sha256(path.read_bytes()).hexdigest()
            for name in ('load_manifest','execute','check_sources'):
                self.assertIs(getattr(value,name).__globals__,value.__dict__)
            value.LEASE_FDS=(91,92);self.assertEqual(value.execute.__globals__['LEASE_FDS'],(91,92))
            with patch.object(value.socket,'gethostname',return_value=package.duration.HOST):
                self.assertEqual(value.load_manifest(path,pin)[0],manifest)
            with patch.object(value.socket,'gethostname',return_value='gfn16-pilot-c4d'):
                with self.assertRaises(ValueError):value.load_manifest(path,pin)

    def test_actual_worker_and_binding_always_request_full5015_budget(self):
        budget=json.loads((DATA/'budget.json').read_text())
        manifest=json.loads((DATA/'packet/manifest.json').read_text())
        worker=package.worker(budget)
        class Meter:
            def validate_budget(self,value,host,max_seconds,**kwargs):
                if max_seconds!=5015:raise AssertionError('short inherited horizon')
                raise ValueError('full5015 horizon does not fit protected deadline')
        with patch.dict(worker.budget_check.__globals__,meter=lambda:Meter()):
            with self.assertRaisesRegex(ValueError,'full5015'):worker.budget_check(budget)
        with patch.dict(package.binding.__globals__,meter=lambda:Meter()):
            with self.assertRaisesRegex(ValueError,'full5015'):
                package.binding(budget,runtime.profile(package.duration.PROFILE),manifest)


if __name__=='__main__':unittest.main()
