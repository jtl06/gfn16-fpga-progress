# Exact division with magnitude matched reciprocal precision

This candidate uses a W-bit reciprocal for a dividend magnitude strictly below `2^W`, with W77 for the first carry division and W47 for the second. A single exact correction remains sufficient. The input reciprocal port and 97-clock carry setup remain unchanged: the helper extracts the required high bits from the existing 96-bit reciprocal.

New modules are `genefer_div_recip_precision` and `genefer_carry_prefix_stream_precision`. They are separate from the frozen 96-bit DSP-shaped candidate. No existing helper, carry module, or square-core selection is changed. Physical DSP savings and timing remain unmeasured.

## Why W bits suffice

For integer b>=2 and integer k>=0, `floor(floor(x)/2^k)=floor(x/2^k)`. Therefore

`floor(floor(2^96/b)/2^(96-W)) = floor(2^W/b)`.

The constant slice `reciprocal96[95:96-W]` is exactly the W-bit reciprocal, not a rounded approximation to it. Let the **division scale** be `S=2^W`, with `c=floor(S/b)`, `0<=m<S`, and `e=floor(m*c/S)`. This is independent of the NTT Montgomery radix, which remains `R=2^32`; no field or root representation changes. Then

`0 <= m/b - m*c/S <= m/S < 1`.

The estimate never exceeds `q=floor(m/b)` and is at most one below q. Accordingly `delta=m-b*e` is in `[0,2*b)`. For the existing base limit b<=1e9, `delta<2^31`, so the low32 subtraction recovers the entire nonnegative delta without ambiguity. Comparing delta with b and conditionally incrementing e/subtracting b gives the exact unsigned quotient and remainder.

Negative values use `-q-[r!=0]` and remainder zero if r is zero, otherwise `b-r`. This preserves Euclidean floor division. The original strict magnitude contract is essential: the signed minimum `-2^W` remains excluded and asserted against. No narrower dividend or radix contract is introduced; the helper still supports every other signed W+1-bit input and bases 2..1e9.

Rounding the reciprocal upward is not interchangeable with taking its floor: it can overestimate, and an increment-only correction cannot repair that case. The regression explicitly mutates the slice, reciprocal rounding and product scale.

## Native width products and exact sums

Both operands are partitioned into at-most-27-bit chunks. Unlike the earlier 27×24 design, only W reciprocal bits enter the multiplier.

| W | Left and right chunks | Main products | Full product width |
| --- | --- | --- | ---: |
| 77 | 27, 27, 23 | Four 27×27, four 27×23 or 23×27, one 23×23 | 154 bits |
| 47 | 27, 20 | One 27×27, two 27×20 or 20×27, one 20×20 | 94 bits |

The two main multipliers per carry lane use 9+4=13 source products rather than the 12+8=20 of the frozen 96-bit tiling. These are **not physical DSP counts**. Each divider retains its separate low32 estimate×base product, and carry bound setup arithmetic is unchanged.

For each left chunk of width L, the adjacent first two right chunks form an exact product with a `min(W,54)`-bit value, fitting `L+min(W,54)` bits. The optional third product is delayed alongside that pair, then added at bit54. The resulting row fits L+W bits. Rows0+1 fit `min(W,54)+W` bits (131 or 94), while an optional third row shifted by54 completes the exact 2W-bit product. Shared multiplicands justify these widths without an extra carry bit: each sum is itself a product with the recombined chunk value.

The helper extracts product bits `[2*W-1:W]`, not the old bit96 boundary. `reference/reciprocal_precision_proof.py` checks all intermediate bounds and compares the reconstructed complete product with Python multiplication.

## Pipeline and protocol preservation

The twelve-stage schedule is intentionally retained for comparison with the frozen 96-bit tiling:

1. Magnitude capture.
2. Partial products.
3. Low pair sum and delayed optional high product.
4. Full row sum.
5. Rows0+1 sum and delayed optional row2.
6. Final high-product estimate.
7. Low32 estimate×base product.
8. Provisional remainder.
9. Comparison and candidate remainder subtraction.
10. Unsigned quotient correction.
11. Sign negation and negative-fraction flag.
12. Floor adjustment and final payload.

An accepted input at edge k responds immediately after edge k+11; initiation interval remains one. The 47-bit elaboration retains register-only stages where no third row or column exists. Data outside `out_valid` remain unspecified/free-running; reset clears valid eligibility.

Base and reciprocal are stable for responses the caller consumes. An abort may abandon old tokens while a new base starts; unchanged carry setup quarantines those outputs before new stream admission. Full signed96 coefficient guards, exact masks/addresses, row ordering, special minus one, host arbitration and completion after the final digit RAM commit are unchanged.

