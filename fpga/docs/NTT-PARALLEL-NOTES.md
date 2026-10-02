# Four-lane DIF/DIT prototype

`genefer_ntt_parallel_engine.sv` is a new candidate; existing engines and the
integrated core were not modified by this subtask. Parameters `LANES=1,2,4,8`
are supported. Four lanes are the comprehensively tested initial target.
There is **no vendor fit or frequency claim yet**.

## Interface and implementation

Ports match `genefer_ntt_difdit_engine`, including its captured `dif` input.
Scalar host load/read/root loading stays unchanged. DIF consumes natural order
and produces a bit-reversed spectrum; DIT consumes bit-reversed order and
produces natural order. Elementwise operations preserve physical ordering.

Each field uses `2*LANES` independently addressed data banks and the same
number of root banks. The XOR-chunk bank mapping and per-stage address groups
are proved in `NTT-NEXT-ARCHITECTURE.md`. No full data/root array is replicated.
Each bank gets at most one synchronous read and one delayed write per cycle;
duplicate twiddles are broadcast. Full pipelines drain between stages.

Each arithmetic lane reuses `genefer_ntt_difdit_butterfly32` from the earlier
candidate plus an existing pointwise multiplier. Four lanes issue four
butterflies or four elementwise products per cycle. For N smaller than the
lane group, only `min(LANES,N/2)` butterfly or `min(LANES,N)` vector lanes
are valid. Scalar host writes/read/start/order changes while busy are ignored.
Reset cancels pending work; operands and root tables must be reloaded.

Simulation assertions independently reject duplicate data-read/write banks,
distinct-root addresses sharing a bank, and same-row read/write collisions.
Root counters now count **physical root-bank reads after broadcasts**, rather
than one logical read per butterfly. The integration leaves these diagnostic
counters open, so this does not affect its functional interface.

## Exact cycles and counters

For N=2^L, B=LANES, `G=ceil(N/(2B))`, `V=ceil(N/B)`:

- Either transform: `L*(G+7)` cycles.
- Optional inverse normalization adds `V+5`.
- Elementwise operation: `V+5` cycles.
- Butterfly count: `N*L/2`; transform reads/writes: `N*L` coefficients each.
- Transform physical root reads: `G * sum(min(B,2^s), s=0..L-1)`.
- Elementwise table multiply reads N roots.
- Drain/wait counter: `7*L`, plus five per pointwise/normalization pass.

Measured LANES4, N65536, all three fields:

| Operation | Cycles |
| --- | ---: |
| Unnormalized DIF / DIT | 131,184 |
| Normalized DIF / DIT | 147,573 |
| Pointwise pass | 16,389 |
| Fused field square | **311,535** |

This is about **4.00x fewer arithmetic cycles** than the single-lane no-reversal
candidate's 1,245,423, and **4.63x fewer** than the original II1 natural-order
candidate's 1,441,743. Whole-system speedup will be smaller: conversion, root
loading, CRT, carry and controller cycles are outside these engine counters.

## Evidence

Remote workspace:
`/home/jtl/gfn-fpga-lab/agent-work/ntt-parallel/fpga`.
`artifacts/parallel-full-v1/report.json` reports **passed**.

Coverage:

- LANES4: all three fields, every runtime N2..N65536, explicit AW1/AW4
  elaborations, both decomposition orders with both root directions.
- Independent integer-DIF oracle, naive DFT cross-checks for small cases,
  parameter-corner exact schoolbook convolution, and six three-field square
  cases including N65536 checked against whole-integer modular squaring.
- Full-size fused/unfused equality; all operation codes; exact cycle, traffic
  and broadcast counters; 32 targeted reset points/field; host interference;
  valid/completion contracts; active collision assertions.
- LANES1/2/8: P1 transforms at N2/4/8/16/32/65536, both orders/directions,
  vector operations and reset cases. This is not equivalent to the complete
  three-field convolution coverage given to LANES4.
- Four separately built mutants rejected: twiddle address, delayed write tag,
  small-N lane mask and bank mapping.

RTL SHA256:
`f02c37af212208974430dceb93f9002772bb55f3d0b3514bfd4f92f80e5fd8d1`.

```sh
. /home/jtl/gfn-fpga-lab/fpga/tools/aethia-env.sh
python3 -m reference.ntt_parallel_regression --output artifacts/parallel-new-run
```

Source dependencies: `genefer_montgomery_mul32_pipe.sv`,
`genefer_ntt_difdit_engine.sv` (shared butterfly), and the new parallel engine.
All builds/simulations ran on aethia with at most two build workers; no Quartus.

## Next: immutable root phase cache, not wider regeneration

Roots depend on the field and transform N, **not** candidate radix b. Retain all
four immutable phase tables across modular squares:

| Phase | Entries per field |
| --- | ---: |
| Twist | N |
| Forward | N/2 |
| Inverse | N/2 |
| Fused postconversion | N |

Total 3N words/field versus the current one active N-word table. This adds
2N words/field, roughly **768 M20Ks across three fields** using present packing.
Adding that to the approximately 1,153-block integrated baseline gives about
1,921/2,713 blocks (~71%), **before** any new carry buffers or packing changes.
This is an estimate requiring a fit, not an allocation guarantee.

For N65536 and K banks, phase-row offsets can be
`0, N/K, 3N/(2K), 2N/K`, with lengths `N/K, N/(2K), N/(2K), N/K`.
Keep each phase's existing bank function, and add the latched phase-row base.
Small N requires explicit rounding/masking. No duplicate root arrays per
lane are needed. A phase-select input and startup cache-fill/commit protocol
are needed; merely generating roots elsewhere still leaves N-word reloads.

Report **cold** startup separately from **warm** steady-state squares. Global
reset invalidates cache-valid flags without clearing RAM. For runtime sizes,
tag validity with N; field parameters are compile-time. Partial reloads cannot
leave a phase valid. Warm execution omits the four root fills, saving roughly
262,144 scalar payload cycles per square, while cold startup can fill only
the 3N actually used entries. Base changes do not invalidate these tables.

The bank construction generalizes algebraically to more power-of-two lanes,
but this RTL deliberately limits support to 1/2/4/8 until wider configurations
are implemented, tested and physically evaluated. Larger designs need careful
lane-routing pipelining, placement and wider system interfaces.

For scale: at a purely illustrative 100 MHz and 1.91M square iterations, a
5–10 minute PRP budget is only about 15.7k–31.4k cycles/square. Scalar conversion
plus scalar CRT alone costs approximately 2N=131,072 cycles (~42 minutes),
even with zero-cost NTT/carry. Eventual 32/64-lane NTT work must therefore also
widen conversion, residue readout, CRT and carry memory paths; caching roots
and adding butterflies alone cannot achieve that goal. No clock is promised.
