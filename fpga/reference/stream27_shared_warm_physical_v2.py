"""Fresh sizing control successor: correct project name and reset scope.

The v1 prepared project was not launched; retain it as source-only malformed
control history. V2 composes its exact source with three control corrections.
"""
import ast
import hashlib
import json
from . import stream27_shared_warm_physical_v1 as parent


def prepare(destination):
    path=parent.ROOT/'reference/stream27_shared_warm_physical_v1.py';raw=path.read_text()
    if hashlib.sha256(raw.encode()).hexdigest()!='83a5844526b9779a536f22f6351055b0f1810b1c5bb1439981f944297b72ea48':
        raise ValueError('S4_WARM_SIZING_PARENT_DRIFT')
    # Unique function/anchors fail closed against an accidental ancestor edit.
    nodes=[n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef) and n.name=='prepare']
    if len(nodes)!=1:raise ValueError('S4_WARM_SIZING_PARENT_FUNCTION')
    lines=raw.splitlines(keepends=True);n=nodes[0];s=''.join(lines[n.lineno-1:n.end_lineno])
    changes=[("ports=['in_slot_valid'","ports=['rst_n','in_slot_valid'"),
        ("'run.tcl':RUN_TCL","'run.tcl':RUN_TCL.replace('project_open probe','project_open warm')"),
        ("derive_clock_uncertainty\\n'","derive_clock_uncertainty\\n# Component sizing only; reset release excluded like frozen probes.\\nset_false_path -from [get_ports {rst_n}]\\n'"),
        ('reference/stream27_shared_warm_physical_v1.py','reference/stream27_shared_warm_physical_v2.py')]
    for old,new in changes:
        expected=2 if old=='reference/stream27_shared_warm_physical_v1.py' else 1
        if s.count(old)!=expected:raise ValueError('S4_WARM_SIZING_CONTROL_ANCHOR:'+old)
        s=s.replace(old,new)
    namespace=dict(vars(parent));exec(compile(s,str(path)+'[project/reset scope successor]','exec'),namespace)
    result=namespace['prepare'](destination)
    result['parent_preparer_sha256']=hashlib.sha256(raw.encode()).hexdigest()
    return result


if __name__=='__main__':
    import sys
    if len(sys.argv)!=2:raise ValueError('S4_WARM_SIZING_V2_USAGE')
    r=prepare(sys.argv[1]);print(json.dumps({k:r[k] for k in ('status','project_manifest_sha256','archive_sha256','source_files','parent_preparer_sha256')},indent=2))
