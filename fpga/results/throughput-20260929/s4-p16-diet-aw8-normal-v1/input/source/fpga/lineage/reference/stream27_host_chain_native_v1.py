"""Frozen scalar-v6 regression plus finite real long-feed native packages.

Only N32/N256 ordinary modular integers are evaluated by this preparer. Native
HDL, runtime limits, immutable source/class/negative gates belong to dispatcher.
"""
import ast
import hashlib
import json
from pathlib import Path
import shutil
from . import stream27_host_core_native_v6 as parent
from . import stream27_host_chain_v1 as core
from . import stream27_host_chain_model_v1 as model

ROOT=core.ROOT
PIN='f9e36480bf0d1f47eb7bdef4db4a424575232c9bd1e868205457bb3515909045'
BENCH='rtl/tb/stream27_host_chain_v1.cpp'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(destination,*,n=32,ordinal=False):
    if n not in (32,256) or ordinal and n!=32:raise ValueError('S4_LONG_SMALL_NATIVE_GEOMETRY')
    path=ROOT/'reference/stream27_host_core_native_v6.py';raw=path.read_text()
    if sha(path)!=PIN:raise ValueError('S4_LONG_SCALAR_NATIVE_PARENT_DRIFT')
    node=next(x for x in ast.parse(raw).body if isinstance(x,ast.FunctionDef) and x.name=='prepare')
    body=''.join(raw.splitlines(keepends=True)[node.lineno-1:node.end_lineno]);namespace=dict(vars(parent))
    namespace['compile_core']=core.prepare;exec(compile(body,'[long host scalar baseline]','exec'),namespace)
    r=namespace['prepare'](destination,n=n);destination=Path(destination).resolve();source=destination/'inputs/fpga'
    legacy=source/'rtl/tb/stream27_host_core_v1.cpp';s=legacy.read_text();old='static void clear(DUT& d){'
    if s.count(old)!=1:raise ValueError('S4_LONG_CLEAR_ADDITIVE_INPUTS')
    legacy.write_text(s.replace(old,old+'d.feed_mode=0;d.command_valid=0;d.command_double=0;d.command_index=0;d.command_generation=0;'))
    shutil.copyfile(ROOT/BENCH,source/BENCH)
    programs=[model.program(n,'paired'),model.program(n,'prp')]
    if n==32:programs[0],programs[1]=programs[1],programs[0]
    lines=[f'{n.bit_length()-1} 2']
    for p in programs:
        paired=n==32 or p['kind']=='paired'
        lines += [f"{p['base']} {p['count']} {int(paired)}",' '.join(map(str,p['initial'])),
                  ' '.join(map(str,p['bits'])),' '.join(map(str,p['expected']))]
    asset='assets/long-program-v1.txt';(source/asset).write_text('\n'.join(lines)+'\n')
    header=source/'rtl/tb/s4_host_config_v1.h';s=header.read_text();aw=n.bit_length()-1
    s+=f'''constexpr unsigned FIRST_DIGIT={r['geometry']['first_digit']};
constexpr const char* LONG_LABEL="S4_LONG_HOST_AW{aw}_PASS",*ORDINAL_LABEL="S4_LONG_ORDINAL_AW{aw}_PASS";
''';header.write_text(s)
    for name in (BENCH,'reference/stream27_host_chain_native_v1.py','reference/stream27_host_chain_model_v1.py','tests/test_stream27_host_chain_v1.py'):
        target=source/'lineage'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    mpath=destination/'manifest.json';m=json.loads(mpath.read_text());scalar_footer=m['steps'][0]['expected_stdout']
    operations=sum(p['count'] for p in programs);descriptors=operations-2
    footer=f'S4_LONG_HOST_AW{aw}_PASS jobs=2 operations={operations} descriptors={descriptors} true_final_rows={2*n//16} reads={2*n} faults=4 reset_aborts=2\n'
    m['build']['cpp_source']=BENCH
    if ordinal:
        m['steps']=[dict(name='s4-long-ordinal-zero-control',argv=['{exe}','--ordinal'],expected_returncode=0,
          expected_stdout=f'S4_LONG_ORDINAL_AW{aw}_PASS operations=65540 descriptors=65539 true_final_rows={n//16} reads={n}\n',expected_stderr='')]
    else:
        m['steps'][0].update(name=f's4-aw{aw}-long-host-real-prp',argv=['{exe}','{root}/assets/host-corpus-v1.txt','{root}/'+asset],expected_stdout=scalar_footer+footer)
        m['steps'].append(dict(name='s4-long-negative-control-oracle',argv=['{exe}','{root}/assets/host-corpus-v1.txt','{root}/'+asset,'--negative-feed'],
          expected_returncode=1,expected_stdout=scalar_footer,expected_stderr=f'S4_LONG_CONTROL_TYPED expected={operations+1} actual={operations}\n'))
    m['sources']={str(path.relative_to(source)):sha(path) for path in sorted(source.rglob('*')) if path.is_file()}
    mpath.write_text(json.dumps(m,indent=2)+'\n')
    r.update(manifest_sha256=sha(mpath),source_count=len(m['sources']),long_counts=dict(jobs=2,operations=operations,descriptors=descriptors,
      true_final_rows=2*n//16,reads=2*n,faults=4,reset_aborts=2),ordinal=ordinal,
      long_programs=[dict(kind=p['kind'],count=p['count'],paired=n==32 or p['kind']=='paired',
                          oracle=p['oracle'],exponent_sha256=hashlib.sha256(str(p['exponent']).encode()).hexdigest()) for p in programs],
      control_scope='Actual pre-edge enqueue/pop/full simultaneous exchange, bounded gaps, underflow/wrong descriptor sticky faults, reset nonempty FIFO+numeric full-reload recovery.',
      ordinal_scope='65540 alternating control bits over zero invariant, actual full-width final raw load and host done; control witness not a random-data PRP.' if ordinal else None,
      limitations=['Not fullN PRP or P8 whole arithmetic qualification','AW8 genuine PRP final ordinary-pow comparison is not paired7653-square T5b replay; separate256-operation paired long gate remains explicit','No physical clock or promotion'])
    (destination/'preparation.json').write_text(json.dumps(r,indent=2)+'\n');return r


if __name__=='__main__':
    import sys
    r=prepare(sys.argv[1],n=int(sys.argv[2]),ordinal=len(sys.argv)==4 and sys.argv[3]=='ordinal')
    print(json.dumps({k:r[k] for k in ('status','manifest_sha256','source_count','top','long_counts','ordinal')},indent=2))
