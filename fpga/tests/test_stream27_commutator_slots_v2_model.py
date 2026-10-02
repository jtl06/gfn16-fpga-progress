import unittest
from fpga.reference.stream27_commutator_slots_v2_model import (
    ChainRow, Pipeline, TwoCell, Token, commit_row, verify_sources,
)
from fpga.reference.stream_ntt_schedule import commutator


def rows(T, context=0, generation=0, base=0):
    return [tuple(Token(base + 2*c+l, context, generation, 2*c+l)
                  for l in range(2)) for c in range(T)]


class ComposableSlotsV2(unittest.TestCase):
    def test_frozen_sources(self):
        self.assertEqual(len(verify_sources()), 4)

    def test_geometry_cancellation_reset_and_commit(self):
        for contexts in (1, 2):
            for d1, d2 in ((1,1), (1,2), (2,1), (2,4), (4,2), (4,16), (16,4), (256,16), (4096,1)):
                T = max(8, 2*max(d1,d2)); delay = d1+1+d2
                for gap in ((0,1,3,138) if T <= 32 else (0,)):
                    for cancel in (None, 0, T//2, T-1, T+delay-1):
                        pipe = Pipeline(d1,d2,T,contexts=contexts)
                        source = {}; expected = {}
                        for f in range(3):
                            start=f*(T+gap); data=rows(T,f%contexts,int(f==2),100000*f)
                            source.update({start+c:(row,c==0) for c,row in enumerate(data)})
                            transformed=commutator(commutator(data,0,d1),0,d2)
                            expected.update({start+delay+c:(tuple(row),c==0) for c,row in enumerate(transformed)})
                        for tick in range(3*(T+gap)+delay+2):
                            gens=(int((cancel is not None and tick>=cancel) or tick>=2*(T+gap)),0)
                            data,start=source.get(tick,(None,False))
                            out,commit=pipe.edge(data,frame_start=start,generations=gens)
                            self.assertFalse(out.error)
                            want=expected.get(tick)
                            self.assertEqual(out.slot_valid,want is not None)
                            if want:
                                row,start=want;ctx=row[0].context
                                self.assertEqual((out.tokens,out.frame_start,out.eligible),(row,start,row[0].generation==gens[ctx]))
                            prev=expected.get(tick-1)
                            live=bool(prev and prev[0][0].generation==gens[prev[0][0].context])
                            self.assertEqual(commit.valid,live)
                            if live:self.assertEqual((commit.tokens,commit.frame_start),prev)

    def test_first_stage_faults_visible_sticky_and_reset(self):
        data=rows(8)
        cases=[[(data[0],False)], [(None,True)],
               [(data[0],True),(None,False)],
               [(data[0],True),(data[1],True)],
               [(data[0],True),(rows(8,1)[1],False)],
               [(data[0],True),(rows(8,generation=1)[1],False)]]
        for case in cases:
            pipe=Pipeline(1,2,8,contexts=2)
            for data_in,start in case:out,commit=pipe.edge(data_in,frame_start=start)
            self.assertEqual(out.stage_errors[0],True)
            self.assertTrue(out.error);self.assertFalse(out.slot_valid);self.assertFalse(commit.valid)
            for _ in range(32):
                out,commit=pipe.edge()
                self.assertTrue(out.error);self.assertFalse(commit.valid)
            out,commit=pipe.edge(reset=True)
            self.assertFalse(out.error);self.assertEqual(out.stage_errors,(False,False));self.assertFalse(commit.valid)
            got=[]
            for tick in range(14):
                out,commit=pipe.edge(data[tick] if tick<8 else None,frame_start=tick==0)
                self.assertFalse(out.error)
                if commit.valid:got.append(commit.tokens)
            self.assertEqual(got,[tuple(row) for row in commutator(commutator(data,0,1),0,2)])

    def test_cancel_between_output_and_commit(self):
        for mode in ('generation','disable','reset','fault'):
            pipe=Pipeline(1,2,8);data=rows(8)
            for tick in range(5):out,commit=pipe.edge(data[tick],frame_start=tick==0)
            self.assertTrue(out.slot_valid);self.assertTrue(out.eligible);self.assertFalse(commit.valid)
            kwargs={'generations':(1,0)} if mode=='generation' else {'enabled':(False,True)} if mode=='disable' else {'reset':True} if mode=='reset' else {}
            out,commit=pipe.edge(None if mode=='fault' else data[5],**kwargs)
            self.assertFalse(commit.valid)
            if mode=='fault':self.assertTrue(out.stage_errors[0])

    def test_advisory_eligible_is_not_commit_authority(self):
        row=ChainRow(True,True,True,False,rows(8)[0])
        self.assertTrue(row.eligible)  # Mutant using old eligible would commit.
        self.assertFalse(commit_row(row,generations=(1,0)).valid)
        self.assertFalse(commit_row(row,enabled=(False,True)).valid)
        self.assertFalse(commit_row(row,chain_error=True).valid)

    def test_reset_every_input_link_output_commit_age(self):
        for age in range(14):
            pipe=Pipeline(1,2,8);data=rows(8)
            for tick in range(age):pipe.edge(data[tick] if tick<8 else None,frame_start=tick==0)
            out,commit=pipe.edge(reset=True)
            self.assertFalse(out.slot_valid or out.error or commit.valid)
            got=[]
            for tick in range(14):
                out,commit=pipe.edge(data[tick] if tick<8 else None,frame_start=tick==0)
                self.assertFalse(out.error)
                if commit.valid:got.append(commit.tokens)
            self.assertEqual(got,[tuple(row) for row in commutator(commutator(data,0,1),0,2)])

    def test_filtered_link_negative_and_downstream_fault_authority(self):
        pipe=Pipeline(1,2,8,broken_link=True);data=rows(8);fault=False
        for tick in range(14):
            out,commit=pipe.edge(data[tick] if tick<8 else None,frame_start=tick==0,
                                 generations=(int(tick>=4),0))
            fault |= out.stage_errors[1]
            if out.error:self.assertFalse(out.slot_valid or commit.valid)
        self.assertTrue(fault)


if __name__=='__main__':unittest.main()
