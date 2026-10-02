import unittest
from fpga.reference.stream27_commutator_sync_model import Pair, Token, compare, transactions
from fpga.reference.stream_ntt_schedule import commutator


class SynchronousCommutator(unittest.TestCase):
    def test_registered_ram_against_ideal(self):
        for depth in (1,2,4,8,16,32,256,4096):
            counts=compare(depth)
            self.assertGreater(counts['valid'],0);self.assertGreater(counts['resets'],10)

    def test_ideal_against_frozen_queue_and_exact_edge(self):
        for depth in (1,2,4,8,16,64):
            T=max(8,2*depth);rows=[[Token(c*2+l,0,0,c*2+l) for l in range(2)] for c in range(T)]
            expected=commutator(rows,0,depth);pair=Pair(depth,T)
            outputs=[];edges=[]
            for c in range(T+depth):
                valid,error,row=pair.edge(tuple(rows[c]) if c<T else None,start=c==0)
                self.assertFalse(error)
                if valid:outputs.append(list(row));edges.append(c)
            self.assertEqual(outputs,expected)
            self.assertEqual(edges,list(range(depth,depth+T)))

    def test_negative_controls(self):
        for mutant in ('current-read-address','frame-flush','phase-one-early','global-cancel'):
            with self.assertRaisesRegex(AssertionError,'COMM_SYNC_MISMATCH'):compare(4,mutant=mutant)

    def test_reset_retains_ram_but_masks_stale(self):
        p=Pair(4,8,synchronous=True)
        for i in range(5):p.edge((Token(i,0,0,i),Token(i+1,0,0,i+1)),start=i==0)
        before=list(p.lower.memory);p.edge(reset=True)
        self.assertEqual(before,p.lower.memory)
        for _ in range(20):self.assertFalse(p.edge()[0])

    def test_generation_filter_not_physical_flush(self):
        ideal=Pair(2,8);sync=Pair(2,8,synchronous=True)
        for tick in range(18):
            pair=tuple(Token(tick*2+l,tick//8,0,tick*2+l) for l in range(2)) if tick<16 else None
            event=dict(pair=pair,start=tick in (0,8),generations=(int(tick>=5),0))
            a=ideal.edge(**event);b=sync.edge(**event);self.assertEqual(a,b)
            if tick>=10:self.assertTrue(a[0]);self.assertEqual(a[2][0].context,1)

    def test_context_cancel_head_middle_tail_preserves_all_B_rows(self):
        for depth in (1,2,4,16):
            T=max(8,2*depth)
            for cancel in (0,T//2,T-1,T+depth-1):
                ideal=Pair(depth,T);sync=Pair(depth,T,synchronous=True);B=[]
                for tick in range(2*T+depth):
                    ctx=tick//T
                    pair=tuple(Token(tick*2+l,ctx,0,(tick%T)*2+l) for l in range(2)) if tick<2*T else None
                    event=dict(pair=pair,start=tick in (0,T),generations=(int(tick>=cancel),0))
                    a=ideal.edge(**event);self.assertEqual(a,sync.edge(**event))
                    if a[0] and a[2][0].context==1:B.extend(t.index for t in a[2])
                    if tick>=cancel and a[0]:self.assertEqual(a[2][0].context,1)
                self.assertEqual(sorted(B),list(range(2*T)))


if __name__=='__main__':unittest.main()
