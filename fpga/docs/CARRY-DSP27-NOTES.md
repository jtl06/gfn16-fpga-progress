# Carry reciprocal products matched to DSP width

This separate experiment replaces the reciprocal multiplier's 32-bit partial-product limbs with explicit operands no wider than 27 bits. It preserves the exact 96-bit reciprocal and all Euclidean division rules. The purpose is to test whether fitting the products to the device's native multiplier shape lowers physical DSP use. Source-level product counts alone do not prove that result; no DSP savings or clock improvement is claimed before synthesis and fitting.

The new helper is `genefer_div_recip_dsp27`; the new streaming carry top is `genefer_carry_prefix_stream_dsp27`. Frozen narrow, divider-retimed and carry modules remain unchanged. No core selection was changed.

## Product partition

The dividend magnitude uses 27-bit chunks, while the 96-bit reciprocal uses four 24-bit chunks. A 27-by-27 partition would also need four reciprocal chunks; using 24-bit chunks makes the adjacent-pair summation regular without increasing the number of products.

| Magnitude width | Frozen 32-bit-limb main products | New main products | New product widths |
| --- | --- | --- | --- |
| 77 | Six 32×32 and three 13×32 | Eight 27×24 and four 23×24 | Eight 51-bit and four 47-bit products |
| 47 | Three 32×32 and three 15×32 | Four 27×24 and four 20×24 | Four 51-bit and four 44-bit products |
| Both dividers per carry lane | 15 partial products | 20 partial products | All operands fit within 27 bits |

The source product count increases. Any physical benefit depends on how the fitter maps the old wide products versus the new native-width products. Each divider also retains its **separate, unchanged low32 estimate×base multiplication**. Those two operations per carry lane are not included in the table and must not disappear from DSP accounting. Carry bound setup arithmetic is likewise unchanged.

## Exact accumulation widths

Write the magnitude as `m=sum(a_i*2^(27*i))` and the reciprocal as `c=sum(c_j*2^(24*j))`. For a magnitude chunk of width L:

- Each `a_i*c_j` fits L+24 bits.
- Pairing chunks 0/1 and 2/3 produces two values of the form `a_i*48-bit-half`, each strictly below `2^(L+48)`.
- Combining the two halves produces the exact row `a_i*c`, strictly below `2^(L+96)`.

No extra carry bit is needed for those pair/row sums because the products share the same magnitude chunk. They are not independent arbitrary maximal numbers.

After shifting rows by 27*i, rows 0+1 equal the low `min(W,54)` magnitude bits times c. Their registered sum therefore fits `min(W,54)+96` bits: 150 for W77 and 143 for W47. The third row exists only for W77; its 23×96 result is shifted by 54 and delayed on the same edge as the rows-0/1 sum. The final result fits W+96 bits and is exactly m*c. No approximation or product-bit omission is introduced by the partition.

`reference/reciprocal_dsp27_proof.py` independently reconstructs the partition with Python integers, checks every intermediate width before truncation could occur, and compares the full result with Python multiplication, including arbitrary 96-bit multipliers rather than only legal reciprocals.

## Pipeline and signed division

| Stage | Registered result |
| --- | --- |
| 0 | Magnitude, low word and sign |
| 1 | Native-width partial products |
| 2 | Two adjacent-product pair sums per row |
| 3 | Full reciprocal product row |
| 4 | Rows 0+1 sum and equally delayed row 2 |
| 5 | High product quotient estimate |
| 6 | Low32 estimate×base product |
| 7 | Provisional remainder subtraction |
| 8 | Correction comparison and candidate remainder subtraction |
| 9 | Unsigned quotient increment and remainder selection |
| 10 | Sign negation, negative-fraction flag and signed remainder |
| 11 | Euclidean floor adjustment, remainder and payload |

The helper remains II1 and now has twelve stages: an input accepted at edge k produces its response after edge k+11. The low-word delay is six, sign delay nine, and valid/payload output index eleven. Two new stages are inserted relative to the frozen ten-stage helper. Registered sums contain at most one wide addition per stage.

For `m<2^W`, `W in {77,47}`, `R=2^96`, and `c=floor(R/b)`, the estimate `floor(m*c/R)` is the exact unsigned quotient or one less. Its error is strictly below m/R<1. The provisional remainder lies in `[0,2*b)`, hence below `2^31` for b<=1e9; low32 subtraction recovers it exactly. One correction suffices. Negative nonmultiples still use `-q-1` with remainder `b-r`, not truncation toward zero. The magnitude and radix contracts, full96 carry guards, and simulation diagnostics are unchanged from the retimed divider.

Base/reciprocal remain stable for responses the caller consumes. Abandoned tokens may drain while a subsequent operation changes configuration; the existing 97-clock setup quarantines those outputs. Reset clears valid eligibility, not free-running data registers. Host arbitration, exact stream masks, row ordering, special minus one, and final RAM-write completion remain unchanged.

