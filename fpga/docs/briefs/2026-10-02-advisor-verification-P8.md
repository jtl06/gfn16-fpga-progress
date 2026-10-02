Owner: main (record); stream_core

# Advisor verification: streaming P8 (canonical-pipeline) ACCEPTED. New record 408.0 s at 78.04 MHz (12.814 ns)

Advisor verification, 2026-10-02 ~00:25 UTC (5:25 PM PDT Oct 1). Covers [S4-P8-canonical-record-advisor-request](replies/2026-10-02-S4-P8-canonical-record-advisor-request.md).

## What I checked
1. **Independent review** `s4-p8-canon1-promotion-independent-v1.json`: SHA-256 recomputed = `36dd77ecf5978799…`, status `PASS_internal_compute_only_evidence_ready_for_advisor_verification`.
   - It binds candidate root `140e2b30…` (also in the owner handoff).
   - It binds the audit5 receipt by hash (`00ec056e1023007b…`, recomputed).
   - It records both the 12.814 ns pass and the 12.812 ns fail (−0.001 ns).
2. **Timing at 12.814 ns:** four-corner minima setup +0.001, hold +0.014, MPW +5.757 ns, zero failing endpoints. Reset recovery/removal have no paths, which is not counted as a pass.
3. **Own qualification:**
   - 8 AW5 PRPs (floor 172);
   - full-size 9-operation/two-image gate (131,072 signed96 words vs T5b and the reference);
   - continuous 100 and **uninterrupted 1,000** (500 doubles, one reset/load);
   - minimal cancel/reset/reload and canonical-cell negatives.
4. **Projection, recomputed:**
   - 680,315 + (1,911,814 − 1) × 16,653 = **31,838,102,204 cycles** × 12.814 ns = **407.9734 s**.
   - The once-per-test canonicalization and copy are inside the 680,315 cold cycles.
5. **Comparison:** **−10.0 % vs F3 (453.48 s)** and **−32.5 % vs crtmont (604.19 s)**.

## Decision
- **ACCEPT streaming P8 canonical-pipeline (root `140e2b30…`) as the production parent and record: 408.0 s at 78.04 MHz, internal compute-only.**
- **Exclusions:**
  - 1 ps setup reserve;
  - virtual I/O (193 inputs / 797 outputs unconstrained);
  - reset release, board and exhaustive fault coverage not signed off;
  - host load/readback excluded;
  - base floor 172.
- F3 stays as the Track A fallback.
- **This is the first streaming record.** Next steps:
  - the r75/r76 A–E bundle (~100 MHz → ~318 s);
  - P16 route-first (≥ 70 MHz → ~231 s);
  - two contexts.
