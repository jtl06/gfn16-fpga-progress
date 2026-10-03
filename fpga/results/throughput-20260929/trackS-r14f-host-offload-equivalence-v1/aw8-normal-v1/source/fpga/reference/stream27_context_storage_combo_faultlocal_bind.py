"""R7: compare full packed-commutator tags before the late phase selector.

Default OFF is the immutable R6 graph. Enabled changes one combinational
predicate and identifier-only callers. Data/tag routing, every register,
fault authority, reset, occupied canceled tails and calendars are literal.
Known-two-state Boolean equivalence is proved separately; unknown-input
equivalence or a physical timing/area benefit is not asserted.
"""
import copy

from . import stream27_context_storage_combo_oneshot_bind as oneshot
from . import stream27_fault_feedback_factoring_model as model

ROOT = oneshot.ROOT
SELF = 'reference/stream27_context_storage_combo_faultlocal_bind.py'
MODEL = 'reference/stream27_fault_feedback_factoring_model.py'
PARENT_PIN = '586117feeb61f81e6049d8bba942e843048b2d792f90ba612ebffd76da401810'
OLD = 'genefer_stream27_mdc_commutator_shared_packed_v1'
NEW = 'genefer_stream27_mdc_commutator_shared_packed_faultlocal_v1'
LEAF_PIN = '30b2ce81f3bff93dc40da9e3d3d15a741c0aeba779f5e1e7e392c5d4c3f2e366'
sha = oneshot.sha
once = oneshot.once
DECL_BEFORE = ' logic malformed,phase,advance,owner_bad,eligible;\n'
DECL_AFTER = DECL_BEFORE + ' logic pair_bad_current,pair_bad_delayed;\n'
COMPARE_BEFORE = '''  owner_bad=(head_upper_tag.valid!=result_lower_tag.valid) ||
   (head_upper_tag.valid && ((head_upper_tag.owner!=result_lower_tag.owner) ||
    (head_upper_tag.generation!=result_lower_tag.generation))) ||
   (head_upper_tag.valid && output_offset!='0 &&
    ((head_upper_tag.owner!=output_owner)||(head_upper_tag.generation!=output_generation)));
'''
COMPARE_AFTER = '''  // Full comparisons settle before phase selects a single mismatch bit.
  // Original packed payload/tag routing and continuity authority stay exact.
  pair_bad_current=(head_upper_tag.valid!=input_tag.valid) ||
   (head_upper_tag.valid && ((head_upper_tag.owner!=input_tag.owner) ||
    (head_upper_tag.generation!=input_tag.generation)));
  pair_bad_delayed=(head_upper_tag.valid!=head_lower_tag.valid) ||
   (head_upper_tag.valid && ((head_upper_tag.owner!=head_lower_tag.owner) ||
    (head_upper_tag.generation!=head_lower_tag.generation)));
  owner_bad=(phase?pair_bad_current:pair_bad_delayed) ||
   (head_upper_tag.valid && output_offset!='0 &&
    ((head_upper_tag.owner!=output_owner)||(head_upper_tag.generation!=output_generation)));
'''


def need(ok, label):
    if not ok:
        raise ValueError('C2_COMBO_FAULTLOCAL_' + label)


def reverse_leaf(text):
    text = once(text, 'module '+NEW+' #', 'module '+OLD+' #')
    text = once(text, COMPARE_AFTER, COMPARE_BEFORE)
    return once(text, DECL_AFTER, DECL_BEFORE)


def reverse_host(text, *, top, parent_top):
    text = once(text, 'module '+top+' #', 'module '+parent_top+' #')
    return once(text, ',COLD_SECOND_ONESHOT=1,COMM_OWNER_COMPARE_LOCAL=1',
                ',COLD_SECOND_ONESHOT=1')


def bind(bundle, *, enabled=0):
    need(type(enabled) is int and enabled in (0, 1), 'BOOLEAN_SWITCH')
    out = copy.deepcopy(bundle)
    if not enabled:
        return out
    need(sha((ROOT/oneshot.SELF).read_bytes()) == PARENT_PIN, 'IMMUTABLE_R6')
    parent = oneshot.prepare(out['geometry']['n'], enabled=1)
    need(out == parent, 'EXACT_R6_ONLY_NO_OTHER_FLAGS')
    proof = model.prove()
    original = out['files'].pop(OLD+'.sv')
    need(sha(original) == LEAF_PIN, 'EXACT_PACKED_COMM_PARENT')
    leaf = once(original, DECL_BEFORE, DECL_AFTER)
    leaf = once(leaf, COMPARE_BEFORE, COMPARE_AFTER)
    leaf = once(leaf, 'module '+OLD+' #', 'module '+NEW+' #')
    need(reverse_leaf(leaf) == original, 'EVERY_LEAF_BYTE_REVERSE')
    changed = []
    counts = []
    for name, text in list(out['files'].items()):
        count = text.count(OLD+' #')
        if not count:
            continue
        need(('_merged_ct_' in name or '_merged_gs_' in name) and count > 0,
             'ONLY_SIX_CT_GS_CALLERS')
        updated = text.replace(OLD+' #', NEW+' #')
        need(updated.replace(NEW+' #', OLD+' #') == text, 'CALLER_IDENTIFIER_REVERSE')
        out['files'][name] = updated
        changed.append(name)
        counts.append(count)
    stages = out['geometry']['aw']-4
    need(len(changed) == 6 and counts == [stages]*6, 'EVERY_STAGE_CALLER_BOUND')
    oldtop = out['top']
    top = f'genefer_stream27_host_contexts_aw{out["geometry"]["aw"]}_p16_storage_combo_faultlocal_v1'
    original_host = out['files'].pop(oldtop+'.sv')
    host = once(original_host, 'module '+oldtop+' #', 'module '+top+' #')
    host = once(host, ',COLD_SECOND_ONESHOT=1',
                ',COLD_SECOND_ONESHOT=1,COMM_OWNER_COMPARE_LOCAL=1')
    need(reverse_host(host, top=top, parent_top=oldtop) == original_host,
         'ALL_HOST_ONESHOT_OWNER_PUBLICATION_BYTES_REVERSE')
    out['files'][NEW+'.sv'] = leaf
    out['files'][top+'.sv'] = host
    out.update(top=top, parameters=dict(out['parameters'], COMM_OWNER_COMPARE_LOCAL=1))
    out['source_dependencies'] = list(dict.fromkeys(out['source_dependencies']+[MODEL, SELF]))
    out['source_sha256'] = {path: sha((ROOT/path).read_bytes()) for path in out['source_dependencies']}
    out['rtl_sources'] = list(out['files'])
    out['generated_sha256'] = {name: sha(text) for name, text in out['files'].items()}
    out['context_storage_combo_faultlocal'] = dict(parent_top=oldtop,
        parent_generated_sha256=parent['generated_sha256'], roster=['COMM_OWNER_COMPARE_LOCAL'],
        model=proof, reverse_to_parent_exact=True, caller_identifier_only=changed,
        stage_instances=sum(counts), comparison_full_valid_owner_generation=True,
        data_and_tag_routing_unchanged=True, all_register_reset_fault_publication_edges_exact=True,
        calendar_delta=0, no_new_registers_or_delayed_faults=True,
        no_unknown_input_equivalence_claim=True, comparator_area_tradeoff_unmeasured=True,
        native_qualified=False, physical_gain_claim=False, clock_claim=False, promotion_allowed=False)
    return out


def prepare(n=256, *, p=16, contexts=2, enabled=0):
    return bind(oneshot.prepare(n, p=p, contexts=contexts, enabled=1), enabled=enabled)
