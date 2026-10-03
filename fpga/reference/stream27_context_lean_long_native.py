"""Own lean-R7 serial100, exact healthy protected-twin driver/reference inputs.

lean build; host GL assumed (unimplemented). No inherited source PASS, timing,
runtime forecast, error protection, host GL or rollback implementation.
"""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_context_lean_long_native.py'
LABEL = 'lean build; host GL assumed (unimplemented)'
BASE = ROOT/'results/throughput-20260929/trackS-c2-lean-r7-native-v2/full-normal'
BASE_PIN = '42906d1b94180fcbed77c2459f15e846d8ab24366f7d5a225ad18df20d07f7c0'
TWIN = ROOT/'results/throughput-20260929/trackS-c2-storage-combo-faultlocal-ownlong-v1/own100-serial-v1'
TWIN_PIN = '85a2ab5f489c755c779f0ca9ca773347c7aeb65c3b7574fab6c132cb5391fbb4'
CPP = 'rtl/tb/stream27_p16_two_context_threadpilot.cpp'
HEADER = 'rtl/tb/s4_p16_two_context_full_config.h'
VALIDATOR = 'reference/stream27_context_storage_combo_faultlocal_long_native.py'
VALIDATOR_PIN = '3199615c75830616fda22a086657fa5398ca8a90776f51109de658bc16ba4162'
ID = 's4-p16-c2-lean-r7-own100-serial-q1-v1'
READY = '2026-10-02T17:41:00Z'


def need(ok, why):
    if not ok:
        raise ValueError('C2_LEAN_LONG_'+why)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def dump(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def validate(stdout, stderr, rc, config, assets):
    need(set(config) == {'parent_config', 'parent_source_sha256'} and assets == {}, 'CONFIG')
    need(config['parent_source_sha256'] == VALIDATOR_PIN and
         stdout.startswith(LABEL+'\n') and stdout.count(LABEL) == 1, 'LABEL_AND_CAPTURED_VALIDATOR')
    raw = (ROOT/VALIDATOR).read_bytes()
    need(sha(raw) == VALIDATOR_PIN, 'EXACT_TWIN_METADATA_FUNCTIONS')
    tree = ast.parse(raw.decode())
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name in ('need', 'bits', 'config', 'validate')]
    need(len(functions) == 4, 'ONLY_PURE_CONFIG_OUTPUT_FUNCTIONS')
    namespace = {'json': json, 'math': math, 'BASES': [604832956, 999999937]}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(ROOT/VALIDATOR), 'exec'), namespace)
    result = namespace['validate'](stdout.removeprefix(LABEL+'\n'), stderr, rc,
                                   config['parent_config'], {})
    result.update(build_label=LABEL, host_gl_implemented=False, rollback_implemented=False,
        twin_fault_immunity_inherited=False, promotion_allowed=False,
        scope='Own lean serial pilot against unchanged independent native reference and context-alone/joint words; '+
              LABEL+'; no protected clock, speed ratio or measured full-sample PRP claim.')
    return result


