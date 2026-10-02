"""Fixed queue/restart/terminal tests. No SSH/cloud/vendor execution."""
from copy import deepcopy
from datetime import datetime, timezone
import errno
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

FPGA=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('plain_queue',FPGA/'tools/plain_fit_queue_v1.py')
q=importlib.util.module_from_spec(spec); spec.loader.exec_module(q)
NOW=datetime(2026,10,1,11,tzinfo=timezone.utc)
F16='gfn16-azure-f16'; AWS='gfn16-aws-m8i'; INV='a'*32


def variant(host):
    workers=q.HOSTS[host]['workers']; root=FPGA/f'results/throughput-20260929/a10-field-physical-probe-v1/project-workers{workers}'
    runner=q.module('fixture_runner','cloud/plain_fit_v2.py')
    context=runner.runner(dict(runner.HOSTS[host],root=str(FPGA/'cloud')),host,False).verify_project(root)
    return dict(path=str(root),files={str(p.relative_to(root)):q.digest(p.read_bytes()) for p in root.rglob('*') if p.is_file()},project=context,exemption='component_sizing_probe')


def job(key='probe',host=F16,after=None):
    return dict(id=key,priority=1,project_name='queue-'+key,unit='gfn16-queue-'+key+'.service',scope='component_probe',allowed_slots={host:list(q.HOSTS[host]['slots'])},variants={host:variant(host)},after=after or [],requires=[])


def queue(jobs=None,adopt=None):
    return dict(schema='plain-fit-queue-v1',until_utc='2026-10-02T04:00:00Z',jobs=jobs or [],adopt=adopt or [])


class FakeBackend:
    def __init__(self): self.calls=[]; self.observations={}; self.fail_launch=False; self.fail_stage=False; self.outcome='native_fit_success'; self.busy=set()
    def preflight(self,host,slot):
        self.calls.append(('preflight',host,slot))
        if (host,slot) in self.busy: raise ValueError('physical lock busy')
        return dict(hostname=host,observed_at=NOW.isoformat(),cpus=[],slots=q.HOSTS[host]['slots'])
    def stage(self,handle,package):
        self.calls.append(('stage',handle['id']))
        if self.fail_stage: raise ValueError('stage partial')
    def launch(self,handle,helpers):
        self.calls.append(('launch',handle['id']))
        if self.fail_launch: raise subprocess.TimeoutExpired('native observation',30)
        value=dict(invocation_id=INV,request_sha256=handle['request_sha256'],state=dict(MainPID='20',ActiveState='active'))
        self.observations[handle['id']]=value; return value
    def observe(self,handle):
        self.calls.append(('observe',handle['id']))
        return self.observations.get(handle['id'],dict(invocation_id=handle.get('invocation_id'),request_sha256=handle['request_sha256'],state=dict(MainPID='0',ActiveState='inactive')))
    def collect(self,handle):
        self.calls.append(('collect',handle['id'])); return dict(outcome=self.outcome)


def fake_prepare(job,host,slot,directory,topology,now):
    directory.mkdir(); request=directory/'request.json'
    q.save(request,dict(schema='plain-fit-request-v1',host=host,slot=slot,unit=job['unit'],project_name=job['project_name'],project=job['variants'][host]['project']))
    ref=dict(path=str(request),sha256=q.digest(request.read_bytes()))
    return dict(id=job['id'],host=host,slot=slot,unit=job['unit'],project_name=job['project_name'],request=ref,request_sha256=ref['sha256'],remote_request=q.HOSTS[host]['root']+'/tools/request.json',tools=q.HOSTS[host]['root']+'/tools',scope=job['scope']),{},request


