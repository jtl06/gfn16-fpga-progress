"""F3-only PRP/retained-state qualification over unchanged numeric donors.

Point PRP/soak harnesses are byte-pinned and adapted only for the actual F3
model and its +2*AW+1 NTT/calendar delta. No point/upper native result is
inherited. No full-N integer, HDL, vendor or cloud execution occurs here.
"""
import argparse
import hashlib
import json
from pathlib import Path
from fpga.reference import anext_writeback_source_v1 as source

ROOT=Path(__file__).resolve().parents[1]
CORE='04fe3faa490c83395cec936c40cad15644885ddfd83f008b9f8d7e27da9f8fc9'
BACKEND='47cfcc569d8eb152cfeeb74b8346fa78d379aa01f6233bc9510b6f3d897fe9ad'
BLOCK='76f195246961fc97db61bdcc9e1958bb4f04e238e59726b6c31add12d87cde45'
PARENTS={
 'rtl/tb/anext_point_small_prp_v1.cpp':'0488e65c703d7ef2c6945a25f8b2f8d59b48f085bc0ec9e46ee1892a80a97f29',
 'rtl/tb/anext_point_soak_v1.cpp':'7a0a44e2866dc99e351232e6da2294338a06a73cafbd8bb9f09e345edb4cd9fa',
 'reference/anext_point_small_prp_v1.py':'19bffe084f56711aef5a868b1254c64b0f136d5c7a66a39a13ad6de90ea907ef',
 'reference/anext_point_soak_output_v1.py':'b32f95b85b748a15678c8e65325f3c01934e4c34262ef8f07e9aa117810173f8',
}
ROLES={
 'prp':('anext-point-qualification-prp-role-v1','44837dd41d92263670dfab86fae8df3d73999b437f346af27717296fdc76db35'),
 'short':('anext-point-qualification-short-role-v1','6604fa677a8801cc2f2fe6ad1d1052bfbe28cd9e7092652eb42a3f5c0c8b6acc'),
 'pilot':('anext-point-qualification-pilot-role-v1','cc7bfb23c5d0553a535706019b0c34b11a5de5be5134e4a947e32f26caf62421'),
 'continuous':('anext-point-qualification-continuous-role-v1','fe6a0dda35ed7311643f2c9dc9a34f40a9b9017129ca7d0ab2228a7101a23fc0'),
}
MODELS={
 5:('anext-writeback-aw5-role-v1','427d71082ef57518da15820e3e8f4020ec285fe5d10e10165c1e46e9a0e480d5'),
 16:('anext-writeback-aw16-role-v1','e1ad866813824a8516b5faa8951a89a7021eefa496a16785589381787fbaa129'),
}


def need(ok,why):
    if not ok:raise ValueError(why)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def once(text,old,new):
    need(text.count(old)==1,'exact F3 qualification anchor '+old)
    return text.replace(old,new,1)


def expected():
    result={}
    for name,pin in PARENTS.items():
        need(sha(ROOT/name)==pin,'frozen point harness/parser '+name)
        text=(ROOT/name).read_text()
        if name.endswith('.cpp'):
            need(text.count('genefer_anext_point_core_v1')==2,'two exact F3 model bindings')
            text=text.replace('genefer_anext_point_core_v1','genefer_anext_writeback_core_v1')
            if 'small_prp' in name:
                text=once(text,'k==0?207u:184u','k==0?218u:195u')
                text=once(text,'d.ntt_cycles==115','d.ntt_cycles==126')
            else:
                text=once(text,'uint64_t(n)/64)+14;','uint64_t(n)/64)+14+(2*uint64_t(aw)+1);')
        else:
            text=once(text,"candidate='A-next-point-v1'","candidate='A-next-writeback-v1'")
            if 'small_prp' in name:
                text=once(text,"wanted=207+(c['operations']-1)*184","wanted=218+(c['operations']-1)*195")
            else:
                text=once(text,'from fpga.reference.anext_point_contract_v1 import schedule',
                          'from fpga.reference.anext_writeback_contract_v2 import schedule')
                text=once(text,"CORE_SHA='f37123255ed08225f9c26a5d556fafb94c4e3eda9547b28713be956cda4cbe7b'","CORE_SHA='"+CORE+"'")
                text=once(text,'genefer_anext_point_core_v1.sv','genefer_anext_writeback_core_v1.sv')
        result[name.replace('anext_point_','anext_writeback_')]=text
    return result


