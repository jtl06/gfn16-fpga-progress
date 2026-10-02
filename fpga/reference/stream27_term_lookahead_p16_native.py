"""Normal-first paired native field role; no local HDL/full-N arithmetic."""
import argparse,json,re
from pathlib import Path
from datetime import datetime,timezone
from . import stream27_term_lookahead_p16_bind as binding
from . import stream27_term_select_native as base
from .stream27_shared_warm_full_native_v1 import compile_bench
from .stream27_p8_warm_native_v2 import lease_ledger
from fpga.tools import native_class_package_v2 as package
ROOT=binding.ROOT
SELF='reference/stream27_term_lookahead_p16_native.py'
CPP='rtl/tb/stream27_term_lookahead_p16_normal.cpp'
def pair(bundle,field):
    b=bundle;actual=b['top'];parent=b['term_lookahead']['parent_top'];s=b['files'][actual+'.sv']
    declaration,rest=s.split(') (',1);ports=rest.split(');',1)[0]
    allowed=set(re.findall(r'\b([A-Z][A-Z0-9_]*)=',declaration));params={k:v for k,v in b['parameters'].items() if k in allowed}
    names=[];outputs=[];wires=[]
    pattern=r'\b(input|output)\s+logic\s+(signed\s+)?(\[[^\]]+\]\s*)?((?!(?:input|output)\b)[A-Za-z_]\w*(?:\s*,\s*(?!(?:input|output)\b)[A-Za-z_]\w*)*)'
    for m in re.finditer(pattern,ports):
        entries=[name.strip() for name in m[4].split(',')];names.extend(entries)
        if m[1]=='output':
            outputs.extend(entries)
            wires.append(' wire '+(m[2] or '')+(m[3] or '')+','.join('reference_'+name for name in entries)+';')
    need=binding.need;need(len(names)==len(set(names)) and 'data_out' in outputs and 'clk' in names,'TERM_LOOKAHEAD_PAIR_PORTS')
    top=f'genefer_stream27_term_lookahead_pair_aw{b["geometry"]["aw"]}_f{field}_v1'
    params_text=', '.join('.'+key+'('+key+')' for key in params)
    connections=', '.join('.'+name+'('+('reference_' if name in outputs else '')+name+')' for name in names)
    wrapper='module '+top+' #('+declaration.split('#(',1)[1]+') ('+ports+');\n'+'\n'.join(wires)+'\n'
    wrapper+=' '+parent+' #('+params_text+') baseline ('+connections+');\n '+actual+' #('+params_text+') candidate (.*);\n'
    wrapper+=' // synthesis translate_off\n always @(negedge clk)if(rst_n)begin\n'
    # Transport validity and fault authority compare every settled phase.
    # Invalid payloads are deliberately not made a qualification contract.
    for name in outputs:
        qualifier='out_slot_valid' if name in ('data_out','generation_out','out_epoch','output_row') else 'commit_valid' if name in ('commit_data','commit_generation','commit_epoch') else '1\'b1'
        wrapper+=f'  if(({qualifier}) && {name}!==reference_{name})$fatal(1,"TERM_LOOKAHEAD_PAIR_{name}");\n'
    wrapper+=' end\n // synthesis translate_on\nendmodule\n'
    b['files'][top+'.sv']=wrapper;b['rtl_sources'].append(top+'.sv');b['top']=top
    return b,params
