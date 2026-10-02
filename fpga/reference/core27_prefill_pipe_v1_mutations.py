"""Eight named T5b negative recipes; no native execution or qualification.

Fresh control must pass before each mutant. A compiler failure, arbitrary data
mismatch, timeout or generic C++ exception is NOT a successful negative gate.
The observed native fatal must match observer basename, line, scope and SIGABRT.
"""
from . import core27_prefill_pipe_v1_structure as design
from . import core27_prefill_pipe_v1_gates as gates
from .core27_prefill_mutations import MUTANTS
from .core27_prefill_qualification_mutations import TEE_MUTANTS,mutate_tee,tee_control

CORE='rtl/kernel/'+design.CORE+'.sv'
CARRY='rtl/kernel/genefer_carry_prefix_stream_precision_emit.sv'
BRIDGE='rtl/tb/'+gates.BRIDGE+'.sv'
OBSERVER='rtl/tb/'+gates.TAIL+'.sv'
NAMES=tuple(MUTANTS)+tuple(TEE_MUTANTS)
OVERRIDES={
 'write_address':(
  "assign addr=(prefill_window || state==CONVERT) ? field_launch_addr[f][1] : AW'(issue_count);",
  "assign addr=prefill_window ? field_launch_addr[f][1]+AW'(IO_STEP) : state==CONVERT ? field_launch_addr[f][1] : AW'(issue_count);",
  'T5_MONITOR_WRITE_ADDRESS'),
 'field_mask':(
  '.vector_lane_mask((prefill_window || state==CONVERT) ? field_launch_mask[f][1] : IO_MASK)',
  ".vector_lane_mask(prefill_window ? (f==1 ? field_launch_mask[f][1] & 16'hfffe : field_launch_mask[f][1]) : state==CONVERT ? field_launch_mask[f][1] : IO_MASK)",
  'T5_MONITOR_WRITE_MASK')}


def pair_sources(root,name):
    if name not in NAMES:raise ValueError('one named T5b mutant')
    design.validate(root);gates.validate(root)
    core=(root/CORE).read_text();carry=(root/CARRY).read_text()
    if name in TEE_MUTANTS:
        changed,fatal=mutate_tee(carry,name)
        fresh={CORE:core,CARRY:tee_control(carry),BRIDGE:gates.bridge(core)}
        mutant=dict(fresh,**{CARRY:changed})
    else:
        before,after,fatal=OVERRIDES.get(name,MUTANTS[name])
        changed=design.once(core,before,after)
        fresh={CORE:core,CARRY:carry,BRIDGE:gates.bridge(core)}
        mutant=dict(fresh,**{CORE:changed,BRIDGE:gates.bridge(changed)})
    lines=[i for i,line in enumerate((root/OBSERVER).read_text().splitlines(),1) if '"'+fatal+'"' in line]
    if not lines:raise ValueError('typed independent observer required')
    mode='--reload-control' if name=='eligibility_after_load' else '--tail-error' if name=='late_host_error' else '--changed-base'
    argv=['{exe}',mode,'{target_vector}']+(['9','final'] if name=='late_host_error' else [])+['control']
    return fresh,mutant,dict(name=name,fatal=fatal,observer=OBSERVER,lines=lines,
        expected_signal=6,required_scope='TOP.'+gates.TAIL,argv=argv,
        stripped_guard='T5_EMIT_SIGNED32_REPRESENTATION' if name in TEE_MUTANTS else None,
        status='recipe_only_requires_fresh_control_and_native_fatal_review')
