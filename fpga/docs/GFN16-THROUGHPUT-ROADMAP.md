# GFN16 weak-GPU throughput roadmap

2026-09-29. This is an engineering budget, **not an achieved FPGA result**.
Keep GFN16; do not pivot to sieving. Target total completed main-task throughput,
with comparable proof/checkpoint work, not merely a fast butterfly or proof check.

## Current measured simulation and target

The integrated single-butterfly-per-field square needs 2,424,980 clocks on its
five chained full-size random cases, including conversion, roots, CRT and carry.
At a hypothetical 100 MHz, 1,911,814 iterations take 46,361 seconds. Integrated
The first integrated 100 MHz-constrained fit reports 95.61 MHz Fmax and misses
setup by 0.459 ns; at a conservative 90 MHz the planning estimate is 14.309 h.
The 150 MHz-constrained experiment is pending. Standalone fits are not substitutes.

The provisional targets are 600 seconds, then 300 seconds. The latter is loosely
grounded in a qualified historical GTX 1050 Ti report; see
[GPU evidence and limitations](GFN16-GPU-TARGET.md). No GPU parity is established.
The current model needs 77x/155x acceleration to those targets. Four lanes alone
cannot supply that improvement.

## Architectural sequence and gates

1. Remove both bit reversals with DIF-forward/DIT-inverse. Separate RTL passes;
   integrated option is being regression-tested. Approximately 196k clocks saved.
2. Four butterflies/cycle using eight conflict-free banks, then measured scaling
   to 8/16/32/64 lanes. Preserve total data capacity; test every stage's root and
   data-bank routing. Resource and Fmax scaling will not be assumed linear.
3. Independent coefficient splitting plus five-state carry prefixes, replacing
   the wide sequential carry dependency. Mathematical model passes exhaustive
   small cases and full-size exact max-digit convolution cases; RTL remains
   under development. Width-prune only with proven input bounds.
4. Cache immutable roots across squares. They depend on field and N, not candidate
   radix or exponent bit. Store twist N + forward N/2 + inverse N/2 + fused-post N
   = 3N words per field. Compared with one N-word table, this adds approximately
   768 M20Ks across three fields, while eliminating ~262k steady-state root-fill
   clocks. Cold initialization and reset invalidation must be measured separately.
   This storage estimate is not a fit result. Prefix intermediate RAM is additional.
5. Widen conversion/CRT/readout together with carry RAM; fuse conversion+twist and
   final postconversion+CRT where useful. Scalar interfaces otherwise set the floor.
   Scalar conversion plus scalar CRT alone cost about 2N clocks: ~42 minutes over
   the example exponent at 100 MHz even if all other work were free.
6. Reuse butterfly multipliers for pointwise operations when phases are disjoint,
   instead of permanently duplicating both arithmetic banks. Fit before promoting.

## Illustrative end-state budget, not an implementation promise

For B butterfly/pointwise lanes per field, no reversals, seven drain clocks/stage:

`A(B) = 2*16*(32768/B + 7) + 3*(65536/B + 5)`.

At B=64, that is 19,695 arithmetic clocks. Add illustrative 16-lane two-pass carry
(8,192), 16-lane CRT transfer (4,096), and 64-lane conversion (1,024): roughly
33k clocks/square before extra pipeline/control/proof work. Cached roots are
assumed warm. At a **hypothetical** 200 MHz, this scale would approach five minutes
for the example candidate. This demonstrates the order of parallelism needed,
not that the design can meet its area, bandwidth or frequency constraints.

DSP budgeting is a major gate. The current engine uses separate butterfly and
pointwise multipliers; replicating both wastes area across non-overlapping phases.
Similarly, unpruned pairs of fully pipelined 96x96 reciprocal products multiplied
by dozens of carry lanes may exceed the device. A convincing solution needs an
integrated fitted resource allocation, not independent best-case lane counts.

Stop treating local speedups as the objective once fixed overhead dominates.
Every promotion must report full-square cycles, supported data bounds, source
hashes, simulation evidence, integrated memory/DSP/ALM use and timing. Complete
PRP/proof generation, board I/O and physical operation remain separate milestones.
