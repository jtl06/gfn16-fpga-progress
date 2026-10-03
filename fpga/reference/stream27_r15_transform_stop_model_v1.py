"""Private AUTHOR model only: no RTL generator, writer, native or fit action.

The boolean macro envelope can preserve first-origin and effective outputs
while private work differs after its sticky aggregate. That is NOT full state,
unqualified payload, arbitrary-input native-trace or numeric recovery equality.
An unrestricted post-aggregate input-range witness is retained, not hidden.
"""
from dataclasses import dataclass
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / 'results/throughput-20260929/trackS-r15-compute-native-v1/full-normal-v2/production-bundle.json'
CAPTURE_PIN = '079ea8523f4599bd521d3a3b3c513001b4e537912fb75ad5a2894447e4c7d428'
FLAG = 'TRANSFORM_DATAPATH_STOP_LOCAL'


def need(condition, reason):
    if not condition:
        raise ValueError('R15_TRANSFORM_STOP_MODEL_' + reason)


def flag(value=0):
    need(type(value) is int and value in (0, 1), 'EXACT_DEFAULT_OFF_FLAG')
    return value


@dataclass(frozen=True)
class Signals:
    """One pre-edge abstract macro sample, not a complete CT/GS simulator."""
    aggregate: bool
    quarantine: bool
    sticky_child: bool
    comb_fault: bool
    private_slot: bool
    private_start: bool
    context_enabled: bool
    generation_matches: bool
    payload: object = 0

    def __post_init__(self):
        need(all(type(getattr(self, name)) is bool for name in
             ('aggregate', 'quarantine', 'sticky_child', 'comb_fault',
              'private_slot', 'private_start', 'context_enabled', 'generation_matches')),
             'EXACT_BOOLEAN_SAMPLE')


def internal_stop(sample, local=0):
    flag(local)
    return sample.quarantine or (sample.aggregate and not local)


def observe(sample, local=0):
    """Retain macro stop/pending/first-origin authority exactly.

    Payload/generation equality is claimed only under an effective slot. Raw
    ports, including generation_out/data_out, are not masked by current RTL.
    """
    stop = sample.quarantine or sample.aggregate
    pending = sample.sticky_child or (not internal_stop(sample, local) and sample.comb_fault)
    slot = sample.private_slot and not stop
    return dict(error=sample.aggregate,
                pending=sample.aggregate or pending,
                slot=slot, start=sample.private_start and slot,
                eligible=slot and sample.context_enabled and sample.generation_matches,
                effective_payload=sample.payload if slot else None,
                next_aggregate=sample.aggregate or (not stop and pending))


def envelope_proof():
    """Exhaust finite abstraction, with explicit relational precondition.

    Before first aggregate, all private state/functions and inputs are equal:
    stop choices then coincide. After aggregate, private state may diverge.
    Reset must establish the same control/eligibility relation again; this is
    separately checked for reset-masked delay histories, not asserted as FF
    equality. Arithmetic/full-host recovery remains an unexecuted obligation.
    """
    before = after = 0
    for values in product((False, True), repeat=7):
        s = Signals(False, *values, payload=('same', 1))
        need(observe(s, 0) == observe(s, 1), 'FIRST_ORIGIN_OR_PRE_AGGREGATE_MISMATCH')
        before += 1
    # Exercise independent old/new private faults/slot/start/generation/payload
    # while both sticky aggregate flags are one, for arbitrary quarantine.
    for q, old_bits, new_bits in product((False, True), product((False, True), repeat=6),
                                       product((False, True), repeat=6)):
        old = Signals(True, q, *old_bits, payload=('old-private', 0))
        new = Signals(True, q, *new_bits, payload=('new-private', 1))
        need(observe(old, 0) == observe(new, 1), 'POST_AGGREGATE_EFFECTIVE_OUTPUT_MISMATCH')
        after += 1
    return dict(pre_aggregate_samples=before, post_aggregate_pairs=after,
                boolean_envelope_equivalent=True, sticky_first_origin_equivalent=True,
                first_fault_preedge_output_not_retroactively_suppressed=True,
                post_A1_slot_start_eligible_suppressed=True,
                unqualified_payload_or_private_state_equal=False,
                complete_RTL_or_native_proof=False)


