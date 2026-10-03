"""AUTHOR registered-credit guard successor; v1 source/captures unchanged."""
import copy
import hashlib
import json
from pathlib import Path
from . import stream27_r15_dma_aperture_v2 as leaf
from . import stream27_r15_dma_aperture_native_v1 as parent

ROOT=parent.ROOT
BASE=ROOT/'results/throughput-20260929/trackS-r15-dma-aperture-native-v2'
SELF='reference/stream27_r15_dma_aperture_native_v2.py'
DONOR=parent.BASE/'normal-v1'
CPP_BEFORE=' b.read(0x800000-32,1);d.down_rd_readdatavalid=1;'
CPP_AFTER=' b.read(0x800000-32,1);b.step();d.down_rd_readdatavalid=1;'
MORE_FAULTS=''' // V2 requires a previously registered response credit, not same-edge
 // credit inferred through WAITREQUEST. A zero-latency RV is terminal.
 b.reset();b.read(0,1);d.down_rd_readdatavalid=1;
 for(unsigned j=0;j<8;j++)d.down_rd_readdata[j]=800+j;
 b.pre();need(d.fault_valid,"R15_APERTURE_ZERO_LATENCY_NOT_REJECTED");b.step();
 d.down_rd_readdatavalid=0;b.step();
 need(b.reads.empty(),"R15_APERTURE_ZERO_LATENCY_FORGED_RECORD");
 // The offered request did actually accept on this standalone wait=0 bus.
 // Its subsequently registered credit must drain INVALID, not disappear.
 b.response(1,900,true);need(b.requests==1&&b.reads.size()==1,"R15_APERTURE_ZERO_LATENCY_CREDIT_DRAIN");b.terminal();cases++;
 // Behavioral PCIe-domain endpoint WAIT witness, not vendor/whole-core RTL:
 // WAIT = latched fault OR same-origin fault_valid, just as the actual V8
 // source cone. Conditional stray RV before credit must have a UNIQUE fixed
 // point independent of whether the solver starts WAIT at zero or one.
 for(unsigned initial=0;initial<2;initial++){
  b.reset();d.down_rd_waitrequest=1;b.read(0,1);d.down_rd_readdatavalid=1;
  d.down_rd_waitrequest=initial;
  for(unsigned settle=0;settle<4;settle++){b.pre();d.down_rd_waitrequest=d.protocol_error||d.fault_valid;}
  b.pre();need(d.fault_valid&&d.down_rd_waitrequest&&d.down_rd_read,"R15_APERTURE_COUPLED_FIXEDPOINT");
  b.step();d.down_rd_readdatavalid=0;d.down_rd_waitrequest=1;
  for(unsigned t=0;t<4;t++)b.step();
  need(b.requests==0&&b.reads.empty()&&b.faults==1,"R15_APERTURE_COUPLED_UNACCEPTED_TAIL");cases++;
 }
'''


