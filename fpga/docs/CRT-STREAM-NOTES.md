# Throughput-oriented CRT candidate

`genefer_crt3_pipe.sv` is a separate candidate, not a replacement of the verified
serial CRT. It accepts canonical, ordinary (not Montgomery) S3 residues every
clock. It uses `genefer_mod64_pipe.sv`; no other RTL dependencies are required.

## Interface and scheduling

Ports exactly match the serial CRT: `clk`, active-low asynchronous `rst_n`,
`in_valid`, unsigned 32-bit `r1/r2/r3`, `ready`, `out_valid`, and signed 96-bit
`coefficient`. `ready` is always one. There is no downstream backpressure.

- Initiation interval: **one clock**.
- Pipeline: **61 registered stages**. A transaction sampled on rising edge `t`
  produces `out_valid` and its coefficient immediately after edge `t+60`.
- Tag alignment: a 61-register tag/valid shift pipeline, sampled alongside the
  residues, has the same output edge. Do not delay tags by 61 *additional* edges.
- A reset cancels every in-flight coefficient, clears `out_valid` and coefficient.
- Coefficient holds its previous value on invalid output cycles. Internal data
  registers need not reset because reset clears every validity pipeline.
- Inputs outside `0 <= r_i < P_i` are not supported.

## Arithmetic architecture

The existing exact Garner reconstruction is retained. Each 64-bit remainder is
computed by a 16-stage restoring pipeline, with four compare/subtract bit steps
per stage. It accepts one input per cycle, instead of reusing a single reducer
for all three operations and all coefficients. Context is explicitly pipelined
with each remainder, so bubbles cannot misalign residues or partial results.

Constant products split their variable operand into two 16-bit halves, register
the partial products, then register their sum. Reconstruction additions and
centering are separate stages. There are no division or remainder operators.
The centered interval is `[-floor(M/2), floor(M/2)]`, where
`M = 9068077028115350401664942081` is odd. Equality to `floor(M/2)` stays positive.

For 65,536 coefficients with continuous input, the last output appears 65,596
clocks after counting the first accepted edge as clock one (65,536 + 60). The
serial 59-cycle-per-input service takes about 3.87 million clocks. This is a
**CRT-only ~59x throughput improvement**, not an end-to-end PRP claim. No
resource usage or achievable frequency is claimed until the parent fit completes.

## Independent verification on aethia

The generator uses the direct CRT basis sum with Python arbitrary-precision
integers, not the RTL Garner ladder. It includes zero, one, negative one,
center-boundary values, powers of two and neighbors, cartesian products of
residue endpoints, the P1/P2 reduction boundary, 12,000 consecutive valid inputs,
random bubbles, arbitrary changing invalid data, and repeated/short reset bursts.
The scoreboard checks exact latency, II=1, output hold behavior, reset cancellation,
every valid result, and transaction accounting.

Results (2026-09-29, aethia only):

| Seed | Simulator | Stream clocks | Accepted | Checked | Reset-canceled |
|---|---|---:|---:|---:|---:|
| 20260929 | Verilator 5.032 | 52,611 | 41,340 | 39,529 | 1,811 |
| 20260929 | Icarus 12.0 | 52,611 | same stream | 39,529 | same stream |
| 137 | Verilator 5.032 | 52,611 | 41,381 | 39,590 | 1,791 |

All passed. Each stream has 124 reset edges. Four separately built RTL mutants
were rejected: wrong inverse constant (cycle 63), incorrect midpoint centering
(cycle 64), one-stage-early valid (cycle 60), and failure to clear input-stage
valids on reset (cycle 58). Icarus emits its known constant-select/`always_comb`
sensitivity limitation notices; they were nonfatal, and the shared vectors passed.

Remote evidence:

- `/home/jtl/gfn-fpga-lab/agent-work/crt-throughput/fpga/artifacts/stream-01/`
- `/home/jtl/gfn-fpga-lab/agent-work/crt-throughput/fpga/artifacts/stream-02/`

Each contains vectors, per-step logs, source SHA-256 values and `report.json`.
The second includes four mutant sources, builds, and expected rejection logs.
To reproduce in a fresh output directory on aethia:

```sh
. /home/jtl/gfn-fpga-lab/fpga/tools/aethia-env.sh
python3 -m reference.crt_stream_regression --output artifacts/crt-new-run --icarus --mutations
```

Only the candidate, its helper, its C++ stream scoreboard, the standalone Python
regression, and this note were added; existing RTL and regression scripts remain
unchanged. No Quartus fit, FPGA programming, or hardware access was performed by
this subtask.
