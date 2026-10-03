"""Fresh source-exact Qsys input: only registered-credit aperture guard repair.

The system name, recipe, application, component interfaces and all other input
bytes remain literal v2. Running this prepares files, never executes vendor tools.
"""
import hashlib
import json
from pathlib import Path
from .stream27_r15_dma_aperture_v2 import source

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/throughput-20260929/trackS-r15-real-pcie-shell-v2'
PARENT=BASE/'system-source-v2'
PARENT_PIN='adeeb37d0dd13a7c023586b01c1ab9ea4bbaeb7a21ae059821ad70ca44e19979'
GUARD='rtl/genefer_stream27_r15_dma_aperture_v1.sv'
NEW_PIN='c3b4c04d5f775739d2d7c820eca3ff1fff620157d68fa7e307b08e472da0d59e'
RECIPE='reference/stream27_r15_dma_aperture_v2.py'
RECIPE_PIN='a4a65e49eb10ae030fb6d6d89cf2414e18dfe214437534ae4cb8c0dd465f8866'
SELF='reference/stream27_r15_qsys_source_v3.py'

def sha(raw):return hashlib.sha256(raw).hexdigest()

def inputs():
    raw=(PARENT/'input-manifest.json').read_bytes()
    if sha(raw)!=PARENT_PIN:raise ValueError('R15_QSYS_V3_PARENT_MANIFEST')
    manifest=json.loads(raw)
    files={p:(PARENT/p).read_bytes() for p in manifest['files']}
    if len(files)!=74 or any(sha(raw)!=manifest['files'][p] for p,raw in files.items()):
        raise ValueError('R15_QSYS_V3_PARENT_FILES')
    if sha((ROOT/RECIPE).read_bytes())!=RECIPE_PIN:raise ValueError('R15_QSYS_V3_GUARD_RECIPE')
    guard=source()
    if sha(guard)!=NEW_PIN:raise ValueError('R15_QSYS_V3_GUARD_BYTES')
    files[GUARD]=guard
    changed=[p for p,raw in files.items() if sha(raw)!=manifest['files'][p]]
    if changed!=[GUARD]:raise ValueError('R15_QSYS_V3_EXACT_SINGLE_DELTA')
    manifest['schema']='r15-real-system-generation-input-v3'
    manifest['files']={p:sha(raw) for p,raw in files.items()}
    manifest['additional_native_guard_sources']={'rtl/kernel/genefer_stream27_r15_dma_aperture_v1.sv':NEW_PIN}
    manifest['parent_input']={'path':str(PARENT/'input-manifest.json'),'sha256':PARENT_PIN}
    manifest['source_delta']={'changed_files':changed,'minimum_downstream_response_edges':1,
      'scope':'Registered response credit removes downstream WAITREQUEST from the combinational fault cone. Zero-latency response is rejected.'}
    manifest['generator_sources'].update({SELF:sha((ROOT/SELF).read_bytes()),RECIPE:RECIPE_PIN})
    return manifest,files

def prepare(output):
    out=Path(output).resolve()
    if not out.is_relative_to(BASE) or out.exists():raise ValueError('R15_QSYS_V3_FRESH_PRIVATE_OUTPUT')
    if any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')):raise ValueError('R15_QSYS_PAUSE')
    manifest,files=inputs()
    out.mkdir(parents=True)
    for name,raw in files.items():
        path=out/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as f:f.write(raw)
    with (out/'input-manifest.json').open('x') as f:json.dump(manifest,f,indent=2);f.write('\n')
    with (out/'.gitignore').open('x') as f:f.write('*\n!.gitignore\n')
    return {'path':str(out),'sha256':sha((out/'input-manifest.json').read_bytes()),'files':len(files),'changed_files':manifest['source_delta']['changed_files']}
