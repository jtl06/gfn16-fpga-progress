import json,unittest
from fpga.reference.core27_t5b_soak_v1 import reference
from fpga.reference.anext_soak_source_v1 import verify,expected
from fpga.reference.anext_soak_output_v1 import normalise
from fpga.reference.anext_composition_contract_v1 import schedule

def fixture(negative='none'):
    ref=reference();plan=ref.make_plan(aw=5,squares=4,chunk_squares=2,checkpoint_every=2,base=1000)
    _,oracle=ref.corpus(plan,'python-small-only')['continuous'];s=schedule(5);checks={c['step']:c for c in oracle['segment']['checkpoints']};rows=[];total=0
    def check(k):
        digits=list(checks[k]['digits'])
        if negative=='loaded-state' and k==0:digits[0]=(digits[0]+1)%1000
        rows.append('ANEXT_SOAK_CHECK '+json.dumps(dict(case_id=plan['case_id'],step=k,digits=digits)))
    check(0)
    if negative=='loaded-state':return '\n'.join(rows)+'\n',oracle,ref,'SOAK_BOUNDARY_MISMATCH step=0 digit=0\n',1
    for step in range(1,5):
        cold=step-1 in checks;load=step==1;cycles=s['warm_backend']+(s['cold_cached_backend']-s['warm_backend'])*cold+9*load;total+=cycles
        row=dict(case_id=plan['case_id'],step=step,bit=int(plan['double_bits'][step-1]),cycles=cycles,prefill=s['cold_prefill_child_cycles']*cold,roots=9*load,ntt=s['ntt_controller_cycles'],post=s['post_child_cycles'],control=7 if cold else 5,profile_loads=int(load),profile_hits=int(not load))
        rows.append('ANEXT_SOAK_STEP '+json.dumps(row))
        if step in checks:
            check(step)
            if negative=='boundary':return '\n'.join(rows)+'\n',oracle,ref,'SOAK_BOUNDARY_MISMATCH step=2 digit=0\n',1
    footer=dict(case_id=plan['case_id'],mode='continuous',start=0,end=4,operations=4,doubles=plan['double_bits'].count('1'),readbacks=3,cycles=total,resets=1,loaded_digits=32,cold_prefill=2,warm_prefill=2,cache_cold=1,cache_warm=3)
    rows.append('ANEXT_SOAK_PASS '+json.dumps(footer));return '\n'.join(rows)+'\n',oracle,ref,'',0

class SoakAdaptation(unittest.TestCase):
    def test_host_delta(self):
        self.assertFalse(verify()['native_pass'])
        self.assertIn('SOAK_CANONICAL_READ_INVALIDATES_PREFILL',expected())
        for port in ('d.start','d.load_we','d.read_en','d.conversion_cycles','d.crt_cycles'):self.assertNotIn(port,expected())
    def test_numeric_donor_contract_and_new_counters(self):
        for negative in ('none','boundary','loaded-state'):
            text,oracle,ref,err,rc=fixture(negative);converted,metrics=normalise(text,oracle,ref)
            ref.validate_rows(converted,err,rc,dict(negative=negative),oracle)
            if negative=='none':self.assertEqual(metrics['cold_prefill'],2)
    def test_wrong_checkpoint_transition_rejected(self):
        text,oracle,ref,_,_=fixture();bad=text.replace('"prefill": 12','"prefill": 0',1)
        self.assertNotEqual(bad,text)
        with self.assertRaises(ValueError):normalise(bad,oracle,ref)
        with self.assertRaises(ValueError):normalise(text.replace('"cache_cold": 1','"cache_cold": 2'),oracle,ref)

if __name__=='__main__':unittest.main()
