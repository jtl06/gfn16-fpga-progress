# Final NTT-to-CRT forwarding: bounded design and schedule proof

Status: design analysis and independent event model only. No NTT, wrapper, core,
CRT or carry RTL was changed. This is not a measured speedup or a 200 MHz claim.

## Existing boundary and coefficient order

Frozen atomic27 core `47f61c26…35ce` (folded clone `081d352e…5c70`) runs five
operations: twist, forward DIF, pointwise square, inverse DIT, and postmultiply.
Only the final phase-3 `op=2` result is eligible for forwarding. Forward DIF has
bit-reversed spectral order, but inverse DIT restores natural coefficient order
before the postmultiply. Phase 3 removes the twist and inverse-length factor.

The post root is an ordinary, not Montgomery-scaled, residue. With R=2^32,
`Mont(R*N*x*psi^j, N^-1*psi^-j) = x mod P`; the forwarded words must therefore be
ordinary canonical residues for the existing CRT27. No extra conversion belongs
on this boundary. The model verifies this identity for all three fields and all
supported sizes, including endpoints and P-1.

The current core waits for all three NTT done signals, then makes N/16 ordered
host-vector RAM reads. CRT has 61 stages, accepts a row every clock, and has no
output backpressure. The existing CRT phase is `ceil(N/16)+62` clocks. Carry v2
receives coefficient writes while idle and starts only after the final one.

Each pointwise arithmetic packet contains L consecutive logical coefficients,
but `product[lane]` is in physical-bank order. With K=log2(2L),

`bank(a)[bit] = XOR of address bits j for which j mod K = bit`.

For a packet-aligned base and offset j<L,
`bank(base+j) = bank(base) XOR j`, and every word has row `base >> K`.
Capture the packet base/bank tag with the read; do not use the current producer
base while older values return. The ordinary host-vector XOR read route can be
reused to restore logical order, if its controls are privately tagged.

## Three alternatives

1. **Direct 16-to-16 tap:** forward a registered canonical final result row to
   CRT. With the currently guaranteed continuously-ready CRT, one row register
   suffices. Arbitrary downstream stalls would instead require issue credits for
   every in-flight arithmetic result, or a deeper FIFO; the multiplier pipeline
   cannot be stalled retrospectively. This is the simplest 16-lane option.
2. **Unrestricted 64-to-16 FIFO:** a producer packet arrives every cycle, while
   consumption takes four cycles. A registered non-fall-through FIFO reaches
   `N - 16*(N/64-1) = 49,168` queued coefficient triples at full N. At 96 bits per
   triple this is 4,720,128 data bits: at least 231 M20Ks by bit count alone,
   before real port/packing constraints. This is not a small skid buffer.
3. **Recommended 64-lane prototype: read committed output RAM using spare bank
   halves.** Keep all existing final writes. A postmultiply reads one L-bank
   half per clock. Request a completed L-word output packet only when its half
   is not used by the current arithmetic read. Serialize it through two common
   packet slots into four 16-word CRT rows. This overlaps the existing readback
   work; it does not eliminate all of its reads.

The third option requires no extra full-vector memory. Two 64-word triple
packets hold 12,288 payload bits, plus addresses/masks/valids. This is a logical
buffer requirement, not an inferred RAM/DSP/ALM prediction. The buffer can be
registers initially; physical placement and sharing of the existing host read
route must be measured before selecting an implementation.

## Concrete proposed protocol

Keep the ordinary host API unchanged when forwarding is disabled. In a new
candidate, enable the side stream only for the final phase-3 operation.

- An internal common coordinator maintains next packet base, next 16-word row
  base, completed/committed prefix, two slot reservations, and the operation
  epoch. Bases count logical coefficients, not physical banks.
- Each field exposes a side-read grant/registered packet response, with
  `{epoch, packet_base, lane_mask, canonical_words}`. Arithmetic read/write
  scheduling and ordinary NTT done stay separate from stream-drained status.
- A side read may target only a packet committed on an earlier edge. Never use
  an implementation-defined same-address mixed-port read/write result. Each
  bank gets at most one read and one write per edge.
- Grant only if all three fields can accept the same descriptor and a slot is
  reserved. Reserve on request, not response. One-cycle RAM return/capture is
  included in the two-slot credit count.
