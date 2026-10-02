"""Local source and symbolic frame checks only; no HDL compiler/simulator invoked."""
from pathlib import Path
import random
import unittest

from reference.ntt27_rootclip_structure import (
    ANCESTOR_SHA, TOP, OLD_TOP, expected, bench_expected, costs, validate_files,
    targeted_mutants, MUTATIONS)

ROOT=Path(__file__).resolve().parents[1]


def bank_capture(frame,lanes):
    """One abstract bank-register edge; mirrors declared cut, not arithmetic RTL."""
    kw=lanes.bit_length();stage=frame['stage']
    clipped=[frame['roots'][b&((1<<stage)-1)] if stage<kw else frame['roots'][b]
             for b in range(2*lanes)]
    return dict(clip=clipped,data=frame['data'][:],point=frame['point'][:],
                pairing=stage%kw,orientation=frame['orientation'],half=frame['half'],
                valid=frame['valid'][:],row=frame['row'][:])


def consume(cut,lanes,mode,dif,scale):
    output=[];p=cut['pairing']
    for lane in range(lanes):
        lo=(lane&((1<<p)-1))|((lane>>p)<<(p+1));hi=lo|(1<<p)
        if cut['orientation']:lo,hi=hi,lo
        if mode=='bf':word=(cut['data'][lo],cut['data'][hi],cut['clip'][lo],dif)
        else:
            index=lane+cut['half']*lanes;lhs=cut['data'][index]
            rhs=lhs if mode=='square' else cut['point'][index] if mode=='twist' else scale
            word=(0,lhs,rhs,False)
        output.append((cut['valid'][lane],word))
    return output


def independent(frame,lanes,mode,dif,scale):
    """Direct pre-cut address expression, without constructing clipped bank words."""
    kw=lanes.bit_length();p=frame['stage']%kw;out=[]
    for lane in range(lanes):
        bits=[(lane>>bit)&1 for bit in range(kw-1)];bits.insert(p,frame['orientation'])
        lower=sum(bit<<index for index,bit in enumerate(bits));upper=lower^(1<<p)
        if mode=='bf':
            root_index=lower% (1<<frame['stage']) if frame['stage']<kw else lower
            word=(frame['data'][lower],frame['data'][upper],frame['roots'][root_index],dif)
        else:
            address=frame['half']*lanes+lane
            value=frame['data'][address]
            rhs={'square':value,'twist':frame['point'][address],'scale':scale}[mode]
            word=(0,value,rhs,False)
        out.append((frame['valid'][lane],word))
    return out


