# Streaming coefficients directly into carry

`genefer_carry_prefix_stream` is a standalone experimental alternative to the
frozen `genefer_carry_prefix_vector_pipe_v2`. It consumes ordered CRT coefficient
vectors directly into the first reciprocal-divider pipeline, rather than first
writing and rereading a 96-bit coefficient RAM. It retains the signed 33-bit
intermediate RAM and stores final digits in a signed 32-bit RAM. No integrated
core source selection is changed by this candidate.

## Stream contract

The existing `start`, size, base, status, and scalar/vector host ports remain.
The new coefficient input ports are:

| Port | Meaning |
|---|---|
| stream_valid | Producer offers one coefficient group |
| stream_ready | This clock can accept one group |
| stream_addr | AW-bit logical address of lane zero |
| stream_mask | LANES-bit exact active-lane mask |
| stream_data | LANES signed 96-bit coefficients, lane zero in the low bits |

A transfer occurs only when valid and ready are both high at the clock edge.
Start latches the size and base, then performs the existing 97-clock bound and
reciprocal setup. Ready stays low during setup. Once ready rises, it remains
high until all expected groups have been accepted, unless reset or an error
terminates the operation. Thus a non-stallable CRT pipeline can deliver one
group per clock after its producer has observed readiness. Producer bubbles
are allowed; an incomplete stream waits indefinitely for its missing groups
until reset. There is no automatic timeout or implicit zero filling.

Groups must arrive in order at addresses `0, LANES, 2*LANES, ...`. The mask
must contain exactly all active lanes: all ones when N is at least LANES,
or the low N bits when N is smaller. Unlike the idle host interface, zero and
partial masks are not valid stream groups. Inactive-lane data are ignored.
The final accepted group is inferred from the latched N; no last flag is needed.
Ready drops after this acceptance while the divider and output pipelines drain.
Requests while ready is low have no effect, including requests after the final
group. The producer must obey ordinary ready/valid holding rules when stalled.

An accepted group with the wrong address, wrong mask, or any out-of-range
active coefficient ends the operation with done/error. The full row is checked
before any first-divider lane receives a valid input, so a partially invalid
row cannot enter the arithmetic. Earlier valid rows may have updated the
intermediate RAM, but no final-digit write happens until all groups pass.
Subsequent operations must supply a complete new stream.

## Arithmetic and storage proof

The supported domain is unchanged: N is a power of two from 2 through 65,536,
`2*N+4 < b <= 1,000,000,000`, and every signed 96-bit coefficient obeys
`abs(a[i]) <= 2*N*(b-1)^2`. The coefficient guard compares the entire signed
96-bit input against the bound before selecting the signed 78-bit divider
input. Both Euclidean divisions, negacyclic redistribution, five-state carry
composition, special minus-one representation, and output pipeline are the
same arithmetic as the frozen narrow/pipelined candidates.

For a valid operation, each ordinary output digit lies between zero and b-1,
which is less than 2^30. The special result consists of -1 followed by zeros.
Every output therefore fits signed 32 bits exactly. Reads sign-extend the
stored 32-bit word back to the original signed 96-bit host representation.

Idle host writes retain their 96-bit ports but must be exact sign extensions
of signed 32-bit values. A wider scalar value rejects that write; a wider
active vector lane rejects the entire vector write. These failures pulse
host_error without RAM mutation. This is a deliberate, explicit restriction
of host storage, not a restriction of the full 96-bit coefficient stream.
All signed 32-bit initial values remain storable, including values that are
not canonical digits. The core can validate them against the newly accepted
base during conversion; checking against a prior base at load time would break
no-reset radix changes.

The vector host priority remains write, read, scalar write, scalar read.
Invalid vector requests suppress scalar fallback. Zero/partial host masks
remain legal and clip to N. Host accesses and host errors are suppressed
while busy or starting. Synchronous read-valid timing is unchanged.

With static AW16 storage, raw RAM bits fall from `129*65536 = 8,454,144` to
`65*65536 = 4,259,840`, saving 4,194,304 bits. Smaller runtime N does not shrink
elaborated RAM capacity. For an elaboration with fewer words than lanes, each
bank still has one physical word and inactive lanes are masked. Actual M20K
counts, area, routing, and achieved clock require a physical fit.

## Ordering and reset safety

