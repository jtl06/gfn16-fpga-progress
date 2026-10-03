"""Additive endpoint successor: current-edge held violation masks authority.

V1 files and captured roles remain unchanged. Default source is read from the
immutable normal-v1 capture, not regenerated from mutable owner files.
"""
import hashlib
from pathlib import Path
from . import stream27_r15_pcie_avmm_native_v1 as parent

SELF='reference/stream27_r15_pcie_avmm_v2.py'
BASE=parent.ROOT/'results/throughput-20260929/trackS-r15-pcie-avmm-native-v2'
FAULT_CPP='rtl/tb/stream27_r15_pcie_avmm_faults.cpp'
FAULT_SOURCE=parent.BASE/'fault-v1/source/fpga'/FAULT_CPP


def source(*,missing_origin_mask=False):
    raw=(parent.BASE/'normal-v1/source/fpga'/parent.RTL).read_bytes()
    text=raw.decode()
    needle=' wire ctrl_active=ctrl_read||ctrl_write;'
    insert=''' wire held_violation=(ctrl_stalled && ctrl_payload!=held_ctrl) ||
   (cold_stalled && cold_payload!=held_cold) ||
   (export_stalled && export_payload!=held_export);
'''
    if text.count(needle)!=1:raise ValueError('R15_AVMM_V2_INSERT_IDENTITY')
    text=text.replace(needle,insert+needle)
    swaps={
      'if(resp_data[15:8]==0 && !protocol_error &&':
      'if(resp_data[15:8]==0 && !protocol_error && !held_violation &&',
      'if(!cmd_valid && !waiting)begin':
      'if(!cmd_valid && !waiting && !held_violation)begin',
    }
    for before,after in swaps.items():
        if text.count(before)!=1:raise ValueError('R15_AVMM_V2_REPLACEMENT_IDENTITY')
        text=text.replace(before,after)
    if missing_origin_mask:
        text=text.replace('if(resp_data[15:8]==0 && !protocol_error && !held_violation &&',
                          'if(resp_data[15:8]==0 && !protocol_error &&')
    return text.encode()


SIMULTANEOUS=''' // Fault originates on a stalled CONTROL request on the SAME edge as
 // a healthy pending READ_A response. A registered error alone is too late.
 bad([&](Bench&b){
  export_request(b);b.respond=false;
  for(unsigned k=0;k<10&&b.responses.empty();k++)b.tick();
  need(!b.responses.empty(),"R15_AVMM_ORIGIN_RESPONSE_CAPTURE");
  b.d.ctrl_write=1;b.d.ctrl_address=0x20;b.d.ctrl_writedata=1009;b.tick();
  b.d.ctrl_writedata=1010;b.respond=true;unsigned count=0;
  b.tick();
  if(b.d.export_readdatavalid){for(unsigned j=0;j<8;j++)need(b.d.export_readdata[j]==0,"R15_AVMM_FAULT_VALID_A_LEAK");count++;}
  b.d.ctrl_write=0;
  for(unsigned k=0;k<80;k++){b.tick();if(b.d.export_readdatavalid){for(unsigned j=0;j<8;j++)need(b.d.export_readdata[j]==0,"R15_AVMM_FAULT_VALID_A_LEAK");count++;}}
  need(count==3,"R15_AVMM_ORIGIN_BURST_DRAIN");invalid_records+=count;
 });
'''


def role(mode='normal',*,missing_origin_mask=False):
    import json
    if mode not in ('normal','fault') or (missing_origin_mask and mode!='fault'):
        raise ValueError('R15_AVMM_V2_MODE')
    m=json.loads((parent.BASE/'normal-v1/manifest.json').read_bytes())
    f={p:(parent.BASE/'normal-v1/source/fpga'/p).read_bytes() for p in m['sources']}
    f[parent.RTL]=source(missing_origin_mask=missing_origin_mask)
    f[SELF]=(parent.ROOT/SELF).read_bytes()
    if mode=='fault':
        text=FAULT_SOURCE.read_text()
        needle=' need(cases==27&&invalid_records==15,"R15_AVMM_FAULT_COVERAGE");'
        if text.count(needle)!=1:raise ValueError('R15_AVMM_V2_FAULT_IDENTITY')
        text=text.replace(needle,SIMULTANEOUS+' need(cases==28&&invalid_records==18,"R15_AVMM_FAULT_COVERAGE");')
        text=text.replace('cases=27 invalid_records=15','cases=28 invalid_records=18')
        f[FAULT_CPP]=text.encode();m['build']['cpp_source']=FAULT_CPP
        m['steps']=[dict(name='pcie-avmm-bounded-origin-faults',argv=['{exe}'],expected_returncode=0,
          expected_stderr='',expected_stdout='R15_AVMM_FAULT_PASS cases=28 invalid_records=18 one_abort=1 reset_cache=1 vendor_core=0\n')]
        m['test_role']='deliberate_fault'
    if missing_origin_mask:
        m['steps'][0].update(name='pcie-avmm-missing-origin-mask-negative',expected_returncode=1,
          expected_stdout='',expected_stderr='R15_AVMM_FAULT_VALID_A_LEAK\n')
    m['source_root']='UNBOUND'
    m['sources']={p:hashlib.sha256(v).hexdigest() for p,v in f.items()}
    snap={parent.RTL:m['sources'][parent.RTL]}
    m['rtl_readiness'].update(candidate_id='s4-r15-pcie-avmm-v2',source_snapshot=snap,
      candidate_source_sha256=hashlib.sha256(json.dumps(snap,sort_keys=True,separators=(',',':')).encode()).hexdigest())
    from datetime import datetime,timezone
    m['rtl_readiness']['rtl_ready_at_utc']=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    m['scope'].update(current_edge_origin_mask=not missing_origin_mask,
                      missing_origin_mask_mutant=missing_origin_mask)
    return m,f


def prepare(output,mode='normal',*,missing_origin_mask=False):
    import json
    out=Path(output).resolve()
    if not out.is_relative_to(BASE) or out.exists():raise ValueError('R15_AVMM_V2_FRESH_OUTPUT')
    if any((parent.ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')):raise ValueError('R15_AVMM_PAUSE')
    m,f=role(mode,missing_origin_mask=missing_origin_mask);root=out/'source/fpga';root.mkdir(parents=True)
    for name,raw in f.items():
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as h:h.write(raw)
    m['source_root']=str(root)
    with (out/'manifest.json').open('x') as h:json.dump(m,h,indent=2);h.write('\n')
    id='s4-r15-pcie-avmm-'+('missing-mask' if missing_origin_mask else mode)+'-q1-v2'
    return dict(id=id,manifest=str(out/'manifest.json'),status='SOURCE_PREPARED_NOT_SUBMITTED')


if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--mode',choices=('normal','fault'),default='normal');p.add_argument('--missing-origin-mask',action='store_true')
    a=p.parse_args();print(json.dumps(prepare(a.output,a.mode,missing_origin_mask=a.missing_origin_mask),indent=2))
