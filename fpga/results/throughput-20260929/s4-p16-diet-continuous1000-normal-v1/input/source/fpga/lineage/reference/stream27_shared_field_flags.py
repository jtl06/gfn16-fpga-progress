"""Additive shared field flags; frozen zero-flag bundles are byte-identical.

COMM_STAGE_SHARED_MLAB replaces only temporal, field-local commutator groups.
Spatial alignment/cadence control, roots, arithmetic, calendars and correction
choice are inherited. Component qualification is not integrated qualification.
"""
import hashlib
import importlib.util
import copy
from . import stream27_shared_field_v5 as parent
from .merged_stream27_model_v1 import topology
from . import stream27_montgomery_factored_bind as montgomery

ROOT = parent.ROOT
SELF = 'reference/stream27_shared_field_flags.py'
HERE = 'results/throughput-20260929/trackS-p16-diet-analysis-v1/commutator-shared-mlab-v1'
LEAF = HERE + '/rtl/genefer_stream27_mdc_commutator_shared_mlab_v1.sv'
FRAGMENT = HERE + '/stage_fragment.py'
DELAY = 'rtl/kernel/genefer_stream27_delay_mlab_v1.sv'
BOUNDARY = 'rtl/kernel/genefer_stream27_signed_boundary_inputreg_v1.sv'


def need(ok, label):
    if not ok:
        raise ValueError(label)


def emitter():
    spec = importlib.util.spec_from_file_location('s4_shared_temporal_fragment', ROOT / FRAGMENT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.emit_shared_temporal


def bind_shared_comm(bundle, *, n, p):
    emit = emitter()
    files = bundle['files']
    renamed = {}
    changed_stages = 0
    for inverse in (False, True):
        direction = 'gs' if inverse else 'ct'
        old = f'genefer_stream28_merged_{direction}_aw{n.bit_length()-1}_p{p}_f{bundle["parameters"]["FIELD"]}_v1'
        need(old + '.sv' in files, 'S4_SHARED_COMM_TRANSFORM_PARENT')
        text = files.pop(old + '.sv')
        plan = topology(n, p, inverse=inverse)
        for stage in plan['stages']:
            depth = stage['shuffle_depth_per_buffer']
            if not depth:
                continue
            s = stage['stage']
            at = text.index(f' if(1)begin: stage{s}\n')
            start = text.index('  logic [PAIRS-1:0] sh_slot,sh_start,sh_error,sh_pending;', at)
            end = text.index('  wire [', start)
            need('packed_roots;' in text[end:text.index('\n', end)], 'S4_SHARED_COMM_TEMPORAL_END')
            pos = stage['commutator_lane_position']
            swaps = [(lane, lane ^ (1 << pos)) for lane in range(p) if not lane & (1 << pos)]
            text = text[:start] + '\n'.join(emit(s, depth, swaps)) + '\n' + text[end:]
            changed_stages += 1
        new = old + '_shared_comm_mlab_v1'
        text = text.replace('module ' + old + ' #', 'module ' + new + ' #', 1)
        files[new + '.sv'] = text
        renamed[old] = new
    top = bundle['top']
    root = files.pop(top + '.sv')
    for old, new in renamed.items():
        need(root.count(old + ' ') == 1, 'S4_SHARED_COMM_ROOT_INSTANCE')
        root = root.replace(old + ' ', new + ' ')
    newtop = top + '_shared_comm_mlab_v1'
    need(root.count('module ' + top + ' #') == 1, 'S4_SHARED_COMM_ROOT_MODULE')
    root = root.replace('module ' + top + ' #', 'module ' + newtop + ' #', 1)
    anchor = ',CONTEXTS=1'
    need(root.count(anchor) == 1, 'S4_SHARED_COMM_PARAM')
    root = root.replace(anchor, anchor + ',COMM_STAGE_SHARED_MLAB=1', 1)
    anchor = 'CONTEXTS!=1'
    need(root.count(anchor) == 1, 'S4_SHARED_COMM_GUARD')
    root = root.replace(anchor, anchor + ' || COMM_STAGE_SHARED_MLAB!=1', 1)
    files[newtop + '.sv'] = root
    for path in (LEAF, DELAY):
        files[path.rsplit('/', 1)[1]] = (ROOT / path).read_text()
    bundle['top'] = newtop
    bundle['parameters'] = dict(bundle['parameters'], COMM_STAGE_SHARED_MLAB=1)
    bundle['shared_comm_temporal_stages'] = changed_stages
    deps = [SELF, LEAF, FRAGMENT, DELAY]
    bundle['source_dependencies'] = list(dict.fromkeys(bundle['source_dependencies'] + deps))
    bundle['source_sha256'] = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                               for path in bundle['source_dependencies']}
    bundle['rtl_sources'] = [name for name in files if name.endswith('.sv')]
    bundle['generated_sha256'] = {name: hashlib.sha256(text.encode()).hexdigest()
                                  for name, text in files.items()}
    bundle['scope'] = 'Shared temporal control/sideband and MLAB short-delay flag; exact inherited arithmetic/calendar. Integrated native/physical qualification remains required.'
    return bundle


