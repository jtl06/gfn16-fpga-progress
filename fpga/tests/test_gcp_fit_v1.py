"""Local packaging and mocked policy tests; no native/cloud jobs."""
import copy
import hashlib
import json
from pathlib import Path
import signal
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import Mock,patch

from cloud import gcp_fit_v1 as g
from synthesis.prepare import prepare


class GCPPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.project=self.root/'probe'
        prepare(self.project,'ntt27_prefetch_r2_host_broadcast64',aw=16,processors=4)
        self.rows=[dict(cpu=c,package_id=0,core_id=c%4) for c in range(8)]

    def test_four_physical_cores_no_smt_and_correct_worker(self):
        actual=g.validate_topology(self.rows,[0,1,2,3],g.HOST)
        self.assertEqual(actual['physical_cores'],[(0,0),(0,1),(0,2),(0,3)])
        for affinity in ([0,1,2,4],[4,5,6,7],[0,1,2],[False,True,2,3]):
            with self.assertRaises(ValueError):g.validate_topology(self.rows,affinity,g.HOST)
        with self.assertRaises(ValueError):g.validate_topology(self.rows,[0,1,2,3],'another-host')
        bad=copy.deepcopy(self.rows);bad[1]['core_id']=0
        with self.assertRaises(ValueError):g.validate_topology(bad,[0,1,2,3],g.HOST)
        with self.assertRaises(ValueError):g.validate_topology(self.rows[:-1],[0,1,2,3],g.HOST)

    def test_aggregate_and_ancestor_cgroup_limits(self):
        g.validate_limits('400000 100000',str(24<<30),[('max 100000','max')])
        for cpu,memory,parents in (('max 100000',str(g.MEMORY),()),('800000 100000',str(g.MEMORY),()),
            ('400000 100000','max',()),('400000 100000',str(g.MEMORY),[('200000 100000','max')]),
            ('400000 100000',str(g.MEMORY),[('max 100000',str(12<<30))])):
            with self.assertRaises(ValueError):g.validate_limits(cpu,memory,parents)

    def test_both_exact_wrappers_all_fields_and_host_lanes(self):
        for target in g.VARIANTS:
            for field in (1,2,3):
                with self.subTest(target=target,field=field):
                    project=self.root/f'{target}-{field}'
                    prepare(project,target,aw=16,field=field,processors=4)
                    context=g.verify_project(project)
                    self.assertEqual(context['qsf_parameters'],dict(AW=16,LANES=64,HOST_LANES=16,
                        P=g.FIELDS[field-1][0],Q=g.FIELDS[field-1][1]))
                    self.assertEqual(len(context['source_sha256']),7)

    def test_frozen_aws_validator_host_lanes_limitation_is_not_inherited(self):
        from cloud import aws_fit_v4
        with self.assertRaisesRegex(ValueError,'unexpected unmanifested QSF parameter'):
            aws_fit_v4.verify_project(self.project)
        self.assertEqual(g.verify_project(self.project)['qsf_parameters']['HOST_LANES'],16)

    def test_controls_are_exact_not_just_selected_qsf_assignments(self):
        qsf=self.project/'probe.qsf';original=qsf.read_text()
        for old,new in (('HOST_LANES 16','HOST_LANES 64'),('SEED 1','SEED 2'),
                        ('NUM_PARALLEL_PROCESSORS 4','NUM_PARALLEL_PROCESSORS 8'),
                        ('LANES 64','LANES 16')):
            qsf.write_text(original.replace(old,new))
            with self.assertRaises(ValueError):g.verify_project(self.project)
        qsf.write_text(original+'exec programmer dangerous\n')
        with self.assertRaises(ValueError):g.verify_project(self.project)
        qsf.write_text(original)
        run=self.project/'run.tcl';run.write_text(run.read_text()+'execute_module -tool asm\n')
        with self.assertRaisesRegex(ValueError,'syn/fit/sta script'):g.verify_project(self.project)

    def test_metadata_types_and_geometry_refuse_silent_defaults(self):
        path=self.project/'manifest.json';original=json.loads(path.read_text())
        for key,value in (('host_lanes',None),('host_lanes',64),('root_profile_format',1),
            ('compile_processors',True),('field',True),('bitstream_generation',True),
            ('device','different'),('clock_period_ns',5)):
            path.write_text(json.dumps(dict(original,**{key:value})))
            with self.assertRaises(ValueError):g.verify_project(self.project)

    def test_no_existing_execution_unlisted_sources_or_logs(self):
        for name in ('qdb','output_files','execution-context.json','execution-result.json','other.txt'):
            path=self.project/name;path.write_text('stale')
            with self.assertRaisesRegex(ValueError,'existing execution'):g.verify_project(self.project)
            path.rename(self.root/(name+'-retained'))
        extra=self.project/'rtl/extra.sv';extra.write_text('// extra')
        with self.assertRaises(ValueError):g.verify_project(self.project)
        extra.rename(self.root/'extra-retained')
        (self.root/'probe-fit.log').write_text('old')
        with self.assertRaisesRegex(ValueError,'existing log'):g.verify_project(self.project)

    def test_prepare_only_closed_fourteen_member_bundle_and_summary_pin(self):
        with patch.object(g.subprocess,'Popen',side_effect=AssertionError('NO PROCESS')):
            output=self.root/'prepared';contract=g.prepare(self.project,output)
            self.assertEqual(contract['status'],'prepared_not_executed')
            self.assertEqual(len(contract['files']),14)
            self.assertEqual(contract['summary_sha256'],g.SUMMARY_SHA)
            self.assertEqual(contract['timeout_seconds'],21600)
            with tarfile.open(output/'payload.tar.gz') as archive:
                self.assertEqual(set(archive.getnames()),set(contract['files']))
                for name,h in contract['files'].items():
                    self.assertEqual(hashlib.sha256(archive.extractfile(name).read()).hexdigest(),h)
            with self.assertRaises(FileExistsError):g.prepare(self.project,output)
            with patch.object(g,'SUMMARY_SHA','0'*64),self.assertRaisesRegex(ValueError,'summary script changed'):
                g.prepare(self.project,self.root/'bad-prepare')

    def test_staged_contract_exact_helpers_and_source_map(self):
        output=self.root/'prepared';contract=g.prepare(self.project,output)
        remote=self.root/'fake-remote';remote.mkdir()
        with tarfile.open(output/'payload.tar.gz') as archive:archive.extractall(remote,filter='data')
        manifest=output/'manifest.json'
        # Tests relocate only the fixed root field; real approved bytes bind ROOT.
        contract['root']=str(remote);manifest.write_text(json.dumps(contract));h=g.digest(manifest.read_bytes())
        with patch.object(g,'ROOT',remote),patch.object(g,'__file__',str(remote/'probe-helpers/gcp_fit_v1.py')):
            result,context=g.verify_contract(manifest,h)
            self.assertEqual(result,contract);self.assertEqual(context['qsf_parameters']['HOST_LANES'],16)
            with self.assertRaisesRegex(ValueError,'contract SHA'):g.verify_contract(manifest,'0'*64)
            (remote/'probe-helpers/unlisted.py').write_text('# wrong')
            with self.assertRaisesRegex(ValueError,'helper directory closure'):g.verify_contract(manifest,h)

    def test_single_job_lock_and_legacy_process_detection(self):
        lock=self.root/'global.lock'
        with g.locked(lock):
            with self.assertRaises(BlockingIOError):
                with g.locked(lock):pass
        fake=self.root/'proc';(fake/'1').mkdir(parents=True);(fake/'2').mkdir()
        (fake/'1/comm').write_text('quartus_fit\n');(fake/'2/comm').write_text('python3\n')
        self.assertEqual(g.active_quartus(fake),[{'pid':1,'name':'quartus_fit'}])

    def test_source_change_link_and_hardlink_refused(self):
        source=next((self.project/'rtl').iterdir());source.write_text('changed')
        with self.assertRaisesRegex(ValueError,'source SHA'):g.verify_project(self.project)
        alias=self.root/'alias';alias.symlink_to(source)
        with self.assertRaisesRegex(ValueError,'symlink'):g.read_regular(alias)
        import os
        link=self.root/'hardlink';os.link(source,link)
        with self.assertRaisesRegex(ValueError,'hard-linked'):g.read_regular(source)

    def test_bounded_timeout_and_interrupt_stop_only_owned_process_group(self):
        for error in (subprocess.TimeoutExpired(['quartus'],1),KeyboardInterrupt()):
            process=Mock(pid=9911);process.wait.side_effect=[error,0,0]
            with self.subTest(error=type(error)),patch.object(g.subprocess,'Popen',return_value=process),\
                 patch.object(g.os,'killpg') as kill:
                expected=TimeoutError if isinstance(error,subprocess.TimeoutExpired) else KeyboardInterrupt
                with self.assertRaises(expected):g.run_bounded(['quartus'],self.root/(type(error).__name__+'.log'),1)
                self.assertEqual(kill.call_args_list[0].args,(9911,signal.SIGTERM))
                self.assertEqual(kill.call_args_list[-1].args,(9911,signal.SIGKILL))

    def test_execution_off_host_refused_without_subprocess(self):
        with patch.object(g.socket,'gethostname',return_value='not-gcp'),\
             patch.object(g.subprocess,'Popen',side_effect=AssertionError('NO PROCESS')):
            with self.assertRaisesRegex(ValueError,'GCP worker'):g.launch(self.root/'missing','0'*64)


if __name__=='__main__':unittest.main()
