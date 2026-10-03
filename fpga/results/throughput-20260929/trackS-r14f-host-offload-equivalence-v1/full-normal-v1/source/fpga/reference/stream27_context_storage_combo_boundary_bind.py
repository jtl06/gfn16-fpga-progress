"""R95: coherent boundary ingress register on frozen combined C2 only.

The exact timing7 wrapper cuts fault/accept/base selection before magnitude.
It delays the correction cache by one edge, not sticky field fault authority.
Small geometry needs one counted frontend edge; full public edges are exact.
No quarantine-replica, final-GS, localbase, selector, GEN or lean flag is mixed.
"""
import copy
import hashlib
import re
from pathlib import Path

from . import stream27_context_storage_combo_bind as combo
from . import s4_two_context_model_v1 as ports

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_context_storage_combo_boundary_bind.py'
LEAF = 'rtl/kernel/genefer_stream27_signed_boundary_inputreg_v1.sv'
PARENT_PIN = '9d34d0980209b48f90a8c2fa96a72fe537bef9094f3a56d71e4e80a4beef5243'


def need(ok, label):
    if not ok:
        raise ValueError('C2_COMBO_BOUNDARY_' + label)


def sha(raw):
    return hashlib.sha256(raw if isinstance(raw, bytes) else raw.encode()).hexdigest()


def once(text, before, after):
    need(text.count(before) == 1, 'ANCHOR:' + before[:80])
    out = text.replace(before, after, 1)
    need(out.count(after) == 1 and out.replace(after, before, 1) == text, 'LITERAL_REVERSE')
    return out


def geometry(before):
    g = dict(before)
    added = max(0, g['correction_cache_latency'] + 2 - g['pointwise_accept'])
    need(added in (0, 1), 'COUNTED_FRONTEND_BOUNDED')
    if added:
        need(g['input_delay'] == 7 and g['n'] == 256, 'ACTUAL_SMALL_FRONTEND_PARENT')
        for key in ('forward_accept', 'pointwise_accept', 'square_accept', 'inverse_accept',
                    'physical_first', 'sink_accept', 'last_sink', 'crt_accept', 'crt_output',
                    'double_register', 'carry_accept', 'first_digit', 'last_digit', 'boundary_output', 'carry_done'):
            g[key] += added
        g['input_delay'] += added
    g['correction_cache_latency'] += 1
    g['term_seed_first'] += 1
    g['term_seed_last'] += 1
    earliest, correction = g['first_digit'] + 1, g['boundary_output'] + 1
    interval = max(earliest, correction + g['correction_cache_latency'] + 1 - g['pointwise_accept'])
    correction = max(correction, interval)
    g.update(warm_interval=interval, earliest_next_frame=earliest,
        feedback_delay=interval-earliest, feedback_fifo_rows=interval-earliest,
        next_correction_accept=correction, next_cache_capture=correction+g['correction_cache_latency'],
        cache_margin=interval+g['pointwise_accept']-correction-g['correction_cache_latency']-1,
        initial_latest_correction=g['pointwise_accept']-g['correction_cache_latency']-1,
        carry_busy_edges=g['carry_done']-g['sink_accept']+1,
        boundary_frontend_added=added, boundary_inputreg=1)
    need(g['feedback_delay'] == before['feedback_delay'] and g['cache_margin'] >= 0 and
         g['initial_latest_correction'] >= 0, 'CACHE_AND_LITERAL_FEEDBACK_DEPTH')
    return g


