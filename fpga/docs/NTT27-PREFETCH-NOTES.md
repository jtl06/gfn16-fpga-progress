# Isolated generated-root seed prefetch candidate

This is a separate RTL candidate, `genefer_ntt_banked27_prefetch_engine`.
It does not replace any frozen source or square-core selection. After explicit
scoped user approval, RTL simulation ran on aethia. Both full-N 16/64-lane gates
pass all three fields, exact whole-integer CRT, every runtime size, reset/profile
recovery and source-integrity checks. All five targeted fault mutants are
rejected. Component fits are now available below; no whole-core throughput
claim is made.

The frozen generated controller remains
`e21c86e5decde7b4e14a4cdd138c10f02b95c8beb147729d52ebf52d9bbefd1f`;
the recurrence component remains
`c8adc265915192807efee46799a782f1649a4408313098baaed8b4a808afeb9e`.
Both hashes were checked after creating the candidate. Montgomery R is still
2^32, and the compact profile format and all sparse27 field constants are
unchanged.

## Schedule and expected bounds

Let `G=ceil(N/(2*LANES))`. Stage s needs
`U=min(4,G,period(s))*min(LANES,2^s)` seed words, where period is one below
stage `log2(2*LANES)` and `2^(s-log2(2*LANES)+1)` thereafter. One clear edge,
U seed requests, one step request and its response occupy U+3 clocks.

The first stage still pays the frozen U+4 setup clocks, including its separate
recurrence-start edge. At ROOT_START it captures an independent descriptor for
the following stage and starts clearing/loading the inactive bank on the next
edge. The descriptor contains bank, stage, transform size, phase, profile key,
active lane count and context count. The step value has separate storage.

The current stage provides G issue clocks plus seven writeback drain clocks.
The next STAGE_SETUP observes whether the descriptor is ready and matching;
otherwise ROOT_WAIT counts residual setup. The recurrence is always started on
a later ROOT_START edge, after the stage controls and step have been registered.
Each later stage therefore exposes `1+max(0,U-G-4)` setup clocks. Background
profile reads are not added to exposed setup or whole-operation clocks.

At N65536, G is 2048 for L16 and 512 for L64. Both cover all following-stage
loads. These five-phase arithmetic counts are now measured in RTL, matching
the independent schedule model for all three fields and four full-size cases:

| Lanes | Frozen generated | Prefetch measured | Clocks removed |
|---|---:|---:|---:|
| 16 | 79,771 | 78,340 | 1,431 |
| 64 | 24,987 | 20,548 | 4,439 |

Cold profile upload, data transfers, CRT, carry and physical clock effects are
excluded. The L64 result still exceeds the cached engine's 19,733 arithmetic
clocks. This remains a RAM/arithmetic tradeoff; prefetch alone does not establish
a better full-chip design.

`reference/ntt27_prefetch_schedule.py` checks an explicit request/response edge
model against the exposed-cycle formula for all N2..65536, LANES1/2/4/8/16/32/64
and both stage orders: 224 cases passed locally. It does not simulate RTL.

## New RTL boundaries

The new profile loader shares the original single profile RAM port and issue/tag
registers. Initial loading and background loading are mutually exclusive.
The recurrence's existing inactive-bank write contract is unchanged. The active
generator captures its own step on start, while the next step is held separately
until its descriptor is consumed. A stage change does not recompute a pending
profile address from live current-stage controls.

Only one operation is active. Profile begin/write/commit requests while busy
remain rejected, so a profile cannot change underneath a prefetched descriptor.
Reset invalidates profile eligibility and clears loader state/read validity.
Every new start clears pending prefetch state. Final stages and root-free
normalization do not launch further loads. Host arbitration, root ordering,
pointwise phases, canonical input assertions and seven-clock RAM drain are
copied from the frozen generated implementation.

Assertions check matching stage/bank/size/phase on descriptor consumption and
reject active-bank background writes. These assertions supplement, rather than
replace, independent exact transform and whole-integer tests.

## Completed validation

New `reference/ntt27_prefetch_regression.py` reuses the frozen independent
pow-based profile producer, DFT comparisons and whole-integer CRT oracle.
Its new C++ benchmark adapter replaces only the cycle model and DUT type.
The runner is restricted to aethia, limits address space to 6 GiB, builds with
two workers under the established shared compile lock, and refuses new builds
below 10 GiB free disk. Lock waiting has a separate 900-second bound; compilation
and each simulation retain a 180-second bound. Output directories must be new.
Reports record executable hashes, P/Q/R=2^32 and mutation provenance, and recheck
the source hashes before marking the gate passed.

