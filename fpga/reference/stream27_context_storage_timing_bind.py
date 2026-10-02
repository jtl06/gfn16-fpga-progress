"""Private clean timing58 + two physical context payload banks.

Captured AW8/full only. Four logical leases and full owners stay intact;
qualified product_slot authority is distinct from raw bypass_data selection.
Default zero is exact. This does not compose compact tags, GEN or MLAB.
"""
import copy
import hashlib
import json
from pathlib import Path

from . import stream27_context_storage_banks_bind as transform
from . import stream27_c2_state_analysis as lifetime

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_context_storage_timing_bind.py'
TRANSFORM_PIN = '0410e782a72be901e523d3ab989c89bafc14ba52d0f5802c0103f197fe7101be'
MODEL_PIN = '55b6909a9b264b1da46facabcc096a95a19600929c69945387e88eb48db4a157'
TERM = 'genefer_stream27_term_context_param_v1_contexts_v1_select_token_v1'
TERM_PIN = '192a8940d81738e45a4c11e745d3d964816b4ed434ad4c2bc1aa598f076dc733'
MAP_PINS = {256: '1d649ce99802fe68ba15183d883d92f5ed9551140271ad07f7d42aa71e3a9c34',
            65536: '83c8268db2dc7451f4292f5372f0bcdb6179deb5990659340c6cda6ab309d85d'}
CALENDARS = {
    256: dict(warm_interval=214, pointwise_accept=79, rows=16,
              next_correction_accept=214, last_sink=168, correction_cache_latency=78,
              feedback_delay=18, second_correction=107),
    65536: dict(warm_interval=8460, pointwise_accept=4207, rows=4096,
                next_correction_accept=12558, last_sink=12512, correction_cache_latency=78,
                feedback_delay=0, second_correction=8232)}


def sha(raw):
    return hashlib.sha256(raw if isinstance(raw, bytes) else raw.encode()).hexdigest()


def need(ok, name):
    if not ok:
        raise ValueError('C2_TIMING_STORAGE2_' + name)


def proof(geometry, counts=(16, 16), anchor=0):
    n = geometry.get('n')
    need(n in CALENDARS, 'SUPPORTED_GEOMETRY')
    c = CALENDARS[n]
    need(all(geometry.get(k) == v for k, v in c.items() if k != 'second_correction'), 'EXACT_CALENDAR')
    windows = lifetime.windows(counts, anchor=anchor, interval=c['warm_interval'],
        pointwise=c['pointwise_accept'], rows=c['rows'],
        next_correction=c['next_correction_accept'], second_correction=c['second_correction'])
    gap = lifetime.check_windows(windows)
    logical = lifetime.logical_peak(windows, release_offset=c['last_sink'])
    return dict(physical_banks=2, logical_leases=4, windows=windows, minimum_gap=gap,
        logical_peak=logical['peak'], last_coefficient_read=c['pointwise_accept'] + c['rows'] - 1,
        last_E4_product_write=c['pointwise_accept'] + c['rows'] - 1,
        conservative_retirement=c['pointwise_accept'] + c['rows'],
        no_sameedge_reuse=True, full_owner_bits=27, reset_revokes_validity=True,
        cancel_retains_raw_drain=True, epoch_wrap_requires_full_tuple=True)


def leaf(text):
    need(sha(text) == TERM_PIN, 'TERM_PIN')
    new = TERM + '_storage2_v1'
    text = transform.once(text, 'module ' + TERM + ' #', 'module ' + new + ' #')
    for old, replacement in (
        ('context_data[0:3][0:3]', 'context_data[0:1][0:3]'),
        ('context_row[0:3][0:3]', 'context_row[0:1][0:3]'),
        ('context_valid[0:3]', 'context_valid[0:1]'),
        ('bank_owner[0:3]', 'bank_owner[0:1]'),
        ('wire [1:0] pw_bank=pointwise_owner[26:25],prod_bank=product_owner[26:25],seed_bank=seed_owner[26:25];',
         'wire pw_bank=pointwise_owner[24],prod_bank=product_owner[24],seed_bank=seed_owner[24];'),
        ('for(int bank=0;bank<4;bank=bank+1)context_valid[bank]',
         'for(int bank=0;bank<2;bank=bank+1)context_valid[bank]')):
        text = transform.once(text, old, replacement)
    # Do not substitute data_select_slot for any write/cache/fault authority.
    for anchor in ('if(bypass_data)current_term=product_data;',
                   "if(bypass)consumer_missing=1'b0;",
                   'if(product_slot && bank_owner[prod_bank]==product_owner)begin',
                   'assign cache_ready=product_slot &&',
                   'bypass_data!=bypass'):
        need(anchor in text, 'QUALIFIED_AUTHORITY:' + anchor)
    return new, text