class QueueTests(unittest.TestCase):
    def setUp(self): self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root=Path(self.tmp.name).resolve(); self.backend=FakeBackend()
    def controller(self,value,terminal=None): return q.Controller(value,self.root,self.backend,fake_prepare,terminal or (lambda h,b:b['outcome']))
    def test_exact_six_disjoint_fixed_slots_and_worker_variants(self):
        self.assertEqual(sum(len(v['slots']) for v in q.HOSTS.values()),6)
        for config in q.HOSTS.values():
            cpus=[c for slot in config['slots'].values() for c in slot]; self.assertEqual(len(cpus),len(set(cpus)))
        q.validate_queue(queue([job('a',F16),job('b',AWS)]))
        bad=job('wrong',AWS); bad['variants'][AWS]=variant(F16)
        with self.assertRaises(ValueError): q.validate_queue(queue([bad]))
    def test_source_variant_hash_or_extra_member_fails(self):
        value=job(); bad=deepcopy(value); bad['variants'][F16]['project']['manifest_sha256']='0'*64
        with self.assertRaises(ValueError): q.validate_queue(queue([bad]))
        bad=deepcopy(value); bad['variants'][F16]['files'].pop('run.tcl')
        with self.assertRaises(ValueError): q.validate_queue(queue([bad]))
    def test_no_gcp_no_unknown_dependency_no_cycle_no_scope_inflation(self):
        for mutate in ('gcp','unknown','cycle','scope'):
            j=job()
            if mutate=='gcp': j['variants']={'gfn16-pilot-c4d':variant(F16)}
            elif mutate=='unknown': j['after']=[dict(job='missing',outcome='native_fit_success')]
            elif mutate=='cycle': j['after']=[dict(job=j['id'],outcome='native_fit_success')]
            else: j['scope']='whole_core'
            with self.subTest(mutate=mutate),self.assertRaises(ValueError): q.validate_queue(queue([j]))
    def test_absolute_end_not_restart_plus_24h(self):
        value=queue([job()]); value['until_utc']='2026-10-02T04:00:01Z'
        with self.assertRaises(ValueError): q.validate_queue(value)
        controller=self.controller(queue([job()])); controller.tick(q.END)
        self.assertEqual(self.backend.calls,[])
        controller.tick(datetime(2026,10,1,23,tzinfo=timezone.utc))
        self.assertEqual(self.backend.calls,[]) # no six-hour launch beyond end
    def test_cutoff_does_not_poll_or_drop_adopted_native_handles(self):
        value=queue([job()]); controller=self.controller(value); controller.tick(NOW)
        self.backend.calls=[]; current=controller.tick(q.END)
        self.assertEqual(self.backend.calls,[]); self.assertEqual(current['probe']['phase'],'started')
    def test_ssh_operation_timeout_is_remaining_absolute_window(self):
        backend=q.SSHBackend(self.root,q.END)
        with patch.object(q,'stamp',return_value=datetime(2026,10,2,3,59,55,tzinfo=timezone.utc)):
            self.assertEqual(backend.timeout(240),5)
        with patch.object(q,'stamp',return_value=q.END),self.assertRaises(ValueError): backend.timeout(240)
    def test_one_controller_flock(self):
        with q.controller_lock(self.root):
            with self.assertRaises(BlockingIOError):
                with q.controller_lock(self.root): pass
    def test_successful_launch_write_ahead_then_exact_handle_no_duplicates(self):
        value=queue([job()]); controller=self.controller(value); result=controller.tick(NOW)
        self.assertEqual(result['probe']['phase'],'started'); self.assertEqual(result['probe']['invocation_id'],INV)
        self.assertEqual([r['event'] for r in controller.journal.rows],['intent','launch_attempt','started'])
        self.controller(value).tick(NOW)
        self.assertEqual(sum(c[0]=='launch' for c in self.backend.calls),1)
    def test_launch_timeout_and_unit_gc_never_retries_or_frees(self):
        self.backend.fail_launch=True; value=queue([job()]); result=self.controller(value).tick(NOW)
        self.assertEqual(result['probe']['phase'],'launch_attempt')
        result=self.controller(value).tick(NOW)
        self.assertEqual(result['probe']['phase'],'launch_attempt')
        self.assertEqual(sum(c[0]=='launch' for c in self.backend.calls),1)
        self.assertFalse(any(c[0]=='collect' for c in self.backend.calls))
    def test_partial_stage_retains_slot_no_retry_duplicate(self):
        self.backend.fail_stage=True; value=queue([job()]); self.controller(value).tick(NOW); result=self.controller(value).tick(NOW)
        self.assertEqual(result['probe']['phase'],'intent'); self.assertEqual(sum(c[0]=='stage' for c in self.backend.calls),1)
        self.assertFalse(any(c[0]=='launch' for c in self.backend.calls))
    def test_recover_exact_original_invocation_after_uncertain_launch(self):
        self.backend.fail_launch=True; value=queue([job()]); self.controller(value).tick(NOW)
        handle=self.controller(value).journal.current()['probe']
        self.backend.observations['probe']=dict(invocation_id=INV,request_sha256=handle['request_sha256'],state=dict(MainPID='20',ActiveState='active'))
        result=self.controller(value).tick(NOW)
        self.assertEqual(result['probe']['phase'],'started'); self.assertEqual(sum(c[0]=='launch' for c in self.backend.calls),1)
    def test_typed_terminal_success_releases_and_launches_dependent_same_tick(self):
        value=queue([job('parent'),job('candidate',after=[dict(job='parent',outcome='native_fit_success')])]); controller=self.controller(value); controller.tick(NOW)
        self.backend.observations['parent']['state']=dict(MainPID='0',ActiveState='inactive')
        result=controller.tick(NOW)
        self.assertEqual(result['parent']['phase'],'terminal'); self.assertEqual(result['candidate']['slot'],'a')
        self.assertEqual(result['candidate']['phase'],'started')
    def test_failed_predecessor_blocks_positive_but_typed_failure_branch_runs(self):
        value=queue([job('parent'),job('positive',after=[dict(job='parent',outcome='native_fit_success')]),job('negative',after=[dict(job='parent',outcome='native_fit_failure')])])
        controller=self.controller(value); controller.tick(NOW); self.backend.outcome='native_fit_failure'
        self.backend.observations['parent']['state']=dict(MainPID='0',ActiveState='failed'); result=controller.tick(NOW)
        self.assertNotIn('positive',result); self.assertEqual(result['negative']['phase'],'started')
    def test_invalid_or_missing_terminal_contract_keeps_lease(self):
        def refuse(h,b): raise ValueError('source/context/guard missing')
        value=queue([job()]); controller=self.controller(value,refuse); controller.tick(NOW)
        self.backend.observations['probe']['state']=dict(MainPID='0',ActiveState='inactive')
        result=controller.tick(NOW); self.assertEqual(result['probe']['phase'],'started')
    def test_sourcebound_external_gate_type_false_never_passes_as_zero(self):
        gate=self.root/'gate.json'; q.save(gate,dict(passed=0,schema='test'))
        j=job(); j['requires']=[dict(path=str(gate),sha256=q.digest(gate.read_bytes()),fields=dict(schema='test',passed=False))]
        self.controller(queue([j])).tick(NOW); self.assertFalse(any(c[0]=='launch' for c in self.backend.calls))
    def test_adopt_exact_original_request_and_invocation_without_stage(self):
        req=self.root/'original.json'; q.save(req,dict(schema='plain-fit-request-v1',host=F16,slot='a',unit='gfn16-original.service',project_name='original'))
        entry=dict(id='original',host=F16,slot='a',unit='gfn16-original.service',invocation_id=INV,project_name='original',request=dict(path=str(req),sha256=q.digest(req.read_bytes())),remote_request=q.HOSTS[F16]['root']+'/old/request.json',scope='whole_core')
        value=queue([], [entry]); self.backend.observations['original']=dict(invocation_id=INV,request_sha256=entry['request']['sha256'],state=dict(MainPID='1',ActiveState='active'))
        result=self.controller(value).tick(NOW); self.assertEqual(result['original']['phase'],'adopt')
        self.assertFalse(any(c[0] in ('stage','launch') for c in self.backend.calls))
        bad=deepcopy(entry); bad['slot']='b'
        with self.assertRaises(ValueError): q.validate_queue(queue([],[bad]))
    def test_journal_queue_drift_or_partial_tail_fail_closed(self):
        value=queue([job()]); self.controller(value).tick(NOW)
        bad=deepcopy(value); bad['jobs'][0]['priority']=2
        with self.assertRaises(ValueError): self.controller(bad)
        with (self.root/'events.jsonl').open('ab') as stream: stream.write(b'{partial')
        with self.assertRaises(ValueError): self.controller(value)
    def test_live_busy_physical_slot_skipped_not_overlapped(self):
        self.backend.busy.add((F16,'a')); result=self.controller(queue([job()])).tick(NOW)
        self.assertEqual(result['probe']['slot'],'b')
    def test_invalid_missing_or_duplicate_allowed_slots_fail_closed(self):
        for slots in (None,{}, {F16:[]}, {F16:['e']}, {F16:['a','a']}, {AWS:['b']}, {F16:['d'],AWS:['b']}):
            value=job()
            if slots is None: value.pop('allowed_slots')
            else: value['allowed_slots']=slots
            with self.subTest(slots=slots),self.assertRaises(ValueError): q.validate_queue(queue([value]))
    def test_allowed_static_subset_preserves_audit_train_slots(self):
        f16=job('f16',F16); f16['allowed_slots']={F16:['d']}
        aws=job('aws',AWS); aws['allowed_slots']={AWS:['b']}
        result=self.controller(queue([f16,aws])).tick(NOW)
        self.assertEqual(result['f16']['slot'],'d'); self.assertEqual(result['aws']['slot'],'b')
        preflights={(c[1],c[2]) for c in self.backend.calls if c[0]=='preflight'}
        self.assertEqual(preflights,{(F16,'d'),(AWS,'b')})
    def test_pause_blocks_new_dispatch_without_losing_running_handle(self):
        value=queue([job()]); controller=self.controller(value); controller.tick(NOW)
        original=Path.exists
        def exists(path): return True if str(path).endswith('/docs/briefs/PAUSE') else original(path)
        with patch.object(Path,'exists',exists): result=controller.tick(NOW)
        self.assertEqual(result['probe']['phase'],'started'); self.assertEqual(sum(c[0]=='launch' for c in self.backend.calls),1)


