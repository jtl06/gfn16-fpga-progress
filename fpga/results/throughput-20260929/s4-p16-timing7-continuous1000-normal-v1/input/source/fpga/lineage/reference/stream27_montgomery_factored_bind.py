"""Isolated MONT_FACTORED flag fragment, never a shared-generator writer.

Flag0 is an exact deep copy. Flag1 only substitutes two frozen Montgomery
definitions with the independently qualified factored leaf and changes their
instantiation identifiers. No top parameter, calendar, root or arithmetic
consumer is changed; frozen source dependencies remain lineage evidence.
"""
from copy import deepcopy
import hashlib
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_montgomery_factored_bind.py'
NEW='rtl/kernel/genefer_stream27_montgomery_factored_v1.sv'
NEW_PIN='866c2b19c9e6afbbb56ce71089288334579f90e977ca139b41097d0f9191c690'
LEAVES={
 'genefer_montgomery_mul27_sparse_pipe':('501d0ce309a3915f7aed0f3bde14ba1ee8d56ddc5f6abef1f2f5bb572d64db4b','genefer_stream27_montgomery_factored_v1'),
 'genefer_montgomery_mul28x27_sparse_pipe_v2':('a93cb002eb08e585e62a847ef4b070175ae8108919da30ea5bf67dad3a597026','genefer_stream27_montgomery28x27_factored_v1')}
def sha(raw):return hashlib.sha256(raw).hexdigest()
def need(ok,why):
    if not ok:raise ValueError(why)
def bind(bundle,*,MONT_FACTORED=1):
    need(type(MONT_FACTORED) is int and MONT_FACTORED in (0,1),'L3_BIND_LITERAL_FLAG')
    out=deepcopy(bundle)
    if MONT_FACTORED==0:return out
    need('montgomery_factored' not in out,'L3_BIND_NOT_ALREADY_BOUND')
    files=out['files'];need(type(files) is dict and all(type(x) is str for x in files.values()),'L3_BIND_TEXT_BUNDLE')
    need(set(out['rtl_sources'])=={n for n in files if n.endswith('.sv')},'L3_BIND_COMPILED_CLOSURE')
    need(out['generated_sha256']=={name:sha(text.encode()) for name,text in files.items()},'L3_BIND_PARENT_GENERATED_SHA')
    raw=(ROOT/NEW).read_bytes();need(sha(raw)==NEW_PIN,'L3_BIND_NATIVE_LEAF_PIN')
    removed={}
    for old,(pin,new) in LEAVES.items():
        name=old+'.sv';need(name in files and sha(files[name].encode())==pin,'L3_BIND_FROZEN_DEFINITION '+old)
        removed[name]=files.pop(name)
    changes={};counts={old:0 for old in LEAVES}
    for name,text in list(files.items()):
        if not name.endswith('.sv'):continue
        changed=text
        for old,(_,new) in LEAVES.items():
            changed,number=re.subn(r'\b'+old+r'\b',new,changed);counts[old]+=number
        # Byte-exact inverse proves no hidden port/root/calendar/control edit.
        reverse=changed
        for old,(_,new) in LEAVES.items():reverse=re.sub(r'\b'+new+r'\b',old,reverse)
        need(reverse==text,'L3_BIND_IDENTIFIER_ONLY '+name)
        if changed!=text:
            changes[name]=dict(parent_sha256=sha(text.encode()),bound_sha256=sha(changed.encode()))
            files[name]=changed
    need(all(v>0 for v in counts.values()),'L3_BIND_BOTH_CANONICAL_LAZY_CONSUMERS')
    files[Path(NEW).name]=raw.decode()
    out['rtl_sources']=[n for n in files if n.endswith('.sv')]
    out['source_dependencies']=list(dict.fromkeys(out['source_dependencies']+[NEW,SELF]))
    out['source_sha256']={**out['source_sha256'],NEW:NEW_PIN,SELF:sha((ROOT/SELF).read_bytes())}
    out['generated_sha256']={name:sha(text.encode()) for name,text in files.items()}
    out['montgomery_factored']=dict(flag=1,leaf_sha256=NEW_PIN,removed_definitions={n:sha(t.encode()) for n,t in removed.items()},
        identifier_changes=changes,identifier_occurrences=counts,leaf_latency_edges=3,II=1,R=1<<32,
        consumer_ABI_changed=False,root_tables_changed=False,calendar_changed=False,
        source_multiplier_delta=0,field_resources_measured=False,whole_P16_GO=False)
    return out
