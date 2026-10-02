"""Deadline/drain boundaries and actual full-source live-namespace checks."""
import ast
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from fpga.tests.test_native_threaded_long_v1 import ROOT,PILOT,sha
from fpga.tools import native_threaded_long_class_v2 as runner


class ThreadedIntrinsicDeadlineTests(unittest.TestCase):
    def test_full_horizon_earlier_drain_and_exact_identity(self):
        selected=runner.profile(runner.duration.PROFILE)
        with patch.object(runner.time,'time',return_value=runner.DEADLINE-4000):
            with self.assertRaisesRegex(ValueError,'full5015'):runner.guard_runtime_deadline(selected)
        for remainder in (runner.DRAIN_LEAD_SECONDS+5014,runner.DRAIN_LEAD_SECONDS+5015):
            with patch.object(runner.time,'time',return_value=runner.DEADLINE-remainder):
                with self.assertRaisesRegex(ValueError,'full5015'):runner.guard_runtime_deadline(selected)
        with patch.object(runner.time,'time',return_value=runner.DEADLINE-runner.DRAIN_LEAD_SECONDS-5016):
            runner.guard_runtime_deadline(selected)
        for field,value in [('burst_deadline_epoch',runner.DEADLINE+1),('profile_id','azure-burst16-static01-v1')]:
            with self.assertRaises(ValueError):runner.guard_runtime_deadline(dict(selected,**{field:value}))

    def test_final_shared_namespace_and_poll_guard_not_just_prelaunch(self):
        value=runner.parent(runner.duration.PROFILE)
        for name in ('load_manifest','check_sources','execute','tools_for'):
            self.assertIs(getattr(value,name).__globals__,value.__dict__)
        self.assertEqual(value.SELF,runner.SELF)
        self.assertEqual(Path(value.__file__).name,'native_threaded_long_class_v2.py')
        self.assertEqual(list(value.PROFILES),[runner.duration.HOST])
        value.LEASE_FDS=(17,18)
        self.assertEqual(value.execute.__globals__['LEASE_FDS'],(17,18))
        raw=runner.base.base.source_policy().host.static_module().pinned('tools/native_source_gate_aethia_cpu02_v2.py').read_bytes()
        text=runner.adapted_source(raw,runner.profile(runner.duration.PROFILE));tree=ast.parse(text)
        execute=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='execute')
        guard=next(x for x in execute.body if isinstance(x,ast.FunctionDef) and x.name=='guard')
        self.assertEqual(ast.unparse(guard.body[0]),'guard_runtime_deadline(profile)')
        calls=[]
        namespace=dict(profile={},guard_runtime_deadline=lambda _:calls.append('checked'))
        # Execute the actual first guard statement (no resource/native effects).
        exec(compile(ast.fix_missing_locations(ast.Module(body=[guard.body[0]],type_ignores=[])),'<guard first line>','exec'),namespace)
        self.assertEqual(calls,['checked'])
        self.assertIn("4500 if name == LONG_RECEIPT['model_step'] else 1800",text)
        self.assertIn('pass_fds=LEASE_FDS + ((lock.fileno(),)',text)
        self.assertIn('native_child_usage=child.resource_receipt()',text)
        self.assertIn('guard_protected(profile); guard(); begin =',text)

    def test_actual_full_source_host_self_gate_and_protected_delegation(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary).resolve();root=folder/'capture/source/fpga';output=folder/'output'
            shutil.copytree(PILOT/'capture/source/fpga',root);output.mkdir()
            manifest=json.loads((PILOT/'manifest.json').read_text())
            for name in ('tools/native_threaded_duration_v1.py','tools/native_threaded_long_class_v1.py',runner.SELF):
                shutil.copyfile(ROOT/name,root/name);manifest['sources'][name]=sha(root/name)
            manifest.update(source_root=str(root),output_parent=str(output))
            path=folder/'manifest.json';path.write_text(json.dumps(manifest));value=runner.parent(runner.duration.PROFILE)
            value.PROFILES={runner.duration.HOST:dict(runner.profile(runner.duration.PROFILE),base=str(folder))}
            value.__file__=str(root/runner.SELF)
            with patch.object(value.socket,'gethostname',return_value=runner.duration.HOST):
                self.assertEqual(value.load_manifest(path,sha(path))[0],manifest)
            with patch.object(value.socket,'gethostname',return_value='wrong-host'):
                with self.assertRaisesRegex(ValueError,'explicit approved native host'):value.load_manifest(path,sha(path))
            value.__file__=str(root/'tools/native_threaded_long_class_v1.py')
            with patch.object(value.socket,'gethostname',return_value=runner.duration.HOST):
                with self.assertRaisesRegex(ValueError,'launcher inside pinned snapshot'):value.load_manifest(path,sha(path))
        host=runner.base.base.source_policy().host
        with patch.object(runner.base.base,'source_policy',return_value=type('Policy',(),dict(host=host))), \
             patch.object(host,'guard_protected',return_value='original-protected-checks') as original, \
             patch.object(runner.time,'time',return_value=runner.DEADLINE-20000):
            self.assertEqual(runner.guard_protected(runner.profile(runner.duration.PROFILE)),'original-protected-checks')
            original.assert_called_once()


if __name__=='__main__':unittest.main()
