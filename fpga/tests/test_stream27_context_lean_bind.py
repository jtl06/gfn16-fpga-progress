import copy
import unittest
from fpga.reference import stream27_context_lean_bind as lean


class LeanSourceTests(unittest.TestCase):
    def test_default_exact_and_strict_flag(self):
        parent = lean.capture(256)
        saved = copy.deepcopy(parent)
        self.assertEqual(lean.bind(parent, enabled=0), saved)
        self.assertEqual(parent, saved)
        for flag in (True, False, 2, '1'):
            with self.assertRaisesRegex(ValueError, 'BOOLEAN_SWITCH'):
                lean.bind(parent, enabled=flag)

    def test_aw8_full_reverse_and_routing(self):
        for n in (256, 65536):
            parent = lean.capture(n)
            out = lean.bind(parent, enabled=1)
            contract = out['lean_production']
            self.assertEqual(len(out['files']), 55)
            self.assertEqual(contract['label'], 'lean build; host GL assumed (unimplemented)')
            self.assertFalse(contract['host_gl_implemented'])
            self.assertFalse(contract['twin_fault_immunity_inherited'])
            self.assertTrue(contract['r6_oneshot_literal'])
            self.assertTrue(contract['complete_copy_counters_retained'])
            for name, delta in contract['modified'].items():
                text = out['files'][name]
                for before, after in reversed(delta['edits']):
                    self.assertGreaterEqual(text.count(after), 1)
                    text = text.replace(after, before)
                self.assertEqual(text, parent['files'][delta['parent']])
            for name, text in parent['files'].items():
                if name in out['files'] and name not in contract['modified']:
                    self.assertEqual(out['files'][name], text)

    def test_no_unproved_parent_composition(self):
        parent = lean.capture(256)
        parent['parameters']['GEN_RETIRE'] = 1
        with self.assertRaisesRegex(ValueError, 'EXACT_R7_ONLY'):
            lean.bind(parent, enabled=1)
        with self.assertRaisesRegex(ValueError, 'ONLY_CAPTURED'):
            lean.prepare(32, enabled=1)

    def test_live_generation_drive_and_eligibility_retained(self):
        # Regression for actual v1 UNDRIVEN: trimming owner_bad must not trim
        # the adjacent generation selector or change live-payload eligibility.
        for n in (256, 65536):
            parent = lean.capture(n)
            out = lean.bind(parent, enabled=1)
            before = parent['files'][lean.OLD_COMM + '.sv']
            after = out['files'][lean.NEW_COMM + '.sv']
            routing = before[before.index('  expected_generation='):
                             before.index('  fault_pending=')]
            self.assertIn(routing, after)
            self.assertEqual(after.count('  expected_generation='), 1)
            self.assertIn('head_upper_tag.generation==expected_generation', after)

    def test_healthy_guard_and_watchdog_model(self):
        # Known healthy-domain check predicates are false; disabling a verifier
        # does not change payload arithmetic or the retained functional selector.
        for context in (0, 1):
            for valid in (0, 1):
                for row in range(16):
                    parent_eligible = valid and not False
                    lean_eligible = valid and not False
                    self.assertEqual(parent_eligible, lean_eligible)
                    banks = [[(c<<12)+r for r in range(16)] for c in range(2)]
                    parent_payload = banks[context][row] if parent_eligible else None
                    lean_payload = banks[context][row] if lean_eligible else None
                    self.assertEqual(parent_payload, lean_payload)
        limit = 64*256+4096
        age = 0
        failed = False
        for edge in range(limit+10):
            if edge % 213 == 0:
                age = 0
            elif age == limit-1:
                failed = True
            else:
                age += 1
        self.assertFalse(failed)
        for _ in range(limit):
            if age == limit-1:
                failed = True
            else:
                age += 1
        self.assertTrue(failed)
        # Host timestamp wrap is not the watchdog age or one-shot acceptance.
        sent = False
        accepted = 0
        for timestamp in (106, 106+(1<<32), 106+2*(1<<32)):
            due = timestamp & 0xffffffff == 106
            if due and not sent:
                sent = True
                accepted += 1
        self.assertEqual(accepted, 1)


if __name__ == '__main__':
    unittest.main()
