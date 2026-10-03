"""Private default-OFF lean on the exact captured R9 protected graph.

lean build; host GL assumed (unimplemented). Keeps R9 safety barriers and
entire publication proposal/drain. No timing10/shared-generator edits.
"""
import copy
import json
from pathlib import Path

from . import stream27_context_lean_bind as subset

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_context_lean_r9_bind.py'
SUBSET = 'reference/stream27_context_lean_bind.py'
SUBSET_PIN = '8b839edd1cdd3a9ce05072a89fdb6dba60a61bb47e66c3a4a98dc57f1afa5778'
BASE = ROOT/'results/throughput-20260929/trackS-c2-storage-combo-registerederror-native-v1'
PINS = {256: '810b778524fe709d5303ce0cb57cd4c9e9296a5acc4c72bcd19e143f69b22a46',
        65536: '01220c6efc522973786786eb5c65076d3bf396a9c290aa65464e3086e34d8bc9'}
sha, need, once, region = subset.sha, subset.need, subset.once, subset.region


def capture(n):
    need(type(n) is int and n in PINS, 'R9_ONLY_CAPTURED_AW8_FULL')
    raw = (BASE/('aw8-normal' if n == 256 else 'full-normal')/'production-bundle.json').read_bytes()
    need(sha(raw) == PINS[n], 'R9_IMMUTABLE_CAPTURE')
    return json.loads(raw)


