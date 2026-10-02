# Bank-centric cached DIF/DIT routing candidate

`genefer_ntt_banked_engine.sv` is a separate prototype. Frozen parallel/cache
engines and the square core are unchanged. It retains the cached engine's
scalar host ports, root_phase selection, compact root regions, DIF/DIT
ordering, small-N masking, arithmetic pipeline lengths and exact counters.
This work has **no Quartus resource/timing result**.

## Physical bank ownership

Let B=LANES, K=2B, k=log2(K), stage bit s, and p=s mod k. Let `base` be the
fixed-bit group address from the earlier proof and `bb=bank(base)`.
For physical arithmetic lane l:

```
bank_lo = insert_zero_bit(l,p)
bank_hi = bank_lo XOR (1<<p)
orientation = bb[p]
u_bank = orientation ? bank_hi : bank_lo
v_bank = orientation ? bank_lo : bank_hi
```

The lane's selected logical low address bits are `u_bank XOR bb`; their p bit
is zero, as required. Each bank independently calculates its RAM row:

```
row(bank) = (base OR (((bank[p] XOR orientation)<<s))) >> k
```

Consequently data reads do not select from K banks independently for each
operand. Each lane selects among only **k fixed pairing patterns**, then a
single orientation swap. Writes similarly use k fixed lane-to-bank patterns
and delayed per-bank row tags, instead of searching all lane addresses for
each bank. Small-N active pairs occupy the first N/2 lanes and first N banks.

Pointwise groups use two physical bank halves. Each lane's input is selected
between bank l and bank l+B, and its result returns to that delayed half.
An XOR-induced permutation within a natural contiguous group changes physical
lane ownership, not the elementwise operation or public data ordering.

## Structured root routing

Pairing alone does not solve root mux growth. For root shift d=L-1-s,
rotation r=d mod k, and `tbase=(base mod 2^s)<<d`, the required root-bank
address is an affine rotated image of the selected low data-address bits.

Each root bank inverts that rotation/XOR to determine whether it is needed
and which single row to read. Read outputs pass through:

1. An XOR-permutation network removing `bank(tbase)`.
2. One of k fixed index-bit rotations.
3. Early-stage root broadcasts (truncate index bits above s).
4. An XOR-permutation network accounting for bb.
5. The same physical-pair selection/orientation used by data operands.

Each XOR layer uses two-input word muxes. The overall routing description
grows approximately as **O(K log K)** word-mux terms rather than O(K²)
independent bank selectors. Generated stage scopes express the combinational
network as an acyclic graph. The remaining scalar host read mux is still
K-way but is not replicated per arithmetic lane.

This describes logical routing complexity, not measured ALMs or Fmax. Root
permutation depth grows with k; 16/32/64-lane timing may require additional
register cuts and matching data/valid/address-tag delays. No multi-pumping or
full-array duplication is introduced.

## Scheduling evidence

`reference/ntt_banked_regression.py` independently enumerates every group at
every stage for every N2..N65536, with both four and sixteen lanes. It checks:

- Physical bank/row reconstruction and bijection.
- Correct u/v order and stage-bit difference.
- Every coefficient visited exactly once per stage.
- Structured root-bank permutation and exact required-root sets.
- Pointwise physical-half scheduling and complete address coverage.

RTL tests use the independent integer-DIF/naive-DFT oracles, cached phase
tables, recurrent/changed inputs, all fields at AW1/AW4/AW16, full-size
whole-integer convolution checks, invalid commands, host interference,
small-N masking, resets, exact counters and collision assertions.
LANES16 gets separate P1 transform/order/reset and full-size cached-square
checks; this is not yet the full three-field coverage given to LANES4.
Four mutants alter operand orientation, root permutation, row tags and vector
half alignment. Root memory shape remains 3N words/field at full size.

Remote workspace:
`/home/jtl/gfn-fpga-lab/agent-work/ntt-banked/fpga`.
The final bounded regression uses `artifacts/banked-full-v2/`; its `lanes16/`
subdirectory preserves separate wide-lane evidence. Builds use two workers
and a 6 GiB per-process virtual-address-space bound, with the existing bounded
subprocess timeouts.

Both reports state **passed**, including all four rejected routing mutants.
Frozen candidate RTL SHA256:
`5f7c0b4d5afc2c55df4432ac05edcf5f348a248c4b81d187eef2a17eca43cd5e`.

```sh
. /home/jtl/gfn-fpga-lab/fpga/tools/aethia-env.sh
python3 -m reference.ntt_banked_regression --output artifacts/banked-new-run
```

Expected arithmetic counts are unchanged from the previous engine:

| N65536 | Four lanes | Sixteen lanes |
| --- | ---: | ---: |
| Unnormalized transform | 131,184 | 32,880 |
| Pointwise pass | 16,389 | 4,101 |
| Fused field square | 311,535 | 78,063 |

These exclude cold cache filling, conversion, CRT and carry. A future integrated
fit must confirm whether the new routing helps physical resources or timing.

## Separate next change: reuse butterfly multiplier for pointwise work

This is an assessment, **not implemented in this candidate**. In DIT mode,
feeding `u=0`, `v=x`, `w=rhs` into the shared butterfly gives `y0=Mont(x,rhs)`.
Ignore y1. Thus square/table/scalar operations can share the butterfly's
Montgomery multiplier because these phases never overlap a transform.

That would remove the dedicated pointwise multiplier from each lane: B rather
than 2B Montgomery pipelines per field. If the present two-DSP-per-multiplier
mapping holds, this changes arithmetic use from roughly 4B to 2B DSP blocks
per field (excluding conversion/root generation/CRT/carry). At 64 lanes across
three fields, that difference would be about 768 versus 384 DSP blocks—not a
fit result or a claim that this unimplemented width closes timing.

The shared butterfly has six stages versus four for the pointwise multiplier.
Vector read-to-write distance would become seven instead of five cycles;
three pointwise passes would add only **six total drain cycles per square**
while retaining B products/cycle. Required changes include operation-driven
operand selection, pointwise valid/write routing, seven-cycle address/half
tags and updated counter checks. Test this independently after freezing the
bank-centric routing, including back-to-back phase changes and reset while
the shared pipeline is occupied. Do not claim the DSP reduction before a fit.
