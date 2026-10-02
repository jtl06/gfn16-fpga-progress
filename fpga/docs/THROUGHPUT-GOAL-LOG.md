# Active throughput goal — 2026-09-29

User authorized an ongoing goal and subagents to improve the GFN16 engine.
All HDL simulation and vendor compiles run on aethia, never on the Mac.
No hardware access, assembler, paid license, or PrimeGrid submission is allowed.
Preserve the original audited baseline and promote only verified candidates.

## Independent candidate work

- `/root/ntt_throughput`: new `genefer_ntt_stream_engine.sv`, parity-banked RAM,
  II=1 butterflies and vector operations. Full three-field simulation passes;
  N=65536 fused field-square is 1,441,743 cycles (old: 8,716,032). Four injected
  faults rejected. Explicit AW=1 elaboration also passes.
- `/root/crt_throughput`: new `genefer_crt3_pipe.sv` + `genefer_mod64_pipe.sv`,
  61 registered stages, II=1; input edge t → result t+60. Verilator and Icarus
  stream checks and four mutations pass. Autonomous `genefer_square_core.sv`
  now passes 384 whole-integer oracle cases, nine full-size squares, no-reset
  radix changes, immediate read/start, 15 reset aborts and four injected faults.
- `/root/carry_throughput`: new `genefer_carry_fast.sv`, exact 96-bit reciprocal
  estimate/correction plus later-sweep early exit. Existing full-size square
  uses 589,934 cycles (old: 2,031,643). Coefficient extrema and arbitrary
  supported radices tested. 1,473 consecutive no-reset starts pass in the final
  candidate and baseline regression (1,964 operations per implementation).
- Parent: new `genefer_root_stream32.sv`, one root/cycle using four interleaved
  power sequences and the existing multiplier. Four phases, all three primes,
  N2/N16/N65536 pass, including immediate complete→complete phase changes.

Peer review found no arithmetic defect. Integration must consume the final root
write before asserting NTT start; root_valid and done coincide on that word.
P2/P3 root generators must use primitive generators 5/31, not default 3.

## Remote workspaces / evidence

Under `/home/jtl/gfn-fpga-lab/agent-work/`:

- `ntt-throughput/fpga/artifacts/stream-full-v2/`
- `crt-throughput/fpga/artifacts/stream-01/` and `stream-02/`
- `carry-throughput/fpga/artifacts/reciprocal-v5-chain/`
- `root-stream/fpga/artifacts/root-stream-v3/`
- `throughput-fits/fpga/artifacts/{ntt_stream,crt_pipe,carry_fast,root_stream}-v1/`
- `square-core/fpga/artifacts/core-boundaries/`: final integration regression.

Parent coordinates at most two simultaneous fits; agents run only bounded
simulations (two build threads each). Fits use 16 GiB virtual-memory and
900-second runtime bounds. All four component fits pass internal timing at
100 MHz: NTT 103.10 MHz reported Fmax, CRT 104.24, carry 100.09, roots 158.98.
Integrated `square_core-v1` (10 ns) completed: 12,100 ALMs, 10,234 registers,
53 DSPs, 1,153 M20Ks, 18,876,416 RAM bits. Reported Fmax 95.61 MHz; setup
slack -0.459 ns (100 MHz NOT met), hold +0.018 ns. Worst paths run from carry
RAM output back to carry RAM input. `square_core-150-v1` (6.667 ns) also completed:
96.15 MHz Fmax, setup -3.733 ns, hold +0.018 ns, 12,153 ALMs/53 DSPs/1,153 M20Ks.
Tighter constraints did not materially lift the clock; keep the 90 MHz model.
The verified DIF/DIT integration has its own `square_core_difdit-v1`
fit running with a 1,500-second bound (full integration took ~12 minutes).

Update: DIF/DIT fit completed, Fmax 97.31 MHz/setup -0.276 ns/hold +0.018 ns,
12,294 ALMs/53 DSPs/1,153 M20Ks. Prefix carry standalone completed, 3,987 ALMs,
43 DSPs/516 M20Ks/Fmax 89.74 MHz/setup -1.143 ns/hold +0.020 ns. Its critical
path is small_mem RAM output through emit arithmetic back to coefficient RAM;
carry agent is registering the new wide candidate's emit output to cut that path.
Four-lane integrated synthesis hit the 16 GiB virtual-memory cap (reported
17,179 MB) before fit; do not call that a fitted candidate. Investigate standalone
small/full NTT RAM inference before simply increasing memory limits.

The integrated full-size random-square sample is 2,424,980 cycles: conversion
65,541 + root generation/loading 262,152 + NTT operations 1,441,753 + CRT
65,598 + carry/control 589,936. Five repeated squares use actual preceding RTL
output, not reloaded oracle inputs. At a hypothetical 100 MHz this is about
12.9 hours for 1,911,814 exponent-bit iterations; this is NOT a CPU/GPU speedup
or measured hardware/complete PRP benchmark. Component timing is insufficient
to establish integrated timing. Carry costs are data-dependent. The completed
integrated fit now supports a conservative 90 MHz planning model: **14.309 hours**,
11.894x faster than the old serial model and 5.424x faster than its hypothetical
parallel version. See source-checked `integrated-performance-v1.json` locally.

Local evidence: `results/throughput-20260929/square-core/` and
`results/throughput-20260929/components.json`. New integrated performance
reporter checks source hashes against the integrated fit and rejects clocks
above reported Fmax; 43 Python tests pass on aethia, including the independent
prefix-carry model and its exact full-size maximum-digit square cases.

DIF/DIT is now verified as an opt-in core parameter. Both default and DIF/DIT
modes pass 384 cases/four mutations. Core hash is
`07a40a884b567d58d39167230cb16f6ee76a004ced01588670170d694b202296`.
DIF/DIT full-size sample is 2,228,660 clocks (8.10% fewer); its fit is pending.
Four-lane/eight-bank NTT candidate now passes all-field full-size checks. Its
integrated core passes 384 cases/four mutations: **1,294,772 clocks** full random
square, 311,545 NTT-phase clocks. Core hash
`e2df6e0d02da4f33bc12ab5687317a2fd6335bd33c2c408c78537a86d4b7aa9b`.
`square_core_parallel4-v1` is queued behind current fits, preserving two slots.

