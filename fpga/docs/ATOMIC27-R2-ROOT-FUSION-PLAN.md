# Atomic27 R²-root/input fusion: isolated plan and root gate

Status: dedicated root-profile validation **passed**. No core RTL is changed,
no whole-core simulation is started, and no fit/bitstream is requested here.
This experiment is separate from tiled routing and CRT-pair changes.

## Pinned starting point

- Precision-stream core ancestor:
  `genefer_square_core27_stream.sv`, SHA256
  `75eb580540fc6a7939f824182d244123e03e3b780e65e57722352564b145b648`.
- Reusable generic root generator:
  `genefer_root_stream32_r2.sv`, SHA256
  `7ca72dbdec54ab0cf7ff0f914b3f764f7751295e4ce60580eee5bd734eef210f`.
- Its unchanged four-stage generic32 Montgomery recurrence:
  `genefer_montgomery_mul32_pipe.sv`, SHA256
  `e8df84884f8d5a079d358cde9c4d349660df83460312781ace31ff2ce166def9`.
- All three fields remain P=104857601/69206017/67239937,
  Q=4190109697/4225761281/4227727361, G=3/5/10 and R=2^32.
  Operand width27 never changes the Montgomery radix.

## Mathematical substitution

Currently the checked canonical residue d is converted to dR, then multiplied
by the phase0 root R·psi^i with Montgomery reduction. Instead, load ordinary d
and use phase0 root R²·psi^i:

`Mont(d, R²·psi^i) = d·R·psi^i = Mont(dR, R·psi^i) (mod P)`.

Only phase0 seeds change. Four interleaved recurrence steps must still be
R·psi^4, not R²·psi^4. Phase1 and phase2 roots remain R·omega^(±i), and phase3
remains ordinary psi^(-i)/N. All root words remain canonical residues<P.

## Root gate first

New private files are `rtl/tb/root_stream27_r2.cpp` and
`reference/root_stream27_r2_regression.py`; the existing generic RTL and old
root bench/regression are unchanged.

The gate checks every coefficient for all four phases, all three fields and
AW1/2/3/4/16. Its ordinary modular oracle is independent of the RTL Montgomery
feedback. Twelve complete tables per profile run back-to-back, with start and
phase inputs deliberately changed while busy. Each small-N reset boundary is
tested; full-N reset points cover initial seeds, first feedback, middle and last
result/done boundaries. Every reset is followed by idle drain checks and a
complete different-phase restart without another reset.

Phase0 additionally checks the fusion identity for canonical reductions of
raw-digit boundaries including -1, P-1/P/P+1, 27-bit boundaries, the sample base
range and999999999. This oracle reduction is **not** a substitute for retaining
the RTL digit reducer in any later core integration.

Six negative format/control variants test wrong seed scaling, wrong recurrence
scaling, wrong inverse output scaling, wrong seed lane, wrong phase latch and
wrong done edge. Mutant builds explicitly pass the selected atomic27 P/Q/G;
none silently falls back to the original31-bit defaults. They are distributed
across all three fields at AW4, each with its normal profile already checked.

The queue uses aethia only, j2,6 GiB,CPU200%, a10 GiB free-disk guard, and the
shared compiler lock only around individual builds. Lock waiting is measured
separately from the180-second compile timeout. Source, executable, logs and
report identities are recorded in fresh artifact directories.

### Completed evidence

The aethia run `agent-work/root27-r2/fpga/artifacts/full-v1/report.json`
passed all 44 recorded steps: 15 normal models and six separately built mutants,
plus tool-version checks. Report SHA256:
`011e4b27822fec5ad722fc341724337948b74a25b992277b6f19902f5223c7a7`.
All recorded source, executable and log hashes were independently rechecked
after completion. Aggregate normal-model evidence:

- 18,096,288 checked root outputs and busy-input perturbations.
- 780 completed tables; 600 reset boundaries and 540 aborted tables.
- 5,900,940 canonical-digit twist identities.
- Every complete phase takes exactly N output clocks after the start edge,
  including 65,536 clocks at AW16. No whole-core cycle claim follows from this.