def schedule(g, counts=(4, 4)):
    need(len(counts) == 2 and all(type(c) is int and 1 <= c <= 16 for c in counts), 'BOUNDED_COUNTS')
    interval, offset = g['warm_interval'], g['warm_interval']//2
    frames = sorted([ports.Frame(ctx, 11+12*ctx, (65534+ordinal)&65535, ordinal,
        ordinal*interval+ctx*offset, (604832956, 999999937)[ctx])
        for ctx in range(2) for ordinal in range(counts[ctx])], key=lambda f: f.start)
    for label, key, width in (('INPUT', None, g['rows']), ('PW', 'pointwise_accept', g['rows']),
                              ('SINK', 'sink_accept', g['rows']), ('DIGIT', 'first_digit', g['rows']),
                              ('CARRY', 'sink_accept', g['carry_busy_edges'])):
        ports.disjoint([(f.start+(g[key] if key else 0), f.start+(g[key] if key else 0)+width-1, f.tag)
                        for f in frames], label)
    corrections = ports.correction_calendar(frames, g, pair_interval=g['correction_pair_interval'])
    feedback = ports.feedback_queues(frames, g)
    live, allocation, peak = {}, [], 0
    for f in frames:
        live = {bank: old for bank, old in live.items() if old.start+g['last_sink'] >= f.start}
        free = [bank for bank in range(4) if bank not in live]
        need(bool(free), 'FOUR_LOGICAL_PREFREE_LEASES')
        bank = free[0]
        live[bank] = f
        live = {b: old for b, old in live.items() if old.start+g['last_sink'] > f.start}
        peak = max(peak, len(live))
        allocation.append(dict(context=f.context, ordinal=f.ordinal, start=f.start, bank=bank))
    return dict(status='PASS_MODEL_ONLY', geometry=g, per_context_interval=interval,
        context_offset=offset, launch_gaps=[offset, interval-offset], correction=corrections,
        frame_starts=[f.start for f in frames], lease_allocation=allocation, lease_peak=peak,
        feedback_peak_rows=feedback, full_N_numeric_performed=False,
        scope='Exact counted boundary ingress/cache/port schedule, not numerical/physical qualification')


def pad_root(text, before, after):
    old, new = before['input_delay'], after['input_delay']
    if old == new:
        return text
    marker = f' // Explicit {old}-edge input delay: serialized corrections precede first pointwise read.'
    start = text.index(marker)
    end = re.search(r' \w+ term_roots \(', text[start:]).start()+start
    parent, updated = text[start:end], text[start:end]
    changes = [(f'Explicit {old}-edge', f'Explicit {new}-edge', 1),
        (f'logic [{old-1}:0] front_valid;', f'logic [{new-1}:0] front_valid;', 1),
        (f'[0:{old-1}]', f'[0:{new-1}]', 2),
        (f'front_valid[{old-1}]', f'front_valid[{new-1}]', 1),
        (f'front_data[{old-1}]', f'front_data[{new-1}]', 1),
        (f'front_tag[{old-1}]', f'front_tag[{new-1}]', 1),
        (f'front_valid[{old-2}:0]', f'front_valid[{new-2}:0]', 1),
        (f'd<{old};', f'd<{new};', 1)]
    for a, b, count in changes:
        need(updated.count(a) == count, 'FRONTPAD:' + a)
        updated = updated.replace(a, b)
    reverse = updated
    for a, b, count in reversed(changes):
        need(reverse.count(b) == count, 'FRONTPAD_REVERSE')
        reverse = reverse.replace(b, a)
    need(reverse == parent, 'FRONTPAD_LITERAL_REVERSE')
    return text[:start]+updated+text[end:]


