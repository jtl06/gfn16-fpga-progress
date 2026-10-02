# Independent square-core review

Read-only review of `genefer_square_core.sv`, its root/NTT/CRT/carry interfaces,
`square_core.cpp`, and `square_core_regression.py`. No functional RTL defect
was identified. This is a source/contract review, not a physical-timing result
or an independent rerun of the integrated simulation suite.

## Handoffs

- **Final root write precedes NTT start.** The root generator registers its
  final `root_valid` and `done` together. At the following edge, the wrapper
  is still in `ROOT_WAIT`: root RAM writes the final address, and the wrapper
  changes state to `NTT_START`. The NTT samples `start` on the next edge.
  Thus even N=2 gets the last write before its transform starts.
- **Final conversion write precedes roots/transform.** Conversion output and
  write counter are consumed while still in `CONVERT`. The last NTT operand
  write commits on the transition to `ROOT_START`; root generation starts at
  the following edge.
- **Final CRT write precedes carry start.** In `RESIDUES`, a valid coefficient
  writes the old `write_count` address. On the edge writing address N-1 the
  wrapper enters `CARRY_START`. Carry samples `start` only on the next edge,
  when its RAM load signal is off. No final-coefficient write is dropped.
- Issue/write counters are AW+1 bits and can represent N itself; address
  truncation happens only where enable/count guards ensure an address <N.

## Reuse, reset, and reads

- A successful start reinitializes both counters, step, base, doubling bit,
  and phase counters. The controller waits for completed carry before exposing
  idle/results. The next run converts those retained canonical carry digits.
- Root/NTT pipelines drain before their `done` pulses; the CRT receives exactly
  N residues, and its final accepted result is consumed before carry starts.
  There is therefore no live prior-operation transaction at the next start.
- Host requests are gated by `IDLE && !start`. Internal carry reads are only
  issued in `CONVERT`; public `read_valid` is also gated by `IDLE`, preventing
  internal conversion reads from leaking to the host. Carry handles concurrent
  read/write with write priority.
- Reset cancels all valid pipelines and returns controllers to idle without
  resetting RAM. The documented full reload after reset/error is essential.
  Reported failures enter `FAILED`, preventing accidental reuse before reset.
- Fixed lane latency is a correctness dependency: all field lanes must accept
  simultaneously and retain their current equal latencies. Existing simulation
  checks reject conversion/residue/NTT-done/root-done lane skew. If lanes become
  independently stalled in future, the present reduction-AND handshakes must
  be replaced with per-lane completion tracking.

## Arithmetic range

For N<=65536 and 2<=b<=10^9, every legal ordinary input digit is below every
field prime. Special digit -1 maps exactly to `P-1`; multiplying by R² converts
the ordinary residue to Montgomery form. Each negacyclic square coefficient
is a signed sum of N products, hence its magnitude is bounded by
`N*(b-1)^2 <= 65536*(10^9-1)^2 < 6.554e22`. This is far below half the
three-prime product, approximately `4.534e27`, so centered CRT uniquely recovers
the integer coefficient rather than merely an ambiguous congruence class.
Optional doubling remains below `1.311e23`, safely inside carry's `2^94`
coefficient bound and signed-96-bit arithmetic. The 96-bit shift by one is safe.

The implementation accepts -1 in any digit position, while documentation
primarily describes canonical `[-1,0,...]`. This broader accepted input set does
not invalidate the bound or arithmetic, but strict canonical-vector validation
would require an additional whole-vector condition if desired later.

## Actionable test coverage follow-ups

1. At review time every `LOAD` command called reset. Recurrent `RUN` commands
   already test retained-result reuse, but not successful completion followed
   by a full reload and a changed radix without reset. Requested a no-reset
   load command/scenario alternating base 2, 604832956, and 10^9 from the owner.
2. A read immediately followed by start without an intervening idle tick would
   directly exercise suppression of the previous host read-valid token. Source
   gating appears correct, but the current harness deliberately inserts an
   idle tick after its result reads.
3. Full-size all-max digits at base 10^9 would exercise the largest supported
   coefficient bound. Existing full-size scenarios use random digits and -1
   at base 604832956; small-size scenarios already cover base 10^9/max digits.

These are coverage improvements, not observed correctness failures. Findings
were sent to the owning agent and parent; no shared RTL/test files were edited
by this review.