Prefix carry candidate initial suite passes 1,132 cases/3,213 normalizations,
55 domain rejections and six aborts, with **131,188 clocks** at N65536. Final
mutation suite is running. `carry_prefix-v1` standalone fit is running.
Supported domain is explicitly narrower: b>2N+4, b<=1e9 and coefficient bound
2N(b-1)^2. Do not replace general carry without preserving/rejecting its domain.
NTT agent is now creating a separate cached-phase root-bank candidate; frozen
parallel RTL is untouched. Details/long-term budgets: GFN16-THROUGHPUT-ROADMAP.md.

User also asked which PrimeGrid workload best suits FPGA. Read-only survey
is complete; this does NOT authorize switching away from the GFN16 goal.
Initial hypothesis: compact modular sieves are more promising for relative
acceleration, but no CPU/GPU win has been established. WW and PPS-Sieve are
suspended; inspect current FC-Sieve/SR5 work rather than recommending retired
BOINC tasks. See `PRIMEGRID-FPGA-WORKLOADS.md` when available.

User then explicitly confirmed continuing GFN16, aspiring to throughput of a
same-era weak GPU. Provisional comparison hardware is GTX 1050 Ti, with GTX
750 Ti as another era-appropriate reference. Carry agent is collecting primary
GFN16 main-task/benchmark evidence with size/version/date caveats; do not use
proof-task times or the generic GPU ranking as matched throughput measurements.
This is a stronger aspiration than the initial goal, not an established outcome.
CRT agent is analyzing parallel/chunked carry and will integrate the opt-in
DIF/DIT engine once NTT agent freezes it. Parent retains baseline fit snapshots.

## Integration target

## Public progress tracking (user requested and authorized)

Created public https://github.com/jtl06/gfn16-fpga-progress at commit
`3ecfc0a0d7a400de79338cf82ffcd2dbd6a3b35c`. Local separate Git repository:
`../gfn16-fpga-progress/`. ONLY sanitized milestone JSON, plotting code, tests,
README and PNG/SVG are published. No lab source, raw reports, host details,
vendor software or licenses are included. Public chart uses a **hypothetical
common 100 MHz** and RTL cycle counts; no vendor-fitted frequency is published.
Private `progress/verify_public_progress.py` checks its data/hashes against lab
regressions. The later public update `0a088986e30bede3a02ad05995f32a6718c1a8fa`
includes the cached sixteen-NTT/sixteen-carry-lane snapshot: 479,674 cold and
217,522 warm clocks. It projects one cold plus 1,911,813 warm iterations at a
hypothetical 100 MHz (about 1.2 hours); this snapshot is not physically timing
qualified. Publication, clean checkout, private evidence gate and three public
tests were verified. All public numbers remain compute-only projections.

Chart dependencies isolated in `/private/tmp/gfn16-chart-deps.BtUeVS` with
matplotlib 3.10.7; this is chart rendering, NOT HDL simulation on the Mac.
Public Git commit identity uses the account's verified GitHub no-reply address.
Keep future publications inside the separate repository and preserve this scope.

## Integration target (continued)

Canonical digit state resides in carry RAM. Each start performs conversion to
three Montgomery fields, on-chip root generation/loading, concurrent twist /
forward / square / unnormalized inverse / fused postconversion operations,
streaming CRT, optional doubling and exact carry normalization. Output remains
in carry RAM for the next start, without host reloads between iterations.

Verification must compare actual output against independent whole-integer
modular squaring, including repeated full-size operations. Include conversion,
root-loading, CRT and carry cycles in the revised performance estimate.

Do not label this a complete PRP worker: exponent sequencing, checkpoints,
proof protocol, host interface, card identity and board timing remain separate.

## Module-memory inference and physical checkpoint (2026-09-29)

Full AW16 generated inline memory arrays exhausted the bounded 16 GiB Quartus
frontend on parallel/banked/local-read-register NTT variants and four-lane carry.
AW8 synthesis inferred RAM later; this was not evidence of FPGA capacity failure.
Moving each RAM into a separate module fixed early extraction without changing
the arithmetic or cycle schedule. Keep the earlier failures as evidence; do not
overwrite their frozen projects.

`genefer_ntt_banked_modulemem_engine.sv` at
`2fad6ba7974e44d4f0081973fc3a243ed793a5ae747400485768ba357d844285`,
with fixed32 helper `993567fb68fdc216b9ff04489d1810f743b86564434e4b48261ad606b25d53b0`,
passed three-field AW1/8/16 arithmetic regressions. Full-size synthesis took
23.9 seconds, approximately 1.9 GiB virtual memory. The four-lane field-1
virtual-I/O fit completed: 6,390 ALMs, 4,001 registers, 16 DSPs, 512 M20Ks,
8,388,608 RAM bits. Restricted Fmax 90.33 MHz; setup -1.070 ns at 100 MHz,
hold +0.018 ns. **100 MHz did not pass.** This is a standalone engine, not
an integrated/core/board clock result. Private evidence is archived under
`results/throughput-20260929/vendor/ntt_modulemem4-aw16-v1/` and the associated
summary/regression JSONs. Worst paths originate in stage control and terminate
at root-read counters or root RAM addresses, not Montgomery arithmetic.

Power-of-two root-group candidate `genefer_ntt_banked_packed_engine.sv`
at `94e5962dd15f9dec57e2896e4280248831543c151af2eea4bf0c1f9cfad18c5f`
passed three-field AW1/4/16 tests and four root-packing mutants; full synthesis
took 24.8 seconds. Its completed field-1 fit uses 6,069 ALMs, 3,974 registers,
16 DSPs and the same 512 M20Ks / 8,388,608 bits. Restricted Fmax is 95.01 MHz,
setup -0.525 ns at 100 MHz, hold +0.018 ns. This is a small measured standalone
timing/logic improvement, not a RAM reduction or passing 100 MHz result. The
module-memory baseline already implements exactly 3N root words plus N data words.

