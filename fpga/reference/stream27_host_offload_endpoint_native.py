"""Private B endpoint proof over captured original C2 storage2 source53.

Copies immutable production, harness, reference and geometry. Only a state-free
observer and private harness additions are compiled. No shared re-emission,
hardware trim, clock/fit change, numerical generation or native launch here.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_host_offload_endpoint_native.py'
OUTPUT = 'reference/stream27_host_offload_endpoint_output.py'
ENDPOINT = 'rtl/tb/stream27_host_offload_endpoint_v1.h'
DONORS = {
    'aw8': ('results/throughput-20260929/trackS-c2-storage2-native-v1/aw8-normal',
            '2a0c70c0e14844f667ce1f39bc7a45e37572b0a46c5ee597649b7d469beb0940',
            'b46fa68fbdb4b7d7bee8c799919490a3329285538e95e087e4ea4a322a1137c9'),
    'full': ('results/throughput-20260929/trackS-c2-storage2-native-v1/full-normal',
             'c5381b56b03507845e397d94c5bbc840a76e3abd2135ece8b4efecca67534afb',
             '7592c3d12f6ecf0ef3e5aa9e9c80a4b4cb0f5c7796e94c179b4f0f9488a77837')}
IDS = {s: 's4-b-offload-endpoint-' + s + '-normal-q1-v1' for s in DONORS}
REFERENCES = {
    'rtl/tb/stream27_host_chain_full_reference_v1.h': '88849a77ad7c58fc99f6d56eeded2a772a78fbe2b2da03fabdf7ac71aaf12c54',
    'rtl/tb/stream27_shared_reference_ntt_v1.h': 'c7837ba92829293131efda704dfdde347708641bf9aff46dccbcb87b825ba390',
    'reference/stream27_host_offload_model_v1.py': 'f9fab4b5a3042046bc90ab2c719a3ae84c1c0504e4a14609b2ddc5b11b6358c5'}
MODEL_CLOSURE = ('reference/stream27_host_offload_model_v1.py',
                 'reference/stream27_signed_boundary_oracle.py',
                 'reference/stream27_blockcarry_param_model_v1.py',
                 'reference/stream27_canonical_image_model_v1.py',
                 'reference/stream_ntt_blockwrap2_proposal.py', 'reference/stream_ntt_model.py')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def need(ok, label):
    if not ok:
        raise ValueError('B_ENDPOINT_PREP_' + label)


def replace_once(text, before, after):
    need(text.count(before) == 1, 'UNIQUE_PRIVATE_HARNESS_ANCHOR:' + before[:40])
    return text.replace(before, after, 1)


def capture(stage):
    need(stage in DONORS, 'AW8_FULL_ONLY')
    directory, manifest_pin, bundle_pin = DONORS[stage]
    base = ROOT / directory
    raw = (base / 'manifest.json').read_bytes()
    need(sha(raw) == manifest_pin, 'CAPTURED_MANIFEST')
    manifest = json.loads(raw)
    files = {}
    for name, digest in manifest['sources'].items():
        need(not Path(name).is_absolute() and '..' not in Path(name).parts, 'SOURCE_PATH')
        data = (base / 'source/fpga' / name).read_bytes()
        need(sha(data) == digest, 'CAPTURED_SOURCE:' + name)
        files[name] = data
    raw = (base / 'production-bundle.json').read_bytes()
    need(sha(raw) == bundle_pin, 'CAPTURED_BUNDLE')
    bundle = json.loads(raw)
    need(len(bundle['files']) == 53 and all(files['rtl/' + name] == text.encode()
         and sha(text.encode()) == bundle['generated_sha256'][name]
         for name, text in bundle['files'].items()), 'EXACT53_PRODUCTION')
    return manifest, files, bundle


def observer(bundle, stage):
    old = bundle['top']
    text = bundle['files'][old + '.sv']
    start = text.index('module ' + old + ' #(')
    header = text[start:text.index(');', start) + 2]
    parameters = re.findall(r'\b([A-Z][A-Z0-9_]*)=\d+', header)
    need(set(parameters) == set(bundle['parameters']) | {'EPOCH_SEED0', 'EPOCH_SEED1'} and
         len(parameters) == len(set(parameters)), 'EXACT_OBSERVER_PARAMETERS')
    top = 'genefer_stream27_b_offload_endpoint_' + stage + '_v1'
    head = header.replace('module ' + old + ' #(', 'module ' + top + ' #(', 1)[:-2]
    head += ''',
 output logic dbg_setup_done,dbg_setup_context,
 output logic [1:0] dbg_config_valid,
 output logic [63:0] dbg_base,
 output logic [191:0] dbg_reciprocal,
 output logic [153:0] dbg_limit,
 output logic [15:0] dbg_generation,
 output logic off_raw_valid,off_capture_fire,off_raw_context,
 output logic [AW-$clog2(P)-1:0] off_raw_row,
 output logic [P*32-1:0] off_raw_data,off_c0,off_c1,
 output logic [55:0] off_raw_owner,off_raw_live_owner,
 output logic off_boundary_valid,off_boundary_context,
 output logic [55:0] off_boundary_owner,off_boundary_live_owner
);
'''
    head += ' ' + old + ' #(\n  ' + ',\n  '.join('.' + n + '(' + n + ')' for n in parameters) + '\n ) candidate (.*);\n'
    head += ''' assign dbg_setup_done=candidate.setup_done;
 assign dbg_setup_context=candidate.setup_done_context;
 assign dbg_config_valid=candidate.config_valid;
 assign off_raw_valid=candidate.final_valid;
 assign off_capture_fire=candidate.capture_fire;
 assign off_raw_context=candidate.final_context;
 assign off_raw_row=candidate.digit_row;
 assign off_raw_data=candidate.digit_data;
 assign off_raw_owner=candidate.final_owner;
 assign off_raw_live_owner=candidate.live_owner[candidate.final_context*56+:56];
 assign off_boundary_valid=candidate.final_boundary_valid;
 assign off_boundary_context=candidate.boundary_context;
 assign off_boundary_owner={candidate.boundary_sequence,16'(candidate.boundary_epoch-16'd1),candidate.boundary_generation};
 assign off_boundary_live_owner=candidate.live_owner[candidate.boundary_context*56+:56];
 assign off_c0=candidate.next_c0;
 assign off_c1=candidate.next_c1;
'''
    for port, name in (('dbg_base', 'profile_base'), ('dbg_reciprocal', 'profile_reciprocal'),
                       ('dbg_limit', 'profile_limit'), ('dbg_generation', 'profile_generation')):
        head += f' assign {port}={{candidate.engine.arithmetic.{name}[1],candidate.engine.arithmetic.{name}[0]}};\n'
    head += 'endmodule\n'
    need(not re.search(r'\b(always|always_ff|always_comb|initial)\b', head), 'STATE_FREE_OBSERVER')
    return top, head


def harness(text, stage):
    # Exact guarded source adaptation; all donor normal checks remain present.
    edge = ('static void edge(DUT& d){d.clk=0;d.eval();d.clk=1;d.eval();}' if stage == 'aw8' else
            'static void edge(DUT& d){d.clk=0;d.eval();d.clk=1;d.eval();d.clk=0;d.eval();}')
    text = replace_once(text, edge, 'static void edge(DUT& d);\n#include "stream27_host_offload_endpoint_v1.h"\n' +
                        edge.replace('d.clk=1;', 'offload.pre(d);d.clk=1;', 1))
    if stage == 'aw8':
        text = replace_once(text, 'static void run(DUT& d){',
                            'static void run(DUT& d){\n    offload.begin(3,{COUNTS[0],COUNTS[1]},"dense");')
        anchor = 'need(d.read_data[0]==uint32_t(expected)&&d.read_data[1]==high&&d.read_data[2]==high,"S4_HOST_CONTEXT_SIGNED96_VALUE ctx="+std::to_string(ctx)+" address="+std::to_string(address));'
        text = replace_once(text, anchor, anchor + '\n    offload.read(ctx,address,d.read_data[0],expected);')
        text = replace_once(text, '    std::cout<<"S4_HOST_CONTEXTS_PASS', '    offload.finish();\n    std::cout<<"S4_HOST_CONTEXTS_PASS')
        probe = 'if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);'
    else:
        text = replace_once(text, ' Result result;for(unsigned ctx=0;',
                            ' offload.begin(mask,{COUNT,COUNT},mask==3?"joint3":mask==1?"single1":"single2");\n Result result;for(unsigned ctx=0;')
        text = replace_once(text, ' return actual;', ' offload.read(ctx,address,actual[0],expected);\n return actual;')
        text = replace_once(text, 'clear(d);edge(d);need(!d.read_valid&&!d.done&&!d.error,"R84_FINAL_READ_DRAIN");return result;',
                            'clear(d);edge(d);need(!d.read_valid&&!d.done&&!d.error,"R84_FINAL_READ_DRAIN");offload.finish();return result;')
        probe = 'if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);'
    text = replace_once(text, probe, probe + '\n if(argc==2&&std::string(argv[1])=="--sentinel"){need(gfn16_runtime::matches(context,d),"B_ENDPOINT_THREADS");offload_sentinel(d);d.final();return 0;}\n')
    return text


def role(stage):
    manifest, files, bundle = capture(stage)
    original = copy.deepcopy(manifest)
    top, wrapper = observer(bundle, stage)
    files['rtl/' + top + '.sv'] = wrapper.encode()
    oldtop = manifest['build']['top']
    header = ('rtl/tb/s4_host_contexts_config_v1.h' if stage == 'aw8' else
              'rtl/tb/s4_p16_two_context_full_config.h')
    private_header = 'rtl/tb/stream27_b_endpoint_' + stage + '_config.h'
    text = files[header].decode()
    need(text.count(oldtop) == 2, 'HEADER_MODEL_IDENTIFIER')
    files[private_header] = text.replace(oldtop, top).encode()
    old_cpp = manifest['build']['cpp_source']
    cpp = 'rtl/tb/stream27_b_endpoint_' + stage + '.cpp'
    text = replace_once(files[old_cpp].decode(), '#include "' + Path(header).name + '"',
                        '#include "' + Path(private_header).name + '"')
    files[cpp] = harness(text, stage).encode()
    for name in (*MODEL_CLOSURE, *REFERENCES, ENDPOINT, OUTPUT, SELF):
        raw = (ROOT / name).read_bytes()
        if name in REFERENCES:
            need(sha(raw) == REFERENCES[name], 'FROZEN_REFERENCE:' + name)
        files[name] = raw
    need(all(files[name] == (ROOT / DONORS[stage][0] / 'source/fpga' / name).read_bytes()
             for name in original['sources']), 'ALL_CAPTURE_INPUT_BYTES_RETAINED')
    manifest['build'].update(top=top, cpp_source=cpp,
        sv_sources=['rtl/' + name for name in bundle['rtl_sources']] + ['rtl/' + top + '.sv'])
    manifest['sources'] = {name: sha(data) for name, data in files.items()}
    manifest['source_root'] = manifest['output_parent'] = 'UNBOUND'
    manifest['test_role'] = 'normal'
    manifest['steps'] = [dict(name='endpoint-' + mode, argv=['{exe}'] + ([] if mode == 'dense' else ['--sentinel']),
        expected_returncode=0, validator=dict(source=OUTPUT, function='validate',
        config=dict(stage=stage, mode=mode), assets={})) for mode in ('dense', 'sentinel')]
    snapshot = {name: pin for name, pin in manifest['sources'].items() if name.endswith('.sv')}
    manifest['rtl_readiness'] = dict(schema='gfn16-candidate-rtl-ready-v1',
        candidate_id=IDS[stage].removesuffix('-q1-v1'), source_snapshot=snapshot,
        candidate_source_sha256=sha(json.dumps(snapshot, sort_keys=True, separators=(',', ':')).encode()),
        rtl_ready_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'))
    manifest['host_offload_endpoint'] = dict(parent_manifest_sha256=DONORS[stage][1],
        parent_bundle_sha256=DONORS[stage][2], production_top=bundle['top'],
        production_generated_sha256=bundle['generated_sha256'],
        taps='PRE-posedge final raw row/data/full56 owner and one final boundary with live-owner equality',
        private_harness_source=cpp, production_bytes_unchanged=True, model_source_sha256=REFERENCES[MODEL_CLOSURE[0]],
        host_finalizer_worker_only=True, hardware_trimmed=False, whole_fit_allowed=False, promotion_allowed=False)
    need(manifest['build']['parameters'] == original['build']['parameters'] and
         manifest['probe'] == original['probe'], 'PARAMETER_PROBE_UNCHANGED')
    return manifest, files, bundle


def dump(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def prepare(output, stage):
    from fpga.tools import candidate_ladder, native_class_package_v2 as package
    out = Path(output).resolve()
    need(out.is_relative_to(ROOT) and not out.exists(), 'FRESH_CONTAINED_OUTPUT')
    need(not any((ROOT / path).exists() for path in ('queue/PAUSE', 'docs/briefs/PAUSE')), 'PAUSE')
    manifest, files, source = role(stage)
    snapshot = out / 'source/fpga'
    snapshot.mkdir(parents=True)
    for name, raw in files.items():
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
    manifest['source_root'] = str(snapshot)
    dump(out / 'manifest.json', manifest)
    dump(out / 'production-bundle.json', source)
    dump(out / 'host-hours.json', candidate_ladder.budget_from_hourly())
    variants = []
    for pair in ('01', '23'):
        profile = 'gcp-c4d-static' + pair + '-v1'
        worker = 's4-b-endpoint-' + stage + '-' + pair + '-v1'
        packet = out / ('packet-' + pair)
        result = package.prepare(out / 'manifest.json', snapshot, profile, worker, 'run', packet, out / 'host-hours.json')
        ticket = json.loads((packet / 'ticket.json').read_text())
        variants.append(dict(archive=str(packet / 'package.tar.gz'), sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'], manifest_sha256=sha((packet / 'manifest.json').read_bytes()),
            worker_id=worker, profile=profile, native_root=ticket['native_root'], runner='tools/native_class_package_v2.py',
            runner_sha256=sha((ROOT / 'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT / 'tools/native_package_v4.py'), stager_sha256=sha((ROOT / 'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT / name), sha256=sha((ROOT / name).read_bytes()))
                for name in ('tools/native_package_v3.py', 'tools/native_package_v2.py')], max_seconds=3700))
    logical = dict(schema='gfn16-global-ticket-v1', id=IDS[stage], owner='independent-review',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), priority='P3', kind='sim',
        needs='verilator', tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1', allowed_hosts=['gfn16-pilot-c4d', 'aethia'],
        resources=dict(cores=2, threads=1, ram_gib=8, scratch_gib=4), minimum_ram_gib=8,
        minimum_ram_rationale='Same C2 source53 full-image harness plus linear host finalizer; no small-role memory sizing inheritance.',
        est_minutes=25 if stage == 'full' else 3, promotion_bound=False, test_role='normal',
        rtl_readiness=manifest['rtl_readiness'], packages=variants)
    if stage == 'full':
        logical.update(after=[IDS['aw8']], on='PASS_expected_contracts')
    dump(out / 'global-ticket.json', logical)
    return dict(id=IDS[stage], ticket=str(out / 'global-ticket.json'), production_rtl=53,
                compiled_rtl=len(manifest['build']['sv_sources']), status='source_prepared_not_native',
                scope='Untrimmed original C2 raw endpoint / exact host finalizer proof, no B-core or PRP qualification')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stage', choices=('aw8', 'full'), required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.stage), indent=2))
