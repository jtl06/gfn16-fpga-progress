"""Additive malformed-response retirement and fatal cold-cursor invalidation.

Issued CDC commands stay ordered/held. Only local response credit and abandoned
burst cursor are retired; already-applied RAM bytes are NOT rolled back.
"""
from pathlib import Path
import hashlib
from . import stream27_r15_pcie_avmm_v5 as parent

ROOT=parent.ROOT
BASE=ROOT/'results/throughput-20260929/trackS-r15-pcie-avmm-native-v6'
SELF='reference/stream27_r15_pcie_avmm_v6.py'


def source(*,missing_origin_mask=False):
    text=parent.source(missing_origin_mask=missing_origin_mask).decode()
    before='begin protocol_error<=1;if(!abort_sent)abort_due<=1; end'
    after='begin protocol_error<=1;cold_left<=0;if(!abort_sent)abort_due<=1; end'
    if text.count(before)!=1:raise ValueError('R15_AVMM_V6_COLD_RETIRE_IDENTITY')
    text=text.replace(before,after)
    before='''       (resp_data&~RESP_MASK)!=0 || resp_data[15:8]>2)begin fault();end'''
    after='''       (resp_data&~RESP_MASK)!=0 || resp_data[15:8]>2 ||
       (resp_data[15:8]==0 && resp_data[152]))begin
     // This consumed response cannot satisfy a future credit. Retire it,
     // complete any owed bus read with INVALID data and then order ABORT.
     fault();waiting<=0;
     if(waiting && ctrl_response)begin ctrl_readdata<=0;ctrl_readdatavalid<=1;end
     if(waiting && waiting_op==READ_A && export_left!=0)begin
      export_readdata<=0;export_readdatavalid<=1;
      export_index<=export_index+1;export_left<=export_left-1;
     end
    end'''
    if text.count(before)!=1:raise ValueError('R15_AVMM_V6_RESPONSE_RETIRE_IDENTITY')
    text=text.replace(before,after)
    before='if(!cmd_valid && !waiting && !held_violation)begin'
    after='if(!cmd_valid && !waiting && !held_violation && !resp_valid)begin'
    if text.count(before)!=1:raise ValueError('R15_AVMM_V6_RESPONSE_ORIGIN_AUTHORITY')
    text=text.replace(before,after)
    before='if(ctrl_response)begin ctrl_readdata<=reg_read(read_address,resp_data);ctrl_readdatavalid<=1;end'
    after="if(ctrl_response)begin ctrl_readdata<=resp_data[15:8]==0?reg_read(read_address,resp_data):32'b0;ctrl_readdatavalid<=1;end"
    if text.count(before)!=1:raise ValueError('R15_AVMM_V6_NONOK_CTRL_IDENTITY')
    text=text.replace(before,after)
    before='ctrl_waitrequest=reset||!link_ready||cmd_valid||waiting'
    after='ctrl_waitrequest=reset||!link_ready||abort_due||resp_valid||cmd_valid||waiting'
    if text.count(before)!=1:raise ValueError('R15_AVMM_V6_AUTO_PRIORITY_CTRL_CREDIT')
    text=text.replace(before,after)
    before='reset||!link_ready||protocol_error||cmd_valid||waiting'
    after='reset||!link_ready||protocol_error||abort_due||resp_valid||cmd_valid||waiting'
    if text.count(before)!=2:raise ValueError('R15_AVMM_V6_RESPONSE_ORIGIN_BUS_CREDIT')
    return text.replace(before,after).encode()


