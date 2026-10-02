import unittest
from fpga.reference.anext_representative_source_v1 import verify
from fpga.reference.anext_representative_output_v1 import validate
from fpga.reference.track_a4_representative_recipe_v1 import geometry,materialize
from fpga.reference.anext_composition_contract_v1 import schedule

def fixture(aw):
    g=geometry(aw);s=schedule(aw);rows=[];latencies=[]
    for identity in g['identities']:
        cold,load=identity['cold'],identity['load'];total=s['warm_backend']+(s['cold_cached_backend']-s['warm_backend'])*cold+9*load
        row=dict(**identity,latency=total+2,total=total,prefill=s['cold_prefill_child_cycles']*cold,root=9*load,ntt=s['ntt_controller_cycles'],post=s['post_child_cycles'],seed=0)
        latencies.append(total+2);rows.append('A4_CORE_SQUARE '+' '.join(f'{k}={v}' for k,v in row.items()))
    footer={k:g[k] for k in ('aw','commands','squares','cold_squares','profile_loads','readbacks','hold_checks')}
    footer.update(ticks=sum(latencies)+1000,max_latency=max(latencies)+100)
    return '\n'.join(rows+['A4_CORE_PASS '+' '.join(f'{k}={v}' for k,v in footer.items())])+'\n'

class Representative(unittest.TestCase):
    def test_exact_top_only_harness(self):self.assertEqual(verify()['recipe_changes'],0)
    def test_scalar_schedules(self):
        for aw in (5,8,16):
            self.assertEqual(validate(fixture(aw),'',0,dict(mode='representative',aw=aw),{})['footer']['squares'],16)
        with self.assertRaises(ValueError):materialize(1,0,131077,65536)
    def test_negative_outputs(self):
        text=fixture(16);cfg=dict(mode='representative',aw=16)
        for change in (text.replace('seed=0','seed=815',1),text.replace('root=9','root=8743',1),text.replace('ntt=17709','ntt=20558',1),text.replace('total=25989','total=25990',1),text+'extra\n',text.split('\n',1)[1],text.rstrip('\n')):
            self.assertNotEqual(change,text)
            with self.assertRaises(ValueError):validate(change,'',0,cfg,{})
        with self.assertRaises(ValueError):validate(text,'bad',0,cfg,{})
        with self.assertRaises(ValueError):validate(text,'',1,cfg,{})

if __name__=='__main__':unittest.main()
