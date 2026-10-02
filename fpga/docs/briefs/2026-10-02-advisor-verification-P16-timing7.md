Owner: main (record); stream_core

# Advisor verification: P16 timing7 ACCEPTED. New record 178.6 s at 90.55 MHz (11.044 ns)

Advisor verification, 2026-10-02 ~03:20 UTC (8:20 PM PDT Oct 1). Covers [P16-timing7-record-advisor-request](replies/2026-10-02-P16-timing7-record-advisor-request.md).

## What I checked
1. **Independent receipt** `s4-p16-timing7-promotion-independent-v1.json`: SHA-256 recomputed = `ecd1b7534400813b…`, status `PASS_required_timing7_own_source_numerical_layout_clock_projection_evidence…`.
   - It binds root `0011468e…`.
   - It binds the audit4 and audit5 receipts by hash (recomputed).
   - It records the 11.044 ns pass, the 11.042 ns fail and the cycle ledger.
2. **Timing at 11.044 ns:** setup +0.001, hold +0.004, pulse +4.878 ns; four corners; no SDC exceptions.
3. **Own numerics** (not inherited from the baseline):
   - PRPs, short, 100, AW8 and faults;
   - **an uninterrupted 1,000-operation full-size chain**: 500 doublings, 9,119,566 cycles, words equal to the native reference.
4. **Projection, recomputed:** 668,026 + 1,911,813 × 8,460 = **16,174,606,006 cycles** × 11.044 ns = **178.6323 s**. That is **−12.3 % vs P16 baseline (203.68 s)** and **−70.4 % vs crtmont (604.19 s)**.
5. **Resources:** 318,091 / 382,948 needed / placed ALMs, 41,959 / 42,720 LABs (98.2 %), 605,823 registers, 1,910 M20K, 1,300 / 1,318 DSP.

## Decision
- **ACCEPT P16 timing7 (root `0011468e…`) as the production parent and record: 178.6 s at 90.55 MHz, internal compute-only.**
- Exclusions:
  - 1 ps setup reserve;
  - virtual I/O;
  - reset release and board not signed off;
  - 98.2 % LABs.
- The P16 baseline (203.7 s) becomes the fallback.

**Next:** two contexts on this source (~89 s effective), then the next clock round toward 100 MHz (~162 s).
