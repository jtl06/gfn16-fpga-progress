"""Copied-bundle whole P16 binding of the three already-emitted diet fields.

No shared generator is changed. Zero flags return the complete donor bundle.
The nonzero experiment is deliberately only N65536/P16/C1/canonical-pipe1.
Changed shared field consumers get private identifiers; CRT and paired T5b
retain their original Montgomery definitions and arithmetic bindings.
"""
import copy
import hashlib
import re
from . import stream27_host_chain_param_v3 as parent
from . import stream27_shared_field_v4 as old_fields
from . import stream27_shared_field_flags as fields

ROOT = parent.ROOT
SELF = 'reference/stream27_host_chain_diet.py'
FLAGS = dict(CORR_SERIAL_BFS=2, COMM_STAGE_SHARED_MLAB=1, MONT_FACTORED=1)
PRESERVED = ('genefer_montgomery_mul27_sparse_pipe.sv',
             'genefer_montgomery_mul28x27_sparse_pipe_v2.sv')
CALENDAR = ('forward_accept', 'pointwise_accept', 'square_accept',
            'inverse_accept', 'physical_first', 'sink_accept', 'last_sink',
            'first_digit', 'carry_done', 'warm_interval', 'rows')


def need(ok, label):
    if not ok: raise ValueError('S4_P16_DIET_'+label)


def sha(text): return hashlib.sha256(text.encode()).hexdigest()


def identifiers(text, names):
    if not names: return text
    pattern = r'\b(?:'+ '|'.join(re.escape(name) for name in sorted(names, key=len, reverse=True))+r')\b'
    return re.sub(pattern, lambda match: names[match.group()], text)


