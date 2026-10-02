# Scalar streaming bounded-transfer carry candidate

New standalone RTL: `genefer_carry_prefix.sv`, depending only on
`genefer_div96_recip_prefix.sv`. Existing `genefer_carry_fast.sv` and core
integration remain unchanged. This candidate has been simulated on aethia;
**no frequency, DSP use, or RAM-block count is claimed until Quartus fitting**.

## Interface and explicit domain

The public ports, signed-96-bit coefficient/digit RAM interface, synchronous
host reads, write-over-read priority, busy request suppression, and reset-abort
semantics match `genefer_carry_fast`. `size_log2` selects N=2^size_log2 within
the configured AW memory capacity. Reload the entire active array after reset
or an error. This candidate is not a universal replacement:

- N>=2 and `size_log2<=AW`;
- `2*N+4 < base <= 1,000,000,000`;
- every coefficient satisfies `|a_i| <= 2*N*(base-1)^2`.

Invalid radix/size is rejected at start. A coefficient beyond either signed
bound is rejected during the first RAM pass. Failure raises `done/error` and
clears `busy`; it is not silently normalized with unsupported mathematics.
The existing full-domain carry remains the fallback for smaller bases.
For valid operations `passes=2` now describes the split and emit passes,
not iterative carry sweeps; cycles use the existing accepted-start convention.

## Arithmetic construction

Precompute `R=floor(2^96/base)` once. Two seven-stage, II=1 signed Euclidean
divider pipelines decompose each coefficient independently into
`a_i = r0_i + b*r1_i + b^2*q_i`, where `0<=r0_i,r1_i<b` and `|q_i|<=2N`.
No runtime division or remainder operator is used. The helper forms an exact
96x96 product from registered 32-bit partial products. For magnitude x<2^96,
`floor(xR/2^96)` is at most one below `floor(x/b)` and never above it. Its
provisional remainder is below 2b<2^31, so low-32-bit product/subtraction recovery
and one comparison/correction are exact. Negative nonmultiples require the
extra floor decrement. All valid carry-domain magnitudes are far below 2^95.

Redistribution using `b^N=-1` forms signed-33-bit values:

```
s0 = r0_0 - r1_(N-1) - q_(N-2)
s1 = r0_1 + r1_0 - q_(N-1)
si = r0_i + r1_(i-1) + q_(i-2), i>=2
```

The N=2 case specifically takes r0_1 from the current last splitter output;
there is no intervening stored first-two entry to assume has updated already.
Later positions stream into small RAM while their five-value carry-transfer
summaries compose. Only the first two entries wait for the tail coefficients.

Each transfer is `f_i(c)=floor((s_i+c)/b)` for c in {-2,-1,0,1,2}. The domain
condition keeps all transfer arguments in [-2b,3b), so five comparisons produce
an exact encoded result. Transfers encode c as c+2 and occupy 15 bits. The suffix
is composed in stream order, then joined after f0 and f1. Solving `c0=-F(c0)`
requires testing the five table entries, not an iterative sweep.

## Why a missing fixed point is exactly canonical -1

Each transfer is monotone with an adjacent-input difference of at most one;
composition preserves both properties. Hence `H(c)=c+F(c)` is strictly
increasing, and can have at most one zero. Also H(-2)<=0 and H(2)>=0. If it skips
zero, there are adjacent c,c+1 with H(c)=-1 and H(c+1)=1, so F jumps by one.

Let S be the redistributed polynomial's integer value. The canonical digits
produced starting at c represent `D(c)=S+c-b^N*F(c)`. Thus
`D(c+1)-D(c)=1-b^N`. Both D values are in [0,b^N-1], forcing D(c)=b^N-1 and
D(c+1)=0. Modulo b^N+1, D(c)=S+H(c)=S-1, so S=b^N: the unique special residue
represented by `[-1,0,...]`. The candidate emits this encoding when no table
entry satisfies the fixed-point condition. This proof covers indefinitely
long zero/max-digit carry chains; it is not a short-propagation assumption.

