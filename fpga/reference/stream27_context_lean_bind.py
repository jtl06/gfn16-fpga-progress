"""Private default-OFF R7 lean subset. No shared generator or arithmetic edits.

Every enabled result: lean build; host GL assumed (unimplemented).
Trusted healthy inputs only. Protected twin fault protections are NOT hardware
properties of this graph. R9 composition is deliberately not accepted here.
"""
import copy
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_context_lean_bind.py'
LABEL = 'lean build; host GL assumed (unimplemented)'
BASE = ROOT / 'results/throughput-20260929/trackS-c2-storage-combo-faultlocal-native-v1'
PINS = {256: '7f17f9e1410eac6d1fbfc3909717bbd28296e943833b15230aeab53dcc625608',
        65536: 'e2671f87b4f6173dbfebd5eb30ddfbe0113cb78fe692d4b594d2492e60c343e7'}
OLD_COMM = 'genefer_stream27_mdc_commutator_shared_packed_faultlocal_v1'
OLD_CANON = 'genefer_stream27_canonical_image_loadlocal_v1'
OLD_SHADOW = 'genefer_stream27_host_image_rowwrite_v1'
NEW_COMM = 'genefer_stream27_mdc_commutator_shared_packed_lean_v1'
NEW_CANON = 'genefer_stream27_canonical_image_lean_v1'
NEW_SHADOW = 'genefer_stream27_host_image_rowwrite_lean_v1'


def sha(raw):
    return hashlib.sha256(raw.encode() if isinstance(raw, str) else raw).hexdigest()


def need(ok, why):
    if not ok:
        raise ValueError('C2_LEAN_' + why)


def once(text, before, after, edits):
    need(text.count(before) == 1, 'EXACT_ANCHOR:' + before[:48])
    edits.append((before, after))
    return text.replace(before, after, 1)


def region(text, begin, end, replacement, edits):
    need(text.count(begin) == text.count(end) == 1, 'UNIQUE_REGION')
    first = text.index(begin)
    last = text.index(end, first)
    return once(text, text[first:last], replacement, edits)


def capture(n):
    need(type(n) is int and n in PINS, 'ONLY_CAPTURED_AW8_FULL')
    p = BASE / ('aw8-normal' if n == 256 else 'full-normal') / 'production-bundle.json'
    raw = p.read_bytes()
    need(sha(raw) == PINS[n], 'IMMUTABLE_R7_CAPTURE')
    return json.loads(raw)


WATCHDOG = ''' // Lean minimal GLOBAL progress watchdog, not a per-context hang proof.
 // Separate age is never the low32 host scheduling timestamp; wrap is harmless.
 localparam int LEAN_WATCHDOG_LIMIT=64*N+4096;
 logic [$clog2(LEAN_WATCHDOG_LIMIT+1)-1:0] lean_watchdog_age;
 logic lean_watchdog_error;
 wire lean_progress=setup_done || child_frame_accept || child_correction_accept ||
  final_valid || final_boundary_valid || shadow_row_valid || canon_read_valid ||
  shadow_commit_ack || canon_done || (|child_warm_done);
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin lean_watchdog_age<=0;lean_watchdog_error<=0;end
  else if(!( |busy) || lean_progress)lean_watchdog_age<=0;
  else if(lean_watchdog_age==$clog2(LEAN_WATCHDOG_LIMIT+1)'(LEAN_WATCHDOG_LIMIT-1))
   lean_watchdog_error<=1;
  else lean_watchdog_age<=lean_watchdog_age+1'b1;
 end
'''


