"""Bounded R6 wrap instrumentation and old-proposal closure tests."""
import unittest
from fpga.reference import stream27_context_storage_combo_oneshot_wrap as w


class OneShotWrapTests(unittest.TestCase):
    def test_monitor_reverse_and_unchanged_nonhost_math(self):
        original, oldfiles, production = w.normal.role('aw8')
        for old in (False, True):
            m, files, _ = w.role(old)
            host = 'rtl/' + production['top'] + '.sv'
            self.assertEqual(len(m['build']['sv_sources']), 55)
            for path in original['build']['sv_sources']:
                if path != host:
                    self.assertEqual(files[path], oldfiles[path])
            self.assertTrue(m['oneshot_wrap']['host_literal_reverse'])
            self.assertEqual(m['build']['parameters'], original['build']['parameters'])
            self.assertTrue(all(m['sources'][name]==pin for name,pin in
                                m['rtl_readiness']['source_snapshot'].items()))

    def test_timestamp_only_and_real_oracle_publication(self):
        m, files, _ = w.role()
        cpp = files[w.CPP].decode()
        self.assertEqual(cpp.count('d.cycles='), 1)
        self.assertIn('(k<<32)+uint64_t(d.probe_anchor)+SECOND_CORRECTION-1', cpp)
        self.assertIn('R6_ACTUAL_TABLE_FULL_OWNER', cpp)
        self.assertIn('R6_EXTERNAL_ACCEPT_NOT_INTERNAL_FEEDBACK', cpp)
        self.assertIn('run(d,false)', cpp)
        self.assertIn('R6_NEWJOB_CLEARS_SENT_PENDING', cpp)
        self.assertIn('R6_RESET_CLEARS_SENT_PENDING', cpp)
        self.assertEqual(cpp.count('(round_index&&age<FIRST[ctx])?COUNTS[ctx]:'), 2)
        self.assertIn('S4_HOST_CONTEXT_SIGNED96_VALUE', cpp)
        self.assertIn('S4_HOST_CONTEXT_ACTUAL_FULL_CHAINS', cpp)
        self.assertIn('S4_HOST_CONTEXT_DONE_READY_ATOMIC', cpp)
        self.assertEqual(m['steps'][0]['expected_stdout'].count('S4_HOST_CONTEXTS_PASS '), 3)

    def test_old_mutant_is_exact_proposal_only(self):
        _, files, _ = w.role(True)
        host = files['rtl/' + w.TOP + '.sv'].decode()
        self.assertIn(w.core.PROPOSAL_BEFORE, host)
        self.assertNotIn(w.core.PROPOSAL_AFTER, host)
        self.assertIn('second_correction_pending<=0', host)
        self.assertIn(w.MONITOR, host)
        self.assertNotIn('always', w.MONITOR)
        self.assertIn('R6_OLD_PROPOSAL_ACTUAL_ABORT', files[w.CPP].decode())


if __name__ == '__main__':
    unittest.main()
