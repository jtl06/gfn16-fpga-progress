import unittest

from fpga.reference.stream27_p16_warm_contract_v1 import (
    Protocol,feedback_schedule,geometry,interface,lane_contract,producer_collisions)
from fpga.reference import merged_stream27_model_v1 as merged
from fpga.reference import stream_ntt_blockcarry_model as block


class WarmP16(unittest.TestCase):
    def test_full_size_event_only_and_variant_delta(self):
        for variant in ('p16c','p16a'):
            result=feedback_schedule(65536,variant=variant)
            self.assertEqual(result['physical_rows'],16384)
            self.assertEqual(result['field_peak_owners'],2)
            self.assertEqual(result['whole_peak_owners'],2)
            self.assertFalse(result['full_N_numeric_NTT_performed'])
        g=geometry()
        self.assertEqual((g['pointwise_accept'],g['sink_accept'],g['warm_interval'],g['cache_margin']),
                         (4207,8416,8459,66))
        self.assertEqual(geometry(variant='p16a')['warm_interval']-g['warm_interval'],8)

    def test_small_feedback_delay_is_not_hidden(self):
        self.assertEqual(geometry(64)['feedback_delay'],4)
        self.assertEqual(geometry(256)['feedback_delay'],0)
        for n in (64,128,256):
            self.assertEqual(feedback_schedule(n)['physical_rows'],4*n//16)

    def test_lane_order_and_wrap(self):
        wires=lane_contract()
        self.assertEqual(sorted(x['carry_lane'] for x in wires),list(range(16)))
        self.assertEqual(sum(x['boundary_sign']==-1 for x in wires),1)
        self.assertEqual(wires[15]['boundary_target_lane'],0)
        self.assertIn('UNPATCHED',interface()['feedback'])
        self.assertIn('before',interface()['carry_begin'])

    def test_cache_deadline_same_edge_is_too_late(self):
        g=geometry(256)
        for offset,okay in ((-1,True),(0,False),(1,False)):
            m=Protocol(256)
            for tick in range(g['pointwise_accept']+1):
                e=m.edge(tick,begin=(0,0,1000000000) if tick==0 else None,
                    correction=(0,0) if tick==1 else None,
                    ready=(0,0) if tick==g['pointwise_accept']+offset else None,
                    pw=(0,True) if tick==g['pointwise_accept'] else None)
            self.assertEqual(e.pointwise_accept,okay)
            self.assertEqual(e.error_after,not okay)

    def test_registered_origin_and_immediate_stale_commit(self):
        g=geometry(256)
        for live,expected in ((0,True),(1,False)):
            m=Protocol(256)
            for tick in range(g['sink_accept']+2):
                row=tick-g['pointwise_accept']
                sinkrow=tick-g['sink_accept']
                e=m.edge(tick,begin=(0,0,1000000000) if tick==0 else None,
                    correction=(0,0) if tick==0 else None,ready=(0,0) if tick==42 else None,
                    pw=(0,row==0) if 0<=row<g['rows'] else None,
                    sink=(0,sinkrow==0) if 0<=sinkrow<g['rows'] else None,
                    external_fault=tick==g['sink_accept'],live_generation=live)
                if tick==g['sink_accept']:
                    self.assertEqual(e.commit,expected);self.assertTrue(e.error_after)
                if tick==g['sink_accept']+1:self.assertFalse(e.commit)

    def test_cancellation_does_not_remove_physical_rows_and_reset(self):
        g=geometry(256);m=Protocol(256);seen=commits=0
        for tick in range(g['last_sink']+1):
            row=tick-g['pointwise_accept'];sinkrow=tick-g['sink_accept']
            sink=(0,sinkrow==0) if 0<=sinkrow<g['rows'] else None
            e=m.edge(tick,begin=(0,0,1000000000) if tick==0 else None,
                correction=(0,0) if tick==0 else None,ready=(0,0) if tick==42 else None,
                pw=(0,row==0) if 0<=row<g['rows'] else None,sink=sink,enabled=False)
            seen+=sink is not None;commits+=e.commit;self.assertFalse(e.error_after)
        self.assertEqual((seen,commits,len(m.owners)),(16,0,0))
        e=m.edge(999,begin=(0,0,1000000000),correction=(0,0),sink=(0,True),reset=True)
        self.assertFalse(e.frame_accept or e.correction_accept or e.commit)

    def test_resource_conflict_and_epoch_uniqueness(self):
        g=geometry(256)
        self.assertFalse(producer_collisions(g,[0,16],[0,16]))
        self.assertTrue(producer_collisions(g,[0,16],[0,40]))
        m=Protocol(256,epoch_bits=2)
        self.assertTrue(m.edge(0,begin=(3,0,1000000000)).frame_accept)
        self.assertTrue(m.edge(16,begin=(0,0,1000000000)).frame_accept)
        e=m.edge(17,begin=(3,1,1000000000))
        self.assertFalse(e.frame_accept);self.assertTrue(e.error_after)
        self.assertIn('ALL old',interface()['finite_tag_reuse'])

    def test_small_redundant_feedback_arithmetic_independent_schoolbook(self):
        # Nonzero c0/c1 are represented at block starts and starts+1, not
        # silently patched before the warm forward transform.
        for n in (64,256):
            base=block.minimum_base(n,16)+99
            digits=tuple((j*j+3*j+7)%base for j in range(n))
            c0=tuple((j%5)-2 for j in range(16));c1=tuple((j%3)-1 for j in range(16))
            state=block.proposal.BlockState(digits,base,c0,c1)
            expanded=list(digits)
            for j in range(16):expanded[j*(n//16)]+=c0[j];expanded[j*(n//16)+1]+=c1[j]
            expected=[0]*n
            for i,a in enumerate(expanded):
                for j,b in enumerate(expanded):
                    expected[(i+j)%n]+=a*b*(1 if i+j<n else -1)
            self.assertEqual(merged.block_state_square(state),expected)


if __name__=='__main__':unittest.main()
