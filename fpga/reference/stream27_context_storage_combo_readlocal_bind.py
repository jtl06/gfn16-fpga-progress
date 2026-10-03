"""Read-only canonical eligibility factoring on immutable R95 R3.

The retained canonical_owner -> correction bound/compare -> legal_read ->
scratch RAM path motivates this one control-only experiment. Exclusive reads
cannot inspect base/correction range: those checks apply to load/begin only.
Authoritative rejection/code/FSM, functional owner selection, pending token,
RAM payload and publication stay literal. No pipeline or fault edge is added.
"""
import copy
import hashlib
import itertools
from pathlib import Path

from . import stream27_context_storage_combo_quarantine_bind as quarantine

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_context_storage_combo_readlocal_bind.py'
PARENT_PIN = 'a45413816ed3cccb112a0e0ec6947c20c22e3314e30e6eaed8be260f5ac25a28'
OLD = 'genefer_stream27_canonical_image_pipe_v1'
NEW = 'genefer_stream27_canonical_image_readlocal_v1'
LEAF_PIN = '763b069a9797b91c7122bdf30fe86879b8c34dd318613ec4e096797610a379a5'
READ_BEFORE = '    wire legal_read=rst_n && state==IDLE && !error && !idle_reject && read_req;\n'
READ_AFTER = '''    // Exclusive read has no base/correction validation dependency.
    // Pending reads may overlap another read, but never load/begin.
    wire legal_read=rst_n && state==IDLE && !error && read_req &&
        !load_valid && !begin_canonical && image_valid;
    wire legal_response=rst_n && read_pending && state==IDLE && image_valid &&
        !error && !load_valid && !begin_canonical;
'''
RESPONSE_BEFORE = 'read_pending && state==IDLE && image_valid && !error && !idle_reject'


def need(ok, label):
    if not ok:
        raise ValueError('C2_COMBO_READLOCAL_' + label)


def sha(raw):
    return hashlib.sha256(raw if isinstance(raw, bytes) else raw.encode()).hexdigest()


def read_model(idle, rst, error, image, pending, load, begin, read,
               base_ok, load_bad, correction_bad, raw_ready, order_bad):
    """Literal old priority versus factored predicates, known Boolean inputs."""
    conflict = load + begin + read > 1 or (pending and (load or begin))
    reject = bool(idle and not error and (conflict or
        (load and (not base_ok or load_bad or order_bad)) or
        (not load and begin and (not raw_ready or not base_ok or correction_bad)) or
        (not load and not begin and read and not image)))
    original_read = bool(rst and idle and not error and not reject and read)
    local_read = bool(rst and idle and not error and read and not load and not begin and image)
    original_response = bool(rst and pending and idle and image and not error and not reject)
    local_response = bool(rst and pending and idle and image and not error and not load and not begin)
    return original_read, local_read, original_response, local_response, reject


def prove_reads():
    cases = read_count = response_count = 0
    for values in itertools.product((0, 1), repeat=13):
        old, new, old_response, new_response, _ = read_model(*values)
        need(old == new and old_response == new_response, 'ALL_BOOLEAN_PRIORITY_CASES')
        cases += 1
        read_count += old
        response_count += old_response
    return dict(cases=cases, eligible_read_cases=read_count,
                eligible_response_cases=response_count, no_unknown_input_equivalence_claim=True)


def reverse_leaf(text):
    text = quarantine.boundary.once(text, 'module '+NEW+' #', 'module '+OLD+' #')
    text = quarantine.boundary.once(text, READ_AFTER, READ_BEFORE)
    need(text.count('if(legal_response)') == 1 and text.count('if(rst_n && legal_response)') == 1,
         'EXACT_TWO_RESPONSE_CONSUMERS')
    text = text.replace('if(legal_response)', 'if('+RESPONSE_BEFORE+')', 1)
    return text.replace('if(rst_n && legal_response)', 'if(rst_n && '+RESPONSE_BEFORE+')', 1)


def bind(bundle, *, enabled=0):
    need(type(enabled) is int and enabled in (0, 1), 'BOOLEAN_SWITCH')
    out = copy.deepcopy(bundle)
    if not enabled:
        return out
    need(sha((ROOT/quarantine.SELF).read_bytes()) == PARENT_PIN, 'IMMUTABLE_R3')
    parent = quarantine.prepare(out['geometry']['n'], enabled=1)
    need(out == parent, 'EXACT_R3_ONLY_NO_OTHER_FLAGS')
    proof = prove_reads()
    original = out['files'].pop(OLD+'.sv')
    need(sha(original) == LEAF_PIN, 'EXACT_CANONICAL_PARENT')
    need(original.count(RESPONSE_BEFORE) == 2, 'TWO_ORIGINAL_RESPONSE_CONSUMERS')
    text = quarantine.boundary.once(original, READ_BEFORE, READ_AFTER)
    text = text.replace(RESPONSE_BEFORE, 'legal_response')
    text = quarantine.boundary.once(text, 'module '+OLD+' #', 'module '+NEW+' #')
    need(reverse_leaf(text) == original, 'EVERY_CANONICAL_BYTE_REVERSE')
    oldtop = out['top']
    top = f'genefer_stream27_host_contexts_aw{out["geometry"]["aw"]}_p16_storage_combo_readlocal_v1'
    host = out['files'].pop(oldtop+'.sv')
    need(host.count(' '+OLD+' #') == 1 and sum(s.count(' '+OLD+' #') for s in out['files'].values()) == 0,
         'ONE_SHARED_SCRATCH_CALLER')
    host = quarantine.boundary.once(host, ' '+OLD+' #', ' '+NEW+' #')
    host = quarantine.boundary.once(host, 'module '+oldtop+' #', 'module '+top+' #')
    host = quarantine.boundary.once(host, ',CONTEXTS=2', ',CONTEXTS=2,CANONICAL_READ_LOCAL=1')
    restored = host.replace(' '+NEW+' #', ' '+OLD+' #', 1).replace('module '+top+' #', 'module '+oldtop+' #', 1)
    need(restored.replace(',CANONICAL_READ_LOCAL=1', '', 1) == parent['files'][oldtop+'.sv'],
         'ALL_HOST_OWNER_ARBITRATION_BARRIERS_EXACT')
    out['files'][NEW+'.sv'] = text
    out['files'][top+'.sv'] = host
    out.update(top=top, parameters=dict(out['parameters'], CANONICAL_READ_LOCAL=1))
    out['source_dependencies'] = list(dict.fromkeys(out['source_dependencies']+[SELF]))
    out['source_sha256'] = {path: sha((ROOT/path).read_bytes()) for path in out['source_dependencies']}
    out['rtl_sources'] = list(out['files'])
    out['generated_sha256'] = {name: sha(text) for name, text in out['files'].items()}
    out['context_storage_combo_readlocal'] = dict(parent_top=oldtop,
        parent_generated_sha256=parent['generated_sha256'], roster=['CANONICAL_READ_LOCAL'],
        model=proof, reverse_to_parent_exact=True, authoritative_fault_priority_unchanged=True,
        full_owner_and_context_routing_unchanged=True, read_pending_and_RAM_payload_unchanged=True,
        read_latency_delta=0, calendar_delta=0, publication_barriers_unchanged=True,
        no_new_registers_or_delayed_faults=True, native_qualified=False,
        physical_gain_claim=False, clock_claim=False, promotion_allowed=False)
    return out


def prepare(n=256, *, p=16, contexts=2, enabled=0):
    return bind(quarantine.prepare(n, p=p, contexts=contexts, enabled=1), enabled=enabled)
