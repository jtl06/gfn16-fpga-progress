"""SYNTHETIC timing fixtures only; these tests never generate fit evidence."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from synthesis.compare_integrated import compare
from synthesis.prepare import prepare
from tests import test_integrated_performance27 as base_fixture
from tests import test_integrated_performance27_stream as stream_fixture
from tests import test_integrated_performance27_folded as folded_fixture


class IntegratedComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.paths = [Path(self.temp.name)/n for n in ("baseline", "candidate")]
        fixtures = [base_fixture.Atomic27PerformanceTests().fixture(),
                    stream_fixture.Stream27PerformanceTests().fixture()]
        self.probes, self.reports = [], []
        for path,(probe,report,_) in zip(self.paths,fixtures):
            manifest = prepare(path,probe['manifest']['target'],aw=16,period=10)
            probe['manifest'] = manifest
            report['sources'] = {'rtl/kernel/'+k:v for k,v in manifest['source_sha256'].items()}
            (path/'output_files').mkdir()
            (path/'output_files/probe.fit.summary').write_text('Quartus Prime Version : SYNTHETIC-TEST-ONLY\n')
            self.probes.append(probe); self.reports.append(report)

    def run_compare(self,old_clock=80,new_clock=100):
        with patch('synthesis.compare_integrated.read_probe',side_effect=self.probes):
            return compare(*self.paths,*self.reports,old_clock,new_clock)

    def test_profile_difference_is_validated_and_ratio_includes_cycles(self):
        for row in self.reports[1]['metrics']:
            if row.get('n')==65536:
                row['cycles']-=100;row['carry']-=100
        result=self.run_compare()
        self.assertGreater(result['projected_cached_chain_speedup'],1.25)
        self.assertEqual(result['planning_clock_ratio'],1.25)
        self.assertEqual(result['phase_deltas']['full-random-s1-d1']['carry'],-100)
        self.assertIn('genefer_square_core27_stream.sv',result['changed_rtl'])
        self.assertIn('not_hardware',result['status'])

    def test_no_fit_borrowed_clock_and_running_gate_rejected(self):
        with self.assertRaisesRegex(ValueError,'Fmax'):self.run_compare(new_clock=150)
        self.probes[1]['fit_success']=False
        with self.assertRaisesRegex(ValueError,'completed fit'):self.run_compare()
        self.probes[1]['fit_success']=True;self.reports[1]['status']='running'
        with self.assertRaisesRegex(ValueError,'passed simulation'):self.run_compare()

    def test_profile_cannot_be_relabelled(self):
        self.reports[1]['configuration']['precision_carry']=False
        with self.assertRaisesRegex(ValueError,'architecture/profile'):self.run_compare()

    def test_folded_routing_profile_accepted_without_borrowing_stream_contract(self):
        probe,report,_=folded_fixture.Folded27PerformanceTests().fixture()
        path=Path(self.temp.name)/'folded'
        manifest=prepare(path,probe['manifest']['target'],aw=16,period=10)
        probe['manifest']=manifest
        report['sources']={'rtl/kernel/'+k:v for k,v in manifest['source_sha256'].items()}
        (path/'output_files').mkdir()
        (path/'output_files/probe.fit.summary').write_text('Quartus Prime Version : SYNTHETIC-TEST-ONLY\n')
        self.paths[1]=path;self.probes[1]=probe;self.reports[1]=report
        self.assertAlmostEqual(self.run_compare()['projected_cached_chain_speedup'],1.25)
        report['configuration']['stream_carry']=True
        with self.assertRaisesRegex(ValueError,'architecture/profile'):self.run_compare()

    def test_constraint_and_worker_mismatch_rejected(self):
        qsf=self.paths[1]/'probe.qsf';original=qsf.read_text()
        qsf.write_text(original.replace('SEED 1','SEED 2'))
        with self.assertRaisesRegex(ValueError,'physical control'):self.run_compare()
        qsf.write_text(original)
        m=self.probes[1]['manifest'];m['compile_processors']=4
        (self.paths[1]/'manifest.json').write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError,'compile_processors'):self.run_compare()

    def test_same_cases_and_cache_states_required(self):
        saved=copy.deepcopy(self.reports[1])
        self.reports[1]['metrics']=[r for r in saved['metrics'] if r['case']!='full-random-s4-d1']
        with self.assertRaisesRegex(ValueError,'case selection'):self.run_compare()
        self.reports[1]=saved
        for row in saved['metrics']:
            if row['case']=='full-random-s4-d1':row['cache_before']=7
        with self.assertRaisesRegex(ValueError,'case metadata'):self.run_compare()

    def test_changed_snapshot_and_unknown_core_rejected(self):
        source=next((self.paths[1]/'rtl').glob('*.sv'))
        content=source.read_bytes();source.write_bytes(content+b'\n// tamper\n')
        with self.assertRaisesRegex(ValueError,'snapshot source mismatch'):self.run_compare()
        source.write_bytes(content)
        m=self.probes[1]['manifest'];m['target']='future_unvalidated_core'
        (self.paths[1]/'manifest.json').write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError,'supported atomic27'):self.run_compare()
