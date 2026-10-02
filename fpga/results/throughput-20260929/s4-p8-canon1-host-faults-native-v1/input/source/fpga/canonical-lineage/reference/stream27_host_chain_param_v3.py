"""Shared host compiler flag: CANONICAL_PIPE_STAGES=0|1.

Zero preserves the frozen native/physical parent's complete generated bundle.
One inserts a value register in the final-image barrier only. Warm scheduling,
CRT/carry feedback, FIFO descriptors and ordinary scalar ports are unchanged.
"""
import hashlib
from . import stream27_host_chain_param_v2 as parent
from . import stream27_host_chain_v1 as ledger

ROOT = parent.ROOT
LEAF = 'rtl/kernel/genefer_stream27_canonical_image_pipe_v1.sv'
SELF = 'reference/stream27_host_chain_param_v3.py'


def cycle_contract(n, g, *, count=1, cache_hit=False, special=False,
                   canonical_pipe_stages=0):
    if type(canonical_pipe_stages) is not int or canonical_pipe_stages not in (0, 1):
        raise ValueError('S4_CANONICAL_PIPE_FLAG')
    result = ledger.cycle_contract(n, g, count=count, cache_hit=cache_hit, special=special)
    extra = 3*n*canonical_pipe_stages
    for key in ('canonical_done', 'first_image_commit', 'host_done', 'canonical_busy_cycles'):
        result[key] += extra
    return result


def prepare(n=32, p=16, *, paired=False, contexts=1,
            allow_full_constants=False, canonical_pipe_stages=0):
    if type(canonical_pipe_stages) is not int or canonical_pipe_stages not in (0, 1):
        raise ValueError('S4_CANONICAL_PIPE_FLAG')
    b = parent.prepare(n, p, paired=paired, contexts=contexts,
                       allow_full_constants=allow_full_constants)
    if canonical_pipe_stages == 0:
        return b
    old_leaf = 'genefer_stream27_canonical_image_v1.sv'
    if hashlib.sha256(b['files'][old_leaf].encode()).hexdigest() != 'c6e59a385ed187dceb9b392c096cc1d7cfc5a71ba820326b9b441f1df8093e74':
        raise ValueError('S4_CANONICAL_PIPE_PARENT_DRIFT')
    b['files'].pop(old_leaf)
    names = {name[:-3]: name[:-3].replace('_param_v1', '_canonreg_v1')
             for name in b['files'] if name.startswith(('genefer_stream27_host_chain_', 'genefer_stream27_chain_canonical_')) and name.endswith('.sv')}
    names['genefer_stream27_canonical_image_v1'] = 'genefer_stream27_canonical_image_pipe_v1'
    def rename(text):
        for old, new in names.items():
            text = text.replace(old, new)
        return text
    b['files'] = {rename(name): rename(text) for name, text in b['files'].items()}
    b['top'] = rename(b['top'])
    b['files'][LEAF.rsplit('/', 1)[1]] = (ROOT/LEAF).read_text()
    # The emitted design is explicit, not a silently ignored build parameter.
    for name in list(b['files']):
        if name.startswith('genefer_stream27_host_chain_') and name.endswith('.sv'):
            s = b['files'][name]
            anchor = '#(parameter int unsigned EPOCH_SEED=0,'
            if s.count(anchor) != 1:
                raise ValueError('S4_CANONICAL_PIPE_HOST_PARAMETER')
            s = s.replace(anchor, '#(parameter int CANONICAL_PIPE_STAGES=1,parameter int unsigned EPOCH_SEED=0,')
            s = s.replace('endmodule', ' // synthesis translate_off\n initial if(CANONICAL_PIPE_STAGES!=1)$fatal(1,"S4_CANONICAL_PIPE_BUILD_FLAG");\n // synthesis translate_on\nendmodule')
            b['files'][name] = s
    b['parameters'] = dict(b['parameters'], CANONICAL_PIPE_STAGES=1)
    b['source_dependencies'] = list(dict.fromkeys(b['source_dependencies']+[SELF, LEAF]))
    b['source_sha256'] = {path: parent.parent.root.sha(path) for path in b['source_dependencies']}
    b['generated_sha256'] = {name: hashlib.sha256(text.encode()).hexdigest() for name, text in b['files'].items()}
    b['rtl_sources'] = [name for name in b['files'] if name.endswith('.sv')]
    b['canonical_cost'].update(normal=9*n, special=10*n,
        added_cycles=3*n, pipeline='one registered signed34 value and stored-digit range bit per digit/pass; both data and write legality use the same token')
    b['cycle_contract'] = cycle_contract(n, b['geometry'], canonical_pipe_stages=1)
    b['host_contract']['final'] = 'Full32 true-last ordinal; one final canonical9N/10N plus N-copy. Warm recurrence unchanged; no intermediate canonicalization.'
    b['scope'] = 'Explicit CANONICAL_PIPE_STAGES=1 final-image register candidate; source only until native/whole fit; frozen stage0 default preserved.'
    return b
