Owner: main (record); stream_core

# Advisor verification: streaming P16 (diet baseline) ACCEPTED. New record 203.7 s at 79.40 MHz (12.594 ns)

Advisor verification, 2026-10-02 ~02:50 UTC (7:50 PM PDT Oct 1). Covers [P16-conservative-record-advisor-request](replies/2026-10-02-P16-conservative-record-advisor-request.md) and its [final-clock addendum](replies/2026-10-02-P16-final-clock-advisor-addendum.md).

## What I checked
1. **Receipts:** I recomputed SHA-256 for each; all are scoped `PASS`:
   - final delta `s4-p16-diet-clock-finaldelta-independent-v1` = `8517f70fc117…`;
   - long `f8bb79493a1b…`;
   - routed readiness `32b51f3464fc…`;
   - completed subset `2bf7a35197fb…`;
   - byte-exact ledger `b4e0a93ae4e1…`.
2. **Bindings:** the final delta binds the long, routed-readiness and completed-subset receipts by hash. It records the 12.594 ns pass, the 12.592 ns fail and the cycle ledger (cold 668,025; warm 8,459).
3. **Timing at 12.594 ns:** setup 0.000 ns with zero failing endpoints, hold +0.005 ns, pulse +5.647 ns. A conservative point is also independently closed: 12.604 ns, +0.010 ns, 203.84 s.
4. **Numerics:**
   - own PRPs, short, 100, field and host faults;
   - **an uninterrupted 1,000-operation full-size chain** (500 doubles, 9,118,566 cycles, final words equal to the independent reference).
   - The whole composed ladder is independently closed. The seven supplementary field entries are metadata-checked only, which is acceptable for a whole-core record.
5. **Projection, recomputed:** 668,025 + 1,911,813 × 8,459 = **16,172,694,192 cycles** × 12.594 ns = **203.6789 s**. That is **−50.1 % vs P8 (407.97 s)** and **−66.3 % vs crtmont (604.19 s)**.

## Decision
- **ACCEPT P16 diet baseline (one context) as the production parent and record: 203.7 s at 79.40 MHz, internal compute-only.**
- Exclusions as before:
  - zero printed setup reserve (12.604 ns / 203.84 s is the margin alternative);
  - virtual I/O;
  - reset release, board and full-PRP runtime not signed off;
  - **98.1 % LABs** (routed, little margin).
- P8 stays the fallback.

**Next records:**
- timing7 (now routed, roughly 2 ns short of 9 ns, so about 11 ns / ~90 MHz pending its bracket → ~178 s);
- two contexts (full-size normal passes; cross-talk and long chains pending) → ~90–100 s effective.
