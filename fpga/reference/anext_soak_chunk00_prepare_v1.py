"""Single already-generated 100-square chunk pilot; not the 1000-chain gate."""
import hashlib,importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PARENT='reference/anext_soak_continuous_prepare_v1.py'
PIN='71a8acd069352c532a95dcc82966844cfba5e85cbb521453f5b786502b398274'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def prepare(output):
    if sha(ROOT/PARENT)!=PIN:raise ValueError('frozen continuous-role preparer')
    spec=importlib.util.spec_from_file_location('_anext_continuous_source',ROOT/PARENT)
    parent=importlib.util.module_from_spec(spec);spec.loader.exec_module(parent)
    result=parent.prepare(output);output=Path(output).resolve();source=output/'source/fpga'
    manifest=json.loads((output/'manifest.json').read_text());generation=json.loads((source/'donor/reference/generation.json').read_text())
    donor=ROOT/'queue/evidence/soak-t5b-aw16-full-reference-q3-v1/attempt-0/collected/output/reference'
    for name in ('chunk-00.txt','chunk-00.json'):
        if sha(donor/name)!=generation['files'][name]:raise ValueError('exact full donor chunk')
        target=source/'donor/reference'/name;target.write_bytes((donor/name).read_bytes())
        manifest['sources']['donor/reference/'+name]=sha(target)
    oracle=json.loads((source/'donor/reference/chunk-00.json').read_text());segment=oracle['segment']
    if (segment['mode'],segment['start'],segment['end'],segment['operations'])!=('chunk',0,100,100):raise ValueError('exact first chunk, not uninterrupted1000')
    for name in ('reference/anext_soak_chunk00_prepare_v1.py','tests/test_anext_soak_chunk00_prepare_v1.py'):
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes());manifest['sources'][name]=sha(target)
    step=manifest['steps'][0];step['name']='anext-soak-chunk00'
    step['argv']=['{exe}','{root}/donor/reference/chunk-00.txt'];step['validator']['assets']['oracle']='donor/reference/chunk-00.json'
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    result.update(manifest_sha256=sha(output/'manifest.json'),sources=len(manifest['sources']),operations=100,
        expected_prefill_cold=1,expected_cache_hits=99,uninterrupted_1000_gate=False,
        scope='One independently loaded100-square first chunk, retained99warm operations; numerical assets/driver/RTL unchanged.')
    return result
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    print(json.dumps(prepare(p.parse_args().output),indent=2))
