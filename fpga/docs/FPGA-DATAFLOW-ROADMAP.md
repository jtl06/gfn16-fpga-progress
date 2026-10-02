# FPGA-specific dataflow optimization roadmap

The user approved pursuing all of the pipeline and algorithm experiments below.
This is an implementation queue for the active project, not an unattended
scheduler, authorization for extra instances, or a claim that any proposal wins.
Existing cloud allowances and manual spending checks remain unchanged.

## Current integration boundary

Preserve the frozen atomic27 cached core and earlier fitted FAST16 baseline.
New component tests earn an integration trial, not automatic baseline promotion.
Compare exact warm/cold square cycles, final integrated timing, raw resources,
and steady-state candidate throughput. Keep sources, test vectors, failed runs
and gate/fit provenance. Do not combine component Fmax values into a core claim.

## Ordered experiments

| Experiment | Current state | Required next evidence |
| --- | --- | --- |
| CRT-to-carry streaming with precision carry | Frozen full16/64 gate passes; 64-profile1,101 operations/19 faults; warm90,521/32,153 clocks | Matched whole-core fit, prepared/staged but not yet launched |
| Simpler NTT routing | Folded component full64 gate passes; separate core integration being implemented | Unchanged arithmetic, exact added cycles, integrated area/clock/throughput |
| Generated-root seed prefetch | Full16 and full64 all-field gates pass; 990 operations and 5 targeted faults | Physical fit, then memory-versus-logic integration decision; cached roots still use fewer arithmetic cycles |
| Local adjacent-stage fusion/radix4 | Authorized, next architecture experiment | Independent modular-transform proof, bank-conflict schedule, register/local-buffer costs, exact fullN RTL comparisons |
| Final NTT postconversion directly into CRT | Authorized, design pending | Preserve coefficient order, handle64-to16 width conversion and backpressure, measure eliminated passes and buffer costs |
| Multiple candidate states/interleaving | Abstract resource-owned event schedule implemented/tested; one versus two complete NTT data sets | Independent model review, actual port/context controller design, RAM packing and fit costs; not implemented RTL |
| Rebalanced lane counts / smaller engines | Authorized, design pending | Compare equal-device-budget designs using aggregate completed candidates/second, not single-square latency alone |
| More regular streaming or hybrid NTT | Authorized architecture experiment | Model stage reuse versus replication/delay buffers; RTL prototype only after credible resource and schedule estimates |
| Lazy modular reduction | Authorized bounded arithmetic experiment | Prove all redundant ranges; preserve DSP mapping or account for wider products; validate exact NTT/CRT boundary normalization |

The faster pair-step CRT is separately correctness-gated and component-fitted.
Integrate it after the carry/routing deltas are attributable; its extra32 latency
clocks and reset boundary changes must remain visible.

The cached atomic27 NTT16 whole-core baseline now has a completed fit:
83.32MHz reported Fmax, 193,133 raw ALMs, 946 raw DSPs. Its worst setup paths
are second-divider quotient to carry suffix (about12.08ns data delay), supporting
the precision-carry integration priority. It still misses its100MHz constraint.

`synthesis.compare_integrated` compares known atomic27 profiles only after each
passes the exact source/profile/geometry checks and has its own completed fit.
It requires matched physical controls and cold/warm case selection, explicit
planning clocks below each fitted Fmax, and records phase deltas and changed
RTL. Synthetic tests of this comparator are not new fit evidence. The generic
component comparator remains strict about identical arithmetic profiles.

## Dependencies and success criteria

Inside an NTT stage the existing multiplier pipeline already accepts work each
cycle. The main opportunities include avoiding extra memory passes, simplifying
permutations, overlapping blocks and sharing them across independent candidates.
Successive squares of one candidate cannot be freely overlapped because the
next transform depends on the previous normalized residue. A multi-candidate
experiment must preserve independent base, digit, carry, root-cache and error
state and cannot count duplicated work as throughput.

Local radix4 fusion should be tried before a wholesale full-width streaming
rewrite. A fully replicated pipeline can greatly increase arithmetic and
buffering requirements. Neither high utilization nor maximal lane count is a
success criterion by itself; fewer operations and simpler wiring may win.

## Issue-capacity model for the frozen64-lane core