class ScratchAndTerminalTests(unittest.TestCase):
    def test_new_variant_descriptor_closes_actual_four_and_six_worker_inputs(self):
        for host in (F16,AWS):
            v=variant(host); actual=q.variant_descriptor(Path(v['path']),host,exemption='component_sizing_probe')
            self.assertEqual(actual,v)

    def test_mount_quota_ramdisk_and_space_floor_fail_closed(self):
        class Libc:
            def quotactl(self,*args): q.ctypes.set_errno(errno.ESRCH); return -1
        for filesystem,options,bytes_free,inodes in (('ext4','rw,usrquota',30<<30,200000),('tmpfs','rw',30<<30,200000),('ext4','rw',19<<30,200000),('ext4','rw',30<<30,99999)):
            raw=json.dumps(dict(filesystems=[dict(source='/dev/sda',target='/home',fstype=filesystem,options=options)]))
            space=type('S',(),dict(f_bavail=bytes_free,f_frsize=1,f_favail=inodes))()
            with self.subTest(options=options,filesystem=filesystem,bytes_free=bytes_free,inodes=inodes),patch.object(q.subprocess,'check_output',return_value=raw),patch.object(q.ctypes,'CDLL',return_value=Libc()),patch.object(q.os,'statvfs',return_value=space),self.assertRaises(ValueError): q.scratch_admission('/home')

    def test_native_launch_command_has_exact_bounded_limits_and_fixed_affinity(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve(); tools=root/'tools'; tools.mkdir(); project=root/'project'; project.mkdir()
            (project/'manifest.json').write_text('{}')
            request=tools/'request.json'; value=dict(host=AWS,slot='b',unit='gfn16-test.service',project_name='project',project=dict(manifest_sha256=q.digest((project/'manifest.json').read_bytes())))
            q.save(request,value)
            handle=dict(value,remote_request=str(request),request_sha256=q.digest(request.read_bytes()),tools=str(tools))
            configs=deepcopy(q.HOSTS); configs[AWS]['root']=str(root)
            before='LoadState=not-found\nMainPID=0\nActiveState=inactive\nInvocationID=\n'
            after='LoadState=loaded\nMainPID=42\nActiveState=active\nInvocationID='+INV+'\n'
            rows=json.dumps(dict(_PID='1',UNIT=value['unit'],JOB_TYPE='start',JOB_RESULT='done',INVOCATION_ID=INV))
            with patch.object(q,'HOSTS',configs),patch.object(q.sys,'platform','linux'),patch.object(q.os,'geteuid',return_value=1000),patch.object(q.socket,'gethostname',return_value=AWS),patch.object(q,'slot_preflight'),patch.object(q.subprocess,'check_output',side_effect=[before,after,rows]),patch.object(q.subprocess,'run') as run:
                result=q.worker(dict(op='launch',host=AWS,handle=handle,helper_sha256={}))
            argv=run.call_args.args[0]
            self.assertIn('--property=RuntimeMaxSec=21720',argv); self.assertIn('--property=TimeoutStopSec=60',argv)
            self.assertIn('--property=MemoryMax='+str(20<<30),argv); self.assertIn('--property=MemorySwapMax=0',argv)
            self.assertIn('--property=CPUQuota=600%',argv); self.assertIn('6,7,8,9,10,11',argv)
            self.assertIn('--property=AllowedCPUs=6-11',argv)
            env=argv.index('/usr/bin/env')
            self.assertEqual(argv[env:env+4],['/usr/bin/env','-i','HOME='+str(root.parent),'PATH=/usr/local/bin:/usr/bin:/bin'])
            self.assertEqual(argv[env+4:env+7],['/usr/bin/python3','-I','-B'])
            self.assertNotIn('--remain-after-exit',argv); self.assertEqual(result['invocation_id'],INV)

    def test_kernel_inactive_quota_required_unknown_or_active_denied(self):
        class Libc:
            def __init__(self,error): self.error=error
            def quotactl(self,*args): q.ctypes.set_errno(self.error); return -1
        document=json.dumps(dict(filesystems=[dict(source='/dev/sda1',target='/home',fstype='ext4',options='rw,relatime')]))
        space=type('S',(),dict(f_bavail=30<<30,f_frsize=1,f_favail=200000))()
        for error in (errno.ESRCH,errno.EPERM,errno.ENOSYS):
            with patch.object(q.subprocess,'check_output',return_value=document),patch.object(q.ctypes,'CDLL',return_value=Libc(error)),patch.object(q.os,'statvfs',return_value=space):
                if error==errno.ESRCH: self.assertEqual(q.scratch_admission('/home')['kernel_Q_GETFMT']['errno'],errno.ESRCH)
                else:
                    with self.assertRaises(ValueError): q.scratch_admission('/home')
    def test_archive_links_duplicates_traversal_and_bomb_denied(self):
        for filename,kind in (('../escape','file'),('a','symlink'),('/absolute','file')):
            raw=io.BytesIO()
            with tarfile.open(fileobj=raw,mode='w:gz') as archive:
                entry=tarfile.TarInfo(filename)
                if kind=='symlink': entry.type=tarfile.SYMTYPE; entry.linkname='elsewhere'
                else: entry.size=1
                archive.addfile(entry,io.BytesIO(b'x') if kind=='file' else None)
            with tempfile.TemporaryDirectory() as directory,self.assertRaises(ValueError): q.unpack(raw.getvalue(),Path(directory).resolve())
    def fixture(self,directory):
        saved=FPGA/'results/throughput-20260929/stream27-p16c-aw16-f16-plain-v1'; root=directory/'evidence'; root.mkdir()
        q.unpack((saved/'native-reports.tar.gz').read_bytes(),root)
        receipt=directory/'receipt.json'; shutil.copy2(saved/'terminal-collection-v1.json',receipt)
        request=root/'request.json'; value=json.loads(request.read_text()); r=json.loads(receipt.read_text())
        handle=dict(id='prior',host=r['host'],slot=value['slot'],unit=r['unit'],invocation_id=r['invocation_id'],project_name=value['project_name'],request=dict(path=str(request),sha256=q.digest(request.read_bytes())),request_sha256=q.digest(request.read_bytes()),scope=r['scope'])
        return handle,dict(receipt=str(receipt),receipt_sha256=q.digest(receipt.read_bytes()),evidence=str(root))
    def test_real_archived_native_terminal_replays_without_vendor_or_cloud(self):
        with tempfile.TemporaryDirectory() as directory:
            handle,bundle=self.fixture(Path(directory).resolve()); self.assertEqual(q.verify_terminal(handle,bundle),'native_fit_success')
    def test_archived_context_source_drift_or_wrong_invocation_never_releases(self):
        for mutate in ('invocation','source','receipt'):
            with tempfile.TemporaryDirectory() as directory:
                handle,bundle=self.fixture(Path(directory).resolve())
                if mutate=='invocation': handle['invocation_id']='f'*32
                elif mutate=='source': (Path(bundle['evidence'])/'project/probe.sdc').write_text('drift')
                else: bundle['receipt_sha256']='f'*64
                with self.subTest(mutate=mutate),self.assertRaises(ValueError): q.verify_terminal(handle,bundle)


if __name__=='__main__': unittest.main()
