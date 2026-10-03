"""Private additive endpoint v8 native roles; no application/core/vendor proof."""
import copy
import hashlib
import json
from pathlib import Path
from . import stream27_r15_pcie_avmm_v8 as leaf

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/throughput-20260929/trackS-r15-pcie-avmm-native-v8'
DONOR=ROOT/'results/throughput-20260929/trackS-r15-pcie-avmm-native-v6/normal-v6'
SELF='reference/stream27_r15_pcie_avmm_v8_native.py'
RTL='rtl/kernel/genefer_stream27_r15_pcie_avmm_v1.sv'
CPP='rtl/tb/stream27_r15_pcie_avmm.cpp'

CASES='''static void external_cases(int argc,char**argv){
 unsigned cases=0;
 {Bench b(argc,argv);b.d.external_fault_valid=1;b.pre();
  need(b.d.external_fault_ready,"R15_AVMM_EXTERNAL_READY");b.tick();b.d.external_fault_valid=0;b.idle(40);
  need(b.d.protocol_error&&b.aborts==1,"R15_AVMM_EXTERNAL_IDLE_ABORT");cases++;}
 {Bench b(argc,argv);b.respond=false;b.begin(0,0x01000201);
  need(!b.responses.empty(),"R15_AVMM_EXTERNAL_BEGIN_CAPTURE");
  b.d.external_fault_valid=1;b.respond=true;b.tick();b.d.external_fault_valid=0;b.idle(40);
  need(b.d.protocol_error&&b.aborts==1&&b.read(0x5c)==0,"R15_AVMM_EXTERNAL_BEGIN_AUTHORITY");cases++;}
 {Bench b(argc,argv);b.begin(0,0x01000201);for(unsigned i=0;i<64;i++)b.data(0,b.owners[0],i);b.idle();b.commit();
  b.respond=false;b.d.export_address=0;b.d.export_burstcount=3;b.d.export_read=1;b.pre();
  need(!b.d.export_waitrequest,"R15_AVMM_EXTERNAL_EXPORT_READY");b.tick();b.d.export_read=0;
  for(unsigned t=0;t<20&&b.responses.empty();t++)b.tick();need(!b.responses.empty(),"R15_AVMM_EXTERNAL_A32_CAPTURE");
  b.respond=true;b.d.external_fault_valid=1;unsigned count=0;
  for(unsigned t=0;t<50;t++){b.tick();if(b.d.export_readdatavalid){
   for(unsigned j=0;j<8;j++)need(b.d.export_readdata[j]==0,"R15_AVMM_EXTERNAL_FAULT_VALID_A_LEAK");count++;}
   b.d.external_fault_valid=0;}
  need(count==3&&b.d.protocol_error&&b.aborts==1,"R15_AVMM_EXTERNAL_ZERO_DRAIN");cases++;}
 {Bench b(argc,argv);b.respond=false;b.d.cmd_ready=0;b.d.ctrl_read=1;b.d.ctrl_address=8;b.tick();b.d.ctrl_read=0;
  Packet held{};for(unsigned j=0;j<16;j++)held[j]=b.d.cmd_data[j];
  b.d.external_fault_valid=1;b.tick();b.d.external_fault_valid=0;
  for(unsigned t=0;t<6;t++){b.tick();need(b.d.cmd_valid,"R15_AVMM_EXTERNAL_ISSUED_VALID");
   for(unsigned j=0;j<16;j++)need(b.d.cmd_data[j]==held[j],"R15_AVMM_EXTERNAL_ISSUED_PAYLOAD");}
  b.d.cmd_ready=1;b.respond=true;b.idle(40);
  need(b.commands.size()==2&&get(b.commands[0],0,4)==5&&get(b.commands[1],0,4)==15&&b.aborts==1,
       "R15_AVMM_EXTERNAL_ORDERED_TAIL");
  b.d.reset=1;b.responses.clear();b.tick();b.d.reset=0;b.idle();
  need(!b.d.protocol_error&&!b.d.cmd_valid,"R15_AVMM_EXTERNAL_RESET_CLEAR");
  b.begin(1,0x01000301);need(!b.d.protocol_error,"R15_AVMM_EXTERNAL_RESET_RECOVERY");cases++;}
 need(cases==4,"R15_AVMM_EXTERNAL_CORPUS_COUNT");
 std::cout<<"R15_AVMM_EXTERNAL_FAULT_PASS cases=4 A32_invalid=3 begin_mask=1 ordered_tail=1 reset=1 core_vendor=0\\n";
}

'''


