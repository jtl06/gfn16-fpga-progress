"""Frame-stable carry thresholds, zero added recurrence edges.

Normal-first source binder: actual candidate/parent are paired edge-by-edge,
and an independent signed128 schoolbook/serial carry oracle checks N<=256.
This coordinator emits source/metadata only; no local HDL or full-N oracle.
"""
import argparse
import copy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from fpga.reference import stream27_threefield_carry_param_v1 as compiler
from fpga.reference import stream27_threefield_carry_param_native_v1 as native

ROOT=native.ROOT
SELF='reference/stream27_carry_localbase_v1.py'
TEST='tests/test_stream27_carry_localbase_v1.py'
CELL='rtl/kernel/genefer_stream27_blockcarry_small_cell_localbase_v1.sv'
LANE='rtl/kernel/genefer_stream27_blockcarry_lane_localbase_v1.sv'
OLD_CELL='rtl/kernel/genefer_stream27_blockcarry_small_cell.sv'
OLD_LANE='rtl/kernel/genefer_stream27_blockcarry_lane_param_v1.sv'
CPP='rtl/tb/stream27_carry_localbase_normal_v1.cpp'
HEADER='rtl/tb/stream27_carry_localbase_config_v1.h'
PROBE='genefer_stream27_carry_localbase_probe_v1'
FAULT_CPP='rtl/tb/stream27_carry_localbase_lane_fault_v1.cpp'
FAULT_VECTORS='reference/stream27_carry_localbase_fault_vectors_v1.py'
FAULT_PROBE='genefer_stream27_carry_localbase_lane_fault_probe_v1'
PINS={OLD_CELL:'eafee617681cbd84cedfe90874938f63bf5ae84123ba1c914410785b44a3e74f',
      OLD_LANE:'8a458519272e89e635eb5cd7e6b2d07c93c8d3b1fc0f44874ba67aeccca77d4b'}


def sha(raw):return hashlib.sha256(raw).hexdigest()
def need(ok,why):
    if not ok:raise ValueError('CARRY_LOCALBASE '+why)
