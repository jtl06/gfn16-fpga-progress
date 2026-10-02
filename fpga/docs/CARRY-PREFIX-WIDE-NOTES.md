# Banked prefix carry with registered output

Separate candidate `genefer_carry_prefix_wide.sv` is validated at **LANES=4,8,16**.
The frozen scalar `genefer_carry_prefix.sv`, shared reciprocal divider, and
existing core integration are unchanged. No Quartus fit was run by this work.
Frequency/resource estimates await a physical fit; clocks below are simulated.

## Measured outcome

All tested valid operations take **2*ceil(N/LANES)+116 clocks**:

| N | Four lanes | Eight lanes | Sixteen lanes | Scalar prefix |
|---:|---:|---:|---:|---:|
| 2 | 118 | 118 | 118 | 120 |
| 4 | 118 | 118 | 118 | 124 |
| 8 | 120 | 118 | 118 | 132 |
| 16 | 124 | 120 | 118 | 148 |
| 65536 | 32,884 | 16,500 | 8,308 | 131,188 |

Both existing full GFN-16 square/double-square coefficient sets return the
exact oracle digits in 32,884/16,500/8,308 clocks at 4/8/16 lanes. These are
carry-stage cycle reductions only, **not** complete-PRP speedups.
The hardware busy counter excludes scalar host loads/result reads; each still
requires N host transfers. No vector interface or integrated boundary-stream
speedup is claimed.

## Architecture and contracts

Public ports match scalar prefix. Runtime domain checks and failure/reset
semantics are unchanged: power-of-two N>=2 within AW, `base>2N+4`, base<=10^9,
and every coefficient bounded by `2N(base-1)^2` in magnitude. Unsupported
inputs fail explicitly. The full-domain carry kernels remain separate.

- Both coefficient/digit RAM96 and intermediate RAM33 are genuinely split
  into LANES independent banks. Logical address low log2(LANES) bits select bank and
  remaining bits select row. Each pass reads or writes at most one word per
  bank per clock; the design does not rely on mixed-port same-address behavior.
- LANES splitter pairs reuse the unchanged seven-stage, II=1 exact reciprocal
  helper. A single 96-cycle reciprocal setup is shared by all lanes.
- Lane0/1 redistribution uses the previous group's final one/two quotients;
  later lanes use predecessors from the current group. The first two global
  entries are excluded from the accumulated transfer summary until the final
  input group provides their wrap terms.
- Both wrap entries are written simultaneously into banks0/1, row0. For a
  single input group (N<=LANES), the wrap expression uses current splitter
  outputs instead of stale first-group registers.
- Each group computes an inclusive five-state transfer scan through a
  **log2(LANES)-level parallel composition tree**. A group summary updates the
  inter-group 15-bit function accumulator. Pass B applies those prefixes to
  the three-bit incoming carry, producing all digit carries in parallel.
  There is no combinational chain of LANES serial scalar normalizers.
- N<LANES is masked. Inactive lanes contribute identity transfer functions and
  never read/write active RAM. AW=1/N=2 is separately elaborated and tested.
- Each output digit, its bank-row address, and valid are registered before the
  coefficient RAM write. The carry feedback advances when the digit is computed,
  so the next group still starts every clock. Completion waits for the final
  actual RAM write; reset invalidates a pending write. This output-only stage
  adds one clock per operation, not one clock per group.
- The scalar-prefix proof of exact decomposition, five-state closure, unique
  negacyclic fixed point, and canonical `[-1,0,...]` special residue applies
  unchanged because function composition is associative. Only grouping changes.

The cycle accounting is 97 setup, `ceil(N/LANES)+15` splitter cycles, two wrap/solve
cycles, and `ceil(N/LANES)+2` emit cycles. Raw RAM bits remain 129N for N>=LANES; banking
can change physical M20K packing, which must be checked rather than assumed.

## Evidence

