"""Small local arithmetic tests only; no hardware schedule or adopted profile."""
import random
import unittest
from fpga.reference import stream_ntt_blockwrap2_proposal as m


class BlockWrapProposalTests(unittest.TestCase):
    def test_full_size_scalar_bounds(self):
        for P in (8,16):
            for base in (604832956,1000000000):
                x=m.bound_proof(65536,P,base)
                self.assertLess(x['doubled_coefficient_bound'],m.core.HALF)
                self.assertLess(x['next_c1_abs_bound'],x['c1_abs_max'])
                self.assertTrue(x['one_adjust_boundary_normalization_proved'])
                self.assertFalse(x['adopted_profile']);self.assertFalse(x['hardware_timing_qualified'])

    def test_geometry_and_base_rejections(self):
        for n,P,b in ((32,32,1000),(32,3,1000),(32,8,69),(16,1,1000)):
            with self.subTest(n=n,P=P,b=b),self.assertRaises(ValueError):m.bound_proof(n,P,b)
        m.bound_proof(32,1,69)

    def test_serial_split_whole_integer_identity(self):
        rng=random.Random(9001)
        for n,P in ((32,1),(32,8),(32,16),(64,8),(128,16)):
            K=2*n+24*P;base=max(2*n+5,m.ceildiv(2*K,3)+1)
            A=m.bound_proof(n,P,base)['doubled_coefficient_bound']
            for a in ([A]*n,[-A]*n,[(-1)**i*A for i in range(n)],
                      [rng.randrange(-A,A+1) for _ in range(n)]):
                with self.subTest(n=n,P=P):
                    serial,q=m.carry_serial(a,base,P);split,stats=m.carry_split(a,base,P)
                    self.assertEqual(serial,split);self.assertEqual(q,stats['block_carries'])
                    ring=base**n+1
                    self.assertEqual(m.core._pack(a,base)%ring,m.core._pack(split.effective(),base)%ring)
                    T=n//P
                    self.assertEqual(m.core._pack(a,base),m.core._pack(split.digits,base)+sum(v*base**((k+1)*T) for k,v in enumerate(q)))

    def test_target_bases_single_adjust_matches_serial(self):
        rng=random.Random(811)
        for n,P in ((32,8),(64,16)):
            for base in (604832956,1000000000):
                A=m.bound_proof(n,P,base)['doubled_coefficient_bound']
                a=[rng.randrange(-A,A+1) for _ in range(n)]
                state,stats=m.carry_split(a,base,P,require_one_adjust=True)
                self.assertEqual(state,m.carry_serial(a,base,P)[0])
                self.assertTrue(all(abs(x)<=1 for x in stats['radix_adjustments']))

    def test_one_adjust_counterexample_is_not_hidden(self):
        x=m.one_adjust_counterexample()
        self.assertEqual(x['raw_boundary'],(412,0));self.assertEqual(x['radix_adjustment'],2)
        a=x['first_block_coefficients']+[0]*28
        with self.assertRaisesRegex(ValueError,'one-adjust'):m.carry_split(a,172,8,require_one_adjust=True)
        self.assertEqual(m.carry_split(a,172,8)[0],m.carry_serial(a,172,8)[0])

    def test_sparse_spectrum_full_bit_reversed_indices(self):
        rng=random.Random(313)
        for n,P in ((32,1),(32,8),(32,16),(64,8)):
            b=1000000;K=2*n+24*P
            state=m.BlockState(tuple(rng.randrange(b) for _ in range(n)),b,
                               tuple(rng.randrange(1-b,b) for _ in range(P)),
                               tuple(rng.randrange(-K,K+1) for _ in range(P)))
            T=n//P
            for f,(p,g) in enumerate(m.core.FIELDS):
                psi=pow(g,(p-1)//(2*n),p);omega=psi*psi%p;tables=m.correction_tables(state,f)
                for i in range(n):
                    j=m.core.bit_reverse(i,n.bit_length()-1);point=psi*pow(omega,j,p)%p
                    direct=sum((state.c0[k]+point*state.c1[k])*pow(point,k*T,p) for k in range(P))%p
                    self.assertEqual(m.spectral_correction(state,f,i,tables),direct)

    def test_invariant_extremes_and_quadratic_oracle(self):
        rng=random.Random(31)
        for n,P in ((32,1),(32,8),(32,16),(64,8)):
            b=1000000;B=b-1;K=2*n+24*P;A=m.bound_proof(n,P,b)['doubled_coefficient_bound']
            for _ in range(3):
                state=m.BlockState((B,)*n,b,tuple(rng.choice((-B,B)) for _ in range(P)),tuple(rng.choice((-K,K)) for _ in range(P)))
                oracle=m.core.direct_negacyclic_square(state.effective(),1)
                self.assertLessEqual(max(map(abs,oracle)),A)
                self.assertEqual(m.square_coefficients(state,1),oracle)
                self.assertEqual(m.carry_split(oracle,b,P)[0],m.carry_serial(oracle,b,P)[0])

    def test_repeated_square_double_whole_integer_chain(self):
        rng=random.Random(932)
        for n,P in ((32,1),(32,8),(64,16),(128,8)):
            K=2*n+24*P
            for b in (max(2*n+5,m.ceildiv(2*K,3)+1),604832956,1000000000):
                digits=[rng.randrange(b) for _ in range(n)];state=m.BlockState.from_digits(digits,b,P)
                expected=m.core._pack(digits,b);ring=b**n+1
                for double in (0,1,1,0):
                    state=m.square(state,double);expected=(expected*expected*(1<<double))%ring
                    self.assertEqual(m.core._pack(state.effective(),b)%ring,expected)
                    self.assertEqual(m.core._pack(state.canonical(),b)%ring,expected)

    def test_typed_mutation_sensitivity(self):
        b=1000000;P=8;n=32
        state=m.BlockState(tuple((i+1)*71 for i in range(n)),b,
                           tuple(11+3*i for i in range(P)),tuple(-5+i for i in range(P)))
        oracle=m.core.direct_negacyclic_square(state.effective())
        self.assertEqual(m.square_coefficients(state),oracle)
        for mutant in ('wrong-twiddle','missing-wrap','wrong-c-sign','wrong-frequency'):
            with self.subTest(mutant=mutant),self.assertRaisesRegex(m.core.ModelMismatch,'blockwrap-mutant'):
                m.core.check_equal(m.square_coefficients(state,mutant=mutant),oracle,'blockwrap-mutant:'+mutant)

    def test_outside_state_and_coefficient_bounds(self):
        with self.assertRaises(ValueError):m.BlockState((0,)*32,1000,(1000,),(0,))
        with self.assertRaises(ValueError):m.BlockState((0,)*32,1000,(0,),(89,))
        A=m.bound_proof(32,1,1000)['doubled_coefficient_bound']
        for fn in (m.carry_serial,m.carry_split):
            with self.assertRaisesRegex(m.core.ModelMismatch,'coefficient-bound'):fn([A+1]+[0]*31,1000,1)
        with self.assertRaisesRegex(ValueError,'limited'):m.square_coefficients(m.BlockState.from_digits([0]*512,1000000,8))


if __name__=='__main__':unittest.main()