MORE_FAULTS=''' // Malformed consumed response retires the outstanding read credit;
 // otherwise ABORT and the remaining accepted DMA beats deadlock forever.
 for(unsigned kind=0;kind<5;kind++)bad([&](Bench&b){
  export_request(b);b.respond=false;
  for(unsigned k=0;k<10&&b.responses.empty();k++)b.tick();
  need(!b.responses.empty(),"R15_AVMM_BAD_METADATA_CAPTURE");auto&p=b.responses.front();
  switch(kind){case 0:put(p,0,4,5);break;case 1:put(p,16,1,1);break;
   case 2:put(p,4,1,1);break;case 3:put(p,8,8,3);break;case 4:put(p,152,1,1);break;}
  b.respond=true;unsigned count=0;
  for(unsigned k=0;k<80;k++){b.tick();if(b.d.export_readdatavalid){for(unsigned j=0;j<8;j++)need(b.d.export_readdata[j]==0,"R15_AVMM_BAD_METADATA_VALID_A");count++;}}
  need(count==3,"R15_AVMM_BAD_METADATA_BURST_DRAIN");invalid_records+=count;
 });
 for(unsigned kind=0;kind<2;kind++)bad([&](Bench&b){
  b.respond=false;b.d.ctrl_read=1;b.d.ctrl_address=8;b.tick();b.d.ctrl_read=0;
  for(unsigned k=0;k<10&&b.responses.empty();k++)b.tick();
  need(!b.responses.empty(),"R15_AVMM_BAD_CTRL_CAPTURE");
  if(kind==0)put(b.responses.front(),4,1,1);else put(b.responses.front(),8,8,2);
  b.respond=true;b.tick();
  need(b.d.ctrl_readdatavalid&&b.d.ctrl_readdata==0&&b.d.protocol_error,"R15_AVMM_BAD_CTRL_COMPLETION");
 });
 bad([](Bench&b){
  b.begin(0,0x01000201);offer(b);b.d.cold_burstcount=3;accept_cold(b);
  offer(b);b.d.cold_writedata[7]=1;accept_cold(b);
  need((b.read(0x4c)&1)==1,"R15_AVMM_FATAL_COLD_CURSOR_STATUS_READ");
 });
 bad([](Bench&b){
  b.write(0x6c,3);Packet p{};put(p,0,4,5);b.responses.push_back(p);
  b.d.ctrl_write=1;b.d.ctrl_address=0x40;b.d.ctrl_writedata=4;b.tick();b.d.ctrl_write=0;b.idle(30);
  for(const auto&q:b.commands)need(get(q,0,4)==15,"R15_AVMM_RESPONSE_ORIGIN_FORWARDED_NEW_COMMAND");
 });
 bad([](Bench&b){
  b.respond=false;b.begin(0,0x01000201);
  need(!b.responses.empty(),"R15_AVMM_INCONSISTENT_BEGIN_CAPTURE");put(b.responses.front(),152,1,1);
  b.respond=true;b.idle(30);need(b.read(0x5c)==0,"R15_AVMM_INCONSISTENT_BEGIN_LEASE_PUBLISHED");
 });
 bad([](Bench&b){
  Packet p{};put(p,0,4,5);b.responses.push_back(p);
  b.d.ctrl_read=1;b.d.ctrl_address=0x4c;b.tick();
  need(!b.d.ctrl_readdatavalid,"R15_AVMM_STRAY_RESPONSE_READ_NOT_FENCED");
  b.d.clk=0;b.d.eval();unsigned count=0;
  while(b.d.ctrl_waitrequest){b.tick();b.d.clk=0;b.d.eval();need(++count<100,"R15_AVMM_ABORT_PRIORITY_LOST_CONTROL_READ");}
  b.tick();b.d.ctrl_read=0;
  need(b.d.ctrl_readdatavalid && (b.d.ctrl_readdata&1),"R15_AVMM_POST_ABORT_ERROR_READ_COMPLETION");
 });
'''


