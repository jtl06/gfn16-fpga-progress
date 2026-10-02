# Streaming NTT candidate — 2026-09-29

`rtl/kernel/genefer_ntt_stream_engine.sv` is a separate candidate; the fitted
baseline `genefer_ntt_engine.sv` remains unchanged. It preserves the baseline's
ports, natural-order host loading/reading, four operation codes, inverse
normalization, busy/reset behavior and fused-square table convention.

## Memory and schedule

Map logical address `a` to bank `^a` (XOR of all address bits), row `a >> 1`.
Together the bank and row uniquely encode the address. Each radix-2 DIT pair
differs in one bit, so it occupies opposite banks at every transform stage.
Each bank is described as explicit true dual-port RAM: port A reads an operand
while port B writes an earlier pipeline result. Butterfly issue interval is
**one cycle**, using the existing five-stage butterfly unchanged.

There is one synchronous-read cycle before arithmetic acceptance. A read's
butterfly result is written six cycles later, using delayed address tags;
pointwise products are written five cycles later. Stage changes wait until all
prior writes complete. Every address is accessed only once per stage, excluding
mixed-port read/write collisions even while reads and writes overlap. Runtime
simulation assertions reject collisions and invalid bank pairings.

Bit reversal preserves address parity, so each swap stays in one bank and
uses its two ports. It retains the baseline's sequential read/write schedule.
Pointwise square, table multiply and scalar multiply issue one operand/cycle.
Root RAM is shared between host writes and one synchronous read/cycle.

RAMs and RAM output registers are not reset. Reset cancels pipeline validity,
work counters and completion; callers must reload operands and required roots.
Host writes/read/start while busy are ignored. Host writes take priority over
host reads, and read data is meaningful only with `read_valid`.

## Exact cycle accounting

Let `N = 2^L`, `B = N*L/2`, `S = (N - 2^ceil(L/2))/2` swaps.

- Forward transform: `N + S + B + 6*L` cycles.
- Inverse with normalization: forward schedule plus `N + 5` cycles.
- Any standalone pointwise operation: `N + 5` cycles.
- Data reads/writes: `2*S + 2*B` for a transform, plus `N` if normalizing.
- Root reads: `B` for transform; `N` for a standalone table multiplication.
- `wait_cycles` counts drain-state cycles, **not** idle arithmetic stages:
  `6*L` per transform, plus five per pointwise pass.

The counters exclude the initial start-accept edge and all host loading/reading
and root-table transfers. The C++ test checks exact totals independently of
the RTL counters for every executed operation.

For N=65,536, measured in simulation for all three fields:

| Operation | Cycles |
| --- | ---: |
| Forward / unnormalized inverse | 622,560 |
| Inverse with normalization | 688,101 |
| Pointwise pass | 65,541 |
| Fused square: two transforms + three pointwise passes | 1,441,743 |

The old fused square needs 8,716,032 cycles: this candidate uses **6.045× fewer
cycles** at the same hypothetical clock. This is not a measured frequency or
hardware-throughput claim. Vendor synthesis, memory inference and timing must
be measured separately before using the result in a clock-qualified estimate.

## Verification

Execute only on aethia:

```sh
. /home/jtl/gfn-fpga-lab/fpga/tools/aethia-env.sh
python3 -m reference.ntt_stream_regression --output artifacts/stream-full-v2
```

Isolated test workspace:
`/home/jtl/gfn-fpga-lab/agent-work/ntt-throughput/fpga`.
The report, build logs, command vectors and exact counters are retained under
`artifacts/stream-full-v2` there. Builds use at most two compiler workers.

Coverage includes all three S3 primes, every transform size from N=2 through
65,536, forward and inverse against independent integer-DIF arithmetic (also
naive DFT for small sizes), sparse/zero/maximal/random operands, all four
operation codes, invalid sizes, host interference, done/read-valid pulses,
eleven targeted reset injection points per field plus aborts in transform tests,
and collision assertions. Six three-field negacyclic square cases include a
full GFN16-sized random operand; centered CRT coefficients are checked against
schoolbook convolution for small sizes and whole-integer modular square for
all sizes. Full-size fused and unfused schedules agree field-for-field.

The regression also injects twiddle-step, write-address-tag and bank-order
defects, plus a forced RAM collision, requiring each mutated build to fail.
This suite tests convolution, not the separate carry RTL or a complete PRP
controller. Prior carry testing remains separately applicable.

Candidate RTL SHA256:
`22974d6114edfcef68a84afa6dde30b678b7ccbe6ef07a46f20737bed995fbee`.

## Remaining optimization possibilities

- Pair forward DIF with inverse DIT in an internal bit-reversed representation
  to remove the two bit-reversal passes. This would require a distinct
  operation/ordering contract and another butterfly variant; it is not part of
  this candidate, which retains natural-order results.
- Fuse twist/input conversion and output untwist/CRT streaming around the
  transform engine. That requires integration rather than changing the tested
  host command semantics.
- Multiple butterflies per cycle require more RAM banking and a new scheduling
  proof. First measure this II=1 candidate's fitted timing and integrated
  postprocessing bottlenecks.
