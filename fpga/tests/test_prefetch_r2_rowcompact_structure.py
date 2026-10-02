"""Source and bank-row/address-age tests; no HDL or remote execution."""
import unittest
from pathlib import Path
from unittest.mock import patch
from fpga.reference import prefetch_r2_rowcompact_structure as s

ROOT=Path(__file__).resolve().parents[1]


class CompactRowTests(unittest.TestCase):
    def test_exact_source_delta(self):
        self.assertEqual(len(s.validate_files(ROOT)),3)

    def test_frozen_ancestor_and_candidate_drift_rejected(self):
        original=(ROOT/'rtl/kernel'/(s.ENGINE+'.sv')).read_text()
        with self.assertRaisesRegex(ValueError,'frozen ancestor'):
            s.expected(s.ENGINE,original+'\n')
        expected=s.expected(s.ENGINE,original)
        self.assertIn('legacy_row_tag[6][b]',expected)
        target=ROOT/'rtl/kernel'/(s.NAMES[s.ENGINE]+'.sv')
        read=Path.read_text
        mutant=expected.replace('.base_pipe[6]','.base_pipe[5]',1)
        self.assertNotEqual(expected,mutant)
        def altered(path,*args,**kwargs):return mutant if path==target else read(path,*args,**kwargs)
        with patch.object(Path,'read_text',altered),self.assertRaisesRegex(ValueError,'unreviewed compact-row delta'):
            s.validate_files(ROOT)

    def test_declared_storage(self):
        self.assertEqual(s.storage_bits(16),(8064,1232))
        self.assertEqual((s.storage_bits(16)[0]-s.storage_bits(16)[1])*3,20496)

    def test_grouped_tags_keep_local_orientation_and_merge_guards(self):
        self.assertEqual(s.NEW_DECLARE.count('(* preserve, dont_merge *)'),3)
        self.assertIn('ROW_TAG_BANKS=16',s.NEW_DECLARE)
        self.assertIn('pairing_pipe[0]<=pairing',s.NEW_DECLARE)
        self.assertIn('orientation_pipe<={orientation_pipe[5:0],orientation}',s.NEW_DECLARE)
        self.assertNotIn('^orientation_pipe[6]',s.NEW_BF)
        self.assertIn('row_tags[bank/ROW_TAG_BANKS].orientation_pipe[6]',s.NEW_BF)

    def test_exhaustive_supported_sizes_stages_groups_and_bank_rows(self):
        # All AW1..16, each runtime size, each stage and every group/bank.
        # Both orientations exercise every allowed row-selection truth value.
        comparisons=0
        for aw in range(1,17):
            kw,rw,_=s.geometry(aw)
            for lg in range(1,aw+1):
                n=1<<lg
                for stage in range(lg):
                    for group in range(max(n//128,1)):
                        base=s.stage_base(group,stage,aw,kw)
                        for orientation in (0,1):
                            old=s.literal_rows(aw,64,'BF',True,base,1<<stage,
                                               stage%kw,orientation,0,0,64)
                            common=s.common_rows(aw,64,'BF',True,base,1<<stage,0)
                            new=[s.write_row(common,stage%kw,orientation,b,'BF') for b in range(128)]
                            self.assertEqual(old,new,(aw,lg,stage,group,orientation))
                            comparisons+=128
        self.assertGreater(comparisons,4_000_000)

    def test_exhaustive_pairing_orientation_and_row_bit_positions(self):
        # Pairing tags may change while older requests are in flight. Cover
        # every pairing value independently of stage and every row bit.
        for aw in range(1,17):
            kw,rw,_=s.geometry(aw)
            values={0,(1<<aw)-1}
            values.update(1<<j for j in range(aw))
            for base in sorted(values):
                for stage in range(aw):
                    for pairing in range(kw):
                        for orientation in (0,1):
                            old=s.literal_rows(aw,64,'BF',True,base,1<<stage,pairing,orientation,0,0,64)
                            common=s.common_rows(aw,64,'BF',True,base,1<<stage,0)
                            new=[s.write_row(common,pairing,orientation,b,'BF') for b in range(128)]
                            self.assertEqual(old,new,(aw,base,stage,pairing,orientation))

    def test_full_schedule_against_logical_bank_inverse(self):
        # Independent physical-bank inverse: row fixes high address bits, then
        # bank_of determines low bits. Every paired bank must select addresses
        # differing by exactly the stage bit, and each stage visits all N words.
        for aw in range(1,17):
            kw,_,_=s.geometry(aw);n=1<<aw
            for stage in range(aw):
                seen=set();pairing=stage%kw
                for group in range(max(n//128,1)):
                    base=s.stage_base(group,stage,aw,kw)
                    orientation=(s.bank_of(base,aw,kw)>>pairing)&1
                    common=s.common_rows(aw,64,'BF',True,base,1<<stage,0)
                    words=[]
                    for bank in range(min(n,128)):
                        high=s.write_row(common,pairing,orientation,bank,'BF')<<kw
                        word=high|(bank^s.bank_of(high,aw,kw))
                        self.assertLess(word,n)
                        words.append(word);seen.add(word)
                    for bank,word in enumerate(words):
                        self.assertEqual(word^words[bank^(1<<pairing)],1<<stage)
                self.assertEqual(len(seen),n,(aw,stage))

    def test_all_mul_sizes_halves_groups_and_selected_banks(self):
        for aw in range(1,17):
            n=1<<aw;active=min(n,64)
            for group in range(max(n//64,1)):
                point=group*64
                for half in (0,1):
                    old=s.literal_rows(aw,64,'MUL',True,0,0,0,0,point,half,active)
                    common=s.common_rows(aw,64,'MUL',True,0,0,point)
                    for lane in range(active):
                        bank=half*64+lane
                        self.assertEqual(old[bank],s.write_row(common,0,0,bank,'MUL'))

    def test_every_request_writes_at_seven_edges_including_drain(self):
        event=dict(mode='BF',fire=True,base=256,toggle=128,pairing=0,orientation=1,n=65536)
        trace=s.age_trace(16,[event]+[{}]*8)
        self.assertEqual({entry[0] for entry in trace},{7})
        self.assertEqual(len(trace),128)
        self.assertTrue(all(old==new for _,_,old,new,_ in trace))

    def test_bubbles_alternating_pairing_modes_drain_and_reset(self):
        for aw in range(1,17):
            kw,_,_=s.geometry(aw);n=1<<aw;events=[]
            for i in range(49):
                if i in (3,8,19,30):events.append(dict(reset=True));continue
                stage=i%aw;pairing=i%kw;mode=('BF','MUL','DRAIN')[i%3]
                events.append(dict(mode=mode,fire=i%5!=0,base=(i*131)&(n-1),
                    toggle=1<<stage,pairing=pairing,orientation=i%2,n=n,
                    point_base=(i*64)&(n-1),point_half=i%2,mul_lanes=min(n,64)))
            events.extend([{}]*8)
            trace=s.age_trace(aw,events)
            self.assertTrue(trace)
            self.assertTrue(all(old==new for _,_,old,new,_ in trace),(aw,trace[:3]))

    def test_reset_cancels_pending_writes(self):
        event=dict(mode='BF',fire=True,base=128,toggle=256,pairing=2,orientation=1,n=65536)
        for abort_edge in range(1,8):
            events=[event]+[{}]*(abort_edge-1)+[dict(reset=True)]+[{}]*10
            self.assertEqual(s.age_trace(16,events),[])

    def test_mutant_wrong_age_is_detected(self):
        events=[dict(mode='MUL',fire=True,point_base=i*128,point_half=i%2,mul_lanes=64)
                for i in range(12)]+[{}]*8
        trace=s.age_trace(16,events,wrong_age=True)
        self.assertTrue(any(old!=new for _,_,old,new,_ in trace))

    def test_mutant_live_pairing_is_detected(self):
        events=[dict(mode='BF',fire=True,base=0,toggle=128,pairing=i%7,
                     orientation=0,n=65536) for i in range(12)]+[{}]*8
        trace=s.age_trace(16,events,wrong_live_pairing=True)
        self.assertTrue(any(old!=new for _,_,old,new,_ in trace))

    def test_inverse_normalization_row_uses_state_not_active_op(self):
        # Inverse normalization enters MUL_READ with active_op still zero.
        common=s.common_rows(16,64,'MUL',True,0,128,512)
        self.assertEqual(common,(4,0))
        self.assertNotEqual(common,s.common_rows(16,64,'BF',True,0,128,512))


if __name__=='__main__':unittest.main()