def bind(bundle, *, enabled=0):
    need(type(enabled) is int and enabled in (0, 1), 'BOOLEAN_SWITCH')
    out = copy.deepcopy(bundle)
    if not enabled:
        return out
    need(sha((ROOT/combo.SELF).read_bytes()) == PARENT_PIN, 'IMMUTABLE_COMBO_GENERATOR')
    n = out['geometry']['n']
    parent = combo.prepare(n, enabled=1)
    need(out == parent, 'EXACT_COMBO_ONLY_NO_OTHER_FLAGS')
    before, g = copy.deepcopy(out['geometry']), geometry(out['geometry'])
    plan = schedule(g)
    renames = {}
    for filename in list(out['files']):
        if not filename.startswith('genefer_stream27_shared_warm_'):
            continue
        text = out['files'].pop(filename)
        old = filename[:-3]
        f = re.search(r'_f([012])_', old)[1]
        new = f'genefer_stream27_shared_warm_aw{g["aw"]}_p16_f{f}_storage_combo_boundary_v1'
        text = pad_root(text, before, g)
        text = once(text, 'genefer_stream27_signed_boundary_reduce27_pipe #(',
                    'genefer_stream27_signed_boundary_inputreg_v1 #(')
        text = once(text, '.clk,.rst_n,.in_valid(boundary_slot),',
                    '.clk,.rst_n,.quarantine(stop),.in_valid(boundary_slot),')
        need(text.count('.PAYLOAD_W(27)) boundary (') == 1, 'FULL27_OWNER_REGISTERED')
        for key, param in (('pointwise_accept', 'POINTWISE_FIRST'), ('sink_accept', 'SINK_FIRST')):
            if before[key] != g[key]:
                text = once(text, f'.{param}({before[key]})', f'.{param}({g[key]})')
        text = once(text, 'module '+old+' #', 'module '+new+' #')
        text = once(text, ',CONTEXTS=2', ',CONTEXTS=2,BOUNDARY_INPUTREG=1')
        text = once(text, 'CONTEXTS!=2', 'CONTEXTS!=2 || BOUNDARY_INPUTREG!=1')
        out['files'][new+'.sv'] = text
        renames[old] = new
    need(len(renames) == 3, 'ALL_THREE_FIELDS')
    for filename, text in list(out['files'].items()):
        for old, new in renames.items():
            text = re.sub(r'\b'+re.escape(old)+r'\b', new, text)
        out['files'][filename] = text
    oldtop = out['top']
    top = f'genefer_stream27_host_contexts_aw{g["aw"]}_p16_storage_combo_boundary_v1'
    host = out['files'].pop(oldtop+'.sv')
    host = once(host, 'module '+oldtop+' #', 'module '+top+' #')
    host = once(host, ',CONTEXTS=2', ',CONTEXTS=2,BOUNDARY_INPUTREG=1')
    old_second = int(re.search(r'CONTEXT_OFFSET=\d+,SECOND_CORRECTION=(\d+)', host)[1])
    second = next(c['accept'] for c in plan['correction'] if c['tag'][0] == 1 and c['tag'][3] == 0)
    host = once(host, f'CONTEXT_OFFSET={before["warm_interval"]//2},SECOND_CORRECTION={old_second}',
                f'CONTEXT_OFFSET={g["warm_interval"]//2},SECOND_CORRECTION={second}')
    out['files'][top+'.sv'] = host
    out['files'][Path(LEAF).name] = (ROOT/LEAF).read_text()
    out.update(top=top, geometry=g, two_context_schedule=plan,
               parameters=dict(out['parameters'], BOUNDARY_INPUTREG=1))
    out['source_dependencies'] = list(dict.fromkeys(out['source_dependencies']+[SELF, LEAF,
        'reference/s4_two_context_model_v1.py']))
    out['source_sha256'] = {path: sha((ROOT/path).read_bytes()) for path in out['source_dependencies']}
    out['rtl_sources'] = list(out['files'])
    out['generated_sha256'] = {name: sha(text) for name, text in out['files'].items()}
    out['context_storage_combo_boundary'] = dict(parent_top=oldtop,
        parent_generated_sha256=parent['generated_sha256'], roster=['BOUNDARY_INPUTREG'],
        parent_roster=parent['context_storage_combo']['roster'], calendar_before=before,
        boundary_latency_before=4, boundary_latency_after=5, correction_cache_added=1,
        counted_frontend_added=g['boundary_frontend_added'], second_cold_correction_accept=second,
        full27_boundary_owner=True, sticky_controller_and_global_authority_edges_unchanged=True,
        accepted_origin_tail_preserved=True, commit_publication_barriers_unchanged=True,
        no_lean_replicas_finalGS_or_other_flags=True, native_qualified=False,
        physical_gain_claim=False, clock_claim=False, promotion_allowed=False)
    return out


def prepare(n=256, *, p=16, contexts=2, enabled=0):
    return bind(combo.prepare(n, p=p, contexts=contexts, enabled=1), enabled=enabled)
