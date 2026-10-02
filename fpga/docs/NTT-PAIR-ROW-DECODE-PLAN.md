# Isolated row-only decode proposal

Baseline is frozen checked `f056b8dc…b73d0`, whose full-size gate is archived
in `results/throughput-20260929/ntt-pair-banked/full64-receipt.json`.
This proposal does not change that source or mix in root-clip/control tiling.

Let k=log2(2*LANES), x=b XOR bank(base). In the proven representative mapping,
only the active one or two transform stage bits replace low representatives.
Every untouched representative is below k and contributes zero after >>k.
Therefore the exact row of physical bank b is:

```
row = base>>k
for s in active stage tuple:
    if s>=k and x[s%k]: row |= 1<<(s-k)
```

There are at most four distinct row values in a group. For low pairs all banks
share base>>k; one high stage permits two rows; two high stages permit four.
The masks are disjoint from base because those stage bits are representatives,
not fixed bits. Both stage orders produce the same row mapping for a pair.
N2/LANES1 fallback and N smaller than the bank count remain explicit cases.

## Exact proposed RTL boundary

Create a separate `genefer_ntt_banked27_pair_row_engine.sv` only after model
review. At STAGE_SETUP register two RW-bit row masks, zeroing unused/below-k
stages, and their bank coordinates. Single-stage fallback sets the second
mask to zero. Keep descriptor eligibility/reset behavior unchanged.

For each physical bank form the two conditional row terms from its constant
bank bits XOR the existing base-bank coordinates, OR with base_row. Replace
only transform `data_ra` and transform `row_tag[0]` inputs with this row value.
Both still use the current read event's group: in the B-root event this MUST
be pair_root_group, never the concurrently advancing first-read group.
The general bank_address function can remain under simulation-only assertions
as an independent witness but should no longer feed synthesized data rows.

Leave root address/routing, held frame, butterfly array, operation controls,
host paths, memory leaves, all valid/tag pipelines and counters untouched.
No new pipeline stage or change in latency is intended. Seven-edge B-read
row tags still reach commit; fault guards still suppress same-edge writes.

## Proof and gate

`reference/ntt_pair_row_decode.py` compares the reduced identity with frozen
physical_rows for every previous geometry, both pair orders and every group
and active bank. It checks small-N masks, minimum/target physical row widths,
and rejects omitted base-fold, omitted second high stage, wrong coordinate,
and copying a B-root row as a data row.

After review, the new RTL should run the existing exact arithmetic/counter
gate plus targeted row-decode mutants and reset/fault tests. Preserve baseline
evidence and compare source deltas mechanically before a matched physical fit.

This aims to remove irrelevant full-address expansion from row control. It
does not prove less area or better timing, and does not address the measured
long root-RAM-to-XOR wire. The tools may already optimize parts of the old
expression; only measured mapping/placement can establish a physical benefit.

## Model result before RTL

The bounded aethia run passed in13.73s: 1,156 geometries, 226,454 groups and
11,314,750 active physical-bank rows. Every reduced row matched the frozen
full-address expansion; the maximum distinct rows per group was four. All
four incorrect formulas produced concrete counterexamples, including
L64/h14/l13/bank1: the required data row is128, not B-root row1.

Report: `results/throughput-20260929/ntt-pair-banked/row-decode-v1/report.json`.
Model source SHA256:
`6e297193a446a6421a8b9139618f5055efa1f21e12f890d74148d6da48e536bf`.
This qualifies the identity only. No row-only RTL candidate has been written.

## Separate RTL and narrow smoke checkpoint

The separate row engine now exists. Its source identity after the narrow
smoke fix is
`5b7b86c703f7ba9e495788172d94a00e4b79ae66ccd7b0adb1f07435afb97c9e`.
`reference/ntt_pair_row_source.py` constructs the exact reviewed delta from
the pinned checked ancestor. The private regression checks this identity
before and after execution; the bench differs only by module naming and
final-newline normalization. Independent source-boundary tests also verify
that bank_address/bf_address are absent from the synthesized view while
fault guards, same-group provenance and writeback pipelines remain intact.

The first AW1/L1/P1 compile failed because an existing simulation assertion
still referenced bf_address. That failed snapshot is preserved. The correction
retains its declaration and full-address witness only inside synthesis
translate_off, so it does not restore the old synthesized row expansion.
The fresh v2 gate then passed eight steps: 62 operations, 124 coefficient
checks and 98 reset aborts, including inverse normalization and pointwise
modes. Four independent source-boundary tests passed as well. This is only a
minimal single-stage smoke, not paired-stage or full-size qualification.

Both reports/snapshots are in
`results/throughput-20260929/ntt-pair-row/row-smoke-aw1-l1-v{1,2}/`.
The compile failure is not counted as a negative arithmetic mutation.
The broader gate is pending source-transfer approval/host scheduling; no
physical fit or whole-core selection is authorized by this narrow result.
