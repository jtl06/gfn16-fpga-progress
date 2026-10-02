"""Local launcher policy tests. subprocess.run is never allowed to execute."""
import copy
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cloud import aws_fit_v4 as fit
from synthesis.prepare import prepare


class TopologyTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,1,tzinfo=timezone.utc)
        # Interleaved IDs, repeated core IDs across sockets, arbitrary SMT IDs.
        self.rows=[dict(cpu=100+3*c+s,package_id=c//8,core_id=c%8)
                   for c in range(16) for s in (0,1)]
        self.doc=dict(hostname=fit.HOST,observed_at=self.now.isoformat(),cpus=self.rows,
                      slots={name:[100+3*c for c in range(4*i,4*i+4)] for i,name in enumerate('abcd')})

    def check(self,document=None,slot='a',affinity=None,live=None,hostname=None,now=None):
        return fit.validate_topology(document or self.doc,slot,
            self.doc['slots'][slot] if affinity is None else affinity,
            live or self.rows,hostname or fit.HOST,now or self.now)

    def test_all_slots_accept_actual_noncontiguous_ids(self):
        used=[]
        for slot in 'abcd':
            result=self.check(slot=slot);used+=result['physical_cores']
            self.assertEqual(result['affinity'],self.doc['slots'][slot])
        self.assertEqual(len(set(used)),16)

    def test_smt_and_cross_slot_physical_collisions_reject(self):
        doc=copy.deepcopy(self.doc);doc['slots']['a']=[100,101,106,109]
        with self.assertRaisesRegex(ValueError,'SMT siblings'):self.check(doc)
        doc=copy.deepcopy(self.doc);doc['slots']['b'][0]=101
        with self.assertRaisesRegex(ValueError,'overlap across slots'):self.check(doc)

    def test_wrong_live_topology_affinity_host_or_timestamp_reject(self):
        with self.assertRaisesRegex(ValueError,'affinity'):self.check(affinity=[100,103,106,110])
        with self.assertRaisesRegex(ValueError,'hostname'):self.check(hostname='elsewhere')
        with self.assertRaisesRegex(ValueError,'stale'):self.check(now=self.now+timedelta(days=2))
        with self.assertRaisesRegex(ValueError,'future'):self.check(now=self.now-timedelta(seconds=1))
        live=copy.deepcopy(self.rows);live[0]['core_id']=900
        with self.assertRaisesRegex(ValueError,'live topology'):self.check(live=live)

    def test_slot_shape_and_cpu_types_reject(self):
        for slot_value in ([100,103,106], [True,103,106,109], [999,103,106,109]):
            doc=copy.deepcopy(self.doc);doc['slots']['a']=slot_value
            with self.assertRaises(ValueError):self.check(doc)

    def test_quota_memory_and_parent_limits(self):
        fit.validate_limits('400000 100000',str(fit.MEMORY),[('max 100000','max')])
        fit.validate_limits('40000 10000',str(fit.MEMORY))
        for cpu,mem,parent in [('max 100000',str(fit.MEMORY),()),
                               ('800000 100000',str(fit.MEMORY),()),
                               ('400000 100000','max',()),
                               ('400000 100000',str(fit.MEMORY),[('200000 100000','max')]),
                               ('400000 100000',str(fit.MEMORY),[('max 100000','1024')])]:
            with self.assertRaises(ValueError):fit.validate_limits(cpu,mem,parent)

    def test_online_cpu_parser(self):
        self.assertEqual(fit.parse_cpus('0-3,8,11-12\n'),[0,1,2,3,8,11,12])
        for text in ('3-1','0-2,2','0,x'):
            with self.assertRaises(ValueError):fit.parse_cpus(text)

    def test_mixed_v3_launcher_compatibility_uses_legacy_slot_locks(self):
        doc=dict(cpus=[dict(cpu=c,package_id=0,core_id=c%16) for c in range(32)])
        self.assertEqual(fit.slot_locks(doc,'c',[(0,0),(0,1),(0,2),(0,3)]),['a','c'])
        self.assertEqual(fit.slot_locks(doc,'d',[(0,4),(0,5),(0,6),(0,7)]),['b','d'])
        self.assertEqual(fit.slot_locks(doc,'c',[(0,8),(0,9),(0,10),(0,11)]),['c'])
        self.assertEqual(fit.slot_locks(doc,'c',[(0,0),(0,4),(0,8),(0,9)]),['a','b','c'])


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.project=self.root/'probe'
        prepare(self.project,'ntt27_prefetch16',aw=16,processors=4)
        patcher=patch.object(fit.subprocess,'run',side_effect=AssertionError('NO SUBPROCESS IN POLICY TEST'))
        patcher.start();self.addCleanup(patcher.stop)

    def test_existing_prepare_contract_and_source_provenance(self):
        context=fit.verify_project(self.project)
        self.assertTrue(context['source_sha256'])
        self.assertEqual(len(context['manifest_sha256']),64)
        self.assertEqual(context['qsf_parameters']['LANES'],16)
        self.assertEqual(context['qsf_parameters']['AW'],16)

    def test_stale_missing_or_extra_source_rejected(self):
        rtl=self.project/'rtl';source=next(rtl.iterdir());source.write_text('changed')
        with self.assertRaisesRegex(ValueError,'source SHA mismatch'):fit.verify_project(self.project)

    def test_extra_source_rejected(self):
        (self.project/'rtl/unlisted.sv').write_text('// extra')
        with self.assertRaisesRegex(ValueError,'closure mismatch'):fit.verify_project(self.project)

    def test_existing_execution_and_logs_rejected(self):
        for name in ('execution-context.json','execution-result.json','output_files','db','incremental_db'):
            with self.subTest(name=name):
                path=self.project/name;path.write_text('existing')
                with self.assertRaisesRegex(ValueError,'existing execution'):fit.verify_project(self.project)
                path.rename(self.root/(name+'-retained'))
        (self.root/'probe-fit.log').write_text('old log')
        with self.assertRaisesRegex(ValueError,'existing log'):fit.verify_project(self.project)

    def test_qsf_source_top_workers_and_parameters_checked(self):
        qsf=self.project/'probe.qsf';original=qsf.read_text()
        changes=[('NUM_PARALLEL_PROCESSORS 4','NUM_PARALLEL_PROCESSORS 8'),
                 ('TOP_LEVEL_ENTITY genefer_ntt_banked27_prefetch_engine','TOP_LEVEL_ENTITY different'),
                 ('set_parameter -name AW 16','set_parameter -name AW 10'),
                 ('set_parameter -name LANES 16','set_parameter -name LANES 64'),
                 ('SDC_FILE probe.sdc','SDC_FILE elsewhere.sdc')]
        for old,new in changes:
            with self.subTest(old=old):
                self.assertIn(old,original);qsf.write_text(original.replace(old,new))
                with self.assertRaises(ValueError):fit.verify_project(self.project)
        qsf.write_text(original+'set_global_assignment -name SYSTEMVERILOG_FILE rtl/other.sv\n')
        with self.assertRaisesRegex(ValueError,'source closure'):fit.verify_project(self.project)

    def test_wrong_manifest_worker_count_and_bitstream_policy_refused(self):
        path=self.project/'manifest.json';original=json.loads(path.read_text())
        for key,value in (('compile_processors',True),('compile_processors',8),('bitstream_generation',True)):
            manifest={**original,key:value};path.write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):fit.verify_project(self.project)

    def test_held_core_or_slot_lock_refuses_second_owner(self):
        path=self.root/'test.lock'
        with fit.locked(path):
            with self.assertRaises(BlockingIOError):
                with fit.locked(path):pass

    def test_core_and_carry_preparation_contracts_accept(self):
        for target in ('square_core27_stream_ntt64_carry16','carry_stream_precision4','ntt27_prefetch64'):
            project=self.root/target;prepare(project,target,aw=16,processors=4)
            self.assertTrue(fit.verify_project(project)['source_sha256'])

    def test_live_cgroup_read_checks_current_and_ancestor_limits(self):
        root=self.root/'cgroups';scope=root/'parent/fit.scope';scope.mkdir(parents=True)
        proc=self.root/'cgroup';proc.write_text('0::/parent/fit.scope\n')
        for path,cpu,memory in ((scope,'400000 100000',str(fit.MEMORY)),
                                (scope.parent,'max 100000','max')):
            (path/'cpu.max').write_text(cpu);(path/'memory.max').write_text(memory)
        limits=fit.live_limits(proc,root)
        self.assertEqual(limits['memory_max'],str(fit.MEMORY))
        (scope.parent/'cpu.max').write_text('200000 100000')
        with self.assertRaisesRegex(ValueError,'ancestor CPU'):fit.live_limits(proc,root)


if __name__=='__main__':unittest.main()
