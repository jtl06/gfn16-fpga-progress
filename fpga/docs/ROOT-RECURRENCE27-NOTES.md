# Standalone four context root generator

`genefer_root_recurrence27` is an experimental standalone implementation of
the direct recurrence in ROOT-RECURRENCE-PROOF.md. It supplies a registered
logical root vector on the same edge as a synchronous RAM read response,
supports bubbles with an explicit result bypass, and permits next-profile
seed prefetch into a second bank. It does not modify or replace any frozen
NTT/core engine or its arbitrary root-write interface.

## Explicit profile contract

The caller supplies a coherent root profile for the chosen prime, transform
stage, direction, runtime size, and phase. Seeds and step must be canonical
unsigned residues below P. Hardware checks those full 32-bit ranges, but it
does not prove that the supplied values are roots of unity or the correct
profile. Zero is a canonical arithmetic value; a real NTT root profile must
supply the appropriate nonzero roots instead.

Twist and butterfly seeds are Montgomery values under R=2^32. Postconversion
seeds are ordinary `psi^(-i)/N`. In both cases, the recurrence step is a
Montgomery value. This preserves the ordinary representation of post roots.
The caller must also apply the stage-dependent XOR/broadcast permutation
from logical root lanes to physical butterfly lanes; this prototype returns
logical lanes and does not duplicate the banked NTT routing network.

### Serial seed port

`seed_bank` selects one of two banks. `seed_context` selects one of four
contexts, `seed_lane` a logical root lane, and `seed_data` its 32-bit seed.
`seed_we` writes one word per clock. A lane outside the elaborated LANES or
a value at least P pulses seed_error and causes no mutation. `seed_clear`
clears the selected bank's validity bits, not its data, and has priority over
a simultaneous write. The seed lane/value are irrelevant to a clear request.

While idle, either bank can be cleared or written. While busy, only the
inactive bank is writable; attempts to clear/write the active bank pulse
seed_error without changing roots or stopping the operation. Inactive-bank
prefetch and clear can run concurrently with every-clock root requests.
An idle start has priority over seed traffic: coincident seed writes/clears
are silently ignored without seed_error, even if malformed. They cannot fill
a missing seed for that same start. A start held high while busy
is ignored and does not prevent legitimate inactive-bank prefetch.

The validity map records which words have been loaded. It does not encode a
profile identity. The caller must clear a bank before loading a different
profile, or otherwise ensure every required word belongs to the new profile.

### Operation configuration

A valid idle start latches:

- `config_bank`: the seed bank to use;
- `config_groups`: number of root vectors, 1 through 65,536;
- `config_active_lanes`: number of low active lanes, 1 through LANES;
- `config_period`: zero for no periodic reseed, otherwise a power of two
  through 65,536;
- `config_step`: a canonical Montgomery recurrence multiplier below P.

Start requires loaded seeds for every active lane and every context in
`0 .. min(4,groups,nonzero_period)-1`. With period zero, omit the period from
that minimum. An invalid configuration or missing seed produces immediate
done/error without entering busy. Error remains set until the next start.
Seed errors are independent, non-sticky pulses.

## Request and response timing

`request_valid && request_ready` accepts a vector request. Only acceptance
advances the group counter. The accepted tag is returned unchanged. For a
request accepted at edge t, root_valid, root_group, root_tag, root_mask, and
the packed roots are registered immediately after edge t. A downstream
butterfly samples them at edge t+1, exactly as it samples synchronous data
RAM q. This is not an extra four-stage delay on the current root.

Active logical lane zero is in the low 32 bits. Inactive output lanes are
zero and absent from the registered mask. On a bubble, valid/mask clear while
root data and tag/group hold. The generator sustains every-clock requests
once started; bubbles are optional producer gaps, not downstream stalls.

The current root is selected from the context seed when its position in the
period is below four. At later positions it comes from either a completed
context update or the matching multiplier result returning this clock.
Selection covers all four contexts after every wrap, including periods 1,
2, and 4. The caller must supply an identity step for short-period profiles
or otherwise use the explicit repeated seed semantics correctly; the seed
selection itself does not rely on speculative cross-wrap update results.

Each accepted current root simultaneously enters one frozen sparse Montgomery
pipeline to compute that context's next value. The helper registers its result
three edges later. A context reused four request edges later bypasses that
result directly: it does not wait for the separate context-store write on the
same edge. If bubbles delay reuse, the stored result is available instead.
Four-stage context tags align writeback and bypass with the helper output.

## Completion and restart

After the last accepted vector, ready drops and four drain clocks are counted
before done and busy deassertion. Extra requests during this drain are ignored.
The drain prevents old helper results from reaching a new configuration, even
when its start arrives on the next edge after completion. Cached seed banks
remain valid across completed operations and can be switched on restart.

