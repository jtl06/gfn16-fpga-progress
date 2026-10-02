"""Exact derived sources and command/fatal contracts for eight T5 mutants.

No HDL execution. Every pair owns a fresh control and a fresh mutant build.
"""
import re
from .core27_prefill_mutations import MUTANTS, mutate
from .core27_prefill_qualification_mutations import TEE_MUTANTS, mutate_tee, tee_control

CORE = 'rtl/kernel/genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill.sv'
CARRY = 'rtl/kernel/genefer_carry_prefix_stream_precision_emit.sv'
BRIDGE = 'rtl/tb/core27_prefill_fault_bridge.sv'
OBSERVER = 'rtl/tb/core27_prefill_tail_probe_v3.sv'
NAMES = tuple(MUTANTS)+tuple(TEE_MUTANTS)


def require(ok, why):
    if not ok: raise ValueError(why)


def bridge(source):
    substitutions = [
        ('module genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill #(',
         'module core27_prefill_fault_bridge #('),
        ('input logic clk, rst_n, load_we, read_en, start,',
         'input logic clk, rst_n, load_we, read_en, start,\n    input logic [2:0] sim_host_error,\n    input logic sim_carry_error,'),
        ('logic carry_load,carry_read,carry_start,carry_valid,carry_busy,carry_done,carry_error;',
         'logic carry_load,carry_read,carry_start,carry_valid,carry_busy,carry_done,carry_error;\n    logic native_carry_error;\n    assign carry_error=native_carry_error | sim_carry_error;'),
        ('logic [2:0] ntt_host_error,ntt_scalar_valid;',
         'logic [2:0] ntt_host_error,ntt_scalar_valid;\n    logic [2:0] native_ntt_host_error;\n    assign ntt_host_error=native_ntt_host_error | sim_host_error;'),
        ('.host_error(ntt_host_error[f])', '.host_error(native_ntt_host_error[f])'),
        ('.error(carry_error)', '.error(native_carry_error)'),
    ]
    for old, new in substitutions:
        require(source.count(old) == 1, 'exact simulation bridge anchor')
        source = source.replace(old, new, 1)
    return '// Simulation-only explicit fault bridge; never synthesize or promote this top.\n'+source


def pair_sources(root, name):
    require(name in NAMES, 'known one-mutation pair')
    core, carry = (root/CORE).read_text(), (root/CARRY).read_text()
    require(bridge(core) == (root/BRIDGE).read_text(), 'frozen fault bridge exact derivation')
    if name in MUTANTS:
        mutant_core, fatal = mutate(core, name)
        control = {CORE: core, CARRY: carry, BRIDGE: bridge(core)}
        mutant = {CORE: mutant_core, CARRY: carry, BRIDGE: bridge(mutant_core)}
    else:
        mutant_carry, fatal = mutate_tee(carry, name)
        control = {CORE: core, CARRY: tee_control(carry), BRIDGE: bridge(core)}
        mutant = {CORE: core, CARRY: mutant_carry, BRIDGE: bridge(core)}
    observer = (root/OBSERVER).read_text()
    lines = [i for i,line in enumerate(observer.splitlines(), 1) if '"'+fatal+'"' in line]
    require(bool(lines), 'typed independent observer exists')
    return control, mutant, dict(fatal=fatal, observer=OBSERVER, lines=lines,
             stripped_guard='T5_EMIT_SIGNED32_REPRESENTATION' if name in TEE_MUTANTS else None)


def command(exe, vector, name):
    require(name in NAMES, 'known mutation command')
    if name == 'eligibility_after_load': return [str(exe),'--reload-control',str(vector),'control']
    if name == 'late_host_error': return [str(exe),'--tail-error',str(vector),'6','final','control']
    return [str(exe),'--changed-base',str(vector),'control']


def check_footer(output, argv):
    require(len(argv) in (4,6), 'targeted command shape')
    mode = argv[1]
    simple = mode in ('--changed-base','--base-reject','--reload-control')
    require((simple and len(argv)==4) or (not simple and len(argv)==6), 'targeted argument count')
    require(argv[-1]=='control' and (simple or mode in ('--tail-reset','--tail-error','--tail-carry-error')), 'targeted control mode')
    age, row = ('0','none') if simple else (argv[3],argv[4])
    counts = (3,3,0) if mode=='--changed-base' else (2,2,1) if mode=='--base-reject' else (2,2,0) if mode=='--reload-control' else (1,1,1)
    expected = dict(mode=mode,age=age,row=row,row_index='0' if row=='first' else '1',middle_aliases_final='1',
                    event_hits='1',successful=str(counts[0]),readbacks=str(counts[1]),recoveries=str(counts[2]))
    matches = re.findall(r'^T5_TARGET_PASS (.*)$',output,re.M)
    require(len(matches)==1, 'one targeted footer')
    tokens = [x.split('=',1) for x in matches[0].split()]
    require(all(len(x)==2 for x in tokens) and len({x[0] for x in tokens})==len(tokens), 'unique footer fields')
    require(dict(tokens)==expected, 'command-bound targeted footer')
    return expected


def check_fatal(output, returncode, contract):
    require(returncode == -6, 'native SIGABRT required, not compiler/C++/timeout failure')
    require('T5_TARGET_PASS' not in output, 'mutant cannot complete normally')
    errors = re.findall(r'^.*%(?:Fatal|Error):\s+(\S+):(\d+): Assertion failed in (\S+): (.*)$',output,re.M)
    require(len(errors)==1, 'exactly one native typed fatal')
    filename,line,scope,message = errors[0]
    require(filename.rsplit('/',1)[-1] == contract['observer'].rsplit('/',1)[-1] and
            int(line) in contract['lines'] and (scope=='TOP.core27_prefill_tail_probe_v3' or
            scope.startswith('TOP.core27_prefill_tail_probe_v3.')) and
            message.strip()==contract['fatal'], 'exact observer/source-line/scoped fatal attribution')
    return dict(returncode=returncode, fatal=message.strip(), source_line=int(line), scope=scope)
