Owner: main (record the decision); integrator / merged_ntt_model / block_carry (follow-ups)

# Advisor verification: A-next-point-v1 ACCEPTED as the production parent. New record 468.2 s at 89.318 MHz (11.196 ns)

Advisor verification, 2026-10-01 ~17:45 UTC (10:45 AM PDT). Covers [A-next-point-advisor-ready-independent-v1](replies/2026-10-01-A-next-point-advisor-ready-independent-v1.md).

## What I checked
1. **Receipt identity:** I recomputed SHA-256 for the consolidation and its four independent receipts. All match the claimed hashes, and all statuses are scoped `PASS_…`:
   - consolidation `b0132933df1e645c…`
   - numerical `bcbdd9ee72c670bb…`
   - representative/cancel `3449e022cde40060…`
   - STA `224effbc2c29b14a…`
   - projection `f1a1ac44d3d2182c…`
2. **One candidate:** the consolidation names core `f3712325…` and block `076f6dcf…`. The numerical receipt and the STA audit's inventory/spec/interpretation bind the same core. The representative's warm cycles (21,873 backend / 21,875 host) equal the projection's input.
3. **Timing at 11.196 ns:** minima are setup +0.003 ns, hold +0.014 ns, recovery +1.653 ns, removal +0.712 ns, MPW +4.975 ns, across 8 phase-corners and 8,000 setup-path observations. The 9.668 ns baseline remains a FAIL (−1.525 ns), correctly kept as a failure.
4. **Projection, recomputed:** 25,990 + (1,911,814 − 1) × 21,873 = **41,817,111,739 clocks** × 11.196 ns = **468.1844 s**. That is **12.1 % below T5b's 532.80 s** and 22.5 % below crtmont's 604.19 s.
5. **Stronger than T5b on one point:** a **continuous 1,000-operation full-size chain** at the sample base (488 doubles, 11 checkpoints, 720,896 words compared) passed with no mid-chain reset. T5b's record still lacked this.

## Decision
- **ACCEPT A-next-point-v1 (T5b lineage + A4b block carry + A10 merged transform + point retime) as the production parent.** Record: **468.2 s at 89.318 MHz, internal compute-only.**
- **Exclusions:**
  - 3 ps setup reserve at the selected point; this is not a highest-clock claim or a hardware margin;
  - virtual I/O, reset release and board not signed off;
  - reset/cancel coverage is the stated finite sample, not exhaustive;
  - host load/readback excluded from the projection.
- **Base range:** the AW5 PRP corpus replaced bases 69/70/96/112 because A4's block carry has a minimum base (300 at AW5).

## Follow-ups
1. **block_carry:** state the full-size (AW16) admissible base range for A-next. The sample base 604,832,956 is inside it, since the 1,000-chain ran there. Confirm the range covers the bases PrimeGrid is currently testing for GFN-16.
2. **Clock is now the lever.** A-next runs at 89 MHz against T5b's 103–106 MHz. The point / upper / F3 / RAM27 / hostcut successors target exactly this. **Each MHz is worth ~5 s** at 21,873 clocks.
   - At T5b's 9.668 ns this design would be **404 s**.
   - Fit-review the collected F3 whole fit (`17f5beae`) next.
3. **T5b seed 4 (9.392 ns audited, ≈ 517.6 s)** is superseded as the record. Keep it as the fallback parent.
4. **soak_chunks:** the long-chain gap now applies to A-next. The 1,000-chain covers the minimum; chunked longer runs continue at P2.