def role(mode='normal',*,missing_origin_mask=False):
    m,f=parent.role(mode,missing_origin_mask=missing_origin_mask)
    rtl=parent.parent.parent.parent.parent.RTL
    f[rtl]=source(missing_origin_mask=missing_origin_mask)
    # The automatic responder must be evaluated before BOTH driver ready
    # sampling and clock edges; changing RESP only inside tick can fabricate
    # a second accepted command in the driver waiting loop.
    cpp_base='rtl/tb/stream27_r15_pcie_avmm.cpp'
    text=f[cpp_base].decode()
    before=''' void tick(){
  d.clk=0;d.resp_valid=respond&&!responses.empty();
  if(d.resp_valid)for(unsigned i=0;i<16;i++)d.resp_data[i]=responses.front()[i];d.eval();'''
    after=''' void pre(){
  d.clk=0;d.resp_valid=respond&&!responses.empty();
  if(d.resp_valid)for(unsigned i=0;i<16;i++)d.resp_data[i]=responses.front()[i];d.eval();
 }
 void tick(){
  pre();'''
    if text.count(before)!=1:raise ValueError('R15_AVMM_V6_BENCH_PREEDGE_IDENTITY')
    text=text.replace(before,after).replace('d.clk=0;d.eval();','pre();')
    text=text.replace('b.d.clk=0;b.d.eval();','b.pre();')
    f[cpp_base]=text.encode()
    if mode=='fault':
        cpp='rtl/tb/stream27_r15_pcie_avmm_faults.cpp';text=f[cpp].decode()
        before=' need(cases==28&&invalid_records==18,"R15_AVMM_FAULT_COVERAGE");'
        if text.count(before)!=1:raise ValueError('R15_AVMM_V6_CPP_FAULT_IDENTITY')
        text=text.replace(before,MORE_FAULTS+' need(cases==39&&invalid_records==33,"R15_AVMM_FAULT_COVERAGE");')
        text=text.replace('cases=28 invalid_records=18','cases=39 invalid_records=33')
        f[cpp]=text.replace('b.d.clk=0;b.d.eval();','b.pre();').encode()
        if not missing_origin_mask:
            m['steps'][0]['expected_stdout']=m['steps'][0]['expected_stdout'].replace(
                'cases=28 invalid_records=18','cases=39 invalid_records=33')
    f[SELF]=(ROOT/SELF).read_bytes();m['sources']={p:hashlib.sha256(v).hexdigest() for p,v in f.items()}
    import json
    snap={rtl:m['sources'][rtl]}
    m['rtl_readiness'].update(candidate_id='s4-r15-pcie-avmm-v6',source_snapshot=snap,
      candidate_source_sha256=hashlib.sha256(json.dumps(snap,sort_keys=True,separators=(',',':')).encode()).hexdigest())
    m['scope'].update(malformed_response_credit_retired=True,fatal_cold_cursor_retired=True,
      inconsistent_success_core_error_rejected=True,response_origin_new_ingress_masked=True)
    return m,f


def prepare(output,mode='normal',*,missing_origin_mask=False):
    import json
    out=Path(output).resolve()
    if not out.is_relative_to(BASE) or out.exists():raise ValueError('R15_AVMM_V6_FRESH_OUTPUT')
    if any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')):raise ValueError('R15_AVMM_PAUSE')
    m,f=role(mode,missing_origin_mask=missing_origin_mask);root=out/'source/fpga';root.mkdir(parents=True)
    for name,raw in f.items():
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as h:h.write(raw)
    m['source_root']=str(root)
    with (out/'manifest.json').open('x') as h:json.dump(m,h,indent=2);h.write('\n')
    id='s4-r15-pcie-avmm-'+('missing-mask' if missing_origin_mask else mode)+'-q1-v6'
    return dict(id=id,manifest=str(out/'manifest.json'),status='SOURCE_PREPARED_NOT_SUBMITTED')


if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--mode',choices=('normal','fault'),default='normal');p.add_argument('--missing-origin-mask',action='store_true')
    a=p.parse_args();print(json.dumps(prepare(a.output,a.mode,missing_origin_mask=a.missing_origin_mask),indent=2))
