"""Additive Avalon correction: read-only writedata is a don't-care, not authority.

Retains v2 current-edge publication guard. Frozen v1/v2 captures unchanged.
"""
from pathlib import Path
import hashlib
from . import stream27_r15_pcie_avmm_v2 as parent

ROOT=parent.parent.ROOT
BASE=ROOT/'results/throughput-20260929/trackS-r15-pcie-avmm-native-v3'
SELF='reference/stream27_r15_pcie_avmm_v3.py'


def source(*,missing_origin_mask=False):
    text=parent.source(missing_origin_mask=missing_origin_mask).decode()
    old='ctrl_address,ctrl_read,ctrl_write,ctrl_writedata,ctrl_byteenable'
    new="ctrl_address,ctrl_read,ctrl_write,(ctrl_write?ctrl_writedata:32'b0),ctrl_byteenable"
    if text.count(old)!=1:raise ValueError('R15_AVMM_V3_READ_DONTCARE_IDENTITY')
    return text.replace(old,new).encode()


READ_DONTCARE=''' // Writedata is not a READ authority field. A legal master may alter it
 // while READ/address/byteenable remain held under waitrequest.
 b.d.cmd_ready=0;b.respond=false;b.d.ctrl_read=1;b.d.ctrl_address=8;b.tick();
 b.d.ctrl_read=0;b.tick();b.d.ctrl_read=1;b.tick();
 for(unsigned k=0;k<4;k++){b.d.ctrl_writedata=0xa5a50000u+k;b.tick();need(!b.d.protocol_error,"R15_AVMM_READ_DONTCARE_OVERREJECTION");}
 b.d.cmd_ready=1;b.respond=true;
 b.d.clk=0;b.d.eval();unsigned waitcycles=0;
 while(b.d.ctrl_waitrequest){b.tick();b.d.clk=0;b.d.eval();need(++waitcycles<100,"R15_AVMM_READ_DONTCARE_TIMEOUT");}
 b.tick();b.d.ctrl_read=0;b.idle();need(!b.d.protocol_error,"R15_AVMM_READ_DONTCARE_ACCEPT");
'''


def role(mode='normal',*,missing_origin_mask=False):
    m,f=parent.role(mode,missing_origin_mask=missing_origin_mask)
    rtl=parent.parent.RTL;cpp=parent.parent.CPP
    f[rtl]=source(missing_origin_mask=missing_origin_mask)
    if mode=='normal':
        old=' std::cout<<"R15_AVMM_NORMAL_PASS'
        text=f[cpp].decode()
        if text.count(old)!=1:raise ValueError('R15_AVMM_V3_CPP_INSERT_IDENTITY')
        f[cpp]=text.replace(old,READ_DONTCARE+old).replace('command_hold=11 vendor_core=0',
          'command_hold=11 read_dontcare=4 vendor_core=0').encode()
        m['steps'][0]['expected_stdout']=m['steps'][0]['expected_stdout'].replace(
          'command_hold=11 vendor_core=0','command_hold=11 read_dontcare=4 vendor_core=0')
    f[SELF]=(ROOT/SELF).read_bytes()
    m['sources']={p:hashlib.sha256(v).hexdigest() for p,v in f.items()}
    import json
    snap={rtl:m['sources'][rtl]}
    m['rtl_readiness'].update(candidate_id='s4-r15-pcie-avmm-v3',source_snapshot=snap,
      candidate_source_sha256=hashlib.sha256(json.dumps(snap,sort_keys=True,separators=(',',':')).encode()).hexdigest())
    m['scope']['read_writedata_dontcare_normalized']=True
    return m,f


def prepare(output,mode='normal',*,missing_origin_mask=False):
    import json
    out=Path(output).resolve()
    if not out.is_relative_to(BASE) or out.exists():raise ValueError('R15_AVMM_V3_FRESH_OUTPUT')
    if any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')):raise ValueError('R15_AVMM_PAUSE')
    m,f=role(mode,missing_origin_mask=missing_origin_mask);root=out/'source/fpga';root.mkdir(parents=True)
    for name,raw in f.items():
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as h:h.write(raw)
    m['source_root']=str(root)
    with (out/'manifest.json').open('x') as h:json.dump(m,h,indent=2);h.write('\n')
    id='s4-r15-pcie-avmm-'+('missing-mask' if missing_origin_mask else mode)+'-q1-v3'
    return dict(id=id,manifest=str(out/'manifest.json'),status='SOURCE_PREPARED_NOT_SUBMITTED')


if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--mode',choices=('normal','fault'),default='normal');p.add_argument('--missing-origin-mask',action='store_true')
    a=p.parse_args();print(json.dumps(prepare(a.output,a.mode,missing_origin_mask=a.missing_origin_mask),indent=2))