The initial AW1/L16/all-field and AW10/L16/field1 gates passed. Tests cover every runtime
size in each elaboration, all forward/inverse and DIF/DIT combinations, separate
pointwise operations, cached profile replacement, host fuzzing and repeated
exact negacyclic squares. Small-N reset tests abort at every operation edge in
both stage orders, including background loads and exposed waits. Five targeted
mutants attack active-bank selection, inverse-stage key, recurrence step,
response tag (background loading only) and premature READY. AW10 covers real recurrence periods above
four and actual unhidden setup.

The final reports are under
`results/throughput-20260929/ntt27-prefetch/`, copied from the same directory names
under `/home/jtl/gfn-fpga-lab/agent-work/ntt27-prefetch/fpga/artifacts/`:

| Gate | Passed steps | Scope |
|---|---:|---|
| quick-v2 | 36 | AW10/L16/P1; all five targeted faults rejected |
| wide-small-v2 | 78 | AW10/L64/all fields; exact CRT |
| wide-aw1-v1 | 48 | Explicit AW1/L64/all fields; exact CRT |
| full16-v1 | 96 | AW16/L16/all fields; every runtime size and exact CRT |
| full64-v1 | 96 | AW16/L64/all fields; every runtime size and exact CRT |

The two full-size gates total 990 completed operations, 11,017,488 per-coefficient
checks and 2,982 reset aborts. Each field's four full-size square cases has the
same measured five-phase count. Exact cycles and all data/root/butterfly/drain
counters are checked. An independent read-only RTL review found no seed-bank,
descriptor, response-valid or short-stage scheduling issue.

The original `wide-small-v1` combined reset sweep exceeded its 180-second
subprocess bound after normal arithmetic passed. Its report/logs are preserved,
with an adjacent `outcome.json` explaining the original report's unfinished
status. The next runner partitioned the same exhaustive reset cases by operation,
retaining the same per-operation time limit; no RTL correction was needed.
Whole-core integration remains pending; the later component fits do not replace
that requirement.

The candidate RTL hash is
`9381ff17205c65f5b34ba355b845e15fa25cc7ce1370f81160c147aea51c4a9c`,
benchmark hash
`7fadaaa7d32c80f91be878055300c9496412ace40f254d003e0d9dc2a281e585`,
runner hash
`ab616c009a7743d4ea6939811c80ef7a1dafed167760d3157147cdefd78712e9`.
The final source archive is `artifacts/quick-v2/source-snapshot.tar.gz`,
SHA256 `7fd714f635af06d0594f4e505e73ecc535627546b7f7076e2f62492b9979cce1`.
Report hashes are:

- full16-v1: `8ee6ad19a74e7d4f74816b9521e02da981003614103655452282a756979587f4`.
- full64-v1: `1e4a3868f3cf26da36e955acb177e11d3423ecd6e8016179ae8faaa165d96d59`.

## Completed physical comparison: 64 lanes, field 2

The September30 Quartus Pro26.1 fit passed the10ns clock constraint with
setup slack+0.397ns, hold slack+0.016ns and reported Fmax104.13MHz. This is a
single-field component virtual-I/O probe on the provisional Arria10 device,
not a board clock, an all-field clock guarantee, or an integrated PRP estimate.

`results/throughput-20260929/ntt27-prefetch64-p2-fit/` preserves the compiled RTL,
constraints, reports, execution receipt and log. Quartus and summary generation
both returned0. `matched-generated-comparison.json` independently checks both
passed simulation source closures, identical field/AW/lane configuration,
four-worker projects, QSF controls, SDC, flow, and Quartus version against the
archived generated64 field2 fit.

| Quantity | Generated | Prefetch |
| --- | ---: | ---: |
| Reported Fmax |104.08MHz|104.13MHz|
| Raw placed ALMs |105614|101091|
| Packing-adjusted ALMs needed |94511|89752|
| Raw DSP blocks |128|128|
| Registers |66204|66346|
| RAM bits |2383680|2383680|
| M20K blocks |224|224|

The raw placement reduction is4523ALMs, about4.3percent. The0.05MHz difference
does not establish a reproducible clock improvement from one fitter seed.
Combined with the independently measured24987→20548 arithmetic clocks, this
is encouraging component evidence: fewer clocks without a demonstrated clock
or resource penalty relative to generated roots. Cold profile upload and all
non-NTT phases remain excluded. The cached-root architecture still uses fewer
NTT clocks, so this does not establish which whole-core design is faster.

