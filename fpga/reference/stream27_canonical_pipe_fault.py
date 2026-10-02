"""Real small canonical-pipe fault role for the existing candidate ladder."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SV='rtl/kernel/genefer_stream27_canonical_image_pipe_v1.sv'
RAM='rtl/kernel/genefer_sdp_ram32.sv'
CPP='rtl/tb/stream27_canonical_pipe_fault.cpp'
SELF='reference/stream27_canonical_pipe_fault.py'
TEST='tests/test_stream27_canonical_pipe_fault.py'


def sha(raw):return hashlib.sha256(raw).hexdigest()


def role():
    files={name:(ROOT/name).read_bytes() for name in (SV,RAM,CPP,SELF,TEST)}
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',
        source_root='/not-a-dispatch-path/canon-pipe-fault/fpga',
        output_parent='/not-a-dispatch-path/canon-pipe-fault/output',
        sources={name:sha(raw) for name,raw in files.items()},
        build=dict(top='genefer_stream27_canonical_image_pipe_v1',sv_sources=[RAM,SV],
            cpp_source=CPP,parameters=dict(AW=5,P=8),cflags=['-std=c++17','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='canonical-pipe-range-reset',argv=['{exe}'],expected_returncode=0,
            expected_stdout='CANON_PIPE_FAULT_PASS aw=5 p=8 range_faults=2 reset_aborts=11 pending_read_resets=1 recovery_images=15 signed96_reads=480\n',expected_stderr=''),
            dict(name='canonical-pipe-wrong-word',argv=['{exe}','--wrong-word'],expected_returncode=1,
                expected_stdout='',expected_stderr='CANON_PIPE_WRONG_WORD_REJECT\n')],
        scope='Small standalone registered canonical boundary range/reset/E1 revocation and full reload only; not whole-host/fullN/clock/promotion.')
    return manifest,files


def prepare(output):
    if any((ROOT/name).exists() for name in ('docs/briefs/PAUSE','queue/PAUSE')):raise ValueError('PAUSE')
    out=Path(output).resolve()
    if out.exists():raise ValueError('fresh output required')
    manifest,files=role();source=out/'input/source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    path=out/'input/manifest.json';path.write_text(json.dumps(manifest,indent=2)+'\n')
    ready=json.loads((ROOT/'results/throughput-20260929/s4-canonical-pipe-aw5-p8-normal-v1/global-ticket-v1.json').read_text())['rtl_readiness']
    if ready['source_snapshot']!={SV:sha(files[SV])}:raise ValueError('shared source-freeze mismatch')
    descriptor=dict(schema='gfn16-candidate-ladder-v1',candidate_id='s4-canonical-value-register-v1',
        owner='stream-core',track='S',flags=dict(CANONICAL_PIPE_STAGES=1),rtl_readiness=ready,
        roles=[dict(id='s4-canon-pipe-aw5-p8-fault-q1-v1',stage='typed_mutant',test_role='deliberate_fault',
            manifest=dict(path=str(path),sha256=sha(path.read_bytes())),source_root=str(source),
            after=['s4-canon-pipe-aw5-p8-normal-q1-v2'],minimum_ram_gib=4,
            minimum_ram_rationale='Five-source standalone N32 component; bounded4GiB exploratory cap, no measured peak claim.',est_minutes=5)])
    (out/'candidate.json').write_text(json.dumps(descriptor,indent=2)+'\n')
    return dict(status='source_ready_not_submitted',descriptor=str(out/'candidate.json'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.output)))