The input-group counter advances only on a legal handshake. The received-group
counter, previous quotients/remainders, and ordered transfer summary advance
only when the second divider produces a valid row. Both dividers have fixed
latency and accept bubbles, so relative group order is preserved. The existing
first-two-digit wrap correction and five-state prefix composition therefore
see precisely the same sequence as a contiguous RAM-fed pass.

On error, late divider outputs are ignored outside SPLIT. Any new valid start
performs 97 setup clocks before reentering SPLIT, more than enough to drain the
two seven-stage dividers. Reset cancels pipeline valid state and gates RAM
access. Neither reset nor an early stream error clears digit RAM; a reset
during emission can leave a partial result, which must not be used as a
completed normalization. Completion still follows the last actual digit write.

## Cycle scope and integration

With no producer bubbles after readiness, measured busy clocks are
`2*ceil(N/LANES)+117`: 32,885 for N65,536 at four lanes, 8,309 at sixteen lanes,
and 119 for N2 at either tested width. Each producer bubble while ready adds
one clock. These counts include the 97 setup clocks but exclude host traffic.

This is only one standalone clock less than pipe_v2. The larger intended
system benefit comes from overlapping coefficient ingestion/division with
CRT output, removing the separate coefficient-staging phase. It is not a
halving of the standalone normalization schedule. The core owner agreed that
setup can start after conversion finishes and overlap NTT/root work; residue
reads must not launch until ready guarantees capacity for every CRT result.
Those core scheduling changes and an end-to-end throughput measurement are
separate work. No clock-frequency or complete-PRP speedup is claimed here.

The child cycle counter includes every busy clock, even while ready and waiting
for a producer. If setup starts during NTT work, that interval overlaps the
core's other phase counters and must not be added to them. End-to-end square
clocks and exclusive core phases are the appropriate system measurements.

## Validation evidence

The final source-hashed report has status `passed` at
`/home/jtl/gfn-fpga-lab/agent-work/carry-stream/fpga/artifacts/stream-v3-reviewed/report.json`.
All runs used aethia, two build workers, and a systemd scope capped at 6 GiB
memory with no swap and a two-CPU quota. No Quartus run was performed here.

Four- and sixteen-lane candidates each passed AW16/full-size and explicit AW1
elaborations. In total, the four main suites completed 12,062 normalizations,
218 arithmetic-domain rejections, 28 malformed-stream rejections, and 34
reset aborts. Host scoreboards checked 5,917,850 accesses; producer tests
inserted 585,638 bubbles. An additional AW17 test rejected sizes 0, 17, 18,
and 31, then successfully normalized N2. All valid runs checked exact cycle
counts, including producer bubbles.

The independent Python whole-integer oracle corpus includes N65,536 extrema,
random coefficients, both signs, minimum supported bases and base 1,000,000,000,
canonical minus one, recurrence, and real reference square postprocessing
vectors. Repeated completed operations change size/base without reset, then
restream canonical outputs to check normalization idempotence. Tests hold the
first valid packet across setup backpressure, verify that no downstream stall
appears once ready, inject malformed traffic when not ready, and check final
drain plus scalar/vector host suppression while busy.

Protocol tests cover wrong, repeated, and skipped addresses; zero/partial
stream masks; and high signed 96-bit violations. Inactive stream lanes contain
large garbage values to verify masking. Reset tests target setup, divider
occupancy, truncated streams, and final emission. Pre-emission resets preserve
the previously stored digits. A rejected row with earlier divider work in
flight is followed on the very next edge by a different-base/N start, without
reset; the resulting digits and cycle count are checked.

Eight injected defects were rejected: missing mask check, missing address
check, missing full-width bound check, accepting without valid, accepting past
the last row, lost stored sign bit, unsigned read extension, and missing scalar
host-width validation. Read-only peer review found no protocol or arithmetic
issue and prompted the immediate-restart test above.

## Frozen implementation

- `genefer_carry_prefix_stream.sv`: `67ab9b601a83b9d8bb3d6425daefb786f6eb7359d2f1827fa16be298f9184071`
- `genefer_div_recip_narrow.sv`: `eef327cee81d41895a068b746a3715daba95d43bea919edbddf9b498ecfc38bf`
- `genefer_sp_ram.sv`: `b97d2f43db1b1e1aa60b9b7fc2b720af1e302bd5ff9e35854c89b30e5fb610df`
- `genefer_carry_transfer_tree.sv`: `b18e39ebcaf2a1b514e0b617170dc1491a576772fe94ff3cf55316feee09971c`
