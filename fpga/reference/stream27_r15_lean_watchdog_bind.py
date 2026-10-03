"""Private default-OFF FIELD100 lean/report delta and per-context watchdog.

Pure source transform. No shared generator writes, arithmetic/native execution
or protected-twin fault credit. lean build; host GL assumed (unimplemented).
"""
import copy
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_r15_lean_watchdog_bind.py'
MODEL = 'reference/stream27_r15_lean_watchdog_model.py'
WATCH = 'rtl/kernel/genefer_stream27_r15_progress_watchdog_v1.sv'
LABEL = 'lean build; host GL assumed (unimplemented)'
BASE = ROOT / 'results/throughput-20260929/trackS-c2-protected-field100-native-v1'
PARENTS = {256: ('aw8-normal', 'dd8d9196a5ac79381b8e701d021d19a067dde4d319b15799b13f8d8f61441a00'),
           65536: ('full-normal-v2', 'f5f0617d989b64bb965b612a0d0cb8b6074c1ecd4f85f01ed66f970dfbf521f2')}


def sha(raw):
    return hashlib.sha256(raw.encode() if isinstance(raw, str) else raw).hexdigest()


def need(ok, why):
    if not ok:
        raise ValueError('R15_LEAN_WATCHDOG_' + why)


def capture(n):
    need(type(n) is int and n in PARENTS, 'FIELD100_AW8_FULL')
    stage, digest = PARENTS[n]
    raw = (BASE / stage / 'production-bundle.json').read_bytes()
    need(sha(raw) == digest, 'IMMUTABLE_FIELD100')
    return json.loads(raw)


WATCH_HOST = ''' // Real per-context work, not BUSY/peer progress or host timestamps.
 wire [1:0] r15_watch_error,r15_watch_demand,r15_watch_aux;
 wire [2*$clog2(64*N+4097)-1:0] r15_watch_ages;
 wire r15_job_accept=(|start_contexts) && !(|busy) && !canonical_owned && !safety_error;
 for(genvar w=0;w<2;w++)begin: r15_context_liveness
  wire inflight=child_started[w*32+:32]>child_completed[w*32+:32];
  wire runnable_next=phase[w]==RUN && child_completed[w*32+:32]<job_count[w] &&
   (!job_feed[w] || levels[w]!=0);
  wire owned_profile=setup_inflight && setup_context==w;
  wire owned_cold=cold_reader && cold_context==w;
  wire owned_final=canonical_owned && canonical_owner==w &&
   (phase[w]==CANON_LOAD || phase[w]==CANON_WAIT || phase[w]==COPY || phase[w]==COPY_DRAIN);
  assign r15_watch_demand[w]=inflight || runnable_next || owned_profile || owned_cold || owned_final;
  assign r15_watch_aux[w]=(setup_done && setup_done_context==w) ||
   (source_valid && source_context==w) ||
   (child_correction_accept && cold_correction_context==w) ||
   (final_valid && final_context==w) || (final_boundary_valid && boundary_context==w) ||
   (shadow_row_valid && row_context_d==w) ||
   (canonical_owned && canonical_owner==w && (canon_read_valid || shadow_commit_ack || canon_done));
 end
 genefer_stream27_r15_progress_watchdog_v1 #(.CONTEXTS(2),.LIMIT(64*N+4096)) r15_watchdog (
  .clk,.rst_n,.new_job(start_contexts & {2{r15_job_accept}}),
  .active(jobs & {2{!safety_error}}),.demand(r15_watch_demand),.aux_progress(r15_watch_aux),
  .stop(child_cancelled | {2{safety_error}}),.completed(child_completed),
  .error(r15_watch_error),.ages(r15_watch_ages));
'''


