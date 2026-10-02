"""Matched F2 registered boundary source/native/physical preparation only.

Both shells use one pinned common recipe and the exact frozen rootfused host
children. No HDL or vendor execution occurs here. Native host transactions
explicitly account for input+output register latency; child cycle counters
are unchanged. The physical inventory is a scoped single-component probe,
never a whole-core topology or frequency qualification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from fpga.reference import root_lookahead_field_v2 as field
from fpga.reference import root_recurrence27_lookahead_v1 as rec
from fpga.tools import registered_probe_recipe_v1 as recipe
from fpga.tools import prefit_structural_guard_v1 as structural


ROOT = field.ROOT
SELF = 'reference/f2_registered_probe_v1.py'
RECIPE_SHA = '9ca0de19a859ca3298c4a06e027f50d4345a47303db9b3d2756c374ba67d1594'
STRUCTURAL_SHA = '9494570410b0cfb083ae0d383164cf773bf7f8e8298e2b81dca7580914383979'
GENERATOR_SHA = '2d950d370a7472b6b311e9008a6027d36611a792a52beb89410138604b5cefca'
BENCH_SHA = '34319982e2f0e3135fceebe376288de91ef1ab2ae30f3c0f7812a06ca93a7657'
PARENT_PACKET = ROOT/'artifacts/root-lookahead-v1-prepared'
PARENT_MANIFEST = 'aethia-aw5-one-field.json'
PARENT_MANIFEST_SHA = '79f75584fda3e95730238f18e372496d749c9284a4b1429ecaae8a84630ffc06'
BASE_TARGET = 'ntt27_prefetch_r2_host_broadcast_orient8_rootfused_64'
MODULES = dict(parent='f2_registered_parent_probe_v1', candidate='f2_registered_candidate_probe_v1')
PAIR = 'f2_registered_pair_probe_v1'
BENCH = 'rtl/tb/f2_registered_field_probe_v1.cpp'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def source_guard():
    field.source_guard()
    field.need(sha(recipe.__file__) == RECIPE_SHA and sha(structural.__file__) == STRUCTURAL_SHA,
               'shared registered recipe/structural checker pins')
    field.need(sha(ROOT/field.SELF) == '8104fa1e6eeeee0114937e1ce988078e4a2ad8bbe2b59fef9913acb3bbd34904'
               and sha(ROOT/field.BENCH) == BENCH_SHA, 'frozen field oracle/bench')
    return rec.verify(ROOT)


def generated_sources():
    source_guard()
    sources, receipts = {}, {}
    for role, module in MODULES.items():
        child = rec.HOST if role == 'parent' else rec.NAMES[rec.HOST]
        raw = (ROOT/'rtl/kernel'/(child+'.sv')).read_bytes()
        sources['rtl/kernel/'+module+'.sv'], receipts[role] = recipe.generate(raw, module)
    ports = recipe.interface((ROOT/'rtl/kernel'/(rec.HOST+'.sv')).read_bytes())['ports']
    raw = (ROOT/'rtl/kernel'/(rec.HOST+'.sv')).read_bytes()
    header = recipe.interface(raw)['header'].replace('module '+rec.HOST+' #(', 'module '+PAIR+' #(', 1)
    header = rec.once(header, 'root_reads,wait_cycles\n', 'root_reads,wait_cycles,\n    output logic pair_mismatch\n')
    outputs = [p for p in ports if p['direction'] == 'output']
    lines = ['// Native matched registered-boundary pair; not a physical top.', header]
    for p in outputs:
        lines.append('    logic '+(p['width']+' ' if p['width'] else '')+'baseline_'+p['name']+';')
    for role, instance in [('parent', 'baseline'), ('candidate', 'candidate')]:
        lines.append('    '+MODULES[role]+' #(.AW(AW),.LANES(LANES),.HOST_LANES(HOST_LANES),.P(P),.Q(Q)) '+instance+' (')
        bindings = []
        for p in ports:
            name = p['name']
            signal = 'baseline_'+name if role == 'parent' and p['direction'] == 'output' else name
            bindings.append('        .'+name+'('+signal+')')
        lines += [',\n'.join(bindings), '    );']
    checks = ['('+p['name']+' !== baseline_'+p['name']+')' for p in outputs
              if p['name'] not in ('read_data', 'vector_read_data')]
    checks += ['(read_valid && read_data !== baseline_read_data)']
    checks += [f'(vector_read_valid && vector_read_mask[{i}] && vector_read_data[{32*i}+:32] !== baseline_vector_read_data[{32*i}+:32])'
               for i in range(16)]
    lines += ['    assign pair_mismatch=\n        '+' ||\n        '.join(checks)+';', 'endmodule', '']
    sources['rtl/tb/'+PAIR+'.sv'] = '\n'.join(lines)
    text = (ROOT/field.BENCH).read_text()
    field.need(text.count('Vroot_lookahead_engine_pair_v1') == 2, 'frozen bench model anchors')
    text = text.replace('Vroot_lookahead_engine_pair_v1', 'V'+PAIR).replace('F2_FIELD', 'F2_REGISTERED_FIELD')
    text = rec.once(text, '    auto reset = [&]() {',
                    '    // One external request edge, then two idle edges for launch and capture.\n'
                    '    auto pulse = [&]() { tick(); idle(); tick(); tick(); };\n'
                    '    auto reset = [&]() {')
    changes = [
        ('d.profile_modulus=p; d.profile_format=2; tick(); idle();', 'd.profile_modulus=p; d.profile_format=2; pulse();'),
        ('d.profile_we=1; d.profile_addr=a; d.profile_data=profile[a]; tick();', 'd.profile_we=1; d.profile_addr=a; d.profile_data=profile[a]; pulse();'),
        ('idle(); d.profile_commit=1; tick(); idle();', 'idle(); d.profile_commit=1; pulse();'),
        ('d.load_we=1; d.host_addr=a; d.write_data=values[a]; tick();', 'd.load_we=1; d.host_addr=a; d.write_data=values[a]; pulse();'),
        ('d.dif=step==1; d.inverse=0; d.scale=0; d.start=1; tick(); idle();', 'd.dif=step==1; d.inverse=0; d.scale=0; d.start=1; pulse();'),
        ('d.profile_modulus=p; d.profile_format=1; tick(); idle();', 'd.profile_modulus=p; d.profile_format=1; pulse();'),
        ('d.read_en=1; d.host_addr=a; tick();', 'd.read_en=1; d.host_addr=a; pulse();'),
        ('reset(); d.load_we=1; d.host_addr=0; d.write_data=111; tick(); idle();', 'reset(); d.load_we=1; d.host_addr=0; d.write_data=111; pulse();'),
        ('d.read_en=1; d.host_addr=0; tick();', 'd.read_en=1; d.host_addr=0; pulse();'),
        ('d.op=0; d.root_phase=1; d.dif=1; d.inverse=0; d.start=1; tick(); idle();', 'd.op=0; d.root_phase=1; d.dif=1; d.inverse=0; d.start=1; pulse();'),
    ]
    for old, new in changes:
        text = rec.once(text, old, new)
    sources[BENCH] = text
    return sources, receipts


def validate(stdout, stderr, code, config, assets):
    prefix = 'F2_REGISTERED_FIELD_PASS '
    field.need(stdout.startswith(prefix), 'registered boundary exact footer prefix')
    result = field.validate(stdout.replace(prefix, 'F2_FIELD_PASS ', 1), stderr, code, config, assets)
    field.need(result['phase_cycles'] == [44,72,8,68,44], 'registered AW5 frozen child cycles')
    result.update(status='PASS_F2_registered_AW5_field_native', request_added_edges=1,
                  response_added_edges=1, child_cycle_counter_delta=0,
                  public_drop_in_interface=False, whole_core_or_physical_claim=False)
    return result


def fresh(output):
    output = Path(output)
    field.need(not (ROOT/'docs/briefs/PAUSE').exists(), 'brief PAUSE')
    field.need(output.is_absolute() and not output.exists() and output.parent.is_dir()
               and output.parent.resolve() == output.parent, 'fresh canonical registered probe packet')
    return output


def prepare_native(output):
    output = fresh(output)
    sources, receipts = generated_sources()
    parent = PARENT_PACKET/PARENT_MANIFEST
    field.need(sha(parent) == PARENT_MANIFEST_SHA, 'frozen component packet')
    old = json.loads(parent.read_text())
    original = PARENT_PACKET/'source/fpga'
    field.need({p.relative_to(original).as_posix(): sha(p) for p in original.rglob('*') if p.is_file()}
               == old['sources'], 'frozen original closure')
    target = output/'source/fpga'
    shutil.copytree(original, target)
    for name in [field.SELF, field.BENCH, field.THREAD_HEADER, SELF,
                 'reference/merged_negacyclic27_model.py', 'tools/registered_probe_recipe_v1.py',
                 'tools/prefit_structural_guard_v1.py']:
        destination = target/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, destination)
    for name, text in sources.items():
        destination = target/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text)
    vectors, meta = field.corpus(5, 0)
    (target/'field-aw5-f0-vectors.txt').write_text(vectors)
    build = field.integration_build(5, 0, 1)
    build['top'], build['cpp_source'] = PAIR, BENCH
    build['sv_sources'] = build['sv_sources'][:-1] + list(sources)[:3]
    build['validator'] = dict(source=SELF, function='validate', config=dict(aw=5,p=104857601,runtime_threads=1),
                             assets=dict(vectors='field-aw5-f0-vectors.txt'))
    build['negative_step']['expected_stderr'] = 'F2_REGISTERED_FIELD_INTEGER_ORACLE\n'
    manifest = dict(old)
    manifest['build'] = {k: build[k] for k in ('top','sv_sources','cpp_source','parameters','cflags','runtime_threads')}
    manifest['steps'] = [dict(name='registered-field-control', argv=['{exe}','{root}/field-aw5-f0-vectors.txt'],
                              expected_returncode=0, validator=build['validator']),
                         dict(name='registered-field-negative-oracle', **build['negative_step'])]
    manifest['sources'] = {p.relative_to(target).as_posix(): sha(p) for p in target.rglob('*') if p.is_file()}
    manifest['scope'] = 'Matched common registered-I/O F2 paired AW5 engine oracle; not drop-in public interface or physical top.'
    manifest['admission'] = dict(old['admission'], prepared_by=SELF, promotion_allowed=False,
        limitation='Mandatory actual r38 class gates and exact worker admission; added boundary latency explicitly tested, no physical claim.')
    path = output/'role-manifest.json'
    path.write_text(json.dumps(manifest, indent=2)+'\n')
    result = dict(status='prepared_source_only_F2_registered_AW5_native_role',
                  role_manifest_sha256=sha(path), source_files=len(manifest['sources']),
                  wrapper_receipts=receipts, oracle=meta, source_only=True,
                  parent_bench_sha256=BENCH_SHA, generated_bench_sha256=sha(target/BENCH),
                  launcher_clones_created=0, native_RTL_executed=False, promotion_allowed=False)
    (output/'preparation.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def prepare_physical(output):
    output = fresh(output)
    source_guard()
    field.need(sha(ROOT/'synthesis/prepare.py') == GENERATOR_SHA, 'matched physical generator pin')
    from fpga.synthesis import prepare as synthesis
    output.mkdir()
    seed_project = output/'raw-parent-source'
    synthesis.prepare(seed_project, BASE_TARGET, 16, 8.0, 'pro', 1, 4)
    generated, receipts = generated_sources()
    seed = json.loads((seed_project/'manifest.json').read_text())
    results = {}
    for role, module in MODULES.items():
        project = output/role
        (project/'rtl').mkdir(parents=True)
        files = []
        for name in seed['source_sha256']:
            stem = Path(name).stem
            chosen = rec.NAMES.get(stem, stem) if role == 'candidate' else stem
            destination = project/'rtl'/(chosen+'.sv')
            shutil.copyfile(ROOT/'rtl/kernel'/(chosen+'.sv'), destination)
            files.append(chosen+'.sv')
        wrapper_file = module+'.sv'
        (project/'rtl'/wrapper_file).write_text(generated['rtl/kernel/'+wrapper_file])
        files.append(wrapper_file)
        for name in ('probe.qpf','probe.sdc','run.tcl'):
            shutil.copyfile(seed_project/name, project/name)
        qsf = (seed_project/'probe.qsf').read_text()
        qsf = rec.once(qsf, 'TOP_LEVEL_ENTITY '+rec.HOST, 'TOP_LEVEL_ENTITY '+module)
        for stem, new in rec.NAMES.items():
            if role == 'candidate':
                qsf = rec.once(qsf, 'SYSTEMVERILOG_FILE rtl/'+stem+'.sv', 'SYSTEMVERILOG_FILE rtl/'+new+'.sv')
        qsf += 'set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+wrapper_file+'\n'
        qsf += 'set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS on\n'
        # Equivalent integer literals let the existing shared structural parser
        # reproduce the actual QSF parameters without inventing an adapter.
        qsf = rec.once(qsf, "set_parameter -name P 32'd104857601", 'set_parameter -name P 104857601')
        qsf = rec.once(qsf, "set_parameter -name Q 32'd4190109697", 'set_parameter -name Q 4190109697')
        (project/'probe.qsf').write_text(qsf)
        controls = {name: sha(project/name) for name in ('probe.qpf','probe.qsf','probe.sdc','run.tcl')}
        manifest = dict(seed)
        parameters = dict(AW=16, LANES=64, HOST_LANES=16, P=104857601, Q=4190109697)
        manifest.update(top=module, target='F2-registered-'+role+'-probe-v1', seed=1,
            core_parameters=parameters, source_sha256={name: sha(project/'rtl'/name) for name in files},
            control_sha256=controls, status='prepared_source_only_not_vendor_validated',
            matched_probe_group='F2_rootfused_registered_AW16_L64_F0_seed1_8ns_v1',
            matched_probe_role=role, registered_boundary_recipe_sha256=RECIPE_SHA,
            registered_boundary_receipt=receipts[role], baseline_generator_sha256=GENERATOR_SHA,
            baseline_target=BASE_TARGET, native_small_gate_pending=True,
            r47_scope='single-component registered virtual-I/O probe; no whole-core crossing claim',
            requested_snapshot_retention=True, physical_timing_proven=False,
            note='Exact shared registered shell; request+1/response+1. Virtual pins, no deployable image or whole-core clock claim.')
        (project/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
        spec = dict(schema=structural.SCHEMA, scope='component_probe',
            identity=dict(top=module, device=manifest['device'], parameters=parameters, clock_period_ns=8.0, seed=1),
            sources={'rtl/'+name: pin for name, pin in manifest['source_sha256'].items()},
            settings={**controls, 'manifest.json': sha(project/'manifest.json')},
            blocks=['ntt_host_with_common_registered_boundary'], transfers=[],
            exclusions=[dict(kind='external_virtual_io', endpoints=[p['name'] for p in receipts[role]['ports'] if p['name'] not in ('clk','rst_n')],
                             reason='External virtual-I/O ports cross explicit common launch/capture registers; not another whole-core macroblock.'),
                        dict(kind='external_reset', endpoints=['clk','rst_n'],
                             reason='Direct common clock/asynchronous reset; inherited reset-release false path excludes board reset qualification.'),
                        dict(kind='inside_single_macroblock', endpoints=['registered_probe_boundary','child'],
                             reason='Entire NTT host engine and common probe boundary are one declared component. Internal paths remain timed by component STA; no whole-core interface/netlist completeness claim.')],
            coverage_claim='declared_source_inventory_not_netlist_completeness')
        inventory = structural.source_inventory(project, spec)
        (project/'structural-spec.json').write_text(json.dumps(spec, indent=2)+'\n')
        result = dict(status='PASS_declared_single_component_source_inventory_only',
            **structural.identities(spec), checker_sha256=STRUCTURAL_SHA,
            source_inventory=inventory, inventory_sha256=structural.digest(spec),
            native_design_assistant_pending=True, early_placed_top100_screen_pending=True,
            scope_awaits_fit_owner_confirmation=True, fit_allowed=False, promotion_allowed=False,
            physical_timing_proven=False, native_small_registered_gate_pending=True)
        (project/'structural-source-result.json').write_text(json.dumps(result, indent=2)+'\n')
        results[role] = dict(manifest_sha256=sha(project/'manifest.json'), wrapper_receipt=receipts[role],
                             structural_source_result_sha256=sha(project/'structural-source-result.json'),
                             project_root=str(project), **result)
    receipt = dict(status='prepared_matched_registered_F2_component_projects_not_executed',
                   projects=results, unchanged_settings_between_roles_except_top_and_source_names=True,
                   parameters=dict(AW=16,LANES=64,HOST_LANES=16,P=104857601,Q=4190109697),
                   period_ns=8.0, seed=1, compile_workers=4,
                   wrapper_native_gate_pending=True, actual_AW16_integration_pending=True,
                   fit_allowed=False, promotion_allowed=False)
    (output/'preparation.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=('native','physical'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps((prepare_native if args.kind == 'native' else prepare_physical)(args.output), indent=2))
