"""Packed-delay-only whole P16 successor of the frozen composed diet.

No timing7/root-register/L7/CT-fusion changes are implied. The same qualified
stage leaf is bound into all actual field consumers; controls/calendars and
CRT/T5b arithmetic remain exact. Actual whole native and synthesis evidence
are required, and isolated field LAB deltas are not multiplied by three.
"""
import copy
import hashlib
from . import stream27_host_chain_diet as parent
from . import stream27_comm_packed_bind as packed

ROOT = parent.ROOT
SELF = 'reference/stream27_host_chain_packed.py'


def bind(bundle, *, comm_delay_packed=0):
    parent.need(type(comm_delay_packed) is int and comm_delay_packed in (0, 1), 'PACKED_LITERAL_FLAG')
    if not comm_delay_packed:
        return copy.deepcopy(bundle)
    params = bundle['parameters']
    parent.need(params['AW'] == 16 and params['P'] == 16 and params['CONTEXTS'] == 1 and
                params.get('CANONICAL_PIPE_STAGES') == 1 and
                all(params.get(name) == value for name, value in parent.FLAGS.items()), 'PACKED_EXACT_FULL_DIET')
    parent.need('diet_binding' in bundle and 'timing_roster' not in bundle and
                not bundle['diet_binding']['boundary_inputreg'], 'PACKED_BASELINE_NOT_TIMING_SUCCESSOR')
    result = packed.bind(bundle)
    parent.need(result['geometry'] == bundle['geometry'] and result['parameters'] == params,
                'PACKED_ZERO_CALENDAR_PARAMETER_DELTA')
    parent.need(result['top'] == bundle['top'], 'PACKED_SAME_HOST_ABI')
    for name in parent.PRESERVED:
        parent.need(result['files'][name] == bundle['files'][name], 'PACKED_CRT_T5B_UNCHANGED')
    result['source_dependencies'] = list(dict.fromkeys(result['source_dependencies'] + [SELF]))
    result['source_sha256'][SELF] = hashlib.sha256((ROOT / SELF).read_bytes()).hexdigest()
    result['packed_whole_binding'] = dict(flag=1, parent_generated_sha256=bundle['generated_sha256'],
        parent_top=bundle['top'], donor='reference/stream27_host_chain_diet.py',
        added_timing_flags=False, field_measurement='s4-packed-delay-warm-p16-f0-v1',
        whole_calendar_changed=False, whole_area_measured=False, whole_fit_GO=False,
        scope='Whole baseline58 donor plus packed delay only; no field-times3 area credit.')
    result['scope'] = 'Source-specific packed-only whole P16: own normal and whole SYN screen; no routing release or inherited timing7 evidence.'
    return result


def prepare(n=65536, p=16, *, comm_delay_packed=0, **kwargs):
    # Flag0 is the exact donor, including its default-parameter behavior.
    return bind(parent.prepare(n, p, **kwargs), comm_delay_packed=comm_delay_packed)