Carry candidate `genefer_carry_prefix_wide_ram.sv` at
`d40767ec1a089bee19501ff0e9080226c6c73c71b0bf75b2c7bf155ea939a511`,
with generic single-port helper
`b97d2f43db1b1e1aa60b9b7fc2b720af1e302bd5ff9e35854c89b30e5fb610df`,
passed the four-lane full-N oracle suite at unchanged 32,884 kernel cycles.
Full AW16 synthesis now passes in 38 seconds / 1.14 GB peak RSS, instead of
hitting the 16 GiB cap. A physical carry fit and remaining lane/host regressions
are in progress. These snapshots are not yet a new validated integrated fit.

The projection checker now distinguishes a sampled all-cold upper model from
a cached-chain model: one measured cold maximum plus (exponent bits - 1)
measured warm maxima. It requires matching measured cache state/hit/load data;
without both states it emits no cached-chain projection. This remains a
sample-based compute estimate, not a full PRP benchmark or universal carry bound.
All 48 reference/preparation/evidence tests passed on aethia after this change.

Next: integrate both module-memory fixes, fit the four- and sixteen-lane cores,
then widen scalar conversion/CRT interfaces and pipeline stage-control decoding.
Keep vendor fit data private; public progress remains normalized hypothetical
100 MHz RTL-cycle projections only.

## Integrated module-memory and vector-boundary checkpoint (2026-09-29)

Legacy inline sixteen-lane core `f8a4b393...eacf8` completed all 1,255 cases and
eight injected-fault checks. Full-N cold/warm cycles are 479,674 / 217,522;
scalar conversion plus CRT consume 131,139 warm clocks. This evidence supports
the public cycle-only milestone, not a fitted operating clock.

New core snapshot
`80851bdfc16f90dc7c343f67496d253ab59c5fbde1c6311d7e18231c82acd9e5`
selects module-memory NTT and wide carry without changing parameters/ports.
Four/four integration passed all 1,255 cases plus eight mutants, preserving
737,722 cold / 475,570 warm clocks. Its full AW16 fit started only after checking
all twenty frozen source hashes and six architecture parameters against the
passing report. Project `square_core_banked4_carry4-mem-v1` in the parent fit
workspace; 16 GiB / 1,500-second cap. Sixteen/sixteen project is prepared but not
started; its matching complete regression is still running. The standalone
carry4 physical fit is also still running under its existing 900-second cap.

Module-memory carry suites are complete across wide4/8/16 and vector4/16,
including AW1 and full N: 30,030 successful normalizations, 385 domain rejects,
30 reset aborts, 8,820,591 vector host checks, 80,264 RAM helper checks and three
helper mutants. Private report archived at `carry-module-ram/report.json` under
the dated results folder. Vector NTT also passed all three fields at 4/16 lanes,
AW1/4/16, independent whole-integer checks and nine interface mutants. Core owner
is authorized to integrate these under a separate `VECTOR_IO` flag after the
current memory-only snapshots are frozen/validated. Real widening requires
sixteen CRT pipelines and forty-eight input Montgomery converters at sixteen lanes.

Further isolated work: registered stage-control NTT (32 extra clocks per square)
to shorten address/counter timing paths; carry divider specialization to proven
77-bit coefficient magnitude and 47-bit first-quotient magnitude. Both keep
earlier frozen candidates; resource savings and clock improvement need fits.
No predecode candidate has been fitted yet. Synthesis preparation supports
vector/predecode targets with all host ports virtual, and explicit banked/core
lane configurations. All 52 reference/preparation/evidence tests now pass on aethia.

## DSP accounting correction and new timing result (2026-09-29)

Earlier shorthand DSP counts copied Quartus's summary `Total DSP Blocks`,
which is actually `DSP Blocks Needed = raw fixed + floating + prime - estimated
recoverable dense merging`. It is not the raw placed block count. Preserve the
old summaries as historical output, but use `resource-accounting-v2.json` and
the corrected parser for planning. NTT module-memory4 uses raw24 / needed16;
carry module-memory4 uses raw222 / needed152. ALM summary counts likewise
describe packing-adjusted need rather than raw placement. The parser now emits
both separately when detailed reports exist and rejects inconsistent DSP totals.

Carry RAM4 fit: 72.00 MHz Fmax, -3.888 ns setup at100 MHz, +0.018 ns hold;
516 M20Ks, 14,338 ALMs needed. Limiting path is intermediate RAM lane2 through
cross-lane normalization to lane3's emit registers (~14.17 ns). Narrow-divider
four-lane synthesis reduces raw DSP elements222→174 and estimated postmerge
need152→112, while ALM estimates10539→11255. No narrow-only fit is claimed.
Retimed carry4 source `409f452266aaaa624a2e561f14c385aaf0433bdbcb545c07bae5faf4936d726a`
is now in a full physical probe `carry_pipe4-aw16-v1` (16 GiB /1,200 sec),
after passing full-size arithmetic; other lane/host/mutation suites also passed.
It adds two fixed clocks per normalization, preserving one group per clock.

Predecode NTT4 v2 at hash
`3694e9e2c0ab11866736754eeedbd65f2449e451dc275e0f3e98e7838af7f8f1`
passed full three-field 4/16-lane regressions and **passes100 MHz** in its field1
standalone fit: Fmax107.40 MHz, setup+0.689 ns, hold+0.021 ns, raw24 /needed16
DSPs, raw7382 /needed7191 ALMs, 512 M20Ks. It adds32 clocks per full square.
The packed predecessor reached95.01 MHz but lacked vector ports, so this is
not a perfectly isolated predecode-only area comparison. It remains a virtual-I/O
standalone result, not integrated clock or board sign-off.

The user also authorized the 27-bit-prime arithmetic experiment. See
`GFN16-27BIT-EXPERIMENT.md`; full-size mathematical checks pass, and the separate
native-width multiplier RTL is being implemented without replacing existing
field constants. Shared NTT multipliers, vector core boundaries and retimed carry
remain separate source-frozen experiments.

## Pipelined carry, matched multiplier probes and fit timeout (2026-09-29)

