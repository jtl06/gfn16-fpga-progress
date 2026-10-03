"""R8: exact signed33 canonical c0 interval on immutable R7.

Default OFF is the frozen R7 graph. Enabled removes the base-minus-one
expression from the live BEGIN bound without changing c1, priority, state,
registers, owners, load/read controls or any calendar. Binary equivalence
holds for all unsigned32 bases and signed32 c0 values, including base zero.
No unknown-input, native, clock or area benefit is asserted here.
"""
import copy

from . import stream27_context_storage_combo_faultlocal_bind as faultlocal
from . import stream27_canonical_begin_bound_model as model

ROOT = faultlocal.ROOT
SELF = 'reference/stream27_context_storage_combo_directbound_bind.py'
MODEL = 'reference/stream27_canonical_begin_bound_model.py'
PARENT_PIN = '847dc928e3c84e565d8971fbd05e65ff2e3d50627e0d8b8347ff2ae025918d06'
OLD = 'genefer_stream27_canonical_image_loadlocal_v1'
NEW = 'genefer_stream27_canonical_image_directbound_v1'
LEAF_PIN = 'b8d0806344a737ce019a677f49f325442afecd1c388771bb009d5107dd525a6f'
sha = faultlocal.sha
once = faultlocal.once
CHANGES = [
    ('logic signed [32:0] bound_c0,input_c0,input_c1;',
     'logic signed [32:0] direct_base_c0,input_c0,input_c1;'),
    ("bound_c0=$signed({1'b0,base})-33'sd1;",
     "direct_base_c0=$signed({1'b0,base});"),
    ('if(input_c0>bound_c0 || input_c0< -bound_c0 ||',
     'if(input_c0>=direct_base_c0 || input_c0<= -direct_base_c0 ||'),
]


def need(ok, label):
    if not ok:
        raise ValueError('C2_COMBO_DIRECTBOUND_' + label)


def reverse_leaf(text):
    text = once(text, 'module '+NEW+' #', 'module '+OLD+' #')
    for before, after in reversed(CHANGES):
        text = once(text, after, before)
    return text


def reverse_host(text, *, top, parent_top):
    text = once(text, 'module '+top+' #', 'module '+parent_top+' #')
    text = once(text, ' '+NEW+' #', ' '+OLD+' #')
    return once(text, ',COMM_OWNER_COMPARE_LOCAL=1,CANONICAL_C0_DIRECT=1',
                ',COMM_OWNER_COMPARE_LOCAL=1')


def bind(bundle, *, enabled=0):
    need(type(enabled) is int and enabled in (0, 1), 'BOOLEAN_SWITCH')
    out = copy.deepcopy(bundle)
    if not enabled:
        return out
    need(sha((ROOT/faultlocal.SELF).read_bytes()) == PARENT_PIN, 'IMMUTABLE_R7')
    parent = faultlocal.prepare(out['geometry']['n'], enabled=1)
    need(out == parent, 'EXACT_R7_ONLY_NO_OTHER_FLAGS')
    proof = model.prove()
    original = out['files'].pop(OLD+'.sv')
    need(sha(original) == LEAF_PIN, 'EXACT_CANONICAL_PARENT')
    leaf = original
    for before, after in CHANGES:
        leaf = once(leaf, before, after)
    leaf = once(leaf, 'module '+OLD+' #', 'module '+NEW+' #')
    need(reverse_leaf(leaf) == original, 'EVERY_CANONICAL_BYTE_REVERSE')
    oldtop = out['top']
    top = f'genefer_stream27_host_contexts_aw{out["geometry"]["aw"]}_p16_storage_combo_directbound_v1'
    original_host = out['files'].pop(oldtop+'.sv')
    need(original_host.count(' '+OLD+' #') == 1 and
         sum(text.count(' '+OLD+' #') for text in out['files'].values()) == 0,
         'ONE_SHARED_SCRATCH_CALLER')
    host = once(original_host, ' '+OLD+' #', ' '+NEW+' #')
    host = once(host, 'module '+oldtop+' #', 'module '+top+' #')
    host = once(host, ',COMM_OWNER_COMPARE_LOCAL=1',
                ',COMM_OWNER_COMPARE_LOCAL=1,CANONICAL_C0_DIRECT=1')
    need(reverse_host(host, top=top, parent_top=oldtop) == original_host,
         'ALL_HOST_ONESHOT_OWNER_PUBLICATION_BYTES_REVERSE')
    out['files'][NEW+'.sv'] = leaf
    out['files'][top+'.sv'] = host
    out.update(top=top, parameters=dict(out['parameters'], CANONICAL_C0_DIRECT=1))
    out['source_dependencies'] = list(dict.fromkeys(out['source_dependencies']+[MODEL, SELF]))
    out['source_sha256'] = {path: sha((ROOT/path).read_bytes()) for path in out['source_dependencies']}
    out['rtl_sources'] = list(out['files'])
    out['generated_sha256'] = {name: sha(text) for name, text in out['files'].items()}
    out['context_storage_combo_directbound'] = dict(parent_top=oldtop,
        parent_generated_sha256=parent['generated_sha256'], roster=['CANONICAL_C0_DIRECT'],
        model=proof, reverse_to_parent_exact=True, signed_bound_width=33,
        full_unsigned_base_width=32, full_signed_c0_width=32,
        c1_live_inputs_fault_priority_load_read_reset_FFs_unchanged=True,
        full_owner_oneshot_and_publication_unchanged=True, calendar_delta=0,
        no_new_registers_or_delayed_faults=True, native_qualified=False,
        physical_gain_claim=False, clock_claim=False, promotion_allowed=False)
    return out


def prepare(n=256, *, p=16, contexts=2, enabled=0):
    return bind(faultlocal.prepare(n, p=p, contexts=contexts, enabled=1), enabled=enabled)
