"""R6: accepted one-shot second cold correction on immutable R5.

The old 32-bit elapsed-time equality recurs during a full sample chain.
Retain its genuine first proposal edge, hold an unaccepted proposal, and
retire this cold-only transaction on the actual child acceptance. All warm
recurrence, full owners, faults and publication logic remains literal.
"""
import copy

from . import stream27_context_storage_combo_loadlocal_bind as loadlocal

ROOT = loadlocal.ROOT
SELF = 'reference/stream27_context_storage_combo_oneshot_bind.py'
PARENT_PIN = 'c9173c97266126ebd8fb19ea6736b310bcc785427ff73da3505a9442e6bbdf2f'
sha = loadlocal.sha
once = loadlocal.once
DECL_BEFORE = ' logic anchor_valid,anchor_context,first_cold_inflight;logic [31:0] anchor_cycle;\n'
DECL_AFTER = DECL_BEFORE + ' logic second_correction_sent,second_correction_pending;\n'
PROPOSAL_BEFORE = ''' wire cold_second_correction=anchor_valid && jobs[!anchor_context] &&
  32'(cycles[31:0]-anchor_cycle)==32'(SECOND_CORRECTION);
'''
PROPOSAL_AFTER = '''  // Cold-only transaction: do not reissue when the low cycle counter wraps.
  // Pending retains a genuine due proposal until actual child acceptance.
  wire cold_second_due=anchor_valid && jobs[!anchor_context] &&
   32'(cycles[31:0]-anchor_cycle)==32'(SECOND_CORRECTION);
  wire cold_second_correction=anchor_valid && jobs[!anchor_context] &&
   !second_correction_sent && (second_correction_pending || cold_second_due);
'''
RESET_BEFORE = '   setup_inflight<=0;setup_context<=0;anchor_valid<=0;anchor_context<=0;anchor_cycle<=0;first_cold_inflight<=0;\n'
RESET_AFTER = RESET_BEFORE + '    second_correction_sent<=0;second_correction_pending<=0;\n'
NEWJOB_BEFORE = '    jobs<=start_contexts;cycles<=0;anchor_valid<=0;first_cold_inflight<=0;published<=published & ~start_contexts;\n'
NEWJOB_AFTER = NEWJOB_BEFORE + '     second_correction_sent<=0;second_correction_pending<=0;\n'
UPDATE_BEFORE = '   for(int c=0;c<2;c=c+1)if(feed_push[c])next_index[c]<=next_index[c]+32\'d1;\n'
UPDATE_AFTER = '''    if(cold_second_correction && !error)begin
     if(child_correction_accept)begin second_correction_sent<=1;second_correction_pending<=0;end
     else second_correction_pending<=1;
    end
''' + UPDATE_BEFORE
HOST_CHANGES = [(DECL_BEFORE, DECL_AFTER), (PROPOSAL_BEFORE, PROPOSAL_AFTER),
                (RESET_BEFORE, RESET_AFTER), (NEWJOB_BEFORE, NEWJOB_AFTER),
                (UPDATE_BEFORE, UPDATE_AFTER)]


def need(ok, label):
    if not ok:
        raise ValueError('C2_COMBO_ONESHOT_' + label)


def reverse_host(text, *, top, parent_top):
    text = once(text, 'module '+top+' #', 'module '+parent_top+' #')
    text = once(text, ',CONTEXTS=2,COLD_SECOND_ONESHOT=1', ',CONTEXTS=2')
    for before, after in reversed(HOST_CHANGES):
        text = once(text, after, before)
    return text


def proposal(cycle, anchor, second, *, anchor_valid=True, peer_job=True,
             sent=False, pending=False, fixed=True):
    due = bool(anchor_valid and peer_job and ((cycle-anchor) & 0xffffffff) == second)
    return bool(anchor_valid and peer_job and not sent and (pending or due)) if fixed else due


def step(sent, pending, *, proposed, accepted, error=False, reset=False, newjob=False):
    if reset or newjob:
        return False, False
    if proposed and not error:
        if accepted:
            return True, False
        return sent, True
    return sent, pending


