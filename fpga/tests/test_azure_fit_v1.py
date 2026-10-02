import copy
from datetime import datetime,timedelta,timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from fpga.cloud import azure_fit_v1 as p


class AzurePolicyTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,1,5,tzinfo=timezone.utc)
        self.rows=[dict(cpu=i,package_id=0,core_id=i) for i in range(16)]
        self.doc=dict(schema='azure-fit-topology-v1',profile=p.PROFILE,hostname=p.HOST,
                      observed_at=self.now.isoformat(),cpus=self.rows,slots=copy.deepcopy(p.SLOTS),
                      memory_total_bytes=135066714112)

    def validate(self,doc=None,rows=None,slot='a',affinity=None):
        return p.validate_topology(doc or self.doc,slot,affinity or p.SLOTS[slot],
                                   rows or self.rows,p.HOST,self.now)

    def test_four_disjoint_physical_slots(self):
        used=[]
        for slot in 'abcd':
            result=self.validate(slot=slot);used+=result['physical_cores']
            self.assertEqual(len(result['affinity']),4)
        self.assertEqual(len(set(used)),16)
        rows=[dict(cpu=i,package_id=i%2,core_id=i+100) for i in range(16)]
        doc=copy.deepcopy(self.doc);doc['cpus']=rows
        self.assertEqual(self.validate(doc,rows)['physical_cores'][0],(0,100))

    def test_topology_refuses_smt_drift_stale_and_wrong_slot(self):
        for change in (lambda d:d['cpus'][15].update(core_id=0),
                       lambda d:d.update(profile='aws'),lambda d:d.update(memory_total_bytes=119<<30),
                       lambda d:d['slots']['b'].__setitem__(0,3),
                       lambda d:d.update(observed_at=(self.now-timedelta(days=2)).isoformat())):
            doc=copy.deepcopy(self.doc);change(doc)
            with self.assertRaises(ValueError):self.validate(doc,doc['cpus'])
        with self.assertRaises(ValueError):self.validate(affinity=[0,2,4,6])
        rows=copy.deepcopy(self.rows);rows[0]['core_id']=99
        with self.assertRaises(ValueError):self.validate(rows=rows)

    def test_exact_resources_and_ancestors(self):
        p.runner.validate_limits('400000 100000',str(24<<30))
        for cpu,mem in [('max 100000',24<<30),('600000 100000',24<<30),('400000 100000',20<<30)]:
            with self.assertRaises(ValueError):p.runner.validate_limits(cpu,str(mem))
        with self.assertRaises(ValueError):p.runner.validate_limits('400000 100000',str(24<<30),[('200000 100000','max')])
        with tempfile.TemporaryDirectory() as folder:
            where=Path(folder);(where/'memory.swap.max').write_text('0\n')
            with patch.object(p,'parent_limits',return_value={'cgroup_path':folder}):
                self.assertEqual(p.live_limits()['memory_swap_max_bytes'],0)
                (where/'memory.swap.max').write_text('max\n')
                with self.assertRaises(ValueError):p.live_limits()

    def test_fresh_credit_conservative_not_hardcap(self):
        credit=dict(provider='Microsoft.Consumption/credits/balanceSummary',currency='USD',
                    observed_at=self.now.isoformat(),current_balance=200,pending_eligible_charges=0)
        self.assertEqual(p.credit_guard(credit,self.now)['conservative_remaining_usd'],200)
        for key,value in [('current_balance',29),('current_balance',float('nan')),('pending_eligible_charges',float('inf')),
                          ('observed_at',(self.now-timedelta(days=2)).isoformat()),('currency','EUR')]:
            bad={**credit,key:value}
            with self.assertRaises(ValueError):p.credit_guard(bad,self.now)

    def test_protected_deadline_no_extend_and_no_job_overrun(self):
        with tempfile.TemporaryDirectory() as folder:
            guard=Path(folder).resolve()/'deadline';guard.write_text('1791189913\n')
            with patch.object(p,'PROTECTED',{str(guard):p.sha(guard)}),patch.object(p.subprocess,'run') as call:
                call.side_effect=[type('R',(),{'returncode':0,'stdout':'active'})(),type('R',(),{'returncode':0,'stdout':'enabled'})()]
                self.assertEqual(p.deadline_guard(self.now)['epoch'],1791189913)
                late=datetime.fromtimestamp(p.DEADLINE-p.TIMEOUT,timezone.utc)
                with self.assertRaises(ValueError):p.deadline_guard(late)
                guard.write_text('1799999999\n')
                with self.assertRaises(ValueError):p.deadline_guard(self.now)

    def test_pinned_parent_and_native_timeout_preserved(self):
        raw=Path(p.__file__).with_name('aws_fit_v6.py').read_bytes();source=p.adapted_source(raw)
        for token in ('os.O_NOFOLLOW','--kill-after=60s','str(TIMEOUT)',"'.fit-physical-p{package}-c{core}.lock'",
                      'topology file changed','existing execution refused',str(p.QUARTUS)):
            self.assertIn(token,source)
        with self.assertRaises(ValueError):p.adapted_source(raw+b'\n')

    def test_exact_project_closure_sources_parameters(self):
        original=Path(__file__).parents[1]/'results/throughput-20260929/crt27-mont-hostbench-stage-v1/project'
        with tempfile.TemporaryDirectory() as folder:
            project=Path(folder).resolve()/'project';shutil.copytree(original,project)
            context=p.verify_project(project);self.assertEqual(context['manifest_sha256'],p.BENCHMARK_SHA)
            (project/'extra').write_text('x')
            with self.assertRaises(ValueError):p.verify_project(project)
            (project/'extra').unlink();(project/'rtl/extra.sv').write_text('x')
            with self.assertRaises(ValueError):p.verify_project(project)
            (project/'rtl/extra.sv').unlink()
            qsf=project/'probe.qsf';qsf.write_text(qsf.read_text().replace('NUM_PARALLEL_PROCESSORS 4','NUM_PARALLEL_PROCESSORS 6'))
            with self.assertRaises(ValueError):p.verify_project(project)

    def test_missing_and_extra_input_final_drift_is_recordable(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();project=root/'p';(project/'rtl').mkdir(parents=True)
            source=project/'rtl/a.sv';source.write_text('module a; endmodule\n')
            context=dict(source_sha256={'a.sv':p.sha(source)},control_sha256={})
            approval=root/'approval';approval.write_text('{}')
            approved=dict(tool_sha256={},helper_sha256={})
            with patch.object(p,'ROOT',root),patch.object(p,'PROTECTED',{}):
                self.assertEqual(p.final_changes(project,context,approved,approval,p.sha(approval)),[])
                source.unlink()
                self.assertIn('rtl/a.sv',p.final_changes(project,context,approved,approval,p.sha(approval)))
                (project/'rtl/extra.sv').write_text('x')
                self.assertIn('RTL closure',p.final_changes(project,context,approved,approval,p.sha(approval)))

    def test_hardlinked_and_symlink_inputs_refused(self):
        import os
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder).resolve()/'source';path.write_text('x')
            alias=Path(folder).resolve()/'alias';os.link(path,alias)
            with self.assertRaises(ValueError):p.read_regular(path)
            alias.unlink();alias.symlink_to(path)
            with self.assertRaises(ValueError):p.read_regular(alias)

    def test_exact_approval_tools_helpers_activation_and_first_benchmark(self):
        context={'manifest_sha256':p.BENCHMARK_SHA}
        paths=[p.QUARTUS,p.QUARTUS.parent.parent/'linux64/quartus_sh',p.QUARTUS.parent.parent/'linux64/quartus_syn',
               p.QUARTUS.parent.parent/'linux64/quartus_fit',p.QUARTUS.parent.parent/'linux64/quartus_sta',
               Path('/usr/bin/python3'),Path('/usr/bin/time'),Path('/usr/bin/timeout')]
        tools={str(path):'1'*64 for path in paths}
        helpers={'azure_fit_v1.py':'2'*64,'aws_fit_v6.py':p.PARENT_SHA,'run-azure-fit-v1.sh':'3'*64,'summarize.py':p.SUMMARY_SHA}
        approval=dict(profile=p.PROFILE,hostname=p.HOST,status='prepared_not_executed',normal_fresh_activation_confirmed=True,
                      project=context,topology_sha256='4'*64,mode='matched_crt_first',tool_sha256=tools,helper_sha256=helpers)
        expected={**tools,**{str(p.ROOT/n):s for n,s in helpers.items()},'/tmp/topology':'4'*64}
        def check(doc,drift=None):
            raw=json.dumps(doc).encode();pin=hashlib.sha256(raw).hexdigest()
            with patch.object(p,'read_regular',return_value=raw),patch.object(p,'verify_project',return_value=context),\
                 patch.object(p,'sha',side_effect=lambda path:('f'*64 if str(path)==drift else expected[str(path)])),\
                 patch.object(p,'__file__',str(p.ROOT/'azure_fit_v1.py')),patch.object(Path,'resolve',lambda self:self):
                return p.verify_approval(Path('/tmp/approval'),pin,p.ROOT/'project',Path('/tmp/topology'))
        self.assertEqual(check(approval)[1],context)
        for key,value in [('normal_fresh_activation_confirmed',False),('hostname','aws'),('mode','any')]:
            with self.assertRaises(ValueError):check({**approval,key:value})
        with self.assertRaises(ValueError):check(approval,str(p.QUARTUS))
        with self.assertRaises(ValueError):check(approval,str(p.ROOT/'azure_fit_v1.py'))
        bad=copy.deepcopy(approval);bad['tool_sha256'].pop('/usr/bin/time')
        with self.assertRaises(ValueError):check(bad)
        context['manifest_sha256']='f'*64
        with self.assertRaises(ValueError):check(approval)


if __name__=='__main__':unittest.main()
