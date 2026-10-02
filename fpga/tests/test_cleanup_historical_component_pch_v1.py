"""Local pure-Python guard tests; no helper run/native action/deletion."""
import importlib.util
from pathlib import Path
import tempfile
import hashlib
import json
import unittest
from unittest.mock import patch

SOURCE=Path(__file__).resolve().parents[1]/'tools/cleanup_historical_component_pch_v1.py'
spec=importlib.util.spec_from_file_location('pch_cleanup',SOURCE)
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.build=self.root/'build';self.build.mkdir()
        self.target=self.build/'Vgenefer_square_core__pch.h.fast.gch'
        self.target.write_bytes(b'gpchregenerable')
        (self.build/'Vgenefer_square_core__pch.h').write_text('retained header')
        exe=self.build/'Vgenefer_square_core';exe.write_bytes(b'retained executable');exe.chmod(0o755)
        self.original_roots=helper.ROOTS
        self.roots=patch.object(helper,'ROOTS',(self.root,));self.roots.start();self.addCleanup(self.roots.stop)

    def record(self):
        original=helper.identity
        def owned(path):
            result=original(path);result['uid']=1000;return result
        with patch.object(helper,'identity',owned):return helper.target_record(self.target)

    def test_exact_pch_keeps_header_executable_pins(self):
        record=self.record()
        self.assertEqual(record['identity']['size'],15)
        self.assertEqual(len(record['header_sha256']),64)
        self.assertEqual(len(record['executable_sha256']),64)

    def test_non_pch_magic_rejected(self):
        self.target.write_bytes(b'ELF!notpch')
        with self.assertRaisesRegex(RuntimeError,'GCC PCH'):self.record()

    def test_protected_digest_detects_retained_content_change(self):
        before=helper.protected({self.target})
        self.target.write_bytes(b'gpchchanged')
        self.assertEqual(before,helper.protected({self.target}))
        (self.build/'Vgenefer_square_core__pch.h').write_text('changed header')
        self.assertNotEqual(before,helper.protected({self.target}))

    def test_symlink_rejected(self):
        (self.root/'link').symlink_to(self.target)
        with self.assertRaisesRegex(RuntimeError,'symlink'):helper.protected({self.target})

    def test_wrong_scope_rejected(self):
        with patch.object(helper,'ROOTS',(self.root/'other',)):
            with self.assertRaisesRegex(RuntimeError,'outside exact'):self.record()

    def test_saved_inventory_keeps_nanosecond_integer_exact(self):
        path=self.root/'inventory.json'
        stamp=1790723431055006534
        value=dict(status='inventoried_not_removed',targets=[dict(identity=dict(mtime_ns=stamp,ctime_ns=stamp+1))],allocated_bytes=100,process_check={})
        with patch.object(helper,'INVENTORY',path):
            summary=helper.save_inventory(value,path)
        raw=path.read_bytes()
        self.assertIn(str(stamp).encode(),raw)
        self.assertEqual(json.loads(raw),value)
        self.assertEqual(summary['inventory_sha256'],hashlib.sha256(raw).hexdigest())
        self.assertNotIn('targets',summary)
        with patch.object(helper,'INVENTORY',path):
            with self.assertRaises(FileExistsError):helper.save_inventory(value,path)

    def test_save_path_rejects_unapproved_location(self):
        with self.assertRaisesRegex(RuntimeError,'exact fresh'):
            helper.save_inventory({},self.root/'other.json')

    def test_selected_relative_paths_and_roots_are_frozen(self):
        selection=SOURCE.parents[1]/'results/throughput-20260929/aethia-historical-component-pch-selection-v1.json'
        raw=selection.read_bytes();value=json.loads(raw)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),helper.SELECTION_SHA)
        self.assertEqual(len(value['targets']),546)
        self.assertEqual(len(set(value['targets'])),546)
        self.assertEqual(len(value['report_pins']),35)
        self.assertEqual(value['allocated_bytes'],44256260096)
        self.assertEqual(value['roots'],[str(p) for p in self.original_roots])
        for name in value['targets']:
            self.assertFalse(Path(name).is_absolute())
            self.assertNotIn('..',Path(name).parts)
            self.assertNotIn('executable-cache',name)
            self.assertIsNotNone(helper.re.fullmatch(r'V[A-Za-z0-9_]+__pch\.h\.(fast|slow)\.gch',Path(name).name))

    def test_apply_surface_is_exact_unlink_not_recursion(self):
        source=SOURCE.read_text()
        self.assertEqual(source.count('path.unlink()'),1)
        self.assertNotIn('rmtree',source)
        self.assertNotIn('.chmod(',source)
        self.assertIn('len(value[\'targets\'])==546',source)
        self.assertIn("args.confirm==CONFIRM",source)
        self.assertIn("protected(set())==value['protected']",source)


if __name__=='__main__':unittest.main()
