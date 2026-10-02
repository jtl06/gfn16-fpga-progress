# Adjacent-stage NTT fusion: mathematical and schedule feasibility

Status: mathematical prototype passed; **no new RTL, simulation, synthesis,
fit, Fmax, or measured throughput result**. Frozen cached/generated/prefetch
engines are unchanged. This is a bounded next-step design, not a replacement
for the validated implementation.

## Decision

Proceed first with an isolated two-stage controller that reuses the existing
butterfly array. The exact coefficient banking permits two dependent stages
to keep their intermediate values in registers instead of writing and reading
the entire NTT RAM. This halves transform data accesses without adding generic
multiplier pipelines. It does not halve arithmetic work or transform cycles.
The modeled saving is only two clocks per stage pair, before new control and
routing costs. Its plausible benefit is physical locality and reduced RAM
activity; only RTL and a matched fit can establish that benefit.

Do not initially double the butterfly array. The obvious two-layer spatial
schedule has actual root-bank conflicts, and adds one complete array of
multiplier pipelines per field. Neither aggregate root width nor four-point
notation proves that spatial design feasible.

## Exact arithmetic and evidence

`reference/ntt27_radix4_feasibility.py` checks ordinary exact modular arithmetic
independently of hardware Montgomery encoding. The hardware contract remains
the current three primes 104857601, 69206017, 67239937 and R=2^32; an RTL
implementation must preserve canonical operands and existing root profiles.

For a pair of adjacent stages s and t=s-1, use coefficient order
`[a,b,c,d] = [x[j],x[j+2^t],x[j+2^s],x[j+2^s+2^t]]` within each group.
Let w be the high-stage root, v=w^2 and i=omega^(N/4). The exact DIF equations
are:

```
x0 = a+c;       x1 = b+d
x2 = (a-c)*w;   x3 = (b-d)*w*i
out = [x0+x1, (x0-x1)*v, x2+x3, (x2-x3)*v] mod P
```

A factored version uses `(a-c) +/- i*(b-d)` followed by w and w^3,
and `(a+c-b-d)*w^2`. It still has three variable-root products **plus one
nontrivial constant-i product**. For our selected generators:

| Field | i, centered | Implication |
| --- | ---: | --- |
| 104857601 | -10240 | Sparse -(2^13+2^11), but exact reduction is still required |
| 69206017 | 4325896 | Not a sign flip or word permutation |
| 67239937 | -22238187 | Not a sign flip or word permutation |

Thus there is no established 25% multiplier saving. A later constant-product
experiment must measure the reduction circuitry and timing, not count only
shifts. The first proposed RTL should use the unchanged two radix2 layers.

