# Complete banked adjacent-stage candidate: pre-implementation contract

This design is for a new `genefer_ntt_banked27_pair_engine`, not an edit to a
frozen engine. Primary target is LANES64; LANES16 is the smaller integration
gate. AW1..16 and every runtime N=2^lg, 1<=lg<=AW, remain supported. The frozen
six-stage butterfly and four-stage sparse Montgomery helper remain unchanged.
No Fmax, resource reduction, or whole-square improvement is assumed.
Other power-of-two lane counts through 64 remain legal; LANES1 uses only
single-stage traversal because a two-bank group cannot contain four points.

## State and ownership boundary

Keep the cached atomic27 engine's scalar and vector host ports, canonical
32-bit words, R=2^32, four root phases, load/read arbitration, size validation,
host-error behavior and reset invalidation responsibility. Retain exactly one
data store of Nmax words and the existing compact root store (with the same
minimum small-AW bank rounding). Reuse the existing RAM leaf module so memory
inference remains isolated. There is no duplicate fallback engine or memory.

One central scheduler controls LANES butterflies and one 2*LANES-word held
intermediate frame. Pair controllers are not replicated per four-point group.
One registered layer descriptor selects the active first/second pairing, root
geometry, response routing, and delayed writeback metadata.

## Pair-closed bank geometry

Let B=2L and k=log2(B). Existing storage uses
`bank(a)=XOR of k-bit chunks of a`, `row(a)=a>>k`.
For an adjacent pair h,l=h−1, choose one varying address bit per bank coordinate:

```
representative[h mod k] = h
representative[l mod k] = l
representative[r]       = r otherwise
```

Only coordinates below lg are active when N<B. All address bits not selected
as representatives are fixed bits. Expand group index g into those fixed bits,
in increasing address-bit order, to obtain base(g). Its representative bits
are zero. For physical bank b:

```
x = b XOR bank(base)
address(b) = base OR sum(x[r] << representative[r])
```

This is bijective, visits one address per active bank, and is closed under
toggling h or l. Both stage coordinates are distinct modulo k. For N<B only
b<N is active; base is zero and the existing physical-lane masking applies.
The single-stage fallback uses the same construction with only one replaced
representative. No arithmetic value is indexed through a general B-way mux.

## Root ports and routing

For the currently read layer s, set shift=lg−1−s and
`root_base=(base & ((1<<s)−1))<<shift`.
The variable mask contains exactly those r whose representative[r]<s.
For root RAM physical bank rb:

```
v = rotate_right(rb XOR bank(root_base), shift mod k)
read_enable = (v & ~variable_mask) == 0
root_address = root_base OR
               sum(v[r] << (representative[r]+shift))
               over representative[r]<s
```

Every enabled bank has one distinct in-range exponent. Duplicate requested
roots are broadcasts, not multiple port reads. For a data bank b, its selected
root bank is
`bank(root_base) XOR rotate_left((b XOR bank(base)) & variable_mask, shift mod k)`.
Fold the base term into an XOR routing control, rotate fixed wiring, then clip
disabled index dimensions through a k-layer two-input broadcast network.
This generalizes folded routing to the pair's arbitrary representative mask;
it must not assume a contiguous low-bit mask or the old single-stage row map.

Each root bank performs at most one read per edge. Root writes remain idle-only
host operations; the four cached phases are not reloaded between stages.
Each data bank uses one read and one write port. Final group g writes overlap
first reads of group g+7; they are disjoint addresses in every active bank.
No intermediate first-layer result touches data RAM.

## Issue, response and commit schedule

The first candidate adds no routing pipeline beyond the existing synchronous
RAM response. Routing complexity may affect fitted timing and must be measured.
Relative to the first read:

| Edge | Action |
| --- | --- |
| 2g | Read first-layer roots and data |
| 2g+1 | Issue first layer |
| 2g+7 | Hold first result; read second-layer roots |
| 2g+8 | Issue second layer from held frame |
| 2g+14 | Write final result |

First and second root requests occupy opposite parities, as do arithmetic
issues. The held physical-bank frame is captured and consumed on consecutive
edges. Six-edge issue metadata contains valid, layer kind, group, pairing and
orientation. Write eligibility requires current result-valids and matching
delayed kind/group, before any sticky error update.
Result-valid reduction covers every active arithmetic lane and excludes
inactive lanes when N<2L; a reduction over all configured lanes is incorrect.