def prove_wraps(second):
    """Bounded event model, not an execution of 2**32 clock edges."""
    need(type(second) is int and 0 < second < 2**32, 'SECOND_RANGE')
    anchor = 204
    aliases = [anchor+second+k*2**32 for k in range(4)]
    sent = pending = False
    accepted = []
    for cycle in aliases:
        offered = proposal(cycle, anchor, second, sent=sent, pending=pending)
        if offered:
            accepted.append(cycle)
        sent, pending = step(sent, pending, proposed=offered, accepted=offered)
    need(accepted == aliases[:1] and sent and not pending, 'ONE_ACCEPT_ACROSS_THREE_WRAPS')
    # A missed acceptance does not consume the transaction or lose its pulse.
    sent = pending = False
    due = aliases[0]
    offered = proposal(due, anchor, second, sent=sent, pending=pending)
    sent, pending = step(sent, pending, proposed=offered, accepted=False)
    need(not sent and pending, 'NO_SENT_ON_PROPOSAL')
    for cycle in (due+1, due+2, aliases[1], aliases[1]+1):
        need(proposal(cycle, anchor, second, sent=sent, pending=pending), 'RETAIN_UNACCEPTED')
    sent, pending = step(sent, pending, proposed=True, accepted=True)
    need(sent and not pending and not proposal(aliases[2], anchor, second, sent=sent), 'RETIRE_ON_ACCEPT')
    need(step(sent, pending, proposed=False, accepted=False, reset=True) == (False, False) and
         step(sent, pending, proposed=False, accepted=False, newjob=True) == (False, False), 'RESET_NEWJOB')
    return dict(anchor=anchor, second_correction=second, old_alias_edges=aliases,
                fixed_accepted_edges=accepted, bounded_event_model_only=True,
                no_native_wrap_claim=True, missed_accept_retained=True)


def bind(bundle, *, enabled=0):
    need(type(enabled) is int and enabled in (0, 1), 'BOOLEAN_SWITCH')
    out = copy.deepcopy(bundle)
    if not enabled:
        return out
    need(sha((ROOT/loadlocal.SELF).read_bytes()) == PARENT_PIN, 'IMMUTABLE_R5')
    parent = loadlocal.prepare(out['geometry']['n'], enabled=1)
    need(out == parent, 'EXACT_R5_ONLY_NO_OTHER_FLAGS')
    oldtop = out['top']
    top = f'genefer_stream27_host_contexts_aw{out["geometry"]["aw"]}_p16_storage_combo_oneshot_v1'
    original = out['files'].pop(oldtop+'.sv')
    host = original
    for before, after in HOST_CHANGES:
        host = once(host, before, after)
    host = once(host, 'module '+oldtop+' #', 'module '+top+' #')
    host = once(host, ',CONTEXTS=2', ',CONTEXTS=2,COLD_SECOND_ONESHOT=1')
    need(reverse_host(host, top=top, parent_top=oldtop) == original, 'HOST_LITERAL_REVERSE')
    out['files'][top+'.sv'] = host
    out.update(top=top, parameters=dict(out['parameters'], COLD_SECOND_ONESHOT=1))
    out['source_dependencies'] = list(dict.fromkeys(out['source_dependencies']+[SELF]))
    out['source_sha256'] = {path: sha((ROOT/path).read_bytes()) for path in out['source_dependencies']}
    out['rtl_sources'] = list(out['files'])
    out['generated_sha256'] = {name: sha(text) for name, text in out['files'].items()}
    second = int(host.split('SECOND_CORRECTION=', 1)[1].split(';', 1)[0])
    out['context_storage_combo_oneshot'] = dict(parent_top=oldtop,
        parent_generated_sha256=parent['generated_sha256'], roster=['COLD_SECOND_ONESHOT'],
        model=prove_wraps(second), reverse_to_parent_exact=True,
        reset_and_newjob_clear=True, actual_accept_only_retires=True, pending_proposal_retained=True,
        calendar_delta_on_legal_accepted_trace=0, downstream_owner_fault_and_publication_exact=True,
        added_state_bits=2, native_qualified=False, clock_claim=False, promotion_allowed=False)
    return out


def prepare(n=256, *, p=16, contexts=2, enabled=0):
    return bind(loadlocal.prepare(n, p=p, contexts=contexts, enabled=1), enabled=enabled)