Retimed narrow carry4 completed its standalone fit: Fmax94.61 MHz, setup−0.570 ns
at100 MHz, hold+0.019 ns, raw174 /needed112 DSPs, raw12533 /needed11908 ALMs,
516 M20Ks. This improves on the72 MHz generic module-memory carry, but still
does not pass100 MHz. The new critical path is setup-only `base_reg→bound`
(10.634 ns), no longer intermediate RAM→digit emission. Next isolated carry
variant will pipeline the coefficient-bound calculation within existing reciprocal
setup clocks, not add steady-state group bubbles.

The integrated memory-only4/4 run actually reached its1,500-second execution
limit after placement/routing, exit124; no final fit or STA reports were emitted.
This is not a passing fit or an FPGA capacity failure. The exact same prepared
snapshot is rerunning with a2,700-second cap and unchanged16 GiB memory bound;
original and extended logs remain separate. No integrated timing claim yet.

Standalone Montgomery27 at
`4c8d9f32654c902f80274d160d01ae0bd80f41854ac6529da5a76fa347f9384a`
passed all three selected primes, 76,518 exact outputs, 954 reset cancellations,
14,154 invalid-cycle hold checks, input/parameter rejection probes and24 mutants.
The frozen32-bit helper also passes the identical vectors/scoreboard on the new
primes. Sequential physical comparisons use identical5 ns constraints for both
implementations at each of the three fields; those fits are in progress, not
assumed to achieve200 MHz. New manifests explicitly include field profile and
P/Q constants. `completed-fit-accounting-v3.json` supersedes ambiguous resource
shorthand across all12 earlier completed fits. All60 preparation/reference/gate
tests passed before launching the comparison queue.

Vector core snapshot `18fe0ae9b5a278b084e1ff53bc1ad54c94a9e8fcede78f6117822647e9bf2f06`
passes the full4-lane regression and13 fault checks: cold639,418/warm377,266
clocks. Its prepared fit snapshot matches all22 RTL dependencies and7 flags.
Sixteen-lane normal arithmetic tests measured cold356,794/warm94,642, but its
final fault-injection/compatibility gate is pending. A16-lane address mutant was
initially a no-op because its N8 test wrapped an8-word increment; the corrected
test uses N32 and runs into a fresh artifact directory. Do not publish that
sixteen-lane milestone as fully gated until the corrected report passes.

### Integrated fit completion and vector gate follow-up

The exact original module-memory4/4 project completed its extended run in
31m05.72s (exit0, peak RSS7,195,188 KiB). It fits, but misses100 MHz:
Fmax69.55 MHz, setup−4.379 ns, hold+0.018 ns, raw326 /needed221 DSPs,
raw38,512 /needed35,847 ALMs, 2,053 M20Ks and33,622,016 logical RAM bits.
This is integrated evidence, not a standalone-clock substitution. A source- and
configuration-checked planning projection at65 MHz is3.88548 hours/candidate
using one measured cold737,722 plus1,911,813 warm475,570 squares. That65 MHz
projection is below the reported internal Fmax, not a rerun closing65 MHz or
hardware/board validation; no exponent worker or PrimeGrid proof overhead is
included. Evidence is archived under `square-modulemem4-fit`.

Corrected vector16 v2 passed1,255 cases and13 non-equivalent mutants. Its
baseline compatibility also passed for vector-off4 and original stream. Warm
94,642/cold356,794 clocks are now correctness-gated, but not clock-qualified.
All22 source hashes and7 parameters of the prepared vector16 fit match that
report. Its integrated2700-second/16 GiB fit is now running. In parallel, the
validated carry bound-setup pipe_v2 is fitting at100 MHz. At most two physical
compiler jobs are active; standalone helpers do not establish integrated clocks.

All six paired27-bit multiplier fits completed. Each new field uses raw3 DSPs
with native27 versus raw5 for generic32 on the SAME primes. This is not a
three-to-one claim for an ordinary multiply; it includes modular reduction.
An isolated sparse shift/add reduction experiment is now testing, while agents
continue FAST_ARITH integration, a16-word host adapter for64-lane NTT, and a
streaming carry architecture to eliminate the96-bit coefficient RAM roundtrip.

Sparse27 reduction is now independently validated at SHA256
`501d0ce309a3915f7aed0f3bde14ba1ee8d56ddc5f6abef1f2f5bb572d64db4b`:
76,518 outputs,954 cancellations,14,154 invalid-cycle hold checks,19 injected
faults,12 invalid inputs,two parameter rejects and30,009 arithmetic identities.
The failed preflight P1 decomposition was fixed by including its2^22 term before
any passing RTL claim. Frozen generic/native helpers remain unchanged. All three
sparse physical snapshots match the passing report; they are prepared, not run.
No resource or clock saving is yet claimed for this new variant.

The64-lane NTT component is fully gated (all fields/runtime sizes/fullN/repeated
bigint squares plus five routing/upper-lane mutants), measured19,733 clocks per
field square. It is not yet integrated with16-word host I/O or physically fitted.
The independent streaming carry prototype passed its first4-lane fullN checks;
its remaining16-lane/AW1/mutation gates are still in progress. Do not conflate
these component results with full-core throughput.

### Bound-setup timing closure and new source-gated probes

The four-lane bound-setup carry pipe_v2 now PASSES the requested100 MHz
standalone internal timing: Fmax109.40 MHz, setup+0.859 ns, hold+0.018 ns.
Raw DSP171 /packing-adjusted need108; raw ALM12,668 /need12,064;
7,851 registers;516 M20Ks;8,454,144 logical RAM bits. This is the exact
validated17d3f703 source, unchanged32886 kernel clocks. Previous pipe was
94.61 MHz. New worst reported setup path is previous_r1[4]→suffix[14],9.312 ns;
the slow-corner and fast-corner summaries explicitly report worst-case conditions.
This does not qualify the integrated/vector design at109.4 MHz.

The freed second compiler slot now runs the three sparse27 comparisons in order,
each at5 ns, while baseline vector16 continues physical fitting. No third fitter
was started. FAST4 at9ccea541 is prepared/source-gated against its passing
1,255-case/13-mutant report:25 dependencies andeight architecture flags.
FAST_ARITH is now explicit in the common configuration model; the evidence
gate rejects mixing a retimed regression with a baseline fit or vice versa.

