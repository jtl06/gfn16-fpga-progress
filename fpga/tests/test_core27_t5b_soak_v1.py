"""T5b lineage/host-loop/scalar tests only; no HDL or full-N arithmetic."""
from pathlib import Path
import unittest

from fpga.reference import core27_crtmont_soak_v1 as old
from fpga.reference import core27_t5b_soak_v1 as t5b


class PromotedSoakTests(unittest.TestCase):
    def test_accepted_parent_has_exact_sixteen_sources(self):
        order, pins = t5b.parent_sources()
        self.assertEqual(len(order), 16)
        self.assertEqual(pins['rtl/kernel/'+t5b.TOP+'.sv'], t5b.CORE_SHA)
        self.assertEqual(pins['rtl/kernel/genefer_carry_prefix_stream_precision_emit.sv'],
            'ac01093c075b8bb0f7c5493b18623209164e42659a92a0310893aee086619c3a')

    def test_old_evidence_cannot_be_relabeled(self):
        ref = t5b.reference()
        before = old.make_plan(5,4,2,2,20261001,69)
        after = ref.make_plan(5,4,2,2,20261001,69)
        self.assertEqual(after['lineage'], 'promoted-t5b')
        self.assertEqual(after['parent_manifest_sha256'], t5b.FIT_SHA)
        self.assertNotEqual(before['case_id'], after['case_id'])
        with self.assertRaisesRegex(ValueError, 'EXACT_PLAN_IDENTITY'):
            ref.check_plan(before)

    def test_independent_scalar_arithmetic_is_unchanged(self):
        ref = t5b.reference()
        before = old.make_plan(5,4,2,2,20261001,69)
        after = ref.make_plan(5,4,2,2,20261001,69)
        a, _ = old.compute_states(before,'python-small-only',4,[0,2,4])
        b, _ = ref.compute_states(after,'python-small-only',4,[0,2,4])
        self.assertEqual(a,b)
        self.assertEqual(before['double_bits'],after['double_bits'])

    def test_cpp_driver_is_only_model_name_successor(self):
        baseline = (t5b.ROOT/old.BENCH).read_text().splitlines()[1:]
        successor = (t5b.ROOT/'rtl/tb/core27_t5b_soak_v1.cpp').read_text().splitlines()[1:]
        self.assertEqual(successor,[line.replace(old.TOP,t5b.TOP) for line in baseline])
        self.assertEqual(t5b.sha(t5b.ROOT/t5b.BASE),t5b.BASE_SHA)


if __name__ == '__main__':
    unittest.main()
