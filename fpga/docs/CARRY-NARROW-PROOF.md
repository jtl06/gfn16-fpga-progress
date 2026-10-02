# Width specialized prefix carry division

The new `genefer_carry_prefix_wide_narrow` and
`genefer_carry_prefix_vector_narrow` candidates replace the two generic signed96
dividers per lane with 77-bit and 47-bit magnitude dividers. Their RAMs, ports,
seven-stage divider latency, II=1 throughput, and carry scheduling are unchanged.
Frozen generic and module-memory candidates remain available and unmodified.
This is a structural area optimization; it does not reduce carry clocks, and no
DSP count or achievable frequency is inferred from simulation.

## Domain and exact width bounds

Let K=2N. Accepted operations satisfy power-of-two `2<=N<=65536`,
`K+4<b<=10^9`, and each original signed96 coefficient satisfies
`|a|<=B=K(b-1)^2`. The new candidates explicitly reject `size_log2>16` even
if elaborated with larger AW. Existing base and full-width coefficient checks
remain in place.

Since `K<=2^17` and `b-1<2^30`,

```
B = K(b-1)^2 < 2^17 * 2^60 = 2^77.
```

The first divider therefore needs 77 magnitude bits plus a sign bit. Its
Euclidean quotient is `q=floor(a/b)`. Negative rounding is the limiting case:

```
|q| <= ceil(B/b)
     = K(b-2) + ceil(K/b)
     = K(b-2) + 1
     < Kb
     <= 2^17 * 10^9
     < 2^47.
```

The equality `ceil(K/b)=1` follows from `0<K<b`. Thus the second divider needs
47 magnitude bits plus a sign bit, including the most negative accepted first
quotient. Its quotient magnitude is at most K, as required by the original
five-state carry proof. No assumption that division truncates toward zero is
used. The positive quotient bound is the slightly tighter `K(b-2)`.

## Exact reciprocal correction

Both helpers still use `R=floor(2^96/b)`. For nonnegative magnitude x below
`2^MAG_W`, where MAG_W is 77 or 47, let `q0=floor(xR/2^96)`. Writing
`R=2^96/b-delta` with `0<=delta<1` gives

```
q0 <= floor(x/b) <= q0+1,
0 <= x-q0*b < 2b < 2^31.
```

Consequently one correction suffices. The provisional remainder is recovered
exactly with the low32-bit subtraction `x_low32-(q0*b)_low32`: the actual
remainder is already below `2^32`, so the modular subtraction loses nothing.
After unsigned correction, negative inputs produce quotient
`-q_unsigned-(r_unsigned!=0)` and remainder
`r_unsigned==0 ? 0 : b-r_unsigned`. These are Euclidean floor division and a
canonical remainder in `[0,b)`.

## Physical operand widths and pipeline

The helper does not merely zero-mask a 96-bit operand. Its magnitude registers,
quotient estimates, products, and product rows have parameter-dependent widths.
Each 32-bit reciprocal limb multiplies an explicitly sized magnitude limb.

| Divider | Magnitude limbs | Registered partial products | Full product width |
|---|---|---|---:|
| First | 32,32,13 bits | Six 32x32 and three 13x32 | 173 bits |
| Second | 32,15 bits | Three 32x32 and three 15x32 | 143 bits |

The frozen pair had eighteen 32x32 partial products. The new pair has nine such
products plus six narrower ones. Both retain their low32-bit estimate-times-base
remainder product. Device DSP packing and synthesis pruning must be measured;
product counts are not equivalent to DSP counts.

A limb of LW bits produces three `(LW+32)`-bit partial products. Their shifted
sum occupies exactly `(LW+96)` bits and equals that limb times R. Summing the
shifted limb rows in `(MAG_W+96)` bits recovers the full product without overflow.
The stages remain magnitude, partial products, rows, high-product estimate,
residue product, unsigned correction, and signed correction. A request sampled
at edge t produces valid output at edge t+6, with a new request accepted each
clock. Payload and sign alignment retain the same schedule.

## Rejection and discarded transactions

The first narrow divider accepts a coefficient only when the original signed96
comparison proves it lies in `[-B,B]`. Rejected high coefficients are not sliced
and then treated as valid narrow inputs. The existing controller asserts
arithmetic error/done and returns idle on a failing full-width comparison.

The second divider accepts first-stage outputs only while the controller remains
in SPLIT. This prevents transactions discarded after an error from entering it
when a subsequent start changes shared base/reciprocal parameters. No rejected
operation consumes such residual pipeline outputs. Every new accepted operation
has 97 setup clocks, exceeding the combined divider drain time, before SPLIT.
Simulation assertions also check the first quotient's signed48 representation
and reject the excluded minimum signed input of each narrow helper.

## Validation evidence

The final isolated aethia report has status `passed`:
`/home/jtl/gfn-fpga-lab/agent-work/carry-narrow/fpga/artifacts/narrow-v2-final/report.json`.
Builds use at most two threads; no Quartus runs are performed by this agent.

Across both divider widths, 101,270 whole-integer quotient/remainder/payload
checks, with 1,900 reset-canceled transactions. Wide4/8/16 and vector4/16 each
passed 3,309 AW16-suite and 2,697 AW1 normalizations, 90+19 domain rejections,
and six reset aborts. The vector suites checked 9,357,357 host transactions.
All retained the measured `2*ceil(N/LANES)+116` carry clocks. An AW17 elaboration
also rejected size_log2 values 0,17,18,31 and successfully normalized N2 afterward.

Python whole-integer `divmod` vectors cover signed width extrema, powers of two,
exact multiples and their neighbors, boundary and random bases, bubbles, and resets.
An additional 3,520 first-quotient samples derive from accepted carry bounds at
all supported N sizes. Full carry tests reuse the preserved independent big-int
oracle data, append rejected coefficients at ±2^77 and ±(2^94−1), and retain
recurrent operations, no-reset size/base changes, full N65536 vectors, AW1
masking, explicit domain failures, reset aborts, and scalar/vector host tests.

Mutation tests remove negative floor correction, break the reciprocal boundary
comparison, shift payload alignment, and erase the high magnitude limb at each
width. Another removes the full-width acceptance gate before the first divider;
the rejected ±2^77 case triggered the narrow-input assertion. A tenth mutant
removed the maximum-N guard and was rejected by the AW17 size test.
All ten mutants failed for their intended arithmetic, payload, or domain check.
The earlier narrow-v1 run passed arithmetic but stopped when a mutation fixture
caused a compiler width warning; v2 corrected only that fixture and extended
the size tests. The tested RTL hashes did not change between those runs.

Current RTL hashes for test/fit matching:

- `genefer_div_recip_narrow.sv`: `eef327cee81d41895a068b746a3715daba95d43bea919edbddf9b498ecfc38bf`
- `genefer_carry_prefix_wide_narrow.sv`: `892d4eee5df4b92350cb6f9663c86679b812e37983e8f66faead76d0c78d216e`
- `genefer_carry_prefix_vector_narrow.sv`: `97a1f9becb32d00bcf0dd2a42e64edf6e8c14a594eecb54c512cb79303457c63`

Dependencies remain `genefer_sp_ram.sv` and `genefer_carry_transfer_tree.sv`.
