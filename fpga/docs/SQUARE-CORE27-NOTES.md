# Isolated atomic27 square core

`genefer_square_core27.sv` is derived from the frozen core snapshot SHA256
`c6dad925fe58c17074722aabfee1d757232552465ecf0026fcc078373e08d5db`, extracted from
`core-host64-full-v1/source-snapshot.tar.gz`. It does not consume the current
fusion-working core. The new `genefer_ntt_banked27_host_engine.sv` preserves the
frozen host-wrapper arbitration and quarter mapping, selecting the native27
child explicitly rather than merely changing parameters on the old31 child.

Only two profiles are supported: 16 NTT lanes /16 IO lanes, and 64 NTT lanes /
16 IO lanes. Both use sixteen conversion, CRT, and frozen v2 carry lanes. Cached
four-phase roots remain; generated roots, input-Montgomery fusion, streamed CRT
carry, and the newer carry-retiming candidates are intentionally absent.

## Atomic arithmetic profile

The Montgomery radix is **2^32**, not2^27. Canonical words remain32 bits.

| Field | P | Positive Q=P^-1 mod2^32 | R² modP | Generator |
|---|---:|---:|---:|---:|
| 1 |104857601|4190109697|45971250|3|
| 2 |69206017|4225761281|50081300|5|
| 3 |67239937|4227727361|63576045|10|

All three moduli support a primitive negacyclic root for every N=2..65536.
Their CRT modulus is487945222748036195811329, exceeding twice the largest
doubled coefficient bound131071999737856000131072 at N65536/base1e9.
The centered reconstruction therefore remains unique throughout the supported
integer-convolution domain; this is not an approximate or probabilistic CRT.

The core switches P/Q/R²/generators, native sparse27 NTT, and centered CRT27
together. A private root-streamer clone in the same new file preserves the
archive's exact four-stage feedback and phase formats: phases0/1/2 contain
R-scaled roots, phase3 contains ordinary inverse-twist/N roots. Its three small
root-recursion multipliers still use the frozen generic32 helper with canonical
27-bit operands; conversion and NTT use the sparse27 helper explicitly.

## Conversion and control contracts

Legal radix digits can exceed P. The complete signed96 carry-memory row is
validated against the latched base before any word enters a reducer. Every
active word must be -1 or satisfy0<=digit<base; a bad word suppresses the whole
row. The original signed32 bit pattern then enters the four-stage checked
`genefer_digit_reduce27_pipe`. Its canonical residue feeds the four-stage sparse
Montgomery converter with R². There is no raw27 truncation, undocumented
noncanonical Montgomery input, or use of R=2^27. Any reducer error quarantines
the operation and invalidates the root cache.

Converted results are addressed by ordered valid output count, as in the
ancestor. Consequently conversion costs `ceil(N/16)+9` clocks, four more than
the old path, without a new fixed-delay address assumption. The last NTT write
still precedes a separate START edge. CRT retains its61-stage/II1 contract and
the existing carry v2 protocol remains unchanged.

The carry domain is unchanged: `2*N+4 < base <= 1,000,000,000`. Unsupported
arithmetic widths reject and quarantine. Host load/read/start priority, busy
suppression, signed special-minus-one digits, immediate restart after done,
and no-host repeated-square operation retain their original contracts. Reset
or an error requires reloading all digits; reset clears all root-cache validity.
Successful cache contents can survive base changes because roots depend on
the fixed N and field profile, not the candidate base.

## Verification scope

`square_core27_regression.py` is separate from the frozen/current core harness.
It checks the exact field constants against independently calculated radix32
identities, primality/root order, and the CRT bound; then uses the frozen
divide-and-conquer big-integer oracle for whole squareDup results. It exercises
AW1/5/16 at both supported lane widths, max base, reduction boundaries above P,
special-1, doubled and repeated squares, phase reset aborts, warm/cold cache
accounting, changed bases, and no-host chains. Baseline models retain default
compiler optimization; mutation-only models use explicitly recorded-O0 to
reduce rebuild cost, never to reuse a correctness result.

Targeted faults include raw27 truncation, wrong radix conversion, lane mixing,
root order/phase, coefficient doubling/addressing, runtime-base equality,
cache lifetime, immediate restart, reducer-error propagation, wrong R², a
non-atomic old31 CRT substitution, and a64/16 read-quarter error. All tests run
only on aethia with two build workers and a6GiB per-process address-space cap.
Output directories must be fresh and source hashes are recorded.

