# Next arithmetic architecture: remove serial carry, retain three fields

This widened architecture remains a mathematical design proposal, not measured
FPGA timing. A scalar two-pass prefix implementation was subsequently verified
and integrated opt-in; see SQUARE-CORE-NOTES.md for actual cycle evidence. The
original complete-core budget was 2,424,980 clocks: NTT work 1,441,753,
carry 589,936, root loads 262,152, conversion 65,541, CRT transfer 65,598.
After widening the NTT, serial carry and repeated whole-array passes will dominate.
Reaching a weak-GPU target needs much more than four butterfly lanes.

## Best option: independent quotient splitting plus small-domain carry prefix

Let `N=65536`, `b` be the radix, and `a_i` the exact centered convolution
coefficient after optional doubling. For canonical digits the conservative bound
is `|a_i| <= 2N(b-1)^2`. Ordinary signed arithmetic, not modulo-field arithmetic,
is used in everything below.

Independently for every coefficient, compute Euclidean decomposition

`a_i = r0_i + b*r1_i + b^2*q_i`, with `0 <= r0_i,r1_i < b`.

This can use two fully pipelined reciprocal divide/remainder units with reciprocal
computed once per candidate. Negative inputs require floor division, not truncation.
The expensive wide multiplications have no neighbor-to-neighbor dependency, so
their latency can be pipelined and throughput scaled with lane count. The bound
above implies `|q_i| <= 2N`.

Redistribute these parts using `b^N = -1`:

- `s_0 = r0_0 - r1_(N-1) - q_(N-2)`.
- `s_1 = r0_1 + r1_0 - q_(N-1)`.
- `s_i = r0_i + r1_(i-1) + q_(i-2)` for `i >= 2`.

This preserves the represented residue exactly. Only two predecessor coefficients
are needed; first two positions wait for the final two input coefficients.

For `b > 2N+4`, including 604832956 and 1000000000, each normalized carry belongs
to the five-element set `C={-2,-1,0,1,2}`. Indeed, with `K=2N`, every `s_i` is
between `-b-K` and `2b-2+K`; adding any member of C and dividing by b maps back
into C. Thus each position has the exact tiny transfer function

`f_i(c) = floor((s_i+c)/b)`, for the five possible input carries.

It is five 3-bit outputs, computed with a few comparisons to small multiples of
b, not a wide divider. Transfer functions compose associatively. A W-lane prefix
tree produces W carry results in `ceil(log2 W)` composition levels; groups can
accumulate their 15-bit summaries through a small feedback multiplexer.

### Negacyclic wrap and the special residue

Let `F=f_(N-1) o ... o f_0`. Solve `c0=-F(c0)` by checking all five candidates.
For a solution, actual carries are obtained by prefix evaluation and output
digits are `d_i=s_i+c_i-b*c_(i+1)`, all in `[0,b-1]`. Their represented value is
congruent to the original because the end carry cancels the initial carry under
`b^N=-1`.

There is at most one solution: `H(c)=c+F(c)` is strictly increasing. If it skips
zero, adjacent inputs differ by one while the final carry also jumps by one.
The two corresponding canonical digit values must then be `b^N-1` and zero;
the original residue is `b^N`, i.e. canonical `[-1,0,...]`. Detect this case and
write the special encoding. This handles arbitrarily long zero/max-digit chains;
it does not assume folded carries die within a few positions.

### Schedule, storage and cost

Pass A streams W coefficients per clock through independent quotient splitters,
forms/stores signed33 `s_i`, and accumulates transfer summaries. Final wrap entries
are composed in their mathematically correct order after the stream drains.
Pass B streams W `s_i` per clock, computes real carry prefixes from solved `c0`,
and writes W canonical digits. This gives a design budget of approximately
`2*ceil(N/W) + pipeline fill + prefix/control overhead`, not an achieved bound
until a collision-free RAM schedule and pipelined composition are implemented.
Optional separate digit-to-Montgomery loading adds another `ceil(N/W)` pass.

| W | Two-pass body clocks | Three-pass body clocks |
|---|---:|---:|
| 4 | 32,768 | 49,152 |
| 8 | 16,384 | 24,576 |
| 16 | 8,192 | 12,288 |
| 64 | 2,048 | 3,072 |

