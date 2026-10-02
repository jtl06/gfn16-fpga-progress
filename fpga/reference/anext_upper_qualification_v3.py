"""Mechanical upper-composition PRP/retained-state qualification successors.

Copies immutable numerical assets; no full-size oracle generation. Only the
compiled candidate, C++ top, and measured +1 point-cycle contract change.
"""
import hashlib,json,shutil
from pathlib import Path
from fpga.reference import anext_upper_source_v1 as upper
ROOT=upper.ROOT
PINS={
 'rtl/tb/anext_small_prp_v1.cpp':'bff93876595c35230516121a99c87cf81fd6eebdd76b7190ef78cf7c45cc4f0b',
 'reference/anext_small_prp_v1.py':'0bb44dca3493710ff5e0b9d7c1031ac825cc0e97e35e0335bf7127449125e7b4',
 'rtl/tb/anext_soak_v1.cpp':'017e59212902a04fe532464658d77f1e80ee344a6603dfc87399537ff8d7fb6a',
 'reference/anext_soak_output_v1.py':'b6aa9257623edcf20bc9f0733555c64252fbb9211c3ca38c0f81782ba11aeac2'}
ROLES={
 'prp':('anext-small-prp-aw5-role-v1','f0616eadb7804366991aa4e7fc53125dfa36e2556cf7c9e2ef3a154673f59989'),
 'short':('anext-soak-short-aw16-role-v1','2d8a6832db2c37f61f0c0a0036f6bee1de18b3ca468b7598160b5469e6fcb69f'),
 'pilot':('anext-soak-chunk00-aw16-role-v1','cb036a46262afd2efea6c88983e47ee894cf3aad9355d08da5779eed9095dbae'),
 'continuous':('anext-soak-continuous-aw16-role-v1','93600acbdbec2cef42f4531a0eaf55ac18040afeaa058e47578e42f25a37869b')}
UPPER_ROLES={5:('anext-upper-whole-aw5-role-v1','74cc883d85fef7d696a8ae62e26378b7719e5079b28d0b791cda605435b14351'),16:('anext-upper-representative-aw16-role-v1','734b33e574f38d227bfbadff0c0beaeecc9891c078672ff69024ba76d32aeae4')}
CORE='47a84a9f20490709756af28623b3a7233832a2080a435f2fe71b2487b0dbe8bc'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok,why):
    if not ok:raise ValueError(why)
def once(t,a,b):
    need(t.count(a)==1,'unique qualification delta '+a);return t.replace(a,b)
def expected():
    out={}
    for name,pin in PINS.items():
        need(sha(ROOT/name)==pin,'frozen qualification parent '+name)
        t=(ROOT/name).read_text()
        if name.endswith('.cpp'):
            need(t.count('genefer_anext_core_v1')==2,'exact C++ top references')
            t=t.replace('genefer_anext_core_v1','genefer_anext_upper_core_v1')
            if 'small_prp' in name:
                t=once(t,'k==0?206u:183u','k==0?207u:184u')
                t=once(t,'d.ntt_cycles==114','d.ntt_cycles==115')
            else:t=once(t,'uint64_t(n)/64)+13;','uint64_t(n)/64)+14;')
        elif 'small_prp' in name:
            t=once(t,"wanted=206+(c['operations']-1)*183","wanted=207+(c['operations']-1)*184")
            t=once(t,"candidate='A-next-v1'","candidate='A-next-upper-v1'")
        else:
            t=once(t,'from fpga.reference.anext_composition_contract_v1 import schedule','from fpga.reference.anext_point_contract_v1 import schedule')
            t=once(t,"CORE_SHA='0ff3de9b3ce6ab4dba3d7a5df20e115bbed8c763c2aa4d7e5fd780f006edba56'",f"CORE_SHA='{CORE}'")
            t=once(t,"ROOT/'rtl/kernel/genefer_anext_core_v1.sv'","ROOT/'rtl/kernel/genefer_anext_upper_core_v1.sv'")
            t=once(t,"candidate='A-next-v1'","candidate='A-next-upper-v1'")
        child=name.replace('anext_small_prp','anext_upper_small_prp').replace('anext_soak','anext_upper_soak')
        out[child]=t
    return out
def verify():
    upper.verify()
    for name,t in expected().items():need((ROOT/name).read_text()==t,'exact upper harness delta '+name)
    return {'source_only':True,'per_square_delta_from_original':1,'reset_reload_loop_unchanged':True}
def closed(role,pin):
    root=ROOT/'artifacts'/role;need(sha(root/'manifest.json')==pin,'immutable role manifest')
    m=json.loads((root/'manifest.json').read_text());files={}
    for name,h in m['sources'].items():
        p=root/'source/fpga'/name;need(sha(p)==h,'closed role '+name);files[name]=p.read_bytes()
    return m,files
def prepare(kind,output):
    verify();need(kind in ROLES,'finite qualification role');output=Path(output).resolve()
    need(not output.exists() and not (ROOT/'docs/briefs/PAUSE').exists(),'fresh output/no PAUSE')
    m,files=closed(*ROLES[kind]);u,uf=closed(*UPPER_ROLES[5 if kind=='prp' else 16])
    for name,data in uf.items():
        need(name not in files or files[name]==data,'no overwritten ancestor '+name);files[name]=data
    for name in [*expected(),*PINS,'reference/anext_upper_qualification_v1.py','reference/anext_upper_qualification_v2.py','reference/anext_upper_qualification_v3.py','reference/core27_small_gfn_prp_v1.py','tests/test_anext_upper_qualification_v1.py','tests/test_anext_soak_v1.py','reference/anext_soak_source_v1.py','reference/core27_t5b_soak_v1.py','reference/core27_crtmont_soak_v1.py','rtl/tb/core27_t5b_soak_v1.cpp']:
        files[name]=(ROOT/name).read_bytes()
    m['build']['top']=u['build']['top'];m['build']['sv_sources']=u['build']['sv_sources']
    m['build']['cpp_source']=m['build']['cpp_source'].replace('anext_small_prp','anext_upper_small_prp').replace('anext_soak','anext_upper_soak')
    for step in m['steps']:
        step['validator']['source']=step['validator']['source'].replace('anext_small_prp','anext_upper_small_prp').replace('anext_soak','anext_upper_soak')
    need(len(m['build']['sv_sources'])==30 and all(not n.startswith('donor/') for n in m['build']['sv_sources']),'candidate-only thirty RTL')
    source=output/'source/fpga';source.mkdir(parents=True)
    for name,data in files.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    m['sources']={name:hashlib.sha256(data).hexdigest() for name,data in files.items()}
    (output/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    return dict(kind=kind,manifest_sha256=sha(output/'manifest.json'),source_count=len(files),compiled_sv=30,core_sha256=CORE,numeric_assets_unchanged=True,native_executed=False)
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--kind',choices=ROLES,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(prepare(a.kind,a.output),indent=2))
