# Replacing cached NTT roots with short recurrences

Root generation is mathematically feasible for the frozen wide engine's exact
bank schedule, at 16 and 64 lanes and every runtime power-of-two N from 2 to
65,536. Both a common-factor design and a direct per-root-lane recurrence
passed independent Python checks for all three experimental 27-bit fields.
Neither requires the current 3N cached root words per field. This is a proof
and resource-planning result only: no generator RTL, integration, synthesis,
timing result, or measured throughput improvement is included.

The original proposed high-stage exponent formula was incomplete. Correct
generation needs a parity term, explicit period-wrap handling, the actual bank
permutation, and ordinary rather than Montgomery postconversion roots.

## Exact exponent and lane schedule

Write N=2^ell, L=LANES, K=log2(2L), s=stage_bit, p=s mod K, and
h=ell-1-s. Let g be the existing butterfly group_index. The frozen engine's
`fixed_position` mapping gives the common root exponent B(g):

```text
s < K:   B(g) = 0
s >= K:  B(g) = [(g mod 2)*2^p
                + (floor(g/2) mod 2^(s-K))*2^K] * 2^h
```

At high stages, the first fixed address bit is the low position p, supplied
by g[0]. Positions K through s-1 then receive g[1] upward. Consequently the
period is `T=2^(s-K+1)`, not `2^(s-K)`. For example, at L16, N65,536, s=5,
group 1 has B=1024, whereas the originally proposed expression gives zero.

Each needed root exponent is `E=B(g)+v*2^h`. At low stages v occupies positions
below s. At high stages v occupies the low K bits except position p. The
common exponent uses position p and positions K through s-1 before shifting.
These bits are disjoint, so the frozen bitwise OR is exactly integer addition.
There are `D_s=min(L,2^s)` distinct roots per group, even when more butterfly
lanes reuse them.

Let bb be the frozen XOR-folded `bank_of(base_addr)`. A compressed seed index
j for arithmetic lane a is:

```text
s < K:   j = (a XOR bb) AND (2^s-1); v = j
s >= K:  j = a XOR remove_bit(bb,p); v = insert_zero(j,p)
```

This is not generally j=a. For L16, stage 5, group 2, arithmetic lane zero
requires seed index one. A logarithmic XOR/broadcast network can route the
seed vector; no separate many-port seed RAM is needed per arithmetic lane.
Small N activates only its existing N/2 butterfly lanes. The independent
proof reconstructs each logical data address from its physical bank and RAM
row before checking the candidate exponent, rather than using the candidate
formula as its own oracle.

## Four interleaved recurrence contexts

For a forward or inverse cyclic root alpha, use Montgomery R=2^32, unchanged
from the existing arithmetic despite the 27-bit primes. The common factor is
`C(g)=alpha^B(g)*R mod P`. A logical root-lane seed is
`S_j=alpha^(v_j*2^h)*R mod P`. The common-factor architecture produces the
required Montgomery root with `Mont(C(g),S_j)`.

For T>4, groups g and g+4 retain the same parity while floor(g/2) advances by
two. Away from period wrap, the common-factor and every direct-root context
advance by the same Montgomery step:

```text
D_R = alpha^(2^(K+h+1))*R mod P
C(g+4) = Mont(C(g),D_R)
```

The exponent decreases by N/2 at a period wrap. Omitting this wrap correction
therefore introduces a factor of -1, not an innocuous full-turn identity.
Use seeds for the first four groups of every period and discard the speculative
updates crossing that boundary. For T=1, 2, or 4, use the corresponding repeated
seed pattern directly, or an identity step for each repeated context. The
proof explicitly tests these short periods rather than extrapolating the
unwrapped step formula.

A simpler alternative maintains the complete logical root for each j:
`A_j(g)=C(g)*S_j/R mod P`. Each of L extra Montgomery pipelines advances one
logical root lane by D_R. It needs four context seeds per lane at long-period
stages, but no common-factor multiplier or separate root-combination stage.
After selecting the current root vector, apply the lane permutation above.

