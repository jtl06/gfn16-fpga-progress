"""R95 R3: same-edge transform-local quarantine replicas on frozen R2.

The routed controller_error -> inverse stop -> row-slot/protocol -> global
error path motivates a locality/fanout experiment, not a new authority edge.
Only two copies of each field's exact sticky setter drive CT/GS quarantine.
The public setter, pending diagnostics, full owners and calendars stay exact.
The instance is deliberately after all its input declarations (Quartus).
"""
import copy
import hashlib
import re
from pathlib import Path

from . import stream27_context_storage_combo_boundary_bind as boundary
from . import stream27_fault_fanout_bind as fault

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_context_storage_combo_quarantine_bind.py'
PARENT_PIN = '0540d53c0bfce872f6aec87d71e16daa368984a5f3b2df5bd288441754d31bab'
FAULT_HELPER_PIN = '1fa948689c5c8f785f871160477eec176b53faa70b38a288d10f8c435fc52bca'
LEAF_PIN = '9fc57a202e70c7894d05e29a9de09f44bcf97bb410d783d432cd9aa5ea342a9f'
DECL = ' wire [1:0] transform_quarantine;\n'
ANCHOR = ' wire inverse_error,inverse_pending;\n'
INSTANCE = fault.INSERT.replace(' wire [1:0] transform_quarantine;\n', '')


def need(ok, label):
    if not ok:
        raise ValueError('C2_COMBO_QUARANTINE_' + label)


def sha(raw):
    return hashlib.sha256(raw if isinstance(raw, bytes) else raw.encode()).hexdigest()


def reverse_field(text, old, new):
    """Restore every original field byte, including original public authority."""
    for part in (DECL, INSTANCE, fault.ASSERT):
        need(text.count(part) == 1, 'REVERSE_INSERT')
        text = text.replace(part, '', 1)
    for index, name in enumerate(('forward_transform', 'inverse_transform')):
        text = fault.connect_transform(text, name,
            f'.quarantine(transform_quarantine[{index}])', '.quarantine(stop)')
    text = boundary.once(text, 'module ' + new + ' #', 'module ' + old + ' #')
    for part in (',QUARANTINE_REPLICAS=1', ' || QUARANTINE_REPLICAS!=1'):
        need(text.count(part) == 1, 'REVERSE_PARAMETER')
        text = text.replace(part, '', 1)
    return text


def bind(bundle, *, enabled=0):
    need(type(enabled) is int and enabled in (0, 1), 'BOOLEAN_SWITCH')
    out = copy.deepcopy(bundle)
    if not enabled:
        return out
    for path, pin in ((boundary.SELF, PARENT_PIN),
                      (fault.SELF, FAULT_HELPER_PIN), (fault.LEAF, LEAF_PIN)):
        need(sha((ROOT/path).read_bytes()) == pin, 'IMMUTABLE_SOURCE:' + path)
    n = out['geometry']['n']
    parent = boundary.prepare(n, enabled=1)
    need(out == parent, 'EXACT_R2_ONLY_NO_OTHER_FLAGS')
    renames = {}
    for filename in list(out['files']):
        if not filename.startswith('genefer_stream27_shared_warm_'):
            continue
        original = out['files'].pop(filename)
        old = filename[:-3]
        field = re.search(r'_f([012])_', old)[1]
        new = f'genefer_stream27_shared_warm_aw{out["geometry"]["aw"]}_p16_f{field}_storage_combo_quarantine_v1'
        need(original.count('if(' + fault.SETTER + ')') == 1 and
             original.count('controller_error<=0;') == 1 and
             original.count('controller_error<=1;') == 1 and
             original.count('assign out_error=controller_error;') == 1,
             'EXACT_ORIGINAL_PUBLIC_SETTER')
        text = boundary.once(original, fault.DECL, fault.DECL + DECL)
        # Declare-only forward use is harmless; no replica port is elaborated
        # until all nine child errors and protocol/inverse signals are typed.
        text = boundary.once(text, ANCHOR, ANCHOR + INSTANCE)
        for name in ('child_error,child_pending;', 'admission_bad,join_bad;',
                     'protocol_error,protocol_pending;', 'inverse_error,inverse_pending;'):
            need(text.index(name) < text.index(' fault_replicas ('), 'INPUT_DECLARATION_ORDER:' + name)
        for index, name in enumerate(('forward_transform', 'inverse_transform')):
            text = fault.connect_transform(text, name, '.quarantine(stop)',
                                           f'.quarantine(transform_quarantine[{index}])')
        text = boundary.once(text, 'endmodule\n', fault.ASSERT + 'endmodule\n')
        text = boundary.once(text, 'module ' + old + ' #', 'module ' + new + ' #')
        text = boundary.once(text, ',CONTEXTS=2', ',CONTEXTS=2,QUARANTINE_REPLICAS=1')
        text = boundary.once(text, 'CONTEXTS!=2', 'CONTEXTS!=2 || QUARANTINE_REPLICAS!=1')
        need(reverse_field(text, old, new) == original, 'EVERY_FIELD_BYTE_REVERSE')
        out['files'][new+'.sv'] = text
        renames[old] = new
    need(len(renames) == 3, 'ALL_THREE_FIELDS')
    for filename, text in list(out['files'].items()):
        for old, new in renames.items():
            text = re.sub(r'\b'+re.escape(old)+r'\b', new, text)
        out['files'][filename] = text
    oldtop = out['top']
    top = f'genefer_stream27_host_contexts_aw{out["geometry"]["aw"]}_p16_storage_combo_quarantine_v1'
    host = out['files'].pop(oldtop+'.sv')
    host = boundary.once(host, 'module '+oldtop+' #', 'module '+top+' #')
    host = boundary.once(host, ',CONTEXTS=2', ',CONTEXTS=2,QUARANTINE_REPLICAS=1')
    restored = host.replace('module '+top+' #', 'module '+oldtop+' #', 1)
    need(restored.replace(',QUARANTINE_REPLICAS=1', '', 1) == parent['files'][oldtop+'.sv'],
         'HOST_EVERY_FUNCTIONAL_BYTE_UNCHANGED')
    out['files'][top+'.sv'] = host
    out['files'][Path(fault.LEAF).name] = (ROOT/fault.LEAF).read_text()
    out.update(top=top, parameters=dict(out['parameters'], QUARANTINE_REPLICAS=1))
    out['source_dependencies'] = list(dict.fromkeys(out['source_dependencies'] +
        [SELF, fault.SELF, fault.LEAF]))
    out['source_sha256'] = {path: sha((ROOT/path).read_bytes()) for path in out['source_dependencies']}
    out['rtl_sources'] = list(out['files'])
    out['generated_sha256'] = {name: sha(text) for name, text in out['files'].items()}
    out['context_storage_combo_quarantine'] = dict(parent_top=oldtop,
        parent_generated_sha256=parent['generated_sha256'], roster=['QUARANTINE_REPLICAS'],
        copies_per_field=2, total_sticky_copies=6, setter=fault.SETTER,
        destinations=['forward_transform', 'inverse_transform'],
        all_inputs_declared_before_instance=True, same_origin_edge=True,
        public_fault_and_pending_unchanged=True, full_owner_checks_unchanged=True,
        commit_publication_barriers_unchanged=True, calendar_unchanged=True,
        accepted_origin_tail_preserved=True, reverse_to_parent_exact=True,
        native_qualified=False, physical_gain_claim=False, clock_claim=False,
        promotion_allowed=False)
    return out


def prepare(n=256, *, p=16, contexts=2, enabled=0):
    return bind(boundary.prepare(n, p=p, contexts=contexts, enabled=1), enabled=enabled)
