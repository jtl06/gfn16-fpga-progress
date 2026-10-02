"""Audit admission/closure/resource negatives; all native calls mocked."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import errno
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

FPGA=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('plain_audit_adapter',FPGA/'cloud/plain_fit_audit_v1.py')
q=importlib.util.module_from_spec(spec); spec.loader.exec_module(q)
NOW=datetime(2026,10,1,9,0,tzinfo=timezone.utc)


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root=Path(self.temp.name).resolve()
        configs=deepcopy(q.HOSTS)
        for value in configs.values(): value['root']=str(self.root)
        self.patch=patch.object(q,'HOSTS',configs); self.patch.start(); self.addCleanup(self.patch.stop)
        real_meter=q.meter
        def meter(host,source_root):
            m=real_meter(host,source_root)
            if host==q.AWS:
                admit=m.admit; m.admit=lambda host,seconds:admit(host,seconds,now=NOW)
            else:
                validate=m.validate_budget
                m.validate_budget=lambda value,host,seconds,**kwargs:validate(value,host,seconds,now=NOW,**kwargs)
            return m
        self.patch_meter=patch.object(q,'meter',side_effect=meter); self.patch_meter.start(); self.addCleanup(self.patch_meter.stop)

    def fixture(self,host=q.AWS):
        if host==q.AWS: saved=FPGA/'results/throughput-20260929/track-a4b-aw16-aws-plain-v1'; scope='whole_core'; slot='b'
        else: saved=FPGA/'results/throughput-20260929/stream27-p16c-aw16-f16-plain-v1'; scope='component_probe'; slot='c'
        original=saved/'request.json'; original_value=json.loads(original.read_text())
        project=self.root/original_value['project_name']; shutil.copytree(saved/'project',project)
        (project/'qdb').mkdir(); (project/'qdb/compiled.hsd').write_bytes(b'synthetic exact private-copy QDB fixture, NEVER native evidence')
        tools=self.root/'audit-tools'; tools.mkdir()
        for source,target in ((FPGA/'cloud/plain_fit_audit_v1.py','plain_fit_audit_v1.py'),(FPGA/'tools'/q.AUDIT,q.AUDIT),(FPGA/'synthesis'/q.TCL,q.TCL)):
            shutil.copy2(source,tools/target)
        h=q.helper(tools); database=h.qdb_inventory(h.inventory(project)); (project/'database-inventory-final.json').write_text(json.dumps(database))
        terminal=json.loads((saved/'terminal-collection-v1.json').read_text()); terminal['project']=str(project)
        terminal_path=tools/'original-terminal.json'; terminal_path.write_text(json.dumps(terminal))
        toolroot=self.root/'altera_pro/26.1/quartus'; (toolroot/'bin').mkdir(parents=True); (toolroot/'linux64').mkdir()
        for folder in ('bin','linux64'): (toolroot/folder/'quartus_sta').write_bytes(b'pure native tool fixture: not executed')
        native_pins={relative:q.sha(toolroot/relative) for relative in q.STA_PINS}
        toolpatch=patch.object(q,'STA_PINS',native_pins); toolpatch.start(); self.addCleanup(toolpatch.stop)
        tools_map={str(toolroot/relative):pin for relative,pin in native_pins.items()}
        selected='10.958'
        audit_spec=h.make_spec(project,self.root/'audit-output',terminal_path,tools/q.TCL,tools_map,scope=scope,native_seconds=2100,
          maximum_copy_bytes=64<<30,selected_period_ns=selected,selection_reason='explicit scoped audit test point')
        spec_path=tools/'spec.json'; spec_path.write_text(json.dumps(audit_spec)); spec_ref=dict(path=str(spec_path),sha256=q.sha(spec_path))
        budget=None
        if host==q.FIT:
            m=q.meter(host,FPGA); provider='results/throughput-20260929/azure-sim-resize-r49-v1/provider-inputs-v1.json'
            transition='results/throughput-20260929/azure-sim-resize-r49-v1/rate-transition-v1.json'
            budget=m.make_budget(host,2280,provider,q.sha(FPGA/provider),spec_ref['sha256'],transition_path=transition,transition_sha256=q.TRANSITION_SHA)
        pins=q.runtime_pins(host,budget,FPGA)
        for relative,pin in pins.items():
            if not relative.startswith('fpga/'): continue
            source=FPGA/relative[5:]; target=tools/relative; target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(source,target)
        original_ref=dict(path=str(original),sha256=q.sha(original))
        request=q.make_request(spec_ref,original_ref,host,slot,'gfn16-audit-fixture.service',pins,budget)
        request_path=tools/'request.json'; request_path.write_text(json.dumps(request))
        return tools,project,audit_spec,request,request_path

    def test_request_binds_actual_source_context_terminal_and_full_qdb_maps(self):
        tools,project,spec,request,path=self.fixture()
        self.assertEqual(request['original_tree'],q.helper(tools).inventory(project))
        self.assertEqual(request['qdb_inventory'],json.loads((project/'database-inventory-final.json').read_text()))
        self.assertEqual(q.verify_request(request,tools)[0],spec)
        self.assertFalse(any('python' in name for name in request['runtime_sha256']))

    def test_original_request_or_terminal_source_proof_cannot_be_substituted(self):
        tools,project,spec,request,path=self.fixture()
        bad=deepcopy(request); bad['original_request']['sha256']='0'*64
        with self.assertRaises(ValueError): q.verify_request(bad,tools)
        receipt=Path(spec['terminal_receipt']); value=json.loads(receipt.read_text()); value['source_request_sha256']='0'*64; receipt.write_text(json.dumps(value))
        badspec=deepcopy(spec); badspec['terminal_receipt_sha256']=q.sha(receipt)
        Path(request['audit_spec']['path']).write_text(json.dumps(badspec)); request['audit_spec']['sha256']=q.sha(Path(request['audit_spec']['path']))
        with self.assertRaisesRegex(ValueError,'trusted native'): q.verify_request(request,tools)

    def test_unknown_original_qdb_or_source_changes_refused(self):
        tools,project,spec,request,path=self.fixture()
        (project/'qdb/compiled.hsd').write_bytes(b'drift')
        with self.assertRaises(ValueError): q.verify_request(request,tools)

    def test_helper_closure_extra_or_missing_pin_refused(self):
        tools,project,spec,request,path=self.fixture()
        for operation in ('extra','missing'):
            bad=deepcopy(request)
            if operation=='extra': bad['runtime_sha256']['/usr/bin/python3']='0'*64
            else: bad['runtime_sha256'].pop(q.TCL)
            with self.subTest(operation=operation),self.assertRaises(ValueError): q.verify_request(bad,tools)

    def test_inner_runtime_overflow_and_unknown_host_slot_refused(self):
        tools,project,spec,request,path=self.fixture()
        for host,slot in (('gfn16-pilot-c4d','a'),(q.AWS,'c')):
            bad=deepcopy(request); bad.update(host=host,slot=slot)
            with self.assertRaises(ValueError): q.verify_request(bad,tools)
        spec['native_seconds']=2101; Path(request['audit_spec']['path']).write_text(json.dumps(spec)); request['audit_spec']['sha256']=q.sha(Path(request['audit_spec']['path']))
        with self.assertRaisesRegex(ValueError,'inner STA'): q.verify_request(request,tools)

    def test_azure_spec_source_runtime_and_qualified_phase_are_bound(self):
        tools,project,spec,request,path=self.fixture(q.FIT)
        q.verify_request(request,tools)
        for key,value in (('source_sha256','f'*64),('max_seconds',2281),('transition',None)):
            bad=deepcopy(request); bad['host_hours_budget'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError): q.verify_request(bad,tools)

    def test_service_argv_exact_resource_bounds_allowed_cpus_and_cleanenv(self):
        tools,project,spec,request,path=self.fixture(); ref=dict(path=str(path),sha256=q.sha(path)); argv=q.service_argv(ref)
        for property in ('AllowedCPUs=6-11','CPUQuota=600%','MemoryMax='+str(20<<30),'MemorySwapMax=0','RuntimeMaxSec=2220','TimeoutStopSec=60','KillMode=control-group'):
            self.assertIn('--property='+property,argv)
        self.assertIn('6,7,8,9,10,11',argv); index=argv.index('/usr/bin/env')
        self.assertEqual(argv[index:index+4],['/usr/bin/env','-i','HOME='+str(self.root.parent),'PATH=/usr/local/bin:/usr/bin:/bin'])

    def test_static_shared_and_physical_lock_names_are_interoperable(self):
        names=dict(q.lock_names(q.AWS,'b',[(0,i) for i in range(8,14)]))
        self.assertEqual(names['.fit-m8azn12-mode.lock'],q.fcntl.LOCK_SH)
        self.assertEqual(names['.fit-slot-a.lock'],q.fcntl.LOCK_SH); self.assertEqual(names['.fit-slot-b.lock'],q.fcntl.LOCK_SH)
        self.assertEqual(names['.fit-slot-m8azn12-b.lock'],q.fcntl.LOCK_EX)
        self.assertTrue(all(names[f'.fit-physical-p0-c{i}.lock']==q.fcntl.LOCK_EX for i in range(8,14)))

    def mocked_launch(self,timing_closes=True,mutate_original=False):
        tools,project,spec,request,path=self.fixture(); h=q.helper(tools); before=request['original_tree']
        def native(command,**kwargs):
            self.assertEqual(command[:4],['/usr/bin/python3','-I','-B',str(tools/q.AUDIT)])
            self.assertEqual(kwargs['timeout'],2220)
            output=Path(spec['output']); output.mkdir(); copied=output/'snapshot'; shutil.copytree(project,copied)
            status='native_scoped_timing_closes_pending_independent_review' if timing_closes else 'native_timing_violation'
            receipt=dict(schema='plain-fit-postfit-audit-result-v1',project=str(project),scope=spec['scope'],helper_sha256=q.AUDIT_SHA,tcl_sha256=q.TCL_SHA,tool_sha256=spec['tool_sha256'],
              spec_sha256=request['audit_spec']['sha256'],original_before=before,original_tree_sha256=spec['original_tree_sha256'],qdb_inventory_sha256=spec['qdb_inventory_sha256'],
              original_unchanged=True,compiled_input_unchanged=True,final_verification_errors=[],snapshot_after=h.inventory(copied),status=status,native_execution_complete=True,
              timing_closes=timing_closes,assessed_phase='selected',fit_commands=0,promotion_allowed=False)
            (output/'receipt.json').write_text(json.dumps(receipt))
            if mutate_original: (project/'qdb/compiled.hsd').write_bytes(b'illegal original mutation')
            return subprocess.CompletedProcess(command,0 if timing_closes else 2)
        show='MainPID=0\nActiveState=inactive\nSubState=dead\nInvocationID=\n'
        real_read_text=Path.read_text
        def text(path,*args,**kwargs):
            if str(path)=='/proc/meminfo': return 'MemAvailable: 104857600 kB\n'
            return real_read_text(path,*args,**kwargs)
        with patch.object(q,'HERE',tools),patch.object(q.sys,'platform','linux'),patch.object(q.os,'geteuid',return_value=1000),patch.object(q.socket,'gethostname',return_value=q.AWS),\
             patch.object(Path,'cwd',return_value=self.root),patch.object(Path,'read_text',text),patch.object(q,'topology',return_value=[(0,i) for i in range(8,14)]),\
             patch.object(q,'limits',return_value=dict(constrained=True)),patch.object(q,'scratch',return_value=dict(admitted=True)),\
             patch.object(q.subprocess,'check_output',side_effect=[show,'26.1.0 Build 110 Pro Edition']),patch.object(q.subprocess,'run',side_effect=native):
            code=q.launch(path,q.sha(path))
        return code,json.loads((self.root/'audit-output-adapter-result.json').read_text())

    def test_mocked_native_closure_retains_scoped_unpromoted_success(self):
        code,result=self.mocked_launch(); self.assertEqual(code,0); self.assertTrue(result['timing_closes']); self.assertFalse(result['promotion_allowed'])

    def test_mocked_native_violation_is_typed_not_inferred_success(self):
        code,result=self.mocked_launch(False); self.assertEqual(code,2); self.assertEqual(result['status'],'native_timing_violation'); self.assertTrue(result['native_execution_complete'])

    def test_mocked_original_mutation_fails_final_sourceguard(self):
        code,result=self.mocked_launch(True,True); self.assertEqual(code,2); self.assertEqual(result['status'],'failed_native_or_evidence'); self.assertTrue(result['final_errors'])


class ScratchTests(unittest.TestCase):
    def test_native_cgroup_requires_exact_effective_cpuset_and_bounded_unit(self):
        unit='gfn16-audit-limits.service'; base='/sys/fs/cgroup/system.slice/'+unit
        files={'/proc/self/cgroup':'0::/system.slice/'+unit+'\n',base+'/cpu.max':'6000000 1000000',
          base+'/memory.max':str(20<<30),base+'/memory.swap.max':'0',base+'/cpuset.cpus.effective':'6-11',
          '/sys/fs/cgroup/system.slice/cpu.max':'max 1000000','/sys/fs/cgroup/system.slice/memory.max':'max'}
        props='RuntimeMaxUSec=37min\nTimeoutStopUSec=1min\nKillMode=control-group\n'
        request=dict(host=q.AWS,slot='b',unit=unit)
        with patch.object(Path,'read_text',lambda path:files[str(path)]),patch.object(q.subprocess,'check_output',return_value=props):
            self.assertEqual(q.limits(request)['allowed_cpus'],list(range(6,12)))
            files[base+'/cpuset.cpus.effective']='0-11'
            with self.assertRaisesRegex(ValueError,'AllowedCPUs'): q.limits(request)
            files[base+'/cpuset.cpus.effective']='6-11'; files[base+'/memory.swap.max']='1024'
            with self.assertRaises(ValueError): q.limits(request)

    def test_kernel_quota_unknown_copy_byte_or_inode_floor_fail_closed(self):
        class Libc:
            def __init__(self,error): self.error=error
            def quotactl(self,*args): q.ctypes.set_errno(self.error); return -1
        raw=json.dumps(dict(filesystems=[dict(source='/dev/sda',fstype='ext4',options='rw',target='/home')]))
        for error,free,inodes,copy,passes in ((errno.ESRCH,30<<30,200000,1<<30,True),(errno.EPERM,30<<30,200000,1<<30,False),
          (errno.ESRCH,19<<30,200000,1<<30,False),(errno.ESRCH,30<<30,99999,1<<30,False),(errno.ESRCH,30<<30,200000,21<<30,False)):
            space=type('S',(),dict(f_bavail=free,f_frsize=1,f_favail=inodes))()
            with self.subTest(error=error,free=free,inodes=inodes,copy=copy),patch.object(q.subprocess,'check_output',return_value=raw),patch.object(q.ctypes,'CDLL',return_value=Libc(error)),patch.object(q.os,'statvfs',return_value=space):
                if passes: self.assertEqual(q.scratch(self.root if hasattr(self,'root') else '/home',copy)['kernel_Q_GETFMT']['errno'],errno.ESRCH)
                else:
                    with self.assertRaises(ValueError): q.scratch('/home',copy)


if __name__=='__main__': unittest.main()
