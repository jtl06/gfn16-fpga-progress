"""Closed flags-off role from actual promoted-parent native source archive."""
import hashlib,json,tarfile
from pathlib import Path
from fpga.reference.track_a_trunk_flags_off_source_v1 import verify,expected,NEW
ROOT=Path(__file__).resolve().parents[1]
ANCESTOR='results/throughput-20260929/core27-t5b-aw5-normal-aethia-v1'
MANIFEST_SHA='7a082142f666db4600442522bc67565b0f64edd04f1765a663ed422fa247ce39'
ARCHIVE_SHA='ad4541d1ea3385a9aaff6dac384019cd523d7d9e2fd0f2bf11bf66fe39dc38a7'
def sha(data):return hashlib.sha256(data).hexdigest()

def prepare(output):
    output=Path(output).resolve()
    if output.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('fresh output/no PAUSE')
    verify();base=ROOT/ANCESTOR;raw=(base/'approved-manifest.json').read_bytes()
    if sha(raw)!=MANIFEST_SHA or sha((base/'sources.tar.gz').read_bytes())!=ARCHIVE_SHA:raise ValueError('frozen native parent identity')
    manifest=json.loads(raw);files={}
    with tarfile.open(base/'sources.tar.gz') as tf:
        members=tf.getmembers()
        if len({m.name for m in members})!=len(members):raise ValueError('duplicate ancestor member')
        for m in members:
            if not m.isfile() or m.name not in manifest['sources'] or Path(m.name).is_absolute() or '..' in Path(m.name).parts:raise ValueError('unexpected ancestor member')
            data=tf.extractfile(m).read()
            if sha(data)!=manifest['sources'][m.name]:raise ValueError('ancestor source drift')
            files[m.name]=data
    if set(files)!=set(manifest['sources']):raise ValueError('incomplete ancestor archive')
    extra=[*expected(),'rtl/kernel/genefer_track_a_trunk_v1.sv',
      'reference/track_a_trunk_contract_v1.py','reference/track_a_trunk_flags_off_source_v1.py',
      'reference/track_a_trunk_flags_off_prepare_v1.py','tests/test_track_a_trunk_contract_v1.py',
      'tests/test_track_a_trunk_flags_off_source_v1.py','docs/INTEGRATION-CONFLICTS.md']
    for name in extra:files[name]=(ROOT/name).read_bytes()
    source=output/'source/fpga';source.mkdir(parents=True)
    for name,data in files.items():
        dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    manifest['sources']={name:sha(data) for name,data in files.items()}
    manifest['source_root']='/home/jtl/gfn-fpga-lab/agent-work/track-a-trunk-flags-off-aw5/source/fpga'
    manifest['output_parent']='/home/jtl/gfn-fpga-lab/agent-work/track-a-trunk-flags-off-aw5/output'
    b=manifest['build'];b['top']=NEW
    b['sv_sources']=[p for p in b['sv_sources'] if p!='rtl/tb/core27_prefill_pipe_probe_v1.sv']+['rtl/kernel/genefer_track_a_trunk_v1.sv','rtl/tb/'+NEW+'.sv']
    b['cpp_source']='rtl/tb/track_a_trunk_flags_off_threaded_v1.cpp'
    # Probe and the complete recorded568-square stdout remain byte-identical.
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return dict(status='prepared_not_executed',manifest_sha256=sha((output/'manifest.json').read_bytes()),
                sources=len(files),parent_expected_output_unchanged=True,direct_parent_lockstep=True,promotion_allowed=False)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(json.dumps(prepare(a.output),indent=2))