def verify():
    source.verify()
    for name,pin in [('genefer_anext_writeback_core_v1.sv',CORE),
                     ('genefer_anext_writeback_square_backend_v1.sv',BACKEND),
                     ('genefer_anext_writeback_block_engine_v1.sv',BLOCK)]:
        need(sha(ROOT/'rtl/kernel'/name)==pin,'unchanged actual F3 '+name)
    for name,text in expected().items():
        need((ROOT/name).read_text()==text,'exact additive F3 qualification '+name)
    return dict(source_only=True,RTL_changed=False,numeric_donor_changed=False,inherited_native_result=False)


def prepare(kind,output):
    from fpga.reference.anext_point_qualification_v1 import closed
    need(kind in ROLES,'finite F3 qualification recipe');verify()
    output=Path(output).resolve()
    need(not output.exists() and not (ROOT/'docs/briefs/PAUSE').exists(),'fresh F3 output/no PAUSE')
    m,files=closed(*ROLES[kind]);model,model_files=closed(*MODELS[5 if kind=='prp' else 16])
    for name,data in model_files.items():
        need(name not in files or files[name]==data,'no ancestor source overwrite '+name)
        files[name]=data
    extras=[*PARENTS,*expected(),'reference/anext_writeback_qualification_v1.py',
        'tests/test_anext_writeback_qualification_v1.py','reference/anext_writeback_source_v1.py',
        'reference/anext_writeback_contract_v1.py','reference/anext_writeback_contract_v2.py']
    for name in extras:
        data=(ROOT/name).read_bytes()
        need(name not in files or files[name]==data,'immutable F3 source dependency '+name)
        files[name]=data
    m['build'].update(top=model['build']['top'],sv_sources=model['build']['sv_sources'],
        cpp_source=m['build']['cpp_source'].replace('anext_point_','anext_writeback_'))
    for step in m['steps']:
        step['validator']['source']=step['validator']['source'].replace('anext_point_','anext_writeback_')
    need(len(m['build']['sv_sources'])==30 and
         all(not name.startswith('donor/') for name in m['build']['sv_sources']),'only30 actual F3 compiled RTL')
    for name in m['build']['sv_sources']:
        live=ROOT/name
        if live.is_file():
            need(files[name]==live.read_bytes(),'exact existing compiled F3 source '+name)
        else:
            # The already-qualified native ROM width wrapper is generated
            # inside its immutable closed role, not authored in live RTL.
            aw=model['build']['parameters']['AW']
            need(name==f'rtl/kernel/a10_packed_lookup_aw{aw}_lint_bound_v2.sv' and
                 hashlib.sha256(files[name]).hexdigest()==model['sources'][name],
                 'only exact inherited closed F3 lookup wrapper may lack live file')
    destination=output/'source/fpga';destination.mkdir(parents=True)
    for name,data in files.items():
        target=destination/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    m['sources']={name:hashlib.sha256(data).hexdigest() for name,data in files.items()}
    (output/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    result=dict(kind=kind,status='prepared_not_native',manifest_sha256=sha(output/'manifest.json'),
        sources=len(files),compiled_sv=30,core_sha256=CORE,backend_sha256=BACKEND,
        numeric_assets_byte_preserved=True,inherited_native_result=False,promotion_allowed=False)
    (output/'preparation.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind',choices=ROLES,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.kind,args.output),indent=2))
