"""Exact P2 admission and frozen execution-guard lineage; no vendor processes."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from fpga.cloud import gcp_stream27_p2_fit_v1 as p

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT/'artifacts/stream27-field-physical-probe-aw16-p8-f0-prepared-v2/project'


class P2GCPAdmission(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name).resolve();self.project=self.root/'p2'
        shutil.copytree(PROJECT,self.project)

    def test_exact_project_and_provisional_scope(self):
        context=p.verify_project(self.project)
        self.assertEqual(context['manifest_sha256'],p.PROJECT_SHA)
        self.assertEqual(len(context['source_sha256']),10)
        self.assertEqual(context['qsf_parameters'],{'AW':16})

    def test_frozen_shared_execution_guards_are_byte_identical(self):
        raw=(ROOT/'cloud/gcp_fit_v3.py').read_bytes();old=raw.decode();new=p.adapted_source(raw)
        def functions(source):
            return {node.name:ast.get_source_segment(source,node) for node in ast.parse(source).body
                    if isinstance(node,ast.FunctionDef)}
        a,b=functions(old),functions(new)
        changed={name for name in a if a[name]!=b[name]}
        self.assertEqual(changed,{'prepare','verify_contract','launch'})
        for name in ('validate_limits','live_limits','validate_topology','locked','active_quartus',
                     'run_bounded','read_regular','qsf_version_update'):
            self.assertEqual(a[name],b[name])
        with self.assertRaisesRegex(ValueError,'frozen GCP'):
            p.adapted_source(raw+b'\n')

    def test_manifest_control_source_drift_and_extra_refused(self):
        for name in ('manifest.json','probe.qsf','probe.qpf','probe.sdc','run.tcl',
                     'rtl/genefer_stream27_field_physical_probe_aw16_p8_f0_v1.sv'):
            path=self.project/name;original=path.read_bytes()
            path.write_bytes(original+b'\n')
            with self.subTest(name=name),self.assertRaises(ValueError):p.verify_project(self.project)
            path.write_bytes(original)
        for name in ('extra.txt','rtl/extra.sv','execution-result.json'):
            path=self.project/name;path.write_text('extra')
            with self.subTest(name=name),self.assertRaises(ValueError):p.verify_project(self.project)
            path.rename(self.root/name.replace('/','-'))

    def test_links_and_existing_outputs_refused(self):
        path=self.project/'probe.sdc';original=path.read_bytes();path.rename(self.root/'sdc-retained')
        path.symlink_to(self.root/'sdc-retained')
        with self.assertRaisesRegex(ValueError,'symlink'):p.verify_project(self.project)
        path.rename(self.root/'symlink-retained');path.write_bytes(original)
        (self.root/'p2-fit.log').write_text('earlier failure retained')
        with self.assertRaisesRegex(ValueError,'existing log'):p.verify_project(self.project)

    def test_closed_packet_and_staged_contract(self):
        with patch.object(p.runner.subprocess,'Popen',side_effect=AssertionError('no vendor process')):
            output=self.root/'packet';contract=p.prepare(self.project,output)
        self.assertEqual(len(contract['files']),18)
        self.assertEqual(contract['project']['manifest_sha256'],p.PROJECT_SHA)
        self.assertEqual(contract['affinity'],[0,1,2,3])
        self.assertEqual(contract['cpu_quota_percent'],400)
        self.assertEqual(contract['memory_max_bytes'],24<<30)
        self.assertEqual(contract['timeout_seconds'],21600)
        remote=self.root/'remote';remote.mkdir()
        with tarfile.open(output/'deployment/payload.tar.gz') as archive:
            self.assertEqual(set(archive.getnames()),set(contract['files']))
            self.assertTrue(all(m.isfile() for m in archive.getmembers()))
            for name,pin in contract['files'].items():
                self.assertEqual(hashlib.sha256(archive.extractfile(name).read()).hexdigest(),pin)
            archive.extractall(remote,filter='data')
        # Relocate only the fixed root for a local source-only verification.
        contract['root']=str(remote);manifest=self.root/'test-contract.json'
        manifest.write_text(json.dumps(contract));pin=hashlib.sha256(manifest.read_bytes()).hexdigest()
        staged=remote/contract['helper_directory']/p.LAUNCHER
        with patch.object(p.runner,'ROOT',remote),patch.object(p.runner,'__file__',str(staged)):
            self.assertEqual(p.runner.verify_contract(manifest,pin)[0],contract)
            with self.assertRaisesRegex(ValueError,'contract SHA'):p.runner.verify_contract(manifest,'0'*64)
            (staged.parent/'extra.py').write_text('unlisted')
            with self.assertRaisesRegex(ValueError,'helper directory closure'):p.runner.verify_contract(manifest,pin)

    def test_frozen_topology_caps_and_offhost_execution(self):
        g=p.runner;rows=[dict(cpu=c,package_id=0,core_id=c%4) for c in range(8)]
        g.validate_topology(rows,[0,1,2,3],g.HOST)
        g.validate_limits('400000 100000',str(24<<30))
        for affinity in ([0,1,2,4],[4,5,6,7]):
            with self.assertRaises(ValueError):g.validate_topology(rows,affinity,g.HOST)
        with self.assertRaises(ValueError):g.validate_limits('600000 100000',str(24<<30))
        with patch.object(g.socket,'gethostname',return_value='not-gcp'),\
             patch.object(g.subprocess,'Popen',side_effect=AssertionError('no vendor')):
            with self.assertRaises(ValueError):g.launch(self.root/'missing','0'*64)


if __name__=='__main__':unittest.main()
