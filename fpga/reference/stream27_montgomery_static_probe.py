"""Static streaming CT/GS bindings only; exact arithmetic leaves are unchanged."""
import argparse
from collections import deque
from datetime import datetime,timezone
import json
from pathlib import Path
from fpga.reference import stream27_montgomery_fused_native as n
ROOT=n.ROOT;need=n.need;sha=n.sha;SELF='reference/stream27_montgomery_static_probe.py'
TOP='genefer_stream27_l3_static_direction_probe_v1';SV='rtl/kernel/'+TOP+'.sv'
CPP='rtl/tb/stream27_montgomery_static_normal.cpp';READY='results/throughput-20260929/stream27-l3-static-source-v1/rtl-ready.json'
PINS={'rtl/kernel/genefer_stream27_factored_lazy28_butterfly_v1.sv':'71f629d23214cd0278ebc5027b4245819a7299b207fda8530983e11847d658b9',
 n.RTL2:'65b78b58f68dbf18d857707c4ea00b573989ed13a845dffd14e51fdf8b6720b3',
 n.package_helper.s.RTL:'866c2b19c9e6afbbb56ce71089288334579f90e977ca139b41097d0f9191c690'}
TEXT='''// Static CT/GS sizing: four independent input FF sets; no shared products.
// TAG_W=1 matches current streaming cells. E0 input -> E6 output, II1.
// Only gs constant binding changes; arithmetic definitions stay byte-identical.
module genefer_stream27_l3_static_direction_probe_v1 #(
 parameter logic [31:0] P=32'd104857601,Q=32'd4190109697
)(input logic clk,rst_n,input logic [3:0] in_valid,in_tag,
 input logic [111:0] u,v,input logic [107:0] w,
 output logic [3:0] out_valid,out_tag,output logic [111:0] y0,y1);
 logic [3:0] valid_q,tag_q;logic [111:0] u_q,v_q;logic [107:0] w_q;
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin valid_q<=0;tag_q<=0;u_q<=0;v_q<=0;w_q<=0;end
  else begin valid_q<=in_valid;tag_q<=in_tag;u_q<=u;v_q<=v;w_q<=w;end
 end
 genefer_stream27_factored_lazy28_butterfly_v1 #(.P(P),.Q(Q),.TAG_W(1)) normalized_ct(
  .clk,.rst_n,.in_valid(valid_q[0]),.gs(1'b0),.u(u_q[0+:28]),.v(v_q[0+:28]),.w(w_q[0+:27]),
  .in_tag(tag_q[0]),.out_valid(out_valid[0]),.y0(y0[0+:28]),.y1(y1[0+:28]),.out_tag(out_tag[0]));
 genefer_stream27_fused_sign_lazy28_butterfly_v1 #(.P(P),.Q(Q),.TAG_W(1)) fused_ct(
  .clk,.rst_n,.in_valid(valid_q[1]),.gs(1'b0),.u(u_q[28+:28]),.v(v_q[28+:28]),.w(w_q[27+:27]),
  .in_tag(tag_q[1]),.out_valid(out_valid[1]),.y0(y0[28+:28]),.y1(y1[28+:28]),.out_tag(out_tag[1]));
 genefer_stream27_factored_lazy28_butterfly_v1 #(.P(P),.Q(Q),.TAG_W(1)) normalized_gs(
  .clk,.rst_n,.in_valid(valid_q[2]),.gs(1'b1),.u(u_q[56+:28]),.v(v_q[56+:28]),.w(w_q[54+:27]),
  .in_tag(tag_q[2]),.out_valid(out_valid[2]),.y0(y0[56+:28]),.y1(y1[56+:28]),.out_tag(out_tag[2]));
 genefer_stream27_fused_sign_lazy28_butterfly_v1 #(.P(P),.Q(Q),.TAG_W(1)) fused_gs(
  .clk,.rst_n,.in_valid(valid_q[3]),.gs(1'b1),.u(u_q[84+:28]),.v(v_q[84+:28]),.w(w_q[81+:27]),
  .in_tag(tag_q[3]),.out_valid(out_valid[3]),.y0(y0[84+:28]),.y1(y1[84+:28]),.out_tag(out_tag[3]));
endmodule
'''
CPP_TEXT=r'''#include "Vgenefer_stream27_l3_static_direction_probe_v1.h"
#include "verilated.h"
#include <cstdint>
#include <deque>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#ifndef TEST_P
#define TEST_P 104857601
#endif
static constexpr uint64_t P=TEST_P;
static void require(bool good,const char* why){if(!good)throw std::runtime_error(why);}
static uint64_t power(uint64_t a,uint64_t e){uint64_t r=1;while(e){if(e&1)r=r*a%P;a=a*a%P;e>>=1;}return r;}
template<class T>static void put(T&words,unsigned offset,unsigned width,uint32_t value){
 for(unsigned k=0;k<width;k++){unsigned at=offset+k;uint32_t mask=uint32_t(1)<<(at%32);
  words[at/32]=(words[at/32]&~mask)|(((value>>k)&1)?mask:0);}}
template<class T>static uint32_t get(const T&words,unsigned offset,unsigned width){uint32_t value=0;
 for(unsigned k=0;k<width;k++)value|=((words[(offset+k)/32]>>((offset+k)%32))&1)<<k;return value;}
struct Pending{uint64_t due;uint32_t a,b,tag;};
int main(int argc,char**argv){try{
 VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
 Vgenefer_stream27_l3_static_direction_probe_v1 d{&context};d.eval();
 if(argc==2&&std::string(argv[1])=="--runtime-probe"){
  std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
  return context.threads()==1&&d.threads()==1?0:2;}
 require(argc==2,"STATIC_ARGS");std::ifstream input(argv[1]);std::string magic;uint64_t field,events;
 input>>magic>>field>>events;require(magic=="LAZYBFLY1"&&field==P&&events>0,"STATIC_HEADER");
 const uint64_t ri=power((uint64_t(1)<<32)%P,P-2);std::deque<Pending> pending[4];
 uint64_t checked[4]={0,0,0,0},cancelled=0,holds=0;uint32_t last0[4]={},last1[4]={},lasttag=0,lastvalid=0;
 for(uint64_t edge=0;edge<events;edge++){
  unsigned reset,valid,ignored_form;uint64_t u,v,w,tag;
  require(bool(input>>reset>>valid>>ignored_form>>u>>v>>w>>tag),"STATIC_SHORT_INPUT");
  require(reset<2&&valid<2&&ignored_form<2&&u<2*P&&v<2*P&&w<P&&tag<(uint64_t(1)<<32),"STATIC_INPUT_RANGE");
  const unsigned mask=valid?(edge%5==0?15u:(15u^(1u<<(edge%4)))):0;
  d.clk=0;d.rst_n=reset;d.in_valid=mask;d.in_tag=0;
  for(unsigned word=0;word<4;word++){d.u[word]=0;d.v[word]=0;d.w[word]=0;}
  for(unsigned cell=0;cell<4;cell++){
   put(d.u,28*cell,28,u);put(d.v,28*cell,28,v);put(d.w,27*cell,27,w);
   const unsigned token=(tag^(edge>>(cell+1))^cell)&1;d.in_tag|=token<<cell;
   if(!reset){cancelled+=pending[cell].size();pending[cell].clear();last0[cell]=last1[cell]=0;}
  }
  d.eval();if(!reset){lastvalid=0;lasttag=0;}
  require(d.out_valid==lastvalid&&d.out_tag==lasttag,"STATIC_BEFORE_EDGE_METADATA");
  for(unsigned cell=0;cell<4;cell++){
   require(get(d.y0,28*cell,28)==last0[cell]&&get(d.y1,28*cell,28)==last1[cell],"STATIC_BEFORE_EDGE_PAYLOAD");
   if(reset&&(mask&(1u<<cell))){uint64_t a,b;
    if(cell>=2){a=(u+v)%(2*P);b=(((u+2*P-v)%(2*P))*w%P)*ri%P;}
    else{uint64_t t=(v*w%P)*ri%P;a=u%P+t;b=u%P+P-t;}
    pending[cell].push_back({edge+6,uint32_t(a),uint32_t(b),(d.in_tag>>cell)&1u});}
  }
  d.clk=1;d.eval();unsigned expected_valid=0;
  for(unsigned cell=0;cell<4;cell++){
   bool due=!pending[cell].empty()&&pending[cell].front().due==edge;expected_valid|=unsigned(due)<<cell;
   uint32_t a=get(d.y0,28*cell,28),b=get(d.y1,28*cell,28),token=(d.out_tag>>cell)&1;
   if(due){Pending expected=pending[cell].front();pending[cell].pop_front();
    require(a<2*P&&b<2*P,"STATIC_PUBLIC_RANGE");
    require(a%P==expected.a%P&&b%P==expected.b%P&&token==expected.tag,"STATIC_MODE_VALUE_TAG");
    if(cell%2==0)require(a==expected.a&&b==expected.b,"STATIC_NORMALIZED_BIT_EXACT");
    last0[cell]=a;last1[cell]=b;lasttag=(lasttag&~(1u<<cell))|(token<<cell);checked[cell]++;
   }else{require(a==last0[cell]&&b==last1[cell]&&token==((lasttag>>cell)&1),"STATIC_INVALID_HOLD");holds++;}
  }
  require(d.out_valid==expected_valid,"STATIC_VALID_E6");lastvalid=expected_valid;
 }
 std::string extra;require(!(input>>extra)&&input.eof(),"STATIC_TAIL");
 for(unsigned cell=0;cell<4;cell++)require(pending[cell].empty()&&checked[cell]>3000,"STATIC_COVERAGE");
 std::cout<<"P5_STATIC_PASS p="<<P<<" events="<<events<<" normalized_ct="<<checked[0]<<" fused_ct="<<checked[1]
  <<" normalized_gs="<<checked[2]<<" fused_gs="<<checked[3]<<" cancelled="<<cancelled<<" holds="<<holds<<"\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
'''
def counts(p):
    corpus,_=n.donor.corpus(p);lines=corpus.splitlines();events=int(lines[0].split()[2]);pending=[deque() for _ in range(4)]
    checked=[0]*4;cancelled=holds=0
    for edge,line in enumerate(lines[1:]):
        reset,valid,*_=map(int,line.split());mask=(15 if edge%5==0 else 15^(1<<(edge%4))) if valid else 0
        for cell in range(4):
            if not reset:cancelled+=len(pending[cell]);pending[cell].clear()
            if reset and mask&(1<<cell):pending[cell].append(edge+6)
            if pending[cell] and pending[cell][0]==edge:pending[cell].popleft();checked[cell]+=1
            else:holds+=1
    need(all(not q for q in pending),'STATIC_TAIL_LEDGER')
    return dict(events=events,normalized_ct=checked[0],fused_ct=checked[1],normalized_gs=checked[2],fused_gs=checked[3],cancelled=cancelled,holds=holds)
