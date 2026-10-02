"""Scalar/source gates only; never elaborate HDL or run full-N arithmetic."""
from itertools import product
from pathlib import Path
import random
import unittest

from fpga.reference import stream27_canonical_image_model_v1 as model

ROOT = Path(__file__).resolve().parents[1]


class CanonicalImage(unittest.TestCase):
    def test_profile_and_full_size_symbolic_only(self):
        for aw in range(5, 17):
            for p in (8, 16):
                g = model.geometry(aw, p)
                for base in (g['minimum_base'], model.MAX_BASE):
                    proof = model.proof(aw, p, base)
                    self.assertEqual(proof['normal_begin_to_done'], 6*(1 << aw))
                    self.assertEqual(proof['special_begin_to_done'], 7*(1 << aw))
                    self.assertEqual(proof['image_RAM_bits'], 32*(1 << aw))
                    self.assertFalse(proof['numerical_full_N_performed'])
                with self.assertRaisesRegex(ValueError, 'BASE_RANGE'):
                    model.proof(aw, p, g['minimum_base']-1)
        for bad in ((4,8), (17,8), (5,4), (5,32), (5.0,8)):
            with self.assertRaisesRegex(ValueError, 'GEOMETRY'):
                model.geometry(*bad)

    def test_five_way_fold_exact_euclidean_not_signed_truncation(self):
        for base in (3, 5, 173, 300):
            for v in range(-2*base, 3*base):
                q, r = model.fold(v, base)
                self.assertEqual((q,r), divmod(v, base))
        for v in (-11, 15):
            with self.assertRaisesRegex(ValueError, 'FOLD_RANGE'):
                model.fold(v, 5)

    def test_carry_bound_closed_at_every_extreme(self):
        for aw, p in product((5,8), (8,16)):
            g = model.geometry(aw,p)
            for base in (g['minimum_base'], model.MAX_BASE):
                b, k = base-1, g['k']
                for raw,carry in product((0,b), range(-2,3)):
                    for correction in (0,-b,b,-k,k):
                        q,r = model.fold(raw+carry+correction,base)
                        self.assertTrue(-2<=q<=2 and 0<=r<base)
                    q,r = model.fold(raw+carry,base)
                    self.assertTrue(-1<=q<=1 and 0<=r<base)

    def test_small_independent_whole_integer_all_geometries(self):
        rng = random.Random(0x534343414e4f4e)
        for aw,p in product((5,8),(8,16)):
            g = model.geometry(aw,p);n=g['n'];k=g['k']
            for base in (g['minimum_base'], model.MAX_BASE):
                vectors = [( [0]*n, [0]*p, [0]*p ),
                    ([base-1]*n,[base-1 if b%2 else 1-base for b in range(p)],
                     [k if b%2 else -k for b in range(p)]),
                    ([i%base for i in range(n)], [-1 if b==0 else 0 for b in range(p)],[0]*p)]
                vectors += [([rng.randrange(base) for _ in range(n)],
                    [rng.randrange(1-base,base) for _ in range(p)],
                    [rng.randrange(-k,k+1) for _ in range(p)]) for _ in range(24)]
                for digits,c0,c1 in vectors:
                    result = model.canonicalize(digits,c0,c1,base)
                    self.assertEqual(result.digits,model.independent_integer_oracle(digits,c0,c1,base))
                    self.assertEqual(result.cycles,(7 if result.special else 6)*n)
                    self.assertTrue(abs(result.carries[0])<=2)
                    self.assertTrue(all(abs(q)<=1 for q in result.carries[1:]))

    def test_both_third_pass_special_encodings_materialize(self):
        for aw,p in product((5,8),(8,16)):
            g=model.geometry(aw,p);n=g['n'];base=g['minimum_base']
            for digits,c0 in (([0]*n,[-1]+[0]*(p-1)),
                               ([base-1]*n,[1]+[0]*(p-1))):
                r=model.canonicalize(digits,c0,[0]*p,base)
                self.assertTrue(r.special)
                self.assertEqual(r.digits,(-1,)+(0,)*(n-1))
                self.assertEqual(r.cycles,7*n)
                self.assertEqual(r.digits,model.independent_integer_oracle(digits,c0,[0]*p,base))
        # Exhaustive normalized tiny chains independently validate the final
        # propagation lemma. No profile/whole-N numeric transform is involved.
        for base in range(3,7):
            for digits in product(range(base),repeat=3):
                for initial in (-1,0,1):
                    q=initial;image=[]
                    for d in digits:q,r=divmod(d+q,base);image.append(r)
                    if q==1:self.assertEqual(image,[0]*3)
                    elif q==-1:self.assertEqual(image,[base-1]*3)

    def test_mutants_omit_corrections_wrap_sign_and_counter_rejected(self):
        g=model.geometry(5,16);base=g['minimum_base'];n=g['n'];p=g['p']
        digits=[0]*n;c0=[0]*p;c1=[0]*p;c1[-1]=-g['k'];c0[0]=-1
        expected=model.independent_integer_oracle(digits,c0,c1,base)
        self.assertNotEqual(expected,model.canonicalize(digits,c0,[0]*p,base).digits)
        image=list(digits);carry=0
        for phase in range(3):
            for j in range(n):
                b,row=divmod(j,g['t']);v=image[j]+carry
                if phase==0:v+=c0[b] if row==0 else c1[b] if row==1 else 0
                carry,image[j]=divmod(v,base)
            # Intentional ordinary-cyclic wrap fault, not the module algorithm.
        self.assertNotEqual(tuple(image),expected)
        result=model.canonicalize(digits,c0,c1,base)
        self.assertNotEqual(result.cycles,result.cycles-1)

    def test_range_and_no_numeric_full_size(self):
        g=model.geometry(5,8);base=g['minimum_base'];n=g['n'];p=g['p']
        for digits,c0,c1,error in (([base]*n,[0]*p,[0]*p,'DIGIT_RANGE'),
            ([0]*n,[base]*p,[0]*p,'CORRECTION_RANGE'),
            ([0]*n,[0]*p,[g['k']+1]*p,'CORRECTION_RANGE')):
            with self.assertRaisesRegex(ValueError,error):model.canonicalize(digits,c0,c1,base)
        with self.assertRaisesRegex(ValueError,'NUMERIC_SMALL_ONLY'):
            model.canonicalize([0]*512,[0]*8,[0]*8,2000)

    def test_actual_ram_and_source_edge_ledger(self):
        sv=(ROOT/'rtl/kernel/genefer_stream27_canonical_image_v1.sv').read_text()
        for token in ('genefer_sdp_ram32 #(.AW(ROW_W),.DEPTH(T))',
            'READ_WORD:state<=PROCESS_WORD;', 'state<=SPECIAL_WRITE;',
            "ram_w[b]=address==0 ? 32'hffffffff : 32'd0;",
            'read_pending<=legal_read;', 'read_address_out<=read_address_d;',
            "read_data<=$signed({{64{ram_q[read_bank_d][31]}},ram_q[read_bank_d]});",
            'read_pending && (load_valid || begin_canonical)',
            'base_reg<=base;', 'process_bad', 'raw_ready<=0;loaded_count<=0;'):
            self.assertIn(token,sv)
        self.assertNotIn('$readmem',sv)
        self.assertNotIn('blackbox',sv)
        ledger=model.protocol_ledger(16,16)
        self.assertEqual(ledger['normal_cycles'],393216)
        self.assertEqual(ledger['special_cycles'],458752)
        self.assertIn('not per square',ledger['barrier_usage'])


if __name__=='__main__':unittest.main()
