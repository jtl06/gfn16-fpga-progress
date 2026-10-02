"""Separate r75 test-only input-bundle, normalization and reset mutants."""
import argparse
import json
from pathlib import Path
from fpga.reference import stream27_final_pair_inputreg_native as n

ROOT=n.ROOT;TOP='genefer_stream27_final_pair_inputreg_mutants_v2'
SV='rtl/tb/'+TOP+'.sv';CPP='rtl/tb/stream27_final_pair_inputreg_mutants_v2.cpp'
SELF='reference/stream27_final_pair_inputreg_mutants.py'
MUTATIONS=(
    ('root', '.normalized_lower_root(lower_root_q)', '.normalized_lower_root(normalized_lower_root)'),
    ('operand', '.u(u_q)', '.u(u)'),
    ('valid', '.in_valid(input_valid_q)', '.in_valid(in_valid)'),
    ('reset', 'if(!rst_n)input_valid_q<=0;', 'if(!rst_n)input_valid_q<=1;'),
    ('scale', '.UPPER_SCALE(UPPER_SCALE)', ".UPPER_SCALE(32'd1)"))

def generated_sv():
    n.verify();base=(ROOT/n.RTL).read_text();copies=[]
    head=f'''// Test-only five actual mutants; never field-bound or fitted.
module {TOP} #(
 parameter logic [31:0] P=32'd104857601,Q=32'd4190109697,UPPER_SCALE=32'd1
)(input logic clk,rst_n,in_valid,input logic [31:0] u,v,normalized_lower_root,
 output logic old_valid,new_valid,old_error,new_error,
 output logic [31:0] old_y0,old_y1,new_y0,new_y1,
 output logic [4:0] bad_valid,bad_error,output logic [159:0] bad_y0,bad_y1);
 {n.TOP} #(.P(P),.Q(Q),.UPPER_SCALE(UPPER_SCALE)) good(
  .clk,.rst_n,.in_valid,.u,.v,.normalized_lower_root,
  .old_valid,.new_valid,.old_error,.new_error,.old_y0,.old_y1,.new_y0,.new_y1);
'''
    name=Path(n.RTL).stem
    for k,(kind,before,after) in enumerate(MUTATIONS):
        n.need(base.count(before)==1,'FINAL_PAIR_MUTANT_UNIQUE_SITE '+kind)
        changed=base.replace(before,after,1).replace(name,name+'_'+kind)
        reverse=changed.replace(name+'_'+kind,name).replace(after,before,1)
        n.need(reverse==base,'FINAL_PAIR_MUTANT_BYTE_REVERSE '+kind);copies.append(changed)
        head+=f''' {name}_{kind} #(.P(P),.Q(Q),.UPPER_SCALE(UPPER_SCALE)) mutant_{kind}(
  .clk,.rst_n,.in_valid,.u,.v,.normalized_lower_root,
  .out_valid(bad_valid[{k}]),.out_error(bad_error[{k}]),.y0(bad_y0[{32*k}+:32]),.y1(bad_y1[{32*k}+:32]));
'''
    return head+'endmodule\n'+''.join(copies)

def generated_cpp():
    text=(ROOT/n.CPP).read_text().replace(n.TOP,TOP)
    def once(a,b):
        nonlocal text
        n.need(text.count(a)==1,'FINAL_PAIR_MUTANT_CPP_SITE '+a);text=text.replace(a,b,1)
    once('uint32_t held0[2]={}', 'unsigned detected=0;uint32_t held0[2]={}')
    once('d.clk=1;d.eval();need(!d.old_error&&!d.new_error,"FINAL_PAIR_ALIGNMENT_ERROR");',
         '''d.clk=1;d.eval();need(!d.old_error&&!d.new_error,"FINAL_PAIR_ALIGNMENT_ERROR");
        bool good_due=!pending[1].empty()&&pending[1].front().due==edge;
        for(unsigned bad=0;bad<5;bad++)if(bool(d.bad_valid&(1u<<bad))!=good_due ||
            (good_due&&(d.bad_y0[bad]!=pending[1].front().a||d.bad_y1[bad]!=pending[1].front().b)))
            detected|=1u<<bad;''')
    once('std::cout<<"FINAL_PAIR_INPUTREG_PASS', 'need(detected==31,"FINAL_PAIR_FIVE_REAL_MUTANTS_DETECTED");\n    std::cout<<"FINAL_PAIR_INPUTREG_MUTANTS_PASS')
    once('<<" old_latency=5 new_latency=6\\n";', '<<" old_latency=5 new_latency=6 detected="<<detected<<"\\n";')
    return text

def write_source():
    for name,text in ((SV,generated_sv()),(CPP,generated_cpp())):
        path=ROOT/name
        if path.exists():n.need(path.read_text()==text,'FINAL_PAIR_MUTANT_FROZEN_FIXTURE');continue
        with path.open('x') as f:f.write(text)

def role(p):
    n.need((ROOT/SV).read_text()==generated_sv() and (ROOT/CPP).read_text()==generated_cpp(),'FINAL_PAIR_EXACT_MUTANT_FIXTURE')
    manifest,files=n.role(p)
    files.update({name:(ROOT/name).read_bytes() for name in (SV,CPP,SELF)})
    manifest['sources']={name:n.sha(raw) for name,raw in files.items()}
    manifest['build'].update(top=TOP,sv_sources=[SV,*manifest['build']['sv_sources']],cpp_source=CPP)
    stdout=n.expected(p).replace('FINAL_PAIR_INPUTREG_PASS','FINAL_PAIR_INPUTREG_MUTANTS_PASS').rstrip()+' detected=31\n'
    manifest['steps']=[dict(name='deliberate-five-actual-rtl-input-root-operand-valid-reset-scale-mutants',argv=['{exe}'],
        expected_returncode=0,expected_stdout=stdout,expected_stderr='')]
    manifest['test_role']='deliberate_fault'
    manifest['scope']='Test-only actual mutations detected while paired correct arithmetic/latency/reset/hold checks remain strict. No field binding or physical claim.'
    return n.preflight(manifest,files)

def prepare(output,p,budget):
    from fpga.reference import stream27_l3_factored_native_v1 as package
    return package.prepare(output,p,budget,role_builder=role,identity='mutants2',family='stream27-final-pair-inputreg')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--write-source',action='store_true')
    parser.add_argument('--p',type=int,choices=n.FIELDS);parser.add_argument('--output',type=Path);parser.add_argument('--budget',type=Path)
    args=parser.parse_args()
    if args.write_source:write_source();print('five test-only input-register mutants source ready')
    else:print(json.dumps(prepare(args.output,args.p,args.budget),indent=2))