- Join all three matching field packets before presenting CRT input. Require
  identical valid, epoch, base and mask; any skew is an error, not permission to
  advance whichever field arrives first. The existing field pipelines have
  equal latency, but the join must assert this explicitly.
- Serialize offsets 0,16,32,48 for L=64 (only offset0 for L=16). Clip inactive
  lanes for N<16. Advance the row only on an all-lane CRT-ready acceptance;
  hold payload and tags while blocked.
- Current CRT27 ready is continuously asserted after reset. If a future CRT
  can backpressure, stop side reads when slots fill; arithmetic may finish
  because every result still resides in its original output RAM. Do not attach
  arbitrary backpressure to a direct arithmetic tap without in-flight credits.
- Gate coefficient writes with their ordered CRT output count, not NTT done.
  Allow those writes during the final NTT operation and its drain. Conversion
  has already completed, so no source digit remains unread at this point.
- Start carry only after all N rows have been committed, NTT arithmetic has
  completed, no side response remains in flight, and the stream is drained.
  Reject new root/host mutations while the side stream is active, even if the
  arithmetic engine has already pulsed done. No new operation may reuse RAM.
- Reset clears all coordinator reservations, packet valid bits, CRT valid
  eligibility and epoch tags. Any field error aborts the whole operation,
  suppresses further coefficient writes, invalidates roots and enters the
  existing reset-required failure quarantine. Do not treat stale post-reset
  responses as new-operation data.

## Independent event model and exact modeled savings

`reference/ntt_crt_forward_schedule.py` models the frozen bank function, point
read sequence and 7/8-clock arithmetic commit distance. It checks all AW1..16,
L16/L64, always-ready and deliberately stalled consumers: 128 schedules, plus
262,140 packet-layout checks and full bank/row bijections. Every read occurs
after commit, no arithmetic/side read ports overlap, no packet is lost or
duplicated, and at most two slots (including in-flight reads) are reserved.

At full N, the two-slot RAM-reader model has **zero CRT input bubbles for L64**,
once the first row starts. L16 shared-RAM reading has 204 bubbles in this model;
the direct 16-to-16 tap is preferable if its fixed-ready contract is retained.

Edge convention: final-operation start is edge0; packet g is read at 1+g and
committed at 1+D+g. Side reads require a strictly earlier commit, and their
packet capture is not consumed on the same edge. CRT writes into carry occur
61 clocks after CRT input acceptance. These conservative registered boundaries
are part of the model, not inferred from an unspecified combinational bypass.

| Architecture | Existing warm clocks | Modeled saved clocks | Modeled warm clocks |
| --- | ---: | ---: | ---: |
| Frozen cached atomic27, 64/16, RAM side reader | 36,318 | 1,022 | 35,296 |
| Folded cached atomic27, 64/16, RAM side reader | 36,353 | 1,023 | 35,330 |
| Folded cached atomic27, 16/16, direct fixed-ready tap | 94,721 | 4,097 | 90,624 |

The 64-lane saving is about 2.8% at unchanged clock. Most of the 4,158-clock CRT
phase remains: the 16-wide consumer still needs 4,096 input rows plus pipeline
drain. The overlap hides roughly the 1,024-clock final producer pass, not the
entire CRT phase. Further clock loss from added routing could erase this gain.

These counts apply to the nonstreaming carry baseline. A precision-stream carry
core has overlapping setup/split work already; re-derive its critical schedule
instead of subtracting these savings blindly. If CRT latency changes but carry
stays nonstreaming, the common CRT tail cancels in this comparison; other
controller boundary changes still need their own measured gate.

## Recommended next gate, before any full-core rewrite

Build a new standalone final-post side-reader candidate, preserving frozen
engines. Check streamed logical words against the existing independent NTT
oracle and the final host-read RAM contents for all fields, AW1/4/16 and both
lane widths. Inject arbitrary ready stalls, per-field valid/tag skew, delayed
last packet, and resets at every request/capture/quarter/last-commit boundary.
Mutate the logical XOR route, request tag, read-port grant, commit watermark,
slot credit and field join. Only after that should a new core clone overlap CRT
inputs and measure whole-operation clocks. Physical fit must assess the added
data-RAM address mux and packet route, not merely the small buffer bit count.
