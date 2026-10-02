"""Pure actual report attribution; no native run or RTL mutation."""
from decimal import Decimal as D
import unittest
from fpga.reference import stream27_r91_overhead_attribution as r
from fpga.reference.stream27_c2_place_resource_diagnosis import parse


class AttributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.a=r.analyze()

    def test_actual_whole_reports_and_denominators(self):
        a=self.a['cohorts']
        self.assertEqual(a['C1_timing7']['whole']['registers'],605823)
        self.assertEqual(a['C2_compact']['whole']['registers'],613726)
        self.assertEqual(a['C1_timing7']['stage'],'final FIT')
        self.assertEqual(a['C2_compact']['stage'],'PLACE only')

    def test_disjoint_closure_without_hiding_report_residual(self):
        for cohort in self.a['cohorts'].values():
            for metric in r.FIELDS:
                total=sum(g['metrics'][metric] for g in cohort['buckets'].values())
                self.assertEqual(total+cohort['attribution_residual'][metric],cohort['whole'][metric])
        self.assertEqual(self.a['cohorts']['C1_timing7']['attribution_residual']['registers'],2)
        self.assertEqual(self.a['cohorts']['C2_compact']['attribution_residual']['registers'],0)

    def test_tag_instances_not_quoted120_and_no_observer(self):
        for c in self.a['cohorts'].values():
            evidence=c['special_evidence']
            self.assertEqual(evidence['actual_tag_delay_instances'],144)
            self.assertEqual(evidence['total_tag_delay_M20K'],72)
            self.assertEqual(evidence['synthesized_observer_modules'],0)
            self.assertFalse(evidence['dictionary_ALM_FF_separately_resolved'])
            self.assertTrue(evidence['embedded_metric_port_increment_unknown'])

    def test_mixed_dictionaries_not_called_removable_metadata(self):
        c=self.a['cohorts']['C2_compact']
        mixed=c['buckets']['mixed_shells']['reported_rows']
        self.assertEqual(sum(x['entity']=='genefer_stream27_mdc_commutator_tagcompact_v1' for x in mixed),72)
        self.assertEqual(c['buckets']['metadata_named']['metrics']['registers'],1892)
        self.assertGreater(c['buckets']['mixed_shells']['metrics']['registers'],120000)

    def test_cold_fronts_stay_mixed_and_required_numeric_BF_stays_datapath(self):
        for name,cohort in r.COHORTS.items():
            n=parse((r.ROOT/cohort['project']/'output_files'/cohort['report']).read_text())
            for node in n.values():
                if node['entity']=='genefer_digit_reduce27_pipe':
                    self.assertEqual(r.classify(node,n),'mixed_shells')
                if node['entity'].startswith('genefer_ntt_lazy28_butterfly_v1'):
                    self.assertEqual(r.classify(node,n),'other_datapath')

    def test_A_B_hold_and_no_new_job_or_rules(self):
        p=self.a['policy']
        self.assertEqual(p['A_lean_production'],'HOLD_PENDING_DIRECT_HUMAN_APPROVAL')
        self.assertEqual(p['B_host_offload'],'HOLD_PENDING_DIRECT_HUMAN_APPROVAL')
        self.assertTrue(p['RTL_fault_rules_record_boundary_hosts_unchanged'])


if __name__=='__main__':unittest.main()
