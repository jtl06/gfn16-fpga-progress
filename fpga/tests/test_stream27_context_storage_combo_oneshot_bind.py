import copy
import unittest

from fpga.reference import stream27_context_storage_combo_oneshot_bind as oneshot


class ColdSecondOneShotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parents = {n: oneshot.prepare(n) for n in (256, 65536)}
        cls.candidates = {n: oneshot.prepare(n, enabled=1) for n in cls.parents}

    def test_default_and_source_guards(self):
        for parent in self.parents.values():
            self.assertEqual(oneshot.bind(parent), parent)
            self.assertIsNot(oneshot.bind(parent)['files'], parent['files'])
        for flag in (True, -1, 2):
            with self.assertRaises(ValueError):
                oneshot.prepare(256, enabled=flag)
        mutated = copy.deepcopy(self.parents[256])
        mutated['files'][mutated['top']+'.sv'] += '// mutation\n'
        with self.assertRaisesRegex(ValueError, 'EXACT_R5_ONLY'):
            oneshot.bind(mutated, enabled=1)

    def test_every_host_byte_and_all_other_files_reverse(self):
        for n, candidate in self.candidates.items():
            parent = self.parents[n]
            self.assertEqual(len(candidate['files']), 55)
            self.assertEqual(oneshot.reverse_host(candidate['files'][candidate['top']+'.sv'],
                top=candidate['top'], parent_top=parent['top']), parent['files'][parent['top']+'.sv'])
            for name, text in parent['files'].items():
                if name != parent['top']+'.sv':
                    self.assertEqual(candidate['files'][name], text)
            self.assertEqual(candidate['geometry'], parent['geometry'])
            self.assertEqual(candidate['two_context_schedule'], parent['two_context_schedule'])
            self.assertEqual(candidate['parameters'], dict(parent['parameters'], COLD_SECOND_ONESHOT=1))
            self.assertEqual(candidate['generated_sha256'], {name: oneshot.sha(text)
                for name, text in candidate['files'].items()})

    def test_old_alias_and_fixed_retirement_across_three_wraps(self):
        for second in (106, 8232, 8233):
            proof = oneshot.prove_wraps(second)
            self.assertEqual(len(proof['old_alias_edges']), 4)
            self.assertEqual(proof['fixed_accepted_edges'], proof['old_alias_edges'][:1])
            for edge in proof['old_alias_edges']:
                self.assertTrue(oneshot.proposal(edge, 204, second, fixed=False))
            self.assertTrue(proof['missed_accept_retained'])

    def test_accepted_legal_trace_has_no_calendar_delta(self):
        for second in (106, 8232):
            sent = pending = False
            old_edges, new_edges = [], []
            for cycle in range(204+second+100):
                old = oneshot.proposal(cycle, 204, second, fixed=False, anchor_valid=cycle>204)
                new = oneshot.proposal(cycle, 204, second, sent=sent, pending=pending,
                                       anchor_valid=cycle>204)
                if old: old_edges.append(cycle)
                if new: new_edges.append(cycle)
                sent, pending = oneshot.step(sent, pending, proposed=new, accepted=new)
            self.assertEqual(old_edges, new_edges)

    def test_error_does_not_acknowledge_and_single_context_never_offers(self):
        self.assertEqual(oneshot.step(False, False, proposed=True, accepted=True, error=True),
                         (False, False))
        for edge in (310, 8436, 2**32+8436):
            self.assertFalse(oneshot.proposal(edge, 204, 8232, peer_job=False))
        # New job clear remains exact even when an old pending proposal exists.
        self.assertEqual(oneshot.step(False, True, proposed=False, accepted=False, newjob=True),
                         (False, False))


if __name__ == '__main__':
    unittest.main()