## Measured carry cost

Two extra stages in each of two dividers add four clocks once per carry operation, not per streamed row. For G=`ceil(N/LANES)` and K=`log2(LANES)`:

`cycles = 2*G + 135 + 3*K + producer_bubbles`

| LANES | N65,536 ten-stage helper | New twelve-stage helper | Added clocks |
| --- | ---: | ---: | ---: |
| 4 | 32,905 | 32,909 | 4 |
| 16 | 8,335 | 8,339 | 4 |

Setup is still 97 clocks and every legal remaining stream row can be accepted each clock once ready. DSP, register, ALM and Fmax changes remain unmeasured for this candidate.

## Validation status

Initial RTL checks passed 59,644 magnitude77 and 63,164 magnitude47 signed division results against independent Python `divmod`, with 5,022 canceled tokens and eight invalid-input assertions. Additional radix and dividend boundaries target 24/27-bit partition edges. Four- and sixteen-lane AW16/AW1 carry suites passed, including full-N results, no-reset/recurrent cases, malformed host/stream requests and cancellation through the longer pipeline followed by changed-base recovery.

The independent whole-product proof passed 42,420 arbitrary-product checks, 80,000 signed-division checks and 20,000 checks of the equivalent low-pair variant described below. Its report is `/home/jtl/gfn-fpga-lab/agent-work/carry-dsp27-final/fpga/artifacts/product-proof-v1/report.json`.

The initial mutation gate correctly remained failed when one purported fault survived at W47: halving only the reciprocal chunk1 contribution lowers c by less than `2^47`. Its total estimate deficit is still below `2^-2+2^-49<1`, so one correction repairs every allowed division. That is an equivalent public-divider implementation, not an arithmetic failure or evidence that the entire product is unchanged. The proof script records this distinction. The initial report is preserved under `agent-work/carry-dsp27/fpga/artifacts/dsp27-v1/`. The final test perturbs the high reciprocal pair instead, producing a genuinely non-equivalent division fault. No candidate RTL was changed in response.

The final full rerun passed **all 84 steps and rejected all 31 non-equivalent mutants**. It checked 122,808 divider responses, 5,022 canceled tokens, eight malformed helper inputs, 12,470 main-suite carry normalizations, 218 domain rejections, 170 reset aborts, 28 malformed-stream faults and 5,918,527 host operations. AW17 separately rejected invalid sizes and recovered with a legal N2 operation. An independent read-only peer review found no width, stage-alignment or signed-division issue.

Final RTL gate report: `/home/jtl/gfn-fpga-lab/agent-work/carry-dsp27-final/fpga/artifacts/dsp27-v2/report.json`. The independent whole-product report is alongside it at `artifacts/product-proof-v1/report.json`. The entry points are `reference.carry_dsp27_regression --mutations` with the frozen vector paths and a fresh output directory, and `reference.reciprocal_dsp27_proof --output <fresh-directory>`.

Simulation was only on aethia, using two build workers, a 6 GiB memory limit and no swap. Dependencies are frozen `genefer_sp_ram.sv` (`b97d2f43db1b1e1aa60b9b7fc2b720af1e302bd5ff9e35854c89b30e5fb610df`) and the scan-helper definition in frozen `genefer_carry_prefix_stream_pipe.sv` (`9838c6852cac57f7901f8b57dcbb4ee11b7fa129ef86e40158d67cc789b06e5e`); only the new carry top is instantiated. No Quartus run was performed by this agent.

The candidate is frozen for physical comparison without changing the baseline or any core selection.

| File | SHA-256 |
| --- | --- |
| `genefer_div_recip_dsp27.sv` | `15d377127ae9c0274d7cdbc394127ec915a1fddd3979f48d718b0792c9a9b6be` |
| `genefer_carry_prefix_stream_dsp27.sv` | `8fff906268095811bf9cdb1d9fe481f3c505d43b723577e8a8288df1da959bc2` |
| `carry_div_dsp27.cpp` | `2975fd3ff54112b4d8990cf16b1e28ff15e80cdb5e8fce370142a6011b73e8eb` |
| `carry_prefix_stream_dsp27.cpp` | `12612ea5fdccfbe50ecdfdbb0c155a3ff390ddcb0c6a87b8758c8ea51a46fc3a` |
| `carry_stream_dsp27_size.cpp` | `e333182fd0e0aaa5e5bd5d18854bbb6af9c99cd3fda8230c93a57f38ca4dd536` |
| `carry_dsp27_regression.py` | `5e054eed50bbc1814cb7f94edb5bd2b2e29ab81a4c90b9d53ab831220716af84` |
| `reciprocal_dsp27_proof.py` | `077d41646e0a2b9ffec3bab541835fb49c5000f09029ccceb00dbce5266db54e` |