- All six negative variants failed at their intended root/done checks.

New bench SHA256:
`c97281ac35c8f4bcc092147150d58ebfc3ec56bee7b12cd1b3ec9c39e2d29843`.
New harness SHA256:
`fece5464e7a51de5ebc34d3eed2abc2f2b813b865dce7824c451d957eae28a41`.
These are simulation/oracle results, not formal proof or physical-fit evidence.

## Exact later core patch, subject to root results and review

Make a **new named core clone** from75eb, leaving all frozen cores and tiled
experiments untouched. Preserve the current16/64 NTT,16-wide IO, cached roots,
CRT27 and precision-stream carry.

1. Retain the entire signed96 whole-row `bad_digit` guard. It must reject a
   digit>=the latched base before any per-field reduction; reducing it moduloP
   would otherwise conceal the invalid input.
2. Retain all48 `genefer_digit_reduce27_pipe` instances, their full signed32
   input words, error signals and existing valid-mask assertions. Legal radix
   digits can exceed every27-bit prime. Never truncate to27 bits, bypass the
   reducer, or feed raw999999999 into a canonical sparse multiplier.
3. Replace only the48 following sparse Montgomery conversion instances with
   one registered canonical-residue boundary. Set each output-valid register
   to `state==CONVERT && reduce_valid && !reduce_error`, clearing it on reset;
   capture the canonical32-bit residue under that same condition. Gate data
   validity in FAILED/other states exactly as the old converter input was
   gated. Do not add a combinational load path from reducer output to NTT RAM.
4. Replace the inline private root generator binding with the separately gated
   generic `genefer_root_stream32_r2`, explicitly supplying AW/P/Q/GENERATOR.
   Remove or uniquely rename the clone's now-unused private root definition;
   do not change the ancestor helper. Preserve all root phases and cache
   completion/validity counters. The new core must have an explicit R² profile
   identity, since old phase0 cached roots are not interchangeable.
5. Keep last counted conversion commit before the distinct NTT-start edge.
   Keep early carry-start tied to that same last committed conversion row.
   Thus source digits cannot be overwritten before conversion drains, and the
   relative carry-setup versus NTT/CRT schedule remains unchanged.
6. Preserve the existing field/word skew checks, base/double latching,
   no-host chaining, root invalidation on reset/error and reset-required error
   quarantine. A late reducer token must never become a post-error NTT write.

No caller interface, prime basis, NTT schedule, root word count, CRT ordering,
carry algorithm or source digit read count needs to change for this substitution.

## Expected latency/resource effect, not a measured result

If the reducer accepts a raw digit at edge t, its result is registered at t+3.
The old conversion multiplier accepts it at t+4 and produces output at t+7;
NTT RAM commits at t+8. The proposed single register captures at t+4 and NTT RAM
commits at t+5. Expected improvement is exactly **three conversion fill clocks**:
`ceil(N/16)+9` should become `ceil(N/16)+6`.

All4096 full-N input row beats remain. Cold root loading, root throughput and
NTT arithmetic cycles are unchanged. Because carry-start and NTT-start move
together, the warm-small-N setup reservation should not be reduced separately
or double-counted. Whole-core tests must verify those expectations before any
performance report uses them.

Removing48 instantiated one-DSP sparse converters is a logical operation-count
opportunity, not a confirmed48-block whole-chip saving. The three generic32 root
recurrences remain, and placement/packing/clock effects require a later fit.

## Later integration gate, not launched by this task

After root review, require small/full16/16 and64/16 independent bigint squares,
doubled operations, max-base and reduction-boundary digits, special -1,
cold/warm cache, immediate/no-host chains, and reset near final reducer/register
and NTT-load edges. Explicitly fault omitted reduction, truncated digits,
wrong phase0 format, wrong valid delay, field/row misalignment, late error
tokens and old cached phase0 roots. Check exact conversion counters and all
unchanged phase counters. No core default or physical target changes yet.