def role(variant='normal'):
    if variant not in ('normal','external-fault','missing-external-mask'):raise ValueError('R15_AVMM_V8_VARIANT')
    original=json.loads((DONOR/'manifest.json').read_bytes());m=copy.deepcopy(original)
    f={p:(DONOR/'source/fpga'/p).read_bytes() for p in original['sources']}
    if any(hashlib.sha256(raw).hexdigest()!=original['sources'][p] for p,raw in f.items()):raise ValueError('R15_AVMM_V8_DONOR_PINS')
    f[RTL]=leaf.source()
    if variant=='missing-external-mask':
        before=b'if(resp_data[15:8]==0 && !protocol_error && !held_violation && !external_fault_valid &&'
        after=b'if(resp_data[15:8]==0 && !protocol_error && !held_violation &&'
        if f[RTL].count(before)!=1:raise ValueError('R15_AVMM_V8_A32_MASK_ANCHOR')
        f[RTL]=f[RTL].replace(before,after,1)
    text=f[CPP].decode();before='d.clk=0;d.reset=1;d.link_ready=0;'
    if text.count(before)!=1 or text.count('int main(int argc,char**argv)')!=1:raise ValueError('R15_AVMM_V8_CPP_ANCHOR')
    text=text.replace(before,before+'d.external_fault_valid=0;',1)
    text=text.replace('int main(int argc,char**argv)',CASES+'int main(int argc,char**argv)',1)
    before=' const bool faults=argc==2&&std::string(argv[1])=="--faults";'
    if text.count(before)!=1:raise ValueError('R15_AVMM_V8_MAIN_DISPATCH')
    text=text.replace(before,' if(argc==2&&std::string(argv[1])=="--external-faults"){external_cases(argc,argv);return 0;}\n'+before,1)
    f[CPP]=text.encode()
    for p in (SELF,'reference/stream27_r15_pcie_avmm_v7.py','reference/stream27_r15_pcie_avmm_v8.py'):f[p]=(ROOT/p).read_bytes()
    m['sources']={p:hashlib.sha256(raw).hexdigest() for p,raw in f.items()}
    if variant!='normal':
        m['steps']=[dict(name='pcie-avmm-v8-'+variant,argv=['{exe}','--external-faults'],
          expected_returncode=1 if variant=='missing-external-mask' else 0,
          expected_stdout='' if variant=='missing-external-mask' else 'R15_AVMM_EXTERNAL_FAULT_PASS cases=4 A32_invalid=3 begin_mask=1 ordered_tail=1 reset=1 core_vendor=0\n',
          expected_stderr='R15_AVMM_EXTERNAL_FAULT_VALID_A_LEAK\n' if variant=='missing-external-mask' else '')]
        m['test_role']='bounded-fault'
    snap={RTL:m['sources'][RTL]}
    m['rtl_readiness'].update(candidate_id='s4-r15-pcie-avmm-v8-'+variant,source_snapshot=snap,
      candidate_source_sha256=hashlib.sha256(json.dumps(snap,sort_keys=True,separators=(',',':')).encode()).hexdigest())
    m['scope'].update(author='p16_independent_reviewer',external_fault_conduit=True,
      v8_width_only_reverse=True,behavioral_responder=True,ordered_issued_tail_not_flush=True,
      whole_core=False,vendor_IP=False,physical=False,independent_review=False,promotion_allowed=False)
    return m,f


def prepare(output,variant='normal'):
    out=Path(output).resolve()
    if not out.is_relative_to(BASE) or out.exists():raise ValueError('R15_AVMM_V8_FRESH_OUTPUT')
    if any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')):raise ValueError('R15_AVMM_V8_PAUSE')
    m,f=role(variant);source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in f.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as h:h.write(raw)
    m['source_root']=str(source)
    with (out/'manifest.json').open('x') as h:json.dump(m,h,indent=2);h.write('\n')
    return dict(id='s4-r15-pcie-avmm-'+variant+'-q1-v8',manifest=str(out/'manifest.json'),status='SOURCE_PREPARED_NOT_SUBMITTED')


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--variant',default='normal')
    a=p.parse_args();print(json.dumps(prepare(a.output,a.variant),indent=2))
