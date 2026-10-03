Owner: main (record); stream_core; independent_review

# Advisor verification: protected C2 FIELD100 (seed 2) ACCEPTED. New record 95.8 s per test (two-context amortized) at 84.46 MHz (11.840 ns)

Advisor verification, 2026-10-03 ~04:40 UTC (9:40 PM PDT Oct 2). Covers [FIELD100 record request](replies/2026-10-02-FIELD100-record-request.md) and `results/throughput-20260929/trackS-protected-field100-promotion-v1/promotion-request-v1.json` (SHA-256 `3b17693a…`).

## What I checked
1. **All cited files:** SHA-256 recomputed, all match. The one path written repo-relative (`fpga/reference/stream27_protected_field100_physical.py`) also matches.
   - Source freeze `2bb4189d…`.
   - Full bundle `f5f0617d…`.
   - Numerical index (`OWN_TEN_NUMERICAL_SCOPED_FAULT_GATES_PASS…`).
   - Healthy native 2/100/1,000 ledger (`OWN_SOURCE_NATIVE2_100_1000_JOIN_PASS`).
   - Standalone source/numerical/ledger review (`PASS_SCOPED_FIELD100_SOURCE_OWN_TEN_TARGETED_AND_HEALTHY_LEDGER`).
   - Base-ENA and fold-component scoped reviews (PASS).
   - Standalone physical/clock review (`PASS_PHYSICAL_ONLY_SOURCE_BOUND`).
   - Both bracket receipts.
2. **Bindings:**
   - The numerical review binds the source freeze, which binds root `cf789d38…` and binder `84b14c2c…`. That binder is the same FIELD100 identity R13's freeze names as its `immutable_field100_parent`.
   - The physical review binds root `cf789d38…`, layout tree `361610d6…` and the pair-cycle figure.
   - Both bracket receipts share tree `361610d6…` and QDB inventory `3b02bba5…`.
3. **Bracket (AWS, 12 ns raw target, seed 2):**
   - **11.840 ns** (audit2 `2d6e507e…`): setup ≥ 0 at all four corners. Worst is **0.000 at Slow 100C with 0 failing endpoints, so there is no printed reserve.** Hold ≥ +0.007; MPW ≥ +5.323.
   - **11.838 ns** (audit1 `6eafa657…`): Slow 100C −0.002 with 1 failing endpoint.
   - No timing exceptions; same tool binaries.
4. **Own numerics:** ten own gates, including the 2,000-square long chain (1,000 per context) and the targeted fault/raw-origin contracts. Nothing is inherited from R9/R12.
5. **Projection, recomputed:**
   - FIELD100's own pair ledger **16,177,181,485 cycles**;
   - × 11.840 ns = **191.5378 s per pair = 95.7689 s per test amortized**;
   - **−9.4 % vs R9 (105.693 s)**, −46.4 % vs timing7 (178.632 s).
6. **Resources:** 318,615 / 383,577 needed / placed ALMs, 42,114 / 42,720 LABs (98.6 %), 1,916 M20K, 624 MLAB, 1,300 / 1,318 DSP.

## Decision
**ACCEPT protected C2 FIELD100 seed 2 (root `cf789d38…`) as the record: 95.8 s per test, two tests interleaved, internal compute-only, full on-chip checks.**

Exclusions as disclosed:
- **Throughput, not latency:** each test's latency is the pair time (191.5 s).
- **Clock margin:** **zero printed setup reserve** at 11.840 ns.
- **Board-level items not signed off:** virtual I/O; reset release.
- **Scope of the evidence:** this is a projection, not a measured full-sample PRP; host Gerbicz–Li is unimplemented.

**Fallbacks:** R9 (105.7 s) becomes the two-context fallback; timing7 (178.6 s) remains the single-test fallback. FIELD100 seed 3/4 layouts and R14-F need their own brackets/evidence to replace this.
