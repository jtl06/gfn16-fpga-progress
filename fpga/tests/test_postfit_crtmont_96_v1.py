"""9.6ns adapter guards and report fixtures only; no native/cloud commands."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from cloud import aws_postfit_crtmont_96_v1 as a
from tests.test_postfit_crtmont_a1_v1 import fixture

FPGA=Path(__file__).resolve().parents[1]
STAGE=FPGA/'results/throughput-20260929/crtmont-96-tools-stage-v1'


class Clock96Tests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name).resolve()

    def timing_fixture(self):
        p,log=fixture(self.root,'selected_clock')
        p['period_ns']='9.6'
        log=log.replace('11.764','9.6').replace('5.882','4.8')
        for f in self.root.glob('selected_clock-*'):
            f.write_text(f.read_text().replace('11.764','9.6'))
        return p,log

    def test_source_derivative_fails_closed(self):
        raw=(FPGA/'cloud/aws_postfit_crtmont_a1_v1.py').read_bytes()
        text=a.adapted_source(raw)
        for expected in ("slot=='b'", "selected['affinity']==[4,5,6,7]", 'max_copy_bytes<=(1<<30)',
                         'promotion_allowed=False', 'original project mutated', "base.run(command,out,out/'audit.log',1800)"):
            self.assertIn(expected,text)
        with self.assertRaisesRegex(ValueError,'source identity'):a.adapted_source(raw+b'\n')

    def test_tcl_preserves_native_help_final_db_and_exclusions(self):
        text=a.runner.tcl_source((FPGA/'synthesis/postfit_rootfused85_audit_v1.tcl').read_bytes()).decode()
        for expected in ('($a1_period != 9.6 && $a1_period != 10)', '-snapshot final',
                         'set_false_path -from [get_ports {rst_n}]','project_close -dont_export_assignments',
                         'Expected four supported corners','HELP_BEGIN','PREFLIGHT_COMPLETE'):
            self.assertIn(expected,text)
        for forbidden in ('execute_module','execute_flow','project_open -force','quartus_fit'):
            self.assertNotIn(forbidden,text)
        self.assertEqual(text,(STAGE/'postfit_crtmont_96_v1.tcl').read_text())

    def test_only_exact_periods_admitted(self):
        self.assertEqual(a.runner.period_value('9.6'),9.6)
        self.assertEqual(a.runner.period_value('10'),10)
        for value in ('9.5','9.7','10.1','nan','1e1','9.6;exit',None):
            with self.assertRaises(ValueError):a.runner.period_value(value)

    def test_positive_96_fixture_still_requires_replay(self):
        p,log=self.timing_fixture();result=a.runner.parse_results(self.root,log,p)
        self.assertNotIn('supported_audit_clock',result)
        self.assertEqual(result['candidate_audit_clock_pending_replay']['period_ns'],9.6)
        self.assertEqual(len(result['selected_clock']),4)

    def test_negative_setup_hold_pulse_rejected(self):
        p,log=self.timing_fixture()
        for kind in ('setup','hold','mpw'):
            f=self.root/f'selected_clock-0-{kind}-summary.rpt';saved=f.read_text()
            f.write_text('; kernel_clk ; -.001 ; -1 ; 1 ;\n')
            with self.assertRaisesRegex(ValueError,'timing failure '+kind):a.runner.parse_results(self.root,log,p)
            f.write_text(saved)

    def test_clock_or_corner_change_rejected(self):
        p,log=self.timing_fixture()
        for bad in (log.replace('\t9.6\t0\t4.8','\t9.5\t0\t4.75'),
                    log.replace('\tBEGIN\tselected_clock\t3','\tBEGIN\tselected_clock\t2')):
            with self.assertRaises(ValueError):a.runner.parse_results(self.root,bad,p)

    def test_exclusion_change_rejected(self):
        p,log=self.timing_fixture();f=self.root/'selected_clock-0-effective.sdc'
        f.write_text(f.read_text()+'set_false_path -to [all_registers]\n')
        with self.assertRaises(ValueError):a.runner.parse_results(self.root,log,p)

    def test_terminal_proposal_inventory_and_promotion_lock(self):
        p=json.loads((STAGE/'proposal.json').read_text());a.verify_proposal(p)
        a.runner.verified_terminal((FPGA/'results/throughput-20260929/core27-rootfused-crtmont64-aws-fit-v1').resolve(),p,require_db=False)
        receipt=json.loads((STAGE/'preparation.json').read_text())
        self.assertEqual(len(receipt['inventory']),7)
        for name,row in receipt['inventory'].items():
            self.assertEqual(a.digest((STAGE/name).read_bytes()),row['sha256'])
        for key,value in [('promotion_allowed',True),('period_ns','10'),('maximum_copy_bytes',2<<30),('adapter_sha256','0'*64)]:
            bad=copy.deepcopy(p);bad[key]=value
            with self.assertRaises(ValueError):a.verify_proposal(bad)

    def test_slot_and_copy_ceiling_rejected_without_dispatch(self):
        p=STAGE/'proposal.json';pin=a.digest(p.read_bytes())
        with patch.object(a.runner,'launch') as launch:
            for slot,ceiling in [('a',1<<30),('b',(1<<30)+1),('b',0)]:
                with self.assertRaises(ValueError):a.launch(slot,self.root/'topology','crtmont-96-test',p,pin,ceiling)
            launch.assert_not_called()


if __name__=='__main__':unittest.main()
