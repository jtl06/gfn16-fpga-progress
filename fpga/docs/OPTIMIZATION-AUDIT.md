# GFN16 arithmetic optimization audit — 2026-09-29

> The original audit below is historical. See the dated wiring/congestion
> follow-up at the end for the current parallel whole-core architecture.

Work runs on aethia using Quartus Prime Pro 26.1.0 build 110 and Verilator.
The device is the **provisional** `10AX115N4F40E3SG`, not a verified card.
All projects are compute-only, with virtual data/control pins and an arbitrary
physical clock pin. There is no assembler, bitstream, or hardware programming.

## Changes and evidence

1. **NTT RAM inference:** the original 256-point probe synthesized to an
   estimated 17,066 ALMs and 9,772 registers. The main data array did not infer
   as block RAM. The original fit hit its 600-second bound; it is not a timing
   result. Explicit dual-port addresses, mutually exclusive reads/writes and
   collision-free scheduling now infer M20K data RAM. The root table has one
   shared read port. A running twiddle index replaces address multiplication.
2. **Carry division:** the original 96-bit `/` and `%` failed vendor synthesis:
   `lpm_divide` supports numerator/denominator widths only through 64 bits.
   The replacement performs four restoring-division bits per cycle, followed
   by a separate signed correction stage. Already-canonical positive digits
   take a fast path. The 96-bit signed floor-division semantics are preserved.
3. **CRT:** the original fitted design used 3,446 ALMs and 9 DSPs, with reported
   Fmax 11.01 MHz (it failed the 100 MHz constraint). A shared sequential
   remainder unit removes the three wide constant `%` networks. Additional
   registers separate modular differences, products, and additions; all input
   operands are captured before internal arithmetic. The current acceptance
   interval is 59 cycles, checked explicitly in simulation.
4. **Square scheduling:** combine inverse normalization, untwist, and conversion
   out of Montgomery representation into one multiplication table/pass. The
   fused sequence uses 8,716,032 cycles per field versus 9,502,464 originally,
   an 8.28% cycle reduction (about 1.09× operation-rate improvement at equal clock).
   This changes the host-orchestrated simulation schedule, not an integrated
   on-FPGA PRP controller.

### Interface detail

NTT and carry host writes now take priority over simultaneous host reads;
`read_valid` is low on a write. During internal operations the read-data output
may change while invalid. Callers must consume it only with `read_valid`.
RAM output registers are not reset; contents must be reloaded after reset.
The two NTT data ports never perform observable cross-port read/write collisions.
The `no_rw_check` attribute does not waive any valid read's expected value.

## Verification

- Full independent three-field forward/inverse transform tests through N=65,536.
- Zero, -1, wraparound, maximal-digit, random and full-size modular squares;
  both conditional-double choices compared with Python whole-integer arithmetic.
- Fused and original full-size schedules compared directly for all three fields.
- 90 focused CRT/carry cases, including negative exact/nonexact division,
  large centered coefficients, six radices, and canonical -1.
- Reset cancellation, hostile inputs while busy, write/read priority, exact
  transform counters, exact CRT latency, and carry cycle/status checks.
- All seven existing injected RTL defects are detected.
- Resource-report and performance-model tests reject missing fit evidence,
  negative hold slack, unsupported clocks and stale RTL hashes.

All 33 Python tests pass. The full RTL regression is recorded in
`artifacts/opt-engine-20260929-v6/report.json` on aethia; source hashes match the
final fitted RTL. Earlier candidate/failure logs are preserved separately.

## Final standalone fits

| Block | ALMs | DSP blocks | M20K blocks | Reported Fmax | Setup slack at 100 MHz |
| --- | ---: | ---: | ---: | ---: | ---: |
| Multiplier | 207 | 2 | 0 | 150.90 MHz | 3.373 ns |
| NTT, full N=65,536, P1 | 1,599 | 4 | 256 | 107.18 MHz | 0.670 ns |
| CRT, pipelined serial reduction | 917 | 7 | 0 | 112.94 MHz | 1.146 ns |
| Carry, full N=65,536 | 1,689 | 0 | 384 | 100.01 MHz | 0.001 ns |

All four fit and pass internal setup/hold checks at 100 MHz. **Carry has essentially
no timing margin**; this is one seed, one provisional part, not robust timing
closure for an integrated board. The initial sequential carry reached 87.74 MHz;
separating sign correction raised it to 100.01 MHz. The initial sequential CRT
reached 75.01 MHz; pipeline cuts raised it to 112.94 MHz while reducing DSP use.

The probes intentionally have critical warnings for the unassigned clock pin/
I/O standard and unused transceiver channels. Reset is false-pathed and virtual
I/O is not a host-interface timing sign-off. Standalone multiplier input-to-first-
register paths are not fully constrained; the NTT fit times its registered
operands driving the instantiated multipliers.

Machine-readable evidence: `results/audit-opt-20260929/fitted-summary.json`.
Use actual fitted counts, not the occasionally malformed Quartus synthesis
ALM estimate for inferred RAM.

## Compute-only performance model

For the tested GFN16 base **604,832,956**, at an assumed common **100 MHz**:

- Each field's fused square: **8,716,032 cycles**.
- CRT for all coefficients: **3,866,624 cycles** (59 per coefficient).
- Carry: **2,031,643 cycles**, two sweeps, for each tested exponent-bit choice.
- Serial field scheduling: **32,046,363 cycles / 0.3205 seconds per square/dup**.
- Proposed three-field-parallel scheduling: **14,614,299 cycles / 0.1461 seconds**.
- About 1,911,814 exponent bits gives roughly **7.1 days** serial or **3.2 days**
  with three parallel fields for a PRP-style exponentiation, before omitted costs.

These are **planning estimates, not measured hardware throughput**. The parallel
controller is not implemented, only P1 NTT timing is fitted, and neither estimate
includes transfers, root-table reloads, CRT staging, control overhead,
checkpoint/proof generation, or PrimeGrid integration. The carry timing margin
also argues for a lower initial clock or more optimization before hardware.
No primality result or PrimeGrid performance claim is made.

Summing three P1 NTT fits plus CRT/carry gives **7,403 ALMs, 19 DSP blocks and
1,152/2,713 RAM blocks (~42.5%)**. This is not an integrated fit and includes
only one active root table per field. Keeping all four root-table variants
resident would consume substantially more RAM. External DDR is not required
by these arithmetic arrays alone; system-level storage remains unverified.

Machine-readable model: `results/audit-opt-20260929/performance.json`. Its guard
checks fitted timing limits and RTL hashes against the passing regression.

## Remaining scope

The NTT controller is still serial: one butterfly is issued every seven cycles.
P2/P3 functionality is tested, but only P1 has a separately fitted NTT instance.
Summing three P1 resource reports is a planning estimate, not an integrated fit.
Root-table transfers, PCIe/DDR, PRP sequencing, checkpoint/proof generation and
PrimeGrid allocation/result protocols remain unimplemented.

The next performance target is overlapping butterfly operations with conflict-
free RAM scheduling (currently one issue per seven cycles), then integrating
the three field lanes and measuring the whole core. The present changes make
the arithmetic synthesizable and much smaller; they do not yet make it a
competitive prime-search accelerator.

## Wiring/congestion follow-up — 2026-09-30

User priority is now reducing congestion and improving useful whole-core
throughput. Later explicit authorizations permit AWS fits and GCP simulation
within their existing budgets; the original aethia-only audit above is not the
current resource policy. Baselines and failed attempts remain preserved.

| User checklist item | Current evidence/status | Next isolated check |
| --- | --- | --- |
| Pipeline, fanout, narrower logic | Tiled64 completed at99.40MHz versus folded64 at87.89MHz;100MHz setup still fails by0.060ns. Its worst path is root RAM to root-selection register,10.110ns with7.224ns interconnect. | Target root-path locality/pipeline separately; data-RAM-only27-bit candidate passed its small gate and remains separate from the fitted prefetch source. |
| Placement/floorplanning | Whole16 RAM placement inventory now captures384 logical NTT memories and their physical block coordinates. It shows scattered slices, not measured route lengths. | Combine placed RAM/DSP/register locations with critical paths before choosing regions; no unmeasured hard rectangles applied. |
| Resource balancing | Original cached whole64 failed routing congestion, not compiler-host RAM. Whole16 root RAM already trims to27 bits; data RAM remains32. | Reduce unnecessary data-path demand first; do not assume moving DSP work into already-congested ALMs helps. |
| Clock management | Current compute-only probes have one kernel clock; no generated fabric clock is introduced by these changes. | Preserve clock/enable discipline and recheck clock/hold reports; this is not board-level clock sign-off. |
| Hierarchy | Post-fit audit found all112 logical tiled control bits represented by179 physical registers, with no out-of-tile pairing/orientation arithmetic endpoints. Hierarchy alone is not physical locality. | Root-bank selection still has broad reach; inspect RAM-to-consumer wiring before partitions or floorplan claims. |
| Tool settings/incremental work | Existing comparison keeps constraints, seed, tool and worker controls matched; archived snapshots remain immutable. | Separate recorded routability-setting experiment only after selecting a suitable baseline; incremental reuse must not conceal source/settings differences. |
| Sharing/TDM/memory usage | NTT butterfly multipliers already serve pointwise operations. Prefetch replaces large cached root tables with compact profiles and recurrence. | Compare whole-square cycles/Fmax/area; further sharing is useful only if reduced congestion offsets the extra cycles. |

The source-hashed placement inventory is
`results/throughput-20260929/core27-stream-ntt16-fit/ram-placement.json`, from
fit-report SHA2561354a0b21afbf969e10ebc16fae4ec8ba3222f9572fa2b61e71292c088bf80ac.
Its parser has five focused tests and makes no timing/locality-improvement claim.
All96 data banks are2048x32 (384M20Ks); all288 root banks are2048x27
(864M20Ks). The worst root path therefore does not have five unused live bits
waiting to be removed. Data narrowing is a separate surrounding-congestion
experiment; at64lanes512-deep data banks may retain the same M20K count.