def bind(bundle, *, enabled=0):
    need(type(enabled) is int and enabled in (0, 1), 'BOOLEAN_SWITCH')
    out = copy.deepcopy(bundle)
    if not enabled:
        return out
    n = out['geometry']['n']
    parent = capture(n)
    need(out == parent and len(out['files']) == 55, 'EXACT_R7_ONLY_NO_R9_GUESS')
    changes = {}
    substitutions = {}

    def transform(old, new, apply):
        text = out['files'].pop(old + '.sv')
        edits = []
        changed = apply(text, edits)
        changed = once(changed, 'module ' + old + ' #', 'module ' + new + ' #', edits)
        reverse = changed
        for before, after in reversed(edits):
            need(reverse.count(after) == 1, 'UNIQUE_REVERSE')
            reverse = reverse.replace(after, before, 1)
        need(reverse == text, 'EVERY_CHANGED_BYTE_REVERSES')
        out['files'][new + '.sv'] = changed
        changes[new + '.sv'] = dict(parent=old + '.sv', parent_sha256=sha(text),
                                  reverse_exact=True, edits=edits)
        substitutions[old] = new

    def comm(text, edits):
        return region(text, '  owner_bad=(phase?pair_bad_current:pair_bad_delayed)',
                      '\n  expected_generation=',
                      '  owner_bad=1\'b0; // Lean: no owner/generation fault protection.\n', edits)

    def shadow(text, edits):
        text = region(text, '    wire commit_authorized=', '    logic [CONTEXTS-1:0] denied;',
                      '''    // Lean keeps context/port collision arbitration, not full-owner checks.
    wire commit_authorized=owner_enabled[commit_context];
    wire capture_authorized=owner_enabled[row_write_context];
    wire row_authorized=owner_enabled[row_read_context];
''', edits)
        return text

    def canon(text, edits):
        text = once(text, "    wire base_ok=base>=32'(BASE_MIN) && base<=32'd1000000000;",
                    "    wire base_ok=1'b1; // Lean trusted-profile assumption, not admission.", edits)
        text = region(text, '    always_comb begin\n        load_bad=0;correction_bad=0;',
                      '    // The supported profile closes',
                      '''    // Lean omits malformed/range guards; exclusive operation framing remains.
    always_comb begin
        load_bad=0;correction_bad=0;bound_c0=0;input_c0=0;input_c1=0;
        idle_reject=0;idle_code=0;
    end
''', edits)
        text = region(text, '        process_bad=0;process_code=0;\n', '    for(genvar b=0;b<P;',
                      '        process_bad=0;process_code=0; // Lean: no intermediate range detection.\n    end\n', edits)
        return text

    transform(OLD_COMM, NEW_COMM, comm)
    # Live generation selects eligible payloads; it is routing, not verification.
    parent_comm = parent['files'][OLD_COMM + '.sv']
    live_generation = parent_comm[parent_comm.index('  expected_generation='):
                                  parent_comm.index('  fault_pending=')]
    need(live_generation in out['files'][NEW_COMM + '.sv'], 'FUNCTIONAL_GENERATION_ELIGIBILITY_RETAINED')
    transform(OLD_CANON, NEW_CANON, canon)
    transform(OLD_SHADOW, NEW_SHADOW, shadow)
    oldtop = out['top']
    top = f'genefer_stream27_host_contexts_aw{out["geometry"]["aw"]}_p16_lean_r7_v1'

    def host(text, edits):
        text = once(text, 'CONTEXTS=2,COLD_SECOND_ONESHOT=1,',
                    'CONTEXTS=2,LEAN_PRODUCTION=1,COLD_SECOND_ONESHOT=1,', edits)
        text = region(text, ' wire capture_bad=final_valid && ', ' wire capture_fire=',
                      " wire capture_bad=1'b0; // Lean: no full56/row capture verification.\n", edits)
        text = region(text, ' wire response_bad=shadow_row_valid && ', ' wire canonical_load=',
                      " wire response_bad=1'b0; // Lean: no full56 response verification.\n", edits)
        text = once(text, ' assign error=local_error || child_error || canon_error;',
                    WATCHDOG+' assign error=local_error || lean_watchdog_error;', edits)
        text = once(text, '''   if(ingress_bad || capture_bad || response_bad || copy_bad || shadow_rejected ||
    (capture_req_d && !shadow_capture_ack) || (|child_cancelled))local_error<=1;''',
                    '''   // Minimal descriptor/copy framing retained; child typed faults are not aggregated.
   if(ingress_bad || copy_bad || (capture_req_d && !shadow_capture_ack))local_error<=1;''', edits)
        text = once(text, '''     if(base[c*32+:32]<32'(MIN_BASE) || base[c*32+:32]>32'd1000000000 || job_generation[c]==8'hff ||
      (batch_mode[c] && (warm_count[c*32+:32]==0 || (!feed_mode[c] && warm_count[c*32+:32]>32'd32))))local_error<=1;''',
                    '''     // Lean input domain is supplied by the trusted host; count framing remains.
     if(batch_mode[c] && (warm_count[c*32+:32]==0 || (!feed_mode[c] && warm_count[c*32+:32]>32'd32)))local_error<=1;''', edits)
        text = once(text, '''    if(boundary_sequence!=job_count[boundary_context]-32'd1 ||
     {boundary_sequence,16'(boundary_epoch-16'd1),boundary_generation}!=live_owner[boundary_context*56+:56])local_error<=1;
''', '    // Lean does not verify boundary owner/ordinal; routing/data remain unchanged.\n', edits)
        return text

    transform(oldtop, top, host)
    # Identifier-only binding at existing consumers; no unrelated module replacement.
    for name, text in list(out['files'].items()):
        for old, new in substitutions.items():
            if old + ' #' in text:
                count = text.count(old + ' #')
                need((old == OLD_COMM and ('_merged_ct_' in name or '_merged_gs_' in name)
                      and count == out['geometry']['aw']-4) or
                     (old in (OLD_CANON, OLD_SHADOW) and name == top+'.sv' and count == 1),
                     'ONLY_EXACT_EXISTING_CALLERS')
                updated = text.replace(old + ' #', new + ' #')
                need(updated.replace(new + ' #', old + ' #') == text, 'CALLER_REVERSE')
                out['files'][name] = text = updated
                if name not in changes:
                    changes[name] = dict(parent=name, parent_sha256=sha(parent['files'][name]),
                                         reverse_exact=True, edits=[])
                changes[name]['edits'].append((old + ' #', new + ' #'))
                need(count > 0, 'ACTUAL_CONSUMER')
    out['top'] = top
    out['parameters'] = dict(out['parameters'], LEAN_PRODUCTION=1)
    out['rtl_sources'] = list(out['files'])
    out['generated_sha256'] = {name: sha(text) for name, text in out['files'].items()}
    out['source_dependencies'] = list(dict.fromkeys(out['source_dependencies']+[SELF]))
    out['source_sha256'] = {p: sha((ROOT/p).read_bytes()) for p in out['source_dependencies']}
    # R6 acceptance/pending/wrap transaction is literal, not an inferred equivalent.
    original_host = parent['files'][oldtop + '.sv']
    original_oneshot = original_host[original_host.index('  // Cold-only transaction:'):original_host.index(' wire cold_first_correction=')]
    need(original_oneshot in out['files'][top + '.sv'], 'R6_ONESHOT_LITERAL')
    need('canonical_owner<=phase[0]!=RAW_READY' in out['files'][top + '.sv'], 'FUNCTIONAL_SELECTOR_RETAINED')
    out['lean_production'] = dict(label=LABEL, enabled=True, parent_top=oldtop,
        parent_bundle_sha256=PINS[n], parent_generated_sha256=parent['generated_sha256'],
        modified=changes, default_off_exact=True, r6_oneshot_literal=True,
        functional_context_row_profile_payload_valid_cadence_routing_retained=True,
        recurrence_lease_lookup_bypass_and_write_eligibility_retained=True,
        complete_copy_counters_retained=True, canonical_owner_functional_not_removed=True,
        watchdog='global progress only; peer progress can mask an isolated hang; trusted timely feed',
        host_gl_implemented=False, rollback_implemented=False, twin_fault_immunity_inherited=False,
        native_qualified=False, physical_gain_claim=False, clock_claim=False, promotion_allowed=False)
    return out


def prepare(n=256, *, enabled=0):
    return bind(capture(n), enabled=enabled)
