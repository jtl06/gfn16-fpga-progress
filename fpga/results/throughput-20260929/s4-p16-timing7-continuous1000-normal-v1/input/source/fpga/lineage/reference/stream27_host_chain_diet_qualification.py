"""Separate small-P16 qualification binding for the frozen composed diet.

FullN returns byte-identical fitted RTL. N32/N256 use the actual CORR_SERIAL2
field calendar, including a counted feedback pipeline when the cache needs it.
No shared compiler, fitted variant, arithmetic or public host ABI is changed.
These are source/event contracts, not native qualification or physical GO.
"""
import copy
import hashlib
import json
import re
import types
from . import stream27_host_chain_diet as fitted
from . import stream27_warm_recurrence_v1 as recurrence
from . import stream27_warm_chain_v1 as chain

ROOT = fitted.ROOT
SELF = 'reference/stream27_host_chain_diet_qualification.py'
FULL_MAP = {
    False: (58, '9a88a9f185bec153dd2531bcaa5e2634305bc30e216c53cc2107bc7f43e2111f'),
    True: (69, 'd05d90dd2ffb0f3ec06951288afdf7d0fc748b0f2221c2a608ac05434720c025'),
}
SMALL = {
    32: dict(input_delay=40, first_digit=156, warm_interval=161,
             carry_done=161, feedback_delay=4, correction_cache_latency=75),
    256: dict(input_delay=7, first_digit=193, warm_interval=212,
              carry_done=212, feedback_delay=18, correction_cache_latency=77),
}


def need(ok, label):
    if not ok:
        raise ValueError('S4_P16_DIET_QUAL_'+label)