def bind(bundle, *, enabled=0):
    need(type(enabled) is int and enabled in (0, 1), 'BOOLEAN_SWITCH')
    out = copy.deepcopy(bundle)
    if not enabled:
        return out
    need(sha((ROOT/SUBSET).read_bytes()) == SUBSET_PIN, 'FROZEN_APPROVED_R7_SUBSET')
    n = out['geometry']['n']
    parent = capture(n)
    need(out == parent and len(out['files']) == 55, 'EXACT_R9_ONLY_NO_R10_GUESS')
    legacy = subset.prepare(n, enabled=1)
    changes = {}
    substitutions = {}

    def transform(old, new, apply):
        original = out['files'].pop(old+'.sv')
        edits = []
        changed = apply(original, edits)
        changed = once(changed, 'module '+old+' #', 'module '+new+' #', edits)
        reverse = changed
        for before, after in reversed(edits):
            need(reverse.count(after) == 1, 'R9_UNIQUE_REVERSE')
            reverse = reverse.replace(after, before, 1)
        need(reverse == original, 'R9_EVERY_MODIFIED_BYTE_REVERSES')
        out['files'][new+'.sv'] = changed
        changes[new+'.sv'] = dict(parent=old+'.sv', parent_sha256=sha(original),
                                 reverse_exact=True, edits=edits)
        substitutions[old] = new

    # Only literal, already-tested private checking edits, not arbitrary hooks.
    for old, new in ((subset.OLD_COMM, subset.NEW_COMM), (subset.OLD_SHADOW, subset.NEW_SHADOW)):
        delta = legacy['lean_production']['modified'][new+'.sv']
        need(sha(out['files'][old+'.sv']) == delta['parent_sha256'], 'R9_EXACT_COMMON_LEAF')
        def apply(text, edits, operations=delta['edits'][:-1]):
            for before, after in operations:
                text = once(text, before, after, edits)
            return text
        transform(old, new, apply)
    oldcanon = 'genefer_stream27_canonical_image_directbound_v1'
    newcanon = 'genefer_stream27_canonical_image_lean_r9_v1'

    def canonical(text, edits):
        text = once(text, "    wire base_ok=base>=32'(BASE_MIN) && base<=32'd1000000000;",
                    "    wire base_ok=1'b1; // Lean trusted-profile assumption, not admission.", edits)
        text = region(text, '    always_comb begin\n        load_bad=0;correction_bad=0;',
            '    // The supported profile closes',
            '''    // Lean range checking absent; live arithmetic/fold and exclusive framing remain.
    always_comb begin
        load_bad=0;correction_bad=0;direct_base_c0=0;input_c0=0;input_c1=0;
        idle_reject=0;idle_code=0;
    end
''', edits)
        text = region(text, '        process_bad=0;process_code=0;\n', '    for(genvar b=0;b<P;',
            '        process_bad=0;process_code=0; // Lean: no intermediate range detection.\n    end\n', edits)
        return text

    transform(oldcanon, newcanon, canonical)
    oldtop = out['top']
    top = f'genefer_stream27_host_contexts_aw{out["geometry"]["aw"]}_p16_lean_r9_v1'
    legacy_host = legacy['lean_production']['modified'][legacy['top']+'.sv']

    def host(text, edits):
        for before, after in legacy_host['edits']:
            if before.startswith('module ') or before.endswith(' #'):
                continue  # R9 root/caller identifiers are rebound separately.
            # R9 retained every healthy R7 anchor modified by the subset. Its
            # new safety/publication behavior is outside all these regions.
            text = once(text, before, after, edits)
        text = once(text, ' assign safety_error=local_error || child_error_barrier || canon_error;',
                    ' assign safety_error=local_error || child_error_barrier || canon_error || lean_watchdog_error;', edits)
        return text

    transform(oldtop, top, host)
    for name, text in list(out['files'].items()):
        for old, new in substitutions.items():
            if old+' #' not in text:
                continue
            count = text.count(old+' #')
            need((old == subset.OLD_COMM and ('_merged_ct_' in name or '_merged_gs_' in name)
                  and count == out['geometry']['aw']-4) or
                 (old in (oldcanon, subset.OLD_SHADOW) and name == top+'.sv' and count == 1),
                 'R9_ONLY_EXACT_CALLERS')
            updated = text.replace(old+' #', new+' #')
            need(updated.replace(new+' #', old+' #') == text, 'R9_CALLER_REVERSE')
            out['files'][name] = text = updated
            if name not in changes:
                changes[name] = dict(parent=name, parent_sha256=sha(parent['files'][name]),
                                     reverse_exact=True, edits=[])
            changes[name]['edits'].append((old+' #', new+' #'))
    # Source-level assertions bind the exact retained functional interfaces.
    protected = parent['files'][oldtop+'.sv']
    emitted = out['files'][top+'.sv']
    for begin, end in (('  // Cold-only transaction:', ' wire cold_first_correction='),
                       ('   // Hold the scratch lease', '   if(shadow_commit_ack && canonical_owned)begin')):
        block = protected[protected.index(begin):protected.index(end)]
        need(block in emitted, 'R9_ONESHOT_AND_PUBLICATION_BLOCKS_LITERAL')
    for anchor in ('publish_pending<=0;publish_context<=0;publish_owner<=0;',
                   'publish_pending<=1;publish_context<=canonical_owner;',
                   'publish_owner<=live_owner[canonical_owner*56+:56];',
                   'wire child_error_barrier,safety_error;',
                   '.error_barrier(child_error_barrier),',
                   'canonical_owner<=phase[0]!=RAW_READY'):
        need(anchor in emitted, 'R9_FUNCTIONAL_PUBLICATION_BARRIER:'+anchor)
    comm = parent['files'][subset.OLD_COMM+'.sv']
    gen = comm[comm.index('  expected_generation='):comm.index('  fault_pending=')]
    need(gen in out['files'][subset.NEW_COMM+'.sv'], 'R9_FUNCTIONAL_GENERATION_DRIVE')
    for name in parent['files']:
        if 'registered_error_v1' in name or name.startswith('genefer_stream27_shared_warm_aw'):
            need(out['files'][name] == parent['files'][name], 'R9_ARITHMETIC_WARM_FIELD_BARRIERS_LITERAL')
    out.update(top=top, parameters=dict(out['parameters'], LEAN_PRODUCTION=1))
    out['rtl_sources'] = list(out['files'])
    out['generated_sha256'] = {name: sha(text) for name, text in out['files'].items()}
    out['source_dependencies'] = list(dict.fromkeys(out['source_dependencies']+[SUBSET, SELF]))
    out['source_sha256'] = {name: sha((ROOT/name).read_bytes()) for name in out['source_dependencies']}
    out['lean_production'] = dict(label=subset.LABEL, enabled=True, default_off_exact=True,
        parent_top=oldtop, parent_bundle_sha256=PINS[n], parent_generated_sha256=parent['generated_sha256'],
        modified=changes, r6_oneshot_literal=True, r9_publication_proposal_and_drain_literal=True,
        r9_arithmetic_warm_error_barrier_literal=True, safety_error_masks_retained=True,
        watchdog_stop_added_to_safety_mask=True, functional_generation_eligibility_retained=True,
        functional_context_row_profile_payload_valid_cadence_routing_retained=True,
        recurrence_lease_lookup_bypass_and_write_eligibility_retained=True,
        canonical_owner_functional_not_removed=True, complete_copy_counters_retained=True,
        canonical_live_arithmetic_and_fold_retained=True, healthy_publication_edges_extra_vs_R9=0,
        watchdog='global progress only; peer progress can mask an isolated hang; trusted timely feed',
        host_gl_implemented=False, rollback_implemented=False, twin_fault_immunity_inherited=False,
        native_qualified=False, clock_or_area_claim=False, promotion_allowed=False)
    return out


def prepare(n=256, *, enabled=0):
    return bind(capture(n), enabled=enabled)