For G vectors and B producer-bubble clocks before the final acceptance,
the measured busy count is `G+B+4`. If the first request follows immediately
after start, its registered response appears one clock after that start;
there is no internal arithmetic setup delay. All seed-loading clocks occur
before start or overlap work in the inactive bank and are excluded from this
busy counter.

A cold profile needs one clear request and U serial seed writes, followed by
start and the first request. If clear is at edge zero and writes occupy edges
1 through U, start can occur at U+1 and the first registered root at U+2.
There is no embedded seed ROM or automatic profile prefetch controller in
this prototype. The caller must supply those requests. A small operation can
finish before the next seed set is fully loaded; tests complete any remaining
inactive-bank writes while idle before selecting that bank.

Reset clears both seed-valid maps, recurrence availability, helper valids,
outputs and operation state. Seed/context data arrays themselves are not
reset. A start after reset must reload the required seeds; stale data cannot
be used merely because the arrays retained their bits. Tests reset during
all four update-pipeline occupancy depths and during the final drain.

## Resource scope

There is one additional sparse Montgomery pipeline per elaborated logical
root lane. This module has no external seed ROM and makes no fitted DSP or
M20K claim. The earlier proof's seed-table capacity estimates are not the
complete register count of this bubble-capable prototype.

The source currently declares 32-bit data arrays: two banks of four seed
vectors (`256*LANES` bits), four stored update contexts (`128*LANES` bits),
and one output vector (`32*LANES` bits). At LANES64 these total 26,624 data
bits, before multiplier pipeline registers, validity maps, counters, tags,
and control. Valid values need only 27 meaningful bits, but any physical
elimination of upper bits must be checked in synthesis rather than assumed.
Two banks enable one-port prefetch without replication of the entire seed
table per arithmetic lane. Actual routing/clock and area remain unmeasured.

## Verification evidence

The final report has status `passed` at
`/home/jtl/gfn-fpga-lab/agent-work/root-rtl/fpga/artifacts/full-v2-final/report.json`.
All runs were on aethia with two build workers in a 6 GiB/no-swap/two-CPU
systemd scope. The NTT, core, sparse multiplier, and original proof sources
were not edited; no Quartus run was performed.

The generator was elaborated at LANES16 and LANES64 for each of P=104857601,
69206017, and 67239937. Each combination tested 304 butterfly/twist/post
profiles covering every runtime N from 2 through 65,536. Golden roots came
from modular powers at the frozen engine's independently reconstructed
physical bank/row demands, then were mapped to logical root lanes. They did
not come from stepping the candidate recurrence.

The six suites completed 3,648 operations and checked 1,044,828 registered
vector responses containing 20,387,520 active root words. They inserted
261,795 producer bubbles, checked 233,412 explicit idle seed accesses plus
concurrent prefetch/arbitration on every busy clock, aborted 306 operations
with reset, and rejected 348 invalid/stale-seed starts. Every completed
operation checked `cycles=groups+bubbles+4`, with no downstream request stall.

Coverage includes continuous bursts, randomized bubbles at feedback reuse,
all four contexts after periodic reseeds, periods 0/1/2/4/8 and larger,
small-N masks, ordinary post roots, held start while busy, active-bank mutation
rejection, inactive-bank write/clear during generation, and cached-bank restart
on the next edge after done when prefetch has completed. Tests also check
reset cancellation at each helper occupancy depth, final drain cancellation,
ignored excess requests during drain, invalid full-width seed values, bad
lane indices, and required-seed validity after reset.

All ten injected faults were detected: missing bypass, wrong context tag,
reseeding only context zero, no periodic reseed, accepting a bubble as a
request, allowing active-bank writes, checking a truncated seed value,
premature drain completion, wrong response tag, and retaining seed validity
through reset. The first full run's classifier did not recognize the correctly
detected feedback-backpressure message; the final test-only correction also
made the intentionally truncated-seed mutant's comparison width explicit.
The normal RTL was unchanged between the full runs.
Read-only review by the NTT owner found no context-tag, bypass, writeback,
drain, or seed-prefetch hazard; the start-priority contract above records its
one documentation clarification.

## Source identities

- Prototype: `c8adc265915192807efee46799a782f1649a4408313098baaed8b4a808afeb9e`
- Sole RTL dependency, `genefer_montgomery_mul27_sparse_pipe.sv`: `501d0ce309a3915f7aed0f3bde14ba1ee8d56ddc5f6abef1f2f5bb572d64db4b`

The interface and one-edge response convention were reviewed with the NTT
and core owners before implementation. Future integration must explicitly
specialize the root profile or define a new seed API; it must not pretend to
retain arbitrary cached-root writes.