## Completed gate and measured cycles

The completed report is
`agent-work/square-core27/fpga/artifacts/core27-final-v1/report.json` on aethia,
SHA256 `9fbeb49234080d32b8c91d5cbf5be28cf7fbd14a5010537bcb4586e9cbfdf37e`.
Its 48 recorded steps cover 2,168 matrix squares (AW1/5/16 at both widths),
2,136 matrix readbacks, 36 reset aborts, an additional 12-square AW7 matching
control, and 15 distinct faults. The quarter fault has two rejection executions,
not two distinct mutants. Unsupported 32-lane configuration rejects and
quarantines correctly.

The original combined full-N 64-lane test exceeded the unchanged 600-second
per-command limit. `core27-full-v1/report.json` remains failed. Recovery split
the exact original vector stream at its resetting LOAD boundary into five- and
seven-square segments; it did not split LOAD_KEEP/no-host chains, increase
limits, regenerate oracle values, or alter the preserved executable. Every
original command and case ID is accounted for exactly once. Both segments
passed (321.16 and 353.54 seconds in that run).

The recovery report also remains failed: its last mutant correctly triggered
`residue mask skew`, which the rejection parser had omitted from its diagnostic
allowlist. The separate finalization gate verifies those identities, runs an
unmutated AW7 control against the same quarter vectors, and reruns the frozen
mutant accepting only that precise assertion. No RTL or prior report was edited
to produce the final passed report. The original run did not record an
executable hash; recovery explicitly records that limitation and pins the
preserved successful-build executable before and after its new executions.

Per-profile views are in `artifacts/normalized-full-v1/core27-16-16-report.json`
and `core27-64-16-report.json`, with 1,084 metrics each and source-report
provenance. They do not claim independent reruns.

| N=65,536 profile | Conversion | NTT | CRT | Carry | Warm square | Cold square |
|---|---:|---:|---:|---:|---:|---:|
| 16 NTT / 16 IO | 4,105 | 78,111 | 4,158 | 8,312 | 94,686 | 356,838 |
| 64 NTT / 16 IO | 4,105 | 19,743 | 4,158 | 8,312 | 36,318 | 298,470 |

Cold fill adds 262,152 clocks in either profile. These are simulator-measured
clock counts, not execution-time estimates or a placed-and-routed clock claim.

Frozen implementation identities:

- Core: `47f61c263ddcfe6f707ab65fdaadf5a412528692f99a3c9bd3dc123137b435ce`.
- Host wrapper: `d431f5193c45ff6128a15d7dcb353a5cc8f49f2b9b3fa6ec40f0c0d9f4e4851e`.
- Bench: `98f857f0eed900a176e67ed7f31e8ecb3c71710d2929368ad2ddd082ad67a632`.

No DSP, RAM, clock, or end-to-end speed benefit is claimed from simulation.
Native27 still uses32-bit host/cache words, so smaller arithmetic operands do
not by themselves imply less root/data RAM. Physical fitting is a separate gate.

## Full64 physical failure, 2026-09-30

The original cached atomic27 whole64 probe terminated at07:36UTC with actual
Quartus exit3 after4h04m wall time. Routing failed from congestion (16618,
25111,170143), not the six-hour job limit or VM memory exhaustion. The retired
outer timeout wrapper's137 is not the compiler status; the preserved
`timeout-extension-6h.json` records the actual child exit3.

Archive: `results/throughput-20260929/core27-ntt64-gcp-fit/`. All13 RTL hashes
match the manifest. Compressed evidence SHA256:
`605d6a7c7811e1a8e8b8b400980cedaee3902a00fb57e57f29923db44c781bbb`.
The failed placement reported408681 raw ALMs,394636 packing-adjusted ALMs,
1090 raw DSPs,836 adjusted DSPs and30749696 RAM bits. These are diagnostics
from an unrouted design, not usable fitted resources or a clock/throughput claim.

This result favors reducing root-routing/storage pressure in the64-lane
architecture. It does not establish failure of the separate precision-carry,
pair-CRT or prefetch whole-core candidates.