For the existing radix2 schedule atN65536, two transforms perform
`N*log2(N)` butterfly multiply requests per field, and twist/square/postconversion
add`3*N`:1,245,184requests per field. At64 requests per clock this is19,456
ideal issue clocks. The measured warm core spends19,743clocks in its NTT phase,
including controller boundaries, out of36,318clocks for the square.

Consequently the scheduled useful-issue count is98.55% of NTT-phase capacity,
but53.57% of the entire square's corresponding lane-clock capacity. These are
an arithmetic request-count model, **not measured DSP switching or device-wide
utilization**. It counts even products by trivial constants as requests under
the current algorithm.

Removing every NTT-phase bubble without changing arithmetic work could save at
most287clocks, below0.8% of this whole square. Adding pipeline registers alone
therefore has little cycle-count headroom inside this already-pipelined stage;
it can still improve Fmax or routing. Stage fusion should target memory passes,
physical wiring, or arithmetic simplification rather than promise large gains
from eliminating drain bubbles alone.

For independent candidates, an idealized disjoint-phase pipeline would have
interval at least19,743clocks if the existing NTT remains its bottleneck. The
36,318/19,743≈1.84 ratio is an optimistic scheduling bound, not a projected
implementation speedup: it assumes conflict-free buffers, independent state,
unchanged clock and no extra resource bottleneck. Same-candidate dependencies
and shared RAM ports prevent assuming this overlap for free.

### Refined buffer-ownership experiment on precision-stream64

`reference/candidate_overlap_model.py` uses the frozen measured warm phases:
conversion4,105, NTT19,743, CRT4,158, carry tail4,147, total32,153.
The event model serializes each candidate's dependent squares, reserves a data
set from conversion until CRT drain, and reserves postprocessing through carry
completion. Five tests check engine exclusion, candidate ordering, data-set
ownership and resource bounds. This is a software architectural model, not RTL
simulation; it assumes redesigned access interfaces and hidden setup/control.

With two independent digit contexts but one NTT data set, that shared storage
still serializes conversion+NTT+CRT: at least28,006clocks per completed square,
an ideal scheduling ratio about1.148 versus32,153. With two independently
accessible full NTT data sets, the NTT bound becomes19,743clocks, ratio1.629.
The constructive100-round/two-context schedules average28,026.735 and19,805.05
clocks respectively, including fill/drain. No clock improvement is assumed.

The second configuration adds6,291,456 logical NTT data bits (three fields,
65,536 words,32bits each) plus2,097,152 digit-context bits:1MiB total. These are
not M20K counts or proof of fit; metadata, muxes, queues, packing and physical
routing are excluded. Here a data set means a complete three-field coefficient
store, not one of the existing engine's internal physical banks. The frozen
engine explicitly disallows host data access while computing, so controllers
alone cannot realize the second configuration. Near-full whole-core logic
placement also makes its added routing cost important.

Evidence: `results/throughput-20260929/core27-stream-full64/overlap-feasibility.json`
records the normalized gate SHA and selected sample. Do not add these ratios
to the measured progress chart or multiply them by unrelated component wins.

Independent review confirms that32-bit canonical digit contexts suffice only
if the one postprocessing engine retains exclusive ownership of its transient
CRT/carry scratch through completion. Per-context base, exponent, error and
controller metadata remain necessary; complete proof/checkpoint/Gerbicz state
is not counted. These are square-recurrence contexts, not complete prime-test
contexts. Reconfiguration must wait for old post tokens to drain, and releasing
an NTT data set requires all RAM read responses to have drained into independent
CRT tokens. These are implementation proof obligations, not existing features.

## Immediate lazy-reduction width constraint

For the existing primes104857601,69206017,67239937, canonical residues fit27bits,
but every complete redundant range[0,2P) requires28bits. Thus a general
redundant-residue interface cannot be passed unchanged into our canonical
27-bit sparse Montgomery multiplier. A first bounded experiment should consider
redundancy within addition/subtraction paths with normalization before multiply,
or explicitly measure the cost of a wider multiplier. It must not truncate a
redundant residue or silently assume the one-DSP mapping survives.

The mathematical idea is supported by Harvey's redundant-residue NTT work:
https://arxiv.org/abs/1205.2926 . Streaming permutation networks and local dataflow
are relevant architectural references, not transferable speedup claims:
https://past.date-conference.com/proceedings-archive/2026/DATA/64.pdf .