Streaming carry final reviewed regression passed12,062 normalizations,
218 domain rejects,28 malformed-stream rejects,34 reset aborts,5,917,850 host
checks and585,638 producer bubbles, plus AW17 checks andeight mutants. Its
four-lane physical snapshot matches allfour dependency hashes, but has not run.
The raw RAM reduction is8,454,144→4,259,840 bits; physical M20Ks remain unmeasured.
Twenty-nine targeted preparation/summary/evidence tests pass with these targets.

Current-status chart was regenerated privately with the fully gated baseline
vector16 milestone:1809.3816274 seconds (~30.2 minutes) at hypothetical100 MHz.
This is not an integrated clock claim; the published repository was not changed.
The plotted variant still has separate butterfly/pointwise hardware: analytical
launch duties are65536/94642 and12288/94642, not an aggregate DSP switching
measurement. Measured NTT phase occupancy is78073/94642 (~82.5%).

First sparse27 physical fit is complete and internally closes200 MHz: P1
rawDSP1,needed1; rawALM138,needed179; registers154; Fmax244.38 MHz;
setup+0.908 ns,hold+0.064 ns. This compares with rawDSP3/rawALM114/Fmax192.05
for the frozen native27 helper on the identical P/Q and5 ns constraint. Two
DSPs were replaced by24 rawALMs without increasing pipeline latency or II.
P2/P3 fits continue sequentially; the vector16 integrated fit remains separate.
NTT owner will test a separate27-basis arithmetic engine after freezing the
current64/16 host adapter, using the already-validated sparse helper.

### Eight-processor iteration policy and cloud pilot authorization

User explicitly requested eight processors per Quartus job. New prepared probes
now default to NUM_PARALLEL_PROCESSORS8 and record compile_processors in their
manifest; existing running/frozen projects retain their original settings. The
two-concurrent-compiler and16 GiB per-job caps remain. A frozen-input cloning tool
prepares exact source/constraint/seed comparisons without copying old compilation
databases. The validated carry-v2 cpu8 comparison is prepared but not run.

User approved testing C4 Granite Rapids, H4D Turin andC4D Turin under a$30 total
pilot allowance from a stated$295 credit, with shutdown/cleanup. Confirmed target
project is gsbot-504619. Read-only CLI preflight currently denies project billing
and service access to the active account; no cloud resource/API was created or
enabled, no license moved, and no spend incurred. Do not silently switch projects
or identities. Cloud work needs the user to resolve access; aethia work continues.
For C4, explicitly verify Granite Rapids/minCPU in a supported zone rather than
assuming all C4 shapes use it. H4D minimum listed size is192 physical cores and
requires particular quota/cost care; it is not a small16-core alternative.

### Streaming-carry physical result and first cpu8 integrated run

Streaming carry4 completed successfully at the requested100 MHz:
M20Ks260 (versus516 nonstream), RAM4,259,840bits, rawDSP171 /needed108,
rawALM12,959 /needed13,007, registers7,998; Fmax108.19 MHz,
setup+0.757 ns,hold+0.020 ns. Its exact source67ab9b60 remains unchanged and
matched the final reviewed regression. This verifies the256-M20K reduction at
the component level, not an integrated-clock or whole-core resource result.

The freed compiler slot now runs `square_core_fast16-cpu8-v1`: core9ccea541,
25 source-matched dependencies,eight architecture flags,eight processors;
90-minute execution limit and unchanged16 GiB per-process address-space cap.
The older baseline vector16 two-processor fit continues untouched. New global
default8 tests passed the full68-test Python suite. Both4/16 FAST regressions,
all13 injected faults each and baseline/default compatibility are now complete.

All three sparse27 fits use one rawDSP and pass200 MHz; reported component
Fmax values244.38/250.13/245.64 MHz. The64-lane/16-word host wrapper is fully
validated at a49b2e6f with eight mutants; isolatedNTT27 arithmetic is still being
tested. The root-recurrence proof passed25,165,824 numerical comparisons and
1,966,082 geometry checks; root generation remains an isolated prototype effort,
not an integrated replacement for the arbitrary cached-root interface.

### Cloud project correction, terminal fit evidence, and 36-bit experiment

User explicitly selected project-a2417519-1d17-4419-bfe instead of the inaccessible
gsbot project. Billing is enabled and the active account has Owner/IAP access;
the stated credit balance is not independently verified. Global CPU quota is12,
but C4 andC4D regional quotas are8 and available small shapes are2/4/8/16 rather
than12. Plan is sequential8-vCPU workers, maximumone VM, two-hour server-side
DELETE deadline, auto-deleted200GiB disk, no attached service account, private
pilot network and IAP-only SSH ingress. Total user authorization stays$30.
IAP/OSLogin APIs and the dedicated network were created; no VM has been created.
User separately approved the same QuartusPro26.1 EULA and normal evaluation
activation on temporary workers. Never copy machine-bound trial state.

The older baseline vector16 fit ended with exit124 at its actual2700-second
execution limit. This is neither successful timing evidence nor a resource
capacity failure. It was not restarted. The independently prepared FAST16 cpu8
fit remains live; synthesis completed and the fitter is running.

IsolatedNTT27 is now fully verified at16/64 lanes across allthree fields,
all runtime sizes through65536, repeated bigint squares, canonical input/reset
checks andfour mutants. Radix stays2^32. The root-recurrence27 prototype also
completed its final gate:20,387,520 active root-word comparisons andten mutants.
Neither has an integrated clock/resource claim. SeparateNTT27 physical targets
retain their own source hashes and matching field profile.

User requested trying36-bit arithmetic. A separate experiment will compare raw
27-bit, inferred36-bit and explicit four18x18-partial-product multiplication with
identical three-register-stage latency. TwoDSPs+externaladder is the vendor's
raw36x36 configuration, not a measured whole modular-multiplier cost. For our
unchanged digits, anytwo36-bit fields have product<2^72, insufficient for the
full doubled centered-CRT bound4*65536*(1e9-1)^2. No two-field core substitution
is authorized by operand width alone. An independent agent owns sparse36-bit
modular arithmetic and exact limited-base range proofs; no current core changed.

