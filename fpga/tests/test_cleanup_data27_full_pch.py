from contextlib import ExitStack,contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from fpga.tools import cleanup_data27_full_pch as cleanup


@contextmanager
def fixture():
    with tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
        outer=Path(tmp).resolve();root=outer/'full';root.mkdir();sizes={};executables=[];exehashes={}
        for field in (1,2,3):
            parent=root/f'build-candidate-p{field}';parent.mkdir()
            exe=parent/cleanup.PREFIX;exe.write_bytes(f'fixture executable {field}'.encode())
            exehashes[field]=cleanup.digest(exe)
            executables.append({'field':field,'kind':'candidate','path':str(exe),'sha256':exehashes[field]})
            field_sizes=[]
            for kind in ('fast','slow'):
                path=parent/(cleanup.PREFIX+'__pch.h.'+kind+'.gch')
                path.write_bytes(b'gpch'+f'{field}-{kind}'.encode())
                s=path.stat();field_sizes.append((s.st_size,s.st_blocks*512))
            sizes[field]=tuple(field_sizes)
        sentinel=root/'unindexed-retained-note.txt';sentinel.write_text('must remain unchanged')
        report={'status':'passed','inputs_rehashed_after':True,'whole_integer_crt':True,
            'steps':[{'passed':True} for _ in range(221)],'matched_cases':[{} for _ in range(93)],
            'executables':executables,'artifact_sha256':{str(p.relative_to(root)):cleanup.digest(p)
                for p in root.rglob('*') if p.is_file() and not p.name.endswith('.gch')}}
        report_path=root/'report.json';report_path.write_text(json.dumps(report))
        replacements={'ROOT':root,'LOCK':outer/'compile.lock','RECEIPT':outer/'cleanup.json',
            'REPORT_SHA':cleanup.digest(report_path),'PCH_UID':os.getuid(),'PCH_GID':os.getgid(),
            'SIZES':sizes,'EXE_SHAS':exehashes}
        for key,value in replacements.items():stack.enter_context(mock.patch.object(cleanup,key,value))
        stack.enter_context(mock.patch.object(cleanup.socket,'gethostname',return_value='aethia'))
        scope=stack.enter_context(mock.patch.object(cleanup,'scope_inactive'))
        yield root,scope


class Data27CleanupTests(unittest.TestCase):
    def test_dry_run_protects_all_other_files_and_never_unlinks(self):
        with fixture() as (root,scope),mock.patch.object(Path,'unlink') as unlink:
            result=cleanup.run()
            self.assertEqual(result['status'],'inventoried_not_removed')
            self.assertEqual(len(result['targets']),6)
            self.assertIn(str(root/'unindexed-retained-note.txt'),result['protected_sha256'])
            self.assertIn(str(root/'report.json'),result['protected_sha256'])
            self.assertEqual(len(list(root.rglob('*.gch'))),6)
            self.assertFalse(cleanup.RECEIPT.exists());unlink.assert_not_called();scope.assert_called_once()

    def test_changed_raw_report_blocks_inventory(self):
        with fixture() as (root,_):
            (root/'report.json').write_text('{}')
            with self.assertRaisesRegex(RuntimeError,'report changed'):cleanup.run()

    def test_changed_candidate_binary_blocks_inventory(self):
        with fixture() as (root,_):
            (root/'build-candidate-p2'/cleanup.PREFIX).write_bytes(b'changed')
            with self.assertRaisesRegex(RuntimeError,'executable bytes changed'):cleanup.run()

    def test_magic_and_extra_cache_rejected(self):
        with fixture() as (root,_):
            path=next(root.rglob('*.gch'));data=path.read_bytes();path.write_bytes(b'nope'+data[4:])
            with self.assertRaisesRegex(RuntimeError,'not a GCC PCH'):cleanup.run()
        with fixture() as (root,_):
            (root/'build-candidate-p3/extra.gch').write_bytes(b'gpch')
            with self.assertRaisesRegex(RuntimeError,'unexpected candidate PCH'):cleanup.run()

    def test_symlink_anywhere_in_protected_tree_rejected(self):
        with fixture() as (root,_):
            (root/'unexpected-link').symlink_to(root/'report.json')
            with self.assertRaisesRegex(RuntimeError,'symlink in completed tree'):cleanup.run()

    def test_wrong_owner_and_active_scope_rejected(self):
        with fixture(),mock.patch.object(cleanup.os,'getuid',return_value=-1):
            with self.assertRaisesRegex(RuntimeError,'inventoried owner'):cleanup.run()
        with mock.patch.object(cleanup.subprocess,'run',return_value=subprocess.CompletedProcess([],0,
            'ActiveState=active\nSubState=running\n','')):
            with self.assertRaisesRegex(RuntimeError,'not inactive/dead'):cleanup.scope_inactive()


if __name__=='__main__':unittest.main()