Signed33 intermediate storage is about 264 KiB total, replacing a 768 KiB signed96
carry array if memories are redesigned around lifetimes. There must be W-way
banking; simply adding W arithmetic units behind the existing single-port RAM
cannot realize these rates. A single fully pipelined splitter pair is much
larger than one reused reciprocal unit: a straightforward pair of 96x96 products
has eighteen 32x32 partial products before width pruning. Sharing one candidate
reciprocal across lanes is essential. Proven coefficient bounds permit narrower
first-stage and especially second-stage arithmetic, but exact DSP/ALM cost must
be synthesized; blindly replicating 64 unpruned splitters is not credible.

Keep the current reciprocal carry as a fallback for `b <= 2N+4` and as an oracle.
Before RTL: exhaustively test the five-state cyclic proof on small radices/sizes,
both wrap positions, all-max/all-zero runs, special -1, and negative coefficients.

## Companion option: fuse conversion/twist and widen boundary streams

Current CRT already accepts one coefficient per clock. W copies plus a W-bank
carry/prefix input array reduce the boundary stream to `N/W` clocks; the existing
61-stage latency is small relative to full-array work. Do this only alongside
the widened carry memory and NTT read interface.

An initial ordinary digit d can be converted and twisted in one Montgomery
multiply using RHS `R^2*psi^i mod P`: `Mont(d,R^2*psi^i)=d*R*psi^i`. Thus the
current separate digit-conversion and twist passes can be fused. After inverse
NTT, multiplying by ordinary `psi^-i/N` yields ordinary coefficients, which can
stream straight into CRT without another write/read round trip. Root streams
must be widened or generated in interleaved lanes too; otherwise they serialize
the now-parallel arithmetic. These are algebraic identities, not validated RTL.

More importantly, these roots depend on N and the field, **not on the candidate
base or current residue**. They can remain resident across all squarings. Three
tables per field suffice: fused-conversion `R^2*psi^i`, forward `R*omega^i`, and
fused-postconversion ordinary `psi^-i/N`. The inverse transform reuses the forward
omega table with address `(-i mod N)`, since omega has order N. Initializing these
banks once removes per-square root-table load costs. Raw storage for three fields
is 0.75 MiB data + 2.25 MiB roots + about 0.258 MiB signed33 carry intermediates,
before memory-bank packing and metadata. This replaces the current overwrite-one-
root-array-per-phase scheme; actual FPGA RAM packing and read conflicts still
need to be measured.

For perspective, ten minutes for 1.91 million squarings at 100 MHz allows only
about 31,400 clocks/square. Sixty-four butterflies/clock **per field** gives
16,384 clocks for the forward+inverse transform bodies; a 16-lane two-pass carry
body costs another 8,192. The remaining ~6,800 clocks must cover pointwise square,
CRT, conversion/postprocessing and fill/control. Thus an asymmetric 64-lane NTT
and 16-lane carry architecture with resident roots and fused boundaries is a
more concrete resource-modeling target than assuming every unit needs 64 lanes.
This is a cycle-budget exercise, not a claim it fits or reaches 100 MHz.

## Why not simply remove an NTT field?

Two current primes multiply to only `4504162581568552961`. Exact signed recovery
requires product greater than twice the maximum convolution magnitude. Even
balanced radix-b digits reduce the conservative coefficient bound by only about
fourfold; at b around 604 million, two fields remain insufficient by thousands.
Dropping P3 without a different digit representation silently corrupts results.

Splitting each digit into smaller limbs introduces additional convolutions:
`(L+cH)^2=L^2+2cLH+c^2H^2`. Three smaller products (or Karatsuba's equivalent)
using two fields consume six field transforms versus the current three.
If b happens to be a perfect square, using sqrt(b) digits doubles transform
length; two fields then cost roughly `4*17/(3*16)=1.42` times current butterfly
work at N=65536, although CRT width drops. Neither is an obvious throughput win.
Retain three fields initially; concentrate on parallel carry, fused passes and
banked streaming. Any field-count reduction needs a new exact range proof and
a whole-pipeline work/memory comparison, not just a smaller CRT unit.
