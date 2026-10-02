"""Bounded P8-b AW5 source input for the existing r38/global queue mechanism."""
import hashlib
import json
from pathlib import Path
from .stream27_p8b_probe_v1 import compile_probe

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def counts():
    cases=[(-1,-1,-1,-1)]*6
    for tick in range(79):cases.extend([(tick,-1,-1,-1),(-1,tick,-1,-1),(-1,-1,tick,-1)])
    cases.extend([(-1,-1,-1,tick) for tick in range(4)])
    c=dict(events=0,physical=0,eligible=0,resets=0,aborts=0)
    for reset,cancel,disable,bad in cases:
        c['events']+=81;c['resets']+=1
        if reset>=0:c['resets']+=1;c['aborts']+=1
        for tick in range(73,77):
            if bad>=0 or reset>=0 and tick>=reset:continue
            c['physical']+=1
            c['eligible']+=int((cancel<0 or tick<cancel) and (disable<0 or tick<disable))
    return c


def prepare(destination):
    destination=Path(destination).resolve()
    assert not destination.exists()
    b=compile_probe();source=destination/'inputs/fpga'
    for name,text in b['files'].items():
        target=source/'rtl'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text)
    bench='rtl/tb/stream27_p8b_aw5_v1.cpp'
    (source/'rtl/tb').mkdir();(source/bench).write_bytes((ROOT/bench).read_bytes())
    deps=['reference/stream27_p8b_probe_v1.py','reference/stream27_p8b_native_v1.py',bench,
        'reference/stream27_p16c_physical_probe_v1.py','reference/merged_stream27_model_v1.py',
        'reference/merged_stream27_root_compile_v1.py']
    lineage=dict(geometry=b['geometry'],calendar=b['calendar'],exact_changes=b['exact_changes'],
                 source_sha256={n:sha(ROOT/n) for n in deps},numeric_limit=256,physical_fit_qualified=False)
    (source/'lineage').mkdir();(source/'lineage/p8b-source-v1.json').write_text(json.dumps(lineage,indent=2)+'\n')
    expected=counts();footer='P8B_AW5_PASS '+' '.join(f'{k}={v}' for k,v in expected.items())+'\n'
    m=dict(schema='native-source-gate-v1',status='prepared_not_executed',host='UNBOUND_NO_DISPATCH',
        source_root=str(source),output_parent=str(destination/'UNBOUND_OUTPUT'),
        sources={str(p.relative_to(source)):sha(p) for p in sorted(source.rglob('*')) if p.is_file()},
        build=dict(top=b['top'],sv_sources=['rtl/'+n for n in b['files']],cpp_source=bench,
                   parameters={'AW':5,'CONTEXTS':1},cflags=['-std=c++17','-O2','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='square-control',argv=['{exe}'],expected_returncode=0,expected_stdout=footer,expected_stderr='')])
    (destination/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    result=dict(status='prepared_not_executed',sources=len(m['sources']),rtl_sources=len(b['files']),
                manifest_sha256=sha(destination/'manifest.json'),counts=expected,**lineage)
    (destination/'preparation.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    import sys
    assert len(sys.argv)==2
    print(json.dumps(prepare(sys.argv[1]),indent=2))