def bind(bundle, before, after):
    """Bind checked emitted bundles, useful for isolated source-negative tests."""
    b = copy.deepcopy(bundle)
    need(len(before) == len(after) == 3, 'THREE_FIELDS')
    private, roots, removed = {}, {}, []
    for field, (old, new) in enumerate(zip(before, after)):
        need(old['parameters']['FIELD'] == new['parameters']['FIELD'] == field, 'FIELD_IDENTITY')
        need(all(b['files'].get(name) == text for name, text in old['files'].items()), 'DONOR_FIELD_BYTES')
        need(all(old['geometry'][key] == new['geometry'][key] == b['geometry'][key]
                 for key in CALENDAR), 'UNCHANGED_WHOLE_CALENDAR')
        need(new['geometry']['input_delay'] == 0 and new['geometry']['cache_margin'] >= 0, 'FULL_CACHE_CALENDAR')
        need(all(new['parameters'][key] == value for key, value in FLAGS.items()), 'COMPOSED_FLAGS')
        roots[old['top']] = new['top']
        for name, text in new['files'].items():
            if name in b['files'] and b['files'][name] != text:
                modules = re.findall(r'\bmodule\s+(\w+)\b', text)
                need(modules, 'CHANGED_MODULE_DEFINITION')
                for module in modules: private[module] = module+'_p16_diet_v1'
        # Field-specific replaced roots, CT/GS, square/correction definitions
        # are removed. Common original leaves remain for the non-field users.
        for name, text in old['files'].items():
            if (name == old['top']+'.sv' or f'_f{field}_' in name) and new['files'].get(name) != text:
                removed.append(name)
    # A byte-identical helper may itself consume a now-private child. Close
    # that identifier dependency transitively rather than replacing its old
    # definition for unrelated CRT/T5b users.
    while True:
        added = False
        for new in after:
            for name, text in new['files'].items():
                if name in b['files'] and identifiers(text, private) != b['files'][name]:
                    for module in re.findall(r'\bmodule\s+(\w+)\b', text):
                        if module not in private:
                            private[module] = module+'_p16_diet_v1'; added = True
        if not added: break
    for name in set(removed): b['files'].pop(name)
    b['files'] = {name: identifiers(text, roots) for name, text in b['files'].items()}
    for new in after:
        for name, text in new['files'].items():
            definitions = re.findall(r'\bmodule\s+(\w+)\b', text)
            renamed = name[:-3]+'_p16_diet_v1.sv' if name.endswith('.sv') and any(module in private for module in definitions) else name
            content = identifiers(text, private)
            need(renamed not in b['files'] or b['files'][renamed] == content, 'DEFINITION_COLLISION:'+renamed)
            b['files'][renamed] = content
    host_names = {name[:-3]: name[:-3].removesuffix('_v1')+'_diet_v1'
                  for name in b['files'] if name.startswith('genefer_stream27_host_chain_') and name.endswith('.sv')}
    b['files'] = {identifiers(name[:-3], host_names)+'.sv': identifiers(text, host_names)
                  for name, text in b['files'].items()}
    b['top'] = host_names[b['top']]
    for name in b['files']:
        if name.startswith('genefer_stream27_host_chain_'):
            text = b['files'][name]
            anchor = '#(parameter int CANONICAL_PIPE_STAGES=1,'
            need(text.count(anchor) == 1, 'HOST_FLAG_ANCHOR')
            text = text.replace(anchor, '#(parameter int CORR_SERIAL_BFS=2,COMM_STAGE_SHARED_MLAB=1,MONT_FACTORED=1,parameter int CANONICAL_PIPE_STAGES=1,')
            anchor = 'initial if(CANONICAL_PIPE_STAGES!=1)'
            need(text.count(anchor) == 1, 'HOST_FLAG_GUARD')
            text = text.replace(anchor, 'initial if(CORR_SERIAL_BFS!=2 || COMM_STAGE_SHARED_MLAB!=1 || MONT_FACTORED!=1 || CANONICAL_PIPE_STAGES!=1)')
            b['files'][name] = text
    need(all(b['files'][name] == bundle['files'][name] for name in PRESERVED), 'CRT_T5B_MONT_PRESERVED')
    # No original field-root instance or replaced definition remains active.
    for old in before:
        need(not any(re.search(r'\b'+re.escape(old['top'])+r'\b', text) for text in b['files'].values()), 'OLD_ROOT_REMAINS')
    b['parameters'] = dict(b['parameters'], **FLAGS)
    b['geometry'].update(after[0]['geometry'])
    deps = list(bundle['source_dependencies'])+[SELF]
    for new in after: deps += new['source_dependencies']
    b['source_dependencies'] = list(dict.fromkeys(deps))
    b['source_sha256'] = {path: hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in b['source_dependencies']}
    b['rtl_sources'] = [name for name in b['files'] if name.endswith('.sv')]
    b['generated_sha256'] = {name: sha(text) for name, text in b['files'].items()}
    b['diet_binding'] = dict(flags=FLAGS, boundary_inputreg=0, contexts=1,
        old_roots=[old['top'] for old in before], new_roots=[new['top'] for new in after],
        private_consumers=private, removed_field_definitions=sorted(set(removed)),
        original_montgomery_preserved={name:sha(b['files'][name]) for name in PRESERVED},
        field_generated_sha256=[new['generated_sha256'] for new in after],
        field_geometries=[new['geometry'] for new in after],
        whole_calendar_changed=False, whole_resource_go=False,
        scope='Actual composed three-field whole host; no 3xfield resource or timing inference.')
    b['scope'] = 'Single-context fullN P16 composed diet whole-host source; own native and actual whole synthesis screen required, no promotion.'
    return b


def prepare(n=65536, p=16, *, paired=False, contexts=1, allow_full_constants=False,
            canonical_pipe_stages=0, corr_serial_bfs=0, comm_stage_shared_mlab=0, mont_factored=0):
    values = (corr_serial_bfs, comm_stage_shared_mlab, mont_factored)
    need(all(type(value) is int for value in values), 'INTEGER_FLAGS')
    if values == (0,0,0):
        return parent.prepare(n,p,paired=paired,contexts=contexts,
            allow_full_constants=allow_full_constants,canonical_pipe_stages=canonical_pipe_stages)
    need((n,p,contexts,canonical_pipe_stages,*values) == (65536,16,1,1,2,1,1)
         and allow_full_constants is True and type(paired) is bool, 'ONLY_FULL_P16_C1_COMPOSITION')
    b = parent.prepare(n,p,paired=paired,contexts=contexts,allow_full_constants=True,canonical_pipe_stages=1)
    kwargs = dict(mode='warm_signed',contexts=1,allow_full_constants=True)
    old = [old_fields.prepare(n,p,field,**kwargs) for field in range(3)]
    new = [fields.prepare(n,p,field,**kwargs,corr_serial_bfs=2,comm_stage_shared_mlab=1,mont_factored=1) for field in range(3)]
    return bind(b,old,new)