The second root read reconstructs exactly the same group's row vector, so
seven-edge row tags from that read reach final commit. There is no need to
carry all bank rows fourteen clocks from the original data read. First-layer
capture uses its own delayed pairing/orientation, not the current root request.
Pointwise requests share the same butterfly array with DIT(0,lhs,rhs), as in
the frozen engine, and retain their seven-edge RAM-read/write path.

## Stage progression and fallbacks

DIF processes pairs (lg−1,lg−2), then (lg−3,lg−4), and so on. DIT processes
(0,1), then (2,3), and so on. A remaining stage is the final radix2 stage in
that traversal; N2 runs only that path. The fallback reuses the same array,
RAMs, response routing and writeback logic. Wait until final commit before
installing the next descriptor. Inverse normalization starts only after the
last transform commit; all pointwise operation semantics are unchanged.

Malformed start parameters retain the original rejection/retry contract.
An unexpected internal tag/result mismatch suppresses writes immediately and
requires a bounded drain before allowing a new operation, so rejected tokens
cannot become valid writes in a later operation. Reset clears every eligibility
tag and may interrupt setup, either microphase, holding, draining or pointwise
normalization. Host traffic is ignored during busy/start as before.
The internal-fault path stops new root/data reads and both issue streams on
the detecting edge, retains busy for seven drain edges, and rejects changed
size/direction starts during that interval. Operation-kind eligibility also
prevents an old pair result from becoming a pointwise write.

## Counters and gate priorities

Count butterflies for both actual layers, data reads only at first-layer RAM
reads, data writes only at final commits, and root reads from actual enabled
physical ports. Single-stage and pointwise accesses retain old definitions.
Drain/wait accounting will be explicitly defined and checked in the new bench;
it is not interchangeable with old stage-by-stage wait counters.

If the schedule survives full integration without extra stalls, a pair uses
2G+13 active clocks plus one setup clock, G=max(1,N/(2L)); a single stage uses
G+8 total clocks. This is a provisional complete-engine formula, not measured
RTL. No claim of 32 clocks saved per square is made until the entire candidate
and exact counter oracle pass.

Gates proceed through independent geometry/root-port/event checks, small
all-field RTL, targeted routing/tag/reset mutants, then full-N transforms and
repeated negacyclic squares. Full host/profile/arithmetic contracts must pass
before any whole-core selection or cloud fit. Frozen RTL and prior reports
remain untouched throughout.

## Pre-RTL physical model result

`reference/ntt_pair_banked_geometry.py` passed on aethia in 54.8 seconds:
1,156 cases, 11,314,750 physical addresses, and 9,339,703 actual arithmetic-lane
root consumers. Both ordered stage tuples are checked. Every lg1..16 is
covered at L16/64; lane counts1/2/4/8/32 are additionally checked through lg8.
The exact k-layer XOR/rotate/arbitrary-mask broadcast network is evaluated,
not merely a deduplicated root set. A separate reviewer independently audited
all 240 L16/64 adjacent-pair geometries with the same conclusions.

The model retains A-read data-row snapshots separately from reconstructed B
metadata and checks all seven-edge row-tag retirements, six-edge arithmetic
tokens, held-frame consumption, concurrent read/write addresses and final
drain. A controller blueprint checks 168 sampled reset/fault boundaries and
changed-descriptor quarantine; this is not verification of unimplemented RTL.
Review found that this blueprint counts the detecting edge among its seven
drain edges. The RTL candidate conservatively implements seven complete edges
AFTER detection; its dedicated fault scoreboard must verify that distinction.

Directed counterexamples reject these shortcuts:

- Activating all 128 physical banks for L64/N4: only banks0..3 are valid.
- Replacing the h7/L64 first-layer root mask126 with a contiguous mask63.
- Copying B-root rows into data writeback tags at h14/L64: required data rows
  are0/64/128/192, whereas root rows are0/1.
- Using an independently advancing group for B-read row reconstruction.

Local report: `results/throughput-20260929/ntt-pair-banked-geometry/geometry-v1-report.json`.
Model source SHA256:
`d0664781f21d0c5ad15e3741ccbc7ab72515e88e0ae25a76a7917df9c0a0ab85`.
No complete-engine RTL has been implemented or simulated at this checkpoint.

## Initial RTL checkpoint (not final qualification)