def verify():
    for name,pin in PINS.items():need(sha((ROOT/name).read_bytes())==pin,'STATIC_EXACT_UNCHANGED_ARITHMETIC '+name)
    need((ROOT/SV).read_text()==TEXT and (ROOT/CPP).read_text()==CPP_TEXT,'STATIC_EXACT_WRAPPER_AND_BENCH')
def write_source():
    for name,text in ((SV,TEXT),(CPP,CPP_TEXT)):
        need(not (ROOT/name).exists(),'STATIC_FRESH_SOURCE')
        with (ROOT/name).open('x') as f:f.write(text)
    snapshot={SV:sha(TEXT.encode())};path=ROOT/READY;path.parent.mkdir(parents=True,exist_ok=True)
    now=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    n.package_helper.dump(path,dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id='stream27-l3-static-direction-v1',
      source_snapshot=snapshot,candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),rtl_ready_at_utc=now))
    verify();return now
def validate(stdout,stderr,rc,config,assets):
    need(set(config)=={'p'} and config['p'] in n.model.FIELDS and not assets,'STATIC_TYPED_CONFIG')
    c=counts(config['p']);expected=f"P5_STATIC_PASS p={config['p']} "+' '.join(f'{k}={v}' for k,v in c.items())+'\n'
    need(rc==0 and stdout==expected and stderr=='','STATIC_NORMAL_FOUR_MODE_ALIGNMENT')
    return dict(status='PASS_expected_contracts',**c,wrapper_latency=6,butterfly_latency=5,II=1,TAG_W=1,
      modes=[0,0,1,1],arithmetic_changed=False,promotion_allowed=False)
