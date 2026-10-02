import random
import unittest
from fpga.reference.stream27_small_carry_oracle import Cell,CellInputError,bounds,geometry,oracle,threshold_cell


class SmallCarryArithmetic(unittest.TestCase):
    def test_profile_minimums(self):
        self.assertEqual(geometry(16,8)['minimum_base'],131077)
        self.assertEqual(geometry(5,8)['minimum_base'],172)
        for args in [(4,8),(17,8),(5,0),(5,3),(5,32)]:
            with self.assertRaises(CellInputError):geometry(*args)

    def test_scalar_proof_all_parameter_geometries(self):
        count=0
        for aw in range(5,17):
            for exponent in range(aw):
                p=1<<exponent;minimum=geometry(aw,p)['minimum_base']
                for base in (minimum,minimum+1,604832956,10**9):
                    proof=bounds(aw,p,base);count+=1
                    self.assertLessEqual(proof['exact_q2_bound'],proof['q'])
                    self.assertGreaterEqual(proof['total_min'],-2*base)
                    self.assertLess(proof['total_max'],4*base)
                    self.assertLess(4*base,1<<32)
        self.assertEqual(count,504)

    def test_small_profiles_exhaust_all_legal_y_and_six_states(self):
        count=0;seen=set()
        for p in (1,8):
            minimum=geometry(5,p)['minimum_base']
            for base in range(minimum,minimum+8):
                proof=bounds(5,p,base)
                for carry in range(-2,4):
                    for y in range(proof['y_min'],proof['y_max']+1):
                        expected=oracle(y,carry,base,5,p)
                        self.assertEqual(threshold_cell(y,carry,base),expected)
                        seen.add(expected[1]);count+=1
        self.assertGreater(count,50000)
        self.assertEqual(seen,set(range(-2,4)))

    def test_every_threshold_neighbor_at_supported_profile_boundaries(self):
        count=0
        for aw in range(5,17):
            for p in (8,16):
                minimum=geometry(aw,p)['minimum_base']
                for base in (minimum,minimum+1,604832956,10**9):
                    proof=bounds(aw,p,base)
                    for carry in range(-2,4):
                        ys={proof['y_min'],proof['y_max'],0,base-1}
                        for multiple in range(-2,5):
                            ys.update(multiple*base+delta-carry for delta in (-1,0,1))
                        for y in sorted(ys):
                            if proof['y_min']<=y<=proof['y_max']:
                                self.assertEqual(threshold_cell(y,carry,base),oracle(y,carry,base,aw,p));count+=1
        self.assertGreater(count,5000)

    def test_block_start_exhausts_small_digits_and_ignores_legal_old_carry(self):
        base=172
        for carry in range(-2,4):
            for y in range(base):
                self.assertEqual(oracle(y,carry,base,5,8,block_start=True),(y,0))
        for carry in (-4,-3):
            with self.assertRaisesRegex(CellInputError,'CARRY_RANGE'):
                oracle(0,carry,base,5,8,block_start=True)
        for y in (-1,base):
            with self.assertRaisesRegex(CellInputError,'BLOCK_START_RANGE'):
                oracle(y,0,base,5,8,block_start=True)

    def test_full_input_widths_reject_before_truncation(self):
        for base in (0,171,10**9+1,2**32-1):
            with self.assertRaisesRegex(CellInputError,'BASE'):oracle(0,0,base,5,8)
        for y in (-2**32,2**32-1,-249,591):
            with self.assertRaisesRegex(CellInputError,'Y_RANGE'):oracle(y,0,172,5,8)
        for y in (-2**32-1,2**32):
            with self.assertRaisesRegex(CellInputError,'Y_PORT'):oracle(y,0,172,5,8)
        for carry in (-5,4):
            with self.assertRaisesRegex(CellInputError,'CARRY_PORT'):oracle(0,carry,172,5,8)

    def test_random_split_blocks_against_whole_integer_identity(self):
        rng=random.Random(20260930)
        for base in (172,173,604832956,10**9):
            proof=bounds(5,8,base);A=proof['coefficient_bound']
            for _ in range(100):
                coefficients=[rng.choice([-A,A,rng.randrange(-A,A+1)]) for _ in range(4)]
                parts=[]
                for a in coefficients:
                    q,r0=divmod(a,base);q2,r1=divmod(q,base);parts.append((r0,r1,q2))
                digits=[];carry=3 # arbitrary legal previous-block residue
                for i,(r0,r1,q2) in enumerate(parts):
                    y=r0+(parts[i-1][1] if i else 0)+(parts[i-2][2] if i>=2 else 0)
                    digit,carry=oracle(y,carry,base,5,8,block_start=i==0);digits.append(digit)
                boundary=parts[-1][1]+parts[-2][2]+carry+base*parts[-1][2]
                self.assertEqual(sum(a*base**i for i,a in enumerate(coefficients)),
                                 sum(d*base**i for i,d in enumerate(digits))+boundary*base**4)

    def test_named_arithmetic_mutants_have_concrete_witnesses(self):
        cases=[('boundary_le',0,0,False),('truncate_negative',-1,0,False),('ignore_block_start',5,3,True)]
        for mutant,y,carry,start in cases:
            with self.subTest(mutant=mutant):
                self.assertNotEqual(threshold_cell(y,carry,172,block_start=start,mutant=mutant),
                                    oracle(y,carry,172,5,8,block_start=start))


