"""Local synthetic planner tests; no cloud calls, subprocesses or live jobs."""
import copy
from datetime import datetime,timezone
import json
from pathlib import Path
import tempfile
import unittest

from cloud.fit_queue_plan import Refused,canonical,digest,plan


class FitQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.now=datetime(2026,10,1,0,0,tzinfo=timezone.utc)
        self.req=dict(schema_version=1,observation_max_age_seconds=300,
            worker=dict(id="synthetic-worker",observed_at=self.now.isoformat(),
                observation_source="synthetic sysfs/affinity fixture, not a live host",
                cpus=[dict(cpu=c,package_id=p,core_id=k) for c,p,k in
                      [(2,0,9),(19,0,9),(8,0,3),(27,0,3),(41,1,3),(55,1,3),(68,1,9),(91,1,9)]],
                allowed_cpus=[2,19,8,27,41,55,68,91],reserved_cpus=[],
                memory_bytes=64*1024**3,reserved_memory_bytes=8*1024**3),active=[],jobs=[])

    def job(self,name="one",cores=2,memory=16,priority=5):
        source=("module "+name+"; endmodule\n").encode()
        source_hash=digest(source)
        manifest=dict(top=name,edition="pro",compile_processors=cores,
                      allowed_stages=["syn","fit","sta"],bitstream_generation=False,
                      source_sha256={name+".sv":source_hash})
        qsf=(f"set_global_assignment -name TOP_LEVEL_ENTITY {name}\n"
             f"set_global_assignment -name NUM_PARALLEL_PROCESSORS {cores}\n"
             f"set_global_assignment -name SYSTEMVERILOG_FILE rtl/{name}.sv\n"
             "set_global_assignment -name SDC_FILE probe.sdc\n")
        contents={"manifest.json":canonical(manifest),"probe.qsf":qsf.encode(),
                  "probe.qpf":b'PROJECT_REVISION = "probe"\n',"probe.sdc":b"# test only\n",
                  "run.tcl":b"# never executed synthetic input\n","rtl/"+name+".sv":source}
        hashes={n:digest(b) for n,b in contents.items()}
        snapshot_hash=digest(canonical(hashes));snapshot=self.root/snapshot_hash
        snapshot.mkdir();(snapshot/"rtl").mkdir()
        for n,b in contents.items():(snapshot/n).write_bytes(b)
        gate=dict(status="passed",source_sha256={"rtl/kernel/"+name+".sv":source_hash},
                  geometry=dict(aw=16,lanes=64),source_hashes_rechecked=True)
        gate_path=self.root/(name+"-gate.json");gate_path.write_bytes(canonical(gate))
        return dict(id=name,priority=priority,physical_cores=cores,memory_bytes=memory*1024**3,
                    snapshot_path=str(snapshot),snapshot_sha256=snapshot_hash,input_sha256=hashes,
                    execution_path=str(self.root/(name+"-execution")),stage="fit",
                    gate=dict(path=str(gate_path),sha256=digest(canonical(gate)),
                              checks={"/geometry":{"aw":16,"lanes":64}}))

    def gate_change(self,job,key,value):
        path=Path(job['gate']['path']);obj=json.loads(path.read_text());obj[key]=value
        path.write_bytes(canonical(obj));job['gate']['sha256']=digest(canonical(obj))

    def reseal(self,job):
        snapshot=Path(job['snapshot_path'])
        hashes={p.relative_to(snapshot).as_posix():digest(p.read_bytes())
                for p in snapshot.rglob('*') if p.is_file()}
        h=digest(canonical(hashes));new=snapshot.with_name(h);snapshot.rename(new)
        job.update(snapshot_path=str(new),snapshot_sha256=h,input_sha256=hashes)

    def refusal(self,request,fragment):
        with self.assertRaisesRegex(Refused,fragment):plan(request,self.now)

    def test_noncontiguous_cross_socket_topology_and_priority(self):
        self.req['jobs']=[self.job('low',priority=1),self.job('high',priority=9)]
        result=plan(self.req,self.now)
        self.assertEqual([j['job_id'] for j in result['dispatch']],['high','low'])
        self.assertEqual(result['dispatch'][0]['cpus'],[8,2])
        self.assertEqual(result['dispatch'][1]['cpus'],[41,68])
        self.assertEqual(result['dispatch'][0]['stage_sequence'],['syn','fit','sta'])
        self.assertFalse(result['execution_authorized'])
        self.assertTrue(result['manual_budget_review_required_before_launch'])
        self.assertFalse(any(Path(j['execution_path']).exists() for j in self.req['jobs']))

    def test_reserving_sibling_reserves_entire_physical_core(self):
        self.req['worker']['reserved_cpus']=[19]
        self.req['jobs']=[self.job('large',cores=4),self.job('small',cores=2)]
        result=plan(self.req,self.now)
        self.assertEqual(result['deferred'][0]['job_id'],'large')
        self.assertEqual(result['dispatch'][0]['cpus'],[8,41])

    def test_memory_overcommit_deferred_and_small_job_backfills(self):
        self.req['jobs']=[self.job('large',memory=60,priority=9),self.job('small',memory=16)]
        result=plan(self.req,self.now)
        self.assertEqual(result['deferred'][0]['reasons'],['insufficient_free_memory'])
        self.assertEqual(len(result['dispatch']),1)

    def test_running_failed_or_incomplete_gates_refused(self):
        for index,status in enumerate(('running','failed','pending')):
            with self.subTest(status=status):
                job=self.job('job'+str(index));self.gate_change(job,'status',status)
                self.req['jobs']=[job];self.refusal(self.req,'completed passed gate')

    def test_gate_hash_source_and_configuration_are_independently_checked(self):
        job=self.job();self.req['jobs']=[job]
        job['gate']['sha256']='0'*64;self.refusal(self.req,'stale gate hash')
        job['gate']['sha256']=digest(Path(job['gate']['path']).read_bytes())
        self.gate_change(job,'geometry',dict(aw=10,lanes=64));self.refusal(self.req,'configuration mismatch')
        self.gate_change(job,'geometry',dict(aw=16,lanes=64))
        self.gate_change(job,'source_sha256',{'rtl/kernel/one.sv':'0'*64})
        self.refusal(self.req,'gate source mismatch')

    def test_missing_stale_extra_and_symlinked_sources_refused(self):
        for index,mode in enumerate(('missing','stale','extra','symlink')):
            with self.subTest(mode=mode):
                job=self.job('src'+str(index));self.req['jobs']=[job]
                snapshot=Path(job['snapshot_path']);source=snapshot/'rtl'/('src'+str(index)+'.sv')
                if mode=='missing':source.unlink()
                if mode=='stale':source.write_text('changed')
                if mode=='extra':(snapshot/'untracked.txt').write_text('extra')
                if mode=='symlink':
                    saved=self.root/('saved'+str(index));source.rename(saved);source.symlink_to(saved)
                self.refusal(self.req,'closure|stale snapshot|symlink')

    def test_gate_ambiguous_sources_and_failed_recheck_refused(self):
        job=self.job();self.req['jobs']=[job]
        self.gate_change(job,'source_hashes_rechecked',False)
        self.refusal(self.req,'source recheck failed')
        self.gate_change(job,'source_hashes_rechecked',True)
        h=job['input_sha256']['rtl/one.sv']
        self.gate_change(job,'source_sha256',{'rtl/kernel/one.sv':h,'/x/rtl/kernel/one.sv':h})
        self.refusal(self.req,'ambiguity')

    def test_snapshot_content_address_and_execution_separation(self):
        job=self.job();self.req['jobs']=[job]
        original=job['snapshot_sha256'];job['snapshot_sha256']='0'*64
        self.refusal(self.req,'content-addressed')
        job['snapshot_sha256']=original;job['execution_path']=job['snapshot_path']+'/work'
        self.refusal(self.req,'overlaps immutable')

    def test_repinned_qsf_cannot_change_manifest_parameters_or_top(self):
        for index,extra in enumerate(('set_parameter -name AW 10\n',
                                     'set_global_assignment -name TOP_LEVEL_ENTITY different\n',
                                     'set_global_assignment -name NUM_PARALLEL_PROCESSORS 4\n')):
            job=self.job('control'+str(index));self.req['jobs']=[job]
            qsf=Path(job['snapshot_path'])/'probe.qsf';qsf.write_text(qsf.read_text()+extra)
            self.reseal(job)
            self.refusal(self.req,'parameter mismatch|top mismatch|worker count mismatch')

    def test_execution_directory_cannot_contain_another_snapshot(self):
        one=self.job('one');two=self.job('two')
        one['execution_path']=two['snapshot_path']+'/execution'
        self.req['jobs']=[one,two]
        self.refusal(self.req,'another immutable snapshot')

    def active(self,name='active',cpus=None,memory=16):
        return dict(job_id=name,state='running',snapshot_sha256=digest(name.encode()),
                    cpus=cpus or [8,2],memory_bytes=memory*1024**3,
                    execution_path=str(self.root/(name+'-active')))

    def test_active_reservation_excludes_siblings_and_accounts_memory(self):
        self.req['active']=[self.active()];self.req['jobs']=[self.job()]
        result=plan(self.req,self.now)
        self.assertEqual(result['dispatch'][0]['cpus'],[41,68])
        self.assertEqual(result['reserved_memory_bytes'],40*1024**3)

    def test_active_smt_overlap_duplicate_and_memory_overcommit_refused(self):
        self.req['active']=[self.active(cpus=[2,19])];self.refusal(self.req,'SMT siblings')
        self.req['active']=[self.active(),self.active('second',cpus=[19,41])]
        self.refusal(self.req,'physical-core overlap')
        self.req['active']=[self.active(),self.active()];self.refusal(self.req,'duplicate active job')
        self.req['active']=[self.active(memory=60)];self.refusal(self.req,'active memory overcommit')

    def test_duplicate_queued_or_active_project_refused(self):
        job=self.job();self.req['jobs']=[job,copy.deepcopy(job)]
        self.refusal(self.req,'duplicate queued/active job')
        self.req['jobs'][1]['id']='different';self.refusal(self.req,'duplicate queued/active project')
        self.req['jobs']=[job];active=self.active();active['snapshot_sha256']=job['snapshot_sha256']
        self.req['active']=[active];self.refusal(self.req,'duplicate queued/active project')

    def test_overlapping_execution_paths_refused(self):
        one=self.job('one');two=self.job('two');two['execution_path']=one['execution_path']+'/nested'
        self.req['jobs']=[one,two];self.refusal(self.req,'overlapping execution paths')

    def test_worker_evidence_must_be_fresh_and_topology_unambiguous(self):
        self.req['worker']['observed_at']='2026-09-30T00:00:00Z'
        self.refusal(self.req,'stale or future')
        self.req['worker']['observed_at']='2026-10-02T00:00:00Z'
        self.refusal(self.req,'stale or future')
        self.req['worker']['observed_at']=self.now.isoformat()
        self.req['worker']['cpus'].append(self.req['worker']['cpus'][0])
        self.refusal(self.req,'duplicate logical CPU')

    def test_unsupported_stage_and_untyped_resources_refused(self):
        job=self.job();self.req['jobs']=[job];job['stage']='asm'
        self.refusal(self.req,'unsupported stage')
        job['stage']='fit';job['physical_cores']=True;self.refusal(self.req,'invalid physical cores')
        job['physical_cores']=4;self.refusal(self.req,'worker count differs')

    def test_sixty_four_logical_cpu_fixture_six_jobs_no_numbering_assumption(self):
        worker=self.req['worker']
        worker['cpus']=[dict(cpu=100+3*c+s,package_id=c//16,core_id=c%16)
                        for c in range(32) for s in (0,1)]
        worker['allowed_cpus']=[r['cpu'] for r in worker['cpus']]
        worker['memory_bytes']=256*1024**3;worker['reserved_memory_bytes']=16*1024**3
        self.req['jobs']=[self.job('fit'+str(i),cores=4,memory=24) for i in range(6)]
        result=plan(self.req,self.now)
        self.assertEqual(len(result['dispatch']),6)
        cores=[tuple(c) for job in result['dispatch'] for c in job['physical_core_ids']]
        self.assertEqual(len(set(cores)),24)
        self.assertEqual(result['reserved_memory_bytes'],160*1024**3)

    def test_existing_atomic_core_configuration_validator_cannot_be_skipped(self):
        from synthesis.prepare import prepare
        # Real prepared controls plus archived gate: no simulation or compiler.
        fpga=Path(__file__).resolve().parents[1]
        gate_path=fpga/'results/throughput-20260929/core27-final/normalized/core27-64-16-report.json'
        gate=json.loads(gate_path.read_text())
        prepared=self.root/'prepared'
        prepare(prepared,'square_core27_ntt64_carry16',aw=16,processors=2)
        hashes={p.relative_to(prepared).as_posix():digest(p.read_bytes())
                for p in prepared.rglob('*') if p.is_file()}
        snapshot_hash=digest(canonical(hashes));snapshot=self.root/snapshot_hash
        prepared.rename(snapshot)
        local_gate=self.root/'archived-gate.json';local_gate.write_bytes(canonical(gate))
        job=dict(id='core',priority=5,physical_cores=2,memory_bytes=16*1024**3,
                 snapshot_path=str(snapshot),snapshot_sha256=snapshot_hash,input_sha256=hashes,
                 execution_path=str(self.root/'core-execution'),stage='fit',
                 gate=dict(path=str(local_gate),sha256=digest(canonical(gate)),
                           checks={'/configuration/ntt_lanes':64}))
        self.req['jobs']=[job]
        result=plan(self.req,self.now)
        self.assertEqual(result['dispatch'][0]['configuration_validator'],
                         'existing_exact_atomic27_profile_source_basis_validator')
        # Deliberately weak caller assertion does not bypass the profile check.
        job['gate']['checks']={'/status':'passed'}
        changed=copy.deepcopy(gate['configuration']);changed['ntt_lanes']=16
        self.gate_change(job,'configuration',changed)
        with self.assertRaisesRegex(ValueError,'architecture/profile mismatch'):plan(self.req,self.now)


if __name__=='__main__':unittest.main()
