"""Selected C2 timing+storage source-order qualification successor.

Only the identical fault_replicas instance moves below its last input
declaration. No names, expressions, registers, public edges or calendars change.
Disabled is an exact deep copy; enabled accepts the two frozen selected captures.
This removes a source ambiguity, not proof that the prior Quartus netlist differs.
"""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_context_fault_order_bind.py'
BASE = 'results/throughput-20260929/trackS-c2-timing-storage2-v1'
CAPTURES = {
    256: ('aw8-normal', 'c32f5d91dcc21e713ba71ecf28674ca52dc4e3f122ca25c5975762dde0be9433'),
    65536: ('full-normal', '5d87ce1c84a00e4b9f93c5a222f551bdbfc3c62647080c82dbc55351250547f7')}
SETTER = '!stop && (admission_bad || join_bad || (|child_pending) || (|child_error) || inverse_pending || inverse_error || protocol_pending || protocol_error)'
INSTANCE = (' genefer_stream27_quarantine_replicas_v1 #(.COPIES(2)) fault_replicas (\n'
            '  .clk,.rst_n,.fault_set(' + SETTER + '),.quarantine(transform_quarantine));\n')
EARLY = ' wire [1:0] transform_quarantine;\n'
LATE = ' wire inverse_error,inverse_pending;\n'
DECLARATIONS = (' logic controller_error;\n', ' wire stop=controller_error;\n', EARLY,
                ' logic [8:0] child_error,child_pending;\n',
                ' logic admission_bad,join_bad;\n',
                ' wire protocol_error,protocol_pending;\n', LATE)


def need(ok, label):
    if not ok:
        raise ValueError('C2_FAULT_ORDER_' + label)


def sha(raw):
    return hashlib.sha256(raw if isinstance(raw, bytes) else raw.encode()).hexdigest()


def source_map(files):
    return {name: sha(text) for name, text in files.items()}


def map_pin(files):
    return sha(json.dumps(source_map(files), sort_keys=True, separators=(',', ':')))


def reverse_root(text):
    """Literal inverse; no parser-equivalence assumption or expression rewrite."""
    need(text.count(LATE + INSTANCE) == 1, 'REVERSE_LATE_ANCHOR')
    text = text.replace(LATE + INSTANCE, LATE, 1)
    need(text.count(EARLY) == 1, 'REVERSE_EARLY_ANCHOR')
    return text.replace(EARLY, EARLY + INSTANCE, 1)


def reorder(text):
    need(text.count(EARLY + INSTANCE) == 1 and text.count(LATE) == 1, 'EXACT_PARENT_INSTANCE')
    need(text.count('if(' + SETTER + ')') == 1, 'ORIGINAL_CONTROLLER_SETTER')
    need(text.index(EARLY + INSTANCE) < text.index(LATE), 'ORIGINAL_ORDER')
    result = text.replace(INSTANCE, '', 1).replace(LATE, LATE + INSTANCE, 1)
    position = result.index(INSTANCE)
    for declaration in DECLARATIONS:
        need(result.count(declaration) == 1 and result.index(declaration) < position,
             'INPUT_DECLARED:' + declaration.strip())
    need(reverse_root(result) == text, 'LITERAL_REVERSE')
    return result


def bind(bundle, *, enabled=0):
    need(type(enabled) is int and enabled in (0, 1), 'BOOLEAN_FLAG')
    result = copy.deepcopy(bundle)
    if not enabled:
        return result
    geometry = result['geometry']; n = geometry.get('n')
    need(n in CAPTURES and geometry.get('p') == 16 and geometry.get('contexts') == 2,
         'SELECTED_TWO_CONTEXT_SOURCE')
    files = result['files']
    parent_pin = map_pin(files)
    need(len(files) == 58 and parent_pin == CAPTURES[n][1], 'EXACT_SELECTED58')
    need(result.get('generated_sha256') == source_map(files), 'SOURCE_MAP_JOIN')
    need(result.get('storage_contract', {}).get('clean_timing_parent') is True and
         result['storage_contract'].get('compact_GEN_MLAB') is False, 'UNMIXED_STORAGE_PARENT')
    changed = []
    for field in range(3):
        name = (f'genefer_stream27_shared_warm_aw{geometry["aw"]}_p16_f{field}'
                '_v1_timing_c2_v1_storage2_v1.sv')
        need(name in files, 'ALL_THREE_FIELDS')
        original = files[name]
        files[name] = reorder(original)
        changed.append(dict(name=name, parent_sha256=sha(original), candidate_sha256=sha(files[name])))
    need(sum(files[name] != bundle['files'][name] for name in files) == 3, 'THREE_MOVES_ONLY')
    need(result['geometry'] == bundle['geometry'] and result['parameters'] == bundle['parameters']
         and result['top'] == bundle['top'], 'UNCHANGED_CALENDAR_ABI_TOP')
    result['generated_sha256'] = source_map(files)
    result['source_dependencies'] = list(dict.fromkeys(result.get('source_dependencies', []) + [SELF]))
    result['source_sha256'] = dict(result.get('source_sha256', {}), **{SELF: sha((ROOT / SELF).read_bytes())})
    result['fault_source_order'] = dict(schema='stream27-c2-fault-instance-order-v1',
        parent_map_sha256=parent_pin, changed=changed, unchanged_files=55,
        only_instance_location_changed=True, identifiers_unchanged=True,
        expressions_registers_reset_calendar_unchanged=True, reverse_exact=True,
        native_qualified=False, physical_fanin_qualified=False,
        prior_source_defect_claim=False, wholefit_released=False, promotion_allowed=False)
    return result


def prepare(n=256, *, enabled=0):
    need(n in CAPTURES, 'AW8_FULL_ONLY')
    stage, pin = CAPTURES[n]
    bundle = json.loads((ROOT / BASE / stage / 'production-bundle.json').read_text())
    need(map_pin(bundle['files']) == pin, 'IMMUTABLE_CAPTURE')
    return bind(bundle, enabled=enabled)