class SmallCarryEdges(unittest.TestCase):
    def test_one_edge_payload_and_external_feedback(self):
        cell=Cell(5,8,8)
        a=cell.edge(y=527,carry=0,base=172,payload=7)
        self.assertEqual((a.valid,a.error,a.digit,a.carry,a.payload),(True,False,11,3,7))
        b=cell.edge(y=170,carry=a.carry,base=172,payload=8)
        self.assertEqual((b.digit,b.carry,b.payload),(1,1,8))

    def test_bubbles_hold_all_payload_and_clear_flags(self):
        cell=Cell(5,8,8);good=cell.edge(y=527,carry=0,base=172,payload=7)
        for _ in range(10):
            bubble=cell.edge(y=-2**32,carry=-4,base=0,payload=255,valid=False)
            self.assertEqual((bubble.valid,bubble.error),(False,False))
            self.assertEqual((bubble.digit,bubble.carry,bubble.payload),(good.digit,good.carry,good.payload))

    def test_invalid_token_has_its_tag_but_holds_digit_and_carry(self):
        cell=Cell(5,8,8);good=cell.edge(y=527,carry=0,base=172,payload=7)
        bad=cell.edge(y=-249,carry=0,base=172,payload=8)
        self.assertEqual((bad.valid,bad.error,bad.payload),(False,True,8))
        self.assertEqual((bad.digit,bad.carry),(good.digit,good.carry))
        # Error quarantine belongs to the outer controller, not this primitive.
        next_good=cell.edge(y=42,carry=bad.carry,base=172,payload=9,block_start=True)
        self.assertEqual((next_good.valid,next_good.digit,next_good.carry),(True,42,0))

    def test_async_reset_cancels_eligibility_and_feedback_only(self):
        cell=Cell(5,8,8);good=cell.edge(y=527,carry=0,base=172,payload=7)
        reset=cell.reset()
        self.assertEqual((reset.valid,reset.error,reset.carry),(False,False,0))
        self.assertEqual((reset.digit,reset.payload),(good.digit,good.payload))
        self.assertFalse(cell.edge(valid=False).valid)
        new=cell.edge(y=0,carry=0,base=10**9,payload=8,block_start=True)
        self.assertEqual((new.valid,new.digit,new.carry,new.payload),(True,0,0,8))

    def test_reset_wins_over_simultaneous_invalid_input(self):
        cell=Cell(5,8,8)
        out=cell.edge(y=2**40,carry=100,base=0,payload=1000000,rst_n=False)
        self.assertEqual((out.valid,out.error,out.carry),(False,False,0))


if __name__=='__main__':unittest.main()
