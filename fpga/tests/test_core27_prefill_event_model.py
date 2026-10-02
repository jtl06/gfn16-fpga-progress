import unittest
from fpga.reference.core27_prefill_event_model import Prefill, PrefillFault, native_gate_plan


class PrefillEvents(unittest.TestCase):
    def complete(self, aw=5):
        m = Prefill(aw, 604832956)
        for a in range(0, m.n, m.step):
            m.edge((a, m.mask, [(-1 if a == 0 and i == 0 else a+i) for i in range(m.step)]))
        m.edge(carry_done=True)
        for _ in range(5): m.edge()
        self.assertTrue(m.eligible)
        self.assertFalse(m.busy)
        self.assertEqual(m.written, m.n)
        return m

    def test_edge_identity(self):
        m = self.complete()
        self.assertEqual([x[0] for x in m.writes], [5, 6])
        self.assertEqual(m.writes[0][2][0][0], 104857600)

    def test_small_partial_lane_masks(self):
        for aw in range(1, 6): self.complete(aw)

    def test_same_base_and_double_share_eligibility(self):
        m = self.complete()
        self.assertTrue(m.start(m.base))
        self.assertFalse(m.eligible)

    def test_changed_base_falls_back(self):
        m = self.complete()
        self.assertFalse(m.start(10**9))

    def test_host_load_invalidates(self):
        m = self.complete(); m.load()
        self.assertFalse(m.start(m.base))

    def test_busy_load_ignored(self):
        m = Prefill(5, 10**9); m.load()
        self.assertTrue(m.busy)

    def test_profile_incoherence_disables_fast_start(self):
        m = self.complete()
        self.assertFalse(m.start(m.base, coherent=False))

    def test_each_tail_reset_cancels(self):
        for age in range(7):
            m = Prefill(4, 10**9)
            if age:
                m.edge((0, m.mask, [1]*m.step))
                for i in range(1, age): m.edge(carry_done=i == 1)
            m.reset()
            for _ in range(8): m.edge()
            self.assertFalse(m.eligible)
            self.assertFalse(m.tokens)

    def test_each_tail_error_blocks_eligibility(self):
        for age in range(7):
            m = Prefill(4, 10**9)
            if age:
                m.edge((0, m.mask, [1]*m.step))
                for i in range(1, age): m.edge(carry_done=i == 1)
            with self.assertRaisesRegex(PrefillFault, "T5_LATE_HOST"):
                m.edge(host_error=True)
            self.assertFalse(m.eligible)

    def test_bad_emission_address_mask_digit(self):
        for event, tag in [((16, 65535, [1]*16), "ADDRESS"),
                           ((0, 1, [1]*16), "MASK"),
                           ((0, 65535, [10**9]*16), "DIGIT")]:
            with self.assertRaisesRegex(PrefillFault, tag): Prefill(5, 10**9).edge(event)

    def test_missing_emission_count(self):
        with self.assertRaisesRegex(PrefillFault, "EMIT_COUNT"):
            Prefill(5, 10**9).edge(carry_done=True)

    def test_write_mutants(self):
        for kwargs, tag in [({"address_delta": 16}, "WRITE_ADDRESS"),
                            ({"field_masks": [65535, 1, 65535]}, "FIELD_MASK"),
                            ({"drop_write": True}, "WRITE_COUNT")]:
            m = Prefill(4, 10**9); m.edge((0, m.mask, [1]*16))
            m.edge(carry_done=True)
            for _ in range(3): m.edge()
            with self.assertRaisesRegex(PrefillFault, tag): m.edge(**kwargs)

    def test_gate_plan_not_a_claim(self):
        self.assertEqual(native_gate_plan()["status"], "source_proposal_not_executed")
        self.assertEqual(len(native_gate_plan()["mutants"]), 6)


if __name__ == "__main__": unittest.main()
