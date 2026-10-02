# Two bit remainder stages for CRT27

This isolated candidate targets the measured restoring-remainder bottleneck in the frozen retimed CRT27 pipeline. It retains exact centered reconstruction and initiation interval one, while increasing latency from 64 to 96 stages. No frozen source or integrated core selection is changed. Timing and resource improvements require a new cloud fit; fewer serial correction steps do not establish a physical speedup.

## Measured timing motivation

The archived `results/throughput-20260929/crt27-retimed-fit/probe.sta.rpt` contains detailed paths. Path 1, lines 355 through 462, runs from `reduce_t3|words[11][63]` to `reduce_t3|rems[12][19]`. Its data delay is 7.292 ns through 12 logic levels, with 58 percent interconnect and 38 percent cell delay. Setup slack is minus 2.470 ns against a 5 ns target. The first eight reported paths share this reduction stage; paths nine and ten instead traverse `reduce_t2`. Thus the next measured limiter is the generic four-restoring-bit remainder stage, not the previously retimed modular difference.

The new `genefer_mod27_pair_pipe` performs two restoring bits per register stage. The new `genefer_crt3_27_pair_pipe` substitutes this helper in the three reductions and leaves its products, modular differences, payload routing and centered subtraction unchanged. This candidate introduces no new multiplication operation. Register count, routing cost, DSP mapping and Fmax remain unmeasured.

## Lossless operand widths

Accepted input ports remain full 32-bit words, with assertions requiring canonical residues `0<=r_i<P_i`. An out-of-range word is rejected before its narrowed data could be considered valid simulation input. These assertions are interface diagnostics, not hardware error-response ports; the caller must still supply canonical residues.

The fixed primes are P1=104857601, P2=69206017 and P3=67239937. The first inverse is 44780362 and the second inverse is 10355480. For every accepted residue triple:

- `0<=delta2<P2`, so `a_product<=44780362*(P2-1)<2^53`. The first reducer accepts all 53 product bits.
- `0<=t2<P2` and `0<=r1<P1`, so `x12=P1*t2+r1<=P1*(P2-1)+(P1-1)=P12-1<2^53`, where P12=7256776917385217. The second reducer accepts all 53 bits.
- `0<=delta3<P3`, so `c_product<=10355480*(P3-1)<2^51`. The third reducer accepts all 51 product bits.

These are global canonical-residue bounds, not GFN-specific coefficient bounds. Centered outputs still cover the complete CRT interval for modulus 487945222748036195811329, in signed 96-bit output form.

## Remainder invariant and latency

For a canonical intermediate remainder `0<=r<P`, consuming one bit gives `w=2*r+bit`, hence `0<=w<2*P`. One comparison and conditional subtraction restores `0<=r<P`. Because P is at most 27 bits, w fits 28 bits and each stored remainder fits 27 bits. Repeating this step twice per clock preserves exact modulo reduction; no approximate reciprocal or division operator is used.

Odd input widths receive one zero bit above their most significant bit. Consuming this leading zero leaves the initial zero remainder unchanged. The helper therefore uses `ceil(WORD_W/2)` stages: 27, 27 and 26 for the three CRT reductions. Replacing the three old 16-stage helpers adds 11+11+10=32 clocks. A CRT input accepted at edge k responds immediately after edge k+95; consecutive inputs still produce consecutive outputs.

Reset clears eligibility at every stage. Word, remainder and payload registers are free-running and are not reset; their values outside valid responses are unspecified. The CRT output retains its existing invalid-cycle hold behavior. Bubbles carry their payloads through the same registers but never become eligible outputs.

## Validation status

The standalone modulo oracle covers the actual 53/P2, 53/P3 and 51/P3 instances, plus 64/P1 and 1/2 elaborations. It includes whole-word maxima, exact multiples and neighbors, bit boundaries, random words, bubbles and reset at every pipeline age. A separate small-width exhaustive integer proof checks the canonical-remainder invariant and odd-width padding.