The sparse multiplier accepts at edge t and registers its result at edge
t+3. With four contexts, that result is available before the next use of the
same context at edge t+4. This requires direct result feedback or an explicit
bypass. A separate `state <= result` register updated at edge t+4 cannot also
supply its new value to an edge-t+4 consumer; that naive arrangement needs a
fifth context or a bypass. The Python event model uses the result available
from edge g-1 for the context first consumed at edge g-4.

The frozen engine issues groups contiguously within a stage. That assumption
allows the simple four-cycle feedback model here. A future implementation
that stalls individual groups must use tagged context writeback/bypass or
otherwise preserve the recurrence's accepted-group ordering; a fixed cycle
counter alone would not be sufficient.

## Twist and postconversion

For pointwise group g, the logical coefficient address is `g*L+j`, but the
arithmetic lane's j is `lane XOR (bank_of(g*L) AND (L-1))`. Direct per-logical-
lane sequences therefore work for both pointwise root phases with four initial
groups and step `psi^(4L)*R` or `psi^(-4L)*R` respectively. Partial small-N
groups activate only the first N logical offsets.

Twist seeds are Montgomery values `psi^i*R`. Post seeds are ordinary values
`psi^(-i)/N`, exactly as in the existing fused postconversion. An ordinary
post seed multiplied by a Montgomery step remains ordinary. Encoding post
seeds with an extra R would leave the final result in the wrong representation.
The proof checks both phases separately against their full direct-power tables.

## Seed tables and read ports

The selected generator-derived roots are coherent across sizes:
`omega_N=omega_max^(2^(16-ell))`. Therefore a butterfly seed
`omega_N^(v*2^(ell-1-s))` equals `omega_max^(v*2^(15-s))`, independent of
runtime ell. A single forward/inverse stage-seed table covers every N. This
identity does not hold for unrelated independently selected primitive roots.

In the direct design, store `D_s*min(4,T_s)` seeds per butterfly stage and
direction. Pointwise seeds number `min(4L,N)` per phase. A single serial ROM
read port can preload the active seed registers before each phase/stage.
During arithmetic, seeds are read from parallel registers and routed by XOR;
the ROM is not replicated L times. A second register set permits background
prefetch of the next seed set using the same ROM port.

The following are per-field planning counts, including conservative step
constant storage. A word contains one 27-bit residue. Fixed N means N65,536;
all sizes means all 16 supported runtime sizes in one table. The block columns
are only `ceil(words/512)` capacity estimates for a packed 512-by-32 store,
not inferred or fitted M20K results.

| Design and lanes | Extra multiplier pipelines | Fixed-N words | All-size words | Fixed/all-size block estimate | Active seed register bits |
|---|---:|---:|---:|---:|---:|
| Direct L16 | 16 | 1,568 | 3,002 | 4 / 6 | 1,728 |
| Common-factor L16 | 17 | 582 | 1,116 | 2 / 3 | 540 |
| Direct L64 | 64 | 5,152 | 9,786 | 11 / 20 | 6,912 |
| Common-factor L64 | 65 | 1,658 | 3,172 | 4 / 7 | 1,836 |

Seed double buffering doubles the last column. Current full root tables use
196,608 words per field, or 6,291,456 raw bits at 32 bits per word. Their
512-by-32 capacity equivalent is 384 blocks per field, 1,152 across three
fields. Both alternatives greatly reduce that storage requirement without
changing the N-word data RAM. Table decoder, seed register, routing, pipeline,
and control costs remain additional physical resources.

Across three fields, direct L16/L64 adds 48/192 Montgomery pipeline instances;
the common-factor choices add 51/195. These are arithmetic-instance counts,
not promised DSP block counts or clock rates. Mapping must be measured with
the selected sparse helper. Neither option shares these recurrence operations
with the existing butterfly multiplier at full throughput.

## Pipeline alignment and setup costs

