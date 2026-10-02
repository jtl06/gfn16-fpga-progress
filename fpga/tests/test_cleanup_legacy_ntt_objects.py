"""Synthetic fixtures only. All tested apply/unlink operations are mocked.

Never inventories remote paths or deletes any approved compiler objects.
"""
from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import cleanup_legacy_ntt_objects as cleanup


class LegacyCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.base=self.root/'work';self.base.mkdir()
        experiments=[];self.objects=[];self.executables=[]
        for name in cleanup.EXPERIMENTS:
            root=self.base/name/'fpga/artifacts';group=root/'run/lanes16';build=group/'build-test'
            build.mkdir(parents=True)
            obj=build/'compiler.o';obj.write_bytes(b'object-data');self.objects.append(obj)
            exe=build/'Vtop';exe.write_bytes(b'retained-executable');exe.chmod(0o755);self.executables.append(exe)
            (build/'generated.cpp').write_text('// source')
            (build/'nested').mkdir();(build/'nested/keep.o').write_bytes(b'nested-kept')
            (root/'cache').mkdir();(root/'cache/cached.a').write_bytes(b'cache-kept')
            (root/'top.log').write_text('log retained')
            report=group/'report.json';report.write_text(json.dumps(dict(status='passed')))
            experiments.append(dict(experiment=name,artifact_root=str(root),recommended=True,
                bytes=11,passed_report_groups={str(report):dict(bytes=11,files=1,status='passed',
                report_sha256=cleanup.digest(report),build_directories=[str(build)],retained_executable_names=['Vtop'])}))
        self.candidates=self.root/'candidates.json'
        self.candidates.write_text(json.dumps(dict(allowed_generated_suffixes=['.o','.a','.gch'],experiments=experiments)))
        for name,value in (('BASE',self.base),('EXPECTED_BUILDS',3),('EXPECTED_BYTES',33),
                           ('APPROVED_SHA256',cleanup.digest(self.candidates))):
            mock=patch.object(cleanup,name,value);mock.start();self.addCleanup(mock.stop)
        self.inactive=patch.object(cleanup,'inactive');self.inactive.start();self.addCleanup(self.inactive.stop)

    def save(self):
        record=cleanup.inventory(self.candidates);manifest=self.root/'manifest.json'
        manifest.write_text(json.dumps(record));return record,manifest,cleanup.digest(manifest)

    def reseal_candidates(self,data):
        self.candidates.write_text(json.dumps(data));cleanup.APPROVED_SHA256=cleanup.digest(self.candidates)

    def test_exact_inventory_has_required_identity_and_all_retained_hashes(self):
        record=cleanup.inventory(self.candidates)
        self.assertEqual(len(record['objects']),3)
        self.assertEqual(sum(x['size'] for x in record['objects']),33)
        self.assertEqual(set(record['objects'][0]),{'path','device','inode','nlink','size','mtime_ns','ctime_ns','mode'})
        self.assertEqual(len(record['protected']),18)
        self.assertTrue(any(p.endswith('/cache/cached.a') for p in record['protected']))
        self.assertTrue(any(p.endswith('/nested/keep.o') for p in record['protected']))
        self.assertTrue(all(p.exists() for p in self.objects))

    def test_agent_inventory_hash_and_exact_counts_are_required(self):
        self.candidates.write_text(self.candidates.read_text()+' ')
        with self.assertRaisesRegex(ValueError,'inventory SHA'):cleanup.inventory(self.candidates)
        cleanup.APPROVED_SHA256=cleanup.digest(self.candidates)
        self.objects[0].write_bytes(b'changed-size')
        with self.assertRaisesRegex(ValueError,'exact object inventory'):cleanup.inventory(self.candidates)

    def test_report_hash_and_pass_status_are_independent(self):
        data=json.loads(self.candidates.read_text());name=next(iter(data['experiments'][0]['passed_report_groups']))
        report=Path(name);report.write_text(json.dumps(dict(status='running')))
        with self.assertRaisesRegex(ValueError,'report SHA changed'):cleanup.inventory(self.candidates)
        data['experiments'][0]['passed_report_groups'][name]['report_sha256']=cleanup.digest(report)
        self.reseal_candidates(data)
        with self.assertRaisesRegex(ValueError,'not currently passed'):cleanup.inventory(self.candidates)

    def test_hardlinked_or_executable_objects_are_never_eligible(self):
        obj=self.objects[0];os.link(obj,self.root/'shared-object')
        with self.assertRaisesRegex(ValueError,'shared compiler object'):cleanup.inventory(self.candidates)

    def test_executable_suffix_and_elf_executable_are_preserved(self):
        obj=self.objects[0];obj.chmod(0o755)
        with self.assertRaisesRegex(ValueError,'exact object inventory'):cleanup.inventory(self.candidates)
        obj.chmod(0o644);header=bytearray(20);header[:4]=b'\x7fELF';header[5]=1;header[16:18]=(2).to_bytes(2,'little')
        obj.write_bytes(header)
        self.assertTrue(cleanup.executable(obj,cleanup.identity(obj)))

    def test_symlinks_and_missing_executables_refuse_inventory(self):
        (self.objects[0].parent/'link').symlink_to(self.root/'anything')
        with self.assertRaisesRegex(ValueError,'symlink'):cleanup.inventory(self.candidates)

    def test_missing_retained_executable_refuses_inventory(self):
        self.executables[0].rename(self.executables[0].with_name('renamed'))
        with self.assertRaisesRegex(ValueError,'retained executable missing'):cleanup.inventory(self.candidates)

    def test_frozen_manifest_hash_checked_before_any_unlink(self):
        record,manifest,h=self.save()
        with patch.object(cleanup.os,'unlink') as unlink:
            with self.assertRaisesRegex(ValueError,'manifest SHA changed'):
                cleanup.apply(self.candidates,manifest,'0'*64)
            unlink.assert_not_called()

    def test_changed_object_or_retained_file_blocks_apply_before_unlink(self):
        record,manifest,h=self.save();self.objects[0].write_bytes(b'OBJECT-DATA')
        with patch.object(cleanup,'compiler_lock',return_value=nullcontext()),patch.object(cleanup.os,'unlink') as unlink:
            with self.assertRaisesRegex(ValueError,'pre-apply snapshot changed'):
                cleanup.apply(self.candidates,manifest,h)
            unlink.assert_not_called()

    def test_changed_retained_file_blocks_apply(self):
        record,manifest,h=self.save();self.executables[0].write_bytes(b'changed')
        with patch.object(cleanup,'compiler_lock',return_value=nullcontext()),patch.object(cleanup.os,'unlink') as unlink:
            with self.assertRaisesRegex(ValueError,'pre-apply snapshot changed: protected'):
                cleanup.apply(self.candidates,manifest,h)
            unlink.assert_not_called()

    def test_apply_uses_exact_names_and_dirfds_but_test_never_deletes(self):
        record,manifest,h=self.save()
        pre={key:record[key] for key in ('objects','protected','directories')}
        post={**pre,'objects':[]}
        with patch.object(cleanup,'compiler_lock',return_value=nullcontext()), \
             patch.object(cleanup,'scan',side_effect=[pre,post]),patch.object(cleanup.os,'unlink') as unlink:
            result=cleanup.apply(self.candidates,manifest,h)
            self.assertEqual(result['files_removed'],3)
            self.assertEqual(unlink.call_count,3)
            self.assertTrue(all(call.args==('compiler.o',) and 'dir_fd' in call.kwargs for call in unlink.call_args_list))
        self.assertTrue(all(path.exists() for path in self.objects))
        self.assertIn('completed_all_retained_hashes_verified',Path(result['journal']).read_text())

    def test_postvalidation_failure_is_journaled_and_no_success_claim(self):
        record,manifest,h=self.save();pre={k:record[k] for k in ('objects','protected','directories')}
        post={**pre,'objects':[],'protected':{}}
        with patch.object(cleanup,'compiler_lock',return_value=nullcontext()), \
             patch.object(cleanup,'scan',side_effect=[pre,post]),patch.object(cleanup.os,'unlink'):
            with self.assertRaisesRegex(ValueError,'retained files/identities changed'):
                cleanup.apply(self.candidates,manifest,h)
        events=[json.loads(line) for line in manifest.with_name(manifest.name+'.apply.jsonl').read_text().splitlines()]
        self.assertEqual(events[-1]['status'],'stopped_partial_or_failed')
        self.assertEqual(events[-1]['removed_count'],3)
        self.assertTrue(all(path.exists() for path in self.objects))

    def test_final_file_identity_is_rechecked_before_unlink(self):
        record=cleanup.inventory(self.candidates);row=record['objects'][0]
        Path(row['path']).write_bytes(b'OBJECT-DATA')
        with patch.object(cleanup.os,'unlink') as unlink:
            with self.assertRaisesRegex(ValueError,'identity changed before unlink'):
                cleanup.remove_exact(row,record['directories'],record['approved_scope']['roots'])
            unlink.assert_not_called()

    def test_new_active_process_blocks_final_unlink(self):
        record=cleanup.inventory(self.candidates);row=record['objects'][0]
        with patch.object(cleanup,'inactive',side_effect=ValueError('active process')), \
             patch.object(cleanup.os,'unlink') as unlink:
            with self.assertRaisesRegex(ValueError,'active process'):
                cleanup.remove_exact(row,record['directories'],record['approved_scope']['roots'])
            unlink.assert_not_called()

    def test_compile_lock_contention_blocks_apply_without_unlink(self):
        record,manifest,h=self.save()
        with patch.object(cleanup,'compiler_lock',side_effect=BlockingIOError('busy compiler lock')), \
             patch.object(cleanup.os,'unlink') as unlink:
            with self.assertRaises(BlockingIOError):cleanup.apply(self.candidates,manifest,h)
            unlink.assert_not_called()

    def test_replaced_build_directory_blocks_unlink(self):
        record=cleanup.inventory(self.candidates);row=record['objects'][0];build=Path(row['path']).parent
        build.rename(build.with_name('old-build'));build.mkdir();(build/'compiler.o').write_bytes(b'object-data')
        with patch.object(cleanup.os,'unlink') as unlink:
            with self.assertRaisesRegex(ValueError,'build directory replaced'):
                cleanup.remove_exact(row,record['directories'],record['approved_scope']['roots'])
            unlink.assert_not_called()

    def test_real_approved_inventory_excludes_vector_and_folded(self):
        # Local read-only audit of the user-approved candidate file when present.
        original=Path('/private/tmp/ntt-object-candidates-20260929.json')
        if not original.exists():self.skipTest('local candidate audit not present')
        with patch.object(cleanup,'BASE',Path('/home/jtl/gfn-fpga-lab/agent-work')), \
             patch.object(cleanup,'EXPECTED_BUILDS',84),patch.object(cleanup,'EXPECTED_BYTES',14_140_462_060), \
             patch.object(cleanup,'APPROVED_SHA256','2cd250649181258c424b239966d75ed4d3c774cceb67b08fa847adaa6b18d5dd'):
            scope=cleanup.scope(original)
        self.assertEqual(len(scope['builds']),84)
        self.assertEqual(sum(g['bytes'] for g in scope['reports'].values()),14_140_462_060)
        self.assertTrue(all('folded' not in r and 'ntt-vector' not in r for r in scope['roots']))