def role(variant='normal'):
    if variant not in ('normal','fault','missing-mask','bad-credit'):raise ValueError('R15_APERTURE_V2_VARIANT')
    m=copy.deepcopy(json.loads((DONOR/'manifest.json').read_bytes()))
    f={p:(DONOR/'source/fpga'/p).read_bytes() for p in m['sources']}
    if any(hashlib.sha256(raw).hexdigest()!=m['sources'][p] for p,raw in f.items()):raise ValueError('R15_APERTURE_V2_DONOR_PINS')
    f[parent.RTL]=leaf.source()
    if variant=='missing-mask':
        before=b"rd_readdata=terminal?256'b0:rd_data_q;"
        if f[parent.RTL].count(before)!=1:raise ValueError('R15_APERTURE_V2_MASK_ANCHOR')
        f[parent.RTL]=f[parent.RTL].replace(before,b'rd_readdata=rd_data_q;',1)
    if variant=='bad-credit':
        before=b' wire response_credit=(rd_expected!=0);'
        if f[parent.RTL].count(before)!=1:raise ValueError('R15_APERTURE_V2_CREDIT_ANCHOR')
        f[parent.RTL]=f[parent.RTL].replace(before,leaf.BEFORE,1)
    text=f[parent.CPP].decode()
    if text.count(CPP_BEFORE)!=1 or text.count(' need(cases==20,"R15_APERTURE_FAULT_CORPUS_COUNT");')!=1:raise ValueError('R15_APERTURE_V2_CPP_ANCHOR')
    text=text.replace(CPP_BEFORE,CPP_AFTER,1).replace('R15_APERTURE_ZERO_LATENCY_RESPONSE','R15_APERTURE_REGISTERED_RESPONSE')
    text=text.replace(' need(cases==20,"R15_APERTURE_FAULT_CORPUS_COUNT");',MORE_FAULTS+' need(cases==23,"R15_APERTURE_FAULT_CORPUS_COUNT");',1)
    text=text.replace('dts_partial=1 core_vendor=0','dts_partial=1 registered_credit=1 core_vendor=0')
    text=text.replace('cases=20 high_alias=1','cases=23 high_alias=1')
    text=text.replace('unresolved_tail_reset=1 reset=1 core_vendor=0','unresolved_tail_reset=1 reset=1 zero_latency_refused=1 coupled_wait_witness=2 core_vendor=0')
    f[parent.CPP]=text.encode()
    for p in (SELF,'reference/stream27_r15_dma_aperture_v2.py'):f[p]=(ROOT/p).read_bytes()
    pins={p:hashlib.sha256(raw).hexdigest() for p,raw in f.items()};m['sources']=pins
    normal=parent.NORMAL.replace('dts_partial=1 core_vendor=0','dts_partial=1 registered_credit=1 core_vendor=0')
    fault=parent.FAULT.replace('cases=20 high_alias=1','cases=23 high_alias=1').replace(
      'unresolved_tail_reset=1 reset=1 core_vendor=0','unresolved_tail_reset=1 reset=1 zero_latency_refused=1 coupled_wait_witness=2 core_vendor=0')
    negative=variant in ('missing-mask','bad-credit')
    expected_error='R15_APERTURE_FAULT_ORIGIN_DATA_LEAK\n' if variant=='missing-mask' else 'R15_APERTURE_ZERO_LATENCY_NOT_REJECTED\n' if variant=='bad-credit' else ''
    m['steps']=[dict(name='dma-aperture-v2-'+variant,argv=['{exe}']+([] if variant=='normal' else ['--faults']),
      expected_returncode=1 if negative else 0,expected_stdout='' if negative else normal if variant=='normal' else fault,
      expected_stderr=expected_error)]
    m['test_role']='normal' if variant=='normal' else 'deliberate_fault'
    snap={parent.RTL:pins[parent.RTL]}
    m['rtl_readiness'].update(candidate_id='s4-r15-dma-aperture-v2-'+variant,source_snapshot=snap,
      candidate_source_sha256=hashlib.sha256(json.dumps(snap,sort_keys=True,separators=(',',':')).encode()).hexdigest())
    contract=copy.deepcopy(m['scope']['contract'])
    contract['response_latency']='minimum1-edge after downstream read acceptance; only registered rd_expected credit; zero-latency RV terminal-faulted'
    contract['composition']='no downstream WAITREQUEST/down_rd_fire fan-in to fault; behavioral coupled-wait witness only, not actual vendor/whole-core simulation'
    m['scope'].update(variant=variant,contract=contract,actual_endpoint_registered_latency_required=True,
      parent_sha256=leaf.PARENT_SHA,source_change='credit from registered rd_expected only',
      old_native_outcome_inherited=False,mutant_original_sha256=hashlib.sha256(leaf.source()).hexdigest() if negative else None)
    return m,f


def prepare(output,variant='normal'):
    out=Path(output).resolve()
    if not out.is_relative_to(BASE) or out.exists():raise ValueError('R15_APERTURE_V2_FRESH_OUTPUT')
    if any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')):raise ValueError('R15_APERTURE_V2_PAUSE')
    m,f=role(variant);source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in f.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as h:h.write(raw)
    m['source_root']=str(source)
    with (out/'manifest.json').open('x') as h:json.dump(m,h,indent=2);h.write('\n')
    return dict(id='s4-r15-dma-aperture-'+variant+'-q1-v2',manifest=str(out/'manifest.json'),status='SOURCE_PREPARED_NOT_SUBMITTED')


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--variant',default='normal')
    a=p.parse_args();print(json.dumps(prepare(a.output,a.variant),indent=2))
