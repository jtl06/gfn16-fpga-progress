# Retimed exact carry division

This isolated candidate splits the remaining carry-divider correction path into registered stages. It preserves the frozen narrow divider and streaming-carry implementation, and is not selected by the square core. The physical motivation is the parent-measured carry-stream-pipe path from `first_div.lows[4][3]` to `unsigned_q[47]`: 6.486 ns through remainder subtraction, correction comparison and a wide quotient increment. That frozen four-lane fit reached 159.69 MHz. No fit or clock improvement is claimed for this new candidate until physical evaluation.

## New modules and unchanged dependencies

`genefer_div_recip_narrow_pipe` has the same ports and magnitude parameters as the frozen narrow helper, but ten stages rather than seven. A transaction accepted at edge k produces its response immediately after edge k+9, with initiation interval one. `genefer_carry_prefix_stream_divpipe` instantiates the new helper twice per lane. All stream ordering, full-width input guards, intermediate RAM, five-state scans, wrap handling, carry feedback and final digit commit logic remain unchanged.

The new carry top reuses `genefer_carry_stream_scan_pipe` from the frozen `genefer_carry_prefix_stream_pipe.sv` file. Include that file for the helper definition, but explicitly elaborate the new top; the old carry is not instantiated. The other dependency is frozen `genefer_sp_ram.sv`. The frozen source hashes remain `9838c6852cac57f7901f8b57dcbb4ee11b7fa129ef86e40158d67cc789b06e5e` for stream_pipe and `eef327cee81d41895a068b746a3715daba95d43bea919edbddf9b498ecfc38bf` for the old narrow divider.

## Pipeline schedule

| Stage | Registered operation |
| --- | --- |
| 0 | Input absolute magnitude, low word and sign |
| 1 | Existing narrow-limb reciprocal partial products |
| 2 | Existing per-limb product row sums |
| 3 | Existing high-product quotient estimate |
| 4 | Low32 product of estimate and base |
| 5 | Provisional remainder subtraction; delayed estimate |
| 6 | Correction comparison and candidate remainder subtraction, in parallel |
| 7 | Isolated wide quotient increment and remainder selection |
| 8 | Sign negation, negative-fraction flag and signed remainder |
| 9 | Negative floor adjustment, final remainder and payload |

The comparison no longer feeds a wide increment in the same cycle as the provisional subtraction. Sign negation and the negative-floor decrement are also separated. No multiplier operand was widened and no new multiplication was added. Registers increase; DSP counts and timing still require a fit.

Valid and payload pipelines both have ten stages. Reset clears all valid eligibility immediately; data/payload registers retain the frozen helper's free-running behavior and are unspecified when `out_valid` is false. Inputs can contain bubbles, with no ready/backpressure interface.

## Exact arithmetic and bounds

Let `R=2^96`, `c=floor(R/b)`, `m=abs(value)<2^W`, and `W` be 77 or 47. The caller supplies `2<=b<=1,000,000,000` and the exact reciprocal. The estimate `e=floor(m*c/R)` is either `floor(m/b)` or one less: it cannot overestimate, and the reciprocal error is smaller than `m/R<1`. Consequently `delta=m-b*e` lies in `[0,2*b)`, strictly below `2^31`.

The low32 subtraction `(m_low32-(e_low32*b)_low32) mod 2^32` therefore recovers the complete nonnegative delta, not merely an ambiguous residue. One comparison `delta>=b` exactly selects whether to increment e and subtract b. For a negative input, the final quotient is `-q-[r!=0]`, and the remainder is zero when r is zero, otherwise `b-r`. This is Euclidean floor division, not truncation toward zero.

The input's most-negative signed value `-2^W` remains outside the magnitude contract and is checked by a simulation assertion, as in the frozen helper. The new helper also asserts the documented base range on valid inputs. These are interface diagnostics, not synthesizable error responses. The carry top retains its full signed96 row-wide bound check before either narrowed divider can receive a coefficient; its runtime domain remains `b>2*N+4`, `b<=1e9`, and `abs(coefficient)<=2*N*(b-1)^2`.

The first quotient bound is unchanged: `ceil(2*N*(b-1)^2/b)=2*N*(b-2)+1<2^47`, while the original coefficient bound is below `2^77`. Thus both narrowed input widths remain lossless after the existing full96 guard.

Base and reciprocal are not per-token payloads. They must remain stable for responses the caller intends to consume. During ordinary carry execution they are latched and stable. An invalid streamed row aborts the transaction; an immediate new-base restart may change configuration while abandoned old tokens drain, but the carry ignores those outputs and waits through its unchanged 97-clock setup before accepting new rows. Adding a global assertion that configuration could never change while any old valid bit remained would incorrectly prohibit this existing recovery protocol, so no such assertion was added.