def dump(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n')


def terms(base,aw,p):
    need(type(base) is int and type(aw) is int and aw in range(5,17) and p in (8,16),
         'finite scalar terms')
    n=1<<aw;minimum=max(2*n+5,(2*(2*n+24*p)+2)//3+1)
    need(minimum<=base<=1000000000,'admitted base bounds')
    result=dict(radix=base,two_radix=2*base,three_radix=3*base,four_radix=4*base,
        negative_radix=-base,negative_two_radix=-2*base,y_high=2*base-2+2*n+23*p)
    need(all(-(1<<32)<=x<(1<<32) for x in result.values()),'all exact signed33 terms')
    return result


def bundle(aw,p):
    n=native.arguments(aw,p)
    for name,pin in PINS.items():need(sha((ROOT/name).read_bytes())==pin,'frozen parent '+name)
    old=compiler.prepare(n,p,mode='warm_signed' if p==8 else 'warm');new=copy.deepcopy(old)
    previous=old['top'];new['top']=previous+'_localbase_v1'
    text=old['files'][previous+'.sv']
    need(text.count(previous)==1 and text.count(Path(OLD_LANE).stem)==1,'unique top/lane binding')
    new['files'][new['top']+'.sv']=text.replace(previous,new['top']).replace(Path(OLD_LANE).stem,Path(LANE).stem)
    for name in (CELL,LANE):new['files'][Path(name).name]=(ROOT/name).read_text()
    new['rtl_sources']=[name for name in new['files'] if name.endswith('.sv')]
    new['generated_sha256']={name:sha(text.encode()) for name,text in new['files'].items()}
    new['source_sha256']=dict(old['source_sha256'],**{name:sha((ROOT/name).read_bytes()) for name in (CELL,LANE)})
    need(new['geometry']==old['geometry'],'exact unchanged frame and feedback calendar')
    return old,new


def role(aw=5,p=8):
    old,new=bundle(aw,p)
    files={'rtl/'+name:text.encode() for name,text in new['files'].items()}
    cpp,header=native.compile_bench(new)
    need(cpp.count('s4_threefield_config_v1.h')==1,'unique native header')
    cpp=cpp.replace('s4_threefield_config_v1.h',Path(HEADER).name)
    header=header.replace(native.PROBE,PROBE).replace('PAIRED=false','PAIRED=true').replace('S4_PARAM_CARRY_PASS','S4_LOCALBASE_CARRY_PASS')
    probe=native.probe_source(new,old).replace(native.PROBE,PROBE)
    files[CPP]=cpp.encode();files[HEADER]=header.encode();files['rtl/'+PROBE+'.sv']=probe.encode()
    for name in dict.fromkeys(old['source_dependencies']+[native.BENCH,*native.PINS]):
        data=(ROOT/name).read_bytes();files['lineage/'+name]=data
    for name in (CELL,LANE,SELF,TEST):files[name]=(ROOT/name).read_bytes()
    expected=lambda minimum:native.footer(aw,p,minimum).replace('S4_PARAM_CARRY_PASS','S4_LOCALBASE_CARRY_PASS').replace('paired=0','paired=1')
    steps=[dict(name='carry-localbase-'+mode,argv=['{exe}']+(['--minimum'] if minimum else []),
        expected_returncode=0,expected_stdout=expected(minimum),expected_stderr='')
        for mode,minimum in (('maximum-normal',False),('minimum-normal',True))]
    m=dict(schema='native-source-gate-v1',status='prepared_not_executed',
        source_root='/not-a-dispatch-path/carry-localbase/fpga',output_parent='/not-a-dispatch-path/carry-localbase/output',
        sources={name:sha(data) for name,data in files.items()},
        build=dict(top=PROBE,sv_sources=['rtl/'+name for name in new['rtl_sources']]+['rtl/'+PROBE+'.sv'],
            cpp_source=CPP,parameters=dict(AW=aw,P=p,CONTEXTS=1),cflags=['-std=c++17','-O2','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=steps,carry_localbase=dict(aw=aw,p=p,geometry=new['geometry'],paired_exact_parent=True,
            setup_latency=97,coefficient_to_digit_edges=25,last_digit_to_boundary_edges=3,tail_check_edges=1,
            recurrence_feedback_edges=1,added_edges=0,counts=dict(native.counts(aw,p),paired=1),
            terms_at_minimum=terms(native.minimum_base(aw,p),aw,p),terms_at_maximum=terms(1000000000,aw,p),
            parent_source_sha256=old['source_sha256'],candidate_generated_sha256=new['generated_sha256'],
            normal_only=True,physical_timing_not_measured=True,full_N_numeric_locally_performed=False,
            scope='Actual newlane/newcell vs exact frozen generic parent on every edge; signed128 independent schoolbook/serial carry oracle, setup97, bubbles/reset/signed cold/actual digit and boundary feedback. No whole-host/clock/adoption claim.'))
    return m,files


def fault_role(aw=5,p=8):
    from fpga.reference import stream27_carry_localbase_fault_vectors_v1 as vectors
    text,meta=vectors.corpus(aw,p)
    old=(ROOT/'rtl/tb/track_a4_blockcarry_lane_probe_v1.sv').read_text()
    need(old.count('genefer_track_a4_blockcarry_lane_v1 #(.AW(AW)) lane (.*);')==1,'frozen lane probe')
    probe=old.replace('track_a4_blockcarry_lane_probe_v1 #(parameter int AW=5)',FAULT_PROBE+' #(parameter int AW=5,P=8)')
    probe=probe.replace('output logic busy,done,error,','output logic pair_mismatch,\n    output logic busy,done,error,')
    inputs='clk,rst_n,begin_block,in_valid,block_start,block_end,base,reciprocal,coefficient_limit,coefficient,offset'.split(',')
    outputs='busy,done,error,error_code,digit_valid,digit,digit_offset,boundary_valid,boundary_low,boundary_high'.split(',')
    pair='    '+Path(OLD_LANE).stem+' #(.AW(AW),.P(P)) parent ('+','.join('.'+k for k in inputs)+','+','.join('.'+k+'()' for k in outputs)+');\n'
    pair+='    always_comb begin\n        pair_mismatch='+' || '.join('lane.'+k+'!=parent.'+k for k in ('busy','done','error','error_code','digit_valid','boundary_valid'))+';\n'
    for valid,names in (('digit_valid',('digit','digit_offset')),('boundary_valid',('boundary_low','boundary_high'))):
        pair+='        if(lane.'+valid+')pair_mismatch=pair_mismatch || '+' || '.join('lane.'+k+'!=parent.'+k for k in names)+';\n'
    pair+='    end\n'
    probe=probe.replace('genefer_track_a4_blockcarry_lane_v1 #(.AW(AW)) lane (.*);',Path(LANE).stem+' #(.AW(AW),.P(P)) lane (.*);\n'+pair)
    files={name:(ROOT/name).read_bytes() for name in (OLD_CELL,OLD_LANE,CELL,LANE,
        'rtl/kernel/genefer_div_recip_precision.sv',FAULT_CPP,FAULT_VECTORS,SELF,TEST,
        'reference/stream27_blockcarry_param_model_v1.py','reference/stream_ntt_blockwrap2_proposal.py')}
    files['rtl/'+FAULT_PROBE+'.sv']=probe.encode();files['carry-localbase/fault-vectors.txt']=text.encode()
    rows=text.splitlines()[1:]
    counts=dict(aw=aw,events=len(rows),digits=sum(int(line.split()[14]) for line in rows),
        boundaries=sum(int(line.split()[17]) for line in rows),completed=sum(int(line.split()[11]) for line in rows),
        error_edges=sum(int(line.split()[12]) for line in rows))
    expected='CARRY_LOCALBASE_LANE_FAULT_PASS '+' '.join(f'{k}={v}' for k,v in counts.items())+'\n'
    m=dict(schema='native-source-gate-v1',status='prepared_not_executed',
        source_root='/not-a-dispatch-path/carry-localbase-fault/fpga',output_parent='/not-a-dispatch-path/carry-localbase-fault/output',
        sources={name:sha(data) for name,data in files.items()},
        build=dict(top=FAULT_PROBE,sv_sources=['rtl/kernel/genefer_div_recip_precision.sv',OLD_CELL,OLD_LANE,CELL,LANE,'rtl/'+FAULT_PROBE+'.sv'],
            cpp_source=FAULT_CPP,parameters=dict(AW=aw,P=p),cflags=['-std=c++17','-O2','-Werror=return-type',f'-DA4_LANE_AW={aw}']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='carry-localbase-lane-reset-config-quarantine',argv=['{exe}','{root}/carry-localbase/fault-vectors.txt'],expected_returncode=0,expected_stdout=expected,expected_stderr=''),
            dict(name='carry-localbase-lane-typed-oracle',argv=['{exe}','{root}/carry-localbase/fault-vectors.txt','--wrong-oracle'],expected_returncode=1,expected_stdout='',expected_stderr='CARRY_LOCALBASE_LANE_ORACLE_REJECT\n')],
        carry_localbase=dict(aw=aw,p=p,mode='faults',paired_exact_parent=True,counts=counts,corpus=meta,added_edges=0,
            scope='Own paired lane minimum/max/signed limits, bubbles, all30 pipeline reset ages, mid-input reset, config/protocolcodes1..4 sticky quarantine and complete recovery; independent serial-divmod oracle. No injected child-errorcodes5..10, wholehost or clock claim.'))
    return m,files


def prepare(output,aw,p,budget,mode='normal'):
    from fpga.tools import native_class_package_v2 as package
    out=Path(output).resolve();budget=Path(budget).resolve()
    need(not out.exists() and not any((ROOT/name).exists() for name in ('docs/briefs/PAUSE','queue/PAUSE')),
         'fresh output/no PAUSE')
    need(mode in ('normal','faults'),'separate normal/fault mode')
    m,files=role(aw,p) if mode=='normal' else fault_role(aw,p);source=out/'input/source/fpga';source.mkdir(parents=True)
    for name,data in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    manifest=out/'input/manifest.json';dump(manifest,m)
    worker=f's4-carry-localbase-aw{aw}-p{p}-'+('faults-' if mode=='faults' else '')+'gcp01-v1';packet=out/'packet'
    receipt=package.prepare(manifest,source,'gcp-c4d-static01-v1',worker,'run',packet,budget)
    def pin(name):return dict(path=str(ROOT/'tools'/name),sha256=sha((ROOT/'tools'/name).read_bytes()))
    snapshot={name:sha(files[name]) for name in (CELL,LANE)};now=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    ticket=dict(schema='gfn16-global-ticket-v1',id=f's4-carry-localbase-aw{aw}-p{p}-{mode}-q1-v1',
        owner='soak-chunks',created=now,priority='P1',kind='sim',needs='verilator',test_role='normal' if mode=='normal' else 'deliberate_fault',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=4,
        minimum_ram_rationale='Source-bound paired N<=256 threefield/CRT/lane component; bounded4GiB exploration, no full-core peak claim.',
        est_minutes=10,promotion_bound=False,on='PASS_expected_contracts',
        allowed_hosts=['gfn16-pilot-c4d','gfn16-azure-sim-f32','gfn16-azure-f16'],
        after=[f's4-carry-localbase-aw5-p{p}-normal-q1-v1'] if aw==8 or mode=='faults' else [],
        rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id='s4-carry-localbase-v1',
            rtl_ready_at_utc=now,source_snapshot=snapshot,
            candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode())),
        packages=[dict(profile='gcp-c4d-static01-v1',worker_id=worker,archive=str(packet/'package.tar.gz'),
            sha256=receipt['archive_sha256'],ticket_sha256=receipt['ticket_sha256'],manifest_sha256=sha((packet/'manifest.json').read_bytes()),
            native_root=receipt['native_root'],runner='tools/native_class_package_v2.py',runner_sha256=pin('native_class_package_v2.py')['sha256'],
            stager=str(ROOT/'tools/native_package_v4.py'),stager_sha256=pin('native_package_v4.py')['sha256'],
            stager_dependencies=[pin('native_package_v3.py'),pin('native_package_v2.py')],max_seconds=3700)],
        scope=m['carry_localbase']['scope'])
    dump(out/'global-ticket.json',ticket)
    return dict(status='normal_source_prepared_not_native',id=ticket['id'],global_ticket=str(out/'global-ticket.json'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aw',type=int,choices=(5,8),required=True);parser.add_argument('--p',type=int,choices=(8,16),default=8)
    parser.add_argument('--mode',choices=('normal','faults'),default='normal')
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--budget',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.output,args.aw,args.p,args.budget,args.mode),indent=2))
