"""Controlled whole-core G4 driver delta for A10, no HDL or full-N arithmetic.

Only top/context/geometry, explicit format3 count and three-phase ledger change.
Host/digit/quarantine/carry/output comparison semantics remain the parent driver.
Source-bound full-N parent vector assets may be reused; execution/oracles run
fresh later, on an admitted native host, never on this preparation machine.
"""
import hashlib
from pathlib import Path
from fpga.reference import a10_banked_engine_generate_v1 as gen

ROOT=gen.ROOT/'fpga'
PARENT='rtl/tb/square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont.cpp'
PARENT_SHA='5680df12450b1c301361b23264f3a56a386e5e8dbecd5ca7ad1324ecd1dcd526'
BENCH='rtl/tb/a10_whole_geometry_v1.cpp'
VECTORS='results/throughput-20260929/core27-prefetch-r2-rootfused-crtmont-aw16-v1'
VECTOR_PINS={'segment0.txt':'f7be581453f19dce034d3aeadd4ca29e36bf150f125757a3d40fdd6af3fe3e30',
             'segment1.txt':'e758300d82d2eca169486d4c7282c0bc1c0a56bb5676c2ec34072dd6dd617eb5',
             'independent-review-v1.json':'ec5e1adad36eb815b2525b30f810a1decf760a5ad1d4ec1e43502a7537ea2b0a'}

def need(ok,message):
    if not ok:raise ValueError(message)

def source_guard():
    gen.source_guard()
    need(hashlib.sha256((ROOT/PARENT).read_bytes()).hexdigest()==PARENT_SHA,'A10_WHOLE_DRIVER_PARENT_DRIFT')
    for name,pin in VECTOR_PINS.items():
        need(hashlib.sha256((ROOT/VECTORS/name).read_bytes()).hexdigest()==pin,'A10_WHOLE_VECTOR_EVIDENCE_DRIFT '+name)

def bench_source():
    source_guard();s=(ROOT/PARENT).read_text()
    old='genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont'
    need(s.count(old)==2,'A10_WHOLE_EXACT_TOP_RENAME');s=s.replace(old,gen.CORE)
    declaration='        V'+gen.CORE+' d;\n';s=gen.once(s,declaration,'')
    start=r'''        VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
        Vgenefer_square_core27_a10_crtmont_v1 d{&context};
        if(argc==2 && std::string(argv[1])=="--runtime-probe"){
            std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
            return context.threads()==1 && d.threads()==1 ? 0 : 2;
        }
'''
    s=gen.once(s,'        Verilated::commandArgs(argc,argv);\n',start)
    s=gen.once(s,'        const unsigned profile_words=(2*lg+2)*257;',
        '        if(n!=(1u<<A10_AW))throw std::runtime_error("A10_WHOLE_COMPILED_GEOMETRY");\n        const unsigned profile_words=4;')
    old_block=gen.region(s,'        auto setup=[&](bool reverse)', '        auto tick=[&]()')
    replacement=r'''        const uint64_t point=(n+63)/64+7;
        const uint64_t expected_seed_setup=0;
        const uint64_t expected_ntt=point+2*uint64_t(lg)*((n+127)/128+9)+6;
'''
    s=gen.once(s,old_block,replacement)
    s='// Additive A10 whole geometry driver; controlled G4 host/oracle delta only.\n#ifndef A10_AW\n#define A10_AW 5\n#endif\n'+s
    return s

def corpus_metadata(text):
    """Parse headers/order/extent only; not a full-N numeric oracle."""
    lines=text.splitlines();need(lines,'A10_WHOLE_CORPUS_EMPTY')
    n=int(lines[0]);need(n in (32,256,65536),'A10_WHOLE_CORPUS_GEOMETRY')
    current=None;cache=False;runs=[];loads=[];guards=[];i=1
    while i<len(lines):
        words=lines[i].split();need(words,'A10_WHOLE_CORPUS_EMPTY_LINE');cmd=words[0]
        if cmd in ('LOAD','LOAD_KEEP'):
            need(len(words)==3 and i+1<len(lines),'A10_WHOLE_LOAD_HEADER')
            need(len(lines[i+1].split())==n,'A10_WHOLE_LOAD_EXTENT')
            current=dict(label=words[1],base=int(words[2]));loads.append(dict(current,keep=cmd=='LOAD_KEEP'))
            if cmd=='LOAD':cache=False
            i+=2
        elif cmd in ('RUN','RUN_NOREAD'):
            need(current is not None and len(words)==3 and words[2] in ('0','1') and i+1<len(lines),'A10_WHOLE_RUN_HEADER')
            need(len(lines[i+1].split())==n,'A10_WHOLE_EXPECTED_EXTENT')
            runs.append(dict(label=words[1],base=current['base'],double=int(words[2]),readback=cmd=='RUN',profile_before=int(cache)))
            cache=True;i+=2
        elif cmd in ('BADBASE','BADDIGIT','BADDIGIT_AT'):
            guards.append(dict(command=cmd,arguments=words[1:]));cache=False;i+=1
        else:raise ValueError('A10_WHOLE_CORPUS_UNSUPPORTED_COMMAND '+cmd)
    need(runs,'A10_WHOLE_NO_OPERATIONS')
    return dict(n=n,aw=n.bit_length()-1,operations=len(runs),readbacks=sum(r['readback'] for r in runs),
                cold=sum(not r['profile_before'] for r in runs),warm=sum(r['profile_before'] for r in runs),
                loads=loads,runs=runs,guards=guards,full_N_numeric_arithmetic_performed=False)
