"""P16-c AW6 portable source input, not a host ticket or dispatch authority.

The frozen 13 RTL files and independent schoolbook harness arithmetic remain
unchanged. V2 adds only explicit single-thread context and runtime probe.
Use the shared native_package tool to bind a reviewed host/budget later.
"""
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'artifacts/stream27-p16c-aw6-p16-f0-native-prepared-v1'
PARENT_MANIFEST='dbd5f350ed2ee1e820913f69d88d24c656cee2ee3f79e014b606e7dce2dc6679'
PARENT_BENCH='c24e0b232533acad4f887eb4210b1a7d44339bf32748bbc09fab6cb4c6459cb6'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok,why):
    if not ok:raise ValueError(why)


def verify_bench():
    old=(ROOT/'rtl/tb/stream27_p16c_aw6_v1.cpp').read_text()
    new=(ROOT/'rtl/tb/stream27_p16c_aw6_v2.cpp').read_text()
    require(hashlib.sha256(old.encode()).hexdigest()==PARENT_BENCH,'frozen harness drift')
    restored=new.replace('run(VerilatedContext &context,unsigned image','run(unsigned image')
    restored=restored.replace('    DUT d{&context};\n    if(context.threads()!=1 || d.threads()!=1)throw std::runtime_error("P16C_THREAD_DRIFT");\n    d.rst_n=',
                             '    DUT d;d.rst_n=')
    for key in ('image','3','4','5'):restored=restored.replace('run(context,'+key+',','run('+key+',')
    begin=restored.index('    VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);')
    end=restored.index('        for(unsigned image=0;image<6;++image)',begin)
    prefix=restored[begin:end]
    expected_prefix=r'''    VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
    try{
        if(argc==2 && std::string(argv[1])=="--runtime-probe"){
            DUT probe{&context};
            std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<probe.threads()<<",\"expected_threads\":1}\n";
            return context.threads()==1 && probe.threads()==1 ? 0 : 2;
        }
        if(argc!=1)throw std::runtime_error("P16C_ARGUMENTS");
'''
    require(prefix==expected_prefix,'exact runtime probe contract')
    restored=restored[:begin]+'    Verilated::commandArgs(argc,argv);\n    try{\n'+restored[end:]
    require(restored==old,'arithmetic/calendar/error checks changed')
    return dict(parent_sha256=PARENT_BENCH,successor_sha256=sha(ROOT/'rtl/tb/stream27_p16c_aw6_v2.cpp'),
                delta='Only single-thread context binding, typed runtime probe and unknown-argument rejection')


def footer_counts():
    # Independent event-only count. No NTT, compiler, native model or cloud API.
    cases=[(-1,-1,-1,-1)]*6
    cases += [(tick,-1,-1,-1) for tick in range(91)]
    cases += [(-1,tick,-1,-1) for tick in range(91)]
    cases += [(-1,-1,tick,-1) for tick in range(91)]
    cases += [(-1,-1,-1,tick) for tick in range(4)]
    counts=dict(events=0,physical=0,eligible=0,resets=0,aborts=0)
    for reset,cancel,disable,bad in cases:
        counts['events']+=101;counts['resets']+=1
        if reset>=0:counts['resets']+=1;counts['aborts']+=1
        for tick in range(85,89):
            if (reset>=0 and tick>=reset) or bad>=0:continue
            counts['physical']+=1
            counts['eligible']+=int((cancel<0 or tick<cancel) and (disable<0 or tick<disable))
    return counts


def prepare(destination):
    require(not (ROOT/'docs/briefs/PAUSE').exists(),'brief PAUSE')
    destination=Path(destination).resolve();require(not destination.exists(),'fresh output only')
    m=json.loads((PARENT/'project/manifest.json').read_text())
    require(sha(PARENT/'project/manifest.json')==PARENT_MANIFEST,'frozen AW6 project manifest')
    from .stream27_p16c_physical_probe_v1 import verify_project
    require(verify_project(PARENT/'project')['sources']==13,'exact frozen compiled RTL')
    delta=verify_bench();source=destination/'inputs/fpga';source.mkdir(parents=True)
    names=[]
    for name,pin in m['source_sha256'].items():
        incoming=PARENT/'project/rtl'/name
        require(sha(incoming)==pin,'frozen RTL drift')
        target=source/'rtl'/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(incoming,target);names.append('rtl/'+name)
    bench='rtl/tb/stream27_p16c_aw6_v2.cpp'
    (source/'rtl/tb').mkdir();shutil.copyfile(ROOT/bench,source/bench)
    lineage={'parent-project-manifest.json':PARENT/'project/manifest.json',
             'parent-native-gate.json':PARENT/'native-gate.json',
             'parent-preparation.json':PARENT/'preparation.json'}
    for name,path in lineage.items():
        target=source/'lineage'/name;target.parent.mkdir(exist_ok=True);shutil.copyfile(path,target)
    counts=footer_counts()
    footer='P16C_AW6_PASS '+' '.join(f'{key}={value}' for key,value in counts.items())+'\n'
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',
        host='UNBOUND_NO_DISPATCH',source_root=str(source),output_parent=str(destination/'UNBOUND_OUTPUT'),
        sources={str(path.relative_to(source)):sha(path) for path in sorted(source.rglob('*')) if path.is_file()},
        build=dict(top=m['top'],sv_sources=names,cpp_source=bench,parameters={'AW':6,'CONTEXTS':1},
                   cflags=['-std=c++17','-O2','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='square-control',argv=['{exe}'],expected_returncode=0,expected_stdout=footer,expected_stderr='')],
        lint_baseline_policy='No baseline admitted; exact -Wall lint must be clean or stop with preserved diagnostics.')
    with (destination/'manifest.json').open('x') as stream:json.dump(manifest,stream,indent=2);stream.write('\n')
    result=dict(status='prepared_unbound_source_only_not_executed',source_count=len(manifest['sources']),
                unchanged_rtl_files=13,parent_manifest_sha256=PARENT_MANIFEST,harness=delta,expected_counts=counts,
                manifest_sha256=sha(destination/'manifest.json'),
                requires='Shared native_package profile, fresh budget evidence, host resume authority and mandatory lint-first',
                no_claims='No HDL/native execution, cloud launch, full-N numerical NTT, clock or complete warm/correction field qualification.')
    with (destination/'preparation.json').open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    return result


if __name__=='__main__':
    import sys
    require(len(sys.argv)==2,'usage: python -B -m fpga.reference.stream27_p16c_native_v2 NEW_OUTPUT')
    print(json.dumps(prepare(Path(sys.argv[1])),indent=2))
