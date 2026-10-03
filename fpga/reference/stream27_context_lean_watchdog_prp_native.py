"""Private own SAME-PRP watchdog successor and passive old-source diagnosis.

No old-source PASS/rerun, shared generator or clock claim. Lean build;
host GL assumed (unimplemented). Uses the existing finite class2 package.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_context_lean_watchdog_prp_native.py'
CPP='rtl/tb/stream27_context_lean_watchdog_prp.cpp'
READY='2026-10-02T19:17:49Z'


def diagnostic(bundle,parameters):
    """One state-free observer on EXACT failed58, never a fault injection."""
    from . import stream27_context_lean_prp_native as prp
    out=json.loads(json.dumps(bundle));old=out['top'];top='genefer_stream27_r10_lean_watchdog_observer_v1'
    head=out['files'][old+'.sv'].split(');\n',1)[0]
    ports=head.split(') (',1)[1]
    names=[re.search(r'(\w+)\s*$',part.strip()).group(1) for part in ports.split(',')]
    prp.need(len(names)==len(set(names)) and names[0]=='clk' and names[-1]=='final_image_rows','DIAGNOSTIC_PORT_ABI')
    head=head.replace('module '+old+' #','module '+top+' #',1)
    head+=',\n output logic [31:0] diag_age,diag_limit,\n output logic diag_watchdog,diag_local,diag_progress,\n output logic [63:0] diag_completed,diag_started);\n'
    call=old+' #(\n '+',\n '.join('.'+name+'('+name+')' for name in parameters)+') candidate (\n '+',\n '.join('.'+name for name in names)+');\n'
    body=''' assign diag_age=32'(candidate.lean_watchdog_age);
 assign diag_limit=32'(candidate.LEAN_WATCHDOG_LIMIT);
 assign diag_watchdog=candidate.lean_watchdog_error;
 assign diag_local=candidate.local_error;assign diag_progress=candidate.lean_progress;
 assign diag_completed=candidate.child_completed;assign diag_started=candidate.child_started;
endmodule
'''
    out['files'][top+'.sv']=head+call+body
    out['top']=top;out['rtl_sources']=list(out['files']);out['generated_sha256']={name:prp.sha(text.encode()) for name,text in out['files'].items()}
    return out


def validate(stdout,stderr,rc,config,assets):
    # Standalone native file import: no package/builder dependency here.
    def need(ok,why):
        if not ok:raise ValueError('LEAN_WATCHDOG_OUTPUT_'+why)
    label='lean build; host GL assumed (unimplemented)'
    need(config=={'mode':'passive-old-watchdog'} and assets=={},'DIAGNOSTIC_CONFIG')
    need(type(rc) is int and rc==1 and stdout==label+'\n','DIAGNOSTIC_EXIT_LABEL')
    match=re.fullmatch(r'A_PRP_WATCHDOG_DIAG age=(\d+) watchdog=(\d+) local=(\d+) counter=(\d+) limit=(\d+) completed0=(\d+) completed1=(\d+) started0=(\d+) started1=(\d+)\n',stderr)
    need(match is not None,'EXACT_DIAGNOSTIC_GRAMMAR')
    values=list(map(int,match.groups()))
    need(values==[20805,1,0,20479,20480,96,95,97,96],'ACTUAL_OLD_WATCHDOG_WHILE_SQUARES_PROGRESS')
    return dict(status='PASS_expected_contracts',mode='passive-old-watchdog',measurements=dict(zip(
        ['age','watchdog','local_error','watchdog_counter','watchdog_limit','completed0','completed1','started0','started1'],values)),
        scope='Expected failure localization ONLY on original failed58: watchdog flag, not a numerical PASS. Same failed PRP inputs; passive observer, no fault or FF force.',
        build_label=label,host_gl_implemented=False,promotion_allowed=False)


def role(mode):
    from . import stream27_context_lean_prp_native as prp
    from . import stream27_context_lean_watchdog_bind as binder
    prp.need(mode in ('normal','controls','diagnostic'),'OWN_MODE')
    manifest,files,parent=prp.role('lean',mode=='controls')
    production=diagnostic(parent,manifest['build']['parameters']) if mode=='diagnostic' else binder.bind(parent,enabled=1)
    for name in parent['files']:files.pop('rtl/'+name)
    files.update({'rtl/'+name:text.encode() for name,text in production['files'].items()})
    old=parent['top'];new=production['top']
    text=files[prp.HEADER].decode();prp.need(text.count(old)==2,'HEADER_ONLY_TOP')
    files[prp.HEADER]=text.replace(old,new).encode()
    if mode=='diagnostic':
        text=files[prp.CPP].decode()
        before='need(!d.error,"A_PRP_HEALTHY_ERROR age="+std::to_string(age));'
        after='need(!d.error,"A_PRP_WATCHDOG_DIAG age="+std::to_string(age)+" watchdog="+std::to_string(d.diag_watchdog)+" local="+std::to_string(d.diag_local)+" counter="+std::to_string(d.diag_age)+" limit="+std::to_string(d.diag_limit)+" completed0="+std::to_string(lane32(d.diag_completed,0))+" completed1="+std::to_string(lane32(d.diag_completed,1))+" started0="+std::to_string(lane32(d.diag_started,0))+" started1="+std::to_string(lane32(d.diag_started,1)));'
        prp.need(text.count(before)==1,'ONE_PASSIVE_DIAG_CPP_DELTA')
        files[CPP]=text.replace(before,after,1).encode()
        manifest['build']['cpp_source']=CPP
        manifest['steps']=[dict(name='r10-lean-old-watchdog-localization',argv=['{exe}'],expected_returncode=1,
            validator=dict(source=SELF,function='validate',config={'mode':'passive-old-watchdog'},assets={}))]
    else:
        # Numeric CPP/header/arrays and their assertions are unchanged.
        for step in manifest['steps']:step['name']='r10-lean-warmprogress-'+step['validator']['config']['mode']
    for path in (SELF,binder.SELF):files[path]=(ROOT/path).read_bytes()
    manifest['build'].update(top=new,sv_sources=['rtl/'+name for name in production['rtl_sources']])
    manifest['sources']={name:prp.sha(raw) for name,raw in files.items()}
    identifier='s4-p16-c2-r10-lean-watchdog-'+('diagnostic' if mode=='diagnostic' else 'prp-'+mode)+'-q1-v1'
    manifest['test_role']='normal' if mode=='normal' else 'deliberate_fault'
    snapshot={name:pin for name,pin in manifest['sources'].items() if name.endswith('.sv')}
    manifest['rtl_readiness']=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=identifier.removesuffix('-q1-v1'),
        source_snapshot=snapshot,candidate_source_sha256=prp.sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),rtl_ready_at_utc=READY)
    manifest['healthy_prp'].update(production_top=new,production_generated_sha256=production['generated_sha256'],
        old_failed_lean58_source_not_rebased=True, watchdog_only_successor=mode!='diagnostic',passive_old_watchdog_diagnosis=mode=='diagnostic')
    if mode!='diagnostic':manifest['lean_watchdog_warm_progress']=production['lean_watchdog_warm_progress']
    return manifest,files,production,identifier


def prepare(output,mode):
    from . import stream27_context_lean_prp_native as prp
    from fpga.tools import candidate_ladder,native_class_package_v2 as package
    out=Path(output).resolve();prp.need(out.is_relative_to(ROOT) and not out.exists(),'FRESH_OUTPUT')
    prp.need(not any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')),'PAUSE')
    manifest,files,production,identifier=role(mode);source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    manifest['source_root']=str(source);prp.dump(out/'manifest.json',manifest);prp.dump(out/'production-bundle.json',production)
    prp.dump(out/'host-hours.json',candidate_ladder.budget_from_hourly());variants=[]
    for pair in ('01','23'):
        profile='gcp-c4d-static'+pair+'-v1';worker=identifier.removesuffix('-q1-v1')+'-'+pair+'-v1';packet=out/('packet-'+pair)
        result=package.prepare(out/'manifest.json',source,profile,worker,'run',packet,out/'host-hours.json')
        native=json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],ticket_sha256=result['ticket_sha256'],
            manifest_sha256=prp.sha((packet/'manifest.json').read_bytes()),worker_id=worker,profile=profile,native_root=native['native_root'],
            runner='tools/native_class_package_v2.py',runner_sha256=prp.sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT/'tools/native_package_v4.py'),stager_sha256=prp.sha((ROOT/'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT/p),sha256=prp.sha((ROOT/p).read_bytes())) for p in
                ('tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    ticket=dict(schema='gfn16-global-ticket-v1',id=identifier,owner='independent-review',created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        priority='P1',kind='sim',needs='verilator',tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',allowed_hosts=['gfn16-pilot-c4d','aethia'],
        resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=4,
        minimum_ram_rationale='Own small N256 source-specific healthy watchdog normal/passive localization; no fullN runtime or GL/fault immunity inheritance.',
        est_minutes=30,promotion_bound=False,test_role=manifest['test_role'],rtl_readiness=manifest['rtl_readiness'],packages=variants)
    if mode=='controls':ticket.update(after=['s4-p16-c2-r10-lean-watchdog-prp-normal-q1-v1'],on='PASS_expected_contracts')
    prp.dump(out/'global-ticket.json',ticket)
    return dict(id=identifier,ticket=str(out/'global-ticket.json'),status='PREPARED_NOT_NATIVE',label=prp.LABELS['lean'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('normal','controls','diagnostic'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.output,args.mode),indent=2))
