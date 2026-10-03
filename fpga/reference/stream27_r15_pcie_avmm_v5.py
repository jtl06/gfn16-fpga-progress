"""Additive cross-bus progress and independent descriptor staging correction.

Deferred BAR2 control cannot block continuation DMA beats. Descriptor registers
are independent of the immutable cold header; no core-calendar claim follows.
"""
from pathlib import Path
import hashlib
from . import stream27_r15_pcie_avmm_v4 as parent

ROOT=parent.ROOT
BASE=ROOT/'results/throughput-20260929/trackS-r15-pcie-avmm-native-v5'
SELF='reference/stream27_r15_pcie_avmm_v5.py'


def source(*,missing_origin_mask=False):
    text=parent.source(missing_origin_mask=missing_origin_mask).decode()
    before='export_left!=0||ctrl_active;'
    after='export_left!=0||(ctrl_active&&!ctrl_waitrequest);'
    if text.count(before)!=1:raise ValueError('R15_AVMM_V5_COLD_ARB_IDENTITY')
    text=text.replace(before,after)
    before='export_left!=0||ctrl_active||cold_write;'
    after='export_left!=0||(ctrl_active&&!ctrl_waitrequest)||cold_write;'
    if text.count(before)!=1:raise ValueError('R15_AVMM_V5_EXPORT_ARB_IDENTITY')
    text=text.replace(before,after)
    before="else if(header_locked && ctrl_address!=64'h64 && ctrl_address!=64'h68)fault();"
    after="""else if(header_locked && ctrl_address!=64'h64 && ctrl_address!=64'h68 &&
       ctrl_address!=64'h70 && ctrl_address!=64'h74 && ctrl_address!=64'h78 && ctrl_address!=64'h7c)fault();"""
    if text.count(before)!=1:raise ValueError('R15_AVMM_V5_DESCRIPTOR_STAGING_IDENTITY')
    return text.replace(before,after).encode()


PROGRESS=''' b.data(0,owner0,0,3,false);
 // Deferred BAR2 read is legally held while the cold burst remains active.
 // It must NOT stall cold continuation or both masters deadlock permanently.
 b.d.ctrl_read=1;b.d.ctrl_address=8;b.data(0,owner0,1,3,false);b.data(0,owner0,2,3,true);
 b.d.clk=0;b.d.eval();unsigned deferred=0;
 while(b.d.ctrl_waitrequest){b.tick();b.d.clk=0;b.d.eval();need(++deferred<100,"R15_AVMM_CROSSBUS_PROGRESS");}
 b.tick();b.d.ctrl_read=0;
 while(!b.d.ctrl_readdatavalid){b.tick();need(++deferred<100,"R15_AVMM_CROSSBUS_RESPONSE");}
 need(b.d.ctrl_readdata==7&&!b.d.protocol_error,"R15_AVMM_CROSSBUS_SESSION");b.idle();
 // Separate descriptor staging must work while the cold HEADER is locked.
 // Behavioural peer only: not a numerical/live-calendar service-gap proof.
 b.write(0x70,1);b.write(0x74,0);b.write(0x78,1);b.write(0x7c,1);b.write(0x40,7);
 need(!b.d.protocol_error && get(b.commands.back(),0,4)==7 && get(b.commands.back(),4,1)==1,
      "R15_AVMM_DESCRIPTOR_DURING_COLD_LEASE");
 for(unsigned i=3;i<64;i++)b.data(0,owner0,i);
'''


def role(mode='normal',*,missing_origin_mask=False):
    m,f=parent.role(mode,missing_origin_mask=missing_origin_mask)
    rtl=parent.parent.parent.parent.RTL;cpp=parent.parent.parent.parent.CPP
    f[rtl]=source(missing_origin_mask=missing_origin_mask)
    if mode=='normal':
        before=' for(unsigned i=0;i<64;i++){if(i<3)b.data(0,owner0,i,3,i==2);else b.data(0,owner0,i);}'
        text=f[cpp].decode()
        if text.count(before)!=1:raise ValueError('R15_AVMM_V5_CPP_PROGRESS_IDENTITY')
        text=text.replace(before,PROGRESS).replace('cold_dontcare=2 vendor_core=0',
          'cold_dontcare=2 crossbus_progress=1 descriptor_while_load=1 vendor_core=0')
        f[cpp]=text.encode()
        m['steps'][0]['expected_stdout']=m['steps'][0]['expected_stdout'].replace(
          'cold_dontcare=2 vendor_core=0','cold_dontcare=2 crossbus_progress=1 descriptor_while_load=1 vendor_core=0')
    f[SELF]=(ROOT/SELF).read_bytes();m['sources']={p:hashlib.sha256(v).hexdigest() for p,v in f.items()}
    import json
    snap={rtl:m['sources'][rtl]}
    m['rtl_readiness'].update(candidate_id='s4-r15-pcie-avmm-v5',source_snapshot=snap,
      candidate_source_sha256=hashlib.sha256(json.dumps(snap,sort_keys=True,separators=(',',':')).encode()).hexdigest())
    m['scope'].update(deferred_control_cannot_block_cold_burst=True,
                      separate_descriptor_registers_unlocked=True)
    return m,f


def prepare(output,mode='normal',*,missing_origin_mask=False):
    import json
    out=Path(output).resolve()
    if not out.is_relative_to(BASE) or out.exists():raise ValueError('R15_AVMM_V5_FRESH_OUTPUT')
    if any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')):raise ValueError('R15_AVMM_PAUSE')
    m,f=role(mode,missing_origin_mask=missing_origin_mask);root=out/'source/fpga';root.mkdir(parents=True)
    for name,raw in f.items():
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as h:h.write(raw)
    m['source_root']=str(root)
    with (out/'manifest.json').open('x') as h:json.dump(m,h,indent=2);h.write('\n')
    id='s4-r15-pcie-avmm-'+('missing-mask' if missing_origin_mask else mode)+'-q1-v5'
    return dict(id=id,manifest=str(out/'manifest.json'),status='SOURCE_PREPARED_NOT_SUBMITTED')


if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--mode',choices=('normal','fault'),default='normal');p.add_argument('--missing-origin-mask',action='store_true')
    a=p.parse_args();print(json.dumps(prepare(a.output,a.mode,missing_origin_mask=a.missing_origin_mask),indent=2))
