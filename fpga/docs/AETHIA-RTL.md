# Aethia pre-hardware RTL work — 2026-09-29

## Scope

GFN16 arithmetic simulation on aethia, with GFN17-compatible field arithmetic.
No Mac simulations, Quartus invocation/trial activation, board shell changes,
hardware access, or PrimeGrid work allocation/submission.

## Environment inspected

- SSH alias `aethia-ts`, host reports `aethia`, Linux x86-64.
- 16 logical CPUs, approximately 26 GiB physical RAM.
- Isolated workspace: `/home/jtl/gfn-fpga-lab`.
- Ubuntu Verilator 5.032-1 package downloaded and extracted under
  `/home/jtl/gfn-fpga-lab/tools/verilator`; no system-wide package installation.
- Python, make and g++ available. Compilation and simulation verified with
  the extracted Verilator package, without Quartus or a trial license.

## Implemented and simulation-validated

- `genefer_montgomery_mul32_pipe`: four register stages, initiation interval
  one, positive-inverse Montgomery convention, canonical S3 residues only.
- `genefer_ntt_butterfly32`: five register stages, radix-2 DIT operation,
  canonical Montgomery inputs/outputs. No twiddle scheduling or memory engine.
- Simulation wrapper instantiates baseline, pipeline and butterfly for all
  three primes. Python big-integer vectors and C++ scoreboards check values,
  latency, valid bubbles, output stability, asynchronous reset and cancellation.
- Make targets `rtl-baseline` and `rtl-check` and a complete regression runner.

## Results

The user explicitly approved source/test transfer to aethia after the initial
approval-gate rejection. The approved transfer and all runs completed.

- 25 Python tests: pass.
- Existing SystemVerilog baseline: all 531 committed Montgomery vectors pass.
- Streaming seeds `0x47464e16`, `1`, `0xdeadbeef`: 13,317 input transactions
  each (39,951 over the three seeds), all pass. Edge cases repeat across seeds.
- Per seed: 14,220 cycles, 867 bubbles, 14 reset assertions. Field counts:

| Field | Baseline outputs | Pipeline outputs | Butterfly outputs | Pipeline canceled | Butterfly canceled |
| --- | ---: | ---: | ---: | ---: | ---: |
| P1 | 4439 | 4427 | 4423 | 12 | 16 |
| P2 | 4439 | 4427 | 4423 | 12 | 16 |
| P3 | 4439 | 4424 | 4419 | 15 | 20 |

Canceled transactions are deliberately discarded by reset, not mismatches.
Both output values and validity are checked on every simulated cycle.
The test wrapper exercises one field's inputs at a time while all fields are
instantiated; it does not test a shared simultaneous three-field interface.

- Four negative tests: corrupt multiply expectation, corrupt butterfly
  expectation, missing final vector, truncated final row. Each was rejected
  with the intended diagnostic and nonzero status.
- Software oracle: full 65,536-point NTT round trips pass for P1/P2/P3, plus
  a full-length negacyclic-wrap check for P1. These are NOT full RTL NTT tests.

Logs and source SHA-256 manifest are in
`/home/jtl/gfn-fpga-lab/fpga/artifacts/regression-20260929/` on aethia.
A local copy of the report and logs is in
[`../results/aethia-20260929/`](../results/aethia-20260929/).

## Reproduce on aethia

```bash
cd /home/jtl/gfn-fpga-lab/fpga
export VERILATOR_ROOT=/home/jtl/gfn-fpga-lab/tools/verilator/usr/share/verilator
python3 -m reference.rtl_regression \
  --verilator /home/jtl/gfn-fpga-lab/tools/verilator/usr/bin/verilator \
  --output artifacts/regression-rerun
```

The runner builds with two compile workers for the streaming model, stores
logs and source hashes, and requires the expected result for every positive
and negative test. It is a development harness, not a security sandbox or
hardware admission broker. The baseline reset release was moved off the
active clock edge to remove a testbench race; the Makefile preserves `verify`
as its default target.

## Next milestone

The subsequent [engine milestone](ENGINE-RESULTS.md) adds the memory-backed
NTT, full-size modular-square path, CRT/carry and RTL mutation tests. The
results above remain the historical arithmetic-block milestone.

No timing closure, DSP/RAM fit, power estimate, complete GFN primality test
or PrimeGrid compatibility has been demonstrated.