def role(p):
    verify();corpus,_=n.donor.corpus(p);asset=f'rtl/tb/p5-static-{p}.txt'
    paths=(SV,CPP,*PINS,SELF,n.SELF,'reference/stream27_montgomery_fused_model.py',
      'reference/stream27_l3_factored_native_v1.py','reference/stream27_l3_factored_model_v1.py',
      'reference/lazy28_butterfly_v1.py','reference/__init__.py',READY)
    files={name:(ROOT/name).read_bytes() for name in paths};files[asset]=corpus.encode()
    return dict(schema='native-source-gate-v1',status='prepared_not_executed',source_root='/not-a-dispatch-path/static/fpga',
      output_parent='/not-a-dispatch-path/static/output',sources={name:sha(raw) for name,raw in files.items()},
      build=dict(top=TOP,sv_sources=[SV,*PINS],cpp_source=CPP,parameters=dict(P=p,Q=(2-p)%(1<<32)),
        cflags=['-std=c++17','-O2','-Werror=return-type',f'-DTEST_P={p}']),
      probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
      steps=[dict(name='static-direction-normal-values-mode-tags-six-edges',argv=['{exe}',asset],expected_returncode=0,
        validator=dict(source=SELF,function='validate',config=dict(p=p),assets={}))],
      test_role='normal',rtl_readiness=json.loads((ROOT/READY).read_text()),arithmetic_pins=PINS,
      scope='Only static gs binding and independent input FF wrapper; actual TAG_W1/E6 alignment and bit-exact normalized/modP fused values. No field/clock/area claim.'),files
