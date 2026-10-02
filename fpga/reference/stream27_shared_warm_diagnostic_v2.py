"""Fresh harness-only diagnostic successor; exact v1 RTL preserved."""
import json
from pathlib import Path
import shutil
from .stream27_shared_warm_native_v1 import ROOT,sha

PARENT=ROOT/'artifacts/stream27-s4-aw8-shared-warm-inputs-v1'
PIN='bfc6b53a886e8b4b6ddd94082bccad37f7891b1a6e0411aaed896a443b5e6d57'
BENCH='rtl/tb/stream27_shared_warm_aw8_v1.cpp'


def prepare(destination):
    destination=Path(destination).resolve()
    if destination.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('S4_DIAG_FRESH_PAUSE')
    if sha(PARENT/'manifest.json')!=PIN:raise ValueError('S4_DIAG_PARENT_MANIFEST')
    m=json.loads((PARENT/'manifest.json').read_text());source=destination/'inputs/fpga'
    for name,pin in m['sources'].items():
        incoming=PARENT/'inputs/fpga'/name
        if sha(incoming)!=pin:raise ValueError('S4_DIAG_PARENT_SOURCE')
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(incoming,target)
    path=source/BENCH;s=path.read_text()
    old='"S4_DATA tick="+std::to_string(tick)+" lane="+std::to_string(lane)'
    new='"S4_DATA case="+std::to_string(counts.cases)+" tick="+std::to_string(tick)+" lane="+std::to_string(lane)+" expected="+std::to_string(physical->expected[reverse4(lane)*T+row])+" actual="+std::to_string(unpack(d.data_out,lane))'
    if s.count(old)!=1:raise ValueError('S4_DIAG_EXACT_ANCHOR')
    path.write_text(s.replace(old,new))
    m.update(source_root=str(source),output_parent=str(destination/'UNBOUND_OUTPUT'),
        sources={str(path.relative_to(source)):sha(path) for path in sorted(source.rglob('*')) if path.is_file()})
    changed=[name for name,pin in json.loads((PARENT/'manifest.json').read_text())['sources'].items() if m['sources'][name]!=pin]
    if changed!=[BENCH]:raise ValueError('S4_DIAG_SINGLE_HARNESS_DELTA')
    (destination/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    r=dict(status='prepared_unbound_not_executed',parent_manifest_sha256=PIN,manifest_sha256=sha(destination/'manifest.json'),
        changed_sources=changed,unchanged_rtl_files=len(m['build']['sv_sources']),
        delta='Failure-only case index and expected/actual scalar values; no successful-output or arithmetic change.')
    (destination/'preparation.json').write_text(json.dumps(r,indent=2)+'\n');return r


if __name__=='__main__':
    import sys
    if len(sys.argv)!=2:raise ValueError('S4_DIAG_USAGE')
    print(json.dumps(prepare(sys.argv[1]),indent=2))