Official tool guidance: [Quartus optimization modes](https://docs.altera.com/r/docs/683296/26.1.1/quartus-prime-pro-edition-settings-file-reference-manual/optimization_mode?contentId=uMuScsk88VOeEDLmgik7Jg)
distinguishes placement/packing routability effort from performance effort,
with extra compile cost. The reference is26.1.1; our compiler is26.1.0, so
actual setting acceptance/effect still needs verification. Region capacity and
connectivity must be checked before constrained placement: merely packing a
module more tightly does not prove less congestion.

### Experiment checkpoint — 2026-09-30 08:58 UTC

The completed tiled component has positive hold slack0.018ns but still fails
100MHz setup. Its maximum pairing-control reachable register endpoints fell
from5504 to688. These are transitive endpoints, not direct net loads; neither
this eightfold reduction nor the reported Fmax ratio is a whole-core speedup.
See `ntt27-tiled64-fit/control-audit-v1/` and `diagnostic-comparison.json` under
the current throughput results directory for immutable physical evidence.

Whole-core prefetch correctness passed at32968 warm clocks versus32153 for
the cached precision baseline. Its isolated AWS slot-a fit is running; the
additional815 clocks require a compensating clock/area/routability benefit.
The checked fused-NTT component separately passed63 full-size steps across
all three fields; parent independently checked every step log, complete
archive hash and five-source fit closure before launching slot-b fitting.
The other two whole-core64 fits remain in slots c/d. Each job has four
disjoint physical cores, four Quartus workers and a24GiB memory ceiling.
No new whole-core clock or candidate-throughput result is asserted.

### Root-network pipeline candidate — RTL only

`genefer_ntt_banked27_rootpipe_engine.sv` is a separate clone of the frozen
tiled engine, not a change to any running fit. It inserts a register after
three of the seven root-XOR dimensions at64 lanes, followed by the remaining
XOR dimensions and rotation into the existing root register. Operands,
pointwise roots, local controls, valid bits and writeback rows are delayed
together; RAM read-to-write distance changes from8 to9 clocks. Host access
timing and the six-stage arithmetic primitive are unchanged.

The independent cycle equation predicts five-phase arithmetic19768→19803
clocks (+35, about0.177%). That is not yet an RTL measurement. Matching only
the old component throughput would require a clock ratio greater than
19803/19768, with both setup and hold passing. It says nothing about the
eventual integrated clock, board performance or full PRP runtime.

Ten combined source-delta/permutation tests passed locally. They exhaust
XOR controls/rotations for supported bank counts and include witnesses for
misaligned tail controls, but are not RTL simulation. Independent RTL review
and simulation, including small-N/pointwise/reset/writeback alignment, are
required before physical fitting. No placement-locality improvement is yet
claimed; the added register bank can itself increase placement pressure.

Initial candidate SHA256:
`cab41579a4b96793f52c31a2864f74aeab3d023f23b50f5c8acce368f07d1967`.
Exact source-delta specification:
`reference/ntt27_rootpipe_structure.py`.

### In-progress whole-core congestion evidence

The running pair-CRT precision whole64 fit emitted estimated peak short-wire
demand of128% down,114% right,119% left and111% up in four different local
regions. A source-hashed log prefix and its execution context are archived at
`results/throughput-20260929/core27-stream-pair64-live-v1/`. The context was
checked against the frozen fourteen-source probe and its constraints. This
is explicitly an incomplete fit snapshot, not final resource utilization,
route failure or a clock result. The128% region is X0_Y147 to X7_Y153; it is
a diagnostic hotspot, not a proposed tight placement rectangle.

`synthesis/routing_demand.py` extracts these estimates with log SHA and line
numbers, retains repeated passes and labels missing estimates unknown rather
than zero congestion. Four synthetic parser tests pass. This makes future
comparisons traceable without treating the router's estimates as sign-off.

The separate row-decoder candidate's first AW1/L1 compile exposed a stale
simulation assertion reference. Failed evidence remains preserved; the fix
keeps the old address expression only inside simulation-only witnesses. The
revised smoke passed eight steps; parent rechecked all eight log hashes and
the source archive. This does not establish full-size correctness. Transfer
of its four new source/test files to GCP still awaits scoped user approval;
the tiny smoke used aethia. The root-network pipeline also entered its
independent aethia gate without changing any active fit.

### Matched tool-effort trial prepared, not launched

`probes/ntt27_tiled64-p1-cpu4-100-hpe-v1` uses the already-correctness-checked
tiled64 RTL unchanged. Its sole submitted QSF difference is:

```tcl
set_global_assignment -name OPTIMIZATION_MODE "High Performance Effort"
```

Altera's26.1.1 setting reference says this increases timing effort during
placement/routing and enables timing-oriented physical synthesis, with extra
compile cost. Installed26.1.0 Build110 must still confirm acceptance and the
effective value in Fitter Settings. The prepared manifest explicitly says
effective verification is false. Do not call it a placement-only experiment:
the mode also affects synthesis. No hard placement regions were added.

All four sources, field, seed1, device, four workers,10ns clock, virtual pins,
SDC and flow match the archived tiled64 experiment's pre-fit execution-context
hashes. The post-fit QSF contains a vendor-added LAST_QUARTUS_VERSION line;
comparison uses the recorded submitted QSF hash, not a broad ignore rule.
The baseline Fitter Settings records Balanced. Compare setup and hold across
corners, area, interconnect and congestion before selecting a winner. The
strict generic comparator remains unchanged and must not silently treat this
intentional mode difference as an identical-control RTL experiment.

The completed component has only one short-wire congestion grid above100%
(below the ten-grid reporting threshold), unlike the running whole-core
congestion case above. Its long-wire demand peak125% and long root connection
motivate this bounded trial before selecting hard floorplanning coordinates.
This prepared experiment is waiting for a fit slot; no fifth concurrent fit
or new VM has been launched.

### Root-pipeline mutation coverage gap — preserved failure

The first small pipeline gate completed its ordinary L1/L64 arithmetic tests
throughN1024 across all three fields, but the overall gate failed because a
deliberate point-root delay bypass was not rejected. Eight earlier mutants
were rejected; three later mutants had not run. This is a test-coverage
failure, not evidence of an arithmetic failure in the unchanged candidate.
The failed gate must remain failed and cannot qualify a physical fit.

At64 lanes, pointwise accesses normally alternate physical bank halves, so
the skipped delay can accidentally read the same retained RAM word. The
first consecutive same-half groups are127→128, crossing logical addresses
8128→8192 and physical rows63→64. A power-of-two runtime size must therefore
reachN16384 before this particular hazard is observable. The parent added
an independent bank-mapping unit test proving that boundary.

A separate recovery gate is authorized: unchanged baseline plus the same
mutant atAW14/L64 with distinct canonical data/roots and full output checks,
then the three unrun mutants. It must link the original failed evidence,
not overwrite it or weaken the rejection condition. The normal full-size
gate follows only after this coverage gap is closed and disk is rechecked.

### Recovery verified; full-size gate running

The directedAW14 control passed32768 output checks in265 clocks per phase;
the unchanged escaped mutant fails at index8128, exactly the predicted
folded-bank boundary. The remaining three faults were also rejected. Parent
independently rehashed375 archived evidence files through the composite
validator, checked324 recovery source members and recomputed every directed
expected product as lhs*rhs*R^-1 modP. Originalsmall-v1 remains failed.
See `results/throughput-20260929/ntt27-rootpipe/parent-recovery-review-v1.json`.

The new full-size entry pins the reviewed composite validator and rehashes
the retained executables and current frozen sources before building. Its
threeAW16/L64 models run on aethia with four compiler workers, CPU400%,
6GiB memory limit and one simulation thread. P1/P2 checks passed at this
checkpoint; P3 and final cross-field reconstruction remain pending. The
measured first-field five-phase sum is19803 clocks, as predicted. A matched
rootpipe physical probe is prepared but must not launch until the whole gate
and archive verify and a fit slot is free.

### Reviewed follow-on idea: input/twist fusion, not implemented

An isolated format-2 compact profile could absorb input Montgomery conversion
into twist: Mont(d,R^2*psi^i)=d*R*psi^i. Keep all raw-digit reducers and input
validation; change only key0's4*LANES seeds, while retaining recurrence step
R*psi^(4*LANES). Do not silently reinterpret format1 or mix this into active
prefetch, data-width or root-pipeline experiments.

The fitted stream16 ancestor attributes48 raw DSPs,5792.2 rawALMs and6866
registers to its48 input converters. This motivates a future footprint trial,
not a guaranteed net saving in the prefetch core. A registered replacement
would predict conversion4105→4102 and warm32968→32965 clocks for the recorded
two-pass cases: only three clocks saved, with all4096 input beats retained.
Require new ROM/profile/recurrence/cache/fault/full-bigint gates before any
integration or physical claim; existing scalarR2 tests do not qualify the
compact profile automatically.

### Routing checklist applied — 2026-09-30 10:10 UTC

Rank experiments by validated whole-core throughput, not a component MHz
headline or lower wire count alone. Preserve correctness, setup and hold;
compare submitted source/control hashes and report integration overhead.

| Technique | Project-specific action / status | Caveat |
|---|---|---|
| Pipeline long paths | Root routing cut passed all three fields at N65536, four bigint cases, and recovered mutation coverage. AWS slot b started its matched physical fit at10:08:31UTC. | Five-phase cycles19768→19803 (+0.177%); no new Fmax yet. |
| Reduce fanout | Tiled controls already shorten the logical distribution tree; inspect actual routed driver loads and span before another duplication change. | Reachable endpoints are not direct net fanout. Replication can add upstream wires. |
| Narrow storage/buses | Isolated27-bit residue RAM passes paired AW4/AW8/AW10 tests; full-size executor being prepared. | Keep32-bit Montgomery interfaces/radix and full-word input checks; do not truncate arbitrary intermediates. |
| Placement/locality | Use routed root-RAM→compute paths and resource columns to select a bounded placement experiment after pipeline fit. | No hard region coordinates guessed; an overly tight region may worsen congestion. |
| Balance resources | Inspect local M20K/DSP/ALM pressure, not only total percentages. | DSP→ALM substitution is not automatically helpful in an ALM/routing-limited core. |
| Clocking | Preserve existing synchronous compute clock and aligned control/valid stages. | No extra clock domains or blanket timing exceptions to conceal failing paths. |
| Hierarchy/incremental | Keep source-isolated components for diagnosis; retain whole-core physical gates. | Hierarchy alone does not guarantee locality; partitions can constrain cross-boundary optimization. |
| Tool effort | Unchanged tiled64 High Performance Effort probe is prepared, not launched. | Mode affects synthesis and fit; installed26.1.0 must verify acceptance. |
| Sharing/TDM | Consider only with measured idle capacity and an end-to-end cycle model. | Sharing can add muxes, wires and initiation-interval cost. |

Rootpipe full evidence: `ntt27-rootpipe/parent-full-review-v1.json` and
`ntt27-rootpipe/full-v1/verification.json` under the throughput results.
All66 full-gate steps passed; the historical small mutation-gate failure remains
preserved, with a separately source-verified AW14 recovery. Sourcecab41579…
is unchanged from that qualified gate. The launched fit uses four disjoint
physical cores4–7,24GiB and the existing six-hour job bound.

The paired-stage component has just completed: summary reports58.85MHz,
setup−6.993ns and hold−0.100ns at100MHz. It is physically fitted but fails
timing and is not a usable throughput improvement. Independent raw-report
review is pending. Its failure strengthens the need to evaluate routing
and control geometry alongside the small simulation cycle saving.

Vendor references: [register spread/duplication tradeoffs](https://www.intel.com/content/www/us/en/docs/programmable/683641/25-1/understanding-report-register-spread-data.html)
and [optimization-mode semantics](https://docs.altera.com/r/docs/683296/26.1.1/quartus-prime-pro-edition-settings-file-reference-manual/optimization_mode).
These guide experiments; they are not evidence of a speedup on this design.

### Paired64 critical-path review and metadata-only proposal

The completed paired64 archive is now independently verified:30 artifact
hashes, submitted controls, execution-context/result binding, all five RTL
sources against its passing full simulation report, and regenerated resource/
timing summaries. See `ntt27-pair-checked64-fit/parent-review-v1.json` and the
agent's detailed `archive-review-receipt.json` under the throughput results.

Two setup cones dominate: root RAM→butterfly input17.764ns with13.467ns
interconnect, and scheduler count→root RAM address17.130ns with14.022ns
interconnect. The latter includes count add/compare→read_group→root shifts
and a7.618ns final address wire. Hold−0.100ns is a separate row_tag pipeline
path. No short-wire hotspots above100% were reported; do not describe this
component as globally congested merely because its paths have long wires.

An isolated metadata scheduler prototype keeps all event validity, latency,
issue/hold/commit tags and reset behavior unchanged. It computes root group
and A/B selection from tick parity rather than the validity comparisons.
These two metadata outputs are explicitly don't-care when root_read is false;
no permission or RAM-enable check is removed. Frozen scheduler and engine
are unchanged, and no NTT engine selects the prototype yet.

Five pure model/source tests pass, covering widths1/4/8/16 and event schedules
through65536groups, invalid warmup subtraction, fault witnesses and exact
source/bench deltas. RTL simulation is pending. A code review found consumers
qualified by valid tokens, but full engine integration must still prove that
contract. Even after this change the final root address mux remains gated by
transform_read, so some count→address paths can remain. No cycle or Fmax gain
is asserted.

### Metadata gate terminal; data27 full-size replay started

The metadata-only scheduler now passes its standalone RTL gate on aethia:
182 normal runs,141 reset aborts,1,107,046 checks at widths1/4/16, plus all
nine targeted negative mutants. Parent independently verified27 log hashes,
12 executable hashes and all seven source archive members. Evidence is in
`ntt-pair-schedule-metadata/parent-review-v1.json`. This does not qualify an
integrated NTT or a physical speedup. Further paired-engine work must address
the separate root-data and hold failures, not only this address-cone change.

The data27 full-size runner passed15 local harness tests and a fresh remote
input audit. Its only post-review change tolerates disappearance of a compiler
temporary file during disk accounting; old full-v1 snapshot/audit is retained.
Full-v2 now builds only three candidate models and reuses source-verified
baseline models through diagnostic bench relinks. It requires all93 exact
counter/output pairs,24 malformed-input rejections and independent four-case
whole-integer checks on both designs. Actual compiler flags and generated
sources are checked, not just requested flags. No full-gate pass is claimed
while it is running.

The scheduler completed before this full replay started; its residual7.7MB
is included in free space. Scope `ntt27-data27-full-v2.scope` uses two compiler
workers, one model thread,CPU200%/4GiB, the shared compilation lock and a10GiB
disk floor plus remaining900MiB reservation. No other simulation reservations
were outstanding at launch. Do not start competing artifact-heavy work without
recalculating reservations.

The data27 physical probe is prepared locally as
`probes/ntt27_prefetch_data27_64-p2-cpu4-100-v1`, not transferred or launched.
It matches the existing prefetch64/P2 fit's field,AW16/L64/R32,seed1,four
workers,10ns clock,flow,QPF,SDC and normalized submitted QSF. The submitted
baseline QSF hash was reconstructed/verified before stripping only top/source
declarations for comparison; vendor post-fit version metadata is not silently
ignored by the generic comparator. Seven RTL sources preserve five common
modules and replace the top/add the27-bit leaf. Manifest59a7b4a5… and
QSF78e06357… are frozen. A full-v2 correctness pass remains a prerequisite.

### Future iteration-speed experiment: parallel normal-case pairs

`reference/paired_process_runner.py` is a new OPTIONAL helper, not selected
by the active full-v2 runner or any FPGA gate. Ten synthetic local tests prove
two commands reach a shared barrier concurrently, preserve exact outputs and
explicit fuzz settings, reject mismatches/nonzero exits, stop peers after
timeout/resource/spawn failures, and refuse pre-existing output directories.
The mandatory caller oracle runs after both processes finish; a zero exit code
alone cannot publish a successful pair. Each command has a private process
group, immutable argv receipt and separate log/dump. The final receipt is
atomically published without replacing existing evidence. Groups are reaped
only once, before potentially slow oracle work, to avoid a later PID-reuse kill.

This is process-level parallelism, not a multithreaded Verilator model. A future
aethia-only caller must validate two distinct physical CPUs, an aggregate CPU/
RAM scope, source/model pins and shared disk reservations. Existing malformed-
input tests remain explicit rejection gates; this helper intentionally treats
all nonzero returns as failures. No current gate was edited or restarted.

After current correctness work is terminal, a bounded A/B benchmark can reuse
the same pinned two executables and vectors: sequential versus concurrent
normal pairs, fresh outputs, identical oracle, repeated runs and peak aggregate
memory/CPU measurements. Ideal wall time changes from t_base+t_candidate to
max(t_base,t_candidate), but memory/cache contention and orchestration overhead
can reduce that benefit. No measured speedup or adoption is claimed yet.

### Planned whole16 clock audit, not another fit

`synthesis/postfit_core85_proposal.json` pins the completed whole16 project and
specifies a private routed-database copy, baseline100MHz STA replay, then an
in-memory85MHz clock override and explicit all-four-corner setup/hold/pulse
checks. It must preserve the original reset exclusion and report84 unconstrained
inputs/496 outputs; recovery/removal no-path results are excluded, not passing.
Only a successful native-tool audit could replace the current planning-clock
assumption with internal timing evidence. It would still not be an85MHz refit
or board/host-I/O signoff. Implementation/preflight and a free physical slot
remain required; no audit Quartus process has started.

### Root-pipeline physical result and routing priorities

The rootpipe64/P1 fit completed on2026-09-30 at10:45:41UTC. Its internal
100MHz target passes:104.30MHz reported Fmax,+0.412ns setup,+0.018ns hold.
The matched tiled64 ancestor reported99.40MHz and missed100MHz by0.060ns.
Both use64 DSPs and512 M20Ks; raw placed ALMs increase205 to117719 and
registers increase12961 to60364. Five-phase component cycles increase
19768→19803. Combining these cycle counts with reported Fmax gives an
estimated4.74% component throughput gain, not measured board throughput or
a whole-core result. Controls, source gates and resource comparison are in
`results/throughput-20260929/ntt27-rootpipe64-fit/matched-comparison.json`.

The new worst path is root_rotated[1][10]→arithmetic[43].butterfly|pre_w[10]:
9.760ns data delay,8.346ns interconnect (86%). The pipeline moved the critical
path downstream; it did not eliminate routing pressure. Reported peak long
high-speed routing demand is150%, versus125% for tiled. A successful route
does not mean all regional congestion improved.

Priorities for the user's routing checklist:

1. Test lane-local operand registers and bounded fanout groups at this measured
   register→DSP boundary. Align every valid/data/address tag and count added
   drain clocks; replication is deliberate here, not indiscriminate duplication.
2. Compare loose lane-cluster placement only after mapping DSP/RAM columns and
   endpoint locations. Avoid tight regions that remove placement freedom or
   force cross-region RAM traffic. Keep a same-seed unconstrained control.
3. Finish the independently running27-bit data-RAM correctness gate, then its
   matched physical fit. Storage-bit savings alone do not prove fewer M20Ks or
   less congestion.
4. Keep clocking unchanged. Hierarchy and incremental reuse are implementation
   aids, not evidence of timing improvement; preserved partitions can lock in
   poor placement. Compare physical settings separately from RTL changes.
5. Do not default to TDM or LUT multipliers: both can increase cycles or logic
   routing. Accept them only if measured full-operation throughput improves.

Whole-core rootpipe source and bench clones are prepared locally. Six structural
and cycle-model tests pass; no integration simulation or whole-core fit has run.
The cached whole-core ancestor has a7-clock drain, while tiled has8 and rootpipe9:
the whole-core NTT delta is70 clocks atN65536, not the35-clock component delta.
Predicted warm cycles32153→32223 require measurement before promotion.

The separate whole16/85MHz post-route audit's first two attempts stopped during
native API preflight, before project open; original routed files are unchanged.
Reviewed v3 adapts project_open/report_ucp to installed26.1 APIs, without forcing
database conversion or weakening timing/exclusion checks. This remains an audit
of a private database copy, not another fit or board timing signoff.

Vendor guidance supports inspecting the congestion map before imposing regions:
[Pro design-optimization guide, Chip Planner visualization](https://www.intel.com/content/www/us/en/docs/programmable/683641/24-2/chip-planner-visualization.html)
specifically identifies high fanout and overly restrictive floorplans as possible
causes. This is general methodology, not evidence that a particular new floorplan
will improve our design.

### Full-size data27 verified; whole-core rootpipe simulation started

Data27 full-v2 is terminal PASS:93 exact baseline/candidate pairs,24 invalid-input
tests and221 steps. Parent independently reran the archive verifier over1001
artifacts/88 source members, matched all seven RTL hashes to the prepared P2 fit,
and freshly reconstructed both sets of full-size dumps by CRT and whole-integer
modular arithmetic (four cases each). No physical resource/timing improvement is
claimed. AWS transfer of the12-file probe was blocked before rsync by the
permission reviewer; an explicit payload approval question remains pending.

Six regenerable PCH files from that completed new test were removed after an
inactive-scope check, shared compiler lock, pinned model/report checks and
before/after hashes of every retained file.492740608 allocated bytes reclaimed;
all objects, libraries, executables, sources and results retained. This does not
touch the separately blocked legacy cleanup.

The whole-core rootpipe normal-gate runner is now staged on aethia. Its first
AW1/L64 build/test uses CPUs0/2 (distinct physical cores), one simulation thread,
two compile workers,6GiB aggregate memory,CPU200%,512MiB reserved disk and a10GiB
floor. Twelve source/oracle harness tests passed locally and remotely. Every
reset test must interrupt the requested live phase, rather than silently reset
after completion. Runtime thread identity, fresh vector/segment hashes, exact
case order/readbacks, cache counters and phase-cycle accounting are required.
The source-only32-file archive and launch identity are retained in
`core27-rootpipe-stage-v1`. AW1 alone does not qualify the full-size integration;
AW5/AW7/AW16 and integration-specific negative tests remain subsequent work.

The first AW1 integration gate is now terminal PASS:529 operations/522readbacks,
including two small Fermat chains and reset recovery. Parent rechecked all nine
indexed artifacts,29 source archive members and all529 metric rows. Measured
NTT62 and warm CRT98 confirm the predicted tiny-size overlap; sample total222
cycles is not a full-size estimate. AW5 launched next with the unchanged snapshot
and same resource caps only after AW1 was terminal; no concurrent simulations.

### Next-cut review: benefit ceiling matters

Independent read-only review recommends a post-root_clip bank register as the
next isolated component experiment, not yet implemented. It separates the
broadcast/clip cone from lane pairing/orientation/mode selection. A fully selected
lane u/v/w register would be cheaper but leave that entire cone upstream.
AtL64/AW16, simple full32-bit versions add13603 logical register bits (bank cut)
or7490 (lane cut), including all aligned data/point/control/row tags. Neither is
a physical FF/ALM prediction or a locality guarantee. Both retain II1 and add35
clocks:19803→19838, so component break-even is about104.485MHz.

The same current STA report already has rotation_mid→root_rotated at9.706ns,
including8.820ns interconnect. Neither downstream cut fixes it. Holding other
placement effects constant implies a next ceiling near106MHz, not150–200MHz.
Any future experiment must inspect this path too; a marginal isolated Fmax
gain is insufficient evidence of a worthwhile whole-core change. Required
qualification includes all fields/orders/pointwise modes, small masks, reset
at new-stage/final-write boundaries, and missing-delay/stale-valid mutants.

### Rootpipe integration advances to full N; rootclip remains local RTL

AW5 passed560 operations/553readbacks/16aborts; AW7 passed12 operations/10readbacks.
The independent offline verifier now reconstructs integer squareDup results
without importing a simulator or the project vector generator. It checks exact
source/artifact hashes, segment reconstruction, command/model identities, all
cycle/cache counters and reset/readback coverage. AW1/5/7 are independently
verified; seven intermediate NOREAD steps at each tiny profile and two atAW7
are checked through the final chain readback rather than individually.

All six PCH caches from these completed three tests were safely removed after
locked, inactive-scope, pinned-report checks, reclaiming605925376 allocated bytes.
Models, objects, generated headers, source and results are retained unchanged.
The original full64 baseline build occupies343478272 bytes; the new AW7 build
occupied346275840 before cache removal. Full-N simulation has now started on
aethia with the unchanged32-file snapshot, CPUs0/2,CPU200%,6GiB memory and a
448MiB disk reservation plus10GiB floor. External headroom is only about35MiB
above that reservation, so no other simulation is allowed. The local preparation
oracle contains12 operations/10readbacks and hashes0270fe7b…; no full-size PASS
or new whole-core throughput result is claimed while the run is live.

The post-root_clip candidate is implemented separately with18 passing local
source/model checks (11 new plus7 ancestor checks). RTL3c0b76e6… adds an aligned
bank-register stage; frozen rootpipe remainscab41579…. No HDL compilation,
simulation, transfer, fit or integration of rootclip has occurred. Its15 planned
mutants are merely source anchors, not demonstrated negative-test rejections;
one pairing-delay mutation may be equivalent while stage controls remain stable.

Manual cloud estimates at11:33UTC remain inside approved budgets: about61.59USD
AWS and47.78USD GCP planning allowance after reserves, not actual billing. The
three existing whole-core AWS fits were confirmed live. No new AWS data27 fit
was launched; scoped payload approval remains pending.

### Higher-impact candidate: overlap two independent candidates

A read-only source/port audit and parent-rechecked abstract schedule identify a
potentially larger throughput gain than a marginal clock cut. With rootpipe's
predicted32223 warm clocks (19813NTT,12410 other phases), two candidates could
alternate NTT ownership while the other uses CRT/carry/conversion. The abstract
200-square/600-interval trace completes in3975010 clocks and has no overlapping
post/conversion intervals, supporting investigation of one shared carry scratch.
Steady aggregate gain would be1.626× at unchanged frequency; each candidate's
own round interval becomes39626, about23% slower. These are architecture bounds,
not validated hardware throughput.

This requires a second physically independent data-memory set, not merely a
high address bit: active NTT already uses both ports of each data bank. Existing
geometry implies another6291456 bits/384M20Ks across three fields. Root cache
can be shared only for an identical fixed size/profile. The current single FSM,
base/double-bit state and conversion-triggered carry_start must be redesigned;
after converting B the backend needs carry initialized for A. Continuous stream
acceptance, response/ownership tags and reset/error quarantine must be proven.
Scratch-only persistence also changes checkpoint/export behavior; preserving
both canonical arrays instead costs another256KiB plus ports/arbitration.
See `synthesis/two_context_rootpipe_proposal.json` for assumptions and hazards.
No RTL for this two-context architecture has been implemented or selected.

### Whole-core rootpipe full-size normal gate passed

AW16 completed on aethia; parent independently reran the offline whole-integer
verifier over11 artifacts/29 source members and12 squareDup operations with10
full65536-digit readbacks. The two NOREAD intermediate states are checked through
their final chained readback. Raw report56257648… confirms32223 warm and294375
cold clocks; warm phases are conversion4105,NTT19813,CRT4158,carry4147. Generated
oracleSHA0270fe7b… exactly matches the separately prepared local vector.
Build took125.26s; two simulation segments took286.97s and255.88s. Model thread1,
two compile workers,6GiB and448MiB disk reservation remained unchanged.

This confirms the predicted70-clock increase over cached stream64, about0.218%
more cycles per warm square. It is not yet a speedup: a matched whole-core clock
improvement greater than that is needed. Component104.30MHz cannot substitute
for a new whole-core fit. Using the existing1911814-step modeling convention at
base604832956, one cold operation plus warm repetitions totals61604644674 clocks:
12.079min at an ASSUMED85MHz or10.267min at an ASSUMED100MHz, excluding host/proof
overheads. Neither clock is established for this new core, and no full PRP ran.
Integration-specific fault qualification and physical timing remain pending.

The separately archived composite normal-gate receipt7c84398b… binds all four
profiles to identical29-source maps andseed20260929:1113 operations,1095readbacks,
18 intentional NOREAD intermediates and25 mid-operation reset-aborts. Its1113-row
baseline comparison records tiny-N latency overlap rather than assuming a uniform
penalty: AW1 adds10NTT clocks but removes10CRT reservation clocks, so total is
unchanged; AW5 adds26,AW7 adds34,AW16 adds70. AW7's historical quarter-control
vector hash was not originally recorded, so that comparison is explicitly bound
through the source-derived deterministic vector rather than mislabeled as a
historical hash match. Raw reports and unsuccessful historical gates remain intact.

### 2026-09-30 12:13 UTC — routing checklist and terminal whole-core failures

Both AWS cached precision-stream64 and pair-step CRT64 completed with Quartus
exit3, explicitly `Fitter routing phase terminated due to routing congestion`.
These were not six-hour timeouts or host-memory failures. Their14 source hashes
each match the archived passing correctness gate; execution-context hashes match
the terminal receipts. Reports and sources are retained under
`core27-stream64-aws-fit` and `core27-stream-pair64-aws-fit`.

| Whole core | Raw placed ALMs | Used LABs /42,720 | M20Ks /2,713 | Result |
| --- | ---: | ---: | ---: | --- |
| Cached precision-stream64 | 414,743 | 42,625 (99.78%) | 2,203 | Route failed |
| Pair-step CRT64 | 410,997 | 42,498 (99.48%) | 2,539 | Route failed |

Both report peak long-wire demand200%; neither establishes a clock. Prefetch64
was still running at12:13UTC. No retry or new remote fit was launched.

Apply the user's seven-part checklist as hypotheses, not blanket directives:

| Area | Current decision / next check |
| --- | --- |
| RTL pipeline, fanout, simplification | Prioritize removing word-wide mux layers and unnecessary routed bits. Rootpipe improved component timing; rootclip retains the mux networks and adds13,603 logical register bits per field, so it is not yet a congestion remedy. Replicate only measured high-fanout controls with local consumers. |
| Placement / floorplan | Inspect actual bank/DSP columns, path endpoints and congestion before loose cluster constraints. Do not squeeze near-full logic into tighter regions or invent coordinates. |
| Resource balancing | Retain DSP arithmetic unless a matched fit proves a better tradeoff. LUT multipliers consume the ALMs already under pressure. RAM bits alone hide M20K port/geometry fragmentation. |
| Clock management | Keep the compute core's existing single clock. Audit clock/enable fanout; do not introduce generated clocks as a routing workaround. Board clock/I/O signoff remains separate. |
| Hierarchy | Use modules for ownership and verification; preserved synthesis boundaries do not guarantee locality and may prevent cross-boundary optimization. |
| Tool settings / incremental compilation | One supported setting family per isolated fit; retain full clean-compile controls. Reusing a partition can freeze a bad placement. No new settings sweep launched. |
| TDM / memory / DSP | Sharing can reduce area but adds cycles and selection logic. Judge full-square throughput, not resource count. Prioritize existing generated-root/prefetch and data27 experiments before wider replication or two-context state. |

Vendor guidance explicitly warns that restrictive floorplans can cause congestion
([Chip Planner visualization](https://docs.altera.com/r/docs/683641/25.3.1/quartus-prime-pro-edition-user-guide-design-optimization/chip-planner-visualization));
it also explains cross-hierarchy optimization
([flattening hierarchy](https://docs.altera.com/r/docs/683641/25.3.1/quartus-prime-pro-edition-user-guide-design-optimization/guideline-flatten-the-hierarchy-during-synthesis)).
These sources support methodology, not predicted speedups for our design.

Promotion remains correctness and reset/tag alignment, successful whole-core
routing, setup/hold checks, then cycles divided by a supported integrated clock.
Rootpipe's component104.30MHz is not a whole-core frequency. The new failures
make footprint reduction a prerequisite, rather than a reason to add more
pipeline registers everywhere. AWS data27 payload approval is still pending;
the local simulation-harness review does not authorize that transfer.

### Rootpipe host-quarter integration fault detected

On aethia, a fresh run of the pinned AW7 control passed all12 operations and10
readbacks with unchanged counters. An isolated rebuild changed only the host
adapter's `read_group<=host_group;` to `read_group<=0;`. The mutant exited by
SIGABRT with the expected qualified whole-core line288 `residue mask skew`
assertion. The runner rejects unrelated errors, timeout/OOM, missing/duplicate
diagnostics and terminal PASS; its matcher and source/tool provenance were
independently reviewed before execution.

Raw receipt `core27-rootpipe-host-fault-v1/report.json` SHA256
`2b1bb49477bb8ea84e047554d169957d254b28723d4df23caaf1a3f9da49055e`
indexes12 durable artifacts,29 frozen sources and144 generated-source members.
Parent rehashed those artifacts/members after download. The compiler completed
in127.26seconds using CPUs0/2,CPU200%,6GiB memory and private `/dev/shm` scratch;
source, generated-code archive, executable and logs are durable. Scratch is
retained, not deleted. This is one targeted integration mutation, not a complete
fault matrix, physical fit, full PRP or board result.

Independent offline verifier `reference/verify_rootpipe_host_fault.py` now
verifies the actual archive, including exact compiler/source delta,31 source
archive members (29 baseline sources plus runner and mutant),144 generated
members, tool/executable/thread identity and a fresh ordinary-integer audit of
the12 positive-control operations. Parent reran its seven corruption/contract
tests plus three runner tests and the actual CLI successfully; the machine
receipt is `core27-rootpipe-host-fault-v1/verification.json`.

### Isolated R2 input fusion — local RTL/model evidence only

Four new format2 modules remove the48 standalone conversion multipliers from
the prefetch core without removing the48 digit reducers or signed-digit guards.
Input data remains ordinary canonical residues until the twist. Only phase0
seed constants gain an extra factor R; the recurrence step stays R-scaled:
`Mont(d, R2*psi^i) = Mont(Mont(d,R2), R*psi^i)`. Other transform/profile words
are unchanged. A distinct format2 ROM/core/child binding avoids interpreting
old format1 warm state as the new arithmetic domain. Profile labels are a
contract, not authentication of arbitrary uploaded contents.

Parent reran11 new source/integer-model tests and18 rootpipe/rootclip tests.
They cover786420 twist outputs across all3 fields/AW1..16/L16,64, complete
profile comparisons, small direct-transform/convolution checks, and exact
four-file transformations. Source-only mutation anchors are not RTL fault
tests. The new one-register boundary predicts conversion4105→4102 clocks;
the4096 input beats remain. Archived cached-core hierarchy attributes about
5249 ALMs/48 DSPs to the removed converters, but that is not a net-savings
prediction for prefetch. No HDL compile, RTL simulation, fit, default selection
or remote transfer has occurred. See `synthesis/core27_prefetch_r2_proposal.json`.

Independent read-only RTL review found no blocker to an isolated simulation
gate. Last-row RAM commit still triggers carry-start and the core transition on
the same edge; both move three clocks earlier together. A malformed standalone
profile begin raises an error but does not erase an already-loaded profile
(inherited behavior); format-rejection tests must not assume erasure. The outer
autonomous core exposes no profile upload port. Before running tests, a new
bench must replace old conversion-abort target `ceil(N/16)+9` with `+6` and
require `abort_reached && busy && !done`; the old unchecked ABORT path must not
be copied as evidence of reset coverage. HDL validation remains pending.

### R2 fusion N32 normal RTL gate passed; full-size gate started

The dedicated bench and wrapper now enforce measured conversion
`ceil(N/16)+6`, and every ABORT must reach a live requested phase before reset.
The separate runner retains the original pure integer vector generator and
adds four final-row digit-equals-base error cases. All37 source files were
verified against preparation manifest6404854a… before any project import,
then rechecked against the terminal report; no baseline files were overwritten.

AW5/N32 completed on aethia:568 operations,561 readbacks,7 NOREAD intermediates,
59 cold/509 warm runs and20 live aborts. Independent offline verification
replayed ordinary integer squareDup results, profile/cycle/seed accounting,
segments,37 source members,133 generated members and10 durable artifacts.
Parent reran the verifier and43 source/math/bench/runner/evidence tests.
Raw receipt155f9f9b… and the verified archive reside in
`core27-prefetch-r2-aw5-v1`. Compiler wall time87.17s; simulation82.25s.

All568 cases match the frozen prefetch baseline except conversion and total
cycles, each exactly3 lower. Original vector bytes are an exact prefix of the
new vector; only the four new invalid-final-row commands are appended. The
568-row comparison is archived beside the raw report. This establishes the
small-size cycle saving, not a physical resource or full-core throughput gain.

Sequential AW16/N65536 execution has started from the identical snapshot on
aethia, CPUs0/2,CPU200%,6GiB, one model thread, two compile workers,1800s per
command. Scratch is private volatile tmpfs; durable reservation64MiB sits above
the10GiB SSD floor. No scratch deletion is performed by the runner; only the
durable archive is relied on across sessions/reboots. Scope
`gfn-core27-prefetch-r2-aw16-v1` is separate from terminal AW5. No full-N PASS,
new fit/clock, full PRP, or area-saving claim is made while it is running.

### Fusion full-N normal gate independently verified

AW16 completed:12 squareDup operations,10 full65536-digit readbacks,2 NOREAD
intermediates checked by final chained readback,2 cold/10 warm operations.
Parent ran the independent ordinary-integer verifier successfully; receipt
`core27-prefetch-r2-aw16-v1/verification.json` binds raw reportc871241a…,
all37 approved sources,141 generated members and12 durable artifacts.
Warm32965/cold41708 clocks include conversion4102,NTT20558,CRT4158,carry4147;
cold profile setup adds8743. Build95.19s; simulation segments207.68s/237.77s.

All12 full-size cases match every common baseline metric except conversion and
total clocks, each3 lower. Baseline vector bytes are the exact prefix of the
new vector, followed by the four new invalid-final-row checks. At unchanged
frequency this is only0.0091% fewer warm cycles; removed converter hardware is
the intended physical opportunity, still unmeasured. No full PRP or fit ran.

Two old rootpipe AW16 PCH caches were independently inventoried, locked and
removed, reclaiming200359936 allocated bytes (191.08MiB).434 retained files
were hash-protected before/after, including every indexed result. Regeneration
is possible from retained headers/toolchain. Receipt:
`core27-rootpipe-stage-v1/aw16-pch-cleanup-v1.json`. No live fusion file was removed.

An independently reviewed directed mutation harness is now prepared, with its
first seed-domain invocation started on aethia under the same CPU/memory caps.
The known input impulse1636 atindex0 gives expected2676496, while a missing-R
twist produces a centered66-bit coefficient41972152391961575983 and predicted
first digit961575983. A second prepared test uses impulse1 atindex256: a wrong
phase0 recurrence-step radix produces coefficient2^64 atindex512, predicting
709551616 instead of1. Both avoid confusing arithmetic rejection with a
coefficient-overflow guard. A fresh passing full-size readback precedes each
mutant, and only its exact predicted digit/index plus unchanged cycle line
counts as detection. No mutation success is claimed before terminal evidence.

Both directed domain mutations are now terminal and independently verified.
Seed-domain raw report154dc308… observes exactly digit0=961575983 instead of
2676496. Step-domain raw report39cdf146… observes exactly digit512=709551616
instead of1. Each had a fresh passing65536-digit control readback, an exact
single-ROM delta, unchanged41708-cycle accounting and typed exit1 at the
predicted square mismatch. Neither relied on a crash, assertion, timeout or
overflow error. Each archive verifier checks14 artifacts/39 source members/
141 generated members. Receipts live beside the raw evidence in
`core27-prefetch-r2-fault-{seed,step}-v1`. This proves sensitivity to these two
specific faults, not a complete mutation/profile matrix.

The matched fusion fit probe is prepared locally at
`probes/square_core27_stream_prefetch_r2_ntt64-cpu4-100-v1` (21 files,168708bytes).
All16 compiled RTL hashes match the verified AW16 gate. Device,4-worker setting,
seed1,100MHz constraint,virtual pins,constant-loop limit,SDC,QPF and flow match
the existing prefetch baseline. ManifestSHAaba5974a…; QSF SHAb67c18c2….
Preparation tests passed38cases. No transfer/fit was launched; scoped permission
to copy and fit on the existing AWS worker is pending. No new VM, bitstream or
license copy is part of the request.

A separate read-only arithmetic audit identifies explicit27-bit zero extension
at the sparse multiplier output as a future isolated wire-width experiment.
With the actual54-bit product T, H=T>>32<2^22 and K=(mP)>>32<P, hence
`-P < H-K < P`; one conditional addition yields `[0,P)` below2^27.
Keep the32-bit public port and all timing/reset/hold semantics; do not narrow
the32-bit Montgomery correction m or the59-bit mP calculation. This does not
extend support to arbitrary32-bit inputs or establish physical savings.
Host writes, butterfly sums and seed storage are separate paths, so this alone
does not replace the existing data27-RAM experiment. No RTL change was made.

### Routing-first checklist following the user review

The seven proposed optimization categories are useful, but are not seven
independent switches to enable together. The immediate objective is a routable
whole 64-lane core with higher complete-square throughput, not a higher isolated
component clock. Cached64 and pair-CRT64 failed routing at 99.78% and 99.48% LAB
occupancy respectively; those failed placements establish no usable Fmax.
The existing prefetch64 system service was still active/running at this review
(Quartus fit PID17929). No running fit was changed or restarted.

| Category | Current evidence / decision | Next isolated check |
| --- | --- | --- |
| Pipeline / simplify / reduce fanout | Rootpipe component has a matched fit; whole-core rootpipe has simulation only. R2 fusion removes a separate conversion pipeline and passed full-N normal plus two targeted faults. | Measure fusion physical resources first; add local pipeline/control copies only on measured paths, keeping reset, valid, tags and cycle accounting aligned. |
| Placement / floorplanning | No whole-core locality win established; dense placements leave little room for hard regions. | Inspect congestion and DSP/M20K locations, then test loose bank/arithmetic clusters against unconstrained placement. Do not pack everything into a small region. |
| Resource balancing | LAB occupancy is already critical in failed variants. | Reduce mux/array footprint and unused width before trying DSP-to-ALM substitution. Count occupied LABs and routing, not only nominal ALMs or multiplier counts. |
| Clock management | Prepared fusion probe constrains one kernel clock; compiled sequential RTL uses that clock. | Keep this topology; inspect global control/reset routing. No new generated clocks or blanket clock-network assignments. |
| Hierarchy / partitions | Modular RTL is useful; hard compilation boundaries are a separate decision. | Keep cross-module optimization available initially. Trial preserved partitions only once interfaces and placement are stable, with an unrestricted control fit. |
| Tool settings / incremental builds | Existing source/device/seed/constraints provide an A/B baseline. | Check target/version support and change one routability setting family per experiment; measure runtime, setup, hold and complete routing. Incremental reuse needs compatible source/constraint provenance. |
| TDM / memory and DSP sharing | Phase-disjoint arithmetic sharing can save area but adds muxes/control; hot-loop serialization adds work. | Prefer sharing mutually exclusive phases. Accept added cycles only when measured frequency/resource gains improve total throughput. |

Selection rule for one unchanged candidate stream: compare
`new_frequency / old_frequency` against `new_complete_cycles / old_complete_cycles`.
This is a compute-only square comparison, not a complete PRP/PrimeGrid job estimate.
Include setup amortization, stalls and sustained initiation interval if the
experiment overlaps multiple candidates. Require correctness, successful route,
setup/hold checks and identical device/constraints before promoting a result.

Vendor guidance supports the cautions rather than a universal placement recipe:
[Quartus design optimization](https://docs.altera.com/r/docs/683641/current)
provides congestion, high-wire-count and hierarchy reports, plus separate area,
routing and timing trade-offs. The vendor's
[design partitioning guidance](https://www.intel.com/content/www/us/en/docs/programmable/683247/25-1/design-partitioning.html)
warns that partition boundaries limit cross-boundary optimization and poorly
chosen partitions/floorplans can degrade utilization and timing. Arria 10 is not
a HyperFlex device; do not import Hyper-Retiming-specific advice as a capability
of this target.

The explicit canonical-output helper is now an isolated local RTL candidate,
not merely a proposal: `genefer_montgomery_mul27_canonical_pipe.sv`, SHA256
`1d29fffb22b5ab9414d83b2cdde4d4068d605b51d60bda6d7b5d47688e181352`.
Only module/comment names and two zero-extended result assignments differ from
the frozen sparse ancestor. Parent reran all seven source/integer/clock-model
tests, including 300,363 arithmetic pairs and 60,000 modeled clock edges.
No HDL simulation, synthesis, fit or integration was performed for this helper;
Quartus may already propagate the same zero bits, giving no physical benefit.
The 32-bit public interface and internal Montgomery precision are unchanged.

### Fusion chosen normal-profile matrix complete

AW1 and AW7 are now independently verified against the same37-source preparation
manifest as AW5/AW16. AW1 report5d639efd… contains529 operations,522 readbacks,
7 NOREAD intermediates,228 cold/301 warm operations and9 live reset/abort checks.
All529 ordered cases have conversion and total cycles exactly3 below the frozen
prefetch baseline; every other common counter matches. Vector bytes are the
exact old prefix plus four invalid-final-row commands.

AW7 report e32a3584… contains12 operations,10 readbacks,2 NOREAD intermediates,
2 cold/10 warm operations. Its warm square is796 cycles: conversion14,NTT653,
CRT70,carry59,seed setup490. Build86.17s and simulation5.02s on aethia, under the
same CPU0/2,2-worker compiler,1-thread model and6GiB guards. No old AW7 matched
whole-prefetch run was found, so no measured AW7 baseline delta is claimed.

`core27-prefetch-r2-normal-matrix-v1.json` binds all four independent receipts,
raw report hashes and common source identity. Totals:1121 operations,1103 direct
readbacks,18 NOREAD intermediates checked by eventual chained readback,29 live
abort checks,291 cold/830 warm operations. This is the chosen AW1/5/7/16 normal
matrix, not every parameter, a complete mutation campaign, full PRP, fit or board
qualification. Both new raw archives and independent receipts are retained.

### Concrete congestion targets, not a generic fanout prescription

The archived failed cached64 `probe.fit.route.rpt` explicitly lists field0
`orientation_d` fanout5297, `bf_in_valid[0]`5039, `vector_base_bank[6]`4616,
`orientation_pipe[6]`4101 and `pairing_d[2]`3750. These named controls are useful
targets for source/netlist tracing. The largest anonymous net (`i5510~0`,11290
loads) is not identified as reset/enable without a technology-map trace.
Field0 and field1 NTT children dominate the reported congested hierarchies.
These are failed cached64 placement observations, not measurements from the
still-running prefetch64 fit and not usable whole-core timing evidence.

A source audit found redundant quarter-dependent payload zeroing in the
16-word host adapter. The child already routes and applies the matching write
mask before committing RAM writes. Repeating the16 input words across all four
quarters can make the upper two64-lane payload-XOR stages identities while
leaving the entire mask route intact. This is a candidate-specific proof and
RTL-test obligation, not permission to remove masks or zeroing at other
interfaces. Nominal exposure is6144 bit-wide selections per field (18432 across
three fields), not measured physical mux/ALM savings. Synthesis might already
exploit masked don't-cares; the wider repeated payload also changes fanout.
The appropriate physical A/B is the integrated host wrapper or whole core,
not a raw-engine probe lacking this host adapter.

The isolated host-broadcast wrapper is now present, SHA256
`0960922332ea919a72a1ee591a70006bba76af7f26bc5308b68f50e327583e29`.
Parent reviewed the exact module-name/payload-assignment diff and reran eight
source/symbolic tests. The frozen R2 wrapper, child and core remain unchanged.
`host-broadcast-source-proof-v1.json` records32768 routing combinations; the
tests also cover sparse masks, runtime-size clipping and full32-bit payload
preservation. This is not an RTL simulation or a physical improvement result.

### Canonical-output multiplier: first RTL attempt preserved

Five-file manifest a1cc04b1… was copied to a fresh aethia-only snapshot and
verified before execution. Scope `gfn-mont27-canonical-gate-v1` ran with physical
CPUs0/2,CPU200%,6GiB,shared compiler lock and private tmpfs. The first field's
fresh RTL model passed25527 arithmetic outputs,333 reset cancellations and4767
hold checks over30294 edges. Build3s; normal simulation1s.

The attempt is nevertheless FAILED/INCOMPLETE: the first invalid-input test
exited-6 with the correct `noncanonical Montgomery27 input` assertion at
candidate line55, followed by Verilator's same-file/same-line `Verilog $stop`
trailer. The original parser rejected two diagnostic lines. The entire attempt
is archived in `mont27-canonical-gate-v1`; no result or frozen source is edited
to turn it into a pass. A new runner snapshot must recognize only this precise
paired diagnostic and still reject unrelated errors. Fields2/3 and parameter
assertions did not run in this attempt. No resource/clock/integration claim.

### Canonical-output helper v2 RTL gate independently verified

The fresh v2 snapshot changes only the runner path and exact diagnostic parser;
helper, ancestor and C++ bench hashes are unchanged. Manifest9af45c94… was
verified before execution under the same aethia caps. All three legal-field
models passed:76581 outputs,999 canceled tokens,14301 hold checks and90882
edges. Twelve invalid-input tests and two invalid-parameter models terminated
at their exact expected assertion/file/line; generic failures do not count.

Parent reran the standalone offline verifier and all11 verifier tests. Receipt
`mont27-canonical-gate-v2/verification.json` binds raw report951c7284…,
42 artifacts,5 pinned sources and75 generated members. The verifier never runs
saved executables and uses ordinary modular arithmetic to recheck vectors and
an independent queue for cycle coverage. Compiler execution and remote tool
binaries remain a trusted boundary. v1 remains failed and preserved. This is
standalone helper evidence only: no NTT integration, fit or area/clock claim.

### Prefetch64 whole-core fit also failed routing

The existing AWS fit terminated2026-09-30T13:28:35Z with Quartus exit3 and
explicit25111/170143 routing-congestion diagnostics. It ran16803s, below its
21600s job limit; this was not a timeout/OOM. No retry was launched.
Archive `core27-stream-prefetch64-aws-fit` includes16 RTL files, controls,
terminal context, logs and raw reports, but excludes large databases/licenses.
All16 compiled sources match the passed full-N prefetch correctness gate.
The QSF has exactly one vendor-added LAST_QUARTUS_VERSION assignment; otherwise
it byte-matches the context-pinned prepared QSF. Other controls match exactly.
Parent receipt binds raw routeSHA33d17102… and summary955fb26a….

Final failed-fit accounting:379665 raw placed ALMs (336488 packing-adjusted
needed),41830/42720 LABs=97.92%,1435 M20Ks,867 raw DSPs,306378 registers and96443
route-through ALUTs. The earlier placement-stage report had one fewer raw ALM.
No usable whole-core Fmax was established. This is prefetch, NOT the unfitted
R2-fusion variant. Saving M20Ks alone did not establish routability.

Unlike the earlier cached64 congestion report, current field0 named hotspots
include point_half_d (fanout1731), bf_in_valid[63] (4536), state.BF_READ (1165),
pairing_d[1] (1887) and orientation_d (4089). Several field address-derived
nets exceed6000 loads. Host/bank routing deletion and selective local control
distribution remain relevant; do not infer identical critical paths from the
older component/cached-core report. Dashboard now records this terminal failure
and retains the prior whole16 physical throughput headline.

### Matched primitive probe support and next host-memory gate

`synthesis.prepare` now has an explicit `multiplier27_canonical` target, rather
than changing the sparse baseline. A new preparation test checks all three
fields against the sparse target: identical device/P/Q/radix/clock/workers,
virtual ports,SDC,QPF and flow; only top/source change. All39 preparation tests
pass. This adds preparation support only; no Quartus job or physical result.
Primitive A/B synthesis can establish whether explicit zero-extension changes
mapping before spending a whole-core fit on it; primitive timing cannot be
used as the whole-core clock.

Parent reviewed the paired host-memory bench against the frozen child's RAM,
profile and start/busy behavior. Normal runs compare both instances with an
independent initialized-address memory model. Unmasked/invalid read data are
not compared; reset invalidates the oracle rather than assuming RAM clearing.
All host words are initialized before intended reads, and complete scalar
scans detect damage to neighboring/masked locations. Separate subprocesses
test noncanonical enabled writes in one selected instance at a time.
The first intended smoke profile isAW8/P1; the full intended-address-width
AW16/P1 host-memory profile remains necessary before integration, in addition
to small boundaries and other fields. None of those host-memory RTL runs has
completed at this entry. Existing source/symbolic proof is not a substitute.

The independent host transaction oracle is now pinned at4b819c0a… and has nine
passing local tests, including a second count-only calculation with a bit-array
PRNG. It predicts AW8/P1:3656 edges,3970 word reads,2021 word writes,162 vector
reads,197 vector writes,1284 masked-poison words,73 clipped lanes,806 descriptor
errors,6 profile checks and2 live busy checks. This expectation was saved in
`host-broadcast-memory-expected-aw8-p1-v1.json` before RTL execution. Its trace
hash identifies the expected software schedule, not an observed RTL trace.

The guarded runner (2bcf6db4…) passed12 focused Python tests. It accepts only
exact independently derived normal counters and instance/file/line/bank-bound
assertion diagnostics; generic nonzero exits do not qualify. Source preparation
manifest a02d0bf8… binds14 files (10 compiled sources plus proof/oracle/plan/
runner). Parent verified/extracted the exact archive and checked every source
before executing the first AW8/P1 run on aethia. Scope
`gfn-host-broadcast-memory-aw8-p1-v1`, invocation2a899230ef6549e8bcd5fe89f1296169,
uses CPU0/2,200% quota,6GiB,shared compile lock,compiler2/model1,private tmpfs,
768MiB scratch reservation and64MiB durable reservation above existing floors.
This entry records launch only, not a passed simulation or physical result.

### Host broadcast smoke and full-address-range P1 gates verified

AW8/P1 completed exactly the predeclared counters and all30 typed illegal-write
rejections. Parent reran the independent offline verifier and its nine focused
tests. Raw reportbc68e24f… and receipt are archived in
`host-broadcast-memory-aw8-p1-v1`;40 artifacts,14 source members and55 generated
members were checked. Compiler43.06s; normal simulation1.00s.

After a fresh idle/headroom check, full AW16/P1 ran sequentially from the
identical snapshot, with its own manifest5d90b7f5… and scope
`gfn-host-broadcast-memory-aw16-p1-v1`. It independently verified611608 edges,
881483 word reads,279608 writes,28745 vector reads,28764 vector writes,311364
masked-poison words,68 clipped lanes,799 descriptor errors,6 profile checks,
2 live busy checks and all30 typed assertion cases. Compiler45.06s; normal
simulation93.19s. Raw report86c60eae… and receipt bind40 artifacts/14 sources/
58 generated members. These counters count the expected word events, with both
RTL instances checked against each expected read. They are not full-core NTT
or arithmetic throughput measurements.

Matched wrapper probe targets now exist; parent reran all41 preparation tests.
Both P1/AW16 probes were generated locally, with manifest hashes08aadc62… and
07d0cb30…. Each has seven compiled sources matching the paired gate. Controls
are identical except wrapper top/source:16-word host,64 arithmetic lanes,
format2,same device/P/Q/R32/seed1/4workers/100MHz/virtual pins/SDC/QPF/flow.
`host-broadcast-matched-probes-v1.json` records the preparation. No physical job
was launched; existing raw-engine fits cannot serve as the wrapper baseline.

AW8/P2 has now started sequentially under the same guards, manifesta4d549e5…,
scope`gfn-host-broadcast-memory-aw8-p2-v1`, invocation60865ae28381497f8ed9a0e77167e3df.
The other parameter gates and whole-core integration remain incomplete.

AW8/P2 is now terminal and independently verified, raw reportbcb086db…:
same exact3656-edge counter schedule as P1, with its own P/Q and all30 typed
assertion cases. Receipt checks40 artifacts,14 identical sources and54 generated
members. The follow-on AW8/P3 run has started only after fresh terminal/idle/
headroom checks, manifest582f163e…,scope`gfn-host-broadcast-memory-aw8-p3-v1`,
invocation2faff271b350467d93ae8722aa71a1c8. No P3 pass is claimed by this entry.
Small AW1/AW5 elaboration checks and whole-core integration remain pending.

An isolated whole-core source candidate is now prepared:
`genefer_square_core27_stream_prefetch_r2_host_broadcast.sv`, SHAea2b5188….
Parent reviewed the exact two RTL substitutions (top identity and host-wrapper
type) and reran all eight structural tests. Dedicated C++ benches change only
generated-model names and the included bench filename; independent arithmetic
oracles, strict live-abort checks and expected phase counters are unchanged.
The transformer pins16 kernels plus two bench files and rejects unrelated
FSM/basis/format/counter/dependency edits. The frozen R2 core remains intact.
No integrated RTL runner, simulation or physical result exists for this new
core yet; standalone host-memory equivalence is not promoted to a core pass.

AW8/P3 is now terminal and independently verified, raw reporta8113a0e….
Its exact3656-edge normal schedule and all30 typed assertions passed; receipt
checks40 artifacts,14 sources and54 generated members. All four completed
profiles (AW8/P1,P2,P3 and AW16/P1) retain exactly the same14-source map.
AW1/AW5 elaboration checks remain, as does the isolated whole-core RTL gate.
No host-broadcast physical job has run and no resource/clock/throughput gain is
claimed from these correctness results.

### 2026-09-30 — routing checklist and whole-core host-broadcast gate

The chosen paired-memory matrix is complete: AW1/P1, AW5/P1, AW8/P1/P2/P3,
and AW16/P1. All six retain the same fourteen-source closure. The composite
`host-broadcast-memory-matrix-v1.json` binds the independent receipts:
625,407 clock edges, 894,556 read words, 287,335 written words and 150 typed
illegal-write checks. These are correctness counts, not throughput results.

The separate whole-core runner pins 43 files, compiles sixteen kernels and
changes only the top/wrapper identities and the previously checked host payload
assignment. Its native independent verifier checks source deltas, generated
sources, command lines, artifacts, integer answers and exact baseline vectors
and cycle counters. N32/AW5 passed 568 operations, 561 readbacks and twenty live
abort checks. Raw report `af86917c…`, manifest `6e6a27c3…`; independent receipt
is in `core27-prefetch-r2-host-broadcast-aw5-v1/verification.json`. All cycles
match the frozen R² baseline; this is not an additional three-cycle saving.
N65,536/AW16 was then dispatched on aethia under scope
`gfn-core27-r2-host-broadcast-aw16-v1`, invocation
`fff53518e34f46faae5b29f22c9fc853`, using CPU0/2, quota200%, memory6GiB and
the same disk, shared-lock and timeout guards. This paragraph records dispatch,
not completion. Whole-core matched physical preparation has a dedicated target;
all42 preparation tests passed. No new cloud fit has been launched.

The user's seven optimization categories map to the following ordered checks.
Success means better complete-task throughput, not merely a higher Fmax or
lower RTL operator count. For unchanged candidate scheduling, compare total
cycles divided by a supported integrated clock; include startup and transport
when end-to-end measurements become available.

| Category | Project-specific action | Guardrail / evidence needed |
| --- | --- | --- |
| RTL simplification and pipelines | Remove inactive-quarter payload selection first; then pipeline measured long bank/control paths. | Host masks, reset, valid/data alignment and cycle accounting must remain correct. Extra registers do not remove connectivity by themselves. |
| Placement | Try loose locality for bank, arithmetic and associated control clusters using actual M20K/DSP columns. | Leave routing space; compare unconstrained baseline before hard regions. The failed prefetch64 fit occupied97.92% of LABs. |
| Resource balancing | First reduce excess muxes and conversion hardware; retain DSP multiplication as baseline. | Moving multiplication into ALMs may worsen the existing logic/routing pressure. Device totals alone do not show local congestion. |
| Clock management | Retain the single compute clock and explicit enables. | No fabric-generated clocks or invented multicycle exceptions to hide failing timing. Board clock/reset distribution remains unqualified. |
| Hierarchy | Use hierarchy for locality and targeted control duplication. | An RTL module is not a physical partition; forced boundaries can prevent useful cross-boundary optimization. |
| Tool settings and incremental builds | Isolate routability effort and proximity-aware duplication experiments with fixed source/device/seed controls. | Check ignored assignments and actual duplication reports. Preserve physical partitions only after a useful baseline exists; incremental compilation is an iteration aid, not a speedup claim. |
| TDM and resource sharing | Share low-duty setup/control work where it does not starve the arithmetic pipeline. | Serializing hot memory or multiplier paths adds cycles; accept only if whole-device throughput improves. |

Altera's [design optimization guide](https://docs.altera.com/r/docs/683641/current)
covers congestion reports, mux restructuring, physical synthesis and placement;
its [proximity-aware duplication guidance](https://docs.altera.com/r/docs/683641/25.3.1/quartus-prime-pro-edition-user-guide-design-optimization/automatic-register-duplication-estimated-physical-proximity)
calls for checking the Fitter Duplication Summary. These are candidate tool
strategies, not evidence that a setting was applied to this design. No Stratix10
Hyperflex-specific capability is assumed for the Arria10 target.

### Host-broadcast full-size whole-core evidence completed

The AW16 job completed both segments with exit0. Its independently verified
raw report is `eb20a623…` in `core27-prefetch-r2-host-broadcast-aw16-v1`:
12 operations, ten readbacks, two no-readback operations subsequently checked
through chained readback, two cold and ten warm operations, and four invalid
final-row cases. All vector bytes and all twelve metric records exactly match
the frozen R² baseline:32,965 warm /41,708 cold cycles. The native verifier
checked13 artifacts,43 sources,16 compiled kernels and141 generated members.
Build94.19s; RTL segments209.69s and239.78s. These are simulator wall times,
not FPGA operation latency. AW1/AW7 and broader integrated mutation coverage
are not claimed by these AW5/AW16 results.

`host-broadcast-wholecore-matched-probes-v1.json` records the matched whole-core
preparation. Candidate manifest9185e69d… differs from R² baselineaba5974a… only
in target/top/arithmetic-profile identifiers and the two substituted source
files. QPF/SDC/flow are byte-identical; QSF differs only in those identities.
All sixteen candidate RTL hashes also match the completed AW16 gate. Its
preparation receipt intentionally retains the historical AW5-only status at
the time it was made. Both wrapper and whole-core A/B probe folders total
66files/500,320bytes. Consolidated user approval was requested to copy these
to the existing AWS worker and run four disjoint four-physical-core fits,
24GiB each, six-hour per-job limits within the existing80USD allowance.
No transfer/fit has occurred and no physical improvement is claimed.

### Isolated orientation replication candidate — source/model only

The archived format1 prefetch whole-core route lists
`field_lane[0].engine|child|orientation_d` with98 overused nodes and4089
route-table fanout. This is older failed-route evidence, not a measured
format2/host-broadcast bottleneck. Its corresponding selector/capture cone is
unchanged in the format2 ancestor. The new isolated `*_orient8` engine,
host-broadcast wrapper and core replace only that scalar driver with
ceil(LANES/8) same-edge drivers, each serving at most eight arithmetic lanes.
All replicas capture `orientation` directly on the original edge and reset to
zero asynchronously; they do not sample the old delayed register. The
writeback `orientation_pipe`, datapath, valid/masks and counters are unchanged.

Parent inspected the exact three-file deltas and reran nine new Python tests
plus eight existing core-structure tests. These check pinned ancestors,
bounded abstract reset/transition equivalence, lane/selector coverage, a
one-cycle-wrong negative case and prohibited source changes. The existing
`preserve, dont_merge` pattern is pinned to the earlier tiled-engine source.
`prefetch-r2-orient8-source-review-v1.json` binds the source and test hashes.
Logical cost at64 lanes is+7 registers/field,+21 across three fields; physical
FF/ALM effects remain unknown, including prior register merging. No HDL
simulation, compile, fit, runner or synthesis target has been added for this
candidate. It does not alter the separately prepared host-broadcast A/B fits.

### Orientation8 first RTL gate and coverage-driven full-size dispatch

The isolated runner is `reference/core27_prefetch_r2_orient8_regression.py`,
SHA c7714263…; direct execution requires manifest bc354d45… and verifies all51
source files before project imports. Sixteen kernels compile; the old engine,
wrapper and core are replaced only by the orient8 candidates. The two benches
change only model/include identities. CPU0/2,2compiler workers,1model thread,
6GiB memory, shared compile lock,1800s limits and existing disk reservations
remain unchanged. Parent inspected the source/bench deltas and reran62
runner/structure/preparation tests;21 runner/offline-verifier tests also pass.

AW5 completed on aethia under scope `gfn-core27-r2-orient8-aw5-v1`, invocation
5ed4575b986a41269a931458626ebef6. Raw report0ebadec8… and independent receipt
in `core27-prefetch-r2-orient8-aw5-v1` bind51 sources,16 compiled kernels,
134 generated members and11 artifacts:568 operations,561 readbacks,20 live
aborts and four invalid final-row cases. All expected vectors and metric
records exactly match the frozen R² baseline. This is a small-size normal
integration gate, not a physical result or complete orientation-toggle gate.

The coverage review found that L64/N32 activates only16 butterfly lanes and
never issues orientation1. N128 activates all64 lanes but still onlyorientation0,
so that intermediate size would not detect a delayed orientation register.
Parent independently enumerated the exact fixed-position/address-fold schedule:
N256 is the first size exercising both values on all tiles; N65536 has256
orientation1 groups per stage,4096 per transform. This is derived schedule
coverage, not an observed runtime trace; see
`prefetch-r2-orient8-schedule-coverage-v1.json`. Accordingly the next run is
AW16, not the uninformative-for-this-purpose AW7.

After verifying AW5 and checking idle/headroom state, parent dispatched AW16
from the same immutable snapshot under `gfn-core27-r2-orient8-aw16-v1`,
invocation3d0499a720f04c76bff380f2a2d0f25c. This entry records launch only.
No new source copy was required. Matched orientation wrapper/core synthesis
targets were added locally;43 preparation tests pass, but no orientation
physical fit was launched. The four earlier host-broadcast physical jobs still
await their consolidated copy/run approval.

### Orientation8 full-size normal gate independently verified

AW16 completed both segments on aethia. Report2e917ac3… and native verification
receipt in `core27-prefetch-r2-orient8-aw16-v1` bind51 source files,16 compiled
kernels,134 generated members and13 artifacts. All twelve operation metrics
and full vector bytes match the verified host-broadcast baseline exactly:
32,965 warm /41,708 cold cycles, ten readbacks plus two chained no-readback
operations, and four final-row invalid cases. Parent reran ordinary-integer
validation through the native verifier. Build92.18s, RTL segments209.67s and
243.78s are simulator wall time, not FPGA latency. The source/model orientation
coverage argument remains distinct from a captured internal runtime trace.
No replica-retention, placement, timing or throughput improvement is claimed;
integrated mutation qualification and remaining parameter sizes are not implied.

### Original-objective evidence audit and selected-clock repair

Independent review and parent rechecks establish that the existing routed
whole16 design already contains pipelined NTT,16-wide CRT and streaming
precision carry with three concurrent fields. All fourteen archived fitted RTL
hashes match the passed whole16 regression. Parent freshly reconstructed all
twelve full-size ordinary-integer square/conditional-double expectations from
vector bytes0270fe7b…, which exactly match the vector SHA recorded by whole16;
ten readback identities match its raw report17339799…. This does not turn the
separate64-lane rootpipe or128-operation long-chain execution into16-lane data.

`whole16-evidence-review-v1.json` records the scope. Cold352,673 plus
(1,911,814−1)×warm90,521 equals173,059,577,246 cycles, or33.93325minutes at an
ASSUMED85MHz. Persistent cached roots and sampled carry behavior are assumed;
host orchestration, checkpoints,proofs,verification and board stalls remain
excluded. Fitting succeeded with192,180 raw ALMs,1,467M20Ks and546 raw DSP
blocks; packing-adjusted needs are169,839ALMs/524DSPs. The100MHz constraint
fails setup−1.406ns; worst hold is+0.017ns. Neither reported87.67MHz Fmax nor
this arithmetic extrapolation completes the selected-clock timing requirement.

The existing v3 postroute audit failed before producing85MHz corner reports:
native period truncation, repeated UCP section headings, and known copied
report/cache changes tripped its strict harness. Separate v4 helper/Tcl/tests
now explicitly request11.764ns/5.882ns (85.005100306MHz), without relaxing the
1e-6 identity tolerance; parse the exact six-row/two-count UCP summary table;
and allow only four exact report outputs plus two cache promotions matching
pre-existing routed bytes by SHA/size and direct streaming comparison. All
other copied-file changes/deletions/additions fail. Entire original-project
immutability is independently checked. Old helpers and failed evidence remain
unchanged. Parent and independent reviewer inspected the repair;72 tests pass
(42new,30unchanged). See `core85-v4-review-v1.json` for the four helper pins.

The existing AWS routed database was read-checked as present and idle, with
adequate disk. No v4 file transfer or execution occurred. Separate permission
was requested for the bounded timing-only rerun on a private copy, within the
existing80USD allowance, no new fit or hardware image. Successful selected-
clock timing plus consolidated scoped evidence is the narrow remaining gate
for the original compute-model throughput objective; more64-lane variants
are a further optimization milestone, not a substitute for that evidence.

### 2026-09-30: cloud authorization resumed; routing comparisons dispatched

The user approved continued compute; the existing AWS80USD/GCP60USD planning
allowances remain in force. AWS credentials were renewed through normal login.
No new VM, copied evaluation state, hardware image, or public publication was
needed. Prior permission-pending entries above are historical, not current blockers.

At15:25UTC, AWS started the R² whole64 baseline and host-broadcast whole64
candidate in slots a/b (CPUs0–3/4–7). Their manifests are respectively
`aba5974a39fba3418a11f3656ae762a89ceb0c1510cee3da0d80ae328f597129`
and `9185e69dfa7d7d6ad0ae4d74b2126f77de4b9da8ac0139ad707d35c7bdde98ff`.
The corrected whole16 selected-clock STA ran in slot d and terminated normally
at15:29UTC. Its receipt reports scoped internal timing pass; raw evidence is
archived at `core85-audit/v4`, with independent verification in progress.

After that timing unit became terminal, matched host-wrapper fits started in
slots c/d (CPUs8–11/12–15), using v5 launcher. This narrowly adds explicit
HOST_LANES/arithmetic-LANES manifest validation; frozen v4 is unchanged.
Forty combined launcher tests passed. Units are
`gfn16-r2-wrapper-fit-v1` (invocation9eb0f8875d1945fcbdcdfd5e8fa3bd38) and
`gfn16-r2-broadcast-wrapper-fit-v1` (invocation05e9a70047924a6f84eab464ee03d2ef).
All four fit processes were independently observed live. Each gets four distinct
physical cores,400% CPU,24GiB RAM and a six-hour command bound; SMT siblings16–31
are not assigned to another slot. Component and whole-core comparisons remain
separate, and no clock/resource gain is inferred before their physical results.

Independent v4 archive review subsequently passed:172 indexed artifact hashes,
all14 fitted RTL identities, and all four raw setup/hold/pulse-width corners.
At11.764ns (85.005100306MHz), worst margins are +0.358/+0.017/+5.231ns,
respectively. Original recorded file inventories are unchanged; exactly four
report updates and two permitted byte-identical cache promotions were recorded.
The review is `core85-audit/v4/archive-review.json` (SHA
75726ff92c60fc036b88fbef2b7cb3cb9e1c9d456bf731d321ab4ad2102e2862).
This closes the internal85MHz assumption only:84 input and496 output ports
remain unconstrained, reset release is excluded, and Quartus rejected the
requested latch check. No board timing, complete PRP, or measured throughput
is claimed. The local archive does not contain the complete qdb; the reviewer
checked its recorded inventories and remote byte-comparison evidence.

GCP's idle worker now runs the matched P1 host-broadcast wrapper baseline:
unit `gfn16-orient8-baseline-fit-v1`, invocation2e42371b67e9422b89028d5e5f062b11,
MainPID6646, confirmed active with native Quartus synthesis output. All14 staged
bundle files were checked against manifestd67b75b1cc9446430c4e57190f119b5d74106447fac5593420752118a04bf566.
The orient8 candidate manifest5baa277aef060678db1b17eb09736f89696cf43109e5d485f77700f7a7480884
is staged but not launched; it waits for baseline completion on the same worker.
Both use four distinct physical cores0–3,24GiB,400%CPU and a six-hour bound.
Parent ran76 combined GCP/preparation/dashboard tests successfully.

### 2026-09-30: 64-lane priority, synthesis evidence and root-selection fusion

The user reaffirmed64-lane optimization as the priority and explicitly approved
GPT6.1Sol ultra and GPT6Astra high reviewers. The16-lane result remains only the
verified fallback; its consolidated evidence is `whole16-evidence-review-v2.json`.

The four completed synthesis summaries were archived while their fits remained
live: `routing64-synthesis-snapshot-v1/comparison.json`. Whole-core broadcast
reduces estimated ALMs397018→392996 (4022,1.013%); the matched wrapper reduces
78288→70918 (7370,9.414%). DSP estimates are unchanged within each pair.
These are not final placed resources, route success, or clock improvements.

An isolated orient8-rootfused candidate removes the variable-index root
preclipping plane by incorporating the mask into the existing XOR dimensions.
For each lane it selects `(lane XOR route) AND mask`, without additional
registers or scheduled cycles. Parent and independent Astra review found no
blocking issue. Twelve local tests cover2796032 lane-output comparisons and
the exact58-source/16-compiled-kernel contract. This is mapping/source evidence,
not HDL or physical qualification.

The immutable native snapshot manifest is
7eb2b7cc34c9fcdfd6067480d6d40ae7a7dc542072bf1bf50578bfd71063c69e;
source archive331e03eac01db77506ce650cedd05e9e06bf59e704e7b874d25f24cdab2ffa40.
The first aethia AW5 attempt terminated before compilation because its service
PATH omitted the existing Verilator installation. Its failed output is retained.
Fresh attempt `gfn-core27-r2-rootfused-aw5-v2` uses the explicit existing tool
root and a held SSH session,CPU0/2,200% quota,6GiB memory,shared compile lock,
and retained storage floors. Invocation840f1084ca114bea8b3eff8794f2f863.
Native compilation and thread probe completed successfully; arithmetic results
were still pending at this entry. No output of a live fit was overwritten.

Independent routing review identified broader congestion in the old failed
whole64, including point-half, merged butterfly-valid, pairing and address
controls. The next isolated design investigation is compact common row tags:
replace per-bank delayed row copies with common row pipelines and local bank
selection. Intended storage savings are structural only and may trade against
write-selector fanout; no new resource/clock/correctness claim is made yet.

Rootfused AW5 v2 subsequently completed successfully (2m54.675s service time,
1.3GiB peak). Independent offline verification checked568 operations,561
readbacks,20 abort labels,58 source members,16 kernels and133 generated members;
all original vector bytes and counters match. Raw report SHA
82a99f555fa8f0a7836f616b5b8c0be5b1e78fa339171571492fda87edcff786;
verifierc1a052c3b3c270729939f7c2969f2c26e51f8a9accd91c28fb99d458a31213a9.
Archive: `core27-prefetch-r2-rootfused-aw5-v2`. This is the small normal gate,
not a full-size, mutation, physical, or board qualification.

The same immutable snapshot now runs AW16 in
`gfn-core27-r2-rootfused-aw16-v1`, invocation443be85b29b148dfbe6937d7ddffac88,
under the unchanged CPU0/2,6GiB and disk-floor policy. To retain that floor,
one inactive old orient8-AW5 executable was copied to GCP, SHA-verified against
both its aethia and complete local archive copies, then its redundant aethia
copy was removed. Logs/sources/other results remain. Recovery locations and
hash are recorded in `orient8-aw5-executable-cold-move-v1.json`; no broad cleanup.

### 2026-09-30: full-size rootfusion gate and five concurrent physical experiments

Rootfused AW16 completed its normal whole-core native gate on aethia. Archive
`core27-prefetch-r2-rootfused-aw16-v1` contains 12 operations, 10 readbacks,
2 NOREAD operations, 2 cold and 10 warm cases. Source-matched independent
integer verification passed; warm32965/cold41708 cycles match the frozen R2
schedule exactly. Raw report SHA
7447dbe4813e1e6b45c5c5071da5019c7aa4ee0b47e0a8a923f75852fd01468a.
This proves the tested full-size normal behavior, not mutation, board, or full
PRP qualification and not a clock improvement.

Both matched AWS P1 wrapper fits completed with native fit/summary exit0.
Baseline raw placed ALMs102296, Fmax102.44MHz; host-broadcast ALMs97045,
Fmax101.49MHz. Both pass the100MHz core-clock target; broadcast saves5251
raw placed ALMs (5.13%) but does not show a speedup. DSP128 and M20K224
are unchanged. `host-broadcast-wrapper-physical-comparison-v1.json` binds
the controls, raw reports and source/whole-core simulation identities.
These component numbers cannot be multiplied into a whole-core fit claim.

Freed AWS slots c/d now run matched whole-core rootfused and orient8 fits;
the original R2 and host-broadcast whole-core fits continue in slots a/b.
At16:34UTC all four exact service handles were active/running. Each uses
four distinct physical cores, one SMT thread per core, four Quartus workers
and24GiB; slots are disjoint0-3,4-7,8-11,12-15. New manifests and controls
are recorded in `orient8-rootfused-whole64-matched-probes-v1.json`.

GCP baseline v1 completed native fit and summary successfully, but its guard
rejected Quartus's terminal LAST_QUARTUS_VERSION QSF append. The failed
receipt is retained. A separately tested v2 launcher permits only that exact
append when removing it restores the original QSF hash; all other immutability
checks remain. The orient8 candidate v2 is now running on that worker's
four distinct physical cores. Baseline raw evidence audit remains pending;
no rerun merely to change its status.

Rowcompact remains the next native experiment: 58-source snapshot and
independent offline verifier are reviewed, with19 source/model/runner tests
and13 verifier tests passing. Declared metadata storage reduction20496bits
across three fields is not a fitted resource saving. Frozen small native
profiles do not qualify nonzero-row reconstruction or in-flight tag reset;
AW16 and a separate targeted reset gate are needed. Aethia currently needs
a small safe cache archival to retain its10GiB durable free-space floor.

The completed broadcast wrapper's worst path points to repeat-period decode
feeding the root recurrence multiplier. A separate periodmask candidate
caches the accepted period mask without changing recurrence latency; its
source/model checks pass, while a bounded paired native runner is being
prepared. No periodmask HDL or timing result is claimed yet.

The rowcompact snapshot was subsequently extracted on aethia after checking
the exact58 regular members, every source SHA, archive SHA and manifest SHA.
It has not yet executed. Parent reran32 source/model/runner/offline-verifier
tests successfully. Added distinct rowcompact wrapper and whole-core entries
to synthesis preparation;45 preparation tests now pass, including P1/P2/P3
wrapper comparisons and whole-core comparison against orient8. Their QPF,
SDC and run.tcl are identical, and QSF differs only in the two or three
intended source/top replacements. Rootfusion is deliberately absent. These
are ephemeral preparation tests, not vendor execution or native validation.

Cold archive `cold-cache-fe1ea1907ad7-v1` is verified locally and on GCP:
347 tar members preserve one exact completed cache entry's344 output files
and manifest. Archive SHA
a319462806c7d0fc070a889dfb9d6b4936dcbdefd889729df1bd0a733f314aa0.
Both verification receipts and the complete original source proof are retained.
No aethia cache entry has yet been evicted. A broader read-only inventory
finds97 cache entries totaling about20GiB; all agent-work directories total
about175GiB. This does not classify all of those files as disposable.

The exact verified entry has now been evicted on aethia (344 build outputs
plus its manifest), with a complete two-copy recovery archive and an audit
receipt in `cold-cache-fe1ea1907ad7-v1/eviction-receipt.jsonl`. Both existing
compile/key locks were held, every source member was rehashed, and no active
build/test consumer was detected. The helper's five guard tests pass. Free
disk increased to11124535296bytes before the next gate; storage floors were
not relaxed. No other cache entries were removed.

Rowcompact AW5 native gate completed successfully in3m2.754s with1.3GiB
peak memory. Independent ordinary-integer verification passed568operations,
561readbacks,7NOREAD,59cold/509warm cases and20abort labels. All frozen
vectors/counters match. Raw report SHA
43f06c713f9811a78c13e86b6fe8f65e9e44fbad8e2b5b338af2663c9622178c;
archive `core27-prefetch-r2-rowcompact-aw5-v1`, verifier
eaee0d9bae4ef59c61bd9a0b6de616c2171d17188e7e6b634f1799fb38171dea.
The small profile has only zero row addresses and does not qualify full-size
row reconstruction or BF/MUL in-flight reset. AW16 now runs from the same
immutable snapshot in `gfn-core27-r2-rowcompact-aw16-v1`, invocation
12ae35a71d744f9cb2b91faa792765e5, CPU0/2,200%,6GiB,7200s outer bound.

Two rowcompact physical probes have been prepared locally, not dispatched:
`ntt27-prefetch-r2-host-broadcast-orient8-rowcompact64-aw16-p1-cpu4-100-v1`
and `square-core27-r2-host-broadcast-orient8-rowcompact64-cpu4-100-v1`.
Their seven/sixteen RTL inputs match the corresponding native snapshot pins.
Native correctness and available physical worker slots remain prerequisites.

### 2026-09-30: guide-backed compile-time options, not production changes

Read Altera's25.3 Design Compilation guide, including the user-linked
[placement section](https://docs.altera.com/r/docs/683236/25.3/quartus-prime-pro-edition-user-guide/reducing-placement-time),
[optimization modes](https://docs.altera.com/r/docs/683236/25.3/quartus-prime-pro-edition-user-guide/compiler-optimization-modes),
[routing effort](https://docs.altera.com/r/docs/683236/25.3/quartus-prime-pro-edition-user-guide/changing-fitter-aggressive-routability-optimization-settings),
and [block-based compilation](https://docs.altera.com/r/docs/683236/25.3/quartus-prime-pro-edition-user-guide/using-block-based-compilation).
The live AWS R2 baseline reports Auto Fit, placement effort1.0 and4workers;
synthesis completed7m39s and placement reported39m23s. Fitting was still live.

Recommended future separate comparisons: Balanced vs Aggressive Compile Time
on a known-routable wrapper; automatically vs always aggressive routability
on a congested design; placement effort0.5 vs1.0 only with total route time
and success rate included. The vendor's30%average runtime/15%average Fmax
tradeoff for Aggressive Compile Time is not a measured project result.
Reduced placement effort may worsen routing or cause no-fit, so it cannot
replace consistent final evidence. Block preservation could reuse stable
CRT/carry regions, but boundaries and a suitable baseline need validation.
Reuse of synthesis must be limited to unchanged RTL and synthesis-affecting
settings; optimization modes can change both synthesis and fitting. Running
jobs and frozen probes were not changed by this research.

Periodmask paired component gate has20passing parent-rerun local tests and
was staged on aethia without native execution. Manifest
b31968abb12df60dafc4250e69c8721862c1f2ab548b2c09fa13b9ab341bf25e,
archive fecb0fc0bc0d24af5bd59546f94e725f02e74d24c5e2a813ad4639b26e9d5177,
20source files. Prepared322cases/644runs cover all18legal periods and
independent modular expected roots. A paired baseline/candidate top compares
all11public outputs at each low/high evaluation. It remains queued for
independent dispatch review and the same aethia CPU0/2 slot after rowcompact;
neither a hardware clock benefit nor mutation qualification is established.

The storage metadata scan is retained in `aethia-storage-breakdown-v1.json`.
Approximately130.97GiB are PCH files, of which101.66GiB lie outside named
caches. This is a candidate inventory, not deletion eligibility: inactive
status and manifest dependencies must be checked. No bulk cleanup or change
to PCH compilation settings was performed. New bounded native runners use
tmpfs scratch while retaining executable/source/log evidence on disk.

### 2026 09 30 Periodmask repair and next locality fits

The first periodmask paired native run failed in its C++ harness: renaming
`main` made its missing success return undefined behavior. The failed V1
archive remains unchanged. Isolated V2 adds that return and
`-Werror=return-type`, with unchanged RTL and vectors. Native L64/P1 V2
completed in 18.472 seconds under CPU0/2, 200 percent quota and 6 GiB memory;
peak memory was reported as 682.5M. It passed 322 cases, 644 runs,
594150 responses, 117 reset aborts and 124 rejects. Report SHA
`89d50ed446849e4bf56b3425e2ee05803cd7815edcc84b3a11f18ba8a6e820ac` is
archived in `root-recurrence27-periodmask-pair-l64-p1-v2`. This is one
component profile, not whole-core, mutation, physical or clock qualification.

Rowcompact AW16 normal verification also completed: 12 operations and ten
readbacks, with unchanged 32965 warm / 41708 cold clocks. Targeted in-flight
reset instrumentation and a first eight-case executor are separately prepared;
normal-profile success does not cover that remaining qualification.

The completed GCP orient8 wrapper reports 101.58 MHz, 97133 raw placed ALMs,
85227 packing-adjusted ALMs, 66439 registers, 224 M20Ks and 128 DSPs. Its
full source/control/native report files are archived under
`ntt27-prefetch-r2-host-broadcast-orient8-64-gcp-fit-v2`; the matched independent
archive audit remains pending. Compared with the baseline 101.49 MHz, this is
not a material demonstrated throughput improvement or a whole-core clock.

The new rowcompact wrapper fit passed source/dispatch-policy peer review and
14 local policy tests. All seven fit RTL files match the passed AW16 native
source pins. Prepared bundle manifest SHA
`6568403fb51bdb68b40fc8a4795590bc96db8da5a8a068f0971e39d1a6c0b6da`
and archive SHA `aa1e015f9c3b9e268e8768bf2b7ac9acc50f2647050a556dae63e06d7f4098e2`
are preserved in `rowcompact-gcp-wrapper-stage-v1`. The isolated GCP v3
launcher adds only this exact source variant and identity strings to v2;
topology, input, budget-independent runtime, single-job and metadata guards
are unchanged. Unit `gfn16-rowcompact-wrapper-fit-v1`, invocation
`2aaefb2d14054655b5c240a31bec17cb`, was confirmed active in synthesis at
17:56 UTC, using four distinct physical cores, 400 percent quota, 24 GiB,
100 MHz, seed1 and a six-hour fit bound. It does not qualify the reset gap.

At 17:48 UTC all four AWS whole-core fits remained active on disjoint physical
slots. The earlier 17:36 placement read showed rootfused at 349941 raw ALMs /
41004 LABs versus baseline 372942 / 41675. This approximately 6.2 percent
placed-ALM reduction is preliminary placement evidence, not routed timing.
The read-only budget estimates retained headroom of approximately USD49.24
on AWS and USD39.95 on GCP after reserves; neither is actual billing.

An isolated double16 RTL clone and 12 structural/control tests are now
implemented, preserving the ancestor and exact same-edge acceptance/reset
behavior. Its candidate hash is
`8b5253a6325c48999045838d775973d084b3f4e78dc87c39a0cc76e288d21519`.
The proposed fanout benefit, native equivalence and fitted costs remain
unmeasured. The private dashboard now tracks the new component fit separately.