The measured carry count is `2*ceil(N/LANES)+135+3*log2(LANES)+producer_bubbles`, matching the frozen twelve-stage 96-bit tiling. At N65,536, this candidate takes 32,909 clocks with four lanes and 8,339 with sixteen lanes. All full-size patterns and recurrent-square cases match these counts.

## Proof and validation

Before RTL testing, the independent proof passed 257,796 exhaustive signed cases for smaller generic widths, 2,596 boundaries at W77/W47, 200,000 random signed cases, and 40,000 arbitrary W×W product checks. It covers small and near-1e9 bases, magnitudes near `2^W`, exact-multiple neighbors and limb edges. Both correction-needed and correction-not-needed cases occur at each real width. The proof was rerun with the RTL source hashes recorded at `/home/jtl/gfn-fpga-lab/agent-work/carry-precision/fpga/artifacts/math-with-rtl-v1/report.json`.

The final RTL gate passed all 94 steps, including 36 non-equivalent fault mutants, at `/home/jtl/gfn-fpga-lab/agent-work/carry-precision/fpga/artifacts/precision-v1/report.json`. Simulation ran only on aethia with two build workers, 6 GiB memory, zero swap and a 200% CPU scope. No Quartus run was performed by this agent.

- Independent signed-divmod scoreboards checked 59,644 W77 and 63,164 W47 responses (122,808 total), with 5,022 reset-canceled tokens. Eight explicit malformed inputs were rejected: signed minimum and bases 0, 1 and 1,000,000,001 at each width. Tests include all pipeline reset ages, bubbles, uninterrupted II1 bursts, exact multiples and neighbors, limb boundaries, and configuration changes after drain.
- Four- and sixteen-lane carry elaborations at AW1 and AW16 completed 12,470 normalizations against independent whole-integer vectors. These include full N65,536, boundary radices, negative extrema, canonical minus one, recurrent squarings, repeated starts without reset and changing radix. The suites also checked 218 domain rejections, 170 reset aborts, 28 malformed stream protocols and 5,918,527 host transactions.
- An AW17 elaboration rejected sizes 0, 17, 18 and 31, then recovered with a legal N2 operation. Explicit reset/restart cases cover clocks 98..130 and the edge immediately before final output commit, followed by changed-base recovery.
- The 36 mutants exercise arithmetic floor/correction, scale/slice/rounding, row/partial-product shifts, pipeline tags/valid/reset, bound checking, stream signs and whole-row eligibility. The absent third limb in W47 is not treated as a meaningful fault target. Changes confined to discarded reciprocal bits would be equivalent under this contract and are not counted as escaped defects.

Independent read-only peer review found no width, signedness or payload-alignment defect. Physical DSP counts, ALM usage and clock rate remain unmeasured; fewer source products do not alone establish an area or throughput win.

## Frozen source identity and dependencies

The candidate is frozen with these SHA-256 identities, identical locally and in the passing remote report:

| Source | SHA-256 |
| --- | --- |
| `genefer_div_recip_precision.sv` | `832021ed0b3410dc867d92ac4436a725d5717f9630d233073e39896789ebbd7c` |
| `genefer_carry_prefix_stream_precision.sv` | `ba7ce9d0c1a99ad959bfe9909c62f341fabd537c76f196c5bcb6394c161296d3` |
| `carry_div_precision.cpp` | `731f85a82ca3b73fe703d4958ea9adc9272a6cc7e0ca6c371024d926afb28175` |
| `carry_prefix_stream_precision.cpp` | `3b7bb3e0a79dc5d89921845d0c6dac0eddbc0ebee2d21543bfbfe27d2d18763b` |
| `carry_stream_precision_size.cpp` | `2bb0f2b84be7fd638560efdc9b6cc2595678341d01bffaa5b3c18c5d06b8c274` |
| `carry_precision_regression.py` | `75a543dd56ebcacba9602385de8a4752c8062a729a22e308b0d4d0964c75b229` |
| `reciprocal_precision_proof.py` | `9db880cd858609fcfee384f051ff856f2dd3792bce0d57e78a67a1622b763990` |

The carry top depends on this new divider, the frozen `genefer_sp_ram.sv` (`b97d2f43db1b1e1aa60b9b7fc2b720af1e302bd5ff9e35854c89b30e5fb610df`), and the frozen `genefer_carry_prefix_stream_pipe.sv` (`9838c6852cac57f7901f8b57dcbb4ee11b7fa129ef86e40158d67cc789b06e5e`) solely for its `genefer_carry_stream_scan_pipe` definition. The old top is not instantiated. Public ports and the runtime-checked carry domain are unchanged. No integrated core source selection was modified.
