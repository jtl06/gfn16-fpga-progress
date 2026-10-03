import copy
import unittest

from fpga.reference import stream27_context_storage_combo_directbound_bind as direct


class DirectSignedBoundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parents = {n: direct.prepare(n) for n in (256, 65536)}
        cls.candidates = {n: direct.prepare(n, enabled=1) for n in cls.parents}

    def test_default_exact_deepcopy_and_guards(self):
        for parent in self.parents.values():
            self.assertEqual(direct.bind(parent), parent)
            self.assertIsNot(direct.bind(parent)['files'], parent['files'])
        for flag in (True, -1, 2):
            with self.assertRaises(ValueError):
                direct.prepare(256, enabled=flag)
        bad = copy.deepcopy(self.parents[256])
        bad['files'][direct.OLD+'.sv'] += '// drift\n'
        with self.assertRaisesRegex(ValueError, 'EXACT_R7_ONLY'):
            direct.bind(bad, enabled=1)

    def test_only_leaf_and_host_change_reverse_exact(self):
        for n, candidate in self.candidates.items():
            parent = self.parents[n]
            self.assertEqual(len(candidate['files']), 55)
            self.assertEqual(direct.reverse_leaf(candidate['files'][direct.NEW+'.sv']),
                             parent['files'][direct.OLD+'.sv'])
            self.assertEqual(direct.reverse_host(candidate['files'][candidate['top']+'.sv'],
                top=candidate['top'], parent_top=parent['top']), parent['files'][parent['top']+'.sv'])
            for name, text in parent['files'].items():
                if name not in (direct.OLD+'.sv', parent['top']+'.sv'):
                    self.assertEqual(candidate['files'][name], text)
            self.assertEqual(candidate['geometry'], parent['geometry'])
            self.assertEqual(candidate['two_context_schedule'], parent['two_context_schedule'])
            self.assertEqual(candidate['parameters'], dict(parent['parameters'], CANONICAL_C0_DIRECT=1))
            self.assertEqual(candidate['generated_sha256'], {name: direct.sha(text)
                for name, text in candidate['files'].items()})

    def test_signed_widening_and_all_authority_literal(self):
        for candidate in self.candidates.values():
            leaf = candidate['files'][direct.NEW+'.sv']
            self.assertEqual(leaf.count("direct_base_c0=$signed({1'b0,base});"), 1)
            self.assertEqual(leaf.count('logic signed [32:0] direct_base_c0,input_c0,input_c1;'), 1)
            self.assertNotIn('bound_c0', leaf)
            for anchor in ("input_c0=$signed({c0[b*32+31],c0[b*32+:32]});",
                           "input_c1>33'(K) || input_c1< -33'(K))correction_bad=1;",
                           'wire legal_begin=rst_n && state==IDLE && !error && !idle_reject && begin_canonical;',
                           'base_reg<=base;address<=0;pass_index<=0;carry<=0;',
                           'if(legal_begin)begin'):
                self.assertEqual(leaf.count(anchor), 1)
            proof = candidate['context_storage_combo_directbound']['model']
            self.assertTrue(proof['base0_always_correction_bad'])
            self.assertEqual(proof['random_full_width_cases'], 200000)
            self.assertEqual(candidate['context_storage_combo_directbound']['calendar_delta'], 0)


if __name__ == '__main__':
    unittest.main()