def native_gates(fields=(0,)):
    from fpga.reference import stream27_montgomery_fused_probe as dynamic
    refs=dynamic.gates(2)
    # Sizing is F0 only: its actual wrapper gate plus all-field unchanged
    # arithmetic evidence suffice. Other wrapper fields qualify in parallel.
    for field in fields:
        qid=f'stream27-l3-static-f{field}-normal2-q1-v1';path=ROOT/'queue/evidence'/qid/'gate-receipt.json';raw=path.read_bytes();g=json.loads(raw)
        need(g['id']==qid and g['status']=='PASS_expected_contracts','STATIC_ACTUAL_WRAPPER_NATIVE')
        v=g['steps'][0]['validation'];need(v['wrapper_latency']==6 and v['modes']==[0,0,1,1] and v['TAG_W']==1,'STATIC_NATIVE_BINDING')
        refs.append(dict(path=str(path),sha256=sha(raw),fields=dict(id=qid,status='PASS_expected_contracts')))
    return refs
def prepare_project(destination):
    from fpga.cloud import plain_fit_v5 as fit
    from fpga.tools import fit_dispatch
    verify();native_gates();destination=Path(destination).resolve();need(destination.is_relative_to(ROOT) and not destination.exists(),'STATIC_FRESH_PROJECT')
    rtl=destination/'rtl';rtl.mkdir(parents=True);sources={Path(name).name:(ROOT/name).read_bytes() for name in (SV,*PINS)}
    for name,raw in sources.items():
        with (rtl/name).open('xb') as f:f.write(raw)
    donor=ROOT/'results/throughput-20260929/stream27-l3-fused-sign-butterfly-f0-source-v1/project'
    qsf=(donor/'probe.qsf').read_text();start=qsf.index('set_global_assignment -name TOP_LEVEL_ENTITY ')
    qsf=qsf[:start]+f'set_global_assignment -name TOP_LEVEL_ENTITY {TOP}\n'
    qsf+=''.join(f'set_global_assignment -name SYSTEMVERILOG_FILE rtl/{name}\n' for name in sources)
    qsf+='set_parameter -name P 104857601\nset_parameter -name Q 4190109697\n'
    ports=('rst_n','in_valid[*]','in_tag[*]','u[*]','v[*]','w[*]','out_valid[*]','out_tag[*]','y0[*]','y1[*]')
    qsf+=''.join(f'set_instance_assignment -name VIRTUAL_PIN ON -to {{{port}}}\n' for port in ports)
    controls={name:(donor/name).read_text() for name in ('probe.qpf','probe.sdc','run.tcl')};controls['probe.qsf']=qsf
    need(controls['run.tcl']==fit.FULL_TCL,'STATIC_PLAIN_FLOW')
    for name,text in controls.items():
        with (destination/name).open('x') as f:f.write(text)
    n.package_helper.dump(destination/'manifest.json',dict(schema='stream27-P5-static-direction-sizing-v1',status='prepared_not_fitted',top=TOP,
      target='stream27_P5_static_CT_GS_f0',edition='pro',device='10AX115N4F40E3SG',compile_processors=4,bitstream_generation=False,
      allowed_stages=['syn','fit','sta'],clock_period_ns=10,seed=1,intermediate_snapshots=True,core_parameters=dict(P=104857601,Q=4190109697),
      source_sha256={name:sha(raw) for name,raw in sources.items()},control_sha256={name:sha(text.encode()) for name,text in controls.items()},
      native_prerequisites=native_gates(),arithmetic_source_pins=PINS,independent_input_sets=4,expected_variable_products_by_source=4,
      cell_comparison=['normalized_ct','fused_ct','normalized_gs','fused_gs'],static_gs=[0,0,1,1],TAG_W=1,
      wrapper_fit_gate_fields=[0],unchanged_arithmetic_gate_fields=[0,1,2],
      wrapper_latency=6,butterfly_latency=5,II=1,R=1<<32,
      scope='Matched fixed direction/TAG_W1 scalar diagnostic; no changed arithmetic, shared generator, field fit, wholeP16 area or admitted clock.',promotion_allowed=False))
    return fit_dispatch.snapshot(destination)
def submit_project(project):
    from fpga.tools import fit_submit
    return fit_submit.submit(ROOT/'queue/standing-fits','stream27-l3-static-directions-f0-v1',Path(project).resolve(),
      '10',1,dict(azure4=list('abcd'),aws6=list('ab')),'component_probe',dict(exemption='component_sizing_probe'),
      priority=50,requires=native_gates(),track='S',purpose='p16_diet')
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--write-source',action='store_true');parser.add_argument('--p',type=int,choices=tuple(n.model.FIELDS))
    parser.add_argument('--output',type=Path);parser.add_argument('--budget',type=Path);parser.add_argument('--project',type=Path);parser.add_argument('--submit',action='store_true');a=parser.parse_args()
    if a.write_source:print(write_source())
    elif a.project:print(json.dumps(submit_project(a.project) if a.submit else prepare_project(a.project),indent=2))
    else:print(n.package_helper.prepare(a.output,a.p,a.budget,role_builder=role,identity='normal2',family='stream27-l3-static'))
