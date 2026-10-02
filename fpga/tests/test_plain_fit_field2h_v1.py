"""Field-only actual timeout/outer-cgroup regressions; no native commands."""
from copy import deepcopy
from contextlib import ExitStack
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

FPGA=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('field2h_runner',FPGA/'cloud/plain_fit_field2h_v1.py')
q=importlib.util.module_from_spec(spec); spec.loader.exec_module(q)


class FieldRunnerTests(unittest.TestCase):
    def request(self):
        return dict(schema='plain-fit-request-v1',scope='component_probe',mode='full',exemption='component_sizing_probe',runtime_contract=deepcopy(q.CONTRACT))

    def test_whole_seed_continuation_or_unknown_contract_never_launches(self):
        for mutate in (lambda r:r.update(scope='whole_core'),lambda r:r.update(exemption='constraint_seed_only'),
          lambda r:r.update(mode='saved_syn'),lambda r:r.update(structural_spec={}),lambda r:r.pop('runtime_contract'),
          lambda r:r['runtime_contract'].update(native_timeout_seconds=21600),lambda r:r['runtime_contract'].update(outer_runtime_seconds=7200.0)):
            value=self.request(); mutate(value)
            with self.subTest(request=value),tempfile.TemporaryDirectory() as directory:
                path=Path(directory).resolve()/'request.json'; path.write_text(json.dumps(value))
                with patch.object(q._parent,'launch') as launch,self.assertRaises(ValueError): q.launch(path,q._parent.sha(path))
                launch.assert_not_called()

    def test_frozen_parent_exact_runtime_anchors_and_budget_horizon(self):
        transformed=q.source()
        self.assertEqual(q._parent.sha(FPGA/'cloud/plain_fit_v2.py'),q.FIELD_PARENT_SHA)
        for value in ('m.TIMEOUT=7200',"RuntimeMaxUSec='2h'",'timestamp()+7260<',"'gfn16-azure-f16',7260,source_sha256=","meter.admit('aws-m8azn',7260)"):
            self.assertIn(value,transformed)
        self.assertNotIn('m.TIMEOUT=21600',transformed)
        self.assertEqual(q.HOSTS,q.parent().HOSTS); self.assertEqual(q.CONTRACT['host_hours_horizon_seconds'],7260)

    def test_parent_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve(); (root/'plain_fit_v2.py').write_text('drift')
            with patch.object(q,'HERE',root),self.assertRaisesRegex(ValueError,'SHA drift'): q.source()

    def test_exact_two_hour_outer_unit_properties_only(self):
        props='RuntimeMaxUSec=2h\nTimeoutStopUSec=1min\nKillMode=control-group\n'
        with patch.object(q.subprocess,'check_output',return_value=props): self.assertEqual(q.runtime_properties('gfn16-field.service')['RuntimeMaxUSec'],'2h')
        for bad in (props.replace('2h','6h 2min'),props.replace('1min','5min'),props.replace('control-group','process')):
            with patch.object(q.subprocess,'check_output',return_value=bad),self.assertRaises(ValueError): q.runtime_properties('gfn16-field.service')

    def test_live_cgroup_records_two_hour_metadata_and_effective_cpuset(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve(); config=dict(q.HOSTS['gfn16-azure-f16'],root=str(root))
            policy=q.runner(config,'gfn16-azure-f16',False,'gfn16-field.service')
            base='/sys/fs/cgroup/system.slice/gfn16-field.service'
            files={'/proc/self/cgroup':'0::/system.slice/gfn16-field.service\n',base+'/cpu.max':'400000 100000',
              base+'/memory.max':str(24<<30),base+'/memory.swap.max':'0',base+'/cpuset.cpus.effective':'8-11',
              '/sys/fs/cgroup/system.slice/cpu.max':'max 100000','/sys/fs/cgroup/system.slice/memory.max':'max'}
            with patch.object(Path,'read_text',lambda path:files[str(path)]),patch.object(q.subprocess,'check_output',return_value='RuntimeMaxUSec=2h\nTimeoutStopUSec=1min\nKillMode=control-group\n'),patch.object(q.os,'sched_getaffinity',return_value={8,9,10,11},create=True):
                value=policy.live_limits(); self.assertEqual(value['outer_runtime_max_seconds'],7200); self.assertEqual(value['outer_timeout_stop_seconds'],60)
                self.assertEqual(value['allowed_cpus'],[8,9,10,11]); self.assertEqual(value['runtime_kind'],'field-fit-two-hour-v1')
                files[base+'/cpuset.cpus.effective']='0-15'
                with self.assertRaisesRegex(ValueError,'confinement'): policy.live_limits()

    def test_native_argv_and_context_have_actual_two_hour_timeout_on_both_hosts(self):
        for host,slot in (('gfn16-aws-m8i','b'),('gfn16-azure-f16','c')):
            with self.subTest(host=host),tempfile.TemporaryDirectory() as directory:
                root=Path(directory).resolve(); (root/'run-aws-fit-v6.sh').write_text('# context descriptor only\n')
                config=dict(q.HOSTS[host],root=str(root)); policy=q.runner(config,host,False,'gfn16-field.service')
                project=root/'probe'; project.mkdir(); (project/'run.tcl').write_text(q.FULL_TCL)
                topology=root/'topology.json'; topology.write_text('{}')
                cpus=config['slots'][slot]; selected=dict(affinity=cpus,physical_cores=[(0,c) for c in cpus],topology={str(c):[0,c] for c in cpus})
                policy.verify_project=lambda p:dict(manifest_sha256='a'*64,source_sha256={},control_sha256={})
                policy.live_limits=lambda:dict(cgroup_path='/synthetic',cpu_max=str(config['workers']*100000)+' 100000',memory_max=str(config['memory']),swap_max='0',outer_runtime_max_seconds=7200,outer_timeout_stop_seconds=60,runtime_kind=q.CONTRACT['kind'],allowed_cpus=cpus)
                policy.live_topology=lambda:[]; policy.validate_topology=lambda *a:selected
                calls=[]
                def native(argv,**kwargs): calls.append(argv); return SimpleNamespace(returncode=0)
                with ExitStack() as patches:
                    patches.enter_context(patch.object(Path,'cwd',return_value=root)); patches.enter_context(patch.object(q.os,'sched_getaffinity',return_value=set(cpus),create=True))
                    patches.enter_context(patch.object(policy.socket,'gethostname',return_value=host)); patches.enter_context(patch.object(policy.subprocess,'run',side_effect=native))
                    self.assertEqual(policy.launch('probe',slot,topology),0)
                context=json.loads((project/'execution-context.json').read_text())
                self.assertEqual(context['timeout_seconds'],7200); self.assertEqual(context['outer_runtime_max_seconds'],7200)
                self.assertEqual(context['quartus_workers'],config['workers']); self.assertEqual(context['memory_max'],str(config['memory']))
                self.assertEqual(calls[0][:5],['/usr/bin/time','-v','/usr/bin/timeout','--kill-after=60s','7200'])
                self.assertEqual(calls[0][5],str(root/'altera_pro/26.1/quartus/bin/quartus_sh'))


if __name__=='__main__': unittest.main()
