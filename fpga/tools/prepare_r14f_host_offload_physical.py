"""Fresh R14-F physical source/settings capture, not job submission."""
import argparse
import importlib.util
import json
from pathlib import Path
from fpga.reference import stream27_host_offload_field100_v1 as chip
from fpga.reference import stream27_host_offload_field100_physical_v1 as physical

def encoded(v):return (json.dumps(v,indent=2)+'\n').encode()
def prepare(output):
    out=Path(output).resolve();chip.need(out.is_relative_to(chip.ROOT) and not out.exists(),'FRESH_PHYSICAL')
    chip.need(not any((chip.ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')),'UNPAUSED')
    role=chip.ROOT/'results/throughput-20260929/trackS-r14f-host-offload-equivalence-v1/full-normal-v1'
    native=json.loads((role/'manifest.json').read_bytes());m,files,spec=physical.build()
    chip.need(native['build']['parameters']==m['core_parameters'] and
        all(native['sources'].get('rtl/'+n)==pin for n,pin in m['source_sha256'].items()),'EXACT_FULL_NORMAL_SOURCE_ROLE')
    m.update(native_normal_id='s4-r14f-b-equivalence-full-normal-q1-v1',native_role_manifest_sha256=chip.sha((role/'manifest.json').read_bytes()))
    spec['settings']['manifest.json']=chip.sha(encoded(m))
    for name,raw in files.items():
        p=out/'project'/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(raw)
    (out/'project/manifest.json').write_bytes(encoded(m))
    loader=importlib.util.spec_from_file_location('r14f_structural',chip.ROOT/'tools/prefit_structural_guard_v1.py')
    checker=importlib.util.module_from_spec(loader);loader.loader.exec_module(checker)
    result=checker.source_inventory(out/'project',spec)
    (out/'structural-inventory.json').write_bytes(encoded(spec));(out/'source-structural-result.json').write_bytes(encoded(result))
    chip.need(not result['findings'],'SOURCE_STRUCTURAL:'+repr(result['findings']))
    return dict(status='PREPARED_NOT_SUBMITTED_NORMAL_GATES_PENDING',project=str(out/'project'),sources=66,
        transfers=len(spec['transfers']),findings=result['findings'],manifest_sha256=chip.sha(encoded(m)))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(prepare(a.output),indent=2))
