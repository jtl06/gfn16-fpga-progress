# A-next delta-specific qualification map

Owner: block_carry. This is a coverage plan, not a new fit-launch gate.
Direct prototype: frozen30SV, command-ready/response-valid ABI, no F2 recurrence.
Selector trunk: additive parameter/ABI wrapper, qualified separately.

| Changed interface or state | Existing applicable evidence | Minimal remaining qualification |
|---|---|---|
| A10 ordinary-domain three-pass transform → unchanged CRT/block carry | Direct wholeAW5/AW8 value/cycle gates; independently passedAW16 sixteen squares/eight full images,1029d023; unchanged arithmetic cells and carry proofs remain applicable at their exact pins; valid-base5051-operation E2E independently PASSd648650b including both host negatives; original source uninterrupted1000 actualPASSd0accac2/owner277648eb | Independent fullN continuous replay remains. Do not rerun unchanged divider/CRT/multiplier cells merely for lineage naming. |
| Independent carry-block ports replacing contiguous host16 | Six per-field AW5/AW8 real-RAM probes, owner reports6/6PASS; raw E0/E1 masks/offsets/conflicts/reset checked; fullN direct native image checks | Independent batch replay; fullN nonuniform long-chain checkpoints cover spatial cases missed by uniform representative recipes. No claim that source address enumeration is an exhaustive native RAM proof. |
| Four-word format3 load/epoch and CT→square→GS controller | Actual cold/warm counts9/0 roots, seed0, phases114/193/17709; original engine profile contracts reused only where byte-identical; eleven integration cases independently PASS440545d0 | Directed delta scope closed: header0/header3 corruption, reset atword3/commit/check, partial-field done and field error at each phase, actual RAM quiet tail and complete reload/recovery. This is not an exhaustive fault union. |
| Registered admission and image quarantine in composed backend | A4b backend exactly preserved apart from sequencer module binding; A-next actualfive-case admissioncontrol b14f955d and allfive typed native mutants independently PASS440545d0 | Directed delta scope closed. A4b historical mutants alone do not count as composite native evidence. The inherited bare callback's bool-returncode caveat is documented; actual native integer return codes and machine exact-type checks were verified. |
| Public host interface | Command host and canonicalizer unchanged from independently tested A4b; directnewcore normal/holds/reset and final canonical images pass | Explicit command-host fullPRP/longchain driver. T5b pulse load/read/start, old canonical-read preservation and T5b latency assertions are not inherited. Readback invalidates A4 prefill, so checkpoint-driven cold transitions must be modeled separately. |
| Static selector and unsupported combinations | v1flags-off568-square direct-parent lockstep passed9d855a4c; v2flags-offfd83f983/BLOCK7226624d/MERGED9b5c876c actual typed PASS | Independent replay of the guarded integer0/1 width repair and all three branches; retain bothv1 lint failures. No hidden pulse→command bridge or unsupportedF2 credit. |
| Physical resource/clock change | Source949 declared-boundary inventory passes; direct prototype fit packet matchesAW16 exact30SV | Native fit/resource/four-corner STA, then applicable DA/path diagnostics and independent+advisor review. No inherited T5b clock and no claim of whole-netlist coverage from source anchors. |

## Required long-chain scope

The carry-profile change makes r11 E2E-2 applicable: at least1000AW16 chained
squares with seeded doubles and periodic complete canonical checkpoints against
independent GMP arithmetic. Sixteen representative squares and5051AW5 PRP
operations do not replace it. Use the soak owner's frozen ordinary-integer
oracle, schedule, canonical checkpoint format, runtime identity and negative
loaded-state/boundary controls; add only the command-host driver and explicit
candidate lineage. A-next supports existingbase604832956, so the same mathematical
state/schedule may be reused as donor reference with original provenance intact.
No old T5b RTL result is thereby reclassified as A-next evidence.

Ten independently loaded100-square chunks establish exact arithmetic at each
boundary, but do not establish uninterrupted1000-square controller/cache history.
The uninterrupted case remains separate. A4 readback itself invalidates field
prefill without resetting the retained digit image; subsequent squares after a
checkpoint are cold-prefill/cached-root, not uninterrupted warm starts. Account
for those expected transitions explicitly rather than borrowing T5b counters.
No fullN numeric arithmetic runs on the Mac; admittedLinux reference generation
and native validation only. Duration/resource caps follow measured short gates.

### Retained-state contract (not checkpoint reseeding)

The additive `rtl/tb/anext_soak_v1.cpp` constructs one model once. Its only
reset/configure/full-load sequence is before the square loop (lines76–83).
The checkpoint lambda (85–104) issues only read opcode2, records actual returned
digits, and compares them with the oracle. It never writes expected digits back.
The retained square loop (108–132) issues square opcode5 and calls that read-only
lambda; it neither resets nor recreates the model, reloads digits, changes base,
nor reseeds roots. The source guard pins this exact host-ABI derivative.

For1000 operations with checkpoints0/100/…/1000, the expected counts are one
model/reset,65536 initial digit loads,one root load,999 cache hits,10 prefill-cold
operations (initial plus nine read-induced transitions), and990 warm operations.
The event-only backend sum is21,913,089 cycles; checkpoint-command latency and
wall time are separate. This is uninterrupted retained-state qualification,
not ten independently loaded chunks and not a warm-throughput measurement.

The corrected continuous ticket `anext-soak-continuous-aw16-q1-v2` completed
actual native PASS at12:47:57UTC on GCP2/3/24GiB, invocation
`f521556cacef4ae6a5c673d3e505e329`. Reportd0accac2/gate6084c76b and owner replay
277648eb establish1000 operations/488doubles/11fullimages/21,913,089backendcycles,
one reset/load,10cold+990warm prefill and1rootload+999hits. Native admittedGMP
boundary replay is retained. Local owner replay checks308sources/170generated/
16artifacts/ELF and preserved digit arrays only; no fullN arithmetic executes locally.
Independent promotion replay remains pending. The predecessor's pre-lint/model
namespace failure remains preserved. No point-launch successor evidence is
inherited from this original30SV source.

## Deliberately not inherited or duplicated

- Original T5b E2E bases69/70/96/112 are outside the newAW5minimum300. The new
  eight-case successor uses301/300/448/7552 plus the four retained large bases,
  with independent certificates; no claim covers those rejected old inputs.
- T5b's93 targeted and eight pulse/prefill mutants are not blindly rerun against
  a different host/controller. Map each relevant invariant to the new admission,
  profile, ownership and checkpoint contracts; retired format2/recurrence-only
  paths are not present. Document uncovered surviving invariants rather than
  equating equal test counts with coverage.
- Standalone A10 arithmetic/profile mutant results retain their exact module
  scope. A newly connected controller error path needs its own integration
  witness, not a duplicate unchanged multiplier test.
- Exploration fits proceed under r53 source checks while coverage/review runs;
  promotion still requires independent evidence and advisor verification.