## Schedule and measured cycles

Pass A streams one coefficient per cycle through the independent splitters,
stores redistributed coefficients, and composes the suffix table. Two wrap
writes and one solve step follow. Pass B reads one redistributed coefficient
and writes one canonical digit per clock, updating only a three-bit carry.

Every valid tested operation, including -1 and boundary chains, took
**2N+116 clocks**. The setup/fill/control accounting is 97 setup clocks,
N+15 split clocks, three wrap/solve clocks, and N+1 emit clocks.

| N | Measured clocks |
|---:|---:|
| 2 | 120 |
| 16 | 148 |
| 65536 | 131,188 |

For the existing full GFN-16 square vectors this is **4.50x fewer carry clocks**
than `carry_fast`'s 589,934, a 77.76% reduction. At an assumed 100 MHz the new
block would take 1.31188 ms, but that clock has not been fitted for this block.
This is a carry-only improvement, not a fourfold complete-PRP acceleration.

Storage is still one signed96 coefficient/digit RAM plus a separate signed33
redistributed RAM: raw N65536 storage is 1,056,768 bytes, excluding arithmetic
registers and physical RAM packing. This initial candidate deliberately does
not claim the proposal's possible RAM-lifetime reuse saving.

## Verification

The aethia harness checks both a whole-Python-integer modular oracle and the
independent five-state prefix model. Its full-size/small-size suite has 1,132
cases: 3,213 successful normalizations, 55 rejected out-of-domain operations,
and six reset-aborts. Each successful full reload is followed by two further
normalizations without reload or reset; completed cases also proceed directly
to the next radix/size without reset. The last host read directly precedes
the next start. Tests include:

- Exhaustive N2 coefficient pairs in [-8,8] for bases 9,10,13.
- N=2,4,16,256,65536; base just above its domain threshold, another adjacent
  base, 604832956, and 10^9.
- Exact positive/negative coefficient bounds, alternating extrema, zero,
  all-max digits, -1 at either end, and random coefficients.
- Existing full-size square and square-and-double vectors.
- 36 recurrent N16 square/double operations over three radices.
- Invalid bases and both signs of coefficient bound+1, including tail entries.
- Abort/reload during setup, coefficient splitting/drain, and digit output.

The standalone divider stream additionally verifies 21,300 exact quotient,
remainder and payload results, with bubbles and 440 transactions canceled by
reset, across fixed/random radices and signed-94-bit test values.
The explicit AW=1 elaboration is checked separately from runtime N2 at AW16.
That AW=1 run passes another 2,697 successful normalizations and 11 domain
rejections. All six injected defects are rejected: reversed wrap sign,
reversed transfer-composition order, disabled special-minus-one handling,
missing negative-floor correction, incorrect reciprocal correction boundary,
and one-stage payload misalignment. Final report status is `passed`.

Final evidence location:
`/home/jtl/gfn-fpga-lab/agent-work/carry-prefix/fpga/artifacts/prefix-v3-final/`.
The report records source hashes and command logs. Earlier v1/v2 runs retained
passing arithmetic results but stopped because injected composition/special
defects triggered the expected error status rather than the initially expected
digit-mismatch diagnostic; only harness expectations changed, not RTL.

RTL frozen hashes:

- `genefer_carry_prefix.sv`: `7d45ed60e56ad3d489e30a239b8af5c49274a3ccba42c7a37543820596270b31`
- `genefer_div96_recip_prefix.sv`: `7fb975d75e27e5d66c97b02a2784cba8ed7dde3de624555859b8e8893a71a3b9`

## Future width/lane work, not implemented

Both independent divider pipelines are currently full-width. The supported
GFN16 coefficient bound permits narrower splitter inputs, especially the second
quotient; prove and fit these reductions before multiplying lane count. W lanes
need W-bank RAM, W coefficient splitters, and a logarithmic-depth transfer
composition tree for each group. Merely duplicating arithmetic behind this
scalar RAM cannot achieve 2N/W clocks. The current candidate is strictly W=1.
