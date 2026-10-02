import json
import unittest
from fpga.reference import stream27_host_chain_fit_context_v1 as candidate
from fpga.tools import plain_fit_queue_v3 as queue


class FullNativePhysicalSourceJoin(unittest.TestCase):
    def test_closed_actual49_source_configuration(self):
        context = json.loads((candidate.ROOT / 'results/throughput-20260929/s4-p8-whole-host-fit-source-context-v1/source-context.json').read_text())
        descriptor = json.loads((candidate.ROOT / 'results/throughput-20260929/s4-p8-whole-host-fit-source-context-v1/variant-aws6.json').read_text())
        self.assertEqual(queue.source_variant('gfn16-aws-m8i', descriptor), context['project_context'])
        owner = json.loads(candidate.OWNER.read_text())
        self.assertEqual(owner['standalone_generated_sha256'], context['project_context']['source_sha256'])
        self.assertEqual(context['project_context']['qsf_parameters'],
            dict(AW=16, P=8, CONTEXTS=1, EPOCH_SEED=65534))
        self.assertEqual(context['standalone_rtl'], 49)
        self.assertFalse(context['field_sizing_exemption'])
        self.assertFalse(context['fit_allowed'])

    def test_actual_cycle_assertions_reconcile_without_invented_split(self):
        phase = json.loads(candidate.PHASE.read_text())
        jobs = phase['direct_native_program_assertions']
        self.assertEqual([job['host_done_age'] for job in jobs], [483707, 600179])
        self.assertEqual(sum(job['host_done_age'] for job in jobs), 1083886)
        for job in jobs:
            self.assertEqual(job['canonical_cycles'], 6 * 65536)
            self.assertEqual(job['image_copy_cycles'], 65536 + 3)
            self.assertEqual(job['host_done_age'], job['warm_done_age'] +
                job['canonical_cycles'] + job['image_copy_cycles'] + 2)
        self.assertEqual(jobs[1]['warm_done_age'] - jobs[0]['warm_done_age'], 7 * 16653 - 99)
        self.assertEqual(phase['direct_native_schedule_assertions']['warm_descriptor_spacing'], 16653)

    def test_direct_and_source_event_provenance_remain_distinct(self):
        phase = json.loads(candidate.PHASE.read_text())
        for job in phase['direct_native_program_assertions']:
            self.assertNotIn('canonical_begin_age', job)
            self.assertNotIn('ntt_cycles', job)
            self.assertNotIn('carry_cycles', job)
        self.assertEqual(len(phase['source_event_ledger_not_separate_native_trace']), 2)
        self.assertFalse(phase['full_N_numeric_locally_performed'])
        self.assertFalse(phase['native_repeated'])


if __name__ == '__main__':
    unittest.main()
