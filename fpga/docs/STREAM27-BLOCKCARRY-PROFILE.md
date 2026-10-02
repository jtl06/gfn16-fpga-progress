# stream27-blockcarry — separate arithmetic profile

Status: adopted for implementation by `briefs/2026-09-30-answers-B20260930-r6.md`; S1 model qualified, RTL/physical implementation unqualified. No frozen profile is replaced. P8 is the first implementation; P16 remains a model-only area comparison.

## Geometry and representation

Let N=2^AW, 32≤N≤65536, P a power of two dividing N, and T=N/P≥2. The S3 target is P=8. Arithmetic represents a residue modulo b^N+1, equivalently a polynomial modulo x^N+1 evaluated at x=b.

Store N ordinary digits d[i], and two signed corrections per block:

    effective[k*T]   = d[k*T]   + c0[k]
    effective[k*T+1] = d[k*T+1] + c1[k]
    effective[i]    = d[i] otherwise

Write B=b−1 and K=2N+24P. The invariant is:

- 0≤d[i]≤B;
- |c0[k]|≤B;
- |c1[k]|≤K.

The c0/c1 arrays belong to the same completed image, base and generation as d. They must never be silently omitted from a square, comparison, checkpoint or readback. The canonical −1 residue may be encoded by zero digits, c0[0]=−1 and all other corrections zero. Other accepted signed input vectors must first be normalized into this representation; a signed host digit is not an unsigned NTT residue.

## Supported bases and coefficient proof

Require integer

    max(2N+5, ceil(2*(2N+24P)/3)+1) ≤ b ≤ 1,000,000,000.

For N65536/P8, this is 131077≤b≤10^9. Reject unsupported geometry/base before accepting work; never silently skip vectors. The lower bound combines the frozen precision-carry guard with 2K≤3B.

Use the three fields (prime, primitive root): (104857601,3), (69206017,5), (67239937,10). Their product M supplies centered CRT reconstruction, with values above floor(M/2) mapped negative.

The absolute coefficient bound, including conditional doubling, is

    A = 2 * ((N+3P)*B² + 4P*B*K + P*K²).

The terms bound d*d, all c0 cross terms, c1 cross terms, and c1*c1; both sparse supports have P entries. T≥2 keeps input supports distinct. Verify A≤floor(M/2), rather than assuming three primes suffice for an arbitrary base/profile. At N65536/P8/b10^9, A=131120008138931675533360.

For serial within-block carry, |q|≤ceil(A/B) is inductively closed. Splitting the final carry q=q0+b*q1 with 0≤q0<b gives

    |q1| ≤ ceil(A/(B*b)) ≤ 2N+23P < K.

Thus the next image satisfies the same invariant, including arbitrary square/double chains. The exact-integer executable bound/proof reference is the frozen `reference/stream_ntt_blockwrap2_proposal.py`, SHA b6f94debf66b07aa118ab7e82be6802fd5a81cbc8c41a99cb79f65f91726e255. Its historical “unapproved” labels are preserved; this document records the later adoption without editing that evidence.

## Block carry and complete boundary normalization

Each block starts its carry at zero. For coefficient a[i], two Euclidean divisions produce

    a[i] = r0[i] + b*r1[i] + b²*q2[i],  0≤r0,r1<b.
    y[i] = r0[i] + r1[i−1] + q2[i−2].
    (c_next,d[i]) = divmod(y[i]+c,b).

Missing history at a block start is zero. Only c∈[−2,3] is in the one-edge feedback loop; the wide divisions are feed-forward pipelines. Signed Euclidean division means a nonnegative remainder, including for negative input. Magnitude/sign handling and the proven coefficient/quotient bounds must be explicit in RTL; truncating a signed product is not a valid reduction.

At the end of a block:

    raw0 = r1[last] + q2[last−1] + c_final
    raw1 = q2[last]
    (adjust,low) = divmod(raw0,b)
    high = raw1 + adjust

Transfer low/high to c0/c1 of the next block. Negate both for the final block's wrap to block0 because x^N=−1. Keep the complete normalization: the single ±b adjustment shortcut fails within the supported small-base coefficient bounds. The preserved counterexample is `one_adjust_counterexample()` in the proof reference. Do not assert that every bounded coefficient vector is reachable from a square; the circuit must nevertheless honor its declared input bound.

