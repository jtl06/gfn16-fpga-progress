"""Strict finite generic-carry native contracts and pinned source derivation.

The independent reference is signed128 schoolbook plus SERIAL Euclidean
carry, not the RTL's reciprocal/parts/small-cell recurrence. Local calls
emit source/constants only; arithmetic executes on the admitted native host.
"""
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BENCH='rtl/tb/stream27_threefield_carry_v1.cpp'
CPP='rtl/tb/stream27_threefield_carry_param_v1.cpp'
HEADER='rtl/tb/s4_threefield_config_v1.h'
PROBE='genefer_stream27_carry_param_probe_v1'
PINS={BENCH:'453e7e53efb4ac2982039614e0258974cebd4e7737c3f88c7dc633a20c4cdd29',
 'reference/stream27_threefield_carry_native_v2.py':'bf7caf176ecace29ffbba73cb13d36fc5712a1c9a3cecc8587dbe79e10f5e26d',
 'reference/stream27_threefield_carry_v1.py':'361edd39be8ba787275a19167bc188de4f87489b9df7c6558b587dc4814619bd',
 'reference/stream27_shared_field_v2.py':'05eab167ccb00c2bb6a74475ec2b3c84549f0b328ac4d5dbf9e1faea73657fd2',
 'reference/stream27_shared_field_v3.py':'42d786e62801476c1444861973bae16c98b5d8a74b5d22c1d50c5043d83de546'}

def need(ok,tag):
    if not ok:raise ValueError(tag)

def sha(raw):return hashlib.sha256(raw).hexdigest()

def verify():
    for name,pin in PINS.items():need(sha((ROOT/name).read_bytes())==pin,'S4_PARAM_NATIVE_PARENT_DRIFT '+name)
    from .stream27_blockcarry_param_model_v1 import parent_identity
    return parent_identity()

def arguments(aw,p):
    need(type(aw) is int and aw in (5,8) and type(p) is int and p in (8,16),'S4_PARAM_NATIVE_ROLE')
    return 1<<aw