Four-lane final report:
`/home/jtl/gfn-fpga-lab/agent-work/carry-prefix-wide/fpga/artifacts/wide-v3-pipeline/report.json`
has status `passed`. All simulation ran on aethia, builds limited to two threads.
The separate eight-/sixteen-lane report also has status `passed`:
`/home/jtl/gfn-fpga-lab/agent-work/carry-prefix-wide/fpga/artifacts/wide-v3-w8-w16/report.json`.

- Each lane configuration's full suite: 1,175 cases, 3,309 successful normalizations, 66 explicit domain
  rejections, and six reset-aborts across setup/splitting/emission.
- Each lane configuration's AW=1 elaboration: another 2,697 successful normalizations and 11 rejections.
- Runtime N2/N4/N8 exercise partial groups across the three lane counts;
  N16/N256/N65536 exercise full groups. The abort cases use N256 so setup,
  pipeline, and emission reset phases remain present even at sixteen lanes.
- Every successful full reload is followed by two canonical-output reruns,
  without reload/reset. Next cases change radix/size without resetting. Final
  host reads directly precede subsequent starts/reloads.
- Big-int modular and independent scalar prefix oracles agree for exhaustive
  small signed pairs, full-range coefficient extrema, alternating signs,
  zero/max-digit chains, -1 at both ends, random coefficients, N16 recurrent
  squares, and N65536 sample square/double-square vectors.
- Shared-divider stream: 21,300 exact quotient/remainder/payload checks with
  bubbles and 440 reset-canceled transactions.
- Ten injected defects rejected at four lanes: wrap sign, inter-group composition order,
  disabled -1 special handling, within-group carry-prefix index, output RAM
  bank-row address, registered-output tag alignment, tree composition order, floor division, reciprocal boundary
  correction, and divider payload alignment.

The initial build stopped on Verilator's flattened-array dependency warning.
The scan tree was rewritten with separately generated per-level arrays, making
its acyclic dependencies explicit. No warning suppression was used. The final
arithmetic run and mutations passed with that revised tree.

Frozen dependencies/hashes:

- `genefer_carry_prefix_wide.sv`: `ed3861413e2122c8243189c0688c4e806901d416fd6e6d6440c667de4c1b3fd6`
- `genefer_carry_transfer_tree.sv`: `b18e39ebcaf2a1b514e0b617170dc1491a576772fe94ff3cf55316feee09971c`
- Reused `genefer_div96_recip_prefix.sv`: `7fb975d75e27e5d66c97b02a2784cba8ed7dde3de624555859b8e8893a71a3b9`

## Next decisions, not implemented

LANES4/8/16 are simulation-validated; **no wide candidate was fitted by this agent**.
Each lane currently adds two full-width reciprocal divider pipelines; resource
scaling must be measured before instantiating more lanes. The proven input
bound offers width-pruning opportunities, particularly for the second divider.
Do not extrapolate blindly to 64 splitter lanes.

The parent measured an 11.18 ns scalar-prefix path from intermediate RAM output
through digit adjustment into coefficient RAM input (89.74 MHz overall). That
motivated the wide-only output stage above; the scalar candidate remains frozen.
No post-change wide frequency or resource claim follows from simulation.
The old four-lane unregistered result is preserved separately in
`artifacts/wide-v2/report.json` (32,883 clocks for N65536).

Timing risks still include independent per-lane transfer generation, the logarithmic
composition tree and the final digit adjustment into the new register. If needed, the independent
group table/payload path can be pipelined before the final three-bit carry
feedback; inter-group feedback itself must continue to accept one group per
clock. No additional tree/feedback retiming is included yet.

Before widening the integrated CRT/conversion boundary, agree a vector RAM
interface with explicit row address, lane-valid mask, valid/read-valid timing,
and scalar/vector arbitration. A possible future vector load/read interface
would transfer all banks at one row, but it is deliberately absent here so
existing scalar behavior remains directly comparable.