def role(aw=8,field=1):
    binding.need(aw in (8,16) and field in (0,1,2),'TERM_LOOKAHEAD_NATIVE_GEOMETRY')
    b,params=pair(binding.prepare(1<<aw,field),field);g=b['geometry'];cpp,header=compile_bench(b,field)
    label=f'S4_TERM_LOOKAHEAD_PAIRED_NORMAL aw={aw} p=16 field={field}'
    cpp=binding.once(cpp,'S4_SHARED_AW16_PASS',label)
    ledgers=[lease_ledger(starts,g['sink_accept'],g['rows']) for starts in ([0],[0,g['warm_interval']],[0,g['warm_interval']+16])]
    binding.need(all(not item['rejected'] for item in ledgers),'TERM_LOOKAHEAD_PAIRED_LEASE_CALENDAR')
    counts=dict(cases=9,frames=9,physical_rows=9*g['rows'],physical_words=9*(1<<aw),eligible_rows=7*g['rows'],commits=7*g['rows'],peak_owners=max(item['peak'] for item in ledgers))
    files={'rtl/'+name:text.encode() for name,text in b['files'].items()}
    files.update({CPP:cpp.encode(),base.HEADER:header.encode(),base.REFERENCE:(ROOT/base.REFERENCE).read_bytes()})
    for name in b['source_dependencies']+[SELF,'reference/stream27_shared_warm_full_native_v1.py','reference/stream27_p8_warm_native_v2.py','rtl/tb/stream27_shared_warm_aw8_v1.cpp']:
        files['lineage/'+name]=(ROOT/name).read_bytes()
    footer=label+' '+' '.join(f'{k}={v}' for k,v in counts.items())+'\n'
    m=dict(schema='native-source-gate-v1',status='prepared_not_executed',source_root='UNBOUND',output_parent='UNBOUND',sources={k:base.sha(v) for k,v in files.items()},
        build=dict(top=b['top'],sv_sources=['rtl/'+name for name in b['rtl_sources']],cpp_source=CPP,parameters=params,cflags=['-std=c++17','-O2','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='term-lookahead-paired-normal',argv=['{exe}'],expected_returncode=0,expected_stdout=footer,expected_stderr='')],
        term_lookahead=dict(binding=b['term_lookahead'],geometry=g,counts=counts,scope='Actual copied timing P16 field paired transport/fault/calendar plus independent arithmetic; no whole/physical qualification.'),promotion_allowed=False)
    return m,files
def prepare(output,budget,aw=8,field=1,after=None,revision=1):
    output=Path(output).resolve();base.need(not output.exists() and not any((ROOT/name).exists() for name in ('docs/briefs/PAUSE','queue/PAUSE')),'TERM_LOOKAHEAD_FRESH_PAUSE')
    m,files=role(aw,field);source=output/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(raw)
    m.update(source_root=str(source),output_parent=str(output/'UNBOUND_OUTPUT'));base.dump(output/'manifest.json',m)
    ready=datetime.now(timezone.utc).isoformat().replace('+00:00','Z');stem=f's4-p16-term-lookahead-aw{aw}-f{field}-v{revision}';snapshot={k:v for k,v in m['sources'].items() if k.endswith('.sv')}
    readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=stem,source_snapshot=snapshot,candidate_source_sha256=base.sha(base.json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),rtl_ready_at_utc=ready)
    base.dump(output/'source-readiness.json',readiness);packet=output/'packet-01';r=package.prepare(output/'manifest.json',source,'gcp-c4d-static01-v1',stem+'-normal-01','run',packet,Path(budget).resolve())
    nt=json.loads((packet/'ticket.json').read_text());ticket=json.loads((ROOT/'results/throughput-20260929/trackS-warm-contexts-v1/aw5-p8-normal-v1/global-ticket.json').read_text())
    ticket.update(id=stem+'-normal-q1',candidate_id=stem,owner='p16-mlab',created=ready,test_role='normal',rtl_readiness=readiness,source_gate=dict(scope=m['term_lookahead']['scope'],promotion_allowed=False))
    ticket['packages'][0].update(archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],manifest_sha256=nt['manifest_sha256'],worker_id=nt['id'],native_root=nt['native_root'])
    if after:ticket['after']=[after]
    base.dump(output/'global-ticket.json',ticket);print(output/'global-ticket.json')
if __name__=='__main__':
    q=argparse.ArgumentParser();q.add_argument('--output',type=Path,required=True);q.add_argument('--budget',type=Path,required=True);q.add_argument('--aw',type=int,choices=(8,16),default=8);q.add_argument('--field',type=int,default=1);q.add_argument('--after');q.add_argument('--revision',type=int,default=1)
    a=q.parse_args();prepare(a.output,a.budget,a.aw,a.field,a.after,a.revision)
