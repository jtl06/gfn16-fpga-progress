"""Pure source/range/address checks only; no HDL/vendor/full-N arithmetic."""
import unittest
from fpga.reference import radix22_aa_whole_source_v1 as a


class AAWholeSourceTests(unittest.TestCase):
    def test_exact_alias_plus_one_ram_delta(self):
        result=a.verify();self.assertEqual(len(result),10)
        old=(a.ROOT/'rtl/kernel/genefer_anext_point_block_engine_v1.sv').read_text()
        new=(a.ROOT/a.BLOCK).read_text()
        self.assertEqual(a.reverse(new).replace(a.field.NEW,a.field.OLD),old)
        for path in ('rtl/kernel/genefer_anext_point_core_v1.sv','rtl/kernel/genefer_anext_point_ntt_sequencer_v1.sv','rtl/kernel/genefer_anext_point_square_backend_v1.sv'):
            self.assertEqual(a.reverse((a.ROOT/a.rename(path)).read_text()),(a.ROOT/path).read_text())

    def test_full32_range_at_every_active_lane_and_mask(self):
        for prime in a.FIELDS:
            for bad in (prime,prime+1,0x08000001,0x80000001,0xffffffff):
                for lane in range(16):
                    words=[0]*16;words[lane]=bad
                    flags=a.full32_block_admission(words,65535)
                    self.assertFalse(flags[a.FIELDS.index(prime)])
                    self.assertTrue(all(a.full32_block_admission(words,65535^(1<<lane))))
            self.assertTrue(a.full32_block_admission([prime-1]*16,65535)[a.FIELDS.index(prime)])
        self.assertFalse(any(a.full32_block_admission([1]*16,65535,rst_n=False)))
        self.assertFalse(any(a.full32_block_admission([1]*16,65535,enabled=False)))

    def test_scalar_digit_bound_and_signed_minus_one(self):
        for p in a.FIELDS:
            self.assertLess(999999999,16*p)
            for x in (0,1,p-1,p,p+1,8*p-1,min(8*p,999999999),999999999):
                value=x
                for shift in (3,2,1,0):
                    if value>=p<<shift:value-=p<<shift
                self.assertEqual(value,x%p);self.assertLess(value,p);self.assertLess(value,1<<27)
            self.assertLess(p-1,1<<27) # Full32 signed -1 normalizes to P-1 before narrowing.

    def test_critical_admission_or_eligibility_mutants_reject(self):
        mutations=[('block','genefer_anext_point_block_engine_v1.sv','block_write_words[lane*32+:32]>=P','block_write_words[lane*32+:27]>=P'),
                   ('seq','genefer_anext_point_ntt_sequencer_v1.sv',".load_we(1'b0)",".load_we(block_write_en)"),
                   ('route','genefer_track_a4_blockroute_v2.sv','rst_n && write_en && legal','write_en && legal'),
                   ('transfer','genefer_track_a4_field_transfer_v2.sv','rst_n && !cancel && !error && !protocol_fault','rst_n && !error && !protocol_fault'),
                   ('cold','genefer_track_a4_cold_prefill_v1.sv',"int'(written)!=T","int'(written)!=T-1"),
                   ('post','genefer_track_a4_post_ntt_v1.sv',"patch_words_written!=6'd32","patch_words_written!=6'd16")]
        for key,name,old,new in mutations:
            text=(a.ROOT/'rtl/kernel'/name).read_text();self.assertIn(old,text)
            with self.assertRaises(ValueError):a.range_contract({key:text.replace(old,new)})

    def test_symbolic_full_address_initialization_all_geometries(self):
        for aw in (5,8,16):
            n=1<<aw;t=n//16;addresses={lane*t+offset for lane in range(16) for offset in range(t)}
            self.assertEqual(addresses,set(range(n)))
            physical=set()
            for address in addresses:
                bank=0
                for j in range(aw):bank^=((address>>j)&1)<<(j%7)
                physical.add((bank,address>>7))
            self.assertEqual(len(physical),n)

    def test_extra48_highword_probe_preserves_flat_oracle(self):
        cpp=(a.ROOT/a.PROBE_CPP).read_text()
        self.assertIn('for(uint32_t bad : {0x08000001u,0x80000001u,0xffffffffu})',cpp)
        self.assertIn('event(true,true,0,1,65535,65535,words);check();',cpp)
        self.assertIn('if((wm>>j&1) && words[j]>=P)canonical=false',cpp)
        self.assertIn('highword_cases=48',cpp)


if __name__=='__main__':unittest.main()