def prepare(n=65536, p=16, field=0, *, mode='warm', contexts=1,
            allow_full_constants=False, corr_serial_bfs=0, comm_stage_shared_mlab=0,
            mont_factored=0, boundary_inputreg=0):
    need(type(comm_stage_shared_mlab) is int and comm_stage_shared_mlab in (0, 1),
         'S4_SHARED_COMM_FLAG')
    bundle = parent.prepare(n, p, field, mode=mode, contexts=contexts,
                            allow_full_constants=allow_full_constants,
                            corr_serial_bfs=corr_serial_bfs)
    if comm_stage_shared_mlab:
        need(mode in ('warm', 'warm_signed'), 'S4_SHARED_COMM_WARM_ONLY')
        bundle = bind_shared_comm(bundle, n=n, p=p)
    return bind_boundary(bind_montgomery(bundle, mont_factored=mont_factored),
                         boundary_inputreg=boundary_inputreg)


def bind(bundle, *, comm_stage_shared_mlab=0, mont_factored=0, boundary_inputreg=0):
    """Bind an already emitted warm bundle without re-emitting any root ROM."""
    need(type(comm_stage_shared_mlab) is int and comm_stage_shared_mlab in (0, 1),
         'S4_SHARED_COMM_FLAG')
    result = copy.deepcopy(bundle)
    if comm_stage_shared_mlab:
        need(result['mode'] in ('warm', 'warm_signed'), 'S4_SHARED_COMM_WARM_ONLY')
        need('COMM_STAGE_SHARED_MLAB' not in result['parameters'], 'S4_SHARED_COMM_ALREADY_BOUND')
        result = bind_shared_comm(result, n=1 << result['parameters']['AW'], p=result['parameters']['P'])
    return bind_boundary(bind_montgomery(result, mont_factored=mont_factored),
                         boundary_inputreg=boundary_inputreg)


def boundary_geometry(before):
    """Ingress register shifts only the accepted correction/cache calendar.

    Zero-margin small frontends need a separate counted input delay. Reject
    those rather than silently changing main transform/controller geometry.
    """
    g = dict(before)
    latency = g['correction_cache_latency'] + 1
    need(g['pointwise_accept'] > latency, 'S4_BOUNDARY_INPUTREG_FRONTEND_PADDING_REQUIRED')
    correction = g['boundary_output'] + 1
    interval = max(g['earliest_next_frame'], correction + latency + 1 - g['pointwise_accept'])
    correction = max(correction, interval)
    need(interval == g['warm_interval'], 'S4_BOUNDARY_INPUTREG_WARM_RECALENDAR_REQUIRED')
    g.update(correction_cache_latency=latency, next_correction_accept=correction,
             next_cache_capture=correction + latency,
             cache_margin=interval + g['pointwise_accept'] - correction - latency - 1,
             initial_latest_correction=g['pointwise_accept'] - latency - 1,
             boundary_inputreg=1)
    for key in ('term_seed_first', 'term_seed_last'):
        if key in g:
            g[key] += 1
    need(g['cache_margin'] >= 0, 'S4_BOUNDARY_INPUTREG_CACHE_MARGIN')
    return g