def minimum_base(aw,p):
    n=arguments(aw,p);return max(2*n+5,(2*(2*n+24*p)+2)//3+1)

def counts(aw,p):
    n=arguments(aw,p);signed=p==8;frames=17 if signed else 13
    return dict(cases=7 if signed else 5,frames=frames,coefficient_words=frames*n,
        digit_words=frames*n,boundary_pairs=frames*p,warm_feedback_starts=10 if signed else 8,
        fault_cases=int(signed),peak_owners=1,paired=int(not signed))

def footer(aw,p,minimum=False):
    base=minimum_base(aw,p) if minimum else 1000000000
    return f'S4_PARAM_CARRY_PASS aw={aw} p={p} mode='+('signed' if p==8 else 'warm')+f' base={base} '+ ' '.join(f'{k}={v}' for k,v in counts(aw,p).items())+'\n'

def contract(aw,p,mode):
    arguments(aw,p);need(mode in ('normal','minimum','oracle','owner'),'S4_PARAM_NATIVE_MODE')
    if mode in ('normal','minimum'):return dict(stdout=footer(aw,p,mode=='minimum'),stderr='',returncode=0)
    return dict(stdout='',stderr='S4_PARAM_NEGATIVE_'+mode.upper()+'_REJECT\n',returncode=1)

def validate(stdout,stderr,returncode,config,assets):
    need(set(config)=={'aw','p','mode'} and assets=={},'S4_PARAM_NATIVE_CONFIG')
    e=contract(**config)
    need(type(stdout) is str and type(stderr) is str and type(returncode) is int and
         (stdout,stderr,returncode)==(e['stdout'],e['stderr'],e['returncode']),'S4_PARAM_TYPED_OUTPUT')
    return dict(status='PASS_expected_contracts',**config,promotion_allowed=False,
        scope='P8/defaultP16 three-field/CRT/carry intermediate; not canonical host/long PRP/clock qualification.')

INPUTS='clk,rst_n,begin_setup,in_slot_valid,frame_start,context_enabled,double_in,generation_in,live_generation,base_in,epoch_in,correction_epoch,correction_valid,correction_generation,data_in,c0_in,c1_in'.split(',')
OUTPUTS='config_valid,setup_done,out_error,fault_pending,frame_accept,correction_accept,coefficient_valid,coefficient_start,coefficient_data,coefficient_row,digit_valid,digit_start,digit_eligible,digit_data,digit_row,digit_epoch,digit_generation,boundary_valid,boundary_eligible,next_c0,next_c1,next_epoch,next_generation,frame_done,done_epoch'.split(',')

def probe_source(bundle,old=None):
    text=bundle['files'][bundle['top']+'.sv'];header=text[text.index('module '):text.index(');')+2]
    header=header.replace('module '+bundle['top']+' #','module '+PROBE+' #',1)
    header=header[:-2]+',\n output logic [1:0] owner_count,output logic owner_mismatch,pair_mismatch);'
    body='\n '+bundle['top']+' #(.AW(AW),.P(P),.CONTEXTS(CONTEXTS)) actual (\n  '+','.join('.'+s for s in INPUTS+OUTPUTS)+');\n'
    body+=' assign owner_count=actual.field_owners[0];\n assign owner_mismatch=actual.field_owners[1]!=owner_count || actual.field_owners[2]!=owner_count;\n'
    if old:
        body+=' '+old['top']+' #(.AW(AW),.P(P),.CONTEXTS(CONTEXTS)) parent (\n  '+','.join('.'+s for s in INPUTS)+','+','.join('.'+s+'()' for s in OUTPUTS)+');\n'
        always=['config_valid','setup_done','out_error','fault_pending','frame_accept','correction_accept','coefficient_valid','digit_valid','boundary_valid','frame_done']
        body+=' always_comb begin\n  pair_mismatch='+' || '.join('actual.'+s+'!=parent.'+s for s in always)+';\n'
        for valid,names in [('coefficient_valid',['coefficient_start','coefficient_data','coefficient_row']),
            ('digit_valid',['digit_start','digit_eligible','digit_data','digit_row','digit_epoch','digit_generation']),
            ('boundary_valid',['boundary_eligible','next_c0','next_c1','next_epoch','next_generation']),('frame_done',['done_epoch'])]:
            body+='  if(actual.'+valid+')pair_mismatch=pair_mismatch || '+' || '.join('actual.'+s+'!=parent.'+s for s in names)+';\n'
        body+=' end\n'
    else:body+=' assign pair_mismatch=0;\n'
    return header+body+'endmodule\n'

def compile_bench(bundle):
    verify()
    from .stream27_threefield_carry_native_v2 import serial_bench
    s=serial_bench((ROOT/BENCH).read_text());aw=bundle['parameters']['AW'];p=bundle['parameters']['P'];n=arguments(aw,p);g=bundle['geometry']
    changes=[
      ('static unsigned rev4(unsigned x)', 'static bool negative_oracle=false,negative_owner=false;\nstatic unsigned rev4(unsigned x)'),
      ('k<4;++k','k<LANE_BITS;++k'),
      ('a[j]=x.digits[j];','a[j]=SIGNED_COLD && x.digits[j]==0xffffffffu ? -I(1) : I(x.digits[j]);'),
      ('if(kind==4)x.c0[0]=-1;return x;', 'if(kind==4)x.c0[0]=-1;\n    if(kind==5)x.digits[3]=0xffffffffu;\n    if(kind==6)x.digits[N-1]=0xffffffffu;return x;'),
      ('static void clear(DUT& d)', 'static void monitor(DUT& d){need(!d.pair_mismatch,"S4_PARAM_P16_PAIR");need(!d.owner_mismatch,"S4_PARAM_FIELD_OWNER_JOIN");}\nstatic void clear(DUT& d)'),
      ('Counts& counts){\n    reset_setup(d);','Counts& counts){\n    reset_setup(d);'),
      ('struct Counts{unsigned cases=0,frames=0,coefficients=0,digits=0,boundaries=0,feedback=0;};',
       'struct Counts{unsigned cases=0,frames=0,coefficients=0,digits=0,boundaries=0,feedback=0,faults=0,peak=0;};'),
      ('d.clk=1;d.eval();need(!d.out_error,"S4_ERROR tick="+std::to_string(tick));',
       'd.clk=1;d.eval();monitor(d);need(!d.out_error,"S4_ERROR tick="+std::to_string(tick));\n        unsigned owners=0;for(const auto& f:frames)owners+=tick>=f.start && tick<f.start+SINK+T-1;\n        need(unsigned(d.owner_count)==owners,"S4_PARAM_OWNER_LEDGER");counts.peak=std::max(counts.peak,owners);'),
      ('+" actual="+decimal(got));}counts.coefficients+=P;',
       '+" actual="+decimal(got));if(negative_oracle && counts.cases==0 && row==0 && b==0)need(got==expected+1,"S4_PARAM_NEGATIVE_ORACLE_REJECT");}counts.coefficients+=P;'),
      ('need(argc==1,"S4_ARGUMENTS");Counts counts;',
       'bool minimum=argc==2 && std::string(argv[1])=="--minimum";negative_oracle=argc==2 && std::string(argv[1])=="--negative-oracle";negative_owner=argc==2 && std::string(argv[1])=="--negative-owner";need(argc==1 || minimum || negative_oracle || negative_owner,"S4_ARGUMENTS");if(minimum)BASE=MIN_BASE;Counts counts;if(SIGNED_COLD)invalid_minus2(d,counts);'),
      ('run(d,4,2,counts);need(context.threads()',
       'run(d,4,2,counts);if(SIGNED_COLD){run(d,5,2,counts);run(d,6,2,counts);}need(counts.peak==1,"S4_PARAM_PEAK");if(negative_owner)need(counts.peak==2,"S4_PARAM_NEGATIVE_OWNER_REJECT");need(!negative_oracle,"S4_PARAM_NEGATIVE_ORACLE_MISSED");need(context.threads()'),
      ('std::cout<<PASS_LABEL<<" cases="',
       'std::cout<<PASS_LABEL<<" base="<<BASE<<" cases="'),
      ('<<" warm_feedback_starts="<<counts.feedback<<"\\n";',
       '<<" warm_feedback_starts="<<counts.feedback<<" fault_cases="<<counts.faults<<" peak_owners="<<counts.peak<<" paired="<<PAIRED<<"\\n";'),
    ]
    for old,new in changes:
        need(s.count(old)==1,'S4_PARAM_NATIVE_BENCH_ANCHOR '+old[:60]);s=s.replace(old,new)
    # Pair checks are eligibility-aware; unknown stale payload is never compared.
    s=s.replace('d.eval();need(!d.digit_valid','d.eval();monitor(d);need(!d.digit_valid',1)
    s=s.replace('d.clk=1;d.eval();need(!d.out_error,"S4_SETUP_ERROR");','d.clk=1;d.eval();monitor(d);need(!d.out_error,"S4_SETUP_ERROR");',1)
    fault='''static void invalid_minus2(DUT& d,Counts& counts){
    reset_setup(d);d.clk=0;clear(d);d.in_slot_valid=1;d.frame_start=1;d.correction_valid=1;
    d.data_in[rev4(3/T)]=0xfffffffeu;d.eval();need(d.fault_pending,"S4_PARAM_MINUS2_PENDING");
    d.clk=1;d.eval();monitor(d);need(d.out_error,"S4_PARAM_MINUS2_QUARANTINE");
    for(unsigned tick=0;tick<DONE+T+2;++tick){d.clk=0;clear(d);d.in_slot_valid=1;d.frame_start=1;d.correction_valid=1;d.begin_setup=1;d.eval();need(!d.frame_accept && !d.correction_accept,"S4_PARAM_FAILED_ADMISSION");d.clk=1;d.eval();monitor(d);need(d.out_error && !d.coefficient_valid && !d.digit_valid && !d.boundary_valid && !d.frame_done,"S4_PARAM_FAILED_OUTPUT");}
    ++counts.faults;
}
'''
    need(s.count('int main(')==1,'S4_PARAM_MAIN');s=s.replace('int main(',fault+'int main(',1)
    header=f'''#include "V{PROBE}.h"
using DUT=V{PROBE};
constexpr unsigned N={n},P={p},T=N/P,LANE_BITS={p.bit_length()-1},BOUND={2*n+24*p},MIN_BASE={minimum_base(aw,p)};
static uint32_t BASE=1000000000;
constexpr bool SIGNED_COLD={'true' if p==8 else 'false'},PAIRED={'false' if p==8 else 'true'};
constexpr unsigned COEFFICIENT={g['double_register']},DIGIT={g['first_digit']},BOUNDARY={g['boundary_output']},DONE={g['carry_done']},INTERVAL={g['warm_interval']},CORRECTION={g['next_correction_accept']},SINK={g['sink_accept']};
constexpr const char* PASS_LABEL="S4_PARAM_CARRY_PASS aw={aw} p={p} mode={'signed' if p==8 else 'warm'}";
'''
    # Header needs uint32_t before declaring BASE (the parent includes it later).
    header='#include <cstdint>\n'+header
    return s,header
