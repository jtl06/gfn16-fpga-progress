# Isolated 36 bit arithmetic experiment

Two 36-bit fields cannot cover the project's full GFN16 coefficient range at
base604832956 or base1e9. This experiment therefore tests a standalone
Montgomery multiplier and quantifies a narrower-base option; it does not
replace the frozen 27-bit or 31-bit profiles, NTTs, CRTs or square cores.

## Exact centered CRT range

For N65536 and digits bounded by base minus one, the conservative doubled
negacyclic coefficient bound is C=2*N*(base-1)^2. Unique centered recovery
requires CRT modulus M>2*C=4*N*(base-1)^2. Any two36-bit primes have product
strictly below2^72. The necessary universal base ceiling under this bound is
134217728; it is an upper bound, not a claim that suitable primes attain it.

The required strict modulus lower bounds are 95898279203053771161600 for
base604832956 and 262143999475712000262144 for base1e9. Both exceed2^72.
Three selected36-bit fields are sufficient, but retain three residue planes;
there is no automatic field-count saving versus the validated27-bit basis.

The selected sparse fields are:

| Field | P | Positive inverse Q modulo2^36 | Generator | P minus one |
| --- | ---: | ---: | ---: | --- |
| 1 | 34896609281 | 33822867457 | 3 | 2^35+2^29 |
| 2 | 34426847233 | 34292629505 | 5 | 2^35+2^26 |
| 3 | 52613349377 | 16106127361 | 3 | 2^35+2^34+2^30 |

Exact trial division proves primality. Factoring P-1 proves each generator's
full multiplicative order; the reference also checks primitive roots for
every negacyclic size N2 through N65536. Selection prioritizes fewest nonzero
terms, then larger modulus. It does not claim a globally optimal36-bit basis.

| Selected pair | Maximum base with doubling | Maximum base for square only |
| --- | ---: | ---: |
| 1 and2 | 67697134 | 95738205 |
| 1 and3 | 83689242 | 118354460 |
| 2 and3 | 83124040 | 117555145 |

These ceilings use exact integer square roots and strict inequalities. For
example, the simplest pair's product is1201380236666676969473. The proof checks
that its stated maximum base fits and the next base fails. Using two fields
would thus be a deliberately restricted profile, not a supported universal
replacement or a solution for the current sample base.

## Montgomery identity and width proof

This separate helper uses R=2^36, unlike the existing27-bit helper's R=2^32.
All input/output and P/Q ports are36 bits, with canonical operands0<=a,b<P.
Every nonconstant term in P has exponent at least18, so (P-1)^2 is divisible
by R. Consequently Q=P^-1 modulo R equals2-P modulo R. For t=a*b:

```
m = (t_low36 - sum(t_low36 << s)) mod 2^36
mP = m + sum(m << s)
k = floor(t/2^36) - floor(mP/2^36)
result = k if k >= 0 else k + P
```

The selected shifts s are shown in the field table. Only a*b is a variable
product, explicitly36x36 with a72-bit result. The sparse reduction uses
shifts and adds/subtracts. Since t<P^2<P*R and mP<P*R, both products fit72
bits. Equal low36-bit words make k=(t-mP)/R exact, and -P<k<P proves that
one conditional addition yields the canonical result. The correction uses a
37-bit intermediate because P can exceed R/2; its selected result fits36 bits.

## Pipeline contract

`genefer_montgomery_mul36_sparse_pipe.sv` has six registered stages and II1:
an input accepted at edge k produces result/out_valid immediately after edge
k+5. The stages are variable product, two reduction partials, final reduction
word, two72-bit sparse-product partials, upper product word, and correction.
This deliberately does not claim compatibility with a four-stage helper.

Reset cancels pending requests and clears the output. Invalid output cycles
hold the previous result. Simulation assertions reject unsupported P/Q and
active noncanonical operands; invalid or reset input cycles may contain any
36-bit values. These assertions are synthesis-off contract checks, not a
hardware error protocol or residue converter.

The RTL SHA256 is
`b90c014d41e15db47a865890ceade8590daeac1b4c9929f318462826c25e6596`.
There are no RTL dependencies. Instantiate constants with explicit36-bit
widths: bare decimal simulator parameter overrides can truncate to32 bits.

## Validation and decision boundary

`reference/ntt36_experiment.py` proves the fields, roots, ranges and30009 sparse
identities. `reference/montgomery36_regression.py` uses Python whole-integer
`a*b*pow(2^36,-1,P) mod P` as the independent arithmetic oracle. Its vectors
cover zero/one, P-neighbors, bit35 and lower boundaries, random values, both
correction branches, bubbles, six pipeline-occupancy resets and output holds.
Mutants target product width, each sparse reduction component, full-width m,
negative/equality correction, latency, reset, hold and domain assertions.

The final all-field gate passed103479 exact outputs,2130 reset-canceled
requests and19740 invalid-cycle hold checks. Twelve noncanonical-input probes,
two invalid-parameter probes and31 mutation checks were rejected as intended.
Both correction branches were exercised in every field. All simulation runs
on aethia with two build workers, a6GiB
per-process limit and180-second command timeout. Output directories must be
fresh; early failed parameter-width/testbench-binding attempts are preserved.

Final evidence lives under
`/home/jtl/gfn-fpga-lab/agent-work/montgomery36/fpga/artifacts/`:
`math36-v2/report.json` and `mont36-full-v2/report.json`, both passed. The
regression report pins the RTL, testbench, math script and generated vectors.
Frozen script hashes are
`95fd75510647f3451f88b861322f640c3236a91bd65b6eeaaca2e23c70783c3d`
for the math experiment and
`74ebe12257c87aad19e4e996a9623c77ee9d1544f27fa00ea8469e4b0b94112d`
for the RTL regression. The testbench hash is
`a8b02308d3a5276cc2a680176f7925ad728d031037636c786786c139912f8c5d`.

## Completed component physical measurements

All three sparse36 modular multipliers passed the 5 ns internal timing target
in Quartus Pro 26.1 on the provisional Arria10 device. Restricted Fmax was
257.86, 251.76 and 254.84 MHz for fields 1, 2 and 3. Each used **3 raw DSP
blocks**, with **2 packing-adjusted DSP blocks needed**; these are different
resource accounting measures, not evidence of two raw blocks. Raw ALMs were
225, 227 and 237. Full reports are archived under
`results/throughput-20260929/multiplier36-fit/`.

The separate raw-multiply probes used 1 raw DSP for27x27, 3 for inferred36x36,
and 4 for the explicit four18x18 partial-product version. The latter two both
reported 2 packing-adjusted DSPs needed. These three raw probes passed200MHz;
their full reports are under `results/throughput-20260929/raw36-fit/`.

This is **not a complete36-bit NTT or square core**. The current base/digit
range still needs three fields, so the measured36-bit multiplier does not
provide a field-count or DSP-area advantage over the one-raw-DSP27-bit
modular multiplier. Memory packing, CRT work, a different digit representation
and integrated clock could change the tradeoff, but those require distinct
experiments. Component Fmax alone does not justify replacing the current core.
