"""R95 R5: exclusive canonical LOAD control on immutable read-local R4.

Actual R2 STA reaches RAM write-data through correction bound/negation,
comparison and shared idle_reject. A legal LOAD cannot inspect corrections:
that branch belongs to BEGIN. This isolates write eligibility with the exact
original load range/order/exclusivity predicates. Rejection priority/code,
numeric/RAM state, owners, read controls, reset and calendars remain literal.
No added FF/edge, unknown-input equivalence or physical benefit is claimed.
"""
import copy
import itertools

from . import stream27_context_storage_combo_readlocal_bind as readlocal

ROOT = readlocal.ROOT
SELF = 'reference/stream27_context_storage_combo_loadlocal_bind.py'
PARENT_PIN = '639b05599ba8294e3035ea66298ef216ec2382ca0e506fdb3df910691bd8470d'
OLD = readlocal.NEW
NEW = 'genefer_stream27_canonical_image_loadlocal_v1'
LEAF_PIN = '7df122a90324831c7b330c659c8ba98fbe17074d633f4abd40b89d231d164baa'
LOAD_BEFORE = '    wire legal_load=rst_n && state==IDLE && !error && !idle_reject && load_valid;\n'
ORDER_BAD = '''(loaded_count==(ROW_W+1)'(T) && load_row!=0) ||
                    (loaded_count!=(ROW_W+1)'(T) && (ROW_W+1)'(load_row)!=loaded_count)'''
LOAD_AFTER = '''    // Only exclusive LOAD controls RAM write payload/eligibility.
    // BEGIN correction bounds still feed original authoritative idle_reject.
    wire load_order_ok=!((''' + ORDER_BAD + '''));
    wire legal_load=rst_n && state==IDLE && !error && load_valid &&
        !begin_canonical && !read_req && !read_pending &&
        base_ok && !load_bad && load_order_ok;
'''


def need(ok, label):
    if not ok:
        raise ValueError('C2_COMBO_LOADLOCAL_' + label)


sha = readlocal.sha
once = readlocal.quarantine.boundary.once


def load_model(*values):
    idle, rst, error, image, pending, load, begin, read, base_ok, load_bad, correction_bad, raw_ready, order_bad = values
    reject = readlocal.read_model(*values)[-1]  # Literal old priority model.
    original = bool(rst and idle and not error and not reject and load)
    local = bool(rst and idle and not error and load and not begin and not read and
                 not pending and base_ok and not load_bad and not order_bad)
    return original, local, reject


def prove_loads():
    cases = eligible = 0
    for values in itertools.product((0, 1), repeat=13):
        old, new, _ = load_model(*values)
        need(old == new, 'ALL_BOOLEAN_PRIORITY_CASES')
        cases += 1
        eligible += old
    return dict(cases=cases, eligible_load_cases=eligible, no_unknown_input_equivalence_claim=True)


def reverse_leaf(text):
    text = once(text, 'module '+NEW+' #', 'module '+OLD+' #')
    return once(text, LOAD_AFTER, LOAD_BEFORE)


def bind(bundle, *, enabled=0):
    need(type(enabled) is int and enabled in (0, 1), 'BOOLEAN_SWITCH')
    out = copy.deepcopy(bundle)
    if not enabled:
        return out
    need(sha((ROOT/readlocal.SELF).read_bytes()) == PARENT_PIN, 'IMMUTABLE_R4')
    parent = readlocal.prepare(out['geometry']['n'], enabled=1)
    need(out == parent, 'EXACT_R4_ONLY_NO_OTHER_FLAGS')
    proof = prove_loads()
    original = out['files'].pop(OLD+'.sv')
    need(sha(original) == LEAF_PIN and original.count(ORDER_BAD) == 1, 'EXACT_CANONICAL_PARENT')
    text = once(original, LOAD_BEFORE, LOAD_AFTER)
    text = once(text, 'module '+OLD+' #', 'module '+NEW+' #')
    need(reverse_leaf(text) == original, 'EVERY_CANONICAL_BYTE_REVERSE')
    # The direct predicate has no raw-ready/c0/c1/correction_bad/idle_reject
    # dependency; existing base_ok/load_bad/order checks are still required.
    predicate = text[text.index('    wire legal_load='):text.index(';', text.index('    wire legal_load='))]
    need(not any(name in predicate for name in ('idle_reject', 'correction_bad', 'raw_ready', 'c0', 'c1')) and
         all(name in predicate for name in ('base_ok', 'load_bad', 'load_order_ok',
                                             'read_pending', 'begin_canonical', 'read_req')),
         'REACHABLE_LOAD_CONTROL_DEPENDENCIES')
    oldtop = out['top']
    top = f'genefer_stream27_host_contexts_aw{out["geometry"]["aw"]}_p16_storage_combo_loadlocal_v1'
    host = out['files'].pop(oldtop+'.sv')
    need(host.count(' '+OLD+' #') == 1 and sum(s.count(' '+OLD+' #') for s in out['files'].values()) == 0,
         'ONE_SHARED_SCRATCH_CALLER')
    host = once(host, ' '+OLD+' #', ' '+NEW+' #')
    host = once(host, 'module '+oldtop+' #', 'module '+top+' #')
    host = once(host, ',CONTEXTS=2', ',CONTEXTS=2,CANONICAL_LOAD_LOCAL=1')
    restored = host.replace(' '+NEW+' #', ' '+OLD+' #', 1).replace('module '+top+' #', 'module '+oldtop+' #', 1)
    need(restored.replace(',CANONICAL_LOAD_LOCAL=1', '', 1) == parent['files'][oldtop+'.sv'],
         'ALL_HOST_OWNER_ARBITRATION_BARRIERS_EXACT')
    out['files'][NEW+'.sv'] = text
    out['files'][top+'.sv'] = host
    out.update(top=top, parameters=dict(out['parameters'], CANONICAL_LOAD_LOCAL=1))
    out['source_dependencies'] = list(dict.fromkeys(out['source_dependencies']+[SELF]))
    out['source_sha256'] = {path: sha((ROOT/path).read_bytes()) for path in out['source_dependencies']}
    out['rtl_sources'] = list(out['files'])
    out['generated_sha256'] = {name: sha(text) for name, text in out['files'].items()}
    out['context_storage_combo_loadlocal'] = dict(parent_top=oldtop,
        parent_generated_sha256=parent['generated_sha256'], roster=['CANONICAL_LOAD_LOCAL'],
        model=proof, reverse_to_parent_exact=True, authoritative_fault_priority_unchanged=True,
        full_owner_and_context_routing_unchanged=True, read_controls_and_RAM_payload_unchanged=True,
        reset_and_accepted_origin_work_unchanged=True, calendar_delta=0,
        publication_barriers_unchanged=True, no_new_registers_or_delayed_faults=True,
        native_qualified=False, physical_gain_claim=False, clock_claim=False, promotion_allowed=False)
    return out


def prepare(n=256, *, p=16, contexts=2, enabled=0):
    return bind(readlocal.prepare(n, p=p, contexts=contexts, enabled=1), enabled=enabled)