The complete CRT oracle retains canonical corners, maximal residues, centered-range edges, multiples of each prime, worst GFN doubled-coefficient boundaries, random triples and malicious full-word inputs. Reset-age coverage and output due times are expanded to the 96-stage pipeline. Helper mutations cover comparison, shifts, input bit position, remainder width, previous remainder, payload, valid and reset; CRT mutations retain arithmetic/sign/tag/latency/reset/input-assertion checks.

The final gate passed all 71 build/test steps, including 25 fault mutants. The reducer gate checked 59,123 exact modulo responses, canceled 4,685 tokens on reset, and passed 126,294 exhaustive small-width proof cases. The CRT gate checked 27,508 centered outputs, canceled 8,896 tokens, and verified 20,723 invalid-cycle output holds across 48,231 clocks. All nine full-word out-of-range residue probes were rejected. Exact edge k to k+95 response timing and uninterrupted II1 input were verified.

Reports are `/home/jtl/gfn-fpga-lab/agent-work/crt27-pair-v2/fpga/artifacts/mod-v2/report.json` and the sibling `crt-v2/report.json`. The first isolated snapshot, `crt27-pair/fpga/artifacts/mod-v1`, is preserved: it failed strict elaboration because the CLI modulus override was unsized and the stage-zero procedural validity branch referenced index minus one. The final candidate uses an explicitly 27-bit CLI override and a generate-time previous-valid selection. No arithmetic mismatch was observed in the corrected gate.

Independent read-only review found no arithmetic-width, odd-padding, payload, reset or CRT latency issue. All simulation ran on aethia after the benchmark quiet window, with two build workers, 6 GiB memory, zero swap and 200 percent CPU allocation. No Quartus job was launched during that simulation milestone.

## Subsequent physical comparison

The parent subsequently fitted this frozen candidate and the retimed baseline
on the authorized AWS worker with matched 5 ns/seed1/four-worker controls.
Pair-step CRT reached214.73MHz versus133.87MHz for the baseline, with positive
setup and hold slack at200MHz. Raw DSPs remained10; raw ALMs increased4370→4550
and registers3770→5376. Source/control verification and full reports are in
`results/throughput-20260929/crt27-pair-fit/`, including
`matched-retimed-vs-pair.json` and `INTERPRETATION.md`.

The 1.604 Fmax ratio is not a whole-core throughput ratio. II1 is unchanged
and latency grows by32clocks. Integration must be tested independently,
including moving mid-output abort coverage past the new first-output edge.

## Frozen candidate identity

| Source | SHA256 |
| --- | --- |
| `genefer_mod27_pair_pipe.sv` | `602e788df2d4a1da00ebfb28515fcbefbdace65174ed6ee26961ffaedd353a98` |
| `genefer_crt3_27_pair_pipe.sv` | `2552d4aa26a29ed695966c5bde5ec0c18db372267136e418aa6b44a2e9f0ae6d` |
| `mod27_pair_pipe.cpp` | `6c5ad11a2478bfbbbaeb80ec72e1d79790c876b9e83f9fa3304eaedb45775ad7` |
| `crt3_27_pair_pipe.cpp` | `78faf4821bcd910475b69a8feafdff4f2c29de7292128976a026370aa1612fe2` |
| `mod27_pair_regression.py` | `cb0426915252cda172e2db5c2484f051981fe432947f45e611535d633a5bb378` |
| `crt27_pair_regression.py` | `4ed03ffd323fa772e731e77b6746798b85e3707dac6210f2467f507af1638fd4` |

The new top has the same public ports as frozen CRT27 and depends only on the new pair-step reducer. The frozen retimed top remains `f38bb21304104b63b44513a9b21816a97b1448bc4293fac48868f408134e4479`, and its generic mod64 helper remains `e582dba87dce51794a38039fd02574f443c53750bcafc8fcb1f4d0d50fc60839`. Physical evaluation must use the new top with an explicit 96-stage latency contract; it is not a drop-in latency-preserving replacement.
