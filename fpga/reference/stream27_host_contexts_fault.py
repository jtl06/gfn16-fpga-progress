"""Separate immutable oracle/descriptor/reset roles on closed host normal RTL."""
import argparse,json,tarfile
from datetime import datetime,timezone
from pathlib import Path
from fpga.reference import stream27_two_context_native as base
from fpga.tools import native_class_package_v2 as package
ROOT=base.ROOT
FROZEN=ROOT/'results/throughput-20260929/trackS-host-contexts-v1/aw5-p8-dense-normal-v2'
CPP='rtl/tb/stream27_host_contexts_fault.cpp'
def prepare(out,budget,mode='oracle',normal=None):
    base.need(mode in ('oracle','external','reset','owner') and not out.exists() and not (ROOT/'docs/briefs/PAUSE').exists() and not (ROOT/'queue/PAUSE').exists(),'HOST_FAULT_FRESH_MODE_PAUSE')
    frozen=FROZEN if normal is None else normal
    normal_ticket=json.loads((frozen/'global-ticket.json').read_text())
    m=json.loads((frozen/'manifest.json').read_text());source=out/'source/fpga';source.mkdir(parents=True)
    for name,pin in m['sources'].items():
        raw=(frozen/'source/fpga'/name).read_bytes();base.need(base.sha(raw)==pin,'HOST_FAULT_FROZEN_DRIFT')
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(raw)
    extra=[('lineage/reference/stream27_host_contexts_fault.py',Path(__file__).resolve())]
    if mode!='oracle':extra.append((CPP,ROOT/CPP));m['build']['cpp_source']=CPP
    if mode in ('external','reset'):m['build']['cflags']=m['build']['cflags']+['-DS4_HOST_PORTS_ONLY=1']
    for name,path in extra:
        raw=path.read_bytes()
        if name==CPP and mode=='owner':
            base.need(m['host_contexts']['geometry']['n']==32,'HOST_OWNER_DIAGNOSTIC_SMALL_GEOMETRY')
            raw=raw.replace(b'genefer_stream27_host_contexts_aw5_p8_v1_closed_ram_v2',m['build']['top'].encode())
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(raw)
        m['sources'][name]=base.sha(raw)
    if mode=='oracle':
        step=dict(name='host-contexts-oracle-control',argv=['{exe}','--oracle-negative'],expected_returncode=1,expected_stdout='',expected_stderr='S4_HOST_CONTEXT_SIGNED96_VALUE ctx=0 address=0\n')
    elif mode=='external':
        step=dict(name='host-contexts-external-fault',argv=['{exe}','--external'],expected_returncode=0,expected_stdout='S4_HOST_CONTEXTS_EXTERNAL_FAULT_PASS bad_base=1 stale_generation=1 full32_index_alias=1 global_abort=3 peer_recovery=0\n',expected_stderr='')
    elif mode=='reset':
        footer=m['steps'][0]['expected_stdout'];step=dict(name='host-contexts-reset',argv=['{exe}','--reset'],expected_returncode=0,expected_stdout=footer*2+'S4_HOST_CONTEXTS_RESET_PASS resets=2 retained_words=64 pending_response_invalid=1 nonempty_fifo=2/4 recovered_chains=2\n',expected_stderr='')
    else:
        evidence=ROOT/'queue/evidence'/normal_ticket['id']
        gate=json.loads((evidence/'gate-receipt.json').read_text());base.need(gate['status']=='PASS_expected_contracts','HOST_OWNER_ACTUAL_NORMAL_BASELINE_REQUIRED')
        header=evidence/'attempt-0/collected/output/native/generated-sources.tar.gz'
        with tarfile.open(header,'r:gz') as archive:
            root=archive.extractfile('V'+m['build']['top']+'___024root.h').read().decode()
        for suffix in ('__DOT__job_count','__DOT__job_epoch','__DOT__engine__DOT__arithmetic__DOT__carry_generation','__DOT__engine__DOT__arithmetic__DOT__carry_context'):
            base.need(m['build']['top']+suffix in root,'HOST_OWNER_ACTUAL_GENERATED_HEADER_ABI:'+suffix)
        m['host_contexts']['mutation_scope']='Simulation-only generated root registers:job_count+65536 preserves low16 ordinal and epoch; job_epoch highbit; carried generation highbit; carried context misroute. Baseline and external descriptor negatives remain independently required.'
        m['host_contexts']['actual_normal_baseline_manifest_sha256']=gate['manifest_sha256'];m['host_contexts']['generated_header_archive_sha256']=base.sha(header.read_bytes())
        step=dict(name='host-contexts-owner',argv=['{exe}','--owner'],expected_returncode=0,expected_stdout=m['steps'][0]['expected_stdout']+'S4_HOST_CONTEXTS_OWNER_FAULT_PASS baseline_chains=2 full32_ordinal_alias=1 epoch=1 generation=1 context=1 global_abort=4 publication=0 simulation_mutations=1\n',expected_stderr='')
    m.update(source_root=str(source),output_parent=str(out/'UNBOUND_OUTPUT'));m['steps']=[step]
    m['host_contexts']['scope']='Separate '+mode+' role on frozen closed host RTL; no context-local shared-fault recovery. Oracle control must genuinely fail full signed96 read value; resets revoke responses/readiness, retain RAM and recover both complete chains.'
    base.dump(out/'manifest.json',m);packet=out/'packet-01';stem=normal_ticket['id'].rsplit('-normal-q1-v',1)[0]+'-'+mode
    prepared=package.prepare(out/'manifest.json',source,'gcp-c4d-static01-v1',stem+'-01-v1','run',packet,budget)
    nt=json.loads((packet/'ticket.json').read_text());ticket=normal_ticket
    ticket.update(id=stem+'-q1-v1',created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),test_role='deliberate_fault',source_gate=dict(scope=m['host_contexts']['scope'],promotion_allowed=False));ticket.pop('rtl_readiness',None)
    ticket['packages'][0].update(archive=str(packet/'package.tar.gz'),sha256=prepared['archive_sha256'],ticket_sha256=prepared['ticket_sha256'],manifest_sha256=nt['manifest_sha256'],worker_id=nt['id'],native_root=nt['native_root'])
    base.dump(out/'global-ticket.json',ticket);print(out/'global-ticket.json')
if __name__=='__main__':
    q=argparse.ArgumentParser();q.add_argument('--output',type=Path,required=True);q.add_argument('--budget',type=Path,required=True);q.add_argument('--mode',choices=('oracle','external','reset','owner'),default='oracle')
    q.add_argument('--normal',type=Path)
    a=q.parse_args();prepare(a.output.resolve(),a.budget.resolve(),a.mode,a.normal.resolve() if a.normal else None)
