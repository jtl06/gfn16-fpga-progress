# Pipelined ordered streaming carry experiment

This is a separate candidate, `genefer_carry_prefix_stream_pipe.sv`. The frozen
streaming carry and existing core are unchanged. The isolated four-lane physical
result below is not a sixteen-lane or whole-core frequency result.

## Isolated physical result

The parent-run AW16/four-lane virtual-I/O fit reached 159.69 MHz, versus the
frozen stream's 108.19 MHz. It did not meet the requested 200 MHz constraint:
setup slack is -1.262 ns, hold +0.018 ns. Resources are 12,014 raw placed ALMs
(11,618 packing-adjusted needed), 9,861 registers, 171 raw DSP blocks
(108 packing-adjusted needed), and 260 M20Ks. The fitted RTL hash is
`9838c6852cac57f7901f8b57dcbb4ee11b7fa129ef86e40158d67cc789b06e5e`.

Evidence is archived under `results/throughput-20260929/carry-stream-pipe-fit/`.
This is a virtual-pin component probe: no physical board validation, deployable
image, constrained board-I/O timing, or whole-core clock claim follows from it.

## Measured motivation

The archived carry-pipe-v2 four-lane fit has a 9.312 ns path from
`previous_r1[4]` to `suffix[14]`, spanning row arithmetic, transfer construction,
the prefix tree, and suffix feedback. The streaming four-lane fit has a
9.416 ns / 16-level path from intermediate RAM to `b_transfer[3][5]`, including
2.134 ns RAM clock-to-output. Its nearly tied quotient-to-suffix path is
9.423 ns. These are actual 100 MHz-fit paths, not projected 200 MHz results.

The subsequently completed whole FAST16 core fit reinforces this diagnosis:
`lane[10].second_div.remainder[0]` to `suffix[9]` takes 12.375 ns over 15 logic
levels, with 6.481 ns routing and 5.629 ns cell delay. Its -2.154 ns slack at
100 MHz corresponds to the reported 82.28 MHz Fmax. Registering local map and
tree boundaries is therefore relevant to the integrated path too, but routing
congestion and other paths can still limit the next whole-core result.

## Pipeline boundaries

Row summaries now pass through registered signed33 row sums, registered
half-comparisons, registered transfer encoding, and one register per inclusive
prefix-tree level. Only the final 15-bit composition remains in the one-cycle
suffix feedback loop. Predecessor quotient/remainder registers still advance
on the original divider output, never on the delayed summary output.

The five-state transfer map compares `s+k-2` with `-b, 0, b, 2b`. Equivalent
thresholds are precomputed during setup. Each signed34 comparison is split into
signed high17 and unsigned low17 comparisons, followed by
`high_lt || (high_eq && low_lt)`. This is exact for negative and positive values;
it is not a truncated comparison or an assumed small-value optimization.

The delayed final-row tag causes wrap processing only after its suffix update.
The first two wrap values use the same pipeline; their map is composed before
the suffix in original coefficient order. Fixed-point selection occurs after
that registered composition.

Emission captures intermediate RAM data before transfer construction and carries
the row and all signed33 values through the pipelined scan. One carry-selection
stage advances the inter-row carry once per valid prefix, then digit arithmetic
and the final RAM write complete. `done` follows the actual last write.

## Interface, domain, and exact cycle contract

Ports and host arbitration are unchanged. The stream accepts ordered, aligned,
exactly masked rows of full signed96 coefficients. Every active coefficient must
satisfy `abs(c) <= 2*N*(b-1)^2`; the whole row is rejected atomically before any
divider input if its address, mask, or full96 domain check fails. The supported
base remains `2*N+4 < b <= 1,000,000,000`. Final host data are sign-extended
signed32 digits, with the existing special minus-one representation.

Initial setup is still 97 clocks. Once ready, every remaining legal row can be
accepted each cycle: no new downstream backpressure, and producer bubbles add
exactly one clock each. With `G=ceil(N/LANES)` and `K=log2(LANES)`:

`cycles = 2*G + 125 + 3*K + producer_bubbles`

Compared with the frozen stream's `2*G+117`, overhead is `8+3*K`: 14 clocks for
four lanes, 20 for sixteen lanes. At N=65536 this is 32,899 and 8,329 clocks,
respectively. The scan helper is II1, with accepted edge `t` producing output
after edge `t+K+1`; its valid and payload pipes reset together.

Reset aborts every eligibility/valid pipeline. Invalid-stream aborts retain the
existing immediate completion semantics; the next operation's reciprocal setup
quarantines stale divider/scan data before accepting any new coefficient row.

## Verification and artifacts

`reference/carry_stream_pipe_regression.py` uses fresh output directories and
executes only on aethia, with two compiler workers and a 6 GiB address-space cap.
Dedicated benches retain the independent frozen integer-oracle vectors and
host/protocol fault tests, with explicit new cycle expectations. A separate
scan-helper oracle uses ordinary signed64 comparisons and sequential function
composition, independently checking signed thresholds, prefixes, payloads,
bubbles, reset cancellation, and exact latency at four and sixteen lanes.

Final gate location:
`/home/jtl/gfn-fpga-lab/agent-work/carry-stream-pipe/fpga/artifacts/stream-pipe-v3/`.
The final gate passed all 52 build/test steps and caught all 19 injected faults.
Both lane widths passed AW16 (1,213 cases, 3,332 completions, 90 domain rejects,
15 aborts, seven malformed-stream faults) and AW1 (918 cases, 2,699 completions,
19 domain rejects, two aborts, seven malformed-stream faults). The scan oracle
checked 42,192 four-lane and 41,859 sixteen-lane responses, plus 498 and 831
reset-canceled responses. AW17 elaboration independently rejects runtime sizes
0, 17, 18, and 31, then recovers with a legal N2 operation.

The report pins RTL, benches, harness, and input-vector SHA256 values. Earlier
v1/v2 directories are retained: v1 caught a missing summary-valid connection;
v2 passed four arithmetic configurations but caught an old 119-clock expectation
in the separate size-rejection recovery bench. That expectation is now 133 for
four lanes. Neither failure was a passing report or an overwritten artifact.