def digest_map(pins):
    return hashlib.sha256(json.dumps(pins, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def feedback_source(n, child, geometry):
    """Exact inherited recurrence except the fixed accepted-edge delay rows.

No enable/stall is added: valid/start shift every physical edge, data/owner
only shift with their matching old valid. Clearing reset/error eligibility
discards payload without resetting it, as in the frozen four-row controller.
"""
    delay = geometry['feedback_delay']
    need(type(delay) is int and delay in (4, 18), 'COUNTED_FEEDBACK_DELAY')
    top, text = recurrence.source(n, child, dict(geometry, feedback_delay=4))
    if delay == 4:
        return top, text
    start = text.index(' // Four explicit accepted-edge pipeline rows:')
    end = text.index(' for(genvar lane=0;', start)
    fragment = text[start:end]
    changes = [
        ('Four explicit accepted-edge pipeline rows: carry output k -> field accept k+5.',
         f'{delay} explicit accepted-edge pipeline rows: carry output k -> field accept k+{delay+1}.', 1),
        ('[3:0]', f'[{delay-1}:0]', 1),
        ('[0:3]', f'[0:{delay-1}]', 2),
        ('[3]', f'[{delay-1}]', 4),
        ('[2:0]', f'[{delay-2}:0]', 2),
        ('d<4;', f'd<{delay};', 1),
    ]
    for before, after, count in changes:
        need(fragment.count(before) == count, 'FEEDBACK_ANCHOR:'+before)
        fragment = fragment.replace(before, after)
    return top, text[:start]+fragment+text[end:]


def chain_source(n, child, geometry):
    # Reuse the exact long-control transformation in a private globals map;
    # never replace chain.parent or mutate a shared module while compiling.
    source = types.FunctionType(chain.source.__code__,
        dict(chain.source.__globals__, parent=types.SimpleNamespace(source=feedback_source)))
    return source(n, child, geometry)


def bind_small(bundle, before, after):
    """Copy emitted real fields and update the one geometry-dependent wrapper."""
    b = copy.deepcopy(bundle)
    n = 1 << b['parameters']['AW']
    need(n in SMALL and len(before) == len(after) == 3, 'SMALL_THREE_FIELDS')
    geometry = after[0]['geometry']
    need(all(new['geometry'] == geometry for new in after), 'THREE_FIELD_CALENDAR')
    need(all(geometry[key] == value for key, value in SMALL[n].items()), 'ACTUAL_SERIAL_CALENDAR')
    need(geometry['warm_interval'] == geometry['earliest_next_frame']+geometry['feedback_delay'], 'FEEDBACK_INTERVAL')
    need(geometry['warm_interval'] > geometry['carry_done']-geometry['first_digit'], 'ORDINAL_NONOVERLAP')
    need(geometry['next_cache_capture']+1 <= geometry['warm_interval']+geometry['pointwise_accept']
         and geometry['cache_margin'] == 0, 'CACHE_BEFORE_POINTWISE')
    warm = f'genefer_stream27_warm_chain_aw{n.bit_length()-1}_p16_v1'
    child = f'genefer_stream27_threefield_carry_aw{n.bit_length()-1}_p16_v1_host_v1'
    inherited_top, inherited = chain.source(n, child, b['geometry'])
    need(inherited_top == warm and b['files'].get(warm+'.sv') == inherited, 'WARM_CONTROLLER_PARENT')
    newtop, newtext = chain_source(n, child, geometry)
    need(newtop == warm, 'WARM_CONTROLLER_IDENTIFIER')
    b['files'][warm+'.sv'] = newtext
    private, roots, removed = {}, {}, []
    for field, (old, new) in enumerate(zip(before, after)):
        need(old['parameters']['FIELD'] == new['parameters']['FIELD'] == field, 'FIELD_IDENTITY')
        need(all(bundle['files'].get(name) == text for name, text in old['files'].items()), 'DONOR_FIELD_BYTES')
        need(all(new['parameters'][key] == value for key, value in fitted.FLAGS.items()), 'COMPOSED_FLAGS')
        roots[old['top']] = new['top']
        for name, text in new['files'].items():
            if name in b['files'] and b['files'][name] != text:
                modules = re.findall(r'\bmodule\s+(\w+)\b', text)
                need(modules, 'CHANGED_MODULE_DEFINITION')
                for module in modules:
                    private[module] = module+'_p16_diet_v1'
        for name, text in old['files'].items():
            if (name == old['top']+'.sv' or f'_f{field}_' in name) and new['files'].get(name) != text:
                removed.append(name)
    while True:
        added = False
        for new in after:
            for name, text in new['files'].items():
                if name in b['files'] and fitted.identifiers(text, private) != b['files'][name]:
                    for module in re.findall(r'\bmodule\s+(\w+)\b', text):
                        if module not in private:
                            private[module] = module+'_p16_diet_v1'
                            added = True
        if not added:
            break
    for name in set(removed):
        b['files'].pop(name)
    b['files'] = {name: fitted.identifiers(text, roots) for name, text in b['files'].items()}
    for new in after:
        for name, text in new['files'].items():
            definitions = re.findall(r'\bmodule\s+(\w+)\b', text)
            renamed = name[:-3]+'_p16_diet_v1.sv' if name.endswith('.sv') and any(module in private for module in definitions) else name
            content = fitted.identifiers(text, private)
            need(renamed not in b['files'] or b['files'][renamed] == content, 'DEFINITION_COLLISION:'+renamed)
            b['files'][renamed] = content
    names = {name[:-3]: name[:-3].removesuffix('_v1')+'_diet_qualification_v1'
             for name in b['files'] if name.startswith('genefer_stream27_host_chain_') and name.endswith('.sv')}
    b['files'] = {fitted.identifiers(name[:-3], names)+'.sv': fitted.identifiers(text, names)
                  for name, text in b['files'].items()}
    b['top'] = names[b['top']]
    for name in b['files']:
        if name.startswith('genefer_stream27_host_chain_'):
            text = b['files'][name]
            anchor = '#(parameter int CANONICAL_PIPE_STAGES=1,'
            need(text.count(anchor) == 1, 'HOST_FLAG_ANCHOR')
            text = text.replace(anchor, '#(parameter int CORR_SERIAL_BFS=2,COMM_STAGE_SHARED_MLAB=1,MONT_FACTORED=1,parameter int CANONICAL_PIPE_STAGES=1,')
            anchor = 'initial if(CANONICAL_PIPE_STAGES!=1)'
            need(text.count(anchor) == 1, 'HOST_FLAG_GUARD')
            b['files'][name] = text.replace(anchor, 'initial if(CORR_SERIAL_BFS!=2 || COMM_STAGE_SHARED_MLAB!=1 || MONT_FACTORED!=1 || CANONICAL_PIPE_STAGES!=1)')
    need(all(b['files'][name] == bundle['files'][name] for name in fitted.PRESERVED), 'CRT_T5B_MONT_PRESERVED')
    for old in before:
        need(not any(re.search(r'\b'+re.escape(old['top'])+r'\b', text) for text in b['files'].values()), 'OLD_ROOT_REMAINS')
    b['parameters'] = dict(b['parameters'], **fitted.FLAGS)
    b['geometry'] = copy.deepcopy(geometry)
    b['cycle_contract'] = fitted.parent.cycle_contract(n, geometry, canonical_pipe_stages=1)
    b['source_dependencies'] = list(dict.fromkeys(bundle['source_dependencies']+[fitted.SELF, SELF]+
        [path for new in after for path in new['source_dependencies']]))
    b['source_sha256'] = {path: hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in b['source_dependencies']}
    b['rtl_sources'] = [name for name in b['files'] if name.endswith('.sv')]
    b['generated_sha256'] = {name: fitted.sha(text) for name, text in b['files'].items()}
    b['diet_binding'] = dict(flags=fitted.FLAGS, contexts=1, boundary_inputreg=0,
        old_roots=[old['top'] for old in before], new_roots=[new['top'] for new in after],
        private_consumers=private, field_geometries=[new['geometry'] for new in after],
        whole_calendar_changed=True, counted_feedback_rows=geometry['feedback_delay'],
        full_N_fitted_RTL_unchanged=True, whole_resource_go=False,
        scope='Small-P16 source qualification; actual serialized correction and matching feedback delay, no native/physical/promotion claim.')
    b['scope'] = 'N32/N256 P16 qualification source only; no inherited fullN or P8 result.'
    return b


def prepare(n=65536, p=16, *, paired=False, contexts=1, allow_full_constants=True,
            canonical_pipe_stages=1, corr_serial_bfs=2, comm_stage_shared_mlab=1, mont_factored=1):
    need(all(type(value) is int for value in (n, p, contexts, canonical_pipe_stages,
         corr_serial_bfs, comm_stage_shared_mlab, mont_factored)) and type(paired) is bool
         and type(allow_full_constants) is bool, 'STRICT_ARGUMENT_TYPES')
    need(n in (*SMALL, 65536) and (p, contexts, canonical_pipe_stages,
         corr_serial_bfs, comm_stage_shared_mlab, mont_factored) == (16, 1, 1, 2, 1, 1), 'EXACT_P16_DIET_FLAGS')
    if n == 65536:
        b = fitted.prepare(n, p, paired=paired, contexts=contexts, allow_full_constants=allow_full_constants,
            canonical_pipe_stages=1, corr_serial_bfs=2, comm_stage_shared_mlab=1, mont_factored=1)
        pins = {name: fitted.sha(text) for name, text in b['files'].items()}
        need((len(pins), digest_map(pins)) == FULL_MAP[paired], 'FULL_FITTED_RTL_DRIFT')
        # Only generation provenance grows; files/top/parameters/calendar stay exact.
        b['source_dependencies'] = list(dict.fromkeys(b['source_dependencies']+[SELF]))
        b['source_sha256'][SELF] = hashlib.sha256((ROOT/SELF).read_bytes()).hexdigest()
        return b
    b = fitted.parent.prepare(n, p, paired=paired, contexts=1,
        allow_full_constants=allow_full_constants, canonical_pipe_stages=1)
    kwargs = dict(mode='warm_signed', contexts=1, allow_full_constants=allow_full_constants)
    before = [fitted.old_fields.prepare(n, p, field, **kwargs) for field in range(3)]
    after = [fitted.fields.prepare(n, p, field, **kwargs, corr_serial_bfs=2,
        comm_stage_shared_mlab=1, mont_factored=1) for field in range(3)]
    return bind_small(b, before, after)