## Stream order, corrections and Montgomery domains

The mirrored transforms eliminate the natural-order frame adapters. Physical lane l carries natural block bit_reverse(l,log2P), with within-block offset t. Forward spectral slot s=P*t+l corresponds to frequency j=bit_reverse(s,AW); inverse consumes that same spectral order.

For each field let psi be a primitive2N-th root and omega=psi². Compute two P-point correction transforms from psi^(kT)*c0[k] and psi^(kT)*c1[k]. Their outputs A_small and B_small are indexed by j mod P. Correct the forward result before squaring:

    X_corrected[j] = X_digits[j] + A_small[j mod P]
                    + psi*omega^j*B_small[j mod P]  (mod prime).

The term generator uses four contexts and reseeds when B_small changes; it must not divide by a prior coefficient or apply a constant-coefficient recurrence across a change. Zero coefficients are legal. Corrections and data are generation-tagged through drains and any buffering.

The sparse multiplier uses R=2^32. Data residues are ordinary; multiplication by an R-scaled root preserves that domain. Pointwise Montgomery squaring introduces R^-1. The unnormalized inverse must therefore use the single fused final constant psi^(-i)*N^-1*R². The software inverse's built-in normalization is removed explicitly in the joined model before modeling this final hardware operation. Applying only R, or normalizing twice, is incorrect.

## Canonicalization and host-visible behavior

Canonicalization evaluates the complete effective representation modulo b^N+1. Return N digits in [0,b−1], except represent b^N as [-1,0,…,0]. `BlockState.canonical()` / the independent whole-integer oracle define the result, not an implementation latency.

- Readback/checkpoint/comparison must canonicalize or explicitly preserve the entire redundant image plus its base/profile identifier. Never expose d alone as a canonical result.
- Before a partial host mutation, complete canonicalization, clear cached-transform/correction eligibility, then apply the accepted write. Subsequent work must use a coherently rebuilt image.
- Before changing base, canonicalize under the old base. Reinterpret those canonical digits under the requested base only if they satisfy the new profile's digit/base contract; otherwise reject and require reload. Do not reinterpret old c0/c1 under a new base.
- Canonicalization has real latency and is outside the warm-square interval. The eventual host wrapper must explicitly provide a completion/backpressure or normalization protocol; it may not accept and silently lose a request. Its interface/latency remains an S4 gate, not an inherited immediate-read claim.
- Complete reset/reload into a new valid base is always the recovery path. Host actions presented while busy follow the existing ignored-request priority; they cannot alter the accepted base/double bit.

## Reset, errors and completion

Reset cancels every valid/tag/generation, correction table, carry history, cached-image flag and output eligibility; physical RAM need not be reset. No pre-reset token may produce a later done/read-valid or valid cached image. Reload every digit after reset or reported error. No rollback of partially written RAM is promised.

Accept a new image only after all required data/corrections, tail drains and registered child errors have been accounted for. On a range/order/child error, invalidate eligibility, enter the established error/quarantine behavior and do not report successful completion. Tests must cover reset/error at stream start, interior, boundary correction and final drain, plus an immediate next start.

## Evidence and implementation gates

S1 frozen schedule: `reference/stream_ntt_blockcarry_schedule.py`, SHA eca87517cada3413f18313d447b76e1fcf3c3826e70391f3baf39561ab23b632. Native full-N P8 joined arithmetic passed four dependent square/double operations at the minimum and maximum bases; independent integer digests and38 event rows matched. This is finite software-model evidence, not RTL equivalence or exhaustive arithmetic testing.

At full N/P8 the model interval is16660 clocks with79 clocks correction margin. Nominal269839ALM/1978M20K/717DSP figures are planning estimates. Account for possible8 divider M20Ks and raw-vs-needed DSP differences; none is a physical guarantee.

S3 order: prove the small-carry feedback cell, signed boundary reducers and synchronous-RAM commutators; then one P8 field forward/square/inverse. Gate small AW then AW16 against the model, including mid-stream reset. Measure synthesis/resources, then route the component with setup/hold passing at100MHz. Continue to S4 only if measured one-field ALMs are≤110% of a clearly itemized, source-bound per-field model allocation. Do not substitute the whole-core estimate divided by three without separating shared CRT/carry/control resources. No field or whole-core clock is qualified yet.
