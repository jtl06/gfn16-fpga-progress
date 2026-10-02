"""Actual isolated P5 RTL mutants, separate from already-submitted normal jobs."""
import argparse
import re
from pathlib import Path
from fpga.reference import stream27_montgomery_fused_native as normal
ROOT=normal.ROOT;need=normal.need;sha=normal.sha
SELF='reference/stream27_montgomery_fused_mutants.py';TOP='genefer_stream27_l3_fused_mutants_v1'
SV='rtl/tb/'+TOP+'.sv';CPP='rtl/tb/stream27_montgomery_fused_mutants_v2.cpp'
TOP2='genefer_stream27_l3_fused_sign_mutants_v1';SV2='rtl/tb/'+TOP2+'.sv';CPP2='rtl/tb/stream27_montgomery_fused_sign_mutants.cpp'
MUTATIONS=(
 ('highbit',"lhs[27] ? {1'b0,rhs,27'b0}","1'b0 ? {1'b0,rhs,27'b0}"),
 ('ct_bias','product_raw})+P30;','product_raw})+30\'sd0;'),
 ('gs_bias','gs_biased=raw29+P29;','gs_biased=raw29+29\'sd0;'),
 ('latency','out_valid<=valid_pipe[2];','out_valid<=valid_pipe[1];'))
MUTATIONS2=(MUTATIONS[0],
 ('ct_sign',"ct_sum<0 ? ct_sum+P29 : ct_sum","ct_sum<0 ? ct_sum+29'sd0 : ct_sum"),MUTATIONS[2],MUTATIONS[3])
def variant_info(variant):
    need(variant in (1,2),'P5_MUTANT_VARIANT')
    return (TOP,SV,CPP,normal.TOP,normal.RAW,MUTATIONS) if variant==1 else (TOP2,SV2,CPP2,normal.TOP2,normal.RAW2,MUTATIONS2)
def generated_sv(variant=1):
    normal.verify(variant);base=normal.rtl(variant);copies=[]
    top,_,_,bf,raw,mutations=variant_info(variant)
    body=f'''// Test-only actual mutants; never bind to a field or fitted candidate.
module {top} #(parameter logic [31:0] P=32'd104857601,Q=32'd4190109697,parameter int TAG_W=32)(
 input logic clk,rst_n,in_valid,gs,input logic [27:0] u,v,input logic [26:0] w,
 input logic [TAG_W-1:0] in_tag,output logic [4:0] out_valid,
 output logic [27:0] correct_y0,correct_y1,
 output logic [TAG_W-1:0] correct_tag,
'''
    body+=',\n'.join(f' output logic [27:0] bad_{kind}_y0,bad_{kind}_y1,output logic [TAG_W-1:0] bad_{kind}_tag' for kind,_,_ in mutations)
    body+='\n);\n'
    body+=f' {bf} #(.P(P),.Q(Q),.TAG_W(TAG_W)) correct(.clk,.rst_n,.in_valid,.gs,.u,.v,.w,.in_tag,.out_valid(out_valid[0]),.y0(correct_y0),.y1(correct_y1),.out_tag(correct_tag));\n'
    for i,(kind,before,after) in enumerate(mutations):
        need(base.count(before)==1,'P5_MUTANT_UNIQUE_SITE '+kind)
        changed=base.replace(before,after,1)
        for name in (bf,raw):changed=changed.replace(name,name+'_'+kind)
        reverse=changed
        for name in (bf,raw):reverse=reverse.replace(name+'_'+kind,name)
        reverse=reverse.replace(after,before,1);need(reverse==base,'P5_MUTANT_BYTE_REVERSE '+kind)
        copies.append(changed)
        body+=f' {bf}_{kind} #(.P(P),.Q(Q),.TAG_W(TAG_W)) mutant_{kind}(.clk,.rst_n,.in_valid,.gs,.u,.v,.w,.in_tag,.out_valid(out_valid[{i+1}]),.y0(bad_{kind}_y0),.y1(bad_{kind}_y1),.out_tag(bad_{kind}_tag));\n'
    return body+'endmodule\n'+''.join(copies)