def bind(bundle, *, lean_build=0, progress_watchdog=0):
    need(all(type(flag) is int and flag in (0, 1) for flag in (lean_build, progress_watchdog)), 'BOOL_FLAGS')
    out = copy.deepcopy(bundle)
    if not lean_build and not progress_watchdog:
        return out
    need(out['geometry']['n'] in PARENTS and out['parameters']['P'] == 16
         and out['parameters']['MONT_FACTORED'] == 1
         and out['parameters']['CONTEXTS'] == 2
         and all(out['parameters'].get(flag) == 1 for flag in
                 ('FIELD_PROTOCOL_ORIGIN_FAST', 'FIELD_ERROR_REPORT_REG', 'DATAPATH_QUARANTINE_REG',
                  'FEEDBACK_INGRESS_REG', 'AUTO_CORRECTION_INGRESS_REG', 'C0_ADMISSION_DIRECT',
                  'CANONICAL_FOLD_PAYLOAD_REG', 'CARRY_QUARANTINE_LOCAL'))
         and 'LEAN_BUILD' not in out['parameters'] and 'PROGRESS_WATCHDOG' not in out['parameters'],
         'FIELD100_LINEAGE_OR_COMPATIBLE_NEUTRAL_R15_COMPOSITION')
    original = dict(out['files'])
    bodies, edits, mapping = dict(original), {}, {}

    def change(name, before, after):
        need(bodies[name].count(before) == 1, 'UNIQUE_ANCHOR:' + name + ':' + before[:48])
        bodies[name] = bodies[name].replace(before, after, 1)
        edits.setdefault(name, []).append([before, after])

    host = out['top'] + '.sv'
    error_before = ' assign error=local_error || child_error || canon_error;'
    safety_before = ' assign safety_error=local_error || child_error_barrier || canon_error;'
    if lean_build:
        comm = 'genefer_stream27_mdc_commutator_shared_packed_faultlocal_v1.sv'
        text = bodies[comm]
        start = text.index('  owner_bad=(phase?pair_bad_current:pair_bad_delayed)')
        end = text.index('\n  expected_generation=', start)
        change(comm, text[start:end], "  owner_bad=1'b0; // Optional fault comparison only; eligibility generation remains.")
        field_names = [name for name, text in bodies.items()
                       if name.startswith('genefer_stream27_shared_warm_aw') and ' assign out_error_fast=protocol_error;' in text]
        need(len(field_names) == 3, 'THREE_FIELD_ROLES')
        for name in field_names:
            change(name, ' assign out_error=controller_error;', " assign out_error=1'b0; // Lean optional report aggregation absent.")
            change(name, ' assign fault_pending=out_error_fast || (|child_pending) || protocol_pending || (!stop && (admission_bad || join_bad));',
                   ' assign fault_pending=out_error_fast || protocol_pending || (!stop && (admission_bad || join_bad));')
            change(name, '.external_fault_pending(admission_bad || join_bad || (|child_pending) || inverse_pending)',
                   '.external_fault_pending(admission_bad || join_bad)')
        arithmetic = [name for name, text in bodies.items() if ' assign error_barrier=out_error || (|field_fast) || local_fault_q;' in text]
        need(len(arithmetic) == 1, 'ONE_ARITHMETIC_ROLE')
        change(arithmetic[0], 'wire local_fault_now=setup_error || (|lane_error) || join_bad || carry_bad || admission_bad;',
               'wire local_fault_now=setup_error || join_bad || carry_bad || admission_bad;')
        change(arithmetic[0], '   if((|field_error) || local_fault_q)out_error<=1;',
               '   if(local_fault_q)out_error<=1; // Optional child numeric reports absent; functional framing remains.')
        # The warm descriptor/source/count/collision checks and child FAST
        # propagation are functional authority, including earlier R15 fixed
        # schedule underflow additions. Keep this body literal apart from
        # recursive module identifiers below.
    if progress_watchdog:
        change(host, error_before, WATCH_HOST + ' assign error=local_error || child_error || canon_error || (|r15_watch_error);')
        change(host, safety_before, ' assign safety_error=local_error || child_error_barrier || canon_error || (|r15_watch_error);')
    change(host, 'CONTEXTS=2,', f'CONTEXTS=2,LEAN_BUILD={lean_build},PROGRESS_WATCHDOG={progress_watchdog},')
    # Clone changed definitions and their callers; protected originals can be
    # compiled beside this private graph in a true numerical twin.
    for name in edits:
        mapping[name[:-3]] = name[:-3] + '_r15_leanwatch_v1'
    while True:
        added = False
        for name, text in bodies.items():
            if name[:-3] in mapping:
                continue
            if any(re.search(r'\b' + re.escape(old) + r'\s*#\s*\(', text) for old in mapping):
                need(re.search(r'\bmodule\s+' + re.escape(name[:-3]) + r'\b', text) is not None,
                     'ONE_MODULE_CALLER_ROLE:' + name)
                mapping[name[:-3]] = name[:-3] + '_r15_leanwatch_v1'
                added = True
        if not added:
            break
    changed = {}
    final_files = {}
    for name, text in bodies.items():
        if name[:-3] not in mapping:
            final_files[name] = text
            continue
        new_name = mapping[name[:-3]] + '.sv'
        for old, new in mapping.items():
            text = re.sub(r'\b' + re.escape(old) + r'\b', new, text)
        reverse = text
        for old, new in mapping.items():
            reverse = re.sub(r'\b' + re.escape(new) + r'\b', old, reverse)
        for before, after in reversed(edits.get(name, [])):
            need(reverse.count(after) == 1, 'UNIQUE_REVERSE:' + name)
            reverse = reverse.replace(after, before, 1)
        need(reverse == original[name], 'LITERAL_BYTE_REVERSE:' + name)
        final_files[new_name] = text
        changed[new_name] = dict(parent=name, parent_sha256=sha(original[name]),
                                edits=edits.get(name, []), module_mapping=mapping, reverse_exact=True)
    need(out['top'] in mapping, 'HOST_ROLE_REBOUND')
    if progress_watchdog:
        final_files[Path(WATCH).name] = (ROOT / WATCH).read_text()
    out['files'], out['top'] = final_files, mapping[out['top']]
    out['parameters'] = dict(out['parameters'], LEAN_BUILD=lean_build, PROGRESS_WATCHDOG=progress_watchdog)
    out['rtl_sources'] = list(final_files)
    out['generated_sha256'] = {name: sha(text) for name, text in final_files.items()}
    out['source_dependencies'] = list(dict.fromkeys(out['source_dependencies'] + [SELF, MODEL, WATCH]))
    out['source_sha256'] = {name: sha((ROOT / name).read_bytes()) for name in out['source_dependencies']}
    out['r15_lean_watchdog'] = dict(enabled=True, flags=dict(LEAN_BUILD=lean_build, PROGRESS_WATCHDOG=progress_watchdog),
        label=LABEL if lean_build else 'protected build with per-context liveness watchdog',
        parent_top=bundle['top'], parent_generated_sha256=bundle['generated_sha256'], modified=changed,
        disabled_byte_exact=True, geometry_unchanged=True,
        owner_context_generation_row_profile_lease_lookup_retained=True,
        cold_oneshot_full56_publication_copy_and_descriptor_framing_retained=True,
        optional_comm_owner_fault_compare_removed=bool(lean_build),
        optional_child_numeric_report_aggregation_removed=bool(lean_build),
        protocol_FAST_source_mismatch_join_carry_admission_authority_retained=True,
        warm_descriptor_count_collision_underflow_fault_body_retained=True,
        watchdog_completed_per_context=True, peer_progress_does_not_reset_other_age=True,
        watchdog_inflight_cannot_be_paused_by_missing_descriptor=True,
        legitimate_host_idle_descriptor_gap_or_shared_scratch_wait_not_inflight_work=True,
        active_fixed_schedule_descriptor_underflow_remains_typed_functional_fault=True,
        sticky_watchdog_failure_reset_only=True, cancel_disarms_age_not_raw_tail_flush=True,
        host_gl_implemented=False, rollback_implemented=False, twin_fault_protection_inherited=False,
        native_qualified=False, physical_gain_claim=False, promotion_allowed=False)
    return out


def prepare(n=256, *, lean_build=0, progress_watchdog=0):
    return bind(capture(n), lean_build=lean_build, progress_watchdog=progress_watchdog)
