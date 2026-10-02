import unittest

from fpga.reference.s4_waiting_final_contract import ContractError, Owner, WaitingFinal


class WaitingFinalContractTests(unittest.TestCase):
    def begin(self, model, context, epoch=0):
        tag = Owner(context, 1, epoch, epoch + 9)
        model.begin(tag, 1009 + context * 2, [context] * model.p, [epoch] * model.p)
        return tag

    def capture(self, model, tag):
        expected = [tag.context * 256 + x for x in range(model.n)]
        for row in range(model.rows):
            model.capture(tag, row, [expected[b * model.rows + row]
                                     for b in range(model.p)])
        return expected

    def load(self, model, tag, expected):
        model.acquire_scratch(tag)
        for row in range(model.rows):
            self.assertEqual(model.load_row(tag, row),
                             tuple(expected[b * model.rows + row] for b in range(model.p)))
        model.canonical_ready(tag)

    def finish(self, model, tag):
        # Supplied canonical words test transport only, not normalization math.
        expected = [-1] + [tag.context] * (model.n - 1)
        for address, word in enumerate(expected):
            model.commit(tag, address, word)
        model.publish(tag)
        self.assertEqual([model.host_read(tag, x) for x in range(model.n)], expected)

    def test_other_context_captures_while_scratch_busy(self):
        for n in (32, 256):
            for p in (8, 16):
                m = WaitingFinal(n, p)
                a, b = self.begin(m, 0), self.begin(m, 1)
                self.load(m, a, self.capture(m, a))
                raw_b = self.capture(m, b)
                with self.assertRaisesRegex(ContractError, 'SCRATCH_BUSY'):
                    m.acquire_scratch(b)
                with self.assertRaisesRegex(ContractError, 'PHASE'):
                    m.host_read(b, 0)
                self.finish(m, a)
                self.load(m, b, raw_b)
                self.finish(m, b)
                self.assertEqual(m.host_read(a, 1), 0)
                self.assertEqual(m.host_read(b, 1), 1)

    def test_stale_generation_epoch_ordinal_and_context_rejected(self):
        m = WaitingFinal()
        a = self.begin(m, 0)
        for bad in (Owner(0, 2, 0, 9), Owner(0, 1, 1, 9),
                    Owner(0, 1, 0, 10), Owner(1, 1, 0, 9)):
            with self.assertRaisesRegex(ContractError, 'STALE_OWNER'):
                m.capture(bad, 0, [3] * 8)
        self.assertEqual(m.memory[0], [None] * 32)

    def test_partial_capture_load_and_copy_cannot_publish(self):
        m = WaitingFinal()
        a = self.begin(m, 0)
        with self.assertRaisesRegex(ContractError, 'PHASE'):
            m.acquire_scratch(a)
        raw = self.capture(m, a)
        m.acquire_scratch(a)
        with self.assertRaisesRegex(ContractError, 'PHASE'):
            m.canonical_ready(a)
        for row in range(m.rows):
            m.load_row(a, row)
        m.canonical_ready(a)
        for addr in range(m.n - 1):
            m.commit(a, addr, raw[addr])
        with self.assertRaisesRegex(ContractError, 'INCOMPLETE_PUBLICATION'):
            m.publish(a)
        with self.assertRaisesRegex(ContractError, 'PHASE'):
            m.host_read(a, 0)

    def test_bad_row_and_commit_do_not_advance(self):
        m = WaitingFinal()
        a = self.begin(m, 0)
        for row, words, code in ((1, [0] * 8, 'ROW_ORDER'),
                                  (0, [0], 'ROW_WIDTH'),
                                  (0, [1009] * 8, 'RAW_DIGIT_RANGE')):
            with self.assertRaisesRegex(ContractError, code):
                m.capture(a, row, words)
        self.load(m, a, self.capture(m, a))
        with self.assertRaisesRegex(ContractError, 'COPY_ORDER'):
            m.commit(a, 1, 0)
        with self.assertRaisesRegex(ContractError, 'SIGNED32'):
            m.commit(a, 0, 2**31)
        self.finish(m, a)

    def test_cancel_holds_bank_and_scratch_until_drain(self):
        m = WaitingFinal()
        a, b = self.begin(m, 0), self.begin(m, 1)
        self.load(m, a, self.capture(m, a))
        raw_b = self.capture(m, b)
        m.cancel(a)
        with self.assertRaisesRegex(ContractError, 'PHASE'):
            m.commit(a, 0, 0)
        with self.assertRaisesRegex(ContractError, 'SCRATCH_BUSY'):
            m.acquire_scratch(b)
        with self.assertRaisesRegex(ContractError, 'CONTEXT_BUSY'):
            self.begin(m, 0, 1)
        m.drained(a)
        self.load(m, b, raw_b)
        self.finish(m, b)
        self.begin(m, 0, 1)

    def test_reset_retains_data_but_revokes_all_eligibility(self):
        m = WaitingFinal()
        a = self.begin(m, 0)
        self.load(m, a, self.capture(m, a))
        self.finish(m, a)
        saved = tuple(m.memory[0])
        m.reset()
        self.assertEqual(tuple(m.memory[0]), saved)
        with self.assertRaisesRegex(ContractError, 'STALE_OWNER'):
            m.host_read(a, 0)
        with self.assertRaisesRegex(ContractError, 'RESET_DRAIN_REQUIRED'):
            self.begin(m, 1)
        m.reset_drained()
        with self.assertRaisesRegex(ContractError, 'TAG_REUSE'):
            self.begin(m, 0)
        self.begin(m, 0, 1)

    def test_capture_other_bank_interleaves_scalar_copy_and_metadata_is_frozen(self):
        m = WaitingFinal()
        a = self.begin(m, 0)
        b = Owner(1, 2, 4, 15)
        c0, c1 = [7] * 8, [-3] * 8
        m.begin(b, 1013, c0, c1)
        c0[0], c1[0] = 99, 99
        self.load(m, a, self.capture(m, a))
        for addr in range(m.n):
            if addr < m.rows:
                m.capture(b, addr, [b * m.rows + addr + 40 for b in range(m.p)])
            m.commit(a, addr, -1 if addr == 0 else 0)
        m.publish(a)
        self.assertEqual(m.acquire_scratch(b), (1013, (7,) * 8, (-3,) * 8))
        for row in range(m.rows):
            self.assertEqual(m.load_row(b, row),
                             tuple(block * m.rows + row + 40 for block in range(m.p)))
        m.canonical_ready(b)
        self.finish(m, b)
        self.assertEqual(m.host_read(a, 0), -1)

    def test_shared_fault_aborts_both_contexts(self):
        m = WaitingFinal()
        a, b = self.begin(m, 0), self.begin(m, 1)
        self.load(m, a, self.capture(m, a))
        self.capture(m, b)
        m.abort_all()
        for owner in (a, b):
            with self.assertRaisesRegex(ContractError, 'STALE_OWNER'):
                m.host_read(owner, 0)
            with self.assertRaisesRegex(ContractError, 'STALE_OWNER'):
                m.commit(owner, 0, 0)
        with self.assertRaisesRegex(ContractError, 'RESET_DRAIN_REQUIRED'):
            self.begin(m, 0, 1)


if __name__ == '__main__':
    unittest.main()
