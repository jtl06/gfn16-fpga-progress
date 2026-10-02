"""Source/report/ordinary-process tests; never invokes Quartus or cloud APIs."""
import copy
import inspect
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from cloud import aws_postfit_t5b100_m8azn_v1 as a
from tests.test_postfit_crtmont_a1_v1 import fixture,path_fixture

ARCHIVE=a.FPGA/'results/throughput-20260929/core27-t5b-provisional64-aws-fit-v1'


class T5bAuditTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name).resolve()

    def test_terminal_and_all_twelve_evidence(self):
        m=a.verify_terminal(ARCHIVE)
        self.assertEqual(len(m['source_sha256']),16)
        self.assertEqual(len(list((ARCHIVE/'evidence').iterdir())),12)
        self.assertEqual(a.sha(ARCHIVE/'independent-review-v1.json'),a.REVIEW_SHA)
        self.assertEqual(a.a1.raw_timing((ARCHIVE/'output_files/probe.sta.rpt').read_text())['setup']['slack_ns'],.334)

    def test_exact_tcl_derivative_fixed_clock_final_snapshot(self):
        raw=(a.FPGA/'synthesis/postfit_rootfused85_audit_v1.tcl').read_bytes()
        text=a.tcl_source(raw).decode()
        for token in (a.TOP,'$a1_mode ne "diagnosis" || $a1_period != 10',
                      '-snapshot final','set path_count 1000','project_close -dont_export_assignments','PREFLIGHT_COMPLETE'):
            self.assertIn(token,text)
        for token in ('execute_flow','quartus_fit','quartus_asm','project_open -force'):
            self.assertNotIn(token,text)
        with self.assertRaises(ValueError):a.tcl_source(raw+b'\n')

    def test_prepare_replay_and_no_overwrite(self):
        out=self.root/'packet';r=a.prepare(out)
        p=json.loads((out/'proposal.json').read_text())
        self.assertEqual((r['native_commands'],p['slot'],p['period_ns'],p['policy']['memory_max_bytes']),(0,'b','10',20<<30))
        self.assertEqual(len(p['pinned_files']),40)
        a.verify_terminal(ARCHIVE,p)
        with patch.object(a,'HERE',out):a.verify_proposal(out/'proposal.json',r['proposal_sha256'])
        before=a.base.inventory(out)
        with self.assertRaises(ValueError):a.prepare(out)
        self.assertEqual(a.base.inventory(out),before)
        for key in ('slot','period_ns','mode','maximum_copy_bytes'):
            bad=copy.deepcopy(p);bad[key]='invalid';(out/'proposal.json').write_text(json.dumps(bad))
            with patch.object(a,'HERE',out),self.assertRaises(ValueError):a.verify_proposal(out/'proposal.json',a.sha(out/'proposal.json'))

    def test_pin_closure_source_and_evidence_drift_rejected(self):
        out=self.root/'packet';a.prepare(out);p=json.loads((out/'proposal.json').read_text())
        bad=copy.deepcopy(p);bad['pinned_files'].pop('output_files/probe.sta.rpt')
        with self.assertRaisesRegex(ValueError,'pin closure'):a.verify_terminal(ARCHIVE,bad)
        project=self.root/'project';shutil.copytree(ARCHIVE,project)
        f=project/'evidence/parent-probe.sdc';original=f.read_bytes();f.write_bytes(original+b'\n')
        with self.assertRaises(ValueError):a.verify_terminal(project,p)
        f.write_bytes(original)
        f=next((project/'rtl').iterdir());f.write_bytes(f.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError,'RTL'):a.verify_terminal(project,p)

    def positive_fixture(self):
        p,log=fixture(self.root)
        for kind,slack in [('setup',.334),('hold',.017),('mpw',4.337)]:
            p['baseline100'][kind]['slack_ns']=slack
            for path in self.root.glob('*-'+kind+'-summary.rpt'):path.write_text(f'; kernel_clk ; {slack} ; 0 ; 0 ;\n')
        for path in self.root.glob('*-setup-paths.rpt'):path.write_text(path_fixture(.334))
        for path in self.root.glob('*-effective.sdc'):path.write_text('set_time_format -unit ns -decimal_places 3\n'+path.read_text())
        return p,log

    def test_four_corner_replay_positive_and_worst_path_collection(self):
        p,log=self.positive_fixture();r=a.a1.parse_results(self.root,log,p);a.check_timing(r,self.root)
        self.assertEqual(len(r['baseline100']),4)
        self.assertEqual(r['path_groups']['baseline100']['observed_paths'],8)
        self.assertEqual(r['path_groups']['baseline100']['observed_failing_paths'],0)
        self.assertNotIn('supported_audit_clock',r)

    def test_negative_setup_hold_mpw_recovery_removal_rejected(self):
        p,log=self.positive_fixture();r=a.a1.parse_results(self.root,log,p)
        for kind in ('setup','hold','mpw','recovery','removal'):
            bad=copy.deepcopy(r);row=next(iter(bad['baseline100'].values()))
            row[kind]=dict(status='measured',slack_ns=-.001,tns_ns=-.001,failing_endpoints=1)
            with self.assertRaises(ValueError):a.check_timing(bad,self.root)
        path=next(self.root.glob('*-effective.sdc'));path.write_text(path.read_text()+'set_false_path -to [all_registers]\n')
        with self.assertRaises(ValueError):a.check_timing(r,self.root)

    def test_missing_corner_and_changed_baseline_rejected(self):
        p,log=self.positive_fixture()
        with self.assertRaises(ValueError):a.a1.parse_results(self.root,log.replace('\tBEGIN\tbaseline100\t3','\tBEGIN\tbaseline100\t2'),p)
        p['baseline100']['setup']['slack_ns']=.3355
        with self.assertRaisesRegex(ValueError,'native replay'):a.a1.parse_results(self.root,log,p)

    def test_copy_preserved_and_unreviewed_mutation_fails(self):
        original=self.root/'original';original.mkdir();(original/'probe.qsf').write_text('frozen')
        before=a.base.inventory(original);dest=self.root/'copy';a.base.snapshot(original,dest,before)
        (dest/'probe.qsf').write_text('mutated');receipt={}
        with self.assertRaisesRegex(ValueError,'unreviewed'):a.base.record_snapshot_check(receipt,original,dest,before)
        self.assertEqual(a.base.inventory(original),before)
        self.assertEqual(receipt['snapshot_differences']['probe.qsf']['allowed'],False)

    def test_bound_policy_and_slot_guard(self):
        with self.assertRaisesRegex(ValueError,'slotB'):a.inner_launch('unused','a',self.root/'topology')
        text=inspect.getsource(a.launch)+inspect.getsource(a.inner_launch)
        for token in ("policy.launch(OUTPUT,'b',topology)",'policy.live_limits()',"policy.slot_locks(document,slot,selected['physical_cores'])",'range(6,12)','policy.validate_topology','signal.SIGTERM','base.record_snapshot_check'):
            self.assertIn(token,text)
        self.assertNotIn('quartus_fit',text);self.assertNotIn('quartus_asm',text)

    def test_timeout_and_nonzero_keep_logs_no_overwrite(self):
        log=self.root/'timeout.log'
        with self.assertRaises(subprocess.TimeoutExpired):
            a.run([sys.executable,'-B','-c','import time;print("preserved",flush=True);time.sleep(10)'],self.root,log,.2)
        self.assertEqual(log.read_text(),'preserved\n')
        with self.assertRaises(FileExistsError):a.run([sys.executable,'-V'],self.root,log,1)
        failed=self.root/'failed.log'
        with self.assertRaisesRegex(ValueError,'native command failed 7'):
            a.run([sys.executable,'-B','-c','print("failure");raise SystemExit(7)'],self.root,failed,2)
        self.assertEqual(failed.read_text(),'failure\n')


if __name__=='__main__':unittest.main()