def stage0_range_witness(modulus):
    """Concrete unrestricted-input native assertion sensitivity, not hardware corruption.

    A different stage has latched the aggregate. Stage0 local_error is still
    zero. Quarantine is low and a fresh row is presented. The proposed internal
    accept can reach the unchanged lazy butterfly range assertion, whereas the
    old aggregate stop prevents its execution. Legal caller-derived payloads
    may avoid this witness; proving that restriction is a separate obligation.
    """
    need(type(modulus) is int and modulus > 0 and 2 * modulus < (1 << 28), 'CLOSED_LAZY28_MODULUS')
    old_accept = True and not (False or True) and not False
    new_accept = True and not False and not False
    lhs, rhs = 2 * modulus, 0
    old_fatal = old_accept and (lhs >= 2 * modulus or rhs >= 2 * modulus)
    new_fatal = new_accept and (lhs >= 2 * modulus or rhs >= 2 * modulus)
    need(not old_fatal and new_fatal, 'EXPECTED_POST_AGGREGATE_RANGE_WITNESS')
    return dict(aggregate_error=True, origin='another_stage', external_quarantine=False,
                stage0_local_error=False, row_slot=True, row_start=True,
                remaining=0, lhs=lhs, rhs=rhs, modulus=modulus,
                old_accept=old_accept, proposed_accept=new_accept,
                old_native_range_fatal=old_fatal, proposed_native_range_fatal=new_fatal,
                macro_error_pending_equal=True, macro_effective_output_equal=True,
                hardware_publication_corruption_proven=False,
                actual_whole_caller_reachability_proven=False,
                unrestricted_native_trace_equivalence=False)


def revised_boundary_accept(*, aggregate, quarantine, local_error, row_slot):
    """Revised model keeps RAW stage0 admission on original macro stop."""
    need(all(type(v) is bool for v in (aggregate, quarantine, local_error, row_slot)),
         'EXACT_RAW_BOUNDARY_BOOLEAN')
    return row_slot and not (quarantine or aggregate) and not local_error


def revised_boundary_proof():
    samples = 0
    for a, q, local, slot in product((False, True), repeat=4):
        old = slot and not (q or a) and not local
        revised = revised_boundary_accept(aggregate=a, quarantine=q, local_error=local, row_slot=slot)
        need(old == revised, 'REVISED_RAW_ACCEPT_DIFFERS')
        for p in (104857601, 69206017, 67239937):
            # Includes illegal raw payloads, never predicates them away.
            for u in (0, p - 1, p, 2 * p - 1, 2 * p, (1 << 28) - 1):
                for v in (0, 2 * p - 1, 2 * p):
                    need((old and (u >= 2*p or v >= 2*p)) ==
                         (revised and (u >= 2*p or v >= 2*p)), 'REVISED_RAW_NATIVE_RANGE_DIFFERS')
                    samples += 1
    return dict(samples=samples, raw_accept_exact=True,
                old_and_revised_raw_range_assertion_decisions_equal=True,
                no_new_external_row_after_A1=True, original_counterexample_retained=True)


