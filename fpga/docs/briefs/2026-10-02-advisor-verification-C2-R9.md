Owner: main (record); stream_core; independent_review

# Advisor verification: protected C2 R9 (seed 2) ACCEPTED. New record 105.7 s per test (two-context amortized) at 76.51 MHz (13.070 ns)

Advisor verification, 2026-10-02 ~21:40 UTC (2:40 PM PDT). Covers [advisor-request-protected-R9](replies/2026-10-02-advisor-request-protected-R9.md) and `results/throughput-20260929/trackS-c2-protected-r9-promotion-v1/promotion-request-v1.json` (SHA-256 `78dd2a4e…`).

## What I checked
1. **All 13 cited files:** SHA-256 recomputed, all match.
   - Production bundle `01220c6e…`.
   - Numerical index `3ce202af…` (`OWN_TEN_NUMERICAL_AND_SCOPED_FAULT_GATES_PASS…`).
   - Closure overlay `f284ff2e…`.
   - Healthy ledger `86de887b…` (`OWN_SOURCE_NATIVE_CALENDAR_JOIN_PASS`).
   - Eight-job scoped review `c3b53755…` (PASS).
   - Separate barrier review `a578d009…` (PASS).
   - Clock review `38c3ebd9…` (`PASS_PHYSICAL_BRACKET_ONLY_FOR_ADVISOR`, `no_timing_exceptions: true`, uncertainty 0.030 ns).
   - Package basis, both audit receipts, fit summary and fit report.
2. **Bindings:** root `33a89e3b…` is bound by the bundle, index, ledger, scoped review, clock review and basis. Layout tree `ea15cb87…` is bound by the clock review, basis and both audits; the QDB inventory is the same for both.
3. **Bracket (seed 2, 12 ns raw target, Azure):**
   - **13.070 ns** (audit3 `eb373d08…`): setup ≥ 0 at all four corners (worst +0.001, Slow 100C), 0 failing endpoints; hold ≥ +0.005; MPW ≥ +5.931.
   - **13.068 ns** (audit4 `b2d6fb04…`): Slow 100C −0.001 with 1 failing endpoint.
4. **Own numerics:**
   - full normal;
   - 100 and 1,000 per context;
   - owner/descriptor/reset contracts;
   - accelerated wrap;
   - cache;
   - output-comparator cross-talk.

   The review is partitioned: the eight source jobs and the two authored registered-error/barrier fixtures were reviewed separately.
5. **Projection, recomputed:**
   - pair ledger **16,173,357,858 cycles**: R7's formula + 2, for the documented +1 publication edge per job;
   - × 13.070 ns = **211.3858 s per pair = 105.6929 s per test amortized**;
   - **−12.5 % vs R7 (120.815 s)**, −40.8 % vs timing7 (178.632 s).
6. **Resources:** 312,824 / 376,452 needed / placed ALMs, 42,023 / 42,720 LABs (98.37 %), 590,951 registers, 1,916 M20K, 1,300 / 1,318 DSP.

## Decision
**ACCEPT protected C2 R9 seed 2 (root `33a89e3b…`) as the record: 105.7 s per test, two tests interleaved, internal compute-only.** It is a protected build: full on-chip checks, no lean.

Exclusions as disclosed:
- **Throughput, not latency:** each test's latency is the pair time (211.4 s).
- **Clock margin:** 1 ps setup reserve.
- **Board-level items not signed off:** virtual I/O; reset release; latch selector unsupported.
- **Wrap and cache scope:** the wrap test is accelerated (timestamp aliases); cache protection is eventual duplicate-abort only.
- **No host error check yet:** host Gerbicz–Li is unimplemented.

**Fallbacks:** R7 (120.8 s) becomes the two-context fallback; timing7 (178.6 s) remains the single-test fallback. No R10/R11/R12/lean qualification transfers.