### 36-bit physical comparison, 64/16 core, and cloud worker

All raw multiply probes pass200MHz internal timing, at identical three-register
latency. Raw27 uses1 rawDSP/1 needed,2 rawALMs,Fmax407.50MHz. Inferred raw36
uses3 rawDSP/2 packing-adjusted needed,35 rawALMs,Fmax265.32MHz. Explicitfour
18x18 partials use4 rawDSP/2 needed,63 rawALMs,Fmax242.31MHz. Therefore the
vendor's two-DSP raw36 configuration is not an observed two-raw-block placement
in these probes. The final reviewed regression replays every vector without
resets before a cancellation-stress pass, checks invalid input/parameters and
nine mutants. Originalfailed/mutation-build runs remain preserved.

The six-stage36-bit sparse Montgomery multiplier (R2^36, II1) passed103,479
outputs,2,130 canceled requests,19,740 holds,12 inputrejects,two badparameters
and31 mutants. FrozenRTL b90c014d41e15db47a865890ceade8590daeac1b4c9929f318462826c25e6596.
Allthree matched5ns physical fits pass200MHz: rawDSP3/needed2 each;
rawALMs225/227/237; Fmax257.86/251.76/254.84MHz; holdpositive. Compared with
three sparse27 fields, this is not an area win and still requires three fields
at our sample/full base domain. No full36-bit NTT/core replacement is selected.
Full fit/STA reports and summaries are privately archived under raw36-fit and
multiplier36-fit. PublicGitHub contents remain unchanged.

The c6dad92564/16 core passed its main full-size/14-mutant gate and equal16/default
compatibility; invalid-profile validation is finishing. Full-N cold298466 and
warm36314 = conversion4101 + roots262152/0 + NTT19743 + CRT4158 + carry8312.
This corresponds to about11.6minutes at hypothetical100MHz, not fitted timing.
New target square_core_fast64_carry16 has27 source dependencies. The integrated
estimate checker now validates derived io_lanes/host_adapter metadata instead
of ignoring it. Parentpreparation/evidence/manual-status suite:76 tests pass.
The FAST16 cpu8 fit is still running under its90minute execution limit. Separate
full-size NTT27_64 P1 fit is now running at10ns,8processors,45minute limit;
allthree dependencies match its full-size passing regression.

Userapproved allsix iteration-loop improvements: staged validation, exactbuild
reuse, additional cloud capacity, boundedparallel ownership, bottleneck-directed
arithmetic changes and evidence-qualified area/speed tracking. Build-cache
utility passed18 independent/concurrent/invalidation tests and a real cold/warm
Montgomery36 smoke test. Only verified build products are cached; freshoracles
and mutations still run. Corecachehook is opt-in and waits for currentreports
to finish, avoiding on-disk harness changes during active evidence generation.

Cloud policy supersedes earlier entries: user canceled CPUcomparisons, selected
C4D for useful builds, then authorized C4 fallback. C4D in allfourus-central1
zones failed with capacity errors and no VM/diskleftovers. C4 fallback
gfn16-pilot-c4 (ID1253085359060932967) is running inus-west3-c,8vCPU/30GiBRAM,
IntelEmeraldRapids,200GiBHyperdiskBalanced, no serviceaccount, IAP-onlySSH.
Creation2026-09-30T01:36:08.531Z. Quartus officialdownloader/install wrapper is
running with explicitlyapproved EULA; no machine-bound license state copied.
Userremoved two-hour automatic deletion and explicitlydeclined backgroundbudget
guards. No automation, runtime deadline or guestshutdown timer is enabled.
Usecloud/manual_status.py for read-onlymanualchecks; totalauthorization remains
USD30. At01:43:36Z conservative lifetime estimate wasUSD0.0934, notactualbilling.
Do not recreate a rejected/declined recurringmonitor or a workaroundtimer.

Userexplicitlyapproved critical-path retiming toward150–200MHz. New isolated
streamingcarrypipeline work targets measured9.416ns RAM→transfer and9.423ns
quotient→suffix paths, keepingII1 while registering sums/comparisons/treelevels.
Generated-root27NTT is independently being integrated with explicitprofile API;
initial serializedseedloading trades morecycles for muchlessrootRAM. Neither
candidate has final full validation or fittedclock evidence yet.

### First completed FAST16 whole-core timing and pipelined carry launch

FAST16 cpu8 fit completed successfully after65min06s (not a timeout): source
9ccea541,25dependencies,requested100MHz. Fmax82.28MHz,setup−2.154ns,
hold+0.017ns. RawALM219808/needed201846, rawDSP1196/needed768,
registers130693, RAM33652736bits/1979M20Ks. This does NOT close100MHz.
At a conservative planning80MHz the source-matched cold356834/warm94682
projection is2262.68294125seconds (~37.7minutes), excluding host/fullPRP
overhead. It was not refitted at80MHz; this uses the completed fit's Fmax.
Fullreports and criticalpaths archived in square-fast16-fit.

Actual worst integrated path: lane10.second_div.remainder[0]→carry suffix[9],
12.375ns/15logic levels. Routing6.481ns (52%),cells5.629ns (45%),Tco0.265ns.
That supports retiming the row-sum/classification/prefix/suffix chain rather
than claiming the already-fast multiplier sets the wholeclock.

Separate streamingcarrypipe9838c6852cac57f7901f8b57dcbb4ee11b7fa129ef86e40158d67cc789b06e5e
passed52 regression steps and19 mutants, full4/16/AW1/AW16/AW17 rejection,
84,051 independentscan responses and1,329resetcancellations. II1 and97setup
clocks are preserved. FullNcycles32899/8329 add14/20 over frozenstream.
Onlydependencies are SP RAM and narrowdivider; scanmodule is in the samefile.
Source-gated carry_stream_pipe4-aw16-200-v1 nowfits at5ns on aethia,30minute
limit,8processors; no timing improvement claimed until completion.

