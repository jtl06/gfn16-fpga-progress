"""Additive P16 storage/co-retiming and payload-lookahead composition.

The default is the exact timing donor.  Frozen jobs and its private
non-field arithmetic stay untouched.  Field deltas never establish an
additive whole-area estimate, routing release or inherited clock.
"""
from copy import deepcopy
import hashlib
import re

from . import stream27_p16_timing_flags as donor
from . import stream27_comm_packed_bind as packed
from . import stream27_root_outputreg_bind as rootreg
from . import stream27_term_lookahead_p16_bind as lookahead

ROOT = donor.ROOT
SELF = 'reference/stream27_p16_area_timing_flags.py'


def need(ok, reason):
    if not ok:
        raise ValueError('S4_P16_AREA_' + reason)


def identifier(text, before, after):
    return re.sub(r'\b' + re.escape(before) + r'\b', after, text)


def check_flags(values):
    for key, value in values.items():
        need(type(value) is int and value in (0, 1), 'LITERAL_FLAG:' + key)


def close(bundle, parent, roster):
    need(bundle['geometry'] == parent['geometry'] and
         bundle['parameters'] == parent['parameters'], 'ZERO_PUBLIC_EDGE_PARAMETER_DELTA')
    bundle['source_dependencies'] = list(dict.fromkeys(bundle['source_dependencies'] + [SELF]))
    bundle['source_sha256'] = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in bundle['source_dependencies']}
    bundle['rtl_sources'] = [name for name in bundle['files'] if name.endswith('.sv')]
    bundle['generated_sha256'] = {
        name: hashlib.sha256(text.encode()).hexdigest()
        for name, text in bundle['files'].items()}
    bundle['area_timing_roster'] = dict(roster,
        parent_generated_sha256=parent['generated_sha256'],
        public_calendar_unchanged=True, native_qualification_inherited=False,
        whole_resource_GO=False, whole_clock_claim=False,
        root_M20K_output_FF_absorption_claim=False)
    return bundle


def bind_field(bundle, *, comm_delay_packed=0, root_weight_outputreg=0, term_lookahead=0):
    roster = dict(comm_delay_packed=comm_delay_packed,
                  root_weight_outputreg=root_weight_outputreg, term_lookahead=term_lookahead)
    check_flags(roster)
    if not any(roster.values()):
        return deepcopy(bundle)
    donor.check(bundle)
    result = deepcopy(bundle)
    if comm_delay_packed:
        result = packed.bind(result)
    if root_weight_outputreg:
        result = rootreg.bind(result)
    if term_lookahead:
        result = lookahead.bind(result)
    return close(result, bundle, roster)


def prepare_field(n=256, p=16, f=0, *, comm_delay_packed=0, root_weight_outputreg=0,
                  term_lookahead=0, **kwargs):
    return bind_field(donor.prepare_field(n, p, f, **kwargs),
        comm_delay_packed=comm_delay_packed, root_weight_outputreg=root_weight_outputreg,
        term_lookahead=term_lookahead)