Primary algorithm precedent: Genefer22's `_forward4x1` performs four FWD2
operations, while `forward4io` loads a local four-value group and stores after
both layers. This supports local stage fusion, not a transferable FPGA
speedup or multiplier-count claim. Source inspected:
[Yves Gallot, Genefer22 OpenCL kernel](https://raw.githubusercontent.com/galloty/genefer22/main/ocl/kernel.cl).

## Conflict-free coefficient and root schedule

The existing memory has B=2L banks, with k=log2(B),
`bank(a) = XOR of successive k-bit address chunks`, `row(a)=a>>k`.
Because L>=2, the two adjacent stage bits occupy distinct bank coordinates.
For each coordinate r choose its low representative bit r, except replace
the representatives for s mod k and t mod k by s and t. Vary those chosen
bits and enumerate the remaining fixed bits between groups. Each group:

- contains min(N,2L) coefficients, at most one per physical bank;
- is closed under toggling either stage bit, so contains complete four-point
  dependency groups;
- covers disjoint addresses from every other group;
- retains the original bank/row inverse; no additional complete NTT store.

Each microphase's **distinct** root indices also occupy distinct root banks;
duplicate roots are broadcasts. The prototype enumerates every adjacent pair
for every runtime log2(N)=2..16 and both L=16/64. It checks coefficient
coverage, two-bit closure, bank/row inversion and root conflicts directly.

For the shared six-stage butterfly pipeline, group g uses this edge schedule:

| Event | Edge relative to first read |
| --- | ---: |
| Read group data and first-layer roots | 2g |
| Accept first layer | 2g+1 |
| Capture first-layer output; read second-layer roots | 2g+7 |
| Accept second layer using held intermediate values | 2g+8 |
| Commit second-layer result to coefficient RAM | 2g+14 |

First-layer issues are odd; second-layer issues are even. Root requests also
alternate. A single extra 2L-word frame suffices: capture on one edge, consume
on the next. Read/write overlap addresses belong to disjoint groups, so there
is no same-address read-during-write dependency. The design still requires
the existing one-read/one-write RAM behavior, registered routing, correctly
tagged output kind and row addresses, and complete draining between pairs.

The dedicated two-layer alternative would read A(g) and B(g-6) roots in the
same cycle. The report includes concrete different-address/same-root-bank
conflict witnesses for both lane counts. This is a counterexample to that
naive schedule, not proof that every spatial implementation is impossible.

## Quantified resource and cycle model

At N=65536 there are G=N/(2L) groups per pair. Frozen radix2 stage cost is
G+8 (one setup plus read/compute/drain); the proposed schedule models a pair
as 2G+14. Eight pairs replace sixteen stages. These are static schedule
equations, **not measured new-engine cycles**. Pointwise twist, square and
postconversion are unchanged.

| Per-field quantity | L16 | L64 |
| --- | ---: | ---: |
| Groups per pair | 2048 | 512 |
| Original transform clocks | 32896 | 8320 |
| Modeled fused transform clocks | 32880 | 8304 |
| Additional generic multiplier pipelines, shared design | 0 | 0 |
| Additional intermediate data bits | 1024 | 4096 |
| Original distinct root reads per transform | 423936 | 359936 |
| Fused distinct root reads per transform | 325632 | 278016 |

Both transforms together model only 32 clocks saved per square. A spatial
double-array alternative adds L butterfly/multiplier pipelines per field,
or 3L for all fields, before root delivery and interconnect costs. No raw DSP
block count is inferred from that pipeline count.

Each transform's coefficient accesses fall from 2*N*16=2097152 words to
2*N*8=1048576 words. Across two transforms this removes 2097152 32-bit word
accesses per field: 8 MiB of internal RAM traffic, 24 MiB across all fields.
These are not external memory-transfer savings, capacity savings, or a power
measurement. The data/root RAM capacity is unchanged. Intermediate bits omit
control, mux, valid and address tags; an implementation must budget those.
The 14-clock lifetime at interval2 requires up to seven in-flight group tags;
the existing tags cannot simply be reused without changing their semantics.

## Validation and frozen integration boundary

The full mathematical run checks 240 bank/pair geometries and 3670024
coefficient addresses. It performs 4722984 transform coefficient comparisons,
all three fields and both lane counts, forward/inverse signs, DIF/DIT order,
and factored/direct formulas. Small sizes are cross-checked with a naive NTT.
Twelve negacyclic-square cases include N2/N16/N65536, random digits, the -1
sentinel, full-size all-maximum digits, and optional doubling. Centered CRT
results match exact Python integer squaring modulo base^N+1 at base=10^9;
the all-maximum convolution additionally matches its closed-form coefficients.

Reproduce from the workspace root with:

```
python3 -m fpga.reference.ntt27_radix4_feasibility
```

The report records prototype/reference source hashes. A quick mode limits
runtime sizes to N1024. This is reference/index/event-model validation, not
hardware simulation and not exhaustive value testing.

Recommended next isolated RTL boundary:

1. New named cached-root engine/controller; preserve every frozen engine,
   butterfly, sparse multiplier, memory wrapper and square core unchanged.
2. Preserve the scalar/vector host and profile format, all order modes,
   runtime-size handling, counters, reset/start/error rules and R=2^32.
   Odd log2(N) retains one radix2 stage; N2 remains radix2. Do not silently
   restrict the existing parameter range: use an explicit radix2 fallback
   if a supported configuration cannot form a four-point group.
3. Implement only the shared-array two-stage schedule with canonical outputs.
   Do not simultaneously integrate generated roots, lazy reduction, changed
   arithmetic or direct CRT forwarding; each changes the proof boundary.
4. Run bounded aethia RTL gates for small runtime sizes and all fields,
   comparing exact intermediate pairs, full transforms, counters and reset
   at every pipeline position. Include bad stage/root/address tag mutants.
5. Only then run full-N exact integer gates and matched component fits.
   Physical wins must survive any new first/second-layer routing muxes.
   Whole-core integration follows only if measured cycles and fitted area/
   clock justify it; reduced RAM transactions alone do not prove throughput.