def bounded_origin_interval_proof():
    """Algebraic transfer-domain lemma, not a new arithmetic/native proof.

    Every continued valid internal operand must descend from a pre-A1 raw
    accepted row (or reset-qualified zero/fresh row), not an unconstrained new
    post-fault value. Existing literal BF multiplier/canonical-result and
    accepted-valid alignment contracts are explicit assumptions. Re-pairing
    bounded values can change numbers, but cannot alone break lazy bounds.
    """
    rows = []
    for p in (104857601, 69206017, 67239937):
        # CT: canonical u in[0,P), product in[0,P).
        ct_y0 = (0, 2*p - 2)
        ct_y1 = (1, 2*p - 1)
        # GS: 0<=u,v<2P, sum<=4P-2, difference in[1,4P-1].
        gs_raw_sum = (0, 4*p - 2)
        gs_raw_diff = (1, 4*p - 1)
        need(ct_y0[1] < 2*p and ct_y1[1] < 2*p, 'CT_RANGE_CLOSURE')
        need(gs_raw_sum[1] < 4*p and gs_raw_diff[1] < 4*p, 'GS_ONE_FOLD_RANGE')
        # One subtraction of2P is enough; include the discontinuity endpoints.
        for raw in (0, 1, 2*p-1, 2*p, 2*p+1, 4*p-2, 4*p-1):
            folded = raw - 2*p if raw >= 2*p else raw
            need(0 <= folded < 2*p, 'GS_FOLDED_RANGE')
        rows.append(dict(modulus=p, accepted_origin_domain=[0, 2*p-1],
                         CT_y0_domain=list(ct_y0), CT_y1_domain=list(ct_y1),
                         GS_folded_domain=[0, 2*p-1],
                         direct_caller_27bit_max=(1 << 27)-1,
                         direct_caller_27bit_inside_lazy_domain=(1 << 27)-1 < 2*p))
    return dict(rows=rows,
                pre_A1_accepted_origin_or_reset_qualified_zero_required=True,
                valid_alignment_and_canonical_multiplier_contracts_assumed_literal=True,
                blanket_trusted_post_fault_input_assumption=False,
                arbitrary_RAM_corruption_bound_or_numeric_equality_proven=False,
                wrong_pairing_can_change_arithmetic=True,
                whole_caller_and_native_recovery_qualification_pending=True)


class ResetMaskedRing:
    """Symbolic data+tag delay; initial private payload may be unrelated."""
    def __init__(self, depth, seed):
        need(type(depth) is int and depth > 0 and depth & (depth - 1) == 0, 'POWER_OF_TWO_DELAY')
        self.depth = depth
        self.memory = [(seed, k) for k in range(depth)]
        self.prefetched = (seed, 'q')
        self.pointer = self.filled = 0

    def reset(self):
        # Payload/tag RAM and prefetched register remain deliberately different.
        self.pointer = self.filled = 0

    @property
    def head(self):
        return self.prefetched if self.filled == self.depth else None

    def edge(self, advance, token):
        need(type(advance) is bool, 'EXACT_ADVANCE')
        if advance:
            nxt = (self.pointer + 1) % self.depth
            self.prefetched = token if self.depth == 1 else self.memory[nxt]
            self.memory[self.pointer] = token
            self.pointer = nxt
            self.filled = min(self.depth, self.filled + 1)


def reset_history_proof(depths=(1, 2, 4, 8, 16, 32, 64, 128, 2048)):
    rows = []
    for depth in depths:
        a, b = ResetMaskedRing(depth, 'old'), ResetMaskedRing(depth, 'new')
        # Allow unrelated post-A1 private work and unreset payload histories.
        for k in range(2 * depth + 3):
            a.edge(k % 3 != 0, ('old-tail', k))
            b.edge(k % 5 != 0, ('new-tail', k))
        a.reset(); b.reset()
        checked = advances = 0
        for k in range(3 * depth + 10):
            need(a.head == b.head, 'STALE_RESET_HEAD_VISIBLE')
            advance = k % 4 != 1
            a.edge(advance, ('fresh', k)); b.edge(advance, ('fresh', k))
            advances += int(advance); checked += 1
        need(advances >= depth, 'FRESH_REFILL_NOT_EXERCISED')
        need(a.head == b.head, 'REFILLED_HEAD_MISMATCH')
        rows.append(dict(depth=depth, samples=checked, fresh_advances=advances,
                         payload_reset=False, masked_head_equal=True))
    return rows


