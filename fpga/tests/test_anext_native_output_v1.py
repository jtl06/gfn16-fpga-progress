import unittest
from fpga.reference.anext_native_output_v1 import validate
from fpga.reference.anext_composition_contract_v1 import schedule
from fpga.reference.track_a4_core_vectors_v1 import corpus


def fixture(aw):
    vectors,_=corpus(aw);budget=schedule(aw);lines=[];latencies=[]
    for i,line in enumerate(vectors.splitlines()[1:]):
        command=list(map(int,line.split()))
        if command[0]!=5:continue
        cold,load=command[8:10]
        total=budget['warm_backend']+(budget['cold_cached_backend']-budget['warm_backend'])*cold+9*load
        values=dict(index=i,cold=cold,load=load,double=command[4],latency=total+2,total=total,
            prefill=budget['cold_prefill_child_cycles']*cold,root=9*load,ntt=budget['ntt_controller_cycles'],post=budget['post_child_cycles'],seed=0)
        latencies.append(total+2);lines.append('A4_CORE_SQUARE '+' '.join(f'{k}={v}' for k,v in values.items()))
    n=1<<aw;commands=12*n+20
    footer=dict(aw=aw,commands=commands,squares=14,cold_squares=8,profile_loads=4,readbacks=8*n,hold_checks=2*commands,ticks=sum(latencies)+1000,max_latency=max(latencies)+100)
    lines.append('A4_CORE_PASS '+' '.join(f'{k}={v}' for k,v in footer.items()))
    return '\n'.join(lines)+'\n',vectors


class Output(unittest.TestCase):
    def test_exact_small_contracts(self):
        for aw in (5,8):
            stdout,vectors=fixture(aw)
            self.assertEqual(validate(stdout,'',0,dict(mode='normal',aw=aw),{'vectors':vectors})['aw'],aw)

    def test_wrong_phase_seed_header_and_missing_output_reject(self):
        text,vectors=fixture(5);cfg=dict(mode='normal',aw=5);assets={'vectors':vectors}
        variants=[text.replace('seed=0','seed=122',1),text.replace('ntt=114','ntt=115',1),
                  text.replace('root=9','root=3089',1),text.replace('total=206','total=207',1),
                  text+'extra\n',text.split('\n',1)[1]]
        for changed in variants:
            self.assertNotEqual(changed,text)
            with self.assertRaises((ValueError,AssertionError)):validate(changed,'',0,cfg,assets)
        with self.assertRaises((ValueError,AssertionError)):validate(text,'unexpected',0,cfg,assets)
        with self.assertRaises((ValueError,AssertionError)):validate(text,'',1,cfg,assets)


if __name__=='__main__':unittest.main()
