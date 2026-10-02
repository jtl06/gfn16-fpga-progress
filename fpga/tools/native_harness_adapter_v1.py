"""Pure additive harness adapters; one shared context implementation per build.

Implicit benches use a tiny selection header and the same C++ adapter. Explicit
benches use a guarded, thread-count-independent source successor; arithmetic,
event waits and expected outputs are preserved. No frozen input is edited.
"""
from pathlib import PurePosixPath
import re

ADAPTER = 'rtl/tb/native_runtime_context_v1.cpp'
HEADER = 'rtl/tb/native_runtime_context_v1.h'
SELECTION = 'rtl/tb/native_runtime_selection_v1.h'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def implicit_selection(bench, model):
    path = PurePosixPath(bench)
    need(type(bench) is str and path.parent == PurePosixPath('rtl/tb')
         and path.suffix == '.cpp' and re.fullmatch('[A-Za-z_][A-Za-z_0-9]*', path.stem), 'local bench selection')
    need(type(model) is str and re.fullmatch('V[A-Za-z_][A-Za-z_0-9]*', model), 'generated model identifier')
    return ('// Immutable role data; runtime count is a compiler flag.\n'
            '#define GFN16_RUNTIME_BENCH "' + path.name + '"\n'
            '#define GFN16_RUNTIME_MODEL ' + model + '\n')


def explicit_successor(source):
    """Preserve the frozen T5b targeted bench apart from context operations."""
    need(type(source) is str, 'explicit harness text')
    replacements = [
        ('#include "verilated.h"', '#include "verilated.h"\n#include "native_runtime_context_v1.h"'),
        ('VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);',
         'VerilatedContext context;gfn16_runtime::configure(context,argc,argv);'),
        ('            std::cout<<"{\\"context_threads\\":"<<context.threads()<<",\\"model_threads\\":"<<d.threads()<<",\\"expected_threads\\":1}\\n";\n'
         '            return context.threads()==1 && d.threads()==1?0:2;',
         '            return gfn16_runtime::probe(context,d);'),
        ('need(context.threads()==1 && d.threads()==1,"T5_CONTEXT_DRIFT");',
         'need(gfn16_runtime::matches(context,d),"T5_CONTEXT_DRIFT");'),
    ]
    for before, after in replacements:
        need(source.count(before) == 1, 'unique frozen context anchor')
        source = source.replace(before, after, 1)
    return source
