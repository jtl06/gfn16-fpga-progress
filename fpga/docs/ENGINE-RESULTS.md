# Memory-backed RTL arithmetic milestone — aethia, 2026-09-29

This is the **historical pre-optimization baseline**. The newer
[optimization audit](OPTIMIZATION-AUDIT.md) supersedes the resource limitations,
cycle counts, and toolchain status below.

## Scope and implementation

This milestone implements a simulated modular-square path, not a complete
primality-testing client or a board-ready FPGA image. All HDL compilation and
execution occurs on aethia. No Quartus trial was activated, no board shell was
added, and no hardware or PrimeGrid account was accessed.

New modules:

- `genefer_ntt_engine.sv`: runtime lengths 2 through 65,536, synchronous data
  and root memories, natural-order host interface, internal bit reversal,
  radix-2 DIT scheduling, forward/inverse transforms, inverse normalization,
  pointwise square, per-element multiplication, and scalar multiplication.
- `genefer_crt3.sv`: three-field Garner reconstruction followed by centering,
  with a signed 96-bit result.
- `genefer_carry.sv`: signed floor division, radix carry sweeps, negacyclic
  carry folding, and canonical `[-1,0,...]` output for the special -1 residue.

The host test runner sequences the stages and supplies roots. All transform,
pointwise, CRT and carry arithmetic under test runs in RTL simulation. Host
Python supplies independent expectations; it does not substitute arithmetic
results into the downstream DUT. CRT output is transferred into carry memory
by the C++ test driver, optionally doubled for `square_dup(bit=1)`.

There is not yet a single autonomous RTL top-level that coordinates all three
fields or executes repeated exponentiation steps.

## Verification design

Final run status: **PASS**. All 26 Python tests passed, all seven RTL mutants
were rejected at runtime, and all positive transform, CRT/carry and modular
square tests passed. The report and per-test logs are linked below.

- Existing stream test: injected arithmetic, valid-latency, reset-flush and
  butterfly alignment bugs in disposable RTL copies. Compilation must
  succeed and execution must fail with the expected diagnostic; compiler
  failures are not counted as caught mutations.
- New-stage mutations: deliberately wrong twiddle scheduling, CRT sign
  centering, and negative carry rounding in disposable RTL copies.
- NTT forward/inverse tests at N=2,8,32,65536 for each S3 field. Small cases
  include zero, impulse, maximal and random inputs; full-size cases are seeded
  random inputs. Small results are checked against a direct O(N^2) DFT.
- The scalable independent oracle uses ordinary modular arithmetic and a DIF
  schedule, unlike the DUT's Montgomery DIT implementation. Both directions
  are checked, not just an inverse round trip.
- Reset midway through transforms, CRT and carry; interrupted data is
  explicitly reloaded. Busy-time host writes, starts and configuration changes
  must be ignored. Invalid size/radix, pulse validity and exact operation
  counters are checked.
- 28 direct CRT/carry cases cover -1, negative coefficients, the centered CRT
  endpoints, random wide coefficients, and bases 2,3,1024,10^9.
- Six negacyclic-square inputs: zero, -1, wraparound basis, maximal digits,
  random small digits, and one seeded random full GFN16-size input at base
  604832956. Every case runs all three fields and both `square_dup` bits.
- Small reconstructed convolutions are also checked by signed schoolbook
  multiplication. Final canonical digits are checked against independent
  whole-integer modular squaring, including the full-size case.

The initial CRT edge-case generator accidentally used Python `-M//2`, which
rounds down for odd M and is one below the valid centered range. The test
correctly reported disagreement. The generator now uses `-(M//2)` and rejects
out-of-range expected coefficients explicitly. This was a vector correction,
not an RTL arithmetic change to accommodate a wrong expected result.

## Measured baseline cycle counts

For N=65,536, all three separately instantiated field configurations have
the same operation schedule:

| Operation, one field | Simulated cycles |
| --- | ---: |
| Forward NTT | 3,768,192 |
| Inverse NTT, including normalization | 4,161,408 |
| Each twist, pointwise square, untwist or conversion pass | 393,216 |
| Entire negacyclic square residue path, one field | 9,502,464 |
| Carry normalization in the full-size test, either bit | 262,146 (two sweeps) |

These are kernel operation counts, excluding host transfers, root loading,
test comparisons, and inter-stage orchestration. They are not wall-clock
throughput, timing closure or a PrimeGrid task-time prediction.

A forward transform performs 524,288 butterflies. It spends 2,621,440 cycles
in its butterfly WAIT state (including result consumption), about 70% of its
total cycles. The controller intentionally issues only one butterfly at a
time. Thus the immediate performance opportunity is to overlap independent
butterflies using safe memory banking and an address/valid pipeline, not to
buy more multiplier lanes without a memory schedule.

## Resource and synthesis limitations

Logical storage per full-size field instance is 0.25 MiB data plus 0.25 MiB
roots; the separate 96-bit carry memory is 0.75 MiB. Three field instances plus
one carry memory would therefore contain 2.25 MiB of raw array payload. This
is not a fitted M20K count and does not include a complete multi-register PRP
engine, proof/checkpoint storage, shell, banking or replication overhead.

CRT uses constant remainders; carry uses combinational variable division and
remainder. These are deliberately simple correctness baselines, not claims
of acceptable area or frequency. A sequential divider/reducer and a reviewed
memory organization are prerequisites to treating this as a competitive
Catapult implementation.

The user's selected board reference is pinned in `config/board-reference.json`.
It identifies the Catapult v3 family, not the physical variant/device. Vendor
synthesis remains unrun: Quartus is not installed/activated in this workspace,
and no board-specific target, pins, or constraints have been authorized by
physical-card verification. A provisional compute-only device fit can be a
separate next step after selecting the exact device and trial timing; it must
not be mistaken for a safe board image.

## Reproduction and evidence

On aethia:

```bash
cd /home/jtl/gfn-fpga-lab/fpga
export VERILATOR_ROOT=/home/jtl/gfn-fpga-lab/tools/verilator/usr/share/verilator
python3 -m reference.engine_regression \
  --verilator /home/jtl/gfn-fpga-lab/tools/verilator/usr/bin/verilator \
  --output artifacts/engine-rerun --phase all
```

The final run location is `artifacts/engine-final-20260929/` on aethia.
The [report](../results/engine-final-20260929/report.json), logs and a source
snapshot are copied locally under `results/engine-final-20260929/`.
Generated vectors, binaries and temporary mutant sources remain on aethia.
The report records commands, exit statuses, elapsed test times, cycle metrics,
and source SHA-256 hashes. The harness is not a security sandbox, formal proof,
or hardware admission mechanism.
