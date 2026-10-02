"""Source and symbolic routing tests only. No model build or HDL execution."""
from pathlib import Path
import tempfile
import unittest

from fpga.reference import core27_prefetch_r2_host_broadcast_structure as p

ROOT=Path(__file__).resolve().parents[1]


class HostBroadcastStructureTests(unittest.TestCase):
    def test_exact_two_delta_source_contract(self):
        pins=p.validate_files(ROOT);self.assertEqual(len(pins),1)
        old=(ROOT/'rtl/kernel'/(p.ANCESTOR+'.sv')).read_text()
        new=(ROOT/'rtl/kernel'/(p.CANDIDATE+'.sv')).read_text()
        restored=new.replace('module '+p.CANDIDATE+' #(','module '+p.ANCESTOR+' #(').replace(p.NEW,p.OLD)
        self.assertEqual(restored,old)
        with self.assertRaises(ValueError):p.transform(old+'\n')

    def test_all32768_bank_quarter_lane_cases(self):
        self.assertEqual(p.exhaustive_proof()['comparisons'],32768)

    def test_sparse_zero_and_alternating_masks_all_permutations(self):
        words=[0x80000000+i*0x70101 for i in range(16)]
        masks=[0,0xffff,0x5555,0xaaaa]+[1<<h for h in range(16)]
        for bank in range(128):
            for quarter in range(4):
                for mask in masks:
                    old=p.writes(words,mask,quarter,bank)
                    new=p.writes(words,mask,quarter,bank,broadcast=True)
                    self.assertEqual(old,new)
                    self.assertEqual(sum(x is not None for x in new),mask.bit_count())

    def test_runtime_smallN_clipping_and_real_bank_address_mapping(self):
        words=list(range(16))
        for aw in range(1,17):
            for lg in range(1,aw+1):
                n=1<<lg
                # First/last rows and transitions through both bank halves,
                # all host quarters, and high-bit XOR address folds.
                addresses={0,max(0,((n-1)//16)*16)}
                addresses.update(a for a in (16,32,48,64,80,96,112,128,256,512,8192,16384,32768) if a<n)
                for addr in addresses:
                    child=addr&~63;quarter=(addr>>4)&3;bank=p.bank_of(child,aw)
                    for mask in (0,0xffff,0x5555,0x8001):
                        old=p.writes(words,mask,quarter,bank,n,child)
                        new=p.writes(words,mask,quarter,bank,n,child,True)
                        self.assertEqual(old,new)
                        expected=[None]*128
                        for h in range(16):
                            if addr+h<n and mask&(1<<h):expected[p.bank_of(addr+h,aw)]=words[h]
                        self.assertEqual(new,expected)

    def test_upper_two_payload_stages_identity_not_mask_identity(self):
        words=[0xf0000000+i for i in range(16)]*4
        for low in range(16):
            lower=p.xor_route(words,low)
            for high in (0,16,32,48):self.assertEqual(p.xor_route(words,low|high),lower)
        mask=[h<16 for h in range(64)]
        self.assertNotEqual(p.xor_route(mask,0),p.xor_route(mask,16))
        self.assertNotEqual(p.xor_route(mask,0),p.xor_route(mask,32))

    def test_inactive_poison_never_becomes_write_and_full32_is_preserved(self):
        words=[0xffffffff]*16
        for quarter in range(4):
            for bank in (0,31,64,127):
                self.assertEqual(p.writes(words,0,quarter,bank,broadcast=True),[None]*128)
                old=p.writes(words,1,quarter,bank);new=p.writes(words,1,quarter,bank,broadcast=True)
                self.assertEqual(old,new)
                self.assertEqual([w for w in new if w is not None],[0xffffffff])
        # No truncation or modulo repair of an enabled illegal residue.
        with self.assertRaises(ValueError):p.writes([1<<32]*16,1,0,0,broadcast=True)

    def test_priority_busy_reset_mask_and_collision_guards_unchanged(self):
        candidate=(ROOT/'rtl/kernel'/(p.CANDIDATE+'.sv')).read_text()
        child=(ROOT/'rtl/kernel'/(p.CHILD+'.sv')).read_text()
        for text in (
            "assign child_mask[h]=host_group==GW'(h/HOST_LANES) && vector_lane_mask[h%HOST_LANES];",
            'if(!rst_n)begin local_error<=0;read_group<=0;end',
            '!busy && !start && !profile_request && vector_read_en && !vector_load_we && descriptor_ok',
            '.load_we(load_we && !request && !profile_request)',
            '.vector_load_we(vector_load_we && descriptor_ok && !profile_request)',
            '.vector_read_en(vector_read_en && descriptor_ok && !profile_request)',
            '.vector_lane_mask(child_mask),.vector_write_data(child_write_data)',
            '.vector_read_data(child_read_data)'):
            self.assertIn(text,candidate)
        for text in (
            'if(state==IDLE && !start)',
            "if(vector_ok && 1'(bank/LANES)==vector_base_bank[LW] && vector_write_route[LW].mask[bank%LANES])",
            'data_we[bank]=vector_load_we;data_re[bank]=!vector_load_we;',
            'if(data_we[bank] && data_w[bank]>=P)',
            'if(data_re[bank] && data_we[bank] && data_ra[bank]==data_wa[bank])'):
            self.assertIn(text,child)

    def test_unreviewed_mask_change_is_rejected_and_frozen_core_not_integrated(self):
        rtl=ROOT/'rtl/kernel';core=(rtl/'genefer_square_core27_stream_prefetch_r2.sv').read_text()
        self.assertNotIn(p.CANDIDATE,core)
        self.assertIn(p.ANCESTOR+' #(',core)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);dest=root/'rtl/kernel';dest.mkdir(parents=True)
            for name in (p.ANCESTOR,p.CHILD,p.CANDIDATE):
                text=(rtl/(name+'.sv')).read_text()
                if name==p.CANDIDATE:text=text.replace('&& vector_lane_mask[h%HOST_LANES]','&& 1\'b1')
                (dest/(name+'.sv')).write_text(text)
            with self.assertRaises(ValueError):p.validate_files(root)


if __name__=='__main__':unittest.main()
