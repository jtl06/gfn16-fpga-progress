"""Exact frozen-bench delta for format2 fusion; no build or simulation runner."""
import hashlib
from pathlib import Path

BENCH_SHA = '3f923cd47e7b9729dc16005e702c8d9ed0d7c50caa2988476e297a01caeb5d0c'
WRAPPER_SHA = '68a4e6c2bbb6e32780d13467e94db82bc98a368991bd513ff3860d4ae9d688a2'
OLD_MODEL = 'Vgenefer_square_core27_stream_prefetch'
MODEL = 'Vgenefer_square_core27_stream_prefetch_r2'
ABORT_CONDITIONS = ('d.root_cycles>=target', 'elapsed>=target', 'd.crt_cycles>=63',
                    'd.root_cycles>uint64_t(phase)*profile_words/4+2', 'phase>=3')


def pinned(text, wanted):
    if hashlib.sha256(text.encode()).hexdigest()!=wanted:
        raise ValueError('frozen bench identity mismatch')


def replace(text, old, new, count=1):
    if text.count(old)!=count:
        raise ValueError('ambiguous bench delta: '+old)
    return text.replace(old,new)


def bench_source(original):
    pinned(original,BENCH_SHA)
    text=replace(original,OLD_MODEL,MODEL,2)
    text=replace(text,'// Fixed atomic27 conversion: ceil(N/16)+9 clocks.',
                 '// Format2 fused conversion: ceil(N/16)+6 clocks.')
    text=replace(text,'const unsigned commit=(n+15)/16+9;',
                 'const unsigned commit=(n+15)/16+6;')
    text=replace(text,'                uint64_t elapsed=0;',
                 '                uint64_t elapsed=0; bool abort_reached=false;')
    for condition in ABORT_CONDITIONS:
        text=replace(text,f'if({condition})break;',
                     f'if({condition}){{abort_reached=true;break;}}')
    text=replace(text,'                if(cmd=="ABORT") { reset();++aborts;continue; }',
        '''                if(cmd=="ABORT") {
                    if(!abort_reached || !d.busy || d.done)
                        throw std::runtime_error("abort did not interrupt requested live phase "+label);
                    reset();++aborts;continue;
                }''')
    return replace(text,'                const unsigned expected_loads=cache_before?0:1;',
        '''                if(d.conversion_cycles!=uint64_t((n+15)/16)+6)
                    throw std::runtime_error("fused conversion counter mismatch "+label);
                const unsigned expected_loads=cache_before?0:1;''')


def wrapper_source(original):
    pinned(original,WRAPPER_SHA)
    text=replace(original,'// Private precision-stream thread adapter; wrapper and included bench are keyed together.',
                 '// Private format2 fusion adapter; wrapper and included bench are keyed together.')
    text=replace(text,'square_core27_stream_prefetch.cpp','square_core27_stream_prefetch_r2.cpp')
    text=replace(text,'core27_stream_main','core27_prefetch_r2_main',2)
    text=replace(text,OLD_MODEL,MODEL)
    return replace(text,'CORE27_PREFETCH_RUNTIME_THREADS','CORE27_PREFETCH_R2_RUNTIME_THREADS',9)


def validate_bench_files(root):
    tb=Path(root)/'rtl/tb'
    result={}
    for old,new,transform in (
        ('square_core27_stream_prefetch.cpp','square_core27_stream_prefetch_r2.cpp',bench_source),
        ('square_core27_stream_prefetch_threaded.cpp','square_core27_stream_prefetch_r2_threaded.cpp',wrapper_source),
    ):
        actual=(tb/new).read_text()
        if actual!=transform((tb/old).read_text()):
            raise ValueError('unreviewed fusion bench delta: '+new)
        result['rtl/tb/'+new]=hashlib.sha256(actual.encode()).hexdigest()
    return result
