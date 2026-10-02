"""A7 trace packet v2: all alternative-order totals and critical tail witness.

No HDL, full-N numerical model, remote action or automatic dispatch. Main must
admit lint-first plus fresh native execution; the offline event analyzer follows.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

from .core27_prefetch_r2_rootfused_crtmont_regression import COMPILED_ORDER,FIXED_PINS

PARENT='genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont'
TOP='genefer_track_a7_crtmont_trace_v1'
OLD_BENCH='rtl/tb/square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont.cpp'
THREAD_BENCH=OLD_BENCH.replace('.cpp','_threaded.cpp')
BENCH='rtl/tb/track_a7_crtmont_trace_v1.cpp'
SELF='reference/track_a7_trace_prepare_v2.py'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def replace(text,old,new,count=1):
    if text.count(old)!=count:raise ValueError('A7_EXACT_ANCHOR: '+old)
    return text.replace(old,new)


def wrapper(source):
    header=source[source.index('module '+PARENT):source.index('    // Atomic27/')]
    header=replace(header,'module '+PARENT,'module '+TOP)
    header=replace(header,'output logic [63:0] seed_setup_cycles\n',
        '''output logic [63:0] seed_setup_cycles,
    output wire [383:0] trace_re,trace_we,
    output wire [6143:0] trace_ra,trace_wa,
    output wire [95:0] trace_group,
    output wire [14:0] trace_stage,
    output wire [11:0] trace_state,
    output wire [5:0] trace_op,
    output wire [2:0] trace_phase
''')
    body='    '+PARENT+' #(.AW(AW),.NTT_LANES(NTT_LANES)) core (.*);\n'
    body+='    assign trace_phase=core.step;\n'
    for field in range(3):
        path=f'core.field_lane[{field}].engine.child'
        for target,width,signal in [('group',32,'group_index'),('stage',5,'stage_bit'),('state',4,'state'),('op',2,'active_op')]:
            body+=f'    assign trace_{target}[{field*width}+:{width}]={path}.{signal};\n'
        for bank in range(128):
            offset=field*128+bank
            body+=f'    assign trace_re[{offset}]={path}.data_re[{bank}];\n'
            body+=f'    assign trace_we[{offset}]={path}.data_we[{bank}];\n'
            body+=f"    assign trace_ra[{offset*16}+:16]=16'({path}.data_ra[{bank}]);\n"
            body+=f"    assign trace_wa[{offset*16}+:16]=16'({path}.data_wa[{bank}]);\n"
    return '// Observation-only wrapper; frozen core instance and physical RAM ports.\n'+header+body+'endmodule\n'


def bench(original,threaded):
    original=replace(original,'V'+PARENT,'V'+TOP,2)
    old='auto tick=[&](){d.clk=0;d.eval();d.clk=1;d.eval();};'
    new='''uint64_t a7_edge=0,a7_records=0;unsigned a7_run=0;
        std::cout<<"A7_HEADER "<<n<<"\\n";
        auto tick=[&](){
            d.clk=0;d.eval();
            const unsigned st=d.trace_state&15u;
            if(d.rst_n && (st==5 || st==6) && (d.trace_op&3u)==0){
                if(d.trace_phase!=1 && d.trace_phase!=3)throw std::runtime_error("A7_PHASE");
                for(unsigned f=1;f<3;++f){
                    if(((d.trace_state>>(4*f))&15u)!=st ||
                       ((d.trace_op>>(2*f))&3u)!=0 ||
                       ((d.trace_stage>>(5*f))&31u)!=(d.trace_stage&31u) ||
                       d.trace_group[f]!=d.trace_group[0])throw std::runtime_error("A7_FIELD_METADATA_SKEW");
                }
                for(unsigned write=0;write<2;++write){
                    const auto& mask=write?d.trace_we:d.trace_re;
                    const auto& rows=write?d.trace_wa:d.trace_ra;
                    unsigned count=0;for(unsigned b=0;b<128;++b)count+=(mask[b/32]>>(b%32))&1u;
                    if(!count)continue;
                    for(unsigned f=1;f<3;++f)for(unsigned b=0;b<128;++b){
                        const bool valid=(mask[b/32]>>(b%32))&1u;
                        if(((mask[f*4+b/32]>>(b%32))&1u)!=valid ||
                           (valid && ((rows[f*64+b/2]>>(16*(b%2)))&65535u)!=((rows[b/2]>>(16*(b%2)))&65535u)))
                            throw std::runtime_error("A7_FIELD_PHYSICAL_SKEW");
                    }
                    std::cout<<"A7 "<<(write?'W':'R')<<" "<<a7_edge<<" "<<a7_run<<" "
                        <<unsigned(d.trace_phase)<<" "<<(d.trace_stage&31u)<<" "
                        <<(write?-1:int(d.trace_group[0]))<<" "<<count;
                    for(unsigned b=0;b<128;++b)std::cout<<" "<<(((mask[b/32]>>(b%32))&1u)?int((rows[b/2]>>(16*(b%2)))&65535u):-1);
                    std::cout<<"\\n";++a7_records;
                }
            }
            d.clk=1;d.eval();++a7_edge;
        };'''
    original=replace(original,old,new)
    original=replace(original,'const unsigned cache_before=d.profile_cache_valid;',
                     '++a7_run;const unsigned cache_before=d.profile_cache_valid;')
    marker='std::cout<<"PASS n="<<n<<" squares="<<cases<<" readbacks="<<readbacks<<" aborts="<<aborts<<"\\n";'
    original=replace(original,marker,marker+'''
        if(cases!=2 || readbacks!=2 || aborts || a7_records!=uint64_t(8)*lg*std::max(1u,n/128))
            throw std::runtime_error("A7_TRACE_COVERAGE");
        std::cout<<"A7_TRACE_PASS n="<<n<<" runs="<<a7_run<<" records="<<a7_records<<"\\n";''')
    threaded=threaded.replace('V'+PARENT,'V'+TOP)
    threaded=replace(threaded,'#include "'+Path(OLD_BENCH).name+'"','#include "track_a7_crtmont_trace_body_v1.cpp"')
    return original,threaded


def select_vectors(root,aw):
    folder=root/f'results/throughput-20260929/core27-prefetch-r2-rootfused-crtmont-aw{aw}-v1'
    report=json.loads((folder/'report.json').read_text());path=folder/f'vectors-aw{aw}.txt'
    if sha(path)!=report['vectors']['sha256']:raise ValueError('A7_ARCHIVED_VECTOR_SHA')
    lines=path.read_text().splitlines();first=next(i for i,line in enumerate(lines) if line.startswith('LOAD '))
    selected=lines[first:first+6]
    if not (selected[2].startswith('RUN ') and selected[4].startswith('RUN ')):
        raise ValueError('A7_TWO_RUN_VECTOR_SUBSET')
    labels=[selected[i].split()[1] for i in (2,4)]
    metrics=[m for m in report['metrics'] if m['case'] in labels]
    if len(metrics)!=2:raise ValueError('A7_PARENT_METRIC_SUBSET')
    return str(1<<aw)+'\n'+'\n'.join(selected)+'\n',dict(parent_vectors_sha256=sha(path),
        parent_report_sha256=sha(folder/'report.json'),labels=labels,metrics=metrics)


def prepare(output):
    root=Path(__file__).resolve().parents[1]
    if (root/'docs/briefs/PAUSE').exists():raise ValueError('brief PAUSE')
    output=Path(output).resolve()
    if output.exists():raise ValueError('fresh output required')
    kernel=['rtl/kernel/'+name for name in COMPILED_ORDER]
    for name in kernel+[OLD_BENCH,THREAD_BENCH]:
        if sha(root/name)!=FIXED_PINS[name]:raise ValueError('frozen source drift '+name)
    sv=wrapper((root/('rtl/kernel/'+PARENT+'.sv')).read_text())
    body,cpp=bench((root/OLD_BENCH).read_text(),(root/THREAD_BENCH).read_text())
    live=kernel+[OLD_BENCH,THREAD_BENCH,SELF,'reference/track_a7_stage_trace_v1.py','reference/track_a7_stage_trace_v2.py',
        'reference/track_a7_trace_prepare_v1.py','tests/test_track_a7_stage_trace_v2.py',
        'reference/core27_prefetch_r2_rootfused_crtmont_regression.py','reference/__init__.py',
        'tests/test_track_a7_stage_trace_v1.py','tools/native_source_gate_v1.py']
    pins={name:sha(root/name) for name in live};reports={}
    for aw in (5,16):
        directory=output/f'aw{aw}';source=directory/'source/fpga';source.mkdir(parents=True)
        vectors,lineage=select_vectors(root,aw)
        generated={'rtl/tb/track_a7_crtmont_trace_v1.sv':sv,BENCH:cpp,
                   'rtl/tb/track_a7_crtmont_trace_body_v1.cpp':body,'a7-vectors.txt':vectors}
        for name in live:
            dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,dest)
        for name,text in generated.items():
            dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(text)
        closure={name:sha(source/name) for name in live+list(generated)}
        base='/home/jtl/gfn-fpga-lab/agent-work/track-a7-crtmont-trace-v2'
        manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',host='aethia',
            source_root=f'{base}/aw{aw}-v1/fpga',output_parent=base,sources=closure,
            build=dict(top=TOP,sv_sources=kernel+['rtl/tb/track_a7_crtmont_trace_v1.sv'],
                       cpp_source=BENCH,parameters={'AW':aw},cflags=['-std=c++17','-Werror=return-type']),
            probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
            steps=[dict(name='physical-trace',argv=['{exe}','{root}/a7-vectors.txt','profile'],
                        expected_returncode=0,expected_stderr='')])
        path=directory/'manifest.json';path.write_text(json.dumps(manifest,indent=2)+'\n')
        with tarfile.open(directory/'source.tar.gz','x:gz') as archive:
            for name in sorted(closure):archive.add(source/name,arcname='fpga/'+name,recursive=False)
        reports[str(aw)]=dict(manifest_sha256=sha(path),archive_sha256=sha(directory/'source.tar.gz'),
            sources=closure,vector_lineage=lineage,expected_records=8*aw*max(1,(1<<aw)//128),
            required_prebuild_lint=['verilator','--lint-only','--top-module',TOP,f'-GAW={aw}']+manifest['build']['sv_sources'],
            after_native='Require exact parent metric rows and complete event analyzer replay before any RTL proposal.')
    if any(sha(root/name)!=pin for name,pin in pins.items()):raise ValueError('source drift during preparation')
    result=dict(status='prepared_not_executed',profiles=reports,
                limitation='Harness-only physical-bank trace; memory feasibility is not implemented stage overlap. Main admits lint-first/native commands; no local HDL/full-N numeric work.')
    (output/'preparation.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();r=prepare(args.output)
    print(json.dumps({aw:{k:v for k,v in row.items() if k.endswith('sha256') or k=='expected_records'} for aw,row in r['profiles'].items()},indent=2))
