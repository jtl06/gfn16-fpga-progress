"""PurePython wrap2 arithmetic and transaction ownership, not HDL gates."""
import json
from pathlib import Path
from random import Random
import tempfile
import unittest
from unittest.mock import patch
from fpga.reference import stream_ntt_wrap2_model as w

ROOT=Path(__file__).resolve().parents[1]


class Wrap2Tests(unittest.TestCase):
    def test_frozen_s1_source_identity_and_profile_name(self):
        self.assertEqual(w.sha(ROOT/'reference/stream_ntt_model.py'),w.CORE_SHA)
        self.assertEqual(w.PROFILE,'stream27-wrap2')

    def test_closed_range_both_bases_minimum_and_doubling(self):
        for aw in range(5,17):
            n=1<<aw
            for b in (2*n+5,2*n+6,604832956,1_000_000_000):
                proof=w.bound_proof(n,b)
                self.assertTrue(proof['closed']);self.assertTrue(proof['within_centered_crt'])
                self.assertLessEqual(proof['next_c1_abs_bound'],proof['c1_abs_max'])
                self.assertLessEqual(proof['doubled_coefficient_bound'],w.core.HALF)
                self.assertFalse(proof['final_S2_profile_qualified'])
        self.assertEqual(w.bound_proof(65536,10**9)['doubled_coefficient_bound'],131078000786646371404742)

    def test_signed_extreme_states_against_direct_integer_convolution(self):
        n=32;b=69;K=2*n+24
        for c0 in (-(b-1),0):
            for c1 in (-K,K):
                for digits in ((0,)*n,(b-1,)*n):
                    state=w.Wrap2State(digits,b,c0,c1);signed=list(digits)
                    signed[0]+=c0;signed[1]+=c1
                    for bit in (0,1):
                        exact=w.core.direct_negacyclic_square(signed,bit)
                        self.assertEqual(w.square_coefficients(state,bit),exact)
                        result,stats=w.carry(exact,b)
                        self.assertEqual(result.canonical(),w.core.canonicalize(exact,b))
                        self.assertEqual(stats['carry_in_digit1'],exact[0]//b)

    def test_point_correction_has_bit_reversed_natural_frequency(self):
        state=w.Wrap2State(tuple(range(32)),97,-53,17)
        for f,(p,g) in enumerate(w.core.FIELDS):
            psi=pow(g,(p-1)//64,p)
            for i in range(32):
                j=w.core.bit_reverse(i,5)
                self.assertEqual(w.point_correction(state,f,i),(-53+17*pow(psi,2*j+1,p))%p)
            signed=list(state.digits);signed[0]-=53;signed[1]+=17
            self.assertEqual(w.field_square(state,f),w.core.field_square(signed,f))

    def test_readback_propagates_digit0_borrow_into_digit1(self):
        state=w.Wrap2State((0,)*32,97,-96,31)
        expected=[1,30]+[0]*30
        self.assertEqual(state.canonical(),expected)
        negative=w.Wrap2State((0,)*32,97,-1,0)
        self.assertEqual(negative.canonical(),[-1]+[0]*31)

    def test_repeated_square_double_chains_both_bases_and_minimum(self):
        rng=Random(260930)
        for b in (69,604832956,1_000_000_000):
            canonical=[b-1]*32;state=w.Wrap2State.from_digits(canonical,b)
            nonzero=0
            for bit in [1,0,1,1,0]+[rng.randrange(2) for _ in range(15)]:
                expected=w.core.exact_square(canonical,b,bit)
                state,stats=w.square(state,bit)
                nonzero+=bool(state.c0 and state.c1)
                self.assertEqual(state.canonical(),expected)
                self.assertLessEqual(stats['max_abs_serial_carry'],w.bound_proof(32,b)['serial_carry_abs_bound'])
                canonical=expected
            self.assertGreater(nonzero,0)

    def test_all_three_required_mutants_and_each_correction_term(self):
        state,_=w.square(w.Wrap2State((999999999,)*32,10**9),1)
        self.assertNotEqual(state.c0,0);self.assertNotEqual(state.c1,0)
        expected=w.core.exact_square(state.canonical(),state.base,1)
        signed=list(state.digits);signed[0]+=state.c0;signed[1]+=state.c1
        expected_coefficients=w.core.direct_negacyclic_square(signed,1)
        for mutant in ('wrong-twiddle','missing-wrap','wrong-c-sign','missing-c0','missing-c1','wrong-frequency'):
            control,_=w.square(state,1);w.core.check_equal(control.canonical(),expected,'fresh-control')
            w.core.check_equal(w.square_coefficients(state,1),expected_coefficients,'fresh-coefficient-control')
            changed=w.square_coefficients(state,1,mutant=mutant)
            # Compare before carry: a bad transform can also trip carry-bound,
            # which must not mask whether the requested arithmetic mutation bit.
            with self.assertRaises(w.ModelMismatch) as caught:w.core.check_equal(changed,expected_coefficients,mutant)
            self.assertEqual(caught.exception.kind,mutant)

    def test_state_ranges_reject_invalid_corrections(self):
        for c0,c1 in ((1,0),(-97,0),(0,89),(0,-89)):
            with self.assertRaises(ValueError):w.Wrap2State((0,)*32,97,c0,c1)
        with self.assertRaises(ValueError):w.Wrap2State((97,)*32,97)

    def test_changed_base_canonicalizes_and_preserves_digit_checks(self):
        machine=w.Machine(32);machine.load(list(range(32)),97);machine.run(1)
        digits=machine.readback();expected=w.core.exact_square(digits,131,1)
        machine.run(1,base=131);self.assertEqual(machine.readback(),expected)
        machine.load([96]+[0]*31,97)
        with self.assertRaises(w.ModelMismatch):machine.begin(base=69)
        self.assertTrue(machine.failed)
        with self.assertRaises(w.ContractError):machine.load([0]*32,97)
        machine.reset();machine.load([0]*32,97);machine.run()
        self.assertEqual(machine.readback(),[0]*32)

    def test_host_write_materializes_canonical_digits_and_clears_correction(self):
        machine=w.Machine(32);machine.load([96]*32,97);machine.run(1)
        expected=machine.readback();expected[17]=5
        machine.host_write(17,5);self.assertIsNone(machine.state)
        self.assertEqual(machine.readback(),expected)
        machine.run(1);self.assertEqual(machine.readback(),w.core.exact_square(expected,97,1))

    def test_reset_error_and_incomplete_reload_reject_stale_result(self):
        machine=w.Machine(32);machine.load([1]+[0]*31,97);token=machine.begin(1)
        with self.assertRaises(w.ContractError):machine.host_write(0,7)
        machine.reset()
        with self.assertRaises(w.ContractError):machine.complete(token)
        for i in range(31):machine.host_write(i,0)
        with self.assertRaises(w.ContractError):machine.begin(base=97)
        self.assertTrue(machine.failed)
        machine.reset();machine.load([1]+[0]*31,97);token=machine.begin();machine.error()
        with self.assertRaises(w.ContractError):machine.complete(token)
        self.assertIsNone(machine.state)

    def test_all_archived_aw5_normal_chains(self):
        path=ROOT/'results/throughput-20260929/core27-prefetch-r2-rootfused-aw5-v2/vectors-aw5.txt'
        report=w.verify_vectors(path)
        self.assertEqual(report['cases'],568)
        self.assertGreater(report['both_correction_terms_nonzero_cases'],0)

    def test_new_aw8_aw12_vectors_from_pinned_ordinary_integer_generator(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'vectors';report=w.prepare_vectors(out)
            self.assertFalse(report['historical_archive'])
            self.assertEqual(set(report['vectors']),{'8','12'})
            for row in report['vectors'].values():
                self.assertEqual(row['normal_cases'],12)
                self.assertEqual(w.sha(out/row['path']),row['sha256'])
            self.assertEqual(w.verify_vectors(out/'vectors-aw8.txt')['cases'],12)
            with self.assertRaises(FileExistsError):w.prepare_vectors(out)
        with patch.object(w,'GENERATOR_SHA','0'*64):
            with self.assertRaises(ValueError):w.frozen_generator(ROOT)

    def test_large_integer_evidence_is_lossless_decimal_string(self):
        value=4294836224999475720000000016
        row=json.loads(json.dumps(w.exact_json(dict(value=value,half=w.core.HALF))))
        self.assertEqual(row['value'],str(value));self.assertEqual(int(row['half']),w.core.HALF)


if __name__=='__main__':unittest.main()
