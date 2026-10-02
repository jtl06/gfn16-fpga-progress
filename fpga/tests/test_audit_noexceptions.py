"""Exact P8 no-exception constraint-scope derivative; no native execution."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import test_audit_plain_fit_timing_v1 as fixtures

ROOT = Path(__file__).resolve().parents[1]
def load(path):
    spec=importlib.util.spec_from_file_location('noexceptions',ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
h=load('tools/audit_plain_fit_timing_noexceptions_v1.py')
a=load('cloud/plain_fit_audit_noexceptions_v1.py')

class ConstraintTests(unittest.TestCase):
    def test_only_three_exact_helper_predicates_changed(self):
        expected=(ROOT/'tools/audit_plain_fit_timing_v1.py').read_text()
        for old,new in [("need(len(lines) == 3,","need(len(lines) == 2,"),
          ("['derive_clock_uncertainty','set_false_path -from [get_ports {rst_n}]']","['derive_clock_uncertainty']"),
          ("['set_time_format -unit ns -decimal_places 3','set_false_path -from [get_ports {rst_n}]']","['set_time_format -unit ns -decimal_places 3']")]:
            self.assertEqual(expected.count(old),1);expected=expected.replace(old,new)
        self.assertEqual(expected+'\n',(ROOT/'tools/audit_plain_fit_timing_noexceptions_v1.py').read_text())

    def test_source_p8_and_forbidden_reset_exception(self):
        source=(ROOT/'artifacts/s4-p8-whole-host-aw16-source-v1/project/probe.sdc').read_text()
        h.source_sdc(source,'10.000')
        for extra in ['set_false_path -from [get_ports {rst_n}]\n','set_false_path -to [all_registers]\n','source extra.sdc\n']:
            with self.assertRaises(ValueError):h.source_sdc(source+extra,'10.000')
        with self.assertRaises(ValueError):h.source_sdc(source,'14.120')

    def test_actual_baseline_and_exact_effective_constraints(self):
        path=ROOT/'queue/fit-recovery-controller-aws50-v16/terminal/p8-whole-host-10000-aws6/evidence/project/output_files/probe.sta.rpt'
        baseline=h.baseline_summary(path.read_text(),'10.000')
        self.assertEqual(baseline['setup']['slack_ns'],-4.110)
        effective=fixtures.effective('10.000').replace('set_false_path -from [get_ports {rst_n}]\n','')
        self.assertEqual(h.effective_sdc(effective,'10.000'),['set_time_format -unit ns -decimal_places 3'])
        with self.assertRaises(ValueError):h.effective_sdc(fixtures.effective('10.000'),'10.000')

    def test_all_four_corners_baseline_and_selected_remain_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            spec,baseline,log=fixtures.fixture(root,negative_baseline=True,selected='14.120',measured_recovery=True)
            for path in root.glob('*effective.sdc'):
                path.write_text(path.read_text().replace('set_false_path -from [get_ports {rst_n}]\n',''))
            parsed=h.parse_results(root,log,spec,baseline)
            self.assertEqual(len(parsed['baseline']['corners']),4)
            self.assertEqual(len(parsed['selected']['corners']),4)
            self.assertFalse(parsed['baseline']['timing_closes'])
            self.assertTrue(parsed['selected']['timing_closes'])
            with self.assertRaises(ValueError):h.parse_results(root,log.replace(h.MARK+'\tCOMPLETE',''),spec,baseline)

    def test_adapter_only_exact_helper_and_filename_binding_changes(self):
        expected=(ROOT/'cloud/plain_fit_audit_v2.py').read_text().replace('plain_fit_audit_v2.py','plain_fit_audit_noexceptions_v1.py').replace(
          "AUDIT='audit_plain_fit_timing_v1.py'; AUDIT_SHA='655a0a7c088189c5c49ebd19cd48beab2fba2111f1adc30ddee8c8b450fbc355'",
          "AUDIT='audit_plain_fit_timing_noexceptions_v1.py'; AUDIT_SHA='549041beeeb991f22d04a985bf040ed82393d48c737ce76d5eed90b3a11102b4'")
        self.assertEqual(expected+'\n',(ROOT/'cloud/plain_fit_audit_noexceptions_v1.py').read_text())
        self.assertEqual(a.sha(ROOT/'tools'/a.AUDIT),a.AUDIT_SHA)
        self.assertEqual((a.INNER,a.RUNTIME,a.GRACE,a.HORIZON),(2100,2220,60,2280))

    def test_collectors_only_change_exact_adapter_and_host_slot_bindings(self):
        expected=(ROOT/'tools/collect_plain_fit_audit_v2.py').read_text().replace('plain_fit_audit_v2.py','plain_fit_audit_noexceptions_v1.py').replace(
            '3b8418404165b14ab83b6edae5c2609e6f72271caad12c05cace64b85f250ada','dc2bf465823e04ad54d122d894b992944c8d8bc13687bfb9ff7e59f48ead0bd1')
        self.assertEqual(expected+'\n',(ROOT/'tools/collect_plain_fit_audit_noexceptions_v1.py').read_text())
        for old,new in [
            ("root=Path(ad.HOSTS[ad.FIT]['root'])","root=Path(ad.HOSTS[ad.AWS]['root'])"),
            ("request['host']==ad.FIT and request['slot']=='c','delegated F16C audit collection only'","request['host']==ad.AWS and request['slot']=='b','delegated AWSB audit collection only'"),
            ("ad.topology(ad.FIT,'c')","ad.topology(ad.AWS,'b')"),
            ("ad.lock_names(ad.FIT,'c',physical)","ad.lock_names(ad.AWS,'b',physical)"),
            ("context['slot']=='c'","context['slot']=='b'")]:
            self.assertEqual(expected.count(old),1);expected=expected.replace(old,new)
        self.assertEqual(expected+'\n',(ROOT/'tools/collect_plain_fit_audit_noexceptions_awsb_v1.py').read_text())

    def test_large_report_collection_changes_only_finite_byte_bound(self):
        for stem in ('collect_plain_fit_audit_noexceptions','collect_plain_fit_audit_noexceptions_awsb'):
            old=(ROOT/('tools/'+stem+'_v1.py')).read_text()
            self.assertEqual(old.count('<=512<<20'),1)
            self.assertEqual(old.replace('<=512<<20','<=3<<30').rstrip()+'\n',
                (ROOT/('tools/'+stem+'_large_v1.py')).read_text())

if __name__=='__main__':unittest.main()
