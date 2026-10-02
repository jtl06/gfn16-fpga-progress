"""Local Track S arithmetic tests; full AW12/AW16 transform gates run elsewhere."""
from pathlib import Path
from random import Random
import tempfile
import unittest
from fpga.reference import stream_ntt_model as m
from fpga.reference.carry_prefix_model import normalize as frozen_carry

ROOT=Path(__file__).resolve().parents[1]


class StreamingArithmeticTests(unittest.TestCase):
    def test_field_parameters_roots_and_crt_boundaries(self):
        self.assertEqual(m.MODULUS,487945222748036195811329)
        for n in (2,32,256,4096,65536):
            for p,g in m.FIELDS:
                psi=pow(g,(p-1)//(2*n),p)
                self.assertEqual(pow(psi,n,p),p-1)
        for x in (0,1,-1,m.HALF,-m.HALF):
            self.assertEqual(m.centered_crt([x%p for p,_ in m.FIELDS]),x)

    def test_dif_bit_reversed_output_against_direct_dft(self):
        n=32;aw=5;values=list(range(n))
        for p,g in m.FIELDS:
            omega=pow(g,(p-1)//n,p);actual=m.forward_dif(values,p,omega)
            natural=[sum(x*pow(omega,i*j,p) for i,x in enumerate(values))%p for j in range(n)]
            self.assertEqual(actual,[natural[m.bit_reverse(i,aw)] for i in range(n)])
            self.assertEqual(m.inverse_dit(actual,p,omega),values)

    def test_integer_negacyclic_coefficients_small_and_aw8(self):
        rng=Random(936)
        for n in (2,4,32,256):
            base=2*n+5;digits=[rng.randrange(base) for _ in range(n)]
            for bit in (0,1):
                self.assertEqual(m.square_coefficients(digits,double_bit=bit),m.direct_negacyclic_square(digits,bit))

    def test_exact_carry_matches_independent_existing_model_and_bigint(self):
        rng=Random(930)
        for n in (2,32,256):
            for base in (2*n+5,604832956,1_000_000_000):
                for digits in ([base-1]*n,[-1]+[0]*(n-1),[rng.randrange(base) for _ in range(n)]):
                    for bit in (0,1):
                        coefficients=m.direct_negacyclic_square(digits,bit)
                        actual=m.exact_carry(coefficients,base)
                        self.assertEqual(actual,frozen_carry(coefficients,base)[0])
                        self.assertEqual(actual,m.canonicalize(coefficients,base))
                        self.assertEqual(m.exact_square(digits,base,bit),actual)

    def test_scalar_transform_correction_identity_not_range_proof(self):
        digits=[(i*17)%97 for i in range(32)];c=-53
        for field in range(3):
            corrected=list(digits);corrected[0]+=c
            self.assertEqual(m.field_square(digits,field,correction=(c,)),m.field_square(corrected,field))

    def test_nonuniform_two_term_transform_correction(self):
        digits=[(i*19)%97 for i in range(32)];correction=(-83,7)
        for field in range(3):
            corrected=list(digits)
            for i,c in enumerate(correction):corrected[i]+=c
            self.assertEqual(m.field_square(digits,field,correction=correction),m.field_square(corrected,field))
            self.assertNotEqual(m.field_square(digits,field,correction=correction),m.field_square(digits,field,correction=(sum(correction),)))

    def test_lazy_scalar_small_safe_chain_and_canonicalization(self):
        base=97;digits=[96]*32;state=m.LazyState(tuple(digits),base)
        for bit in (0,1,1,0,1):
            expected=m.exact_square(digits,base,bit)
            state=m.lazy_square(state,bit)
            self.assertEqual(state.canonical(),expected)
            digits=expected

    def test_fullsize_scalar_profile_counterexample_no_full_ntt(self):
        result=m.all_max_counterexample()
        self.assertEqual(result['top_carry'],65535999934462)
        self.assertEqual(result['corrected_digit0'],-65534999999996)
        self.assertEqual(result['next_coefficient0'],4294836224999475720000000016)
        self.assertEqual(result['next_coefficient_bits'],92)
        self.assertTrue(result['range_failure'])
        self.assertNotEqual(result['crt_alias'],result['next_coefficient0'])
        self.assertEqual(result['split_correction'],(-999934462,-65535))
        # Headroom gate refuses the next transform, rather than silently
        # validating an already-aliased RNS value against itself.
        with self.assertRaises(m.CRTRangeError):
            m.square_coefficients([999999999]*65536,correction=(-65535999934462,))

    def test_two_term_proposal_analytic_invariant_not_profile_promotion(self):
        for aw in range(5,17):
            n=1<<aw
            for base in (2*n+5,2*n+6,604832956,1_000_000_000):
                proof=m.two_correction_proposal_bound(n,base)
                self.assertTrue(proof['closed']);self.assertTrue(proof['within_centered_crt'])
                self.assertLessEqual(proof['next_c1_abs_bound'],proof['c1_abs_max'])
                self.assertFalse(proof['hardware_timing_and_profile_qualification'])
        self.assertEqual(m.two_correction_proposal_bound(65536,10**9)['doubled_coefficient_bound'],131078000786646371404742)

    def test_required_mutants_typed_mismatch_with_fresh_controls(self):
        n=32;base=97;digits=[96]*n
        state=m.serial_lazy_carry(m.direct_negacyclic_square(digits),base)
        expected=m.exact_square(state.canonical(),base)
        for mutant in ('wrong-twiddle','missing-wrap','wrong-c-sign'):
            control=m.lazy_square(state).canonical();m.check_equal(control,expected,'control')
            changed=m.lazy_square(state,mutant=mutant).canonical()
            with self.assertRaises(m.ModelMismatch) as caught:m.check_equal(changed,expected,mutant)
            self.assertEqual(caught.exception.kind,mutant)

    def test_archived_aw5_first12_normal_transactions(self):
        path=ROOT/'results/throughput-20260929/core27-prefetch-r2-rootfused-aw5-v2/vectors-aw5.txt'
        for variant in ('exact','lazy-scalar'):
            result=m.verify_normal_vectors(path,variant,max_cases=12)
            self.assertEqual(result['cases'],12)
            self.assertEqual(result['status'],'passed_arithmetic_only')

    def test_parser_rejects_unknown_and_no_empty_success(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'vectors.txt';path.write_text('32\nBADBASE 0\n')
            with self.assertRaises(ValueError):m.verify_normal_vectors(path)
            path.write_text('32\nUNKNOWN 0\n')
            with self.assertRaises(ValueError):list(m.normal_cases(path))
        with self.assertRaises(ValueError):m.verify_normal_vectors('unused',max_cases=0)


if __name__=='__main__':unittest.main()