def boundary_root(text, oldtop):
    """Transform only the field-local selected boundary reducer ingress."""
    newtop = oldtop + '_boundary_inputreg_v1'
    before = 'genefer_stream27_signed_boundary_reduce27_pipe #('
    need(text.count(before) == 1, 'S4_BOUNDARY_INPUTREG_REDUCER_INSTANCE')
    text = text.replace(before, 'genefer_stream27_signed_boundary_inputreg_v1 #(', 1)
    before = '.clk,.rst_n,.in_valid(boundary_slot),'
    need(text.count(before) == 1, 'S4_BOUNDARY_INPUTREG_QUARANTINE_PORT')
    text = text.replace(before, '.clk,.rst_n,.quarantine(stop),.in_valid(boundary_slot),', 1)
    need(text.count('module ' + oldtop + ' #') == 1, 'S4_BOUNDARY_INPUTREG_ROOT')
    text = text.replace('module ' + oldtop + ' #', 'module ' + newtop + ' #', 1)
    need(text.count(',CONTEXTS=1') == 1 and text.count('CONTEXTS!=1') == 1,
         'S4_BOUNDARY_INPUTREG_CONTEXTS1_BUILD')
    text = text.replace(',CONTEXTS=1', ',CONTEXTS=1,BOUNDARY_INPUTREG=1', 1)
    text = text.replace('CONTEXTS!=1', 'CONTEXTS!=1 || BOUNDARY_INPUTREG!=1', 1)
    return newtop, text


def bind_boundary(bundle, *, boundary_inputreg=0):
    need(type(boundary_inputreg) is int and boundary_inputreg in (0, 1),
         'S4_BOUNDARY_INPUTREG_FLAG')
    if boundary_inputreg == 0:
        return bundle
    need(bundle['mode'] in ('warm', 'warm_signed'), 'S4_BOUNDARY_INPUTREG_WARM_ONLY')
    need('BOUNDARY_INPUTREG' not in bundle['parameters'], 'S4_BOUNDARY_INPUTREG_ALREADY_BOUND')
    result = copy.deepcopy(bundle)
    result['geometry'] = boundary_geometry(result['geometry'])
    oldtop = result['top']
    top, text = boundary_root(result['files'].pop(oldtop + '.sv'), oldtop)
    result['files'][top + '.sv'] = text
    result['files'][BOUNDARY.rsplit('/', 1)[1]] = (ROOT / BOUNDARY).read_text()
    result['top'] = top
    result['parameters'] = dict(result['parameters'], BOUNDARY_INPUTREG=1)
    result['source_dependencies'] = list(dict.fromkeys(result['source_dependencies'] + [SELF, BOUNDARY]))
    result['source_sha256'] = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                               for path in result['source_dependencies']}
    result['rtl_sources'] = [name for name in result['files'] if name.endswith('.sv')]
    result['generated_sha256'] = {name: hashlib.sha256(text.encode()).hexdigest()
                                  for name, text in result['files'].items()}
    result['boundary_inputreg_contract'] = 'Accepted correction/base/high/full owner register together; reducer and seed/cache +1, main transform/warm interval unchanged. Quarantine blocks new capture, admitted tail drains; outer stop revokes eligibility.'
    result['scope'] = 'Explicit BOUNDARY_INPUTREG field candidate; source/calendars only until matching native and physical gates.'
    return result


def bind_montgomery(bundle, *, mont_factored=0):
    need(type(mont_factored) is int and mont_factored in (0, 1), 'S4_MONT_FACTORED_FLAG')
    if mont_factored == 0:
        return bundle
    result = montgomery.bind(bundle, MONT_FACTORED=1)
    oldtop = result['top']; newtop = oldtop + '_mont_factored_v1'
    root = result['files'].pop(oldtop + '.sv')
    need(root.count('module ' + oldtop + ' #') == 1, 'S4_MONT_FACTORED_ROOT')
    root = root.replace('module ' + oldtop + ' #', 'module ' + newtop + ' #', 1)
    need(root.count(',CONTEXTS=1') == 1 and root.count('CONTEXTS!=1') == 1,
         'S4_MONT_FACTORED_PARAM')
    root = root.replace(',CONTEXTS=1', ',CONTEXTS=1,MONT_FACTORED=1', 1)
    root = root.replace('CONTEXTS!=1', 'CONTEXTS!=1 || MONT_FACTORED!=1', 1)
    result['files'][newtop+'.sv'] = root; result['top'] = newtop
    result['parameters'] = dict(result['parameters'], MONT_FACTORED=1)
    result['source_dependencies'] = list(dict.fromkeys(result['source_dependencies']+[SELF]))
    result['source_sha256'][SELF] = hashlib.sha256((ROOT/SELF).read_bytes()).hexdigest()
    result['rtl_sources'] = [name for name in result['files'] if name.endswith('.sv')]
    result['generated_sha256'] = {name:hashlib.sha256(text.encode()).hexdigest()
                                  for name,text in result['files'].items()}
    result['scope'] = 'Explicit shared MONT_FACTORED leaf-only flag; canonical consumers, arithmetic domains and calendars unchanged. Composed field numeric/physical qualification not inherited.'
    return result
