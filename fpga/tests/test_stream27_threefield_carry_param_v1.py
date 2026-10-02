"""Source/scalar-only geometry, exact parent identity and strict contracts."""
import json
import random
import unittest
from fpga.reference import stream27_blockcarry_param_model_v1 as proof
from fpga.reference import stream27_threefield_carry_param_v1 as compiler
from fpga.reference import stream27_threefield_carry_v1 as parent
from fpga.reference import stream27_threefield_carry_param_native_v1 as native
from fpga.reference import stream27_threefield_carry_param_prepare_v1 as prepare
from fpga.reference import stream27_shared_field_v3 as field
from fpga.reference.stream_ntt_blockwrap2_proposal import carry_serial,carry_split

class CarryParam(unittest.TestCase):
    def test_exact_RTL_delta_and_width_bounds(self):
        result=proof.parent_identity();self.assertEqual(result['status'],'PASS_source_scalar_equivalence')
        self.assertEqual(len(result['checked']),48)
        for r in result['checked']:self.assertLess(r['A'],1<<77);self.assertLess(r['q'],1<<47)
        for p in (1,2,4,32):
            with self.assertRaisesRegex(ValueError,'QUALIFIED_GEOMETRY'):proof.bounds(256,p,1000000000)

    def test_P16_wrapper_functional_source_identity(self):
        for n in (32,256):
            bundles=[field.prepare(n,16,f) for f in range(3)]
            top,old=parent.source(n,bundles);newtop,new=compiler.source(n,16,bundles)
            a=new.index('\n function automatic integer reverse_lane');b=new.index(' endfunction',a)+len(' endfunction');new=new[:a]+new[b:]
            for x,y in [(newtop,top),('[AW-$clog2(P)-1:0]','[AW-5:0]'),('ROW_W=AW-$clog2(P)','ROW_W=AW-4'),
                ('genefer_stream27_blockcarry_setup_param_v1 #(.AW(AW),.P(P))','genefer_track_a4_setup_v1 #(.AW(AW))'),
                ('genefer_stream27_blockcarry_lane_param_v1 #(.AW(AW),.P(P))','genefer_track_a4_blockcarry_lane_v1 #(.AW(AW))'),
                ('// Static inverse physical lane reverse(b,log2(P)) -> natural block b.\n  localparam int PHYSICAL=reverse_lane(b);',
                 '// Static inverse physical lane reverse(b,4) -> natural block b.\n  localparam int PHYSICAL=((b&1)<<3)|((b&2)<<1)|((b&4)>>1)|((b&8)>>3);')]:new=new.replace(x,y)
            self.assertEqual(new,old)
        for p in (8,16):
            bits=p.bit_length()-1
            for lane in range(p):
                reverse=int(f'{lane:0{bits}b}'[::-1],2)
                self.assertEqual(int(f'{reverse:0{bits}b}'[::-1],2),lane)

    def test_signed_cold_and_measured_unsigned_sources(self):
        from fpga.reference.stream27_p8_warm_native_v1 import verify
        measured=verify();full=field.prepare(65536,8,0,mode='warm',allow_full_constants=True)
        self.assertEqual(full['generated_sha256'],measured['source_sha256'])
        for n in (32,256):
            warm=compiler.prepare(n,8);signed=compiler.prepare(n,8,mode='warm_signed')
            for f in range(3):
                u=field.prepare(n,8,f);s=field.prepare(n,8,f,mode='warm_signed')
                for name,raw in u['files'].items():
                    if name!=u['top']+'.sv':self.assertEqual(raw,s['files'][name])
                old='for(int lane=0;lane<LANES;lane=lane+1)if(data_in[lane*32+:32]>=digit_base)admission_bad=1;'
                new="for(int lane=0;lane<LANES;lane=lane+1)if(data_in[lane*32+:32]>=digit_base && data_in[lane*32+:32]!=32'hffffffff)admission_bad=1;"
                self.assertEqual(u['files'][u['top']+'.sv'].replace(old,new).replace('module '+u['top']+' #','module '+s['top']+' #',1),s['files'][s['top']+'.sv'])
            self.assertNotEqual(warm['top'],signed['top']);self.assertEqual(warm['geometry'],signed['geometry'])

    def test_serial_scalar_split_equivalence_and_timing(self):
        rng=random.Random(0xB8A420261001)
        for n in (32,256):
            for p in (8,16):
                for base in (proof.minimum_base(n,p),1000000000):
                    A=proof.bounds(n,p,base)['A']
                    for coefficients in ([A]*n,[-A]*n,[(-1 if j&1 else 1)*A for j in range(n)],
                                         [rng.randrange(-A,A+1) for _ in range(n)]):
                        serial,_=carry_serial(coefficients,base,p);split,_=carry_split(coefficients,base,p)
                        self.assertEqual(serial,split)
        expected={(5,8):(122,128,129,127,129),(8,8):(220,254,255,221,255)}
        for (aw,p),calendar in expected.items():
            g=compiler.prepare(1<<aw,p)['geometry'];self.assertEqual(tuple(g[k] for k in ('first_digit','boundary_output','carry_done','warm_interval','next_correction_accept')),calendar)
            self.assertEqual(g['first_digit'],g['carry_accept']+25)

    def test_native_independent_oracle_monitor_and_negative(self):
        for aw,p in ((5,16),(8,16),(5,8),(8,8)):
            manifest,files=prepare.role(aw,p);cpp=files[native.CPP].decode();sv=files['rtl/'+native.PROBE+'.sv'].decode()
            self.assertIn('I carry=0;',cpp);self.assertNotIn('previous2_q2',cpp)
            self.assertIn('a[j]=SIGNED_COLD && x.digits[j]==0xffffffffu ? -I(1)',cpp)
            self.assertIn('if(kind==5)x.digits[3]=0xffffffffu;',cpp)
            self.assertIn('if(kind==6)x.digits[N-1]=0xffffffffu;',cpp)
            self.assertIn('got==expected+1',cpp);self.assertIn('tick<f.start+SINK+T-1',cpp)
            self.assertIn('actual.field_owners[2]',sv)
            self.assertEqual('parent (' in sv,p==16)
            self.assertEqual(manifest['build']['parameters'],dict(AW=aw,P=p,CONTEXTS=1))
            self.assertEqual([s['expected_returncode'] for s in manifest['steps']],[0,0,1,1])
            self.assertEqual(manifest['carry_param']['counts'],native.counts(aw,p))

    def test_strict_typed_contracts_and_mutants(self):
        for aw,p in ((5,16),(8,16),(5,8),(8,8)):
            for mode in ('normal','minimum','oracle','owner'):
                c=native.contract(aw,p,mode);config=dict(aw=aw,p=p,mode=mode)
                self.assertEqual(native.validate(c['stdout'],c['stderr'],c['returncode'],config,{})['status'],'PASS_expected_contracts')
                for stdout,stderr,rc in ((c['stdout']+'extra',c['stderr'],c['returncode']),
                    (c['stdout'],c['stderr']+'extra',c['returncode']),(c['stdout'],c['stderr'],1-c['returncode'])):
                    with self.assertRaisesRegex(ValueError,'TYPED_OUTPUT'):native.validate(stdout,stderr,rc,config,{})
            c=native.contract(aw,p,'normal')
            with self.assertRaisesRegex(ValueError,'TYPED_OUTPUT'):native.validate(c['stdout'].replace('peak_owners=1','peak_owners=2'),'',0,dict(aw=aw,p=p,mode='normal'),{})

if __name__=='__main__':unittest.main()
