"""Own actual R15 long metadata/public preflight; no native/model execution."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import types
import unittest
from unittest.mock import patch

from fpga.tools import native_long_class_v2 as runtime
from fpga.tools import native_long_package_v3 as package,native_long_stage_v3 as stage
from fpga.tools import native_class_package_v4 as ordinary

ROOT=Path(__file__).resolve().parents[1]
ROLE=ROOT/'results/throughput-20260929/trackS-r15-compute-ownlong-v1/continuous1000-measured-v1'
EVIDENCE=ROOT/'queue/evidence/s4-p16-c2-r15-compute-own100-serial-q1-v1'


class R15ComputeLongTests(unittest.TestCase):
    def paths(self):
        native=EVIDENCE/'attempt-0/collected/output/native'
        return dict(forecast=ROLE/'forecast.json',pilot_manifest=native/'approved-manifest.json',
                    pilot_report=native/'report.json',pilot_gate=EVIDENCE/'gate-receipt.json')

    def fixture(self):
        paths=self.paths()
        return (json.loads((ROLE/'manifest.json').read_text()),
                {k:json.loads(p.read_text()) for k,p in paths.items()},
                {k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in paths.items()})

    def prepare(self,out):
        bound=package.bind_role(ROLE/'manifest.json',ROLE/'source/fpga',self.paths(),out/'bound',host='gfn16-azure-f16')
        role=json.loads(Path(bound['manifest']).read_text())
        # Reuse actual authenticated cached provider data; no provider capture,
        # finance admission, queue mutation or native execution occurs here.
        inputs=json.loads((ROOT/'queue/provider-cost-status/azure.json').read_text())['provider_inputs']
        provider=out/'provider.json';provider.write_text(json.dumps(inputs))
        budget=ordinary.accounting_meter().make_budget('gfn16-azure-f16',10815,
            str(provider.relative_to(ROOT)),hashlib.sha256(provider.read_bytes()).hexdigest(),
            package.source_identity(role),package.FIT_PROFILE_SHA)
        budgetpath=out/'budget.json';budgetpath.write_text(json.dumps(budget))
        prepared=package.prepare(Path(bound['manifest']),Path(bound['source_root']),runtime.FIT_PROFILE,
            'r15-own-long-metadata-only','run',out/'packet',budgetpath)
        return bound,prepared,budget

    def test_actual_own_assessment_allocation_and_calendar(self):
        m,v,p=self.fixture();admission=runtime.assess(m,v,p,'gfn16-azure-f16')
        self.assertAlmostEqual(admission['model_seconds_estimate'],4306.570927417511)
        self.assertAlmostEqual(admission['overall_seconds_estimate'],5277.535427194008)
        self.assertFalse(admission['promotion_allowed']);self.assertFalse(admission['host_gl_implemented'])
        self.assertEqual(admission['shape']['outer_seconds'],10800)
        self.assertEqual(m['build']['parameters'],runtime.C2_FAMILIES[runtime.C2_R15_HELPER]['parameters'])
        for model,count in ((m,1000),(v['pilot_manifest'],100)):
            group=model['r15_compute']
            self.assertEqual(runtime.c2_frame_calendar(group['geometry'],count,8461,1,1,0,0,1),
                             group['own_long']['own_calendar'])
        warm=[first+999*8461+12559 for first in (204,4434)]
        self.assertEqual(runtime.c2_publication_edges(warm,1),([9124767,9784231],9849767))

    def test_scalar_only_header_prefix_and_no_candidate_import(self):
        m,v,p=self.fixture();family=runtime.C2_FAMILIES[runtime.C2_R15_HELPER]
        scalar=runtime.c2_scalar_functions(family)
        pilot=EVIDENCE/'attempt-0/collected/output/native'
        pilot_source=Path(v['pilot_manifest']['source_root'])
        # Collected source bytes are already saved in the exact selected local
        # package; the pilot manifest's worker path is provenance, not a local path.
        selected=ROOT/'results/throughput-20260929/trackS-r15-compute-ownlong-v1'
        original=selected/'own100-source-v1/source/fpga'/runtime.C2_HEADER
        self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(),family['header_delta']['pilot_sha256'])
        self.assertEqual(scalar['header'](original.read_bytes()),(ROLE/'source/fpga'/runtime.C2_HEADER).read_bytes())
        self.assertEqual([row[:100] for row in scalar['bits']()],scalar['bits'](100))
        load=runtime.importlib.util.spec_from_file_location
        def framework_only(name,path,*args,**kwargs):
            self.assertNotIn('/reference/',str(path));return load(name,path,*args,**kwargs)
        with patch.object(runtime.importlib.util,'spec_from_file_location',side_effect=framework_only):
            runtime.assess(m,v,p,'gfn16-azure-f16')

    def test_source_time_thread_scope_and_geometry_substitutions_refuse(self):
        m,v,p=self.fixture()
        changes=[('m',('build','parameters','LEAN_BUILD'),0),
            ('m',('sources',runtime.C2_R15_CPP),'0'*64),
            ('m',('r15_compute','geometry','correction_cache_latency'),79),
            ('m',('r15_compute','own_long','forecast_inherited'),True),
            ('m',('r15_compute','own_long','no_midchain_reset_reload'),False),
            ('m',('r15_compute','own_long','own_calendar','frames'),200),
            ('m',('steps',0,'validator','config','count'),100),
            ('v',('pilot_report','host'),'gfn16-pilot-c4d'),
            ('v',('pilot_report','limits','affinity'),[14,15]),
            ('v',('pilot_report','limits','memory_max_bytes'),16<<30),
            ('v',('pilot_report','model_threads'),8),
            ('v',('forecast','forecast','continuous_command_seconds_estimate'),1),
            ('p',('pilot_report',),'0'*64)]
        for target,keys,bad in changes:
            mm,vv,pp=copy.deepcopy((m,v,p));value=dict(m=mm,v=vv,p=pp)[target]
            for key in keys[:-1]:value=value[key]
            value[keys[-1]]=bad
            with self.subTest(keys=keys),self.assertRaises((ValueError,KeyError)):
                runtime.assess(mm,vv,pp,'gfn16-azure-f16')

    def test_real_bind_prepare_safe_stage_and_unchanged_donor(self):
        before=(ROLE/'manifest.json').read_bytes()
        with tempfile.TemporaryDirectory(prefix='r15-own-long-',dir=ROOT/'artifacts') as temporary:
            out=Path(temporary).resolve();bound,prepared,budget=self.prepare(out)
            payload,ticket,m,selected=stage.worker().inspect_archive(out/'packet/package.tar.gz',prepared['archive_sha256'],prepared['ticket_sha256'])
            self.assertEqual(ticket['max_seconds'],10800);self.assertEqual(selected['cpus'],[12,13])
            self.assertEqual((selected['static_lanes'],selected['scratch_floor_bytes'],selected['memory_bytes']),(1,20<<30,8<<30))
            self.assertEqual(ticket['runtime_duration'],runtime.duration.SHAPE)
            self.assertEqual(m['build'],json.loads(before)['build']);self.assertEqual(m['steps'],json.loads(before)['steps'])
            runtime.duration.validate(m,out/'packet/capture/source/fpga','gfn16-azure-f16')
            from fpga.tools import native_profile_variants_v14 as checker
            fingerprint=checker.functional_fingerprint(m,ticket['budget'],out/'packet/capture/source/fpga')
            self.assertEqual(len(fingerprint['sha256']),64)
            self.assertFalse(fingerprint['fresh_budget_admission_conferred'])
            self.assertNotIn(runtime.C2_R15_HELPER,fingerprint['ignored_exact_controls'])
            wrong=copy.deepcopy(budget);wrong['checker_sha256']='9c3d902e3da0969145c4148f06a51ec9ca22a322513068074f7b338cb8ddf137'
            with self.assertRaises(ValueError):package.azure_binding(wrong,'gfn16-azure-f16')
            with self.assertRaises(ValueError):stage.worker().profile_from_payload(payload,dict(ticket,profile='azure-f16-static1415-v1'),m['sources'])
        self.assertEqual((ROLE/'manifest.json').read_bytes(),before)

    def test_real_public_run_source_caps_and_long_route_before_any_command(self):
        with tempfile.TemporaryDirectory(prefix='r15-public-long-',dir=ROOT/'artifacts') as temporary:
            out=Path(temporary).resolve();_,_,budget=self.prepare(out)
            base=out/'worker';root=base/'jobs/r15-own-long-metadata-only';shutil.copytree(out/'packet',root)
            source=root/'capture/source/fpga';path=source/'tools/native_long_package_v3.py'
            spec=importlib.util.spec_from_file_location('_actual_r15_closed_long',path)
            closed=importlib.util.module_from_spec(spec);spec.loader.exec_module(closed)
            worker=closed.worker(budget,1);load=worker.load;shared=load('native_long_class_v2.py')
            selected=shared.profile(runtime.FIT_PROFILE);selected['base']=str(base)
            manifest=json.loads((root/'manifest.json').read_text());manifest['source_root']=str(source)
            (root/'manifest.json').write_text(json.dumps(manifest));ticket=json.loads((root/'ticket.json').read_text())
            ticket.update(native_root=str(root),manifest_sha256=hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest())
            ticket['build_key']=load('build_identity_v1.py').build_identity(manifest,selected)['build_key']
            ticket['run_key']=hashlib.sha256(load('native_test_queue_v1.py').canonical(dict(
                build_key=ticket['build_key'],steps=manifest['steps'],probe=manifest['probe'],
                phase=ticket['phase'],id=ticket['id']))).hexdigest()
            (root/'ticket.json').write_text(json.dumps(ticket));pin=hashlib.sha256((root/'ticket.json').read_bytes()).hexdigest()
            (base/'claims').mkdir();claims=[];queue=load('native_test_queue_v1.py')
            worker.load=lambda name:shared if name=='native_long_class_v2.py' else queue if name=='native_test_queue_v1.py' else load(name)
            static=shared.fit.policy.host.static_module();kernel=out/'kernel'
            actual_v2=shared.fit.policy.host.v2()
            def observed(name,value):
                path=kernel/name.lstrip('/');path.parent.mkdir(parents=True,exist_ok=True);path.write_text(str(value))
            for cpu,pair in selected['topology'].items():
                for key,val in zip(('physical_package_id','core_id'),pair):observed('/sys/devices/system/cpu/cpu'+cpu+'/topology/'+key,val)
            observed('/proc/self/cgroup','0::/job');observed('/proc/meminfo','MemAvailable: 100000000 kB\n')
            for name,val in (('memory.max',str(8<<30)),('memory.swap.max','0'),('cpu.max','200000 100000')):observed('/sys/fs/cgroup/job/'+name,val)
            class KernelPath(type(Path())):
                def read_text(self,*args,**kwargs):return (kernel/str(self).lstrip('/')).read_text(*args,**kwargs)
            limits=types.FunctionType(static.execution_limits.__code__,dict(static.execution_limits.__globals__,
                Path=KernelPath,socket=types.SimpleNamespace(gethostname=lambda:'gfn16-azure-f16'),
                os=types.SimpleNamespace(geteuid=lambda:1000,sched_getaffinity=lambda _:set([12,13])),
                pwd=types.SimpleNamespace(getpwuid=lambda _:types.SimpleNamespace(pw_name=selected['user']))))
            def safe_outer(parent_factory,pins,path,digest,out):
                parent=parent_factory(runtime.FIT_PROFILE)
                self.assertIs(parent.execute.__globals__,parent.__dict__)
                self.assertIn(10450,parent.execute.__code__.co_consts);self.assertIn(10700,parent.execute.__code__.co_consts)
                self.assertEqual(parent.PROFILES['gfn16-azure-f16']['static_lanes'],1)
                raise RuntimeError('actual own FIT long route reached before model')
            cwd=Path.cwd()
            try:
                os.chdir(source)
                with patch.object(shared,'profile',return_value=selected),\
                     patch.object(actual_v2,'execution_limits',side_effect=limits),\
                     patch.object(shared.fit.policy.host,'v2',return_value=actual_v2),\
                     patch.object(shared.fit.policy.host,'execute_with_parent',side_effect=safe_outer),\
                     patch.object(queue,'claim',side_effect=lambda *args:claims.append(args)):
                    with self.assertRaisesRegex(RuntimeError,'own FIT long route'):worker.run(root/'ticket.json',pin)
                    self.assertEqual(len(claims),1)
                    observed('/sys/fs/cgroup/job/cpu.max','100000 100000')
                    with self.assertRaisesRegex(ValueError,'two-core CPU caps'):worker.run(root/'ticket.json',pin)
                    self.assertEqual(len(claims),1)
            finally:os.chdir(cwd)

    def test_long_drain_and_actual_historical_capture_are_preserved(self):
        selected=runtime.profile(runtime.FIT_PROFILE);parent=runtime.parent(runtime.FIT_PROFILE)
        with patch.object(runtime.fit.policy.host.time,'time',return_value=selected['protected_deadline_drain_epoch']-10814):
            with self.assertRaisesRegex(ValueError,'full own AzureFIT10815'):parent.guard_protected(selected)
        from fpga.tools import native_profile_variants_v14 as checker
        packet=ROOT/'results/throughput-20260929/trackS-r14-host-offload-ownlong-v1/continuous1000-packet-v1/packet-01'
        m=json.loads((packet/'manifest.json').read_text());t=json.loads((packet/'ticket.json').read_text())
        family=tuple(m['sources'][name] for name in ('tools/native_long_class_v2.py','tools/native_long_package_v3.py'))
        self.assertIn(family,checker.LONG_FAMILIES)
        before=hashlib.sha256((packet/'package.tar.gz').read_bytes()).hexdigest()
        self.assertEqual(len(checker.functional_fingerprint(m,t['budget'],packet/'capture/source/fpga')['sha256']),64)
        self.assertEqual(hashlib.sha256((packet/'package.tar.gz').read_bytes()).hexdigest(),before)


if __name__=='__main__':unittest.main()
