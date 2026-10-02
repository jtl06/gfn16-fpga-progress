# Pipelined carry bound setup

`genefer_carry_prefix_wide_pipe_v2` and
`genefer_carry_prefix_vector_pipe_v2` move the coefficient-bound calculation
into three registered stages within the existing reciprocal setup period.
They preserve the normalization pipeline, narrow reciprocal dividers,
module-scoped RAMs, and host interfaces of the corresponding pipe candidates.
Full-size simulation passed with no added operation clocks. A physical fit is
still required to establish the timing benefit and resource cost of this change.

## Arithmetic and validity proof

The accepted domain remains a power-of-two N from 2 through 65,536, with
`2*N+4 < b <= 1,000,000,000` and every signed 96-bit coefficient satisfying
`abs(a[i]) <= B = 2*N*(b-1)^2`. The full-width coefficient check remains before
any narrowing. Unsupported sizes, bases, or coefficients are explicitly rejected.

Let `u=b-1=L+2^16*H`, where L and H are its low and high 16-bit halves. Then
`u^2=L^2+2^17*L*H+2^32*H^2`. Each of the three partial products fits 32 bits;
their exact sum fits 64 bits even for arbitrary unsigned 32-bit u. Within the
accepted base domain, `u^2 < 2^60`. Shifting by `log2(N)+1 <= 17` produces
`B < 2^77`, safely within the existing 96-bit bound register.

The start edge captures `base-1` directly from the newly accepted input, not
the prior operation's base register. Subsequent stages use only this captured
value and the accepted size. Changes to input base while busy cannot affect B.
Reset and every idle start clear `bound_valid`, including rejected starts.
The arithmetic data registers need no reset because SPLIT can begin only after
the newly calculated bound has been marked valid. Simulation assertions also
compare this bound with the original full-width expression during SPLIT.

## Setup schedule

Edges below are relative to the accepted start edge. The existing BOUND clock
and 96 reciprocal clocks are unchanged.

| Edge | State before edge | Bound pipeline action |
|---:|---|---|
| 0 | IDLE | Capture the new base minus one; clear valid |
| 1 | BOUND | Register the three 16-by-16 partial products |
| 2 | RECIP round 0 | Register the exact 64-bit square |
| 3 | RECIP round 1 | Register the shifted 96-bit bound and set valid |
| 97 | RECIP round 95 | Enter SPLIT only if the bound is valid |

If validity is missing at the final setup clock, the controller terminates
with an error instead of consuming stale arithmetic. Reset during any setup
stage cancels the operation; after a full reload, a later start recomputes all
three stages for its own base and size. Invalid starts never enter BOUND.

## Measured cycles and integration contract

The measured busy-clock formula remains `2*ceil(N/LANES)+118`:

| N | Four lanes | Eight lanes | Sixteen lanes |
|---:|---:|---:|---:|
| 2 | 120 | 120 | 120 |
| 65,536 | 32,886 | 16,502 | 8,310 |

These counts exclude host loading and reading. They match pipe v1 and are two
clocks above the earlier unretimed narrow/module-memory variants, regardless
of N. Both new top modules preserve their respective scalar/vector port sets.
The vector candidate retains aligned logical base addresses, low-packed lane
zero, masked one-cycle reads, pulsed host errors, and the priority order vector
write, vector read, scalar write, scalar read. Invalid vector requests suppress
scalar fallback; all host requests are ignored while busy or starting.

No integrated core source selection was changed by this work. There is no
new achieved-frequency or complete-PRP speed claim from simulation alone.

## Validation evidence

The final report has status `passed` at
`/home/jtl/gfn-fpga-lab/agent-work/carry-pipe-v2/fpga/artifacts/bound-pipe-v1/report.json`.
All simulations ran on aethia with at most two build threads; this work did
not run Quartus.

Wide4/8/16 and vector4/16 each passed 3,330 normalizations in the AW16 suite
and 2,697 in the AW1 suite. Together these covered 30,135 normalizations,
545 explicit domain rejections, and 65 reset aborts. The two vector widths
checked 9,362,714 host transactions. An additional AW17 test rejected sizes
0, 17, 18, and 31 before completing a valid N2 operation.

Inherited coverage includes whole-integer Python oracle results at N65,536,
coefficient extrema, negative carry chains, canonical minus one, recurrence,
changing size and base without reset, small-N bank masking, malformed host
requests, and pipeline reset/drain cases. New tests abort at setup clocks
2, 3, and 4, then reload and run with bases 37, 604,832,956, and 1,000,000,000.
Repeated operations verify that no stale setup arithmetic survives.

Five injected setup defects were rejected: capturing the previous base,
omitting the cross product, omitting the high square, capturing the bound one
clock too early, and never asserting bound validity. The earlier divider and
normalization mutations remain documented in CARRY-NARROW-PROOF.md and
CARRY-PIPE-NOTES.md; this run specifically adds the five setup mutations.

Frozen RTL and dependencies:

- `genefer_carry_prefix_wide_pipe_v2.sv`: `17d3f703ca64d2cd1c58968a4fc3979eef692a25c5aae69fd12f577fc34a1aa1`
- `genefer_carry_prefix_vector_pipe_v2.sv`: `cd95a89e1b5a5221e7159c2492919e6607ecb6ec004fcd0ac782527c87ade3ea`
- `genefer_div_recip_narrow.sv`: `eef327cee81d41895a068b746a3715daba95d43bea919edbddf9b498ecfc38bf`
- `genefer_sp_ram.sv`: `b97d2f43db1b1e1aa60b9b7fc2b720af1e302bd5ff9e35854c89b30e5fb610df`
- `genefer_carry_transfer_tree.sv`: `b18e39ebcaf2a1b514e0b617170dc1491a576772fe94ff3cf55316feee09971c`
