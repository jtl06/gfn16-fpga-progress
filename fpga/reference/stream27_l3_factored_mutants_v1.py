"""Separate actual-RTL mutant detection; correct leaf remains frozen."""
import argparse
import re
from pathlib import Path
from fpga.reference import stream27_l3_factored_native_v1 as normal
s=normal.s;ROOT=s.ROOT
SELF='reference/stream27_l3_factored_mutants_v1.py'
TOP='genefer_stream27_l3_factored_mutants_v1'
SV='rtl/tb/'+TOP+'.sv';CPP='rtl/tb/stream27_l3_factored_mutants_v1.cpp'
MUTATIONS=(('carry','+27\'(carry_s2)','+27\'(1\'b0)'),
 ('inverse','assign m_high=lo[31:K]-lo_coeff;','assign m_high=lo[31:K]+lo_coeff;'),
 ('highbit','lhs[27] ? {1\'b0,rhs,27\'b0}','1\'b0 ? {1\'b0,rhs,27\'b0}'),
 ('latency','out_valid<=valid_pipe[2];','out_valid<=valid_pipe[1];'))
def generated_sv():
    normal.verify_pins();base=(ROOT/s.RTL).read_text().split('endmodule',1)[0]+'endmodule\n'
    name='genefer_stream27_montgomery_factored_core_v1';copies=[]
    body=f'''// Deliberate arithmetic/control mutants, native test only; never a fitted candidate.
module {TOP} #(parameter logic [31:0] P=32'd104857601,Q=32'd4190109697)(
 input logic clk,rst_n,in_valid,input logic [27:0] lhs,input logic [26:0] rhs,
 output logic [4:0] out_valid,output logic [31:0] correct_result,bad_carry,bad_inverse,bad_highbit,bad_latency
);
 {name} #(.P(P),.Q(Q)) correct(.clk,.rst_n,.in_valid,.lhs,.rhs,.out_valid(out_valid[0]),.result(correct_result));
'''
    for i,(kind,before,after) in enumerate(MUTATIONS):
        s.need(base.count(before)==1,'L3_UNIQUE_MUTATION '+kind)
        changed=base.replace(before,after).replace(name,name+'_'+kind)
        s.need(changed.replace(name+'_'+kind,name).replace(after,before)==base,'L3_MUTATION_REVERSIBLE '+kind)
        copies.append(changed)
        body+=f' {name}_{kind} #(.P(P),.Q(Q)) mutant_{kind}(.clk,.rst_n,.in_valid,.lhs,.rhs,.out_valid(out_valid[{i+1}]),.result(bad_{kind}));\n'
    return body+'endmodule\n'+''.join(copies)
def generated_cpp():
    t=(ROOT/normal.DONOR).read_text().replace('genefer_montgomery_mul28x27_sparse_pipe_v2',TOP).replace('d.result','d.correct_result')
    def once(before,after):
        nonlocal t
        s.need(t.count(before)==1,'L3_MUTANT_DONOR_SITE '+before);t=t.replace(before,after)
    once('uint32_t held=0;','uint32_t held=0,seen=0;')
    once('bool(d.out_valid)!=due','bool(d.out_valid&1u)!=due')
    once('if(due) {','''const uint32_t bad[4]={d.bad_carry,d.bad_inverse,d.bad_highbit,d.bad_latency};
        for(unsigned i=0;i<4;i++) if(bool(d.out_valid&(2u<<i))!=due ||
            (due && bad[i]!=pending.front().expected)) seen|=1u<<i;
        if(due) {''')
    once('if(!pending.empty() || checked<10000 || high_inputs==0 || canceled==0)',
         'if(!pending.empty() || checked<10000 || high_inputs==0 || canceled==0 || seen!=15)')
    once('PASS_MONT28 P=','PASS_L3_MUTANTS P=')
    once('<<" edges="<<edge<<"\\n";','<<" edges="<<edge<<" detected="<<seen<<"\\n";')
    return t
def verify():
    s.need((ROOT/SV).read_text()==generated_sv() and (ROOT/CPP).read_text()==generated_cpp(),'L3_MUTANT_EXACT_SOURCE')
def validate(stdout,stderr,rc,config,assets):
    s.need(set(config)=={'p'} and config['p'] in normal.HIGH and not assets,'L3_MUTANT_CONFIG')
    expected=f"PASS_L3_MUTANTS P={config['p']} checked=16925 canceled=224 holds=3166 high_inputs={normal.HIGH[config['p']]} edges=20091 detected=15\n"
    s.need(rc==0 and stdout==expected and stderr=='','L3_ALL_FOUR_RTL_MUTANTS_DETECTED')
    return dict(status='PASS_expected_contracts',mutants_detected=[m[0] for m in MUTATIONS],
       checked_reference_products=16925,p=config['p'],promotion_allowed=False)
def role(p):
    verify();m,files=normal.role(p)
    names=(SELF,SV,CPP);files.update({n:(ROOT/n).read_bytes() for n in names})
    m['sources']={n:s.sha(raw) for n,raw in files.items()}
    m['build'].update(top=TOP,sv_sources=[SV,s.RTL],cpp_source=CPP)
    m['steps']=[dict(name='deliberate-four-rtl-mutant-detection',argv=['{exe}'],expected_returncode=0,
        validator=dict(source=SELF,function='validate',config=dict(p=p),assets={}))]
    m['test_role']='deliberate_fault'
    m['scope']='Native actual four mutated arithmetic/control leaves rejected against independent modular oracle; normal leaf unchanged. No integration/physical claim.'
    return m,files
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--write-fixture',action='store_true');p.add_argument('--p',type=int,choices=tuple(normal.HIGH))
    p.add_argument('--output',type=Path);p.add_argument('--budget',type=Path);a=p.parse_args()
    if a.write_fixture:
        for n,text in ((SV,generated_sv()),(CPP,generated_cpp())):
            s.need(not (ROOT/n).exists(),'L3_MUTANT_FRESH_FIXTURE')
            with (ROOT/n).open('x') as f:f.write(text)
        verify();print('deliberate_mutants_source_ready')
    else:print(normal.prepare(a.output,a.p,a.budget,role_builder=role,identity='mutants2'))
