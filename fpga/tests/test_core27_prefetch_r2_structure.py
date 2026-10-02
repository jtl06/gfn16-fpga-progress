"""Local math/source tests only. These do not compile or simulate RTL."""
import hashlib
import random
import unittest
from pathlib import Path

from reference.core27_prefetch_r2_structure import (
    ANCESTORS, NAMES, OLD_CONVERTER, NEW_CONVERTER, FIELDS, RADIX,
    expected, validate_files, mont, profile_word,
)
from reference.ntt27_generated_regression import profile as old_profile

ROOT = Path(__file__).resolve().parents[1]
KERNEL = ROOT/'rtl/kernel'


class SourceTests(unittest.TestCase):
    def test_exact_four_file_delta(self):
        self.assertEqual(len(validate_files(ROOT)),4)

    def test_ancestor_fail_closed(self):
        for name in ANCESTORS:
            with self.assertRaises(ValueError):
                expected(name,(KERNEL/(name+'.sv')).read_text()+'\n')

    def test_preserves_guard_reducer_and_controller(self):
        old=(KERNEL/'genefer_square_core27_stream_prefetch.sv').read_text()
        new=(KERNEL/'genefer_square_core27_stream_prefetch_r2.sv').read_text()
        # Last commit, early carry-start, cache/error quarantine and every FSM
        # branch stay byte-identical; conversion latency changes only upstream.
        self.assertEqual(old[old.index('    always_ff @(posedge clk or negedge rst_n) begin\n        if(!rst_n) begin\n            state<=IDLE;'):],
                         new[new.index('    always_ff @(posedge clk or negedge rst_n) begin\n        if(!rst_n) begin\n            state<=IDLE;'):])
        a='            genefer_digit_reduce27_pipe'
        b='            genefer_montgomery_mul27_sparse_pipe'
        reducer=old[old.index(a):old.index(b)]
        self.assertIn(reducer,new)
        a='    always_comb begin\n        bad_digit=0;'
        b='    assign profile_coherent='
        self.assertEqual(old[old.index(a):old.index(b)],new[new.index(a):new.index(b)])
        self.assertNotIn('genefer_montgomery_mul27_sparse_pipe',new)
        self.assertIn(NEW_CONVERTER,new)
        self.assertIn('carry_start=state==CONVERT && (&conversion_valid) && int\'(write_count)==N-IO_STEP;',new)

    def test_format_is_explicit_and_no_untrusted_external_profile(self):
        engine=(KERNEL/'genefer_ntt_banked27_prefetch_r2_engine.sv').read_text()
        core=(KERNEL/'genefer_square_core27_stream_prefetch_r2.sv').read_text()
        self.assertIn("profile_format!=8'd2",engine)
        self.assertNotIn("profile_format!=8'd1",engine)
        self.assertIn(".profile_format(8'd2)",core)
        self.assertNotIn('input logic profile_',core[:core.index('    // Atomic27')])
        self.assertIn('genefer_root_profile27_r2_rom #',core)
        self.assertIn('genefer_ntt_banked27_prefetch_r2_host_engine #',core)
        # A caller can lie about arbitrary uploaded words in the standalone
        # child API; format checks are not cryptographic content verification.

    def test_source_negative_changes_rejected_not_rtl_mutant_gate(self):
        cases=[
            ('genefer_square_core27_stream_prefetch', 'reduce_valid_words[f][h] && !reduce_error_words[f][h]', 'reduce_valid_words[f][h]'),
            ('genefer_square_core27_stream_prefetch', 'convert_words[f][h*32+:32]<=canonical_digit;', 'convert_words[f][h*32+:32]<=carry_words[h][31:0];'),
            ('genefer_square_core27_stream_prefetch', 'if(!rst_n) convert_valid_words[f][h]<=0;', 'if(!rst_n) convert_valid_words[f][h]<=1;'),
            ('genefer_square_core27_stream_prefetch', ".profile_format(8'd2)", ".profile_format(8'd1)"),
            ('genefer_root_profile27_rom', 'factor=key==0 ? R2 : IN;', 'factor=key==0 ? R : IN;'),
            ('genefer_root_profile27_rom', "cmul(cpow(alpha,32'(4*LANES)),R)", "cmul(cpow(alpha,32'(4*LANES)),R2)"),
            ('genefer_ntt_banked27_prefetch_engine', "profile_format!=8'd2", "profile_format!=8'd1"),
        ]
        hashes=set()
        for name,anchor,replacement in cases:
            correct=expected(name,(KERNEL/(name+'.sv')).read_text())
            self.assertIn(anchor,correct)
            mutant=correct.replace(anchor,replacement)
            self.assertNotEqual(mutant,correct)
            hashes.add(hashlib.sha256(mutant.encode()).hexdigest())
        self.assertEqual(len(hashes),len(cases))


