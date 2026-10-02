# Next NTT architecture: 4 then 8 butterflies/cycle

Design analysis only, 2026-09-29. No new RTL, fit, or frequency claim.
Recommendation: **forward DIF + inverse DIT, then four butterfly lanes with
eight independently addressed banks**. Treat eight lanes as a later experiment;
the current carry pipeline will limit its end-to-end benefit.

## Conflict-free banking without replicating the array

Let `B` be butterflies/cycle, `K=2B` data banks, and `k=log2(K)`:

- B=4: K=8, k=3.
- B=8: K=16, k=4.

For a 16-bit logical coefficient address `a`, define

```
bank(a)[r] = XOR of a[j] over j congruent to r modulo k
row(a)     = a >> k
```

Equivalently XOR the successive k-bit chunks of `a`. This is a bijection:
the row supplies all high address bits, and XORing their contribution out of
the bank recovers the low k bits. Capacity remains **N 32-bit words**, not
K copies of N words.

At radix-2 stage s, a butterfly pairs `a` with `a XOR (1<<s)`. Let `p=s mod k`.
Form a group by varying exactly these k address bits:

```
{0,...,k-1} minus {p}, together with {s}
```

Hold every other bit fixed; enumerate those fixed-bit assignments between
groups. The varied bits contribute the k different unit vectors to the bank
index, so a group contains **one address in every bank** and **B complete
butterfly pairs**. Across groups every logical address occurs exactly once.
This works for all 16 stages, not only adjacent operands.

Each bank uses one synchronous read and one delayed write per cycle. Stage
drain prevents dependencies crossing stages; within a stage addresses are
disjoint, excluding same-row read/write collisions. Preserve delayed address
tags and assertion checks. Lane routing pairs banks separated by `1<<p`;
only k pairing patterns and a group-dependent operand swap are needed, rather
than an unconstrained all-to-all crossbar. Registers and routing still need fit.

An exhaustive Python enumeration **on aethia** checked both proposed mappings
at N=65536: bijection, every address exactly once per stage, all butterfly
pairs, bank uniqueness, and twiddle-bank uniqueness across all 16 stages.
This is a scheduling check, not RTL or physical verification.

### Ports and packing

Use independent narrow banks. Simply packing K coefficients into one wide
word does not supply K independently addressed operands: upper stages need
two row addresses and concurrent delayed writes. Multi-pumping or duplicated
full arrays are not required by the proposed bank schedule.

Arria 10 M20Ks offer simple/true dual-port configurations; a logical 32-bit
true-dual-port bank may be assembled from narrower physical slices. Do not
count each logical bank as one M20K or assume arbitrary extra ports.
[Vendor memory handbook, embedded-memory chapter](https://www.intel.com/programmable/technical-pdfs/683461.pdf).
At N65536, the current fitted 32-bit data array consumes 128 M20Ks. Splitting
that depth among 8/16 banks should preserve approximately the same block
count because bank depths remain large and aligned; verify actual mapping.
One root table adds another N words, approximately 128 M20Ks. No replication
factor proportional to B is inherent in either array.

Dropping bit reversal permits a simpler one-read/one-write bank template.
Keeping reversal requires explicit two-port swap access; generalized banking
does not necessarily put reverse-address pairs in the same bank.

## Root bandwidth

At stage s, twiddle index is `t=(a mod 2^s)*2^(15-s)` for the member with
address bit s=0. Bank the root table with the same XOR-chunk map. For the
group above, varying the participating low address bits moves t along distinct
bank-coordinate directions. All **distinct** twiddles therefore occupy
distinct root banks; repeated twiddles in early stages are broadcast.
One read per root bank suffices, without table replication.

Table filling is separate from transform bandwidth. Retaining the existing
one-root/cycle generator costs about **4N payload cycles/square**, regardless
of B. A W-root/cycle generator can use W multipliers and **4W interleaved
power contexts**, seeded at exponents 0..4W-1 with recurrence stride 4W.
Then phase filling costs about `4*ceil(N/W)` plus start/drain overhead.
Consecutive generated addresses occupy distinct banks when W<=K.

Do not multiply a single feedback sequence W times in one cycle: the
four-cycle feedback dependency remains. Also, forward/inverse NTTs only use
N/2 roots each, so shortening those two fills reduces the scalar payload
budget from 4N to 3N; phase constants still use the original transform N.
That simpler optimization can precede a wider generator.

## Remove bit reversal with DIF/DIT

Use natural-order twist → **forward DIF** → pointwise square in bit-reversed
order → **inverse DIT without its initial reversal** → natural-order fused
untwist/normalization. Pointwise squaring does not care about permutation.
The new DIF butterfly computes `u+v` and `(u-v)*w`; it needs a separately
verified arithmetic/alignment path. Merely reversing the current DIT stage
counter is incorrect.

For N65536, each current reversal costs `N+S=98176`, where
`S=(N-2^ceil(log2(N)/2))/2`. Removing both saves **196352 cycles/square**,
with no extra full array. Keep this ordering contract internal to a combined
square engine; the existing public natural-order NTT interface must not
silently change. Compare intermediate values using explicit bit reversal in
the independent oracle, then check complete square results and reset behavior.

## Cycle budgets including the surrounding work

Assume three field engines concurrent, II1 within each lane, **B pointwise
lanes**, and a six-cycle butterfly/five-cycle pointwise drain budget:

```
T_B = 16 * (32768/B + 6)          # one transform, no bit reversal
A_B = 2*T_B + 3*(65536/B + 5)    # fused arithmetic per field
C_square = C_convert + C_roots + A_B + C_CRT + C_carry + C_control
```

The table below uses a **schedulable planning budget**, not the current
integrator's measured counters: conversion at one digit/cycle (`65536`),
II1 CRT including its pipeline (`65596`), and the existing measured
full-size-square carry example (`589934`). Root/control pipeline edges,
port stalls, and transfer handshake cycles still need measurement.

| B | Arithmetic A_B | Total with scalar root fills (4N) | Total with W=B root fills |
| --- | ---: | ---: | ---: |
| 1 | 1,245,391 | 2,228,601 | 2,228,601 |
| 4 | 311,503 | 1,294,713 | 1,098,105 |
| 8 | 155,855 | 1,139,065 | 909,689 |

Thus 4→8 butterfly lanes approximately halves arithmetic cycles but improves
this wider-root end-to-end budget by only **1.21x**. Carry alone accounts for
about 65% of the last row. The carry example is **not a universal upper bound**;
canonical/-1 cases, radix, coefficients, and subsequent sweeps change its cost.
Conversion/CRT must really sustain II1, or substitute their actual cycle
counts. A serial host-style memory handshake must not be hidden in the model.
At clock f, time per square is `C_square/f`; no candidate clock is assumed.

## Priority and acceptance gates

1. Measure the integrated one-lane design with all conversion/root/CRT/carry
   work included; keep its independently checked output as the reference.
2. Implement DIF→DIT ordering, prove full-size repeated squares, and fit it.
3. Build four butterfly lanes with eight banks; test the full address schedule,
   root broadcasts, delayed writes, resets, N2/N16 lane masking and N65536.
   For N<K, mask inactive lanes rather than issuing out-of-range addresses.
4. Shorten root fills, then widen generation only if measured overhead warrants.
5. Optimize carry before spending heavily on eight lanes. Promote eight lanes
   only if integrated fit, routing, timing and end-to-end cycles justify it.
