"""Pure source/packaging guards; no HDL compiler or cloud calls."""
import ast
import copy
from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fpga.tools import native_shared_v1 as s
from fpga.tools import native_package_v1 as p


class SharedNativeTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name).resolve()
        self.source=self.root/'fpga';self.source.mkdir()
        self.budget=dict(provider='gcp',observed_at=datetime.now(timezone.utc).isoformat(),total_allowance_usd=100,
            planning_usd_per_hour=1,remaining_after_reserves_usd=50,actual_billing=False,source_receipt_sha256='a'*64)
        self.budget_path=self.root/'budget.json';self.budget_path.write_text(json.dumps(self.budget))
        (self.source/'unit.sv').write_text('module unit; endmodule\n');(self.source/'bench.cpp').write_text('int main(){return 0;}\n')
        self.m=dict(schema='native-source-gate-v1',status='prepared_not_executed',host='oldhost',source_root='/old/fpga',output_parent='/old/output',
            sources={x.name:s.sha(x) for x in self.source.iterdir()},build=dict(top='unit',sv_sources=['unit.sv'],cpp_source='bench.cpp',parameters={},cflags=['-std=c++17','-Werror=return-type']),
            probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
            steps=[dict(name='control',argv=['{exe}'],expected_returncode=0,expected_stdout='PASS\n',expected_stderr='')])
        self.manifest=self.root/'manifest.json';self.manifest.write_text(json.dumps(self.m))

    def prepare(self,out=None):return p.prepare(self.manifest,self.source,'gcp-c4d-sim01-v1','tiny-smoke','run',out or self.root/'packet',self.budget_path)

    def test_package_snapshot_and_build_identity(self):
        result=self.prepare();out=self.root/'packet';m=json.loads((out/'manifest.json').read_text())
        self.assertEqual(result['status'],'prepared_not_executed');self.assertEqual(result['files'],13)
        self.assertEqual(m['host'],'gfn16-pilot-c4d');self.assertEqual(m['phase'],'run')
        self.assertEqual(m['sources']['unit.sv'],self.m['sources']['unit.sv'])
        self.assertEqual(m['sources'][s.SELF],s.sha(s.HERE/'native_shared_v1.py'))
        snapshot=p.load('snapshot_native_sources_v2.py');snapshot.closed_inputs(out/'capture/source/fpga',m['sources'])
        before={str(x.relative_to(out)):s.sha(x) for x in out.rglob('*') if x.is_file()}
        with self.assertRaises(ValueError):self.prepare()
        self.assertEqual(before,{str(x.relative_to(out)):s.sha(x) for x in out.rglob('*') if x.is_file()})

    def test_source_drift_and_unclosed_files_reject_before_output(self):
        (self.source/'unit.sv').write_text('changed')
        with self.assertRaises(ValueError):self.prepare()
        self.assertFalse((self.root/'packet').exists())

    def test_bad_profile_id_and_untyped_contract(self):
        with self.assertRaises(ValueError):p.prepare(self.manifest,self.source,'gcp-c4d-sim04-v1','tiny','run',self.root/'bad',self.budget_path)
        self.m['steps'][0].pop('expected_stderr');self.manifest.write_text(json.dumps(self.m))
        with self.assertRaisesRegex(ValueError,'output contract'):self.prepare()
        self.assertFalse((self.root/'packet').exists())

    def test_budget_stale_future_insufficient_wrong_provider(self):
        p.budget_check(self.budget)
        for delta in [dict(observed_at=(datetime.now(timezone.utc)-timedelta(hours=7)).isoformat()),
                      dict(observed_at=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()),
                      dict(remaining_after_reserves_usd=0),dict(provider='aws'),dict(total_allowance_usd=101),dict(actual_billing=True)]:
            with self.assertRaises(ValueError):p.budget_check(self.budget|delta)

    def test_lint_clean_and_unadmitted_warning(self):
        profile=s.PROFILES['gcp-c4d-sim01-v1']
        self.assertEqual(s.admit_lint(0,b'',b'',self.m,profile,self.source)['status'],'clean_warning_fatal_lint')
        for code,err in [(1,b'%Warning-WIDTH: bad\n'),(0,b'%Warning-WIDTH: bad\n'),(2,b'%Error: fail\n')]:
            with self.assertRaises(ValueError):s.admit_lint(code,b'',err,self.m,profile,self.source)

    def test_exact_reviewed_debt_and_new_site_role_or_tool_rejection(self):
        profile=s.PROFILES['gcp-c4d-sim01-v1'];raw=f'%Warning-UNUSEDSIGNAL: {self.source}/unit.sv:1:2: example\n%Error: Exiting due to 1 warning(s)\n'.encode()
        baseline=dict(schema='native-exact-lint-baseline-v1',identity=s.lint_identity(self.m,profile),normalized_stderr_sha256=hashlib.sha256(s.normalize(raw,self.source)).hexdigest(),warning_count=1)
        folder=self.source/'lint-baseline';folder.mkdir();(folder/'baseline.json').write_text(json.dumps(baseline))
        (folder/'review.json').write_text(json.dumps(dict(status='PASS_EXACT_LINT_DEBT',baseline_sha256=s.sha(folder/'baseline.json'))))
        self.m['sources'].update({str(x.relative_to(self.source)):s.sha(x) for x in folder.iterdir()})
        self.m['lint_baseline']=dict(baseline='lint-baseline/baseline.json',review='lint-baseline/review.json')
        result=s.admit_lint(1,b'',raw,self.m,profile,self.source);self.assertIn('NOT_clean_lint',result['status'])
        for err in (raw.replace(b':1:2',b':2:2'),raw+b'%Warning-NEW: another\n',b'',raw.replace(b'UNUSEDSIGNAL',b'UNOPTFLAT'),raw.replace(b'UNUSEDSIGNAL',b'WIDTH'),raw+b'%Error: native failure\n'):
            with self.assertRaises(ValueError):s.admit_lint(1,b'',err,self.m,profile,self.source)
        changed=copy.deepcopy(self.m);changed['build']['parameters']['AW']=16
        with self.assertRaises(ValueError):s.admit_lint(1,b'',raw,changed,profile,self.source)
        changed=copy.deepcopy(profile);changed['hashes']['verilator']='a'*64
        with self.assertRaises(ValueError):s.admit_lint(1,b'',raw,self.m,changed,self.source)

    def test_closed_validator_values_and_drift(self):
        (self.source/'validator.py').write_text('def validate(out,err,code,config,assets):\n    assert out == assets["expected"] and err == "" and code == 0\n    return {"checks":config["checks"]}\n')
        (self.source/'expected.txt').write_text('PASS\n')
        for name in ('validator.py','expected.txt'):self.m['sources'][name]=s.sha(self.source/name)
        step=dict(validator=dict(source='validator.py',function='validate',config=dict(checks=7),assets=dict(expected='expected.txt')))
        self.assertEqual(s.validate_output(step,'PASS\n','',0,self.source,self.m),{'checks':7})
        with self.assertRaises(AssertionError):s.validate_output(step,'WRONG','',0,self.source,self.m)
        (self.source/'expected.txt').write_text('changed')
        with self.assertRaisesRegex(ValueError,'closure'):s.validate_output(step,'PASS\n','',0,self.source,self.m)

    def test_exact_adapter_retains_lint_before_build_and_lock(self):
        raw=(s.HERE/s.PARENT).read_bytes();text=s.adapted_source(raw,8*s.GIB);ast.parse(text)
        self.assertIn("'--lint-only', '-Wall'",text);self.assertNotIn('-Wno',text)
        self.assertLess(text.index("run('lint', lint)"),text.index("run('build', command)"))
        self.assertIn('fcntl.LOCK_EX | fcntl.LOCK_NB',text);self.assertIn('pass_fds=LEASE_FDS',text)
        self.assertIn("if manifest.get('phase') == 'lint':",text)
        with self.assertRaises(ValueError):s.adapted_source(raw+b'\n',8*s.GIB)

    def test_sibling_pairs_separate_and_offhost_rejected(self):
        left=s.PROFILES['gcp-c4d-sim01-v1'];right=s.PROFILES['gcp-c4d-sim23-v1']
        self.assertFalse(set(map(tuple,[left['topology'][str(x)] for x in left['cpus']])) & set(map(tuple,[right['topology'][str(x)] for x in right['cpus']])))
        with patch.object(s.socket,'gethostname',return_value='Mac'),self.assertRaisesRegex(ValueError,'host'):s.execution_limits(left)

    def test_locks_fail_closed_and_preserve_lockfile(self):
        path=self.root/'core.lock'
        with s.lock(path):
            with self.assertRaises(BlockingIOError):
                with s.lock(path):pass
        self.assertTrue(path.is_file())
        with s.lock(path,True),s.lock(path,True):pass


if __name__=='__main__':unittest.main()
