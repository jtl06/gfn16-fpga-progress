"""One A10 geometry's closed engine role manifests for shared queue packaging.

No host policy clone, SSH, HDL compilation or dispatch. AW8 is prepared first;
AW16 constants are source generation only and require an explicit flag. Actual
predecessor-native/profile/slot checks are the queue/owner's mandatory gate.
"""
import argparse
import hashlib
import json
from pathlib import Path
from fpga.reference import a10_banked_engine_generate_v1 as gen
from fpga.reference import a10_engine_geometry_gates_v1 as geometry
from fpga.reference import a10_native_roles_v1 as roles

ROOT=gen.ROOT/'fpga'
DONOR='results/throughput-20260929/a10-banked-aw5-stage-v1/engine-f0'
DONOR_MANIFEST_SHA='b1d7f110dff0e046d23639e58ddbc8e3c405cd74392d8e23c4db3cc173e967a8'
SELF='reference/a10_geometry_prepare_v1.py'
TEST='tests/test_a10_geometry_prepare_v1.py'
VALIDATOR='reference/a10_native_roles_v1.py'

def need(ok,message):
    if not ok:raise ValueError(message)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def closed(root,pins):
    root=Path(root).resolve()
    files={str(p.relative_to(root)):p for p in root.rglob('*') if p.is_file()}
    need(set(files)==set(pins),'A10_GEOMETRY_DONOR_CLOSURE')
    for name,path in files.items():
        need(not path.is_symlink() and path.stat().st_nlink==1 and sha(path)==pins[name],'A10_GEOMETRY_DONOR_DRIFT '+name)

def prepare(output,aw=8,*,allow_full_constants=False):
    need(not(ROOT/'docs/briefs/PAUSE').exists(),'brief PAUSE')
    need(type(aw) is int and aw in (5,8,16),'A10_NATIVE_GEOMETRY')
    need(aw<=8 or allow_full_constants,'A10_FULL_CONSTANTS_EXPLICIT_ONLY')
    output=Path(output).resolve();need(not output.exists(),'A10_GEOMETRY_FRESH_OUTPUT')
    geometry.source_guard();gen.source_guard()
    need((ROOT/geometry.BENCH).read_text()==geometry.bench_source(),'A10_GEOMETRY_BENCH_DELTA_DRIFT')
    donor=ROOT/DONOR;need(sha(donor/'manifest.json')==DONOR_MANIFEST_SHA,'A10_AW5_PACKET_IDENTITY')
    original=json.loads((donor/'manifest.json').read_text());closed(donor/'source/fpga',original['sources'])
    files={name:(donor/'source/fpga'/name).read_bytes() for name in original['sources']}
    for name in [geometry.BENCH,VALIDATOR,'reference/a10_engine_geometry_gates_v1.py',SELF,TEST,
                 'tests/test_a10_engine_geometry_gates_v1.py','tests/test_a10_native_roles_v1.py']:
        files[name]=(ROOT/name).read_bytes()
    binding=gen.lookup_binding(1<<aw,64,allow_full_constants=allow_full_constants)
    lookup_name=f'rtl/kernel/a10_packed_lookup_aw{aw}_geometry_bound_v1.sv'
    files[lookup_name]=('\n'.join(c['source'] for c in binding['compiled'])+'\n'+binding['source']).encode()
    output.mkdir(parents=True);source=output/'source/fpga';source.mkdir(parents=True)
    pins={}
    for name,data in sorted(files.items()):
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);pins[name]=sha(path)
    closed(source,pins)
    manifests=[];metrics=geometry.ledger(aw)
    for field,f in enumerate(gen.lookup.math.FIELDS):
        m=json.loads(json.dumps(original));m['sources']=pins
        # Placement is rehosted by shared native_package_v1, never dispatched as
        # this old aethia profile. Original namespace is evidence only.
        m['source_root']=f'/not-a-dispatch-path/a10-aw{aw}-f{field}/fpga'
        m['output_parent']=f'/not-a-dispatch-path/a10-aw{aw}-f{field}/output'
        m['build']['parameters'].update(AW=aw,P=f.p,Q=f.q)
        m['build']['sv_sources']=[lookup_name if x.endswith('/a10_packed_lookup_aw5_bound_v1.sv') else x for x in m['build']['sv_sources']]
        m['build']['cpp_source']=geometry.BENCH
        m['build']['cflags']=['-std=c++17','-Werror=return-type',f'-DA10_AW={aw}',f'-DA10_P={f.p}',f'-DA10_G={f.generator}']
        m['steps']=[dict(name='engine-normal',argv=['{exe}'],expected_returncode=0,
            validator=dict(source=VALIDATOR,function='validate',config=dict(role='engine',negative=None,aw=aw,field=f.p),assets={}))]
        m['scope']=f'Additive canonical A10 AW{aw} engine only, common crtmont parent; native numeric check remains unexecuted'
        m['source_only_ledger']=metrics
        m['profile']['size_log2']=aw
        path=output/f'engine-f{field}-manifest.json';path.write_text(json.dumps(m,indent=2)+'\n')
        manifests.append(dict(field=field,modulus=f.p,path=path.name,sha256=sha(path)))
    report=dict(status='prepared_engine_geometry_source_only_not_executed',aw=aw,source_files=len(pins),
        source_sha256=pins,source_bytes=sum(len(x) for x in files.values()),manifests=manifests,
        source_root=str(source),donor_manifest_sha256=DONOR_MANIFEST_SHA,
        unchanged_RTL_donor_pins={k:v for k,v in original['sources'].items() if k.startswith('rtl/kernel/')},
        generated_lookup_source_sha256=pins[lookup_name],generated_lookup_tables=[c['root_table_sha256'] for c in binding['compiled']],
        source_only_ledger=metrics,HDL_or_native_executed=False,full_N_numeric_NTT_performed=False,promotion_allowed=False,
        dispatch_gate='Shared native_package_v1 rehosts exact snapshot; first profile smoke/atomic slot/budget checks, lint observation then accepted lint before build; actual AW5 success before AW8, AW8 success before AW16.',
        next_milestone='AW8 multi-issue bank orientation + synchronous ROM/data/tag latency' if aw==8 else 'AW16 full engine numerical/cycle comparison',
        limits='Shared admitted profile owns caps/ABI/tool pins. This intermediate manifest is deliberately not directly dispatchable.')
    (output/'preparation.json').write_text(json.dumps(report,indent=2)+'\n')
    closed(donor/'source/fpga',original['sources'])
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--aw',type=int,default=8);parser.add_argument('--allow-full-constants',action='store_true')
    print(json.dumps(prepare(parser.parse_args().output,parser.parse_args().aw,allow_full_constants=parser.parse_args().allow_full_constants),indent=2))