## Measured carry cycles

Each divider adds three clocks; the two-divider chain adds six once per operation, not per row. With G=`ceil(N/LANES)` and K=`log2(LANES)`, measured no-bubble cycles are:

`2*G + 131 + 3*K`

Producer bubbles add exactly one clock each. Setup remains 97 clocks, stream acceptance remains one legal row per cycle once ready, and done still follows the final actual digit RAM write.

| LANES | N65,536 frozen stream_pipe | New divider pipeline | Added clocks |
| --- | ---: | ---: | ---: |
| 4 | 32,899 | 32,905 | 6 |
| 16 | 8,329 | 8,335 | 6 |

## Validation

The initial divider oracle checked 48,425 magnitude77 results and 51,945 magnitude47 results against Python whole-integer `divmod`, with 3,300 reset-canceled tokens and eight malformed magnitude/base checks. Inputs include signs, exact multiples, neighboring values, limb boundaries, maximum magnitudes, random radices, bubbles, no-reset base changes after drain, and resets at every pipeline age. The magnitude47 set additionally checks 3,520 first-quotient samples derived independently from every supported N and four representative radix choices.

Both four- and sixteen-lane carry candidates passed initial AW16/AW1 arithmetic, malformed-stream, host-arbitration, no-reset and immediate new-base recovery suites. The initial overall gate correctly remained failed because the copied AW17 recovery bench still expected the old 133-cycle count rather than 139. That test-only expectation was corrected; RTL was unchanged. The initial report is preserved at `/home/jtl/gfn-fpga-lab/agent-work/carry-divpipe/fpga/artifacts/divpipe-v1/report.json`.

The final gate passed **all 70 steps**, including cancellation at every elapsed clock 98..126 and immediately before final RAM commit, each followed by a different-base canonical-minus-one recovery. It rejected all twenty divider arithmetic/latency/payload/reset mutants and all four carry admission/lane/sign mutants. An independent read-only peer review found no arithmetic, sign, stage-alignment or abort-quarantine issue.

Across the four AW16/AW1 carry builds, the final gate completed 12,422 normalizations, checked 218 domain rejections, 154 reset aborts, 28 malformed-stream faults and 5,918,447 host operations. AW16 passed 1,273 cases per lane width; AW1 passed 978. The separate AW17 test rejected sizes 0, 17, 18 and 31, then recovered with a legal N2 operation. Full-N cases include independent expected digits for both GFN16 square/double results and recurrent normalizations. The divider totals remain 100,370 checked results, 3,300 canceled tokens and eight invalid-input assertions.

Final source-hashed report: `/home/jtl/gfn-fpga-lab/agent-work/carry-divpipe-final/fpga/artifacts/divpipe-v2/report.json`. The report also hashes the frozen integer-oracle vectors and the augmented local copies. The reproducible entry point is `python3 -m reference.carry_divpipe_regression --mutations --output <fresh-directory> --vectors <frozen-vectors.txt> --tiny-vectors <frozen-vectors-aw1.txt>`. All simulation was on aethia under 6 GiB memory, zero swap, 200% CPU and two compiler workers; no Quartus run was performed by this agent.

The following sources are frozen for physical evaluation. No existing helper, carry top or core source selection was modified.

| File | SHA-256 |
| --- | --- |
| `genefer_div_recip_narrow_pipe.sv` | `15ef37c0e910942cd82cc69f3fbfbbb9926a9a63d385a16e0e26f00116578011` |
| `genefer_carry_prefix_stream_divpipe.sv` | `f8d12e7a679dde77b5a893d26f68bc3bcc7faad23b4ef0ebb11d6a0d48f96ed8` |
| `carry_div_narrow_pipe.cpp` | `79adbd46a1207f321187a7fdc11c7047fb7beb2f3d080b5be9b0af00b40e6ee2` |
| `carry_prefix_stream_divpipe.cpp` | `07269e12c34e64cf5c1b560c95048d0e24a5aeb98da5b345aaa0ab3671773507` |
| `carry_stream_divpipe_size.cpp` | `879f43508d606c12bade784324357b64d6c26ab8ef85f34543230d3bdd51e7a3` |
| `carry_divpipe_regression.py` | `fd64ed3c3e4480199b7c1e7d62c57ddc3d08afe1fe4a28f8766630784ca5c48a` |
| Frozen `genefer_sp_ram.sv` | `b97d2f43db1b1e1aa60b9b7fc2b720af1e302bd5ff9e35854c89b30e5fb610df` |