def field(name, text):
    # Identifier-only temporary adaptation invokes the already pinned private
    # transform. The raw/qualified timing term logic is not rewritten by it.
    need(text.count(TERM + ' #') == 1, 'TERM_CALLER')
    text = transform.re_identifier(text, TERM, transform.TERM)
    new, text = transform.field(name, text)
    text = transform.re_identifier(text, transform.TERM + '_storage2_v1', TERM + '_storage2_v1')
    return new, text


def bind(bundle, *, enabled=0):
    need(type(enabled) is int and enabled in (0, 1), 'BOOL_FLAG')
    result = copy.deepcopy(bundle)
    if not enabled:
        return result
    need(sha((ROOT / transform.SELF).read_bytes()) == TRANSFORM_PIN, 'FROZEN_TRANSFORM')
    need(sha((ROOT / 'reference/stream27_c2_state_analysis.py').read_bytes()) == MODEL_PIN, 'FROZEN_MODEL')
    g = result['geometry']; n = g.get('n')
    need(n in CALENDARS and g.get('p') == 16 and g.get('contexts') == 2 and
         g.get('lease_banks') == 4 and g.get('corr_serial_bfs') == 2, 'CLOSED_HOST')
    p = result['parameters']
    need(p.get('MONT_FACTORED') == 1 and p.get('COLD_LAUNCH_FENCE') == 1 and
         p.get('TERM_SELECT_TOKEN') == 1 and not p.get('COMM_TAG_COMPACT', 0), 'CLEAN_TIMING_PARENT')
    files = result['files']; original = dict(files)
    actual = {name: sha(text) for name, text in files.items()}
    need(len(files) == 58 and sha(json.dumps(actual, sort_keys=True, separators=(',', ':'))) == MAP_PINS[n], 'CAPTURED58_MAP')
    host = files[result['top'] + '.sv']
    c = CALENDARS[n]
    need('CONTEXT_OFFSET=' + str(c['warm_interval']//2) + ',SECOND_CORRECTION=' + str(c['second_correction']) + ';' in host,
         'HOST_CORRECTION_ANCHORS')
    witness = proof(g)
    renames = {}
    new, text = leaf(files.pop(TERM + '.sv'))
    files[new + '.sv'] = text
    renames[TERM] = new
    aw = g['aw']
    for f in range(3):
        matches = [name for name in files if name == f'genefer_stream27_shared_warm_aw{aw}_p16_f{f}_v1_timing_c2_v1.sv']
        need(len(matches) == 1, 'THREE_FIELDS')
        old = matches[0][:-3]
        new, text = field(old, files.pop(matches[0]))
        files[new + '.sv'] = text; renames[old] = new
    for filename, text in list(files.items()):
        for old, new in renames.items():
            text = transform.re_identifier(text, old, new)
        files[filename] = text
    oldtop = result['top']; newtop = oldtop + '_storage2_v1'
    files[newtop + '.sv'] = transform.once(files.pop(oldtop + '.sv'), 'module ' + oldtop + ' #', 'module ' + newtop + ' #')
    renames[oldtop] = newtop
    changed = []
    for old, text in original.items():
        new = renames.get(old[:-3], old[:-3]) + '.sv'
        if files[new] != text:
            changed.append(dict(parent=old, candidate=new, parent_sha256=sha(text), candidate_sha256=sha(files[new])))
    need(len(changed) == 6 and len(files) == 58, 'SIX_NAMESPACE_DELTA')
    result.update(top=newtop, rtl_sources=list(files), generated_sha256={name: sha(text) for name, text in files.items()})
    deps = (transform.SELF, 'reference/stream27_c2_state_analysis.py', SELF)
    result['source_dependencies'] = list(dict.fromkeys(result.get('source_dependencies', []) + list(deps)))
    result['source_sha256'] = dict(result.get('source_sha256', {}), **{name: sha((ROOT/name).read_bytes()) for name in deps})
    result['storage_contract'] = dict(physical_banks=2, logical_leases=4, full_owner_bits=27,
        clean_timing_parent=True, compact_GEN_MLAB=False, closed_host_only=True,
        changed=changed, unchanged=52, geometry=c, lifetime=witness,
        native_qualified=False, measured_area_saving=None, wholefit_released=False)
    return result
