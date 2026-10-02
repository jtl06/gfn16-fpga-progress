# Exact reciprocal carry candidate

`rtl/kernel/genefer_carry_fast.sv` is a separate, interface-compatible candidate;
the existing `genefer_carry.sv` is unchanged. No FPGA programming or Quartus fit
was performed by this work. Cycle counts below are simulation measurements,
not proof that the new datapath reaches 100 MHz.

## Architecture

Compute `R = floor(2^96 / base)` once at start with a 96-cycle restoring
reciprocal generator. For each noncanonical signed total, take its magnitude
`x`, calculate `q0 = floor(x*R / 2^96)`, and correct that estimate at most once.
The 96-by-96 product uses nine registered 32-by-32 partial products, followed
by registered row sums and a registered final sum. A separate registered
32-by-32 low product recovers the provisional remainder. Signed floor
correction matches the original carry module.

After the first complete sweep, only the folded low digit and its propagated
carry can be noncanonical. Subsequent sweeps therefore stop immediately when
the carry becomes zero: untouched higher digits are already canonical.
The existing `[-1,0,...]` representation, `b^N=-1` folding, 64-sweep failure
bound, synchronous RAM reads, and reset/busy/host interface are preserved.

## Exactness and bounds

Let `M=2^96`, `R=floor(M/b)`, and `delta=M/b-R`, so `0<=delta<1`.
For `0<=x<M`, `xR/M=x/b-x*delta/M`, with the subtracted term in `[0,1)`.
Consequently `q0` is never too large and is at most one below `floor(x/b)`.
The provisional remainder `r0=x-q0*b` is in `[0,2*b)`. Since the entire
interface permits only `b<=10^9`, `r0<2e9<2^31`; recovering it modulo `2^32`
by subtracting the low 32 product bits is therefore exact. If `r0>=b`, one
increment of `q0` and subtraction of `b` yields the exact quotient/remainder.
For negative input with nonzero remainder, quotient decrements and digit
adds the radix, implementing Python-style floor division rather than
truncation toward zero.

No silent narrowing of the coefficient contract occurs. Put `C=2^94-1`.
During the first sweep, input coefficient and incoming carry both lie in
`[-C,C]`: a total in `[-2C,2C]` divided by `b>=2` produces carry in `[-C,C]`.
Thus all first-sweep totals have magnitude below `2^95`. After folding,
the low coefficient is a canonical digit minus the outgoing carry; its
magnitude is at most `C+b-1`, also below `2^95`. All remaining digits are
canonical, and subsequent carry propagation stays inside this bound.
All sums fit signed 96 bits, magnitudes fit unsigned 96 bits, and the
reciprocal estimate proof applies. The row products fit 128 bits and the
full product fits 192 bits exactly.

## Simulation results on aethia

Independent whole-integer oracle: recursively encode the coefficient
polynomial as a Python integer, reduce modulo `b^N+1`, then recursively
decode base-`b` digits. This is not the RTL's sweep algorithm.

491 cases passed on both the original and candidate RTL:

- Signed coefficient extrema `+/-(2^94-1)`, alternating extrema, zero,
  canonical digits, and random full-contract inputs at N=2,4,32,256.
- Eleven fixed radices from 2 through 10^9, including powers of two, plus
  100 random radices.
- Six N=65536 random/all-negative maximum-magnitude cases, including base 2.
- Existing full GFN-16 square/double-square coefficient vectors, with their
  expected digits also checked against the independent integer oracle.
- 48 recurrent N=32 modular squares across four radices.
- Invalid radix, write/read priority, busy start/write/read attempts,
  reset during setup and processing, done/read-valid pulses and cycle counter.
- Explicit N=2,16,65536 with base 2,604832956,10^9 and positive/negative
  full-range coefficients plus canonical `-1`. A second invocation of each
  simulator runs all 491 cases without any reset between completed commands:
  every full reload is followed by two extra normalizations of its canonical
  output without reloading. This verifies 1,473 uninterrupted completed starts
  per implementation, including changing radix and size. Across reset and
  uninterrupted modes, each implementation completes 1,964 tested operations.

Both injected RTL defects were rejected with an arithmetic mismatch: removing
the negative floor decrement, and changing the reciprocal correction boundary
from `>=base` to `>base`.

| N=65536 case | Original cycles | Candidate cycles |
|---|---:|---:|
| Existing GFN-16 square, bit 0 | 2,031,643 | 589,934 |
| Existing GFN-16 square, bit 1 | 2,031,643 | 589,934 |
| Full-range random, b=604832956 | 2,031,668 | 589,943 |
| All `-(2^94-1)`, b=604832956 | 2,031,668 | 589,943 |
| Full-range random, b=2 | 2,033,943 | 590,762 |
| All `-(2^94-1)`, b=2 | 2,033,968 | 590,771 |

The measured existing square is **3.44x fewer carry cycles (70.96% reduction)**.
At an assumed 100 MHz this would be 5.89934 ms rather than 20.31643 ms,
but the new multiplier/sum timing has not been fitted. Small/canonical
operations can regress because of the fixed 96-cycle reciprocal setup.

Cycle accounting: first-sweep canonical digit costs 3 cycles; a noncanonical
digit costs 9 rather than the original 28. Add 96 setup cycles, 2 cycles per
fold, and only the visited second-sweep prefix (same 3/9-cycle digit costs).
The special `-1` rewrite retains one cycle per written digit.

Remote evidence:
`/home/jtl/gfn-fpga-lab/agent-work/carry-throughput/fpga/artifacts/reciprocal-v5-chain/`.
Build/run/chain logs, generated vectors and a source-hashed `report.json` are
preserved there; previous v1-v4 evidence remains untouched. The candidate RTL
was unchanged when adding the uninterrupted-operation checks. Reproduction:

```bash
cd /home/jtl/gfn-fpga-lab/agent-work/carry-throughput/fpga
. /home/jtl/gfn-fpga-lab/fpga/tools/aethia-env.sh
python3 -m reference.carry_fast_regression \
  --output artifacts/reciprocal-recheck \
  --square-vectors /home/jtl/gfn-fpga-lab/fpga/artifacts/opt-engine-20260929-v6 \
  --mutations
```

## Next physical checks

Fit this candidate with the same AW=16 constraints as the baseline. The
registered 128/192-bit row/final addition trees and 96-bit correction path
may require further pipelining; the reciprocal divider itself has only one
33-bit comparison/subtraction per cycle. Inspect actual DSP mapping and
M20K inference rather than extrapolating from RTL multiplications.
If timing is poor, adding one or two arithmetic stages still leaves a large
cycle advantage. A later block-parallel scheme can reduce the inter-digit
carry dependency further, but is not implemented or included in estimates.
