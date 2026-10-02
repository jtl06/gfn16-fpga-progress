# Checked reduction of radix digits to 27 bit fields

`genefer_digit_reduce27_pipe` is a separate four-stage, initiation-interval-one
converter from ordinary 32-bit radix digits to canonical ordinary residues.
It supports the experimental fields 104,857,601, 69,206,017, and 67,239,937.
It is not a Montgomery multiplier and does not change any frozen NTT, carry,
CRT, or integrated-core source selection.

## Input and response contract

The input ports are `clk`, active-low `rst_n`, `in_valid`, unsigned 32-bit
`digit`, and a configurable-width `payload_in`. Every clock with in_valid
accepts one request; there is no downstream backpressure. A request sampled at
edge t produces its response at edge t+3, including consecutive requests.

Only ordinary words from zero through 999,999,999 and the special word
`32'hffffffff` are accepted as valid digits. The latter represents signed -1
and maps to P-1. Every other full 32-bit word produces an `out_error` response,
never an `out_valid` residue. The two response flags are mutually exclusive.
The payload accompanies either kind of response. The residue register holds
its previous value on errors and bubbles; the payload holds on bubbles.
Reset clears both flags, cancels all pending requests, and resets the output
residue and payload to zero.

The input guard checks the full 32-bit word before a narrowed arithmetic
register can update. Invalid high-bit patterns cannot alias smaller valid
digits through truncation. This helper deliberately does not know the runtime
radix: the caller must still check that each ordinary digit is below its
latched base. For a vector group, the core should reject the whole group before
launching any reducer lane if any digit fails that core-level check.

## Four conditional subtractions

The parameter contract is `P < 2^27` and `16*P > 999999999`, equivalent to
`62,500,000 <= P <= 134,217,727`. Primality is not needed for reduction itself.
All three selected primes satisfy the contract. An elaboration-time simulation
guard rejects unsupported parameters; the same constant condition also gates
hardware input legality, so unsupported parameters cannot produce valid
residues even if simulation assertions are omitted for synthesis.

Normalize the special minus-one word to P-1, and call the resulting unsigned
integer x. The domain guarantees `0 <= x < 16*P`. Each stage subtracts its
constant once if the current value is at least that constant:

| Stage | Conditional subtraction | Proven result range | Stored width |
|---:|---|---|---:|
| 1 | 8P | 0 through 8P-1 | 30 bits |
| 2 | 4P | 0 through 4P-1 | 29 bits |
| 3 | 2P | 0 through 2P-1 | 28 bits |
| 4 | P | 0 through P-1 | 27 bits |

Each subtraction preserves the residue modulo P. Halving the upper bound at
each stage proves both the final canonical result and every narrowing step.
The 27-bit result is zero-extended onto its 32-bit output port. There are no
RTL multiplication, division, or remainder operations in this datapath.
Physical resource counts and achieved frequency still require synthesis/fit;
no integrated throughput gain is claimed from this standalone implementation.

Good/error metadata and payloads traverse the same four-stage schedule. Only
good metadata enables arithmetic data updates. Unreset intermediate registers
are safe because reset clears the metadata that could consume their contents.
The result register updates only for a valid residue, while payload can also
update for a quarantined error response.

## Validation evidence

The final source-hashed report has status `passed` at
`/home/jtl/gfn-fpga-lab/agent-work/digit27/fpga/artifacts/digit27-v2-final/report.json`.
All simulation ran on aethia with two build workers inside a 6 GiB, no-swap,
two-CPU systemd scope. No Quartus or integrated-core run was performed here.

The independent Python modulo oracle supplied 24,291 clock records for each
selected field. Across the three fields, the scoreboard verified 46,484
canonical residue responses, 14,770 explicit invalid-word error responses,
717 reset-canceled requests, and 26,101 output-hold checks. It checked payload
alignment on both response classes and the exact edge-t to edge-t+3 latency.

Coverage includes zero, P-1, every relevant multiple of P and its two adjacent
values on either side, all four conditional-subtraction thresholds, the maximum
ordinary digit, values immediately above it, high-bit alias patterns, and
special minus one. Random ordinary/full-32-bit words are mixed with bubbles,
consecutive errors and successes, resets at each pipeline occupancy depth,
and long final idle periods. Unsupported P values 0, 62,499,999, and 134,217,728
were all rejected by the explicit parameter assertion.

Eleven mutations were tested separately for all three fields, and all 33 were
rejected: each of the four threshold equalities, the minus-one mapping,
full-word validation, valid latency, payload alignment, error/valid exclusion,
reset cancellation, and holding the residue on errors. Peer review found no
width, arithmetic, quarantine, or metadata-alignment issue.

The first report stopped only because P=0 generated constant-unsigned compiler
warnings before the explicit parameter assertion could run. The final runner
suppresses that one warning class solely for deliberately unsupported
parameters. All ordinary field builds retain normal warnings, and the RTL is
identical between both runs.

## Implementation identity

The module has no RTL dependencies. Frozen source SHA256:
`61e14bb13c2dbcc13b5030756578a0d0358269beb24fb207a5641b98795883e8`.