def audit_source():
    raw = CAPTURE.read_bytes(); need(sha256(raw).hexdigest() == CAPTURE_PIN, 'FROZEN_COMPUTE_CAPTURE')
    b = json.loads(raw); rows = []
    names = [n for n in b['files'] if re.fullmatch(
        r'genefer_stream28_merged_(ct|gs)_aw16_p16_f[012]_v1_shared_comm_mlab_v1(?:_c2_inputreg_v1)?_r15_leanwatch_v1\.sv', n)]
    need(len(names) == 6, 'EXACT_SIX_ROOTS')
    anchors = (' wire stop=quarantine || aggregate_error;',
               ' assign out_error=aggregate_error;assign fault_pending=aggregate_error || (|stage_pending);',
               ' assign out_slot_valid=slot[STAGES] && !stop;',
               ' assign out_frame_start=start[STAGES] && out_slot_valid;',
               ' assign out_eligible=out_slot_valid && context_enabled && generation_out==live_generation;',
               '   if(!rst_n)aggregate_error<=0;',
               '   else if(!stop && (|stage_pending))aggregate_error<=1;')
    for name in sorted(names):
        text = b['files'][name]
        need(sha256(text.encode()).hexdigest() == b['generated_sha256'][name], 'SOURCE_HASH')
        need(all(text.count(x) == 1 for x in anchors), 'MACRO_ENVELOPE_ANCHORS')
        need(text.count('wire accept=row_slot && !stop && !local_error;') == 16, 'SIXTEEN_ACCEPT_STAGES')
        need(text.count('if(!rst_n)begin slot_pipe<=0;start_pipe<=0;local_error<=0;remaining<=0;end') == 16,
             'SIXTEEN_RESET_CONTROL_STAGES')
        need(text.count('.quarantine(stop)') == 12, 'EXACT_TWELVE_UNCHANGED_COMM_CALLERS')
        rows.append(dict(path='rtl/' + name, sha256=b['generated_sha256'][name], stages=16,
                         shared_comm_quarantine_callers=12))
    butterfly = b['files']['genefer_stream27_lazy28_rootregistered_butterfly_v1.sv']
    need('if(in_valid && ({1\'b0,u}>=TWO_P || {1\'b0,v}>=TWO_P))' in butterfly and
         '$fatal(1,"Lazy28 butterfly input range violation");' in butterfly,
         'UNCHANGED_NATIVE_ASSERTION_WITNESS_ANCHOR')
    return dict(capture_sha256=CAPTURE_PIN, roots=rows,
                butterfly_sha256=b['generated_sha256']['genefer_stream27_lazy28_rootregistered_butterfly_v1.sv'],
                current_source_mutation=False, RTL_generated=False)


def assess():
    return dict(schema='r15-private-transform-stop-author-model-v1',
                status='REVISED_BOUNDARY_MODEL_PASS_RTL_NATIVE_RECOVERY_UNPROVEN',
                author='/root/fit_queue_sol', source=audit_source(),
                flag=FLAG, default=flag(), model_only=True, envelope=envelope_proof(),
                reset_delay_histories=reset_history_proof(),
                range_witnesses=[stage0_range_witness(p) for p in (104857601, 69206017, 67239937)],
                revised_raw_boundary=revised_boundary_proof(),
                bounded_origin_transport=bounded_origin_interval_proof(),
                obligations=['Qualify all six CT/GS and caller logical output/frame/eligibility/data tuples on a new source cohort.',
                             'Keep RAW stage0 accept on original macro stop. Prove each continued valid internal operand has pre-A1 accepted or reset-qualified origin, without weakening assertions.',
                             'Rebuild reset/control/valid relation and run source-specific full numeric reset/recovery after divergent private tails.',
                             'Retain sticky aggregate, same first-origin pending/report, external quarantine, reset authority and peer granularity.',
                             'No raw payload/generation/private FF equality or canceled-tail flush claim.'],
                RTL_emission_allowed=False, native_submission_allowed=False,
                current60_65_shell_changed=False, current_reviews_inherited=False,
                clock_area_or_hardware_publication_gain=False)


if __name__ == '__main__':
    print(json.dumps(assess(), indent=2))