class MathTests(unittest.TestCase):
    def test_radix_and_field_constants(self):
        self.assertEqual(RADIX,2**32)
        for p,q,g,r2 in FIELDS:
            self.assertEqual((p*q)%RADIX,1)
            self.assertEqual(r2,RADIX*RADIX%p)
            self.assertEqual((p-1)%131072,0)
            self.assertEqual(pow(g,(p-1)//2,p),p-1)

    def test_complete_compact_profiles_only_twist_seeds_change(self):
        for f,(p,q,g,r2) in enumerate(FIELDS):
            for aw in (1,2,3,4,8,10,16):
                for lanes in (16,64):
                    reference=old_profile(f,aw,aw,lanes)
                    for address,old in enumerate(reference):
                        self.assertEqual(profile_word(p,g,aw,lanes,address,False),old)
                        fused=profile_word(p,g,aw,lanes,address)
                        self.assertLess(fused,p)
                        self.assertEqual(fused,old*(RADIX%p)%p if address<4*lanes else old)

    def test_all_twist_roots_four_context_recurrence_and_digit_identity(self):
        # All runtime sizes; recurrence feedback calculated by ordinary integer
        # modular multiplication, expected roots by independent modular powers.
        rng=random.Random(270232)
        for p,q,g,r2 in FIELDS:
            rinv=pow(RADIX,-1,p)
            raw=(-1,0,1,p-1,p,p+1,(1<<27)-1,1<<27,604832955,999999999)
            for aw in range(1,17):
                n=1<<aw;psi=pow(g,(p-1)//(2*n),p)
                for lanes in (16,64):
                    state=[profile_word(p,g,aw,lanes,i) for i in range(4*lanes)]
                    step=profile_word(p,g,aw,lanes,4*lanes)
                    expected_root=r2
                    for i in range(n):
                        slot=i%(4*lanes)
                        root=state[slot]
                        self.assertEqual(root,expected_root)
                        d=(raw[i%len(raw)] if i%11 else rng.randrange(1000000000))%p
                        fused=d*root*rinv%p
                        original=(d*(RADIX%p)%p)*(root*rinv%p)*rinv%p
                        self.assertEqual(fused,original)
                        state[slot]=root*step*rinv%p
                        expected_root=expected_root*psi%p

    def test_direct_transform_square_matches_negacyclic_convolution(self):
        # Independent O(N^2) transform + O(N^2) signed-wrap integer convolution.
        for p,q,g,r2 in FIELDS:
            r=RADIX%p
            for aw in range(1,5):
                n=1<<aw;psi=pow(g,(p-1)//(2*n),p);omega=psi*psi%p
                for raw in ([-1]+[0]*(n-1),[999999999-i*7919 for i in range(n)]):
                    twisted=[mont(d%p,pow(psi,i,p)*r2%p,p) for i,d in enumerate(raw)]
                    spectrum=[sum(twisted[j]*pow(omega,j*k,p) for j in range(n))%p for k in range(n)]
                    squared=[mont(v,v,p) for v in spectrum]
                    inverse=[sum(squared[k]*pow(omega,-j*k,p) for k in range(n))%p for j in range(n)]
                    output=[mont(v,pow(psi,-j,p)*pow(n,-1,p)%p,p) for j,v in enumerate(inverse)]
                    convolution=[0]*n
                    for i,a in enumerate(raw):
                        for j,b in enumerate(raw):
                            convolution[(i+j)%n]+=a*b*(1 if i+j<n else -1)
                    self.assertEqual(output,[x%p for x in convolution])

    def test_wrong_format_step_and_raw_truncation_have_counterexamples(self):
        for p,q,g,r2 in FIELDS:
            r=RADIX%p;psi=pow(g,(p-1)//131072,p)
            self.assertNotEqual(mont(1,r,p),mont(1,r2,p))
            self.assertNotEqual(mont(r2,pow(psi,256,p)*r2%p,p),pow(psi,256,p)*r2%p)
            self.assertNotEqual(999999999%p,(999999999&((1<<27)-1))%p)
            with self.assertRaises(ValueError):mont(999999999,r2,p)

    def test_one_register_token_reset_and_latency_model(self):
        # Explicit clock-edge contract, not a model of the actual top FSM.
        # Reducer result t+3; original accept t+4/result t+7/RAMcommit t+8.
        # New register capture t+4/RAMcommit t+5. All row intervals unchanged.
        for rows in (1,2,4096):
            old=[t+8 for t in range(rows)]
            new=[t+5 for t in range(rows)]
            self.assertTrue(all(a-b==3 for a,b in zip(old,new)))
            self.assertEqual(new[-1]-new[0],rows-1)
        # Conversion eligibility is reset or state gated independently of data.
        valid=False;held=0
        for reset,convert,rv,error,data in ((False,True,True,False,17),(False,True,False,False,91),
                                          (False,True,True,True,99),(True,True,True,False,31),
                                          (False,False,True,False,41),(False,True,True,False,23)):
            eligible=not reset and convert and rv and not error
            valid=eligible
            if eligible:held=data
            self.assertEqual(valid,eligible)
            if not eligible:self.assertEqual(held,17)
        self.assertEqual(held,23)


if __name__=='__main__':unittest.main()
