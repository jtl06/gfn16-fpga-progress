import unittest
from fpga.reference.track_a4_core_vectors_v1 import corpus
from fpga.reference.track_a4_core_output_v2 import parse,PROFILES


def synthetic(aw):
    vector,meta=corpus(aw);t=(1<<aw)//16;out=[];maximum=0
    for i,line in enumerate(vector.splitlines()[1:]):
        row=list(map(int,line.split()))
        if row[0]!=5:continue
        cold,load,double=row[8],row[9],row[4];root=((2*aw+2)*257+5)*load
        total=root+246+t+66+(t+12)*cold;maximum=max(maximum,total+2)
        out.append(f'A4_CORE_SQUARE index={i} cold={cold} load={load} double={double} latency={total+2} total={total} prefill={(t+10)*cold} root={root} ntt=246 post={t+62} seed=122')
    out.append(f'A4_CORE_PASS aw={aw} commands={meta["commands"]} squares=14 cold_squares=8 profile_loads=4 readbacks={meta["readbacks"]} hold_checks={meta["hold_checks"]} ticks=1000000 max_latency={maximum}')
    return '\n'.join(out)+'\n',vector


class CoreOutputTests(unittest.TestCase):
    def test_positive_profiles(self):
        for aw in (5,8):
            out,vector=synthetic(aw)
            self.assertTrue(parse(out,vector)['source_schedule_hypotheses_match'])

    def test_mutations_rejected(self):
        out,vector=synthetic(8)
        mutants=[out+'junk\n',out.replace('post=78','post=79',1),out.replace('cold=1','cold=0',1),
                 out.replace('commands=3092','commands=3091'),out.replace('ntt=246','ntt=247',1)]
        for mutant in mutants:
            with self.assertRaises(ValueError):parse(mutant,vector)
        with self.assertRaises(ValueError):parse(out,vector+'\n')
        mismatch=parse(out.replace('post=78','post=79',1),vector,False)
        self.assertFalse(mismatch['source_schedule_hypotheses_match'])


if __name__=='__main__':unittest.main()
