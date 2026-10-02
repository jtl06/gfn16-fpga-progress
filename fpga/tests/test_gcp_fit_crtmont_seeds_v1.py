"""P3 source-only preparation/admission negatives; no native/cloud execution."""
import copy
import importlib.util
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from fpga.cloud import gcp_fit_crtmont_seeds_v1 as a


class SeedTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.out=self.root/'prepared'
        with patch.object(a.base.subprocess,'Popen',side_effect=AssertionError('NO NATIVE PROCESS')):
            self.prep=a.prepare(self.out)
        self.project=self.out/'seed2'/a.probe_name(2)

    def test_both_exact_seed_only_projects_and_frozen_parent(self):
        parent=(a.PARENT_PROJECT/'probe.qsf').read_bytes()
        before={p.name:a.digest(p.read_bytes()) for p in (a.PARENT_PROJECT/'rtl').iterdir()}
        for seed in (2,3):
            stage=self.out/f'seed{seed}';project=stage/a.probe_name(seed)
            context=a.verify_project(project)
            self.assertEqual(context['qsf_parameters'],dict(AW=16,NTT_LANES=64))
            self.assertEqual(context['source_sha256'],before)
            self.assertEqual((project/'probe.qsf').read_bytes().replace(f'SEED {seed}\n'.encode(),b'SEED 1\n'),parent)
            for name in ('probe.qpf','probe.sdc','run.tcl'):
                self.assertEqual((project/name).read_bytes(),(a.PARENT_PROJECT/name).read_bytes())
            self.assertFalse(context['promotion_allowed']);self.assertIsNone(context['usable_clock_mhz'])
            self.assertFalse(context['runtime_single_variable_comparison'])

    def test_closed_payloads_and_explicit_gcp_limits(self):
        for seed,row in self.prep['projects'].items():
            stage=self.out/row['stage'];contract=json.loads((stage/'deployment-contract.json').read_text())
            self.assertEqual(row['payload_files'],27)
            self.assertEqual(contract['affinity'],[0,1,2,3]);self.assertEqual(contract['memory_max_bytes'],24<<30)
            self.assertEqual(contract['memory_swap_max_bytes'],0);self.assertEqual(contract['cpu_quota_percent'],400)
            self.assertEqual(contract['timeout_seconds'],21600)
            with tarfile.open(stage/'payload.tar.gz') as archive:
                members=archive.getmembers();self.assertEqual(len(members),27)
                self.assertTrue(all(m.isfile() for m in members));self.assertEqual(len(set(m.name for m in members)),27)
                self.assertEqual({m.name:a.digest(archive.extractfile(m).read()) for m in members},contract['files'])
        with self.assertRaises(ValueError):a.prepare(self.out)

    def test_other_seeds_and_boolean_geometry_rejected(self):
        for seed in (1,4,True,'2'):
            with self.assertRaises(ValueError):a.probe_name(seed)
        path=self.project/'manifest.json';original=path.read_text();manifest=json.loads(original)
        for key,value in [('compile_processors',6),('address_width',5),('seed',True),('clock_period_ns',9.6),
                          ('promotion_allowed',True),('usable_clock_mhz',100),('source_correctness','T5'),('physical_device_verified',True)]:
            path.write_text(json.dumps(dict(manifest,**{key:value})))
            with self.assertRaises(ValueError):a.verify_project(self.project)
        path.write_text(original)

    def test_seed_worker_qsf_and_stage_injection_refused(self):
        path=self.project/'probe.qsf';original=path.read_text()
        for changed in (original.replace('SEED 2','SEED 3'),original.replace('PROCESSORS 4','PROCESSORS 6'),
                        original.replace('NTT_LANES 64','NTT_LANES 16'),original+'exec unexpected\n'):
            path.write_text(changed)
            with self.assertRaises(ValueError):a.verify_project(self.project)
        path.write_text(original)
        path=self.project/'run.tcl';path.write_text(path.read_text()+'execute_module -tool asm\n')
        with self.assertRaises(ValueError):a.verify_project(self.project)

    def test_extra_or_changed_rtl_and_existing_execution_refused(self):
        extra=self.project/'rtl/extra.sv';extra.write_text('// extra')
        with self.assertRaises(ValueError):a.verify_project(self.project)
        extra.rename(self.root/'retained-extra.sv')
        stale=self.project/'execution-context.json';stale.write_text('{}')
        with self.assertRaises(ValueError):a.verify_project(self.project)
        stale.rename(self.root/'retained-context.json')
        rtl=next((self.project/'rtl').iterdir());rtl.write_text('// changed')
        with self.assertRaises(ValueError):a.verify_project(self.project)

    def test_exact_staged_adapter_contract_and_helper_drift(self):
        stage=self.out/'seed2';helpers=stage/(a.probe_name(2)+'-helpers')
        spec=importlib.util.spec_from_file_location('_test_seed_staged',helpers/a.ADAPTER)
        staged=importlib.util.module_from_spec(spec);spec.loader.exec_module(staged)
        contract=json.loads((stage/'deployment-contract.json').read_text());contract['root']=str(stage)
        path=self.root/'relocated-test-contract.json';path.write_text(json.dumps(contract));pin=a.digest(path.read_bytes())
        with patch.object(staged.base,'ROOT',stage):
            checked,context=staged.verify_contract(path,pin)
            self.assertEqual(checked,contract);self.assertEqual(context['seed'],2)
            with self.assertRaises(ValueError):staged.verify_contract(path,'0'*64)
            (helpers/'summarize.py').write_text('# changed')
            with self.assertRaises(ValueError):staged.verify_contract(path,pin)

    def test_off_host_execution_cannot_start_a_process(self):
        with patch.object(a.base.subprocess,'Popen',side_effect=AssertionError('NO PROCESS')), \
             patch.object(a.base.socket,'gethostname',return_value='not-gcp'):
            with self.assertRaisesRegex(ValueError,'GCP worker'):
                a.launch(self.root/'missing','0'*64)

    def test_four_physical_core_limits_inherited_without_weakening(self):
        rows=[dict(cpu=c,package_id=0,core_id=c%4) for c in range(8)]
        a.base.validate_topology(rows,[0,1,2,3],a.base.HOST)
        a.base.validate_limits('400000 100000',str(24<<30))
        with self.assertRaises(ValueError):a.base.validate_topology(rows,[0,1,2,4],a.base.HOST)
        with self.assertRaises(ValueError):a.base.validate_limits('600000 100000',str(20<<30))

    def test_zero_swap_strengthening_and_restored_policy(self):
        group=self.root/'cgroup';group.mkdir();swap=group/'memory.swap.max';swap.write_text('0')
        original=a.base.verify_contract
        with patch.object(a.base,'live_limits',return_value={'cgroup_path':str(group)}), \
             patch.object(a.base,'launch',side_effect=lambda *args:a.base.live_limits()):
            self.assertEqual(a.launch(None,None)['memory_swap_max_bytes'],0)
            swap.write_text('max')
            with self.assertRaises(ValueError):a.launch(None,None)
        self.assertIs(a.base.verify_contract,original)


if __name__=='__main__':unittest.main()
