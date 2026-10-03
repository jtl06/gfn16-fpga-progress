"""R15 GMP opt-in adapter proof; no compiler, HDL, GMP or cloud execution."""
import ast
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from fpga.tools import native_class_v2 as policy
from fpga.tools import native_class_package_v4 as package,native_package_v6 as stage

ROOT=Path(__file__).resolve().parents[1]


class GmpExistingNativeTests(unittest.TestCase):
    def setUp(self):
        self.selected=policy.profile('azure-f16-static1213-v1')
        self.raw=(ROOT/policy.GMP_INVENTORY).read_bytes()
        self.inventory=json.loads(self.raw)

    def synthetic_role(self):
        # Small metadata-only mutation fixture, never an admitted actual role.
        value=dict(build=dict(ldflags=['-lgmpxx','-lgmp'],top='T',parameters={},cflags=['-O2'],
                              sv_sources=['rtl/x.sv'],cpp_source='rtl/x.cpp'),
                   sources={policy.GMP_INVENTORY:policy.GMP_INVENTORY_SHA,'rtl/x.cpp':'1'*64,'rtl/x.sv':'2'*64},
                   probe=dict(argv=['{exe}','--thread-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
                   steps=[dict(name='normal',argv=['{exe}'],expected_stdout='PASS\n',expected_stderr='')])
        value['metadata']=dict(r15_native_gmp=dict(schema='r15-direct65-gmp-link-v1',
            inventory=dict(path=policy.GMP_INVENTORY,sha256=policy.GMP_INVENTORY_SHA),fixture_sha256=policy.role_identity(value)))
        return value

    def contract(self,role,selected=None,raw=None):
        return policy.gmp_link_contract(role,selected or self.selected,lambda name:self.raw if raw is None else raw)

    def test_defaults_do_not_add_dependency_or_linker_argv(self):
        self.assertIsNone(policy.gmp_link_contract(dict(build={}),{},lambda name:self.fail('default inventory read')))
        self.assertEqual(policy.gmp_ldflags(dict(build={}),{},None),[])
        self.assertNotIn(policy.GMP_INVENTORY,policy.PINS)
        captured=[];original=policy.policy.adapted_source
        def record(raw,selected):
            text=original(raw,selected);captured.append(text);return text
        with patch.object(policy.policy,'adapted_source',side_effect=record):policy.parent(self.selected['profile_id'])
        base=ast.parse(captured[0]);changed=[]
        original_compile=compile
        def capture_compile(source,*args,**kwargs):
            if isinstance(source,str) and '[R15-GMP-opt-in]' in str(args[0]):changed.append(source)
            return original_compile(source,*args,**kwargs)
        with patch('builtins.compile',side_effect=capture_compile):policy.parent(self.selected['profile_id'])
        def argv(tree,manifest=None,selected=None,config=None):
            execute=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='execute')
            assignment=next(n for n in ast.walk(execute) if isinstance(n,ast.Assign)
                            and any(isinstance(t,ast.Name) and t.id=='command' for t in n.targets)
                            and isinstance(n.value,ast.List) and len(n.value.elts)>5)
            env=dict(toolpaths={'verilator':Path('/observed/verilator')},
                config=config or dict(top='T',parameters={'AW':8},cflags=['-std=c++17','-Werror=return-type'],sv_sources=['rtl/a.sv'],cpp_source='rtl/a.cpp'),
                build=Path('/scratch/build'),root=ROOT,manifest=manifest or {'build':{}},profile=selected or {},gmp_ldflags=policy.gmp_ldflags)
            exec(original_compile(ast.fix_missing_locations(ast.Module(body=[assignment],type_ignores=[])),'[scalar argv only]','exec'),env)
            return env['command']
        self.assertEqual(argv(base),argv(ast.parse(changed[0])))
        role=self.synthetic_role()
        with patch.object(policy,'GMP_FIXTURES',(policy.role_identity(role),)):
            opt=argv(ast.parse(changed[0]),role,self.selected,role['build'])
        position=opt.index('-LDFLAGS');self.assertEqual(opt[position+1],'-lgmpxx -lgmp')
        self.assertEqual(opt.count('-LDFLAGS'),1);self.assertEqual(opt[opt.index('-j')+1],'2')
        self.assertEqual(opt[opt.index('--threads')+1],'1')
        guard=next(n for n in ast.walk(ast.parse(changed[0])) if isinstance(n,ast.FunctionDef) and n.name=='guard')
        self.assertEqual(guard.body[0].value.func.id,'gmp_runtime_guard')

    def test_only_exact_flags_and_known_fixture_data_are_admitted(self):
        role=self.synthetic_role();pin=role['metadata']['r15_native_gmp']['fixture_sha256']
        with patch.object(policy,'GMP_FIXTURES',(pin,)):
            self.assertEqual(self.contract(role),self.inventory)
            self.assertEqual(policy.gmp_ldflags(role,self.selected,ROOT),['-LDFLAGS','-lgmpxx -lgmp'])
            for flags in ([],['-lgmp'],['-lgmp','-lgmpxx'],['-lgmpxx','-lgmp','-lm'],
                          ['-lgmpxx -lgmp'],['-lgmpxx;touch /tmp/x','-lgmp'],('-lgmpxx','-lgmp'),None):
                bad=copy.deepcopy(role);bad['build']['ldflags']=flags
                with self.subTest(flags=flags),self.assertRaisesRegex(ValueError,'exact GMP linker'):
                    self.contract(bad)
            bad=copy.deepcopy(role);del bad['build']['ldflags']
            with self.assertRaisesRegex(ValueError,'requires explicit'):self.contract(bad)
            for key in ('build','probe','steps','sources'):
                bad=copy.deepcopy(role)
                if key=='build':bad[key]['top']='Different'
                elif key=='probe':bad[key]['argv']=['{exe}','different']
                elif key=='steps':bad[key][0]['expected_stdout']='WRONG\n'
                else:bad[key]['rtl/x.sv']='f'*64
                with self.subTest(key=key),self.assertRaisesRegex(ValueError,'source-pinned'):self.contract(bad)
            with self.assertRaisesRegex(ValueError,'inventory bytes'):self.contract(role,raw=self.raw+b' ')
        with self.assertRaisesRegex(ValueError,'source-pinned'):self.contract(role)

    def test_gmp_never_changes_host_threads_resources_or_probe(self):
        role=self.synthetic_role();pin=policy.role_identity(role)
        with patch.object(policy,'GMP_FIXTURES',(pin,)):
            for key,value in (('host','aethia'),('profile_id','gcp-c4d-static01-v1'),('model_threads',8),
                              ('compile_workers',4),('memory_bytes',16<<30),('cpu_quota_percent',800),('cpus',[0,1])):
                selected=copy.deepcopy(self.selected);selected[key]=value
                with self.subTest(key=key),self.assertRaisesRegex(ValueError,'resource contract'):self.contract(role,selected)
            selected=copy.deepcopy(self.selected);selected['hashes']['compiler']='0'*64
            with self.assertRaisesRegex(ValueError,'compiler identities'):self.contract(role,selected)
            bad=copy.deepcopy(role);bad['probe']['expected_json']['model_threads']=True
            with self.assertRaises(ValueError):self.contract(bad)

    def test_existing_source_identity_rejects_unbound_gmp_metadata(self):
        role=json.loads((ROOT/'results/throughput-20261003/r15-host-window-gmp-native-v1/normal/manifest.json').read_bytes())
        self.assertEqual(package.source_identity(role),policy.GMP_FIXTURES[0])
        bad=copy.deepcopy(role);bad['metadata']['r15_native_gmp']['fixture_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'source-pinned'):package.source_identity(bad)
        bad=copy.deepcopy(role);bad['build']['ldflags']=['-lgmpxx','-lgmp','-lm']
        with self.assertRaisesRegex(ValueError,'exact GMP'):package.source_identity(bad)
        bad=copy.deepcopy(role);bad['host']='gfn16-pilot-c4d'
        with self.assertRaisesRegex(ValueError,'AzureFIT'):package.source_identity(bad)
        bad=copy.deepcopy(role);bad['metadata']['r15_native_gmp']['library_path']='/tmp/evil'
        with self.assertRaisesRegex(ValueError,'source-pinned'):package.source_identity(bad)

    def test_runtime_guard_rechecks_exact_files_symlinks_and_refuses_drift(self):
        content=b'pinned library bytes';digest=hashlib.sha256(content).hexdigest();state={'sha':content,'uid':0,'mode':0o100644,'link':'library.so.1','resolved':'/usr/lib/library.so.1'}
        wanted=dict(resolved=state['resolved'],sha256=digest,bytes=len(content),uid=0,mode='0o644',symlink=state['link'])
        class FakePath:
            def __init__(self,name):self.name=name
            def resolve(self,strict=True):return FakePath(state['resolved'])
            def stat(self):return types.SimpleNamespace(st_mode=state['mode'],st_uid=state['uid'],st_size=len(state['sha']),
                st_dev=1,st_ino=2,st_mtime_ns=3)
            def is_symlink(self):return self.name=='/usr/lib/library.so'
            def open(self,*args):return io.BytesIO(state['sha'])
            def __str__(self):return self.name
            def __eq__(self,other):return self.name==other.name
        inventory={'files':{'/usr/lib/library.so':wanted}}
        with patch.object(policy,'Path',FakePath),patch.object(policy.os,'readlink',side_effect=lambda p:state['link']):
            policy.gmp_verify_files(inventory)
            for key,value in (('sha',b'drifted library bytes'),('uid',1000),('mode',0o100666),('link','evil.so'),('resolved','/tmp/evil.so')):
                before=state[key];state[key]=value
                with self.subTest(key=key),self.assertRaises(ValueError):policy.gmp_verify_files(inventory)
                state[key]=before
        role=self.synthetic_role()
        with patch.object(policy,'gmp_link_contract',return_value=self.inventory),patch.object(policy,'gmp_verify_files') as verify:
            policy.gmp_runtime_guard(role,self.selected,ROOT);policy.gmp_runtime_guard(role,self.selected,ROOT)
        self.assertEqual(verify.call_count,2)

    def test_existing_worker_refuses_library_drift_before_inherited_claim_path(self):
        role=self.synthetic_role();calls=[]
        dummy=types.SimpleNamespace(PINS={},load=lambda name:policy,
            prepare=lambda *args:calls.append('prepare'),run=lambda *args:calls.append('inherited-run'))
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary);role['source_root']=str(directory)
            role['budget_source_members']=dict(role['sources'])
            manifest=directory/'manifest.json';manifest.write_text(json.dumps(role))
            ticket=directory/'ticket.json';ticket.write_text(json.dumps(dict(native_root=str(directory),
                manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),profile=self.selected['profile_id'],tools={})))
            pin=hashlib.sha256(ticket.read_bytes()).hexdigest()
            with patch.object(package,'descriptor_binding'),patch.object(package.base,'worker',return_value=dummy):
                worker=package.worker({})
            def drift(*args):calls.append('library-guard');raise ValueError('library changed')
            with patch.object(policy,'gmp_runtime_guard',side_effect=drift):
                with self.assertRaisesRegex(ValueError,'library changed'):worker.run(ticket,pin)
            self.assertEqual(calls,['library-guard'])
            with patch.object(policy,'gmp_runtime_guard',side_effect=lambda *args:calls.append('library-guard')):
                worker.run(ticket,pin)
            self.assertEqual(calls,['library-guard','library-guard','inherited-run'])

    def test_real_frozen_direct65_normal_and_fault_prepare_and_dual_safe_stage(self):
        from fpga.tests.test_r15_f16_existing_native import R15ExistingF16Tests
        roles=ROOT/'results/throughput-20261003/r15-host-window-gmp-native-v1'
        with tempfile.TemporaryDirectory(prefix='r15-gmp-source-proof-',dir=ROOT/'artifacts') as temporary:
            out=Path(temporary).resolve()
            for index,mode in enumerate(('normal','faults')):
                path=roles/mode/'manifest.json';raw=path.read_bytes();role=json.loads(raw)
                self.assertEqual(package.source_identity(role),policy.GMP_FIXTURES[index])
                self.assertEqual(len(role['build']['sv_sources']),65)
                self.assertEqual(len(role['sources']),224)
                self.assertEqual(policy.gmp_link_contract(role,self.selected,
                    lambda name:(Path(role['source_root'])/name).read_bytes()),self.inventory)
                budget=R15ExistingF16Tests.fixture_budget(self,out,role)
                budgetpath=out/(mode+'-budget.json');budgetpath.write_text(json.dumps(budget))
                for selected in ('azure-f16-static1213-v1','azure-f16-static1415-v1'):
                    dest=out/(mode+'-'+selected)
                    prepared=package.prepare(path,Path(role['source_root']),selected,
                        'metadata-gmp-'+mode+'-'+selected,'run',dest,budgetpath)
                    payload,ticket,manifest,placement=stage.worker().inspect_archive(dest/'package.tar.gz',
                        prepared['archive_sha256'],prepared['ticket_sha256'])
                    self.assertEqual(manifest['build'],role['build']);self.assertEqual(manifest['steps'],role['steps'])
                    self.assertEqual(manifest['metadata'],role['metadata']);self.assertEqual(manifest['budget_source_members'],role['sources'])
                    self.assertEqual(ticket['max_seconds'],3700);self.assertEqual(placement['static_lanes'],2)
                    self.assertEqual(placement['memory_bytes'],8<<30);self.assertEqual(placement['compile_workers'],2)
                    self.assertEqual(placement['model_threads'],1);self.assertEqual(placement['scratch_floor_bytes'],20<<30)
                    self.assertEqual(payload['capture/source/fpga/'+policy.GMP_INVENTORY],self.raw)
                self.assertEqual(path.read_bytes(),raw)


if __name__=='__main__':unittest.main()
