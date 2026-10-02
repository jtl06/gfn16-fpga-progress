"""Closed source-only A-next eight-small-PRP native ticket input."""
import hashlib,json
from pathlib import Path
from fpga.reference.anext_small_prp_v1 import corpus,MISMATCH
ROOT=Path(__file__).resolve().parents[1]
BASE='artifacts/anext-whole-aw5-role-v2'
BASE_SHA='0e51a47a61a9860a9a3937deedb47d54c554b158d721b6906db4d4ba47637505'
def sha(data):return hashlib.sha256(data).hexdigest()
def prepare(output):
    output=Path(output).resolve()
    if output.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('fresh output/no PAUSE')
    raw=(ROOT/BASE/'manifest.json').read_bytes()
    if sha(raw)!=BASE_SHA:raise ValueError('frozen direct AW5 lineage')
    m=json.loads(raw);files={}
    for name,pin in m['sources'].items():
        data=(ROOT/BASE/'source/fpga'/name).read_bytes()
        if sha(data)!=pin:raise ValueError('source drift')
        files[name]=data
    for name in ('rtl/tb/anext_small_prp_v1.cpp','reference/anext_small_prp_v1.py','reference/anext_small_prp_prepare_v1.py','reference/core27_small_gfn_prp_v1.py','tests/test_anext_small_prp_v1.py'):
        files[name]=(ROOT/name).read_bytes()
    text,oracle=corpus();files['anext-prp-aw5.txt']=text.encode();files['anext-prp-oracle.json']=(json.dumps(oracle,indent=2)+'\n').encode()
    source=output/'source/fpga';source.mkdir(parents=True)
    for name,data in files.items():
        dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    m['sources']={name:sha(data) for name,data in files.items()};m['build']['cpp_source']='rtl/tb/anext_small_prp_v1.cpp'
    m['steps']=[]
    for mode in ('normal','negative-comparator','negative-schedule'):
        m['steps'].append(dict(name='prp-'+mode,argv=['{exe}','{root}/anext-prp-aw5.txt']+([] if mode=='normal' else ['--'+mode]),expected_returncode=0 if mode=='normal' else 1,expected_stderr='' if mode=='normal' else MISMATCH,
                              validator=dict(source='reference/anext_small_prp_v1.py',function='validate',config=dict(mode=mode),assets=dict(corpus='anext-prp-aw5.txt',oracle='anext-prp-oracle.json'))))
    m['source_root']='/home/jtl/gfn-fpga-lab/agent-work/anext-small-prp/source/fpga';m['output_parent']='/home/jtl/gfn-fpga-lab/agent-work/anext-small-prp/output'
    (output/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    return dict(status='prepared_not_executed',manifest_sha256=sha((output/'manifest.json').read_bytes()),sources=len(files),operations=oracle['operations'],doubles=oracle['doubles'],corpus_sha256=oracle['corpus_sha256'],explicit_base_domain_successor=True,promotion_allowed=False)
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(prepare(a.output),indent=2))