class RootclipStructure(unittest.TestCase):
    def setUp(self):
        self.old=(ROOT/'rtl/kernel'/f'{OLD_TOP}.sv').read_text()
        self.new=(ROOT/'rtl/kernel'/f'{TOP}.sv').read_text()
        self.old_bench=(ROOT/'rtl/tb/ntt_banked27_rootpipe_engine.cpp').read_text()
        self.new_bench=(ROOT/'rtl/tb/ntt_banked27_rootclip_engine.cpp').read_text()

    def test_exact_pinned_delta_and_bench(self):
        receipt=validate_files(ROOT)
        self.assertEqual(receipt['ancestor_sha256'],ANCESTOR_SHA)
        self.assertIn('not_simulated',receipt['status'])
        self.assertEqual(self.new_bench,bench_expected(self.old_bench))

    def test_unrelated_ancestor_edit_rejected(self):
        with self.assertRaises(ValueError):expected(self.old.replace('cycles<=cycles+1','cycles<=cycles+2'))
        with self.assertRaises(ValueError):bench_expected(self.old_bench+'\n')

    def test_root_mapping_arithmetic_and_host_unchanged(self):
        def region(text,begin,end):return text[text.index(begin):text.index(end)]
        start='    // Fold the data-bank XOR into the first root-bank XOR:'
        stop='    for(genvar b=0;b<BANKS;b=b+1) begin : root_route'
        self.assertEqual(region(self.old,start,stop),region(self.new,start,stop))
        for line in ('assign read_data=data_q[host_bank_d];',
                     'genefer_ntt_difdit_butterfly27 #(.P(P),.Q(Q)) butterfly (',
                     'assign root_clip[b]=low_stage_e ? root_clip_option[b][PW\'(stage_bit_e)] : root_rotated[b];',
                     'always_ff @(posedge clk) root_rotated[b]<=root_rotate_option[b][control_tiles[b/TILE_BANKS].rotation_mid];'):
            self.assertIn(line,self.old);self.assertIn(line,self.new)
        # All RAM instantiations and canonical/collision assertions stay byte exact.
        begin='        genefer_sdp_ram32 #(.AW(RW),.DEPTH(DEPTH)) data_ram ('
        end='    always_ff @(posedge clk or negedge rst_n) begin\n        if(!rst_n) begin\n            state<=IDLE'
        self.assertEqual(region(self.old,begin,end),region(self.new,begin,end))

    def test_all_consumers_use_same_cut_frame(self):
        section=self.new[self.new.index('begin : arithmetic'):self.new.index('begin : memories')]
        for forbidden in ('data_route_q[','root_point_q[','root_clip[','.pairing_e]',
                          '.orientation_e ','point_half_e','bf_route_valid','mul_route_valid'):
            self.assertNotIn(forbidden,section)
        for required in ('data_clip_q[','root_point_clip_q[','root_clip_q[','.pairing_f]',
                         '.orientation_f ','point_half_f','bf_clip_valid','mul_clip_valid'):
            self.assertIn(required,section)
        self.assertIn('point_type_pipe<={point_type_pipe[4:0],mul_clip_valid[lane]};',section)

    def test_new_valid_reset_and_tags(self):
        for anchor in ('bf_clip_valid<=0;mul_clip_valid<=0;point_half_f<=0;',
                       'pairing_f<=0;orientation_f<=0;',
                       'bf_clip_valid<=bf_route_valid;mul_clip_valid<=mul_route_valid;',
                       'pairing_f<=pairing_e;orientation_f<=orientation_e;',
                       'row_tag [0:9][0:BANKS-1]', 'for(int t=0;t<10;t=t+1)',
                       'for(int t=1;t<10;t=t+1)', 'orientation_pipe[9]', 'point_half_pipe[9]'):
            self.assertIn(anchor,self.new)
        self.assertEqual(self.new.count('row_tag[9][bank]'),2)
        self.assertNotIn('row_tag[8][bank]',self.new)
        # Payload is intentionally not reset; reset-cleared eligibility masks it.
        self.assertIn('always_ff @(posedge clk) root_clip_q[b]<=root_clip[b];',self.new)

    def test_mutation_anchors_are_unique_not_claimed_rtl_rejections(self):
        mutants=targeted_mutants(self.new)
        self.assertEqual(len(mutants),15)
        self.assertEqual(len(set(mutants.values())),15)
        for name,text in mutants.items():self.assertNotEqual(text,self.new,name)
        for name,old,new in MUTATIONS:self.assertEqual(self.new.count(old),1,name)

    def test_symbolic_bank_capture_matches_direct_operand_indices(self):
        rng=random.Random(0xC11F)
        for lanes in (1,2,4,8,16,32,64):
            for prime in (104857601,69206017,67239937):
                for stage in range(16):
                    frame=dict(stage=stage,orientation=stage&1,half=(stage>>1)&1,
                               data=[rng.randrange(prime) for _ in range(2*lanes)],
                               roots=[rng.randrange(prime) for _ in range(2*lanes)],
                               point=[rng.randrange(prime) for _ in range(2*lanes)],
                               row=list(range(2*lanes)),valid=[i<min(lanes,1<<(stage%7)) for i in range(lanes)])
                    for mode in ('bf','square','twist','scale'):
                        for dif in (False,True):
                            self.assertEqual(consume(bank_capture(frame,lanes),lanes,mode,dif,123),
                                             independent(frame,lanes,mode,dif,123))

    def test_abstract_one_edge_valid_payload_and_reset_flush(self):
        # One abstract stage: no bubble can lend validity to stale payload.
        # This checks the intended recurrence, NOT synthesis or real RTL traces.
        for reset_age in range(12):
            stage=None;observed=[];expected_tokens=[]
            for edge in range(24):
                reset=edge==reset_age
                token=edge if edge%3!=1 else None
                if reset:stage=None
                else:
                    if stage is not None:observed.append((edge,stage))
                    stage=token
                if edge>0 and not reset and edge-1!=reset_age and (edge-1)%3!=1:
                    expected_tokens.append((edge,edge-1))
            self.assertEqual(observed,expected_tokens)

    def test_symbolic_read_to_commit_ten_edges_and_row_tap(self):
        # Four registered ingress frames (RAM/mid/route/clip), unchanged six
        # butterfly stages, then RAM samples the prior output at edge t+10.
        # Reset clears eligibility; payload bits need not be physically reset.
        wrong_tap_witness=False
        for abort in (None,*range(16)):
            ingress=[None]*4;butterfly=[None]*6;row=[None]*10;seen=[]
            for edge in range(40):
                if edge==abort:
                    ingress=[None]*4;butterfly=[None]*6;row=[None]*10
                    continue
                completed=butterfly[-1]
                if completed is not None:
                    self.assertEqual(edge-completed,10)
                    self.assertEqual(row[-1],completed)
                    wrong_tap_witness |= row[-2]!=completed
                    seen.append(completed)
                butterfly=[ingress[-1],*butterfly[:-1]]
                ingress=[edge if edge%3!=1 else None,*ingress[:-1]]
                row=[edge,*row[:-1]]
            expected=[read for read in range(30) if read%3!=1 and
                      (abort is None or not read<=abort<=read+10)]
            self.assertEqual(seen,expected)
        self.assertTrue(wrong_tap_witness)

    def test_resource_and_cycle_counts(self):
        self.assertEqual(costs()['logical_register_bits'],13603)
        self.assertEqual((costs()['old_cycles'],costs()['new_cycles'],costs()['extra_cycles']),(19803,19838,35))
        for aw in range(1,17):
            for lanes in (1,2,4,8,16,32,64):
                c=costs(aw,lanes)
                self.assertEqual(c['new_cycles']-c['old_cycles'],2*aw+3)
                self.assertEqual(c['extra_ram_bits'],0)
                self.assertEqual(c['extra_multiplier_pipelines'],0)
        self.assertEqual(costs(1,64)['extra_cycles'],5)

    def test_point_root_bypass_needs_physical_half_repeat_witness(self):
        def half(group):
            address=group*64;bank=0
            while address:bank^=address&127;address>>=7
            return bank>>6
        self.assertEqual(next(g for g in range(255) if half(g)==half(g+1)),127)
        # Future RTL negative must include N>=16384 and distinct roots at rows63/64.
        self.assertEqual((127*64>>7,128*64>>7),(63,64))


if __name__=='__main__':unittest.main()