The direct design can capture its current root in one register alongside the
data RAM read, preserving the current one-clock operand availability and
seven-clock data-read-to-write distance. The recurrence multiply computes a
future root, not the root needed by the current butterfly. Stage/phase changes
must invalidate old recurrence metadata, and seed readiness must gate launch.
The existing seven-clock stage drain exceeds the four-stage root update pipe,
so continuous stage work can drain before new seeds are selected.

The common-factor design combines the current common factor and lane seed
through a four-stage multiplier. If launched beside the data RAM read, the
butterfly must wait three additional clocks relative to the one-clock RAM
root. Data, bank orientation, addresses, valid bits, and output tags must all
be delayed consistently. Alternatively, launch roots three groups ahead and
retain the current data schedule after a three-clock root fill. Hiding that
fill across phase boundaries requires explicit prefetch control; it is not
automatic from the exponent proof.

For an intentionally conservative unprefetched controller, assume U seed reads
plus one step read after the descriptor setup, then one clock to capture the
last synchronous ROM response. This adds U+2 clocks before the first data
read compared with the current one-clock descriptor setup. Under that stated
schedule, one full-size square's two 16-stage transforms plus twist/post add:

| Design | L16 extra clocks | L64 extra clocks |
|---|---:|---:|
| Direct, serialized seed setup | 1,602 | 5,186 |
| Common-factor, serialized seed setup | 616 | 1,692 |
| Common-factor root fill/alignment, additionally | 102 | 102 |

These are proposed-schedule counts, not simulated RTL timing. At full N,
each butterfly stage has 2,048 groups for L16 or 512 for L64, while the largest
next direct seed set needs only 64 or 256 serial seed reads. Thus one-port
background prefetch has enough clocks to hide subsequent stage seed loading,
provided a second seed register set and correct next-stage descriptors exist.
The first phase still needs initial setup unless its seeds were prefetched
earlier. Small runtime N can have fewer work clocks than the next seed load
requires and must explicitly wait. Reset cancels readiness and forces reload;
it must not reuse stale seeds or late updates from another stage.

## Recommendation and compatibility limits

Both designs are worth a bounded standalone generator comparison if resource
measurements justify proceeding. Direct recurrence is simpler on the critical
data path and avoids root-combine latency, but has more seed registers and
greater unprefetched setup cost. Common-factor generation uses one extra
multiplier per field but much smaller seed state. The proof does not establish
which will route or clock better; neither should be selected solely from the
raw memory savings.

This is not a drop-in replacement for arbitrary `root_we` cache contents.
The frozen engine accepts externally supplied root tables, including values
that do not follow a coherent recurrence. A future implementation must be an
explicitly specialized prime/root-profile engine or define and validate a
seed/step-loading contract. It must not silently discard arbitrary root writes
while claiming to preserve the old cache interface.

## Verification evidence

`reference/root_recurrence_proof.py` ran only on aethia with a 6 GiB address-
space limit and systemd 6 GiB/no-swap/two-CPU scope. It tested L16 and L64,
every ell from 1 through 16, and P=104857601/69206017/67239937 with generators
3/5/10. It checked both root directions, every banked butterfly, twist and
ordinary post roots, factorized and direct recurrence outputs, and coherent
size-independent seeds. Totals were 25,165,824 numeric root comparisons,
1,966,082 butterfly geometry checks, 460,938 common-factor checks, and 34,344
cross-size seed checks. Counterexamples explicitly reject the missing parity,
missing wrap reseed, missing XOR routing, wrong post Montgomery scaling, and
naive external-state four-context feedback assumptions.

Final report:
`/home/jtl/gfn-fpga-lab/agent-work/root-proof/fpga/artifacts/recurrence-v2-final/report.json`,
status `passed_python_proof_not_RTL`.

Source identities:

- Proof script: `41136efa238fed74562977010f4c91dcb073b779333400b243c48c26680f6cda`
- Frozen wide engine: `038b496b97d231417c406c334e57c6f21cb0c0f45d7619430630a22d8cb815af`
- Sparse Montgomery helper inspected: `501d0ce309a3915f7aed0f3bde14ba1ee8d56ddc5f6abef1f2f5bb572d64db4b`