def root_whole(bundle):
    """Bind the qualified field transform to actual private whole consumers.

    An identifier-only temporary field view avoids touching the original
    sparse/general Montgomery or lazy BF definitions retained for CRT/T5b.
    Only the selected field's CT/GS and root library return to the whole.
    """
    result = deepcopy(bundle)
    private_bf = bundle['diet_binding']['private_consumers'].get(rootreg.OLD_BF)
    need(private_bf is not None and private_bf + '.sv' in bundle['files'], 'PRIVATE_BF_CLOSURE')
    new_bf = rootreg.NEW_BF + '_p16_area_v1'
    contracts = []
    for field in range(3):
        view = deepcopy(bundle)
        view['parameters'] = dict(view['parameters'], FIELD=field)
        view['mode'] = 'warm_signed'
        # The root binder's count is one field, not three unrelated cohorts.
        view['files'] = {
            name: text for name, text in view['files'].items()
            if not ((name.startswith('genefer_stream28_merged_') or
                     name.startswith('merged_stream27_root_library_')) and
                    f'_f{field}_' not in name)}
        view['files'].pop(rootreg.OLD_BF + '.sv')
        view['files'][rootreg.OLD_BF + '.sv'] = view['files'].pop(private_bf + '.sv')
        view['files'] = {
            name: identifier(text, private_bf, rootreg.OLD_BF)
            for name, text in view['files'].items()}
        selected = rootreg.bind(view)
        for name in selected['root_weight_outputreg']['changes']:
            need(name in bundle['files'], 'ACTUAL_FIELD_FILE:' + name)
            restored_parent = identifier(view['files'][name], rootreg.OLD_BF, private_bf)
            need(restored_parent == bundle['files'][name], 'PRIVATE_IDENTIFIER_PARENT:' + name)
            text = identifier(selected['files'][name], rootreg.OLD_BF, private_bf)
            result['files'][name] = identifier(text, rootreg.NEW_BF, new_bf)
        text = identifier(selected['files'][rootreg.NEW_BF + '.sv'], rootreg.NEW_BF, new_bf)
        need(new_bf + '.sv' not in result['files'] or result['files'][new_bf + '.sv'] == text,
             'COMMON_PRIVATE_NEW_BF_BYTES')
        result['files'][new_bf + '.sv'] = text
        contracts.append(selected['root_weight_outputreg'])
        result['source_dependencies'] += selected['source_dependencies']
    need(sum(item['lazy_butterfly_instances'] for item in contracts) ==
         3 * (2 * bundle['parameters']['AW'] - 1) * 8, 'ALL_THREE_FIELD_COHORTS')
    result['root_weight_outputreg_contracts'] = contracts
    return result


def lookahead_whole(bundle):
    result = deepcopy(bundle)
    names = [name[:-3] for name in bundle['files']
             if name.startswith('genefer_stream27_shared_warm_') and name.endswith('.sv')]
    need(len(names) == 3, 'THREE_REAL_FIELD_ROOTS')
    contracts = []
    for old in names:
        view = deepcopy(bundle)
        view.update(top=old, mode='warm_signed')
        view['parameters'] = dict(view['parameters'], FIELD=int(re.search(r'_f([012])_', old)[1]))
        selected = lookahead.bind(view)
        contract = selected['term_lookahead']
        additions = [selected['top'], contract['new_protocol'], contract['new_term']]
        for module in additions:
            filename = module + '.sv'
            text = selected['files'][filename]
            need(filename not in result['files'] or result['files'][filename] == text,
                 'LOOKAHEAD_COMMON_DEFINITION:' + filename)
            result['files'][filename] = text
        for name, text in list(result['files'].items()):
            result['files'][name] = identifier(text, old, selected['top'])
        # The old source definition is retained only as an unreferenced
        # source, not renamed into a second conflicting new definition.
        result['files'].pop(old + '.sv')
        contracts.append(contract)
        result['source_dependencies'] += selected['source_dependencies']
    result['term_lookahead_contracts'] = contracts
    return result


def bind(bundle, *, comm_delay_packed=0, root_weight_outputreg=0, term_lookahead=0):
    roster = dict(comm_delay_packed=comm_delay_packed,
                  root_weight_outputreg=root_weight_outputreg, term_lookahead=term_lookahead)
    check_flags(roster)
    if not any(roster.values()):
        return deepcopy(bundle)
    donor.check(bundle)
    need(bundle['parameters']['AW'] == 16 and 'diet_binding' in bundle, 'FULL_PRIVATE_WHOLE')
    result = packed.bind(bundle) if comm_delay_packed else deepcopy(bundle)
    if root_weight_outputreg:
        result = root_whole(result)
    if term_lookahead:
        result = lookahead_whole(result)
    for name in donor.donor.fitted.PRESERVED:
        need(result['files'][name] == bundle['files'][name], 'NONFIELD_MONT_PRESERVED:' + name)
    need(result['top'] == bundle['top'], 'SAME_WHOLE_HOST_ABI')
    return close(result, bundle, roster)


def prepare(n=65536, p=16, *, comm_delay_packed=0, root_weight_outputreg=0,
            term_lookahead=0, **kwargs):
    return bind(donor.prepare(n, p, **kwargs), comm_delay_packed=comm_delay_packed,
                root_weight_outputreg=root_weight_outputreg, term_lookahead=term_lookahead)
