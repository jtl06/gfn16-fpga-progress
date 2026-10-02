# Pipelined prefix normalization

`genefer_carry_prefix_wide_pipe` and `genefer_carry_prefix_vector_pipe` split
the carry emission path into separate leaf-map, prefix-selection, and digit
arithmetic stages. They preserve the frozen narrow-divider arithmetic and
module-scoped RAMs. All supported lane configurations passed simulation with
exactly two additional clocks per operation, not two clocks per group.
Achieved frequency and resources still require a physical fit.

## Stage alignment and carry feedback

For group j, whose first RAM-read edge is t, the sequence is:

| Edge | Registered result | Associated row |
|---|---|---|
| t | Intermediate RAM values | j |
| t+1 | Signed33 values and five-state leaf transfer maps | leaf_row=j |
| t+2 | Selected incoming/outgoing carries and delayed values | digit_row=j |
| t+3 | Canonical output digits | emit_row=j |
| t+4 | Coefficient RAM commit | j |

At edge t+2, the group prefix tree operates on the registered maps for group j
and its incoming carry Cj. It simultaneously registers the selected per-lane
carries and updates the group carry to `C(j+1)=Fj(Cj)`. At that same edge, the
leaf registers accept group j+1. Consequently the next clock sees both group
j+1's maps and its correct incoming carry. This preserves a group every clock
without a multi-cycle feedback dependency or inter-group bubbles.

The signed values and row tags travel alongside the maps and selected carries.
Digit arithmetic uses only the matching registered value and selected carry
pair. The special canonical -1 result selects its first digit using digit_row,
not the read-issue counter, which is already ahead in the pipeline.

Completion waits for the last actual coefficient RAM write. The final group
carry has already been registered before this edge, so the negacyclic carry
check still uses the final value. Reset clears all valid/tag state and gates RAM
access without resetting the memory arrays or data registers. A reset during
the final drain therefore cancels the pending write; reloading the active
array remains required after an aborted operation.

## Measured clocks

All tested valid operations use `2*ceil(N/LANES)+118` busy clocks:

| N | Four lanes | Eight lanes | Sixteen lanes |
|---:|---:|---:|---:|
| 2 | 120 | 120 | 120 |
| 4 | 120 | 120 | 120 |
| 8 | 122 | 120 | 120 |
| 16 | 126 | 122 | 120 |
| 65536 | 32,886 | 16,502 | 8,310 |

The two added clocks are fixed fill/drain latency. Scalar and vector host
interfaces, read latency, busy behavior, and the bounded arithmetic contract
are unchanged from the corresponding narrow candidates. The vector interface
still requires the upstream core to deliver groups before boundary throughput
improves; this component does not change core source selection.

## Timing scope

The previous emission path combined RAM output, leaf comparisons, cross-lane
prefix composition, carry selection, and digit arithmetic in one clock. The
new boundaries isolate RAM-to-leaf, leaf-to-selected-carry, and digit arithmetic
paths. No multi-cycle or false-path timing exception is introduced.

The splitter redistribution and pass-A summary-tree feedback path is unchanged.
It may become the next timing limit. No achieved-clock, DSP, ALM, or complete-PRP
speedup claim follows from these simulation results. Raw DSP counts and
packing-adjusted block estimates must also be kept separate in later reports.

## Validation evidence

The final report has status `passed`:
`/home/jtl/gfn-fpga-lab/agent-work/carry-pipe/fpga/artifacts/pipe-v1/report.json`.
All simulation ran on aethia; builds used at most two threads. No Quartus run
was performed by this agent.

Wide4/8/16 and vector4/16 each passed 3,321 normalizations in the AW16 suite,
2,697 in the AW1 suite, 90+19 explicit domain rejections, and ten reset aborts.
The vector configurations checked 9,361,789 host transactions in total. Tests
retain full N65536 big-int oracle vectors, extrema and random coefficients,
negative carry chains, canonical -1, recurrent operations, changing size/base
without reset, partial bank masking, and malformed/busy host requests.

New resets target leaf capture, selected carries, output generation, first
output commit, and the last-write drain. Subsequent full reloads and repeated
normalizations verify there is no surviving stale pipeline state. Every valid
operation also asserts the exact cycle formula; timeouts are bounded near that
formula rather than allowing an accidental non-draining pipeline to run long.

Six injected defects were rejected: incorrect leaf row, misaligned signed
value, misaligned selected carry, incorrect output row, premature completion,
and carry feedback triggered by the wrong valid stage. The inherited narrow
arithmetic and domain mutants remain documented in CARRY-NARROW-PROOF.md.

Frozen RTL and dependencies:

- `genefer_carry_prefix_wide_pipe.sv`: `409f452266aaaa624a2e561f14c385aaf0433bdbcb545c07bae5faf4936d726a`
- `genefer_carry_prefix_vector_pipe.sv`: `8516225afe465308277c9750fb87ab82bbd5b225284f40172c484c445582104d`
- `genefer_div_recip_narrow.sv`: `eef327cee81d41895a068b746a3715daba95d43bea919edbddf9b498ecfc38bf`
- `genefer_sp_ram.sv`: `b97d2f43db1b1e1aa60b9b7fc2b720af1e302bd5ff9e35854c89b30e5fb610df`
- `genefer_carry_transfer_tree.sv`: `b18e39ebcaf2a1b514e0b617170dc1491a576772fe94ff3cf55316feee09971c`
