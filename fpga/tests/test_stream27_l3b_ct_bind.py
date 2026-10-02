from copy import deepcopy
import json
import re
import unittest
from fpga.reference import stream27_l3b_ct_bind as b
from fpga.reference import stream27_l3b_ct_field_native as n
from fpga.reference import stream27_l3b_ct_fault as fault
from fpga.reference import stream27_montgomery_fused_model as math


class L3bCT(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parents={f:n.field_bundle(8,f,enabled=0) for f in range(3)}

    def test_zero_complete_copy_and_literal_enable(self):
        original=self.parents[0];self.assertEqual(b.bind(original),original)
        result=b.bind(original);result['files'].clear();self.assertTrue(original['files'])
        for value in (True,False,2,'1',None):
            with self.assertRaises(ValueError):b.bind(original,enabled=value)

    def test_only_forward_instances_and_private_leaf_change(self):
        for f,parent in self.parents.items():
            new=b.bind(parent,enabled=1);meta=new['l3b_ct_fused'];ct=meta['forward_module']
            self.assertEqual(meta['instances'],64)
            self.assertEqual(new['geometry'],parent['geometry']);self.assertEqual(new['parameters'],parent['parameters'])
            self.assertEqual(new['top'],parent['top'])
            self.assertEqual(re.sub(r'\b'+b.TOP+r'\b',b.OLD,new['files'][ct]),parent['files'][ct])
            for name,text in parent['files'].items():
                if name!=ct:self.assertEqual(new['files'][name],text)
            self.assertEqual(set(new['files'])-set(parent['files']),{b.NEW.split('/')[-1]})
            for unchanged in ('GS_changed','point_changed','correction_changed','reset_policy_changed','calendar_changed'):
                self.assertFalse(meta[unchanged])
            self.assertFalse(meta['whole_GO']);self.assertTrue(meta['scalar_area_not_field_credit'])

    def test_full_current_parent_matches_captured_measured_field(self):
        current=n.field_bundle(16,0,enabled=0)
        project=b.ROOT/'artifacts/s4-diet-warm-p16-f0-v1/project'
        m=json.loads((project/'manifest.json').read_text())
        self.assertEqual(current['generated_sha256'],m['source_sha256'])
        self.assertEqual(len(current['files']),25)
        fused=b.bind(current,enabled=1)
        self.assertEqual(fused['l3b_ct_fused']['instances'],128)

    def test_donor_drift_mode_or_GS_binding_is_rejected(self):
        for change in ('leaf','mode','GS','already'):
            donor=deepcopy(self.parents[0])
            if change=='leaf':donor['files'][b.OLD_FILE]+='\n'
            elif change=='mode':donor['parameters']['CORR_SERIAL_BFS']=0
            elif change=='already':donor['l3b_ct_fused']={'enabled':1}
            else:
                ct=next(k for k in donor['files'] if k.startswith('genefer_stream28_merged_ct'))
                donor['files'][ct]=donor['files'][ct].replace(".gs(1'b0)",".gs(1'b1)",1)
            donor['generated_sha256']={k:b.sha(v.encode()) for k,v in donor['files'].items()}
            with self.assertRaises(ValueError):b.bind(donor,enabled=1)

    def test_direct_scalar_residue_range_and_sign_mutant(self):
        checked=0;witnesses=0
        for p in math.FIELDS:
            vals=(0,1,p//2,p-1,p,p+1,2*p-1)
            roots=(0,1,p//2,p-1)
            rinv=pow(1<<32,-1,p)
            for u in vals:
                for v in vals:
                    for w in roots:
                        out=math.butterfly_sign(u,v,w,p,0)
                        expected=((u+v*w*rinv)%p,(u-v*w*rinv)%p)
                        self.assertEqual(tuple(x%p for x in out),expected)
                        self.assertTrue(all(0<=x<2*p for x in out));checked+=1
                        raw=math.raw_montgomery(v,w,p);total=u%p+raw
                        if total<0:
                            wrong=total&((1<<28)-1)
                            self.assertNotEqual(wrong%p,expected[0]);witnesses+=1
        self.assertEqual(checked,588);self.assertGreater(witnesses,0)

    def test_normal_typed_contract_and_single_source_mutant(self):
        normal,files=n.role(8,0);mutant,changed=n.role(8,0,mutant=True)
        self.assertEqual(normal['steps'][0]['expected_returncode'],0)
        self.assertEqual(mutant['steps'][0]['expected_returncode'],1)
        self.assertIn('physical_words=2304',normal['steps'][0]['expected_stdout'])
        leaf='rtl/'+b.NEW.split('/')[-1]
        self.assertNotEqual(files[leaf],changed[leaf])
        for name in normal['build']['sv_sources']:
            if name!=leaf and 'normal_aw8' not in name:self.assertEqual(files[name],changed[name])
        self.assertEqual(normal['build']['parameters'],mutant['build']['parameters'])
        self.assertEqual(normal['l3b_field']['geometry'],mutant['l3b_field']['geometry'])

    def test_numeric_fault_witness_fail_closed(self):
        config=dict(aw=8,p=16,field=0,mutant='zero-ct-sum')
        line='S4_DATA case=1 tick=150 lane=0 expected=1 actual=0\n'
        self.assertEqual(fault.validate('',line,1,config,{})['status'],'PASS_expected_contracts')
        for stdout,stderr,rc,cfg in (('extra',line,1,config),('',line,0,config),('',line+'extra\n',1,config),
                ('','S4_ERROR tick=150\n',1,config),('',line.replace('lane=0','lane=16'),1,config),
                ('',line.replace('actual=0','actual=1'),1,config),('',line,1,dict(config,p=True))):
            with self.assertRaises(ValueError):fault.validate(stdout,stderr,rc,cfg,{})


if __name__=='__main__':unittest.main()