The separate candidate now exists. After preserving one failed compile caused
by a missing explicit width extension, its AW4/L16/P1 smoke passed. The next
AW8/L16 run passed all three fields, every runtime N2..256, both order modes,
inverse normalization, cached five-phase squares, host arbitration, exact
traffic/root/wait counters, and 226 reset-edge abort/restarts per field.
This is not full-N qualification. Direct row/bank assertions and internal-fault
containment/restart mutations were added afterward and require their own gate.
No frozen engine, whole core or physical target selects this candidate.

## Checked fault-eligibility checkpoint

The original candidate (`212ce15d…`) passed the AW8/L16 and AW8/L64
all-field normal gates, AW1/L64, LANES1, and the 12-negative-mutation gate.
Review then identified a separate fault-detection gap: if every active result
valid disappeared in a single-stage fallback or pointwise pass, the old
`any_valid && !write` predicate could wait forever. This did not affect normal
arithmetic but was inconsistent with the intended bounded fault quarantine.

`genefer_ntt_banked27_pair_checked_engine.sv` is a separate candidate, SHA256
`f056b8dc9cdc971ea5360560228354d88060d4d042b8d2f829c2e8644dfb73d0`.
Its only functional delta is to include expected `valid_pipe[5]` eligibility
and either arithmetic-result valid class in both fallback/pointwise mismatch
checks. The original source and reports remain unchanged.

The checked AW4/L16 all-field gate passed 35 steps, including deliberate
loss of all fallback butterfly valids (detect edge9, done16) and all pointwise
valids (detect8, done15). Both suppress writes on the detecting edge, drain
seven subsequent edges, and restart with a changed size/order without reset.
Restoring the blind predicate in each fault-injected model produces the
expected bounded `NTT timeout` counterexample. The checked AW8/L64 all-field
gate passed 39 steps with every runtime N2..256, both transform orders,
normalization, pointwise modes, cached squares and reset/host tests.

Full AW16/L64 qualification is a separate fresh-build GCP gate; passing these
small gates is not a full-size result. The approved transfer contains the
19-file source closure only. macOS tar also included AppleDouble provenance
metadata companions, ignored by compilation and excluded from the source
closure. Its delivered bundle identity is retained without alteration.

## Physical implementation risks to measure

Pairing halves transform data-RAM transactions for even log2(N), but does not
halve butterfly operations. Root-port transactions depend on the actual
pair geometry. The current root path has k XOR-selection layers, rotation
selection, and k arbitrary-mask broadcast layers; its mask need not be
contiguous (for example L64/h7 gives126). Fewer memory accesses therefore do
not prove less routing congestion or a higher clock.

Representative expansion and group decoding also distribute controls to all
banks. Potential later experiments are bank-local control replicas, explicit
data-row-only decoding (only replaced high representatives change rows), and
a finite-pattern implementation of the proven root masks. These are proposed
physical optimizations, not changes incorporated into the checked gate.
The candidate must pass full-size arithmetic/fault qualification before any
isolated synthesis; only a physical result can justify whole-core selection.

## Full-size checked candidate qualification

The frozen checked candidate passed the fresh GCP AW16/L64/all-three-field
gate: 63 steps, three builds, 519 completed operations, 7,277,166 coefficient
checks and 654 reset aborts. Every runtime N2..65536 was exercised in both
orders, including inverse normalization. Four cross-field centered-CRT
big-integer squares passed: base2, two recurrent base604832956 inputs, and
all-maximal base1e9 digits. Cached roots are retained across the changed inputs.

At N65536 the measured transform count is8304 clocks; normalized inverse9335;
each pointwise pass1031. The five-phase sum is19701, excluding host transfers,
root initialization, conversion, CRT and carry. Each transform performs
524288 butterflies, 524288 data reads, 524288 writes, 278016 root reads and104
wait clocks; the independent bench checks every counter on every operation.

Report SHA256:
`b6538e460fbed6c6abb99a89b5d501232e0f004974f36d3f2cd42663fb203a41`.
The full source snapshot, vectors and all63 logs are archived under
`results/throughput-20260929/ntt-pair-banked/full64-v1/`.
`full64-receipt.json` records source/tool/executable hashes, bounds, verified
archive integrity, the separately scoped fault gates and trusted-tool limits.
This freezes the checked baseline for an isolated physical experiment; it
does not select it in a whole core or establish physical improvement.
