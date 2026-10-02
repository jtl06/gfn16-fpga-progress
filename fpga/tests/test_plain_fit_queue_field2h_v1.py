"""Field-only2h budget/service and old6h adoption/uncertainty regressions."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

FPGA=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
q=load('field2h_queue',FPGA/'tools/plain_fit_queue_field2h_v1.py')
fixtures=load('field2h_old_queue_fixtures',FPGA/'tests/test_plain_fit_queue_v1.py')
q3fixtures=load('field2h_nullable_fixtures',FPGA/'tests/test_plain_fit_queue_v3.py')
NOW=datetime(2026,10,1,11,tzinfo=timezone.utc); F16='gfn16-azure-f16'; AWS='gfn16-aws-m8i'; INV='a'*32


def job(host=F16):
    value=fixtures.job('field',host); value['allowed_slots']={host:['d' if host==F16 else 'b']}; return value


class FieldQueueTests(unittest.TestCase):
    def test_frozen_predecessor_and_resource_policy_unchanged(self):
        self.assertEqual(q.digest((FPGA/'tools/plain_fit_queue_v3.py').read_bytes()),q.FIELD_PARENT_SHA)
        self.assertEqual(q.digest((FPGA/'cloud/plain_fit_v2.py').read_bytes()),q.PINS['cloud/plain_fit_v2.py'])
        predecessor=load('field_frozen3',FPGA/'tools/plain_fit_queue_v3.py')
        self.assertEqual(q.HOSTS,predecessor.HOSTS); self.assertEqual(q.SSH,predecessor.SSH); self.assertEqual(q.END,predecessor.END)
        self.assertEqual((q.RUNTIME,q.GRACE,q.HORIZON),(7200,60,7260))

    def test_noncomponent_seed_or_changed_rtl_new_jobs_rejected(self):
        for change in ('whole','seed','structure'):
            value=job()
            if change=='whole': value['scope']='whole_core'
            elif change=='seed': value['variants'][F16]['exemption']='constraint_seed_only'
            else: value['variants'][F16].pop('exemption'); value['variants'][F16]['structural_spec']={}
            with self.subTest(change=change),self.assertRaises(ValueError): q.validate_queue(fixtures.queue([value]))
        q.validate_queue(fixtures.queue([job()]))

    def test_whole_request_cannot_bypass_direct_prepare_before_sideeffects(self):
        value=job(); value['scope']='whole_core'
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory).resolve()/'not-created'
            with self.assertRaises(ValueError): q.prepare(value,F16,'d',target,{},NOW)
            self.assertFalse(target.exists())

    def prepare_fixture(self,host):
        value=job(host); topology=json.loads((FPGA/('artifacts/plain-f16-launch-v1/fit-plain-tools-v1/topology.json' if host==F16 else 'cloud/aws-topology-plain-0944-v1.json')).read_text())
        m=q.module('field_real_meter', 'cloud/host_hours_azure_v3.py' if host==F16 else 'cloud/host_hours_admit_v1.py'); old_module=q.module
        def modules(name,relative):
            if relative==('cloud/host_hours_azure_v3.py' if host==F16 else 'cloud/host_hours_admit_v1.py'): return m
            return old_module(name,relative)
        clock=NOW
        if host==F16:
            quote=json.loads((FPGA/'results/throughput-20260929/azure-sim-resize-r49-v1/provider-inputs-v1.json').read_text())
            clock=datetime.fromisoformat(quote['observed_at_utc'].replace('Z','+00:00'))+timedelta(seconds=1)
        with tempfile.TemporaryDirectory(prefix='field2h-prepare-test-',dir=FPGA/'artifacts') as directory:
            destination=Path(directory).resolve()/'prepared'
            with patch.object(q,'module',side_effect=modules),patch.object(q,'stamp',return_value=clock):
                if host==F16:
                    with patch.object(m,'provider_inputs',return_value=quote): handle,helpers,archive=q.prepare(value,host,'d',destination,topology,clock)
                else: handle,helpers,archive=q.prepare(value,host,'b',destination,topology,clock)
            request=json.loads(Path(handle['request']['path']).read_text()); budget=json.loads((destination/'host-hours.json').read_text())
            self.assertEqual(request['runtime_contract'],q.FIELD_CONTRACT); self.assertEqual(request['scope'],'component_probe')
            self.assertEqual(request['exemption'],'component_sizing_probe'); self.assertEqual(budget['per_job_charge_usd'],0)
            self.assertIn('plain_fit_field2h_v1.py',helpers); self.assertIn('plain_fit_v2.py',helpers)
            self.assertEqual(helpers['plain_fit_field2h_v1.py'],q.FIELD_RUNNER_SHA)
            self.assertEqual(q.digest(archive.read_bytes()),handle['package_sha256'])
            return request,budget

    def test_azure_7260_actual_budget_and_source_profile_bound(self):
        request,budget=self.prepare_fixture(F16)
        self.assertEqual(request['host_hours_budget']['max_seconds'],7260)
        self.assertEqual(request['host_hours_budget']['source_sha256'],request['project']['manifest_sha256'])
        self.assertEqual(request['host_hours_budget']['transition']['sha256'],q.TRANSITION_SHA)

    def test_aws_7260_pure_budget_no_six_hour_future_fee(self):
        request,budget=self.prepare_fixture(AWS)
        self.assertEqual(budget['outer_runtime_plus_stop_seconds'],7260)
        self.assertEqual(budget['future_full_host_bound_usd'],3.025)

    def test_actual_service_argv_field7200_allowedcpus_and_flat_runner(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve(); tools=root/'tools'; tools.mkdir(); project=root/'project'; project.mkdir(); (project/'manifest.json').write_text('{}')
            approved=dict(host=AWS,slot='b',unit='gfn16-field.service',project_name='project',project=dict(manifest_sha256=q.digest((project/'manifest.json').read_bytes())),scope='component_probe',mode='full',exemption='component_sizing_probe',runtime_contract=q.FIELD_CONTRACT)
            request=tools/'request.json'; q.save(request,approved)
            handle=dict(approved,remote_request=str(request),request_sha256=q.digest(request.read_bytes()),tools=str(tools))
            configs=deepcopy(q.HOSTS); configs[AWS]['root']=str(root)
            before='LoadState=not-found\nMainPID=0\nActiveState=inactive\nInvocationID=\n'
            after='LoadState=loaded\nMainPID=42\nActiveState=active\nInvocationID='+INV+'\n'
            rows=json.dumps(dict(_PID='1',UNIT=approved['unit'],JOB_TYPE='start',JOB_RESULT='done',INVOCATION_ID=INV))
            with patch.object(q,'HOSTS',configs),patch.object(q.sys,'platform','linux'),patch.object(q.os,'geteuid',return_value=1000),patch.object(q.socket,'gethostname',return_value=AWS),patch.object(q,'slot_preflight'),patch.object(q.subprocess,'check_output',side_effect=[before,after,rows]),patch.object(q.subprocess,'run') as native:
                q.worker(dict(op='launch',host=AWS,handle=handle,helper_sha256={}))
            argv=native.call_args.args[0]
            self.assertIn('--property=RuntimeMaxSec=7200',argv); self.assertIn('--property=TimeoutStopSec=60',argv)
            self.assertIn('--property=AllowedCPUs=6-11',argv); self.assertIn('--property=MemoryMax='+str(20<<30),argv)
            self.assertIn(str(tools/'plain_fit_field2h_v1.py'),argv); self.assertNotIn(str(tools/'plain_fit_v2.py'),argv)

    def test_flat_transport_expands_without_mac_parent_dependency(self):
        namespace=dict(__name__='_field_remote_fixture',__file__=str(FPGA/'tools/plain_fit_queue_field2h_v1.py'))
        exec(compile(q.FIELD_CONTROLLER_SOURCE,'field-remote-expanded','exec'),namespace)
        self.assertEqual(namespace['HORIZON'],7260); self.assertTrue(callable(namespace['worker']))
        backend=q.SSHBackend(Path('/private/tmp'),q.END)
        with patch.object(q,'stamp',return_value=NOW),patch.object(q.subprocess,'run',return_value=subprocess.CompletedProcess([],0,b'{"ok":true}',b'')) as run:
            self.assertEqual(backend.call(AWS,dict(op='fixture',host=AWS)),dict(ok=True))
        script=run.call_args.kwargs['input'].decode()
        self.assertIn(repr(q.FIELD_CONTROLLER_SOURCE),script); self.assertNotIn('frozen queue_v3 source drift',script)

    def test_nullable_start_retains_original_lease_never_relaunches(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve(); value=fixtures.queue([job()]); backend=q3fixtures.Backend(None)
            controller=q.Controller(value,root,backend,q3fixtures.prepare)
            current=controller.tick(NOW); self.assertEqual(current['field']['phase'],'launch_attempt')
            current=q.Controller(value,root,backend,q3fixtures.prepare).tick(NOW)
            self.assertEqual(current['field']['phase'],'launch_attempt'); self.assertEqual(sum(c[0]=='launch' for c in backend.calls),1)
            backend.actual=INV; current=q.Controller(value,root,backend,q3fixtures.prepare).tick(NOW)
            self.assertEqual(current['field']['invocation_id'],INV); self.assertEqual(sum(c[0]=='launch' for c in backend.calls),1)

    def test_existing_whole_six_hour_adoption_and_terminal_context_preserved(self):
        saved=FPGA/'results/throughput-20260929/track-a4b-aw16-aws-plain-v1'
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve(); evidence=root/'evidence'; evidence.mkdir(); q.unpack((saved/'native-reports.tar.gz').read_bytes(),evidence)
            receipt_path=root/'receipt.json'; shutil.copy2(saved/'terminal-collection-v1.json',receipt_path)
            receipt=json.loads(receipt_path.read_text()); original=json.loads((evidence/'request.json').read_text())
            ref=dict(path=str(evidence/'request.json'),sha256=q.digest((evidence/'request.json').read_bytes()))
            handle=dict(id='old-whole',host=AWS,slot=original['slot'],unit=receipt['unit'],invocation_id=receipt['invocation_id'],project_name=original['project_name'],request=ref,request_sha256=ref['sha256'],remote_request=q.HOSTS[AWS]['root']+'/old/request.json',scope='whole_core')
            bundle=dict(receipt=str(receipt_path),receipt_sha256=q.digest(receipt_path.read_bytes()),evidence=str(evidence))
            context=json.loads((evidence/'project/execution-context.json').read_text()); self.assertEqual(context['timeout_seconds'],21600)
            self.assertEqual(q.verify_terminal(handle,bundle),'native_fit_success')
            entry={key:handle[key] for key in ('id','host','slot','unit','invocation_id','project_name','request','remote_request','scope')}
            value=fixtures.queue([], [entry]); backend=fixtures.FakeBackend()
            backend.observations['old-whole']=dict(invocation_id=receipt['invocation_id'],request_sha256=ref['sha256'],state=dict(MainPID='42',ActiveState='active'))
            controller=q.Controller(value,root,backend); current=controller.tick(NOW)
            self.assertEqual(current['old-whole']['phase'],'adopt'); self.assertEqual(current['old-whole']['request_sha256'],ref['sha256'])
            self.assertFalse(any(call[0] in ('stage','launch') for call in backend.calls)); self.assertEqual(json.loads((evidence/'project/execution-context.json').read_text())['timeout_seconds'],21600)

    def test_field_terminal_requires_real_two_hour_metadata_not_old_six_hour_label(self):
        # Closed synthetic metadata fixture derived from retained component
        # evidence. This is a checker test, never a new native receipt claim.
        saved=FPGA/'results/throughput-20260929/stream27-p16c-aw16-f16-plain-v1'
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve(); evidence=root/'evidence'; evidence.mkdir(); q.unpack((saved/'native-reports.tar.gz').read_bytes(),evidence)
            request_path=evidence/'request.json'; request=json.loads(request_path.read_text())
            request.update(scope='component_probe',runtime_contract=q.FIELD_CONTRACT); request_path.write_text(json.dumps(request))
            context_path=evidence/'project/execution-context.json'; context=json.loads(context_path.read_text())
            context.update(timeout_seconds=7200,outer_runtime_max_seconds=7200,outer_timeout_stop_seconds=60,
              runtime_kind=q.FIELD_CONTRACT['kind'],allowed_cpus=context['affinity'],launcher_sha256=q.FIELD_RUNNER_SHA)
            context_path.write_text(json.dumps(context))
            result_path=evidence/'project/execution-result.json'; result=json.loads(result_path.read_text()); result['context_sha256']=q.digest(context_path.read_bytes()); result_path.write_text(json.dumps(result))
            inventory_path=evidence/'collection/collection-inventory-v1.json'; inventory=json.loads(inventory_path.read_text())
            for relative in ('request.json','project/execution-context.json','project/execution-result.json'):
                raw=(evidence/relative).read_bytes(); inventory['files'][relative]=dict(sha256=q.digest(raw),size=len(raw))
            inventory_path.write_text(json.dumps(inventory))
            receipt_path=root/'receipt.json'; receipt=json.loads((saved/'terminal-collection-v1.json').read_text())
            receipt.update(source_request_sha256=q.digest(request_path.read_bytes()),inventory_sha256=q.digest(inventory_path.read_bytes()),native_result=result)
            receipt_path.write_text(json.dumps(receipt))
            ref=dict(path=str(request_path),sha256=q.digest(request_path.read_bytes()))
            handle=dict(id='field-terminal',host=F16,slot=request['slot'],unit=receipt['unit'],invocation_id=receipt['invocation_id'],project_name=request['project_name'],request=ref,request_sha256=ref['sha256'],scope='component_probe')
            bundle=dict(receipt=str(receipt_path),receipt_sha256=q.digest(receipt_path.read_bytes()),evidence=str(evidence))
            self.assertEqual(q.verify_terminal(handle,bundle),'native_fit_success')
            context['outer_runtime_max_seconds']=21720; context_path.write_text(json.dumps(context))
            result['context_sha256']=q.digest(context_path.read_bytes()); result_path.write_text(json.dumps(result))
            for relative in ('project/execution-context.json','project/execution-result.json'):
                raw=(evidence/relative).read_bytes(); inventory['files'][relative]=dict(sha256=q.digest(raw),size=len(raw))
            inventory_path.write_text(json.dumps(inventory)); receipt.update(inventory_sha256=q.digest(inventory_path.read_bytes()),native_result=result); receipt_path.write_text(json.dumps(receipt)); bundle['receipt_sha256']=q.digest(receipt_path.read_bytes())
            with self.assertRaisesRegex(ValueError,'two-hour native'): q.verify_terminal(handle,bundle)


if __name__=='__main__': unittest.main()