class ProcessChecksTests(unittest.TestCase):
    def test_cmd_cwd_and_exe_each_block(self):
        for kind in ('cmd','cwd','exe'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);proc=root/'proc';entry=proc/'99999999';entry.mkdir(parents=True)
                target='/approved/legacy/artifacts'
                (entry/'cmdline').write_bytes((target+'/job' if kind=='cmd' else 'idle').encode())
                (entry/'cwd').symlink_to(target if kind=='cwd' else '/unrelated')
                (entry/'exe').symlink_to(target+'/Vtop' if kind=='exe' else '/usr/bin/sleep')
                with self.assertRaisesRegex(ValueError,'active process'):
                    cleanup.inactive([target],proc)

    def test_opaque_live_process_is_not_silently_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc=Path(tmp);entry=proc/'99999999';entry.mkdir();(entry/'cmdline').write_bytes(b'live')
            with self.assertRaisesRegex(ValueError,'opaque live process'):cleanup.inactive(['/approved'],proc)

    def test_proc_permission_failure_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc=Path(tmp);entry=proc/'99999999';entry.mkdir();(entry/'cmdline').write_bytes(b'live')
            with patch.object(cleanup.os,'readlink',side_effect=PermissionError('denied')):
                with self.assertRaisesRegex(ValueError,'insufficient /proc visibility'):
                    cleanup.inactive(['/approved'],proc)


if __name__=='__main__':unittest.main()
