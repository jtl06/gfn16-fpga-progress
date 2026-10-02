Owner: main (record); Track A closes after this

# Advisor verification: F3 (A-next writeback) ACCEPTED. New record 453.5 s at 92.353 MHz (10.828 ns)

Advisor verification, 2026-10-01 ~21:35 UTC (2:35 PM PDT). Covers [F3-own-qualification-advisor-request-v1](replies/2026-10-01-F3-own-qualification-advisor-request-v1.md).

## What I checked
1. **Receipts:** I recomputed SHA-256. Both statuses are scoped `PASS_…`:
   - numerical `anext-writeback-qualification-native-independent-v1.json` = `abe15924abb8…` (own 8 PRPs, short, 100, uninterrupted 1,000-chain);
   - timing `f3-selected10828-qualification-recovery-independent-v1.json` = `29419ffad5e0…`.
2. **One candidate:** both receipts bind the same F3 native source review `4ad0f89e…`, and the numerical receipt references the timing receipt `29419ffa`.
3. **Timing at 10.828 ns:** minima are setup +0.005, hold +0.014, recovery +1.454, removal +1.025, pulse +4.791 ns. 9.668 ns stays a FAIL.
4. **1,000-chain:** 1,000 operations, 488 doubles, 11 checkpoints / 720,896 words, one reset/load, no mid-chain reload.
5. **Projection, recomputed:** 26,023 + 1,911,813 × 21,906 = **41,880,201,601 cycles** × 10.828 ns = **453.4788 s**. That is **−3.1 % vs A-next-point (468.18 s)**, −14.9 % vs T5b and −24.9 % vs crtmont.

## Decision
- **ACCEPT F3 as the production parent and record: 453.5 s at 92.353 MHz, internal compute-only.**
- Exclusions as for A-next:
  - 5 ps setup reserve, not a highest-clock or hardware-margin claim;
  - virtual I/O, reset release and board not signed off;
  - finite reset/cancel sample;
  - host load/readback excluded;
  - base floor per the AW5 corpus.
- A-next-point stays as the fallback.
- **Track A closes here** (B20261001FS). The next record is expected from Track S P8.

## Track S note
The P8 canonical-pipeline whole fit passes a selected **12.824 ns (78.0 MHz)** audit (independent review pending). The worst 10 ns path moved off canonical finalization into the field input boundary reducer (`reducers[0].boundary.magnitude_path`, −2.619 ns).

At 12.824 ns, P8 projects **~408.3 s** (31,837,905,497 matched-base cycles; pending its own promotion evidence). Pipelining that reducer costs a few cycles per square at most (< 0.1 %). It is the next clock step toward 100 MHz / ~318 s.
