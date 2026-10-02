"""One source-exact original storage2 route and declared C2 crossing inventory.

No RTL emission or transformation. No synthesized-connectivity completeness,
clock closure, promotion, or inherited C1 crossing proof is asserted.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / 'results/throughput-20260929/trackS-c2-storage2-native-v1/syn-project'
NORMAL = ROOT / 'results/throughput-20260929/trackS-c2-storage2-native-v1/full-normal'
FLOW = ROOT / 'results/throughput-20260929/trackS-c2-storage2-native-v1/field-project/run.tcl'
PLACE = ROOT / 'queue/standing-fit-state/terminal/s4-p16-c2-storage2-whole-place-v1/receipt.json'
GATE_ID = 's4-p16-c2-storage2-full-normal-q1-v1'
GATE = ROOT / 'queue/evidence' / GATE_ID / 'gate-receipt.json'
TOP = 'genefer_stream27_host_contexts_aw16_p16_v1_diet_c2_m1_v1_cold_fence_v1_closed_ram_v2_explicitnets_v1_storage2_v1'
ARITH = 'genefer_stream27_threefield_carry_aw16_p16_param_v1_signed_contexts2_v1_profile_qualified_v2_diet_c2_m1_v1.sv'
WARM = 'genefer_stream27_warm_contexts_aw16_p16_v1_diet_c2_m1_v1.sv'
BLOCKS = ['host_control', 'shadow_images', 'setup_profile_banks', 'warm_control',
          'arithmetic_control', 'field0', 'field1', 'field2', 'CRT', 'carry',
          'canonical_scratch', 'copy_publication']


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def need(ok, why):
    if not ok:
        raise ValueError(why)


def once(text, old, new):
    need(text.count(old) == 1, 'unique control anchor: ' + old)
    return text.replace(old, new)


def read(path):
    return json.loads(path.read_text())


def build():
    parent, normal = read(PARENT / 'manifest.json'), read(NORMAL / 'production-bundle.json')
    need(parent['top'] == normal['top'] == TOP and len(normal['files']) == 53, 'selected original53')
    need(parent['source_sha256'] == normal['generated_sha256'], 'normal/physical exact production source')
    need(parent['geometry']['warm_interval'] == 8459, 'original calendar, not timing storage')
    files = {}
    for name, pin in parent['source_sha256'].items():
        raw = (PARENT / 'rtl' / name).read_bytes()
        need(sha(raw) == pin == sha(normal['files'][name].encode()), 'immutable source: ' + name)
        files['rtl/' + name] = raw
    for name, pin in parent['control_sha256'].items():
        raw = (PARENT / name).read_bytes()
        need(sha(raw) == pin, 'immutable control: ' + name)
        files[name] = raw
    # Source snapshot keeps its validated four-worker vocabulary. Dispatch
    # adapts the actual QSF to the recorded twelve-core whole-host allocation.
    files['probe.sdc'] = once(files['probe.sdc'].decode(), '-period 10.000', '-period 14.000').encode()
    files['run.tcl'] = FLOW.read_bytes()
    need(b'execute_module -tool fit' in files['run.tcl'] and b'execute_module -tool sta' in files['run.tcl'], 'genuine full flow')
    place = read(PLACE)
    need(place['terminal_proven'] and place['native_job_succeeded'] and
         place['native_result']['mode'] == 'place_only' and
         place['native_result']['placement_resources']['metrics']['labs_used'] == 41886,
         'actual selected source placement')
    gate = read(GATE)
    need('PASS' in str(gate['status']), 'actual normal typed gate')
    manifest = dict(parent)
    manifest.update(status='prepared_original_storage2_full_route', clock_period_ns=14.0,
        allowed_stages=['syn', 'fit', 'sta'], fit_allowed=False, promotion_allowed=False,
        control_sha256={name: sha(files[name]) for name in parent['control_sha256']},
        notes=['Exact original clean corrected C2 storage2 production53; no timing/compact/GEN/MLAB mixing.',
               'One user-authorized full route at 14ns/default Balanced/seed1; no board timing claim.',
               'Source inventory is declared crossing scope, not exhaustive synthesized connectivity.',
               'Actual AWS allocation twelve physical cores/40GiB is recorded by standing dispatch.'],
        route_basis=dict(native_source_gate=GATE_ID, gate_sha256=sha(GATE.read_bytes()),
            placement_receipt_sha256=sha(PLACE.read_bytes()), labs_used=41886,
            labs_available=42720, placement_is_not_routed=True,
            source_parent_manifest_sha256=sha((PARENT / 'manifest.json').read_bytes()),
            normal_bundle_sha256=sha((NORMAL / 'production-bundle.json').read_bytes())))
    return manifest, files


def inventory(manifest, files):
    """Real source anchors; phase exceptions never fabricate a pipeline FF."""
    top, arith, warm = 'rtl/' + TOP + '.sv', 'rtl/' + ARITH, 'rtl/' + WARM
    image = 'rtl/genefer_stream27_host_image_rowwrite_v1.sv'
    canon = 'rtl/genefer_stream27_canonical_image_pipe_v1.sv'
    crt = 'rtl/genefer_crt3_27_mont_pipe.sv'
    transfers = []

    def anchor(source, text):
        need(files[source].decode().count(text) == 1, 'unique exact structural anchor: ' + text)
        return dict(source=source, text=text)

    def stage(identifier, owner, edge, source, payload, valid, metadata, *texts):
        for text in texts:
            anchor(source, text)
        return dict(id=identifier, owner=owner, edge=edge, kind='flop', source=source,
                    payload=payload, valid=valid, metadata=metadata,
                    anchors=list(texts), alignment='same_accepted_edge')

    def crossing(identifier, producer, consumer, signals, reason, anchors, stages=None,
                 kind='phase_local_control'):
        transfers.append(dict(id=identifier, producer=producer, consumer=consumer,
            signals=signals, registered_stages=stages or [], control_reconvergence=[],
            exception=dict(kind=kind, reason=reason,
                           contract_anchors=[anchor(source, text) for source, text in anchors])))

    crossing('cold_registered_row_to_source', 'shadow_images', 'host_control',
        ['shadow_row_data', 'shadow_row_valid', 'shadow_response_owner', 'source_data', 'source_valid', 'source_context', 'source_row'],
        'Enabled RAM output and response owner are followed by the accepted cold-source FF; RAM payload holds on disabled edges.',
        [(top, 'wire response_bad=shadow_row_valid && (shadow_response_context!=row_context_d ||')],
        [stage('cold_response_metadata', 'shadow_images', 0, image, ['ram_q'], 'row_valid_d', ['row_response_context', 'row_response_owner'],
               'read_valid_d<=scalar_fire;row_valid_d<=row_fire;',
               'if(row_fire)begin row_response_context<=row_read_context;row_response_owner<=row_read_owner;end'),
         stage('cold_source_capture', 'host_control', 1, top, ['source_data'], 'source_valid', ['source_context', 'source_row'],
               'source_data[32*lane+:32]<=shadow_row_data[32*NATURAL+:32];',
               'done_q<=0;source_valid<=shadow_row_valid && row_kind_d && !response_bad && !error;',
               'if(shadow_row_valid && row_kind_d && !response_bad)begin source_context<=row_context_d;source_row<=row_address_d;end')])
    crossing('source_to_warm', 'host_control', 'warm_control', ['source_data', 'source_valid', 'source_row', 'source_context', 'job_epoch', 'job_generation'],
        'Source FF feeds the accepted-frame reducer path. Full context/epoch/generation admission remains active; no extra interface cycle is invented.',
        [(top, '.in_slot_valid(source_valid && !error),.frame_start(source_start),.context_in(source_context),')])
    crossing('job_configuration_snapshot', 'host_control', 'setup_profile_banks', ['job_base', 'job_generation', 'job_count', 'cold_c0', 'cold_c1'],
        'Start accepted only with no busy/canonical owner; job configuration is atomically snapshotted and serialized setup retains its context.',
        [(top, 'if((|start_contexts) && !(|busy) && !canonical_owned && !error)begin'),
         (top, 'phase[c]<=PROFILE;job_base[c]<=base[c*32+:32];job_count[c]<=batch_mode[c] ? warm_count[c*32+:32] : 32\'d1;'),
         (arith, 'profile_base[setup_context_q]<=qualified_base;profile_reciprocal[setup_context_q]<=reciprocal;')], kind='operation_latched_configuration')
    crossing('profiles_to_carry', 'setup_profile_banks', 'carry', ['profile_base', 'profile_reciprocal', 'profile_limit', 'profile_generation'],
        'Two profile banks are qualified against the exact frame context/base/generation. Setup is prohibited for a context with live owner/carry state.',
        [(arith, 'assign frame_profile_ok=config_valid[context_in] && base_in==profile_base[context_in] &&'),
         (arith, '.base(profile_base[field_context[0]]),.reciprocal(profile_reciprocal[field_context[0]]),.coefficient_limit(profile_limit[field_context[0]]),')], kind='operation_latched_configuration')
    crossing('descriptors_to_warm_control', 'host_control', 'warm_control', ['head_index', 'head_generation', 'head_double', 'feed_pop'],
        'Full descriptor ordinal/generation are checked before internal frame acceptance; FIFO accepted pop is not an invented pipeline stage.',
        [(warm, 'wire command_bad=command_needed && (!command_valid[feedback_context] ||'),
         (warm, 'assign command_accept[0]=internal_frame_accept && latched_feed[0] && !feedback_context && !command_bad;')])
    for f in range(3):
        field = next(name for name in files if name.startswith('rtl/genefer_stream27_shared_warm_aw16_p16_f' + str(f)) and name.endswith('_storage2_v1.sv'))
        crossing('arithmetic_to_field' + str(f), 'arithmetic_control', 'field' + str(f),
            ['field_input_valid', 'context_in', 'epoch_in', 'generation_in', 'correction_bank'],
            'All four logical lease/full-owner checks remain; accepted data is reduced and tagged under the original calendar, not raw bank-index permission.',
            [(arith, 'assign field_input_valid=in_slot_valid && !out_error && (!frame_start || frame_profile_ok);'),
             (field, 'logic [26:0] payload_owner[0:1];')])
        crossing('field' + str(f) + '_to_CRT', 'field' + str(f), 'CRT',
            ['field_data[' + str(f) + ']', 'field_valid', 'field_context', 'field_epoch', 'field_generation', 'field_row'],
            'Final physical residues feed CRT raw input capture. Three-field full tags/row join is checked; physical lane reverse is explicit. Field-internal pipeline is not counted again as a separate macroblock stage.',
            [(arith, 'wire joined=&field_valid;'), (arith, 'localparam int PHYSICAL=reverse_lane(b);'),
             (crt, 'r1_pipe[0]<=r1[26:0];r2_input<=r2[26:0];r3_input<=r3[26:0];')])
    crossing('CRT_double_to_carry', 'CRT', 'carry', ['crt_coefficient', 'crt_valid', 'crt_tag', 'doubled_data', 'doubled_valid', 'doubled_row', 'doubled_context'],
        'Actual CRT registered coefficient is followed by double-data/valid/context/row FF. Exact owner tag advances alongside CRT latency; selected profile is separately snapshotted.',
        [(arith, 'if(joined)begin crt_tag[0]<={field_context[0],field_epoch[0],field_generation[0],field_row[0]};crt_double[0]<=bank_double[bank];end')],
        [stage('CRT_coefficient_output', 'CRT', 0, crt, ['coefficient'], 'out_valid', [],
               'out_valid<=valid_pipe[14];', 'if(valid_pipe[14])coefficient<=centered_work;'),
         stage('doubled_coefficient', 'arithmetic_control', 1, arith, ['doubled_data'], 'doubled_valid', ['doubled_row', 'doubled_start', 'doubled_context', 'crt_tag'],
               'for(int b=0;b<P;b=b+1)doubled_data[96*b+:96]<=crt_double[15] ? crt_coefficient[b]<<<1 : crt_coefficient[b];',
               'doubled_valid<=(&crt_valid) && !out_error;',
               'doubled_row<=crt_tag[15][ROW_W-1:0];doubled_start<=crt_tag[15][ROW_W-1:0]==0;doubled_context<=crt_tag[15][TAG_W-1];')])
    crossing('carry_feedback_to_warm', 'carry', 'warm_control', ['digit_data', 'digit_valid', 'digit_context', 'digit_epoch', 'digit_generation', 'feedback_owner'],
        'Registered carry output feeds original same-calendar feedback; live generation eligibility and remaining-count authority are retained. Feedback mux is not falsely declared registered.',
        [(warm, 'wire feedback_issue=digit_valid && need_feedback && !local_error;'),
         (warm, 'assign feedback_owner={digit_context,digit_epoch+16\'d1,digit_generation};')])
    crossing('carry_boundary_to_fields', 'carry', 'arithmetic_control', ['next_c0', 'next_c1', 'next_epoch', 'next_generation', 'boundary_context'],
        'Per-context correction begins only at original boundary acceptance; signed final-lane wrap and all owner/cache-ready/E4 checks are unchanged.',
        [(warm, 'wire auto_correction=boundary_valid && feedback_enabled[boundary_context] && !local_error;'),
         (arith, "assign next_c0[0+:32]=32'(-signed_low);assign next_c1[0+:32]=32'(-signed_high);")])
    crossing('final_capture_to_shadows', 'warm_control', 'shadow_images', ['final_owner', 'final_context', 'digit_row', 'digit_data', 'capture_fire'],
        'Actual final raw rows are accepted only in RUN with exact full56 owner and next row. Physical RAM capture acknowledgment is checked one edge later; raw capture is not public canonical publication.',
        [(top, 'wire capture_bad=final_valid && (phase[final_context]!=RUN ||'),
         (top, 'capture_req_d<=capture_fire;'),
         (image, 'commit_ack_d<=commit_fire;capture_ack_d<=capture_fire;rejected_d<=reject_fire;')])
    crossing('shadows_to_canonical_scratch', 'shadow_images', 'canonical_scratch', ['shadow_row_data', 'shadow_response_owner', 'canonical_load', 'row_address_d'],
        'Shared scratch is phase-exclusive. Registered row response is full-owner checked before canonical load; all rows must be loaded before CANON_WAIT. No one-edge total-image claim.',
        [(top, 'wire canonical_load=shadow_row_valid && !row_kind_d && !response_bad && !error;'),
         (top, "if(canonical_load && row_address_d==ROW_W'(ROWS-1))phase[canonical_owner]<=CANON_WAIT;")])
    crossing('canonical_read_to_copy', 'canonical_scratch', 'copy_publication', ['canon_data', 'canon_read_valid', 'canon_address', 'canonical_owner', 'copy_fire'],
        'Real RAM response/read-data FF and ordered copy checks retain sign-extension/address validity. N successful physical commits, not a footer alias, release publication.',
        [(canon, "read_data<=$signed({{64{ram_q[read_bank_d][31]}},ram_q[read_bank_d]});"),
         (top, 'wire copy_bad=canon_read_valid && (copy_issued>=(AW+1)\'(N) || canon_address!=copy_issued[AW-1:0] ||')])
    crossing('copy_to_shadow_publication', 'copy_publication', 'shadow_images', ['copy_fire', 'canon_data', 'canon_address', 'shadow_commit_ack', 'published', 'live_owner'],
        'Shared copy phase commits into the exact context/full56 owner. Final Nth acknowledgment plus requested/issued counts gates done and canonical_ready. No immediate publication of partial data.',
        [(top, '.commit_owner(live_owner[canonical_owner*56+:56]),'),
         (top, 'published[canonical_owner]<=1;done_q[canonical_owner]<=1;phase[canonical_owner]<=IDLE;canonical_owned<=0;')])
    crossing('published_readback_to_host', 'shadow_images', 'copy_publication', ['shadow_scalar_data', 'shadow_scalar_owner', 'shadow_scalar_valid', 'canonical_ready', 'read_valid'],
        'Registered RAM scalar read retains full56 live owner; public read_valid additionally requires this context published and no global error.',
        [(top, 'assign read_valid=shadow_scalar_valid && canonical_ready[shadow_scalar_context] && !error;'),
         (image, 'read_owner<=live_owner[host_context*OWNER_W+:OWNER_W];end')])
    crossing('prospective_fault_to_sticky_origin', 'arithmetic_control', 'host_control', ['child_pending', 'fault_pending', 'out_error', 'child_error', 'local_error'],
        'Prospective diagnostics are intentionally combinational into the origin-edge sticky fault FF; pending has NO source FF. Already admitted origin-edge work/tails are unchanged. This bounded exception does not assert no reconvergent timing path.',
        [(arith, 'if(fault_pending)out_error<=1;'),
         (top, 'assign error=local_error || child_error || canon_error;'),
         (top, '(capture_req_d && !shadow_capture_ack) || (|child_cancelled))local_error<=1;')])
    return dict(schema='prefit-structural-inventory-v1', scope='whole_core',
        identity=dict(top=manifest['top'], device=manifest['device'], parameters=manifest['core_parameters'], clock_period_ns=14.0, seed=1),
        sources={'rtl/' + name: pin for name, pin in manifest['source_sha256'].items()},
        settings=dict(manifest['control_sha256'], **{'manifest.json': sha((json.dumps(manifest, indent=2) + '\n').encode())}),
        blocks=BLOCKS, transfers=transfers,
        exclusions=[dict(kind='external_virtual_io', reason='Compute-only virtual pins; no board I/O, protocol electrical timing, pin mapping or external throughput.', endpoints=['all non-clock top virtual inputs/outputs']),
                    dict(kind='external_reset', reason='Reset release/recovery and board reset distribution are not proven by this source inventory.', endpoints=['rst_n']),
                    dict(kind='inside_single_macroblock', reason='Declared macroblock transfer ledger only; internal CT/GS/root/term/divider connectivity requires actual post-fit reports.', endpoints=['field0/1/2 internal arithmetic', 'CRT/carry internal pipelines'])],
        coverage_claim='declared_source_inventory_not_netlist_completeness',
        limitations=['No C1 mechanical inheritance.', 'No synthesized connectivity completeness or DA/STA PASS.', 'Phase exceptions retain origin-edge fault/control semantics; pending is not registered.'])


def prepare(output):
    out = Path(output).resolve()
    need(out.is_relative_to(ROOT) and not out.exists(), 'fresh owned route output')
    manifest, files = build()
    spec = inventory(manifest, files)
    out.mkdir(parents=True)
    project = out / 'project'
    for name, raw in files.items():
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    (project / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    checker_spec = importlib.util.spec_from_file_location('selected_storage_structural_checker', ROOT / 'tools/prefit_structural_guard_v1.py')
    checker = importlib.util.module_from_spec(checker_spec)
    checker_spec.loader.exec_module(checker)
    result = checker.source_inventory(project, spec)
    need(not result['findings'], 'declared source structural findings')
    (out / 'structural-inventory.json').write_text(json.dumps(spec, indent=2) + '\n')
    return dict(project=str(project), structural_spec=str(out / 'structural-inventory.json'),
                structural_sha256=sha((out / 'structural-inventory.json').read_bytes()),
                source_count=53, declared_crossings=len(spec['transfers']),
                source_findings=result['findings'], native_source_gate=GATE_ID,
                actual_allocation_by_dispatch='AWS12 physical cores/40GiB',
                promotion_allowed=False, physical_timing_proven=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), indent=2))