def role():
    need(sha((BASE/'manifest.json').read_bytes()) == BASE_PIN and
         sha((TWIN/'manifest.json').read_bytes()) == TWIN_PIN, 'IMMUTABLE_ROLE_CAPTURES')
    m, twin = read(BASE/'manifest.json'), read(TWIN/'manifest.json')
    files = {name: (BASE/'source/fpga'/name).read_bytes() for name in m['sources']}
    need(all(sha(raw) == m['sources'][name] for name, raw in files.items()), 'LEAN_CAPTURE_CLOSURE')
    rtl_before = {name: pin for name, pin in m['sources'].items() if name.endswith('.sv')}
    for name in (CPP, HEADER, VALIDATOR):
        raw = (TWIN/'source/fpga'/name).read_bytes()
        need(sha(raw) == twin['sources'][name], 'TWIN_DRIVER_INPUT:'+name)
        files[name] = raw
    need(sha(files[VALIDATOR]) == VALIDATOR_PIN and
         sha(files[CPP]) == '0121cc93bb708e8ad2b40a3ca939aa9b2dee15393a5d7e23f49b9823ac8e8ade',
         'EXACT_NATIVE_REFERENCE_DRIVER')
    cpp = files[CPP].decode()
    marker = 'return gfn16_runtime::probe(context,d);'
    need(cpp.count(marker) == 1, 'PROBE_RETURNS_BEFORE_LABEL_OR_MODEL')
    files[CPP] = cpp.replace(marker, marker+'std::cout<<"'+LABEL+'\\n";', 1).encode()
    parent_config = twin['steps'][0]['validator']['config']
    need(parent_config['count'] == 100 and parent_config['threads'] == 1 and
         parent_config['interval'] == 8459, 'OWN_SERIAL100_CALENDAR')
    m['build']['cpp_source'] = CPP
    m['build']['runtime_threads'] = 1
    m['steps'] = [dict(name='normal-full-c2-lean-r7-own100-percontext', argv=['{exe}'],
        expected_returncode=0, validator=dict(source=SELF, function='validate', assets={},
        config=dict(parent_config=parent_config, parent_source_sha256=VALIDATOR_PIN)))]
    files[SELF] = (ROOT/SELF).read_bytes()
    m['sources'] = {name: sha(raw) for name, raw in files.items()}
    need(rtl_before == {name: pin for name, pin in m['sources'].items() if name.endswith('.sv')},
         'EXACT_OWN_NORMAL55_AND_OBSERVER')
    need(m['probe'] == twin['probe'], 'EXACT_RUNTIME_CONTEXT_BEFORE_MODEL')
    m['rtl_readiness']['candidate_id'] = 's4-p16-c2-lean-r7-own100-v1'
    need(m['rtl_readiness']['rtl_ready_at_utc'] == READY, 'ORIGINAL_CORRECTED_READINESS')
    m['lean_production']['own_serial_pilot'] = dict(label=LABEL, count_per_context=100,
        model_threads=1, protected_twin_manifest_sha256=TWIN_PIN,
        cpp_delta='one explicit nonprobe lean/host-GL-unimplemented label only',
        reference_header_and_oracle_inputs_unchanged=True,
        initial_resets=1, initial_load_words=131072, descriptors=198,
        no_reset_reload_or_checkpoint_barriers=True, own_measured_forecast_pending=True,
        no_native_or_clock_or_runtime_inheritance=True, no_full_N_numeric_locally_performed=True)
    return m, files


def prepare(output):
    from fpga.tools import candidate_ladder, native_class_package_v2 as package
    out = Path(output).resolve()
    need(out.is_relative_to(ROOT) and not out.exists(), 'FRESH_OUTPUT')
    need(not any((ROOT/p).exists() for p in ('queue/PAUSE', 'docs/briefs/PAUSE')), 'PAUSE')
    manifest, files = role()
    source = out/'source/fpga'
    source.mkdir(parents=True)
    for name, raw in files.items():
        path = source/name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    manifest['source_root'] = str(source)
    dump(out/'manifest.json', manifest)
    dump(out/'host-hours.json', candidate_ladder.budget_from_hourly())
    variants = []
    for pair in ('01', '23'):
        profile = 'gcp-c4d-static'+pair+'-v1'
        worker = 's4-p16-c2-lean-r7-own100-'+pair+'-v1'
        packet = out/('packet-'+pair)
        result = package.prepare(out/'manifest.json', source, profile, worker, 'run', packet, out/'host-hours.json')
        ticket = read(packet/'ticket.json')
        variants.append(dict(archive=str(packet/'package.tar.gz'), sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'], manifest_sha256=sha((packet/'manifest.json').read_bytes()),
            worker_id=worker, profile=profile, native_root=ticket['native_root'], runner='tools/native_class_package_v2.py',
            runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT/'tools/native_package_v4.py'), stager_sha256=sha((ROOT/'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT/name), sha256=sha((ROOT/name).read_bytes()))
                for name in ('tools/native_package_v3.py', 'tools/native_package_v2.py')], max_seconds=3700))
    logical = dict(schema='gfn16-global-ticket-v1', id=ID, owner='independent-review',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), priority='P1', kind='sim',
        needs='verilator', tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        allowed_hosts=['gfn16-pilot-c4d'], resources=dict(cores=2, threads=1, ram_gib=8, scratch_gib=4),
        minimum_ram_gib=8, minimum_ram_rationale=LABEL+'; own serial pilot, no twin peak/time inheritance.',
        est_minutes=35, promotion_bound=False, test_role='normal', rtl_readiness=manifest['rtl_readiness'],
        packages=variants, after=['s4-p16-c2-lean-r7-full-normal-q1-v2'], on='PASS_expected_contracts')
    dump(out/'global-ticket.json', logical)
    return dict(id=ID, ticket=str(out/'global-ticket.json'), label=LABEL,
                status='PREPARED_NOT_NATIVE', threads=1, count_per_context=100)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), indent=2))
