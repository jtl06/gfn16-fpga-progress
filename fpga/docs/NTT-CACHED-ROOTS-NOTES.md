# Resident root-phase candidate

`genefer_ntt_parallel_cached_engine.sv` adds compact resident phase tables to
the frozen four-lane parallel engine. Existing engines/core remain unchanged.
No vendor fit, clock result, or integrated speedup is claimed here.

## Contract

The new two-bit `root_phase` port selects the table for **idle scalar root
writes** and is **captured when an operation starts**. Subsequent changes while
busy do not affect that operation. Existing `dif`, `op`, normalization, host
load/read, done/reset, bank-conflict and throughput contracts remain intact.

Let Nmax=2^AW be the physical capacity:

| root_phase | Contents | Stored logical indices |
| --- | --- | --- |
| 0 | Montgomery twist psi^i*R | 0..Nmax-1 |
| 1 | Montgomery forward omega^i*R | 0..Nmax/2-1 |
| 2 | Montgomery inverse omega^-i*R | 0..Nmax/2-1 |
| 3 | Ordinary fused postconversion psi^-i/N | 0..Nmax-1 |

For phases 1/2, writes with `host_addr >= Nmax/2` are **ignored**, not truncated,
aliased, or reported as errors. Thus the existing generator may still emit Nmax
words for all phases; the unused upper halves cannot overwrite another phase.
Op2 table multiplication requires an N-entry table, so starts selecting phase
1/2 for op2 are rejected with error/done and no busy operation. Op1 square and
op3 scalar multiplication do not read roots and can select any phase.

The engine does not own cache-valid flags. The caller must load all required
phases before using them, invalidate its cache state after reset, and reload
for a different transform N. For the integrated fixed-AW core, changing the
candidate radix/base **does not** invalidate roots. RAM is intentionally not
reset. Runtime sizes below Nmax remain supported, but the caller must supply
roots for that runtime N in the same physical phase regions.

## Physical array intent

For K=2*LANES, each bank has one data RAM and **one root RAM**, not four
N-word memories or per-lane table copies. For the full-size configuration:

```
D = Nmax/K; H = Nmax/(2K)
root row offsets = 0, D, D+H, D+2H
root row lengths = D, H, H, D
root depth/bank  = 2D+2H = 3Nmax/K
```

AW16/LANES4 elaborates eight root arrays of **24,576 x 32 bits**, totaling
196,608 words = 3Nmax words/field. The test inspects the generated Verilator
header to verify this exact logical array shape independently of performance
counters. Each array has one synchronous read and one idle host write port,
with an M20K inference attribute. This proves the declared/elaborated compact
structure, **not** successful vendor RAM inference or placement; a Quartus
fit must still check depth/width packing and timing.

For small Nmax<K, each phase rounds its per-bank allocation up to at least
one word. Some banks/phase slots are unreachable, so AW1 does not have an exact
3Nmax physical allocation. This rounding is deliberate for portable parameter
elaboration and does not affect the AW16 capacity calculation.

No new data-array capacity is required. Compared with one active root table,
the full-size design adds 2Nmax root words/field, approximately 768 M20Ks across
three fields using existing packing estimates. Confirm actual counts before
combining this with additional carry memories.

## Cold versus warm execution

On reset, the future core should mark all phases invalid, then fill them once.
It may use existing four N-word generator streams (upper halves ignored), or
shorten forward/inverse streams to N/2 words for a 3N-word cold fill. Mark each
phase valid only after its final **accepted write**; root-stream done coincides
with the last valid word and must not prematurely start an operation.

For warm squares, select phase0 for twist, phase1 for forward DIF and spectral
square, phase2 for inverse DIT, and phase3 for postconversion. Skip root
generation/loading entirely. The engine arithmetic remains **311,535 cycles
per field-square** at N65536/LANES4. Warm integration can avoid approximately
262,144 old scalar root-fill payload cycles per square, plus associated
controller overhead; this saving requires the future core's valid-state logic.
Initial generation time is not silently removed from cold measurements.

## Independent tests

Remote workspace:
`/home/jtl/gfn-fpga-lab/agent-work/ntt-cached/fpga`.
`artifacts/cache-full-v1/report.json` reports **passed**, including all three
rejected cache mutants and the full-size elaborated array-shape checks.

```sh
. /home/jtl/gfn-fpga-lab/fpga/tools/aethia-env.sh
python3 -m reference.ntt_cached_regression --output artifacts/cache-full-v1
```

The test loads four phases **once**, poisons forbidden upper-half write
addresses to verify they are ignored, then runs multiple changed/recurrent
input squares with **no accepted root writes between them**. It changes
root_phase and attempts root writes while busy to check phase capture and
write exclusion. Tests cover all three fields with explicit AW1/AW4/AW16,
zero/-1/max/small-radix inputs, a base change without reloading roots, and
full-size recurrent modular-square inputs. Every intermediate transform is
checked against independent integer modular arithmetic; three-field outputs
are checked against whole-integer modular squares and small-size schoolbook
convolution. A separate phase0-only path checks general forward/inverse
transform semantics, and reset/operation-accounting checks are retained.

Negative controls remove forbidden-write filtering, substitute the live phase
for the captured phase, or overlap forward/inverse regions. Each must fail
the independent value oracle. Four-lane bank/data-path checks from the frozen
parallel candidate remain applicable, with active collision assertions here.

Candidate RTL SHA256:
`b9b330c1d6a42e8025df2824796b8448b59440f4140fe336a5755ce899eb4d84`.