def generated_cpp(variant=1):
    top,_,_,bf,_,mutations=variant_info(variant)
    text=normal.cpp(variant).replace(bf,top)
    # Exact object symbols only: substring replacement also changed expected.y0.
    names={'y0':'correct_y0','y1':'correct_y1','out_tag':'correct_tag'}
    text=re.sub(r'\bd\.(y0|y1|out_tag)\b',lambda m:'d.'+names[m[1]],text)
    text=text.replace('bool(d.out_valid)','bool(d.out_valid&1u)')
    def once(before,after):
        nonlocal text
        need(text.count(before)==1,'P5_MUTANT_CPP_SITE '+before);text=text.replace(before,after,1)
    once('bool lastvalid=false;','bool lastvalid=false;uint32_t seen=0;')
    checks='''d.clk=1;d.eval();
        const uint32_t bad0[4]={d.bad_highbit_y0,d.bad_ct_bias_y0,d.bad_gs_bias_y0,d.bad_latency_y0};
        const uint32_t bad1[4]={d.bad_highbit_y1,d.bad_ct_bias_y1,d.bad_gs_bias_y1,d.bad_latency_y1};
        const uint32_t badtag[4]={d.bad_highbit_tag,d.bad_ct_bias_tag,d.bad_gs_bias_tag,d.bad_latency_tag};
        for(unsigned i=0;i<4;i++)if(bool(d.out_valid&(2u<<i))!=due ||
            (due && (bad0[i]>=2*P || bad1[i]>=2*P || bad0[i]%P!=pending.front().y0%P ||
                      bad1[i]%P!=pending.front().y1%P || badtag[i]!=pending.front().tag)))seen|=1u<<i;'''
    if variant==2:checks=checks.replace('bad_ct_bias','bad_ct_sign')
    once('d.clk=1;d.eval();',checks)
    prefix='P5_FUSED' if variant==1 else 'P5_FUSED_SIGN'
    once('std::cout<<"'+prefix+'_BFLY_PASS p="', 'require(seen==15,"P5_MUTANT_COVERAGE");\n    std::cout<<"'+prefix+'_MUTANTS_PASS p="')
    once('<<" high_inputs="<<high<<" ct="<<ct<<" gs="<<gs<<"\\n";',
         '<<" high_inputs="<<high<<" ct="<<ct<<" gs="<<gs<<" detected="<<seen<<"\\n";')
    return text
def verify(variant=1):
    _,sv,cpp,_,_,_=variant_info(variant)
    need((ROOT/sv).read_text()==generated_sv(variant) and (ROOT/cpp).read_text()==generated_cpp(variant),'P5_MUTANT_EXACT_FIXTURE')
def write_source(variant=1):
    _,sv,cpp,_,_,_=variant_info(variant)
    for name,text in ((sv,generated_sv(variant)),(cpp,generated_cpp(variant))):
        if (ROOT/name).exists():
            need((ROOT/name).read_text()==text,'P5_MUTANT_FROZEN_SOURCE');continue
        with (ROOT/name).open('x') as f:f.write(text)
    verify(variant)
def validate(stdout,stderr,rc,config,assets):
    variant=config.get('variant',1);_,_,_,_,_,mutations=variant_info(variant)
    need(set(config)==({'p'} if variant==1 else {'p','variant'}) and config['p'] in normal.model.FIELDS and not assets,'P5_MUTANT_CONFIG')
    _,counts=normal.donor.corpus(config['p'])
    prefix='P5_FUSED' if variant==1 else 'P5_FUSED_SIGN'
    expected=f"{prefix}_MUTANTS_PASS p={config['p']} "+' '.join(f'{k}={v}' for k,v in counts.items())+' detected=15\n'
    need(rc==0 and stdout==expected and stderr=='','P5_ALL_FOUR_ACTUAL_RTL_MUTANTS_DETECTED')
    return dict(status='PASS_expected_contracts',mutants_detected=[x[0] for x in mutations],
      checked_reference_outputs=counts['checked'],latency=5,II=1,p=config['p'],promotion_allowed=False)
def role(p,variant=1):
    verify(variant);manifest,files=normal.role(p,variant);top,sv,cpp,_,_,_=variant_info(variant)
    files.update({name:(ROOT/name).read_bytes() for name in (SELF,sv,cpp)})
    manifest['sources']={name:sha(raw) for name,raw in files.items()}
    manifest['build'].update(top=top,sv_sources=[sv,normal.RTL if variant==1 else normal.RTL2],cpp_source=cpp)
    asset=manifest['steps'][0]['argv'][1]
    config=dict(p=p)
    if variant==2:config['variant']=2
    manifest['steps']=[dict(name='deliberate-four-fused-rtl-mutant-detection',argv=['{exe}',asset],expected_returncode=0,
      validator=dict(source=SELF,function='validate',config=config,assets={}))]
    manifest['test_role']='deliberate_fault';manifest['scope']='Actual P5 highbit/CTbias/GSbias/latency mutants detected; no field/fit/promotion claim.'
    return manifest,files
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--write-source',action='store_true');parser.add_argument('--p',type=int,choices=tuple(normal.model.FIELDS))
    parser.add_argument('--output',type=Path);parser.add_argument('--budget',type=Path);parser.add_argument('--variant',type=int,choices=(1,2),default=1);args=parser.parse_args()
    if args.write_source:write_source(args.variant);print('P5 deliberate mutant source ready')
    else:print(normal.package_helper.prepare(args.output,args.p,args.budget,role_builder=lambda p:role(p,args.variant),
       identity='mutants2' if args.variant==1 else 'mutants',family='stream27-l3-fused' if args.variant==1 else 'stream27-l3-fused-sign'))
