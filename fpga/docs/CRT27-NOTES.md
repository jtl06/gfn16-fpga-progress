# Centered CRT for the 27 bit basis

`genefer_crt3_27_pipe.sv` reconstructs an exact centered integer from canonical,
ordinary residues for the selected three-field profile. It preserves the frozen
CRT's three-reduction Garner algorithm, II=1 throughput, and 61-stage latency:
input sampled at edge t produces output after edge t+60. The residue ports stay
32 bits and the signed coefficient stays 96 bits. Only constants, internal
operand widths, and payload widths change; the existing CRT and modulo helper
are unmodified.

## Constants and arithmetic

| Quantity | Value |
|---|---:|
| P1 | 104857601 |
| P2 | 69206017 |
| P3 | 67239937 |
| P12=P1*P2 | 7256776917385217 |
| P1 inverse modulo P2 | 44780362 |
| P12 inverse modulo P3 | 10355480 |
| M=P1*P2*P3 | 487945222748036195811329 |
| H=floor(M/2) | 243972611374018097905664 |

Since P1<2*P2, one conditional subtraction computes r1 modulo P2. The
reconstruction then computes:

```
t2  = ((r2 - r1 mod P2) * INV12) mod P2
x12 = r1 + P1*t2
t3  = ((r3 - x12 mod P3) * INV123) mod P3
x   = x12 + P12*t3
```

Here each parenthesized difference is first normalized into its prime's
canonical interval. Thus `0<=t2<P2`, `0<=x12<P12`, `0<=t3<P3`, and `0<=x<M`.
The output is x for `x<=H` and x−M for `x>H`, giving the inclusive centered
interval `[-H,H]`. Comparisons use the unsigned reconstructed value; both
operands are zero-extended to 96 bits before the signed final subtraction.

The maximum supported doubled GFN coefficient magnitude from the parent profile,
131071999737856000131072, is below H and is tested with both signs and neighbors.
Arbitrary legal CRT triples can nevertheless produce larger centered values
than the carry kernel's accepted bound. The narrowed carry divider must retain
its original full 96-bit bound check before slicing to a signed 78-bit input.

## Width and payload proof

All residue differences are below their 27-bit prime. Their add/subtract working
values use 28 bits, sufficient for sums below twice the prime. The two inverse
constants require 26 and 24 bits respectively.

| Stage product | Operand widths | Registered product width |
|---|---|---:|
| INV12*delta2 | 26x27, split into 16+11 input bits | 53 bits |
| P1*t2 | 27x27, split into 16+11 input bits | 54 bits |
| INV123*delta3 | 24x27, split into 16+11 input bits | 51 bits |
| P12*t3 | 53x27, split into 16+11 input bits | 80 bits |

The full products are retained before their registered sums. The stronger bounds
`x12<=P12-1<2^53` and `x<=M-1<2^79` justify the 53-bit x12 and 79-bit final value
registers. Assertions check these bounds at valid stage boundaries.

The first payload is 54 bits `{r1[26:0],r3[26:0]}`. The second is 80 bits
`{x12[52:0],r3[26:0]}`. The final payload is the 53-bit x12 alone. They retain
the frozen algorithm's exact stage alignment. Three unchanged
`genefer_mod64_pipe` instances receive zero-extended products/values and retain
their 16-stage reduction schedules, so no latency retiming is introduced.

Full 32-bit input assertions require each residue to be below its matching prime.
These are simulation contract checks, not hardware error handling or an automatic
converter. Inputs are ordinary residues, not arbitrary radix digits and not
Montgomery-encoded residues. Invalid/bubble cycles may carry garbage because
their payloads are never committed as valid outputs.

## Validation evidence

The final report has status `passed`:
`/home/jtl/gfn-fpga-lab/agent-work/crt27/fpga/artifacts/crt27-v1/report.json`.
The independent oracle uses the whole-integer CRT sum
`sum(ri*(M/Pi)*inverse(M/Pi modulo Pi)) modulo M`, followed by centering; it does
not reproduce the RTL's Garner sequence.

Tests checked 21,152 exact outputs, 3,142 reset-canceled transactions, and 6,487
invalid-cycle output-hold cycles. Coverage includes all 216 combinations of six
canonical corners per residue, centered-range endpoints and neighbors, 216
prime-multiple cases and neighbors, the GFN doubled bound, random residue
triples, continuous streams without reset, bubbles, and resets across all
major pipeline boundaries. Nine noncanonical-input probes triggered assertions.

Eleven mutations were rejected: either inverse, r1 reduction, two payload-stage
alignments, centering equality, negative sign, output latency, reset validity,
the high product limb, and the input-contract assertion. The existing CRT owner
also independently reviewed constants, widths, payload positions, and centering
and found no issue.

All simulation ran on aethia with at most two build threads. No Quartus run or
core/NTT integration was performed by this agent. Resource or complete-PRP
performance claims require separate physical and integration evidence.

Frozen files:

- `genefer_crt3_27_pipe.sv`: `279c6c8c3185eeaaa505283f858fd04904c6daccd30720f6b3bf78e14a6fa160`
- Reused `genefer_mod64_pipe.sv`: `e582dba87dce51794a38039fd02574f443c53750bcafc8fcb1f4d0d50fc60839`