CloudQuartus installation finished with independentvendorhash verification.
Normal30dayevaluation was started through the vendor GUI (no newlicensepurchase,
no copying aethia's activation). The validated64/16 project is now compiling
through the cloudQuartus syn/fit/sta flow,8workers,24GiB/process limit and3hour
job deadline. This is a compile-job timeout, NOT a VMdeletion/shutdown timer.
The cloud's same-versionVerilator5.032 build took123.88s and full-N oracle435.75s;
all12 squares/10 directreadbacks passed from frozen source/vector hashes.
This is a successful additional-host reproduction, not a newarchitecturegate
or a controlled host-speed comparison. Cloudresults and sourcehashes archived.

### Carry retiming result and next measured bottlenecks (2026-09-30 UTC)

The source-matched streaming carry4 pipeline completed its 5 ns fit: Fmax
159.69 MHz, setup -1.262 ns, hold +0.018 ns. This does not close 200 MHz.
Compared with frozen streaming carry4 at 108.19 MHz, reported Fmax rises
47.6%, with raw DSP171 / adjusted108 and 260 M20Ks unchanged. Raw ALMs12014,
adjusted11618, registers9861. Cycles32899 versus32885 add14 at full N.
The result is a standalone virtual-I/O probe, not whole-core or board timing.
Full fit/STA, manifest, log and critical paths are archived in
`results/throughput-20260929/carry-stream-pipe-fit/`.

The new worst path is inside first_div: lows[4][3] to unsigned_q[47],
6.486 ns data delay, seven logic levels, 70% cell / 26% routing / 4% Tco.
The quotient correction combines addition, comparison and corrected addition.
An independent new divider/carry candidate will split this chain while retaining
II1 and updating all valid/tag/latency contracts; frozen helpers remain unchanged.

FAST16 endpoint-group diagnostics establish that carry alone is insufficient:
at requested100MHz, NTT endpoints have -1.731 ns worst slack (middle RAM to
butterfly pre_w), CRT -1.583 ns (data RAM to delta2), controller -0.840 ns,
and conversion -0.800 ns. These are endpoint-group reports, not disjoint counts
of physical registers. Whole-core critical-path evidence remains authoritative.

Generated-root27 passed its final hardened gates for L16/L64, all three fields,
AW1/AW16 and every runtime size: 1,242 operations, 11,016,012 coefficient
checks, 924 reset aborts, and all10 mutants rejected. Frozen top e21c86e5
uses8,738 profile words/field at L64 versus196,608 cached-root words, plus
recurrence registers and multipliers. Warm arithmetic increases from19,733 to
24,987 cycles; this is an explicit storage/throughput tradeoff, not a claimed
speedup. Added separate synthesis targets with all six source dependencies,
explicit profile ports (no root_we), matching27-bit fields and R=2^32.

Manual cloud check at02:22:33Z found the authorized C4 worker RUNNING and
Quartus fitting the frozen64/16 whole core. Conservative lifetime estimate
USD0.5803 plus USD3 reserve, not actual billing. No background guard or runtime
deletion/shutdown policy was enabled.

The synthesis/evidence unit suite passed78 tests on aethia after the generated
root target addition. All six RTL dependency hashes match both full-size lane
reports and the mutation report. Launched source-gated
`ntt27_generated64-aw16-p1-v1` at10ns,8processors,16GiB/process and3600s
compile-job limit. The pre-existing cached-root64 fit and cloud whole64 fit
were independently confirmed live; neither was restarted. The generated-root
fit result remains pending, with no physical resource or clock claim yet.

### NTT routing retime candidate and physical queue update

Implemented a separate cached-root NTT27 routing pipeline, source69a665dd,
registering the root XOR/rotation boundary and aligning data, pointwise roots,
metadata, request valids and eight-clock writeback tags. Existing RTL remains
unchanged. N16/P1/L16 smoke passed6 steps; full L16/L64, three-field,
all-runtime-size/AW1/4/16 gates are now active on aethia. Expected full square
cost is35 extra clocks, not a measured clock/throughput improvement. Mutation
fixtures useN1024 to exercise multiple rows and both bank halves. Documentation
and exact identities are in NTT27-ROUTEPIPE-NOTES.md. Synthesis/evidence unit
suite passed79 tests after adding the isolated prepare-only targets.

The earlier cached-root NTT27_64 physical run reached its actual2700s limit
(exit124,45:00.31 elapsed) during routing. Its compiler handle terminated and
processes were confirmed absent; no fit/clock result exists. This is a timeout,
not proof of device-capacity failure. Log and manifest archived in
`results/throughput-20260929/ntt27-cached64-timeout/`; not automatically restarted.
The generated-root64 fit remains live. The freed slot is used for the fully
source-gated carry_stream_pipe16-aw16-150-v1 at6.666667ns,8processors,
16GiB/process and3600s compile-job cap. Actual150MHz closure remains unproven.

Manual cloud check02:30:40Z: running, conservative USD0.6817 lifetime estimate
plus USD3 reserve, not actual billing; no budget action required at that check.

Routepipe full-size P1/L16 subsequently passed20 cached-square operations and
1,310,720 coefficient checks, measured32,912 clocks/transform and4,104/pass
(78,136/five-phase square). N65536 direction/order and reset tests passed too;
all-field/L64/mutation gates continue. Independent read-only review found the
t→t+1 routing register→t+2 butterfly→t+8 writeback alignment sound. No physical
clock claim or core integration is made from these partial results.

### Frozen divider retime and atomic27 preparation

Retimed divider helper15ef37c0 and carry topf8d12e7a passed the complete70-step
gate, including all24 injected faults. Independent integer divmod checked100,370
outputs and3,300 canceled tokens; carry checked12,422 normalizations,218domain
rejects,154reset aborts,28malformed-stream faults and5,918,447host checks. Both
lane widths and AW1/AW16/AW17 rejection/recovery passed. Full-N carry cycles
are32,905/8,335, exactly6 more than frozen stream_pipe, not6 per row. New
separate synthesis targets use four source files, with the frozen stream_pipe
included solely for its scan helper. No clock improvement is claimed yet.

Added prepare-only atomic27 whole-core targets for16/16 and64/16. Their exact
13-source closure includes the checked digit reducer, native27 NTT/host wrapper,
CRT27 and private root streamer in the new core file. Only AW/NTT_LANES are
emitted as parameters; fixed architecture localparams are not overridden.
Manifest explicitly records all three P/Q/R²/generator tuples and radix32.
The existing integrated estimator deliberately does not yet accept these new
targets; normalized per-profile reports and final fits are still pending.

Synthesis estimates (not final fit/raw placement): cached-root27_64 uses100,033
ALMs/39,701 registers/64 post-merging DSPs; generated-root27_64 uses95,423
ALMs/71,858 registers/128 post-merging DSPs. Thus generated roots clearly trade
extra arithmetic/registers for storage; they are not a free throughput win.
Cloud original31-bit whole64 synthesis estimates410,449ALMs (96%) and1,056
post-merging DSPs. Its final placement/timing is still pending.

Manual cloud check02:40:36Z: running, conservative USD0.8058 lifetime estimate
plus USD3 reserve, not actual billing. No runtime/background policy changed.

### Retimed CRT27 complete gate

Implemented new isolated CRT27f38bb213, splitting r1_modP2, signed28-bit
difference and correction across registers (+2 clocks), and splitting delta3
difference/correction (+1). Payload and valid edges remain aligned, reset
cancels all eligibility, and output holds on invalid cycles.64-stage/II1,
accepted edge k→k+63; original61-stage module and all cores remain unchanged.

All45 gate steps passed:25,833 exact centered-CRT outputs,4,891 canceled tokens,
11,470 invalid-cycle hold checks, nine noncanonical input rejects, and all17
fault models rejected. Resets cover every pipeline age1..65. Independent review
found no alignment/width issue. Exact source/bench/harness/vector hashes and
reports archived in crt27-retimed; source-matched5ns project is prepared only,
waiting for a physical slot. Parent preparation/evidence suite now82PASS.

The next divider area experiment uses≤27-bit lhs /24-bit reciprocal tiles,
then a balanced registered sum tree. Current96-bit reciprocal version remains
separate; a later precision-specialized candidate can exploit m<2^W to use
floor(2^W/b) extracted exactly from reciprocal96. These are arithmetic design
directions, not DSP/Fmax claims; both still include their low32 estimate×base
product beyond the main reciprocal partial products.

Manual cloud check02:50:07Z: running, conservative USD0.9248 lifetime estimate
plus USD3 reserve, not actual billing. Aethia has roughly51GB free; no simulation
artifacts or caches were deleted. Current physical fits continue unchanged.

### Algebraically folded NTT routing candidate

Implemented separate folded-root engine475a7500 from the routepipe candidate.
The identity R XOR rol((b XOR B)&M,r) = [R XOR rol(B&M,r)] XOR rol(b&M,r)
allows the data-bank XOR contribution to be captured in the narrow read-edge
control word, removing the final BANKS-wide root XOR permutation. M is the
broadcast mask, explicitly not the physical root-read mask. The existing
route register, eight-clock writeback distance, pointwise bypass, host API and
all valid/address tags remain unchanged. No existing core selects this candidate.

The independent index check passed1,126,248 cases covering every bank/data-base,
rotation and mask for index widths1..7; the common root-base XOR cancels and is
arbitrary. Six-step N16/P1/L16 smoke passed. Full all-field/L16/L64/N2..65536
integer/reset gates plus13 injected faults are running. Independent actual-RTL
review found the capture/mask/rotation/broadcast timing sound; no edits required.
Details in NTT27-FOLDED-ROUTING.md. No physical ALM/Fmax benefit is claimed yet.

Quiet fitter logs were revalidated against process CPU state, not interpreted
as stalls: cloud whole64 fit had accrued3h56m CPU over41m38s wall time (~567%),
with running worker threads. Aethia generated-root/carry fits were similarly
active (~464%/~406% CPU). No jobs were restarted. Aethia disk headroom is48GB.

The atomic27 whole64 combined oracle hit its600s per-command limit; this is a
simulation timeout, not a diagnosed arithmetic failure. Original failed evidence
is preserved. Recovery will use the same source/bench and verified executable,
splitting only at reset-defined LOAD boundaries, never within LOAD_KEEP chains.
No whole64 gate/fit approval until all original cases and remaining faults pass.

### Physical results: carry16 timing and whole64 capacity

Streaming carrypipe16 source9838 completed: Fmax138.62MHz,setup-0.548ns at
6.666667ns,hold+0.018ns. It does NOT close150MHz. RawDSP675/adjusted426,
rawALM43725/adjusted41736, registers35819, RAM4259840bits/224M20K. This
reinforces that the four-lane159.69MHz result cannot be extrapolated to16 lanes.
Full fit/STA/summary/log archived in carry-stream-pipe16-fit.

Cloud original c6 whole64 fit terminated with exit3 after61m31s. Error25153:
44147 LABs required versus42720 available, about3.34% excess. This is an actual
device-capacity failure, not timeout, licensing or VM-memory exhaustion.
No whole64 fittedclock exists. Log, plan report, synthesis summary and source
manifest are archived in cloud-core64-fit-failure. The private chart now reads
and source-checks that diagnostic;64-lane rows explicitly require area reduction
as well as clock closure. The public repository remains unchanged.

Routepipe69a nowpassed both L16/L64 full gates. Folded475a L16 passed112 steps
including13fault variants and whole-integer checks;L64 remains running. Started
the source-matched folded16 5ns fit on the same existing cloud VM,8workers,
24GiB/process,3600s compile cap. New aethia slot now runs validated carrydivpipe4
f8d/15ef at5ns,8workers,16GiB/process,3600s cap. Generated-root64 fit remainslive.
These are compile-job limits, not VM shutdown/deletion policies.

Userexplicitly requested eight threads on aethia. Queued a separate source-/
vector-matched1-versus8 Verilator runtime experiment after current core27
recovery, with controlled CPU availability. Existing baseline/correctness reports
and production defaults stay unchanged until evidence is available. Compiler
workers and runtime model threads are separate settings;Quartus alreadyuses8.
