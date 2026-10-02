import copy
import json
import unittest

from fpga.reference import stream27_p16_two_context_full_native as native
from fpga.reference import stream27_p16_two_context_crosstalk as fault


class FullContextNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.files = native.role()

    def test_exact_production_readonly_observer_and_independent_profiles(self):
        m, files = self.manifest, self.files
        self.assertEqual(len(m['build']['sv_sources']), 54)
        self.assertEqual(m['build']['parameters']['CONTEXTS'], 2)
        self.assertEqual(m['build']['parameters']['EPOCH_SEED0'], 65534)
        self.assertEqual(m['build']['parameters']['EPOCH_SEED1'], 42)
        observation = m['r84']['native_observer']
        self.assertEqual(observation['production_root_sha256'], native.ROOT_PIN)
        self.assertEqual(observation['added_edges'], 0)
        self.assertFalse(observation['source_selection_or_arithmetic_changed'])
        for name, pin in m['r84']['production_generated_sha256'].items():
            self.assertEqual(native.sha(files['rtl/' + name]), pin)
        wrapper = files['rtl/' + native.TOP + '.sv'].decode()
        self.assertIn('candidate (.*)', wrapper)
        for forbidden in ('always ', 'always_ff', 'always_comb', 'initial '):
            self.assertNotIn(forbidden, wrapper)
        self.assertIn('candidate.engine.arithmetic.profile_reciprocal[1]', wrapper)
        self.assertNotEqual(native.BASES[0], native.BASES[1])
        self.assertEqual(m['test_role'], 'normal')
        self.assertFalse(m['r84']['full_N_numeric_locally_performed'])
        self.assertIn('not a distinct CONTEXTS1 DUT', m['r84']['comparison'])
        for token in (b'R84_FULL_CONTEXT_ALONE_BIT_IDENTITY', b'R84_FULL_SIGNED96_REFERENCE',
                      b'R84_PER_CONTEXT_PROFILE_SNAPSHOT', b'R84_ACTUAL_PEER_OVERLAP',
                      b'R84_REAL_CANONICAL_COPY_COST'):
            self.assertIn(token, files[native.CPP])
        self.assertEqual(m['steps'][0]['argv'], ['{exe}'])

    def test_distinct_base_reciprocal_and_coefficient_bounds_without_ntt(self):
        n, p = 65536, 16
        product = 104857601 * 69206017 * 67239937
        reciprocals = []
        for base in native.BASES:
            reciprocal = (1 << 96) // base
            reciprocals.append(reciprocal)
            self.assertLessEqual(reciprocal * base, 1 << 96)
            self.assertGreater((reciprocal + 1) * base, 1 << 96)
            b, k = base - 1, 2 * n + 24 * p
            limit = 2 * ((n + 3 * p) * b * b + 4 * p * b * k + p * k * k)
            self.assertLess(limit, product // 2)
            self.assertLess(limit, 1 << 77)
        self.assertNotEqual(*reciprocals)

    def test_repaired_aw8_uses_same_small_normal_and_five_exact_net_rewrites(self):
        m,files=native.small_role()
        self.assertEqual(m['build']['parameters']['AW'],8)
        self.assertEqual(m['build']['parameters']['EXPLICIT_NET_DECLARATIONS'],1)
        self.assertEqual(len(m['build']['sv_sources']),53)
        self.assertEqual(len(m['r84_explicit_small']['explicit_net_declarations']['changes']),5)
        self.assertTrue(m['r84_explicit_small']['explicit_net_declarations']['public_edges_unchanged'])
        self.assertFalse(m['r84_explicit_small']['old_source_native_PASS_inherited'])
        self.assertIn('counts=3/14 chains=2 squares=17 reads=1024',m['steps'][0]['expected_stdout'])
        self.assertEqual(m['test_role'],'normal')

    @staticmethod
    def footer():
        return dict(aw=16, p=16, contexts=2, bases=native.BASES, squares=8, reads=6*65536,
                    signed96=True, context_alone_bit_identical=True, independent_reference=True,
                    interval=8459, pair_launch_cycles=8459, peer_live_reads=65536, model_threads=1,
                    launches=[[204, 8663], [4433, 12892]], single_cycles=[743000, 743100],
                    joint_cycles=1400000, overlap_edges=21221, done_edges=[677000, 1333000],
                    warm_edges=[21221, 25450], setup_edges=[99, 199], single_first=[104, 104],
                    seconds=300.0)

    def test_typed_normal_and_wrong_profile_calendar_output_rejections(self):
        def check(v):
            return native.validate('R84_C2_FULL_PASS '+json.dumps(v)+'\n', '', 0, native.config(), {})
        self.assertEqual(check(self.footer())['status'], 'PASS_expected_contracts')
        for name, value in [('bases', [native.BASES[0]]*2), ('interval', 8460),
                            ('pair_launch_cycles', 4230), ('peer_live_reads', 65535),
                            ('signed96', False), ('model_threads', 8),
                            ('launches', [[204, 8664], [4433, 12892]]),
                            ('warm_edges', [21220, 25450]), ('setup_edges', [205, 199]),
                            ('done_edges', [655360, 1333000])]:
            v = copy.deepcopy(self.footer()); v[name] = value
            with self.subTest(name=name), self.assertRaises(ValueError):
                check(v)
        with self.assertRaises(ValueError):
            native.validate('R84_C2_FULL_PASS '+json.dumps(self.footer())+'\n', 'unexpected', 0, native.config(), {})

    def test_separate_output_word_mutant_preserves_production_and_full_peer(self):
        m, files = fault.role()
        for name, pin in m['r84']['production_generated_sha256'].items():
            self.assertEqual(fault.sha(files['rtl/' + name]), pin)
        wrapper = files['rtl/' + fault.TOP + '.sv'].decode()
        self.assertIn('candidate (.read_data(native_read_data), .*);', wrapper)
        self.assertIn("native_read_data ^ 96'd1", wrapper)
        self.assertNotIn('always', wrapper)
        self.assertEqual(m['test_role'], 'deliberate_fault')
        self.assertIn(b'for(unsigned address=0;address<N;address++)', files[fault.CPP])
        self.assertIn(b'R84_CROSSTALK_EXACT_TYPED_MISMATCH', files[fault.CPP])
        self.assertIn(b'R84_CROSSTALK_PEER_POST_REJECTION', files[fault.CPP])
        v = dict(aw=16,p=16,contexts=2,bases=native.BASES,squares=4,peer_verified_words=65536,
                 mutated_context=0,mutated_address=17,typed_mismatches=1,signed96=True,
                 peer_bit_identical=True,metadata_unchanged=True,native_output_word_only=True,
                 model_threads=1,seconds=200.0)
        def check(v):
            return fault.validate('R84_C2_CROSSTALK_PASS '+json.dumps(v)+'\n','',0,fault.config(),{})
        self.assertEqual(check(v)['status'], 'PASS_expected_contracts')
        for key, value in [('peer_verified_words',65535),('typed_mismatches',0),('peer_bit_identical',False),
                           ('mutated_context',1),('metadata_unchanged',False)]:
            bad=copy.deepcopy(v);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):check(bad)


if __name__ == '__main__':
    unittest.main()
