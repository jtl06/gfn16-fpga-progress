"""Normal-first native ladder for the registered canonical-value boundary.

Source emission and <=256 integer corpus checks only on coordinator. The new
RTL and complete signed96 comparison execute exclusively in the native queue.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from fpga.reference import stream27_canonical_image_native_v2 as old
from fpga.reference import stream27_canonical_image_corpus_v1 as corpus
from fpga.tools import native_class_package_v2 as package
from fpga.tools import native_class_v1 as executor

ROOT = old.ROOT
SELF = 'reference/stream27_canonical_pipe_v1.py'
TEST = 'tests/test_stream27_canonical_pipe_v1.py'
TOP = 'genefer_stream27_canonical_image_pipe_v1'
CPP = 'rtl/tb/stream27_canonical_pipe_normal_v1.cpp'
SV = 'rtl/kernel/genefer_stream27_canonical_image_pipe_v1.sv'
RAM = old.RAM


def sha(raw): return hashlib.sha256(raw).hexdigest()
def canonical(value): return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
def need(ok, label):
    if not ok: raise ValueError(label)


def counts(aw, p):
    cases = corpus.corpus(aw, p)
    special = sum(old.model.independent_integer_oracle(digits,c0,c1,base)[0] == -1
                  for base,digits,c0,c1 in cases)
    n = 1 << aw
    return dict(cases=len(cases), reads=len(cases)*n, normal=len(cases)-special,
                special=special, cycles=(9*len(cases)+special)*n)


def validate(stdout, stderr, returncode, config, assets):
    need(type(config) is dict and set(config) == {'aw', 'p'} and assets == {}, 'CANON_PIPE_CONFIG')
    expected = 'CANON_PIPE_PASS aw='+str(config['aw'])+' p='+str(config['p'])+' '+' '.join(f'{k}={v}' for k, v in counts(config['aw'], config['p']).items())+'\n'
    need((stdout, stderr, returncode) == (expected, '', 0), 'CANON_PIPE_TYPED_NORMAL')
    return dict(status='PASS_expected_contracts', counts=counts(config['aw'], config['p']),
                scope='42 standalone normal images, all signed96 words and exact9N/10N latency; not whole-host/warm/clock/promotion.')


def bench():
    raw = (ROOT/old.CPP).read_bytes()
    need(sha(raw) == old.PINS[old.CPP], 'CANON_PIPE_FROZEN_CPP')
    s = raw.decode().replace(old.TOP, TOP)
    changes = [
        ('const unsigned latency = (special ? 7 : 6) * N;', 'const unsigned latency = (special ? 10 : 9) * N;'),
        ('        const Trial recovery = trials[1];\n        protocol_and_range_cases(h, recovery);\n        legal_mutation_cases(h, recovery);\n        reset_cases(h, recovery, trials[3]);\n', ''),
        ('"CANON_IMAGE_PASS aw="', '"CANON_PIPE_PASS aw="')]
    for before, after in changes:
        need(s.count(before) == 1, 'CANON_PIPE_BENCH_ANCHOR')
        s = s.replace(before, after)
    return s.encode()


def role(aw=5, p=8):
    need(type(aw) is int and aw in (5, 8) and type(p) is int and p in (8, 16), 'CANON_PIPE_SMALL_NORMAL')
    names = list(dict.fromkeys([*old.PINS, 'reference/stream27_canonical_image_native_v2.py',
        'reference/stream27_host_chain_param_v3.py', SELF, TEST, SV]))
    files = {name: (ROOT/name).read_bytes() for name in names}
    files[CPP] = bench()
    m = dict(schema='native-source-gate-v1', status='prepared_not_executed',
        source_root='/not-a-dispatch-path/canon-pipe/fpga', output_parent='/not-a-dispatch-path/canon-pipe/output',
        sources={name: sha(raw) for name, raw in files.items()},
        build=dict(top=TOP, sv_sources=[RAM, SV], cpp_source=CPP, parameters=dict(AW=aw, P=p),
            cflags=['-std=c++17', '-Werror=return-type', f'-DCANON_AW={aw}', f'-DCANON_P={p}', f'-DCANON_ORACLE_CHECKSUM={corpus.checksum(aw,p)}']),
        probe=dict(argv=['{exe}', '--runtime-probe'], expected_json=dict(context_threads=1, model_threads=1, expected_threads=1)),
        steps=[dict(name='canonical-pipe-normal', argv=['{exe}'], expected_returncode=0,
            validator=dict(source=SELF, function='validate', config=dict(aw=aw, p=p), assets={}))],
        canonical_pipe=dict(flag='CANONICAL_PIPE_STAGES=1', normal_cycles=9*(1<<aw), special_cycles=10*(1<<aw),
            added_cycles=3*(1<<aw), warm_delta=0, read_request_to_response=1, counts=counts(aw,p),
            normal_only=True, full_N_numeric_locally_performed=False))
    return m, files


def dump(path, value):
    with path.open('x') as stream: json.dump(value, stream, indent=2); stream.write('\n')


def prepare(output, aw, p, budget, revision=1):
    need(not (ROOT/'docs/briefs/PAUSE').exists() and not (ROOT/'queue/PAUSE').exists(), 'CANON_PIPE_PAUSE')
    output = Path(output).resolve(); need(not output.exists(), 'CANON_PIPE_FRESH_OUTPUT')
    need(type(revision) is int and revision in (1,2),'CANON_PIPE_REVISION')
    m, files = role(aw,p)
    ready_at = datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    source = output/'input/source/fpga'; source.mkdir(parents=True)
    for name, raw in files.items():
        path = source/name; path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream: stream.write(raw)
    manifest = output/'input/manifest.json'; dump(manifest,m)
    variants = []
    for pair in ('01','23'):
        profile = f'gcp-c4d-static{pair}-v1'; worker = f's4-canon-pipe-aw{aw}-p{p}-{pair}-v{revision}'; packet = output/('packet-'+pair)
        r = package.prepare(manifest, source, profile, worker, 'run', packet, Path(budget).resolve())
        variants.append(dict(profile=profile, worker_id=worker, packet=str(packet), archive=str(packet/'package.tar.gz'),
            sha256=r['archive_sha256'], ticket_sha256=r['ticket_sha256'], manifest_sha256=sha((packet/'manifest.json').read_bytes()),
            native_root=r['native_root'], build_key=r['build_key'], archive_bytes=r['archive_bytes'],
            resource_profile_sha256=sha(canonical(executor.profile(profile))), runner='tools/native_class_package_v2.py',
            runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()), stager=str(ROOT/'tools/native_package_v3.py'),
            stager_sha256=sha((ROOT/'tools/native_package_v3.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT/'tools/native_package_v2.py'),sha256=sha((ROOT/'tools/native_package_v2.py').read_bytes()))], max_seconds=3700))
    qid = f's4-canon-pipe-aw{aw}-p{p}-normal-q1-v{revision}'
    now = datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    snapshot = {SV:sha(files[SV])}
    ticket = dict(schema='gfn16-global-ticket-v1', id=qid, owner='stream-core', created=now,
        priority='P1', kind='sim', needs='verilator', tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4), minimum_ram_gib=4,
        minimum_ram_rationale='Bounded two-RTL N<=256 component normal;4GiB exploratory allowance, not measured peak; preserve failures.',
        est_minutes=5, promotion_bound=False, test_role='normal', packages=variants,
        rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1', candidate_id='s4-canonical-value-register-v1',
            candidate_source_sha256=sha(canonical(snapshot)), rtl_ready_at_utc=ready_at, source_snapshot=snapshot))
    if revision==2:
        prior=ROOT/f'results/throughput-20260929/s4-canonical-pipe-aw5-p{p}-normal-v1/global-ticket-v1.json'
        ticket['rtl_readiness']=json.loads(prior.read_text())['rtl_readiness']
        need(ticket['rtl_readiness']['source_snapshot']==snapshot,'CANON_PIPE_SHARED_FREEZE_SNAPSHOT')
        ticket['preserved_failed_predecessor']=f's4-canon-pipe-aw5-p{p}-normal-q1-v1'
    if aw == 8: ticket.update(after=[f's4-canon-pipe-aw5-p{p}-normal-q1-v{revision}'],on='PASS_expected_contracts')
    dump(output/'global-ticket-v1.json',ticket)
    dump(output/'preparation.json',dict(status='source_ready_not_dispatched',id=qid,variants=variants,counts=m['canonical_pipe']))
    return dict(status='source_ready_not_dispatched',id=qid)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aw',type=int,choices=(5,8),required=True);parser.add_argument('--p',type=int,choices=(8,16),required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--budget',type=Path,required=True)
    parser.add_argument('--revision',type=int,choices=(1,2),default=1)
    args=parser.parse_args();print(json.dumps(prepare(args.output,args.aw,args.p,args.budget,args.revision)))