The separate16-lane field1 component also passed100MHz (reported110.34MHz,
setup+0.937ns, hold+0.021ns); do not borrow that clock for64 lanes or other fields.

## Supporting sources

The separate fixed profile-ROM producer passed simulation but its first
AW16/L64 physical probe hit Quartus's default5000 constant-loop guard while
initializing8738 words. A second entity-scoped10000 setting was ignored by
Pro26.1 (the synthesis report still showed5000); both failures are archived
under `root-profile27-rom/fit-v1` and `fit-v2`. A fresh third probe uses the
documented project-global `VERILOG_CONSTANT_LOOP_LIMIT 10000` only when the
ROM source is present. It passed synthesis and entered fitting. All three
use identical RTL SHA072487e042b3fc70bcda656ef80cfe0965b350f01fa605baa695c4df5af1c754.
This setting only permits constant elaboration; it changes neither arithmetic
nor timing constraints. ROM inference is recognized; physical cost/timing is
not established by synthesis alone. See the [Quartus settings reference](https://www.intel.com/programmable/technical-pdfs/683296.pdf).

The third probe subsequently completed08:02:46UTC with Quartus/summary exit0.
`root-profile27-rom/fit-v3/` contains source-hashed reports and execution
receipts, all reverified locally. Field2/AW16/L64 standalone result: reported
Fmax211.95MHz, setup+5.282ns andhold+0.021ns at100MHz;0DSPs,16rawALMs,
32registers,279616RAMbits,32M20Ks. Packing-adjusted38ALMs includes27
unavailable minus5recoverable ALMs; do not label it raw placement. The
synthesis report confirms effective constant-loop limit10000. This verifies
constant arithmetic was elaborated into ROM rather than runtime multipliers.
It does not certify other fields or the whole-core clock. Integration retains
the child's compact profile RAM in addition to this producer ROM.

Subsequent separate field1 and field3 fits also completed successfully, archived
as `root-profile27-rom/fit-p1-v1` and `fit-p3-v1`. Parent verification checked
each manifest field, RTL hash, all launch control hashes (excluding only the
vendor-added LAST_QUARTUS_VERSION line), result/context hash and both zero exit
codes. All three standalone field variants report0DSP/32M20K/279616RAMbits,
16rawALMs and32registers; each passes100MHz internal setup/hold and reports
211.95MHz Fmax. The standalone virtual-I/O result does not time the ROM output
through the future consuming core's profile RAM, and is not an integrated
clock guarantee. Do not sum component Fmax values or substitute them for a
whole-core fit.

The isolated whole-core preparation target is now
`square_core27_stream_prefetch_ntt64_carry16`: exactly16 RTL sources, original
61-stage CRT, precision-stream carry,64NTT/16host lanes and32-bit Montgomery
radix. Its new diagnostics replace rather than relabel the old four-table
cache counters. No full-size physical run is authorized by preparation alone.

The integrated estimator recognizes the separate
`atomic27_stream_precision_prefetch_v1` contract. A cold profile has8738 words
per field and8743 root-phase clocks atAW16; a warm profile has zero upload
clocks. Seed setup is already inside the measured NTT phase and must not be
added again. A fitted-clock projection still requires passing full-size
source-matched square evidence, positive hold margin and the candidate's own
completed whole-core fit; the current small gate cannot provide that.

Cross-architecture comparisons explicitly record the different diagnostic
virtual-pin assignments and ROM elaboration guard, validate their exact known
forms, and compare all remaining constraints/tool/worker/seed controls. They
match cold/warm residency semantics, not unlike encodings(15 table-cache bits
versus1 complete compact bundle). Different diagnostics may themselves affect
placement overhead; this is not an identical-netlist or board comparison.
Synthetic full-size/fit fixtures exercise these rejection paths only; they are
never saved as performance results.86 focused preparation/estimator/comparator
tests passed after this integration, including a review-requested bool/int
sample-counter hardening fix.

The immediate feasibility evidence is the already-tested two-bank contract in
[ROOT-RECURRENCE27-NOTES.md](ROOT-RECURRENCE27-NOTES.md) and the serialized
costs in [NTT27-GENERATED-ROOTS.md](NTT27-GENERATED-ROOTS.md).
Harvey's [NTT arithmetic paper](https://arxiv.org/html/1205.2926v2) explains
that transform-root precomputations can be reused. The precise overlap schedule
here is a project-specific inference, not a speedup claimed by that paper.
