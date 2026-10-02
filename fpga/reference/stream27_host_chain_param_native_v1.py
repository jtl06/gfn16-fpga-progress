"""Actual shared-P8 scalar host gate; long feed remains separately unresolved.

Reuses the source-bound scalar-v6 corpus/pairedT5b/width/epoch/reset/error suite,
not inherited P16 execution. Changes only actual P/configured row count and
profile lower guard from the generic carry setup. No output oracle conversion.
"""
import ast
import hashlib
import json
from pathlib import Path
import re
from . import stream27_host_core_native_v6 as scalar
from . import stream27_host_chain_param_v1 as core

ROOT=core.ROOT
PIN='f9e36480bf0d1f47eb7bdef4db4a424575232c9bd1e868205457bb3515909045'


def prepare(destination,*,n=32,p=8):
    if p!=8 or n not in (32,256):raise ValueError('S4_P8_SCALAR_NATIVE_GEOMETRY')
    path=ROOT/'reference/stream27_host_core_native_v6.py';raw=path.read_text()
    if hashlib.sha256(raw.encode()).hexdigest()!=PIN:raise ValueError('S4_P8_SCALAR_PARENT_DRIFT')
    node=next(x for x in ast.parse(raw).body if isinstance(x,ast.FunctionDef) and x.name=='prepare')
    body=''.join(raw.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    def compile_core(n,**kwargs):return core.prepare(n,p,**kwargs)
    ns=dict(vars(scalar));ns['compile_core']=compile_core;exec(compile(body,'[actual shared P8 scalar host]','exec'),ns)
    r=ns['prepare'](destination,n=n);destination=Path(destination).resolve();source=destination/'inputs/fpga'
    bench=source/'rtl/tb/stream27_host_core_v1.cpp';s=bench.read_text();old='static void clear(DUT& d){'
    if s.count(old)!=1:raise ValueError('S4_P8_SCALAR_FEED_CLEAR')
    s=s.replace(old,old+'d.feed_mode=0;d.command_valid=0;d.command_double=0;d.command_index=0;d.command_generation=0;')
    if s.count('N/16')!=1:raise ValueError('S4_P8_SCALAR_COLD_ROWS')
    s=s.replace('N/16','N/P');bench.write_text(s)
    header=source/'rtl/tb/s4_host_config_v1.h';s=header.read_text();k=2*n+24*p;minimum=max(2*n+5,(2*k+2)//3+1)
    s,count=re.subn(r'MIN_BASE=\d+',f'MIN_BASE={minimum}',s)
    if count!=1:raise ValueError('S4_P8_SCALAR_BASE_GUARD')
    s=s.replace(f'S4_SCALAR_HOST_T5B_AW{n.bit_length()-1}_PASS',f'S4_SHARED_P8_SCALAR_HOST_T5B_AW{n.bit_length()-1}_PASS')
    s+=f'constexpr unsigned P={p};\n';header.write_text(s)
    mpath=destination/'manifest.json';m=json.loads(mpath.read_text());m['build']['parameters']['P']=p
    m['steps'][0]['name']=f's4-aw{n.bit_length()-1}-p8-scalar-host-t5b'
    m['steps'][0]['expected_stdout']=m['steps'][0]['expected_stdout'].replace('S4_SCALAR_HOST','S4_SHARED_P8_SCALAR_HOST')
    local='reference/stream27_host_chain_param_native_v1.py';target=source/'lineage'/local;target.write_bytes((ROOT/local).read_bytes())
    m['sources']={str(path.relative_to(source)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(source.rglob('*')) if path.is_file()}
    mpath.write_text(json.dumps(m,indent=2)+'\n');r.update(manifest_sha256=hashlib.sha256(mpath.read_bytes()).hexdigest(),source_count=len(m['sources']),p=p,
      scope='Actual P8 shared three-field/CRT/carry/canonical/copied scalar host finite14job23square/T5b gate. feed_mode0; no long PRP or unresolved long reset qualification.',
      parameter_delta=f'P8/N{n}, ROWS=N/8, MIN_BASE={minimum}, warm interval/physical carry from actual shared geometry, no P16 execution inheritance.',
      numeric_delta='Independent scalar-v6 immutable corpus and exact signed96/T5b assertions unchanged; real P8 hardware path and profile/cold row counts tested.',
      pending_long='Long controller v3 has preserved reset-afterwarm diagnostic failure; no long gate or completion is inferred from this finite scalar suite.')
    (destination/'preparation.json').write_text(json.dumps(r,indent=2)+'\n');return r


if __name__=='__main__':
    import sys
    r=prepare(sys.argv[1],n=int(sys.argv[2]));print(json.dumps({k:r[k] for k in ('status','manifest_sha256','source_count','top','p','scope')},indent=2))
