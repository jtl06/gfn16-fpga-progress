"""Additive general Avalon write-burst slave (constantBurstBehavior=false).

Only first accepted beat owns address/count. Continuation DATA/BE/WRITE remain
held under waitrequest. Retains current-edge fault guard/read don't-care fix.
"""
from pathlib import Path
import hashlib
from . import stream27_r15_pcie_avmm_v3 as parent

ROOT=parent.ROOT
BASE=ROOT/'results/throughput-20260929/trackS-r15-pcie-avmm-native-v4'
SELF='reference/stream27_r15_pcie_avmm_v4.py'


def source(*,missing_origin_mask=False):
    text=parent.source(missing_origin_mask=missing_origin_mask).decode()
    changes={
      '{cold_address,cold_write,cold_writedata,cold_byteenable,cold_burstcount}':
      "{(cold_left==0?cold_address:64'b0),cold_write,cold_writedata,cold_byteenable,(cold_left==0?cold_burstcount:5'b0)}",
      'cold_address[63:22]!=0':'(cold_left==0 && cold_address[63:22]!=0)',
      'cold_address[4:0]!=0':'(cold_left==0 && cold_address[4:0]!=0)',
      'cold_burstcount==0':'(cold_left==0 && cold_burstcount==0)',
      '        (cold_left!=0 && (cold_address!=cold_base || cold_burstcount!=cold_total)) ||\n':'',
    }
    for before,after in changes.items():
        if text.count(before)!=1:raise ValueError('R15_AVMM_V4_BURST_IDENTITY')
        text=text.replace(before,after)
    return text.encode()


def role(mode='normal',*,missing_origin_mask=False):
    m,f=parent.role(mode,missing_origin_mask=missing_origin_mask)
    rtl=parent.parent.parent.RTL;cpp=parent.parent.parent.CPP
    f[rtl]=source(missing_origin_mask=missing_origin_mask)
    old='  d.cold_address=0;d.cold_burstcount=burst;d.cold_writedata[0]=0x52315000|ctx;'
    new='''  d.cold_address=0;d.cold_burstcount=burst;
  // Only first beat address/count are authoritative. Legal continuation
  // don't-cares intentionally look invalid to a first-beat checker.
  if(burst>1 && idx>0){d.cold_address=0xffffffffffffffe1ull;d.cold_burstcount=0;}
  d.cold_writedata[0]=0x52315000|ctx;'''
    text=f[cpp].decode()
    if text.count(old)!=1:raise ValueError('R15_AVMM_V4_CPP_BURST_IDENTITY')
    text=text.replace(old,new)
    if mode=='normal':
        text=text.replace('read_dontcare=4 vendor_core=0','read_dontcare=4 cold_dontcare=2 vendor_core=0')
        m['steps'][0]['expected_stdout']=m['steps'][0]['expected_stdout'].replace(
          'read_dontcare=4 vendor_core=0','read_dontcare=4 cold_dontcare=2 vendor_core=0')
    f[cpp]=text.encode();f[SELF]=(ROOT/SELF).read_bytes()
    m['sources']={p:hashlib.sha256(v).hexdigest() for p,v in f.items()}
    import json
    snap={rtl:m['sources'][rtl]}
    m['rtl_readiness'].update(candidate_id='s4-r15-pcie-avmm-v4',source_snapshot=snap,
      candidate_source_sha256=hashlib.sha256(json.dumps(snap,sort_keys=True,separators=(',',':')).encode()).hexdigest())
    m['scope'].update(constantBurstBehavior=False,byte_address_units=True,
      continuation_address_count_dontcare=True)
    return m,f


def prepare(output,mode='normal',*,missing_origin_mask=False):
    import json
    out=Path(output).resolve()
    if not out.is_relative_to(BASE) or out.exists():raise ValueError('R15_AVMM_V4_FRESH_OUTPUT')
    if any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')):raise ValueError('R15_AVMM_PAUSE')
    m,f=role(mode,missing_origin_mask=missing_origin_mask);root=out/'source/fpga';root.mkdir(parents=True)
    for name,raw in f.items():
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as h:h.write(raw)
    m['source_root']=str(root)
    with (out/'manifest.json').open('x') as h:json.dump(m,h,indent=2);h.write('\n')
    id='s4-r15-pcie-avmm-'+('missing-mask' if missing_origin_mask else mode)+'-q1-v4'
    return dict(id=id,manifest=str(out/'manifest.json'),status='SOURCE_PREPARED_NOT_SUBMITTED')


if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--mode',choices=('normal','fault'),default='normal');p.add_argument('--missing-origin-mask',action='store_true')
    a=p.parse_args();print(json.dumps(prepare(a.output,a.mode,missing_origin_mask=a.missing_origin_mask),indent=2))
