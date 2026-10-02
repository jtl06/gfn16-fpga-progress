# No-reversal DIF/DIT candidate

`rtl/kernel/genefer_ntt_difdit_engine.sv` is a new, separately tested candidate.
It does not replace the natural-order `genefer_ntt_stream_engine.sv` or the
integrated square core. No Quartus fit or hardware programming was performed
for this candidate.

## Ordering contract

The added `dif` input is captured at start:

| op | dif | Input layout | Output layout |
| --- | --- | --- | --- |
| 0 | 1 | Natural order | Bit-reversed order |
| 0 | 0 | Bit-reversed order | Natural order |
| 1, 2, 3 | Either | Any physical ordering | Same physical ordering |

`dif` selects decomposition/order, **not** transform direction. Forward or
inverse roots are still supplied by the caller. As before, `inverse=1` enables
the final caller-supplied normalization multiplication; `inverse=0` omits it.
For the fused square schedule:

1. Load/twist natural-order digits.
2. Run op0, dif=1, inverse=0 with forward roots.
3. Square elementwise (op1) in bit-reversed spectral order.
4. Run op0, dif=0, inverse=0 with inverse roots.
5. Multiply natural-order output by the existing ordinary-residue
   `psi^-i/N` table (op2), combining normalization/untwist/Montgomery conversion.

No explicit reversal occurs. The pointwise square is invariant to the shared
permutation. Intermediate checks must explicitly permute expected spectra;
silently using this module as a natural-order transform is incorrect.

## Shared arithmetic and memory

A six-stage `genefer_ntt_difdit_butterfly32`, defined in the same file, shares
one existing Montgomery multiplier between DIT and DIF. A registered input
stage forms DIF's modular sum/difference or captures DIT operands; multiplier
and output alignment then implement:

- DIT: `u + v*w/R`, `u - v*w/R` modulo P.
- DIF: `u + v`, `(u-v)*w/R` modulo P.

Input sampled on edge k produces valid outputs after edge k+5, at II1.
The registered pre-add/subtract avoids adding that carry chain directly to
the multiplier input's combinational path. This is an architectural choice,
not a measured timing guarantee. A separate pointwise multiplier remains.

The existing parity banking is retained, with no extra full data array.
DIF visits stages in descending size; DIT visits ascending size. A RAM-read
result is written seven cycles later for a butterfly and five later for a
pointwise operation. Stage drain and delayed tags preserve collision freedom.
Reset cancels pending work; memory must be reloaded. Host interference while
busy is ignored, including changes to the new dif input. Invalid sizes and
host read/write priority preserve the stream engine's contract.

## Cycles

For N=2^L, butterfly count B=N*L/2:

- Either unnormalized transform: `B + 7*L`.
- Normalized transform: `B + 7*L + N + 5`.
- Pointwise operation: `N + 5`.
- Transform data reads/writes: `2*B`; root reads: `B`.
- `wait_cycles`: `7*L`, plus five for an enabled normalization pass.

For N=65536, the expected/measured-counter contract is:

| Operation | Cycles |
| --- | ---: |
| DIF / DIT without normalization | 524,400 |
| DIF / DIT with normalization | 589,941 |
| Pointwise operation | 65,541 |
| Fused field square | **1,245,423** |

The II1 natural-order stream engine needs 1,441,743 cycles per fused square.
This candidate saves **196,320 cycles (13.62%)**, or about 1.158x operation rate
at equal hypothetical clocks. The extra butterfly stage costs 32 cycles over
the earlier five-stage planning estimate. Root loading, conversion, CRT,
carry and controller handshakes remain additional costs.

## Reproduction and checks

Isolated aethia workspace:
`/home/jtl/gfn-fpga-lab/agent-work/ntt-difdit/fpga`.

```sh
. /home/jtl/gfn-fpga-lab/fpga/tools/aethia-env.sh
python3 -m reference.ntt_difdit_regression --output artifacts/difdit-full-v1
```

The suite checks all three primes, every runtime size N2..N65536 at AW16,
and explicit AW1/AW4 elaborations. It checks both decompositions with both
root directions against independent integer-DIF outputs (small cases also
checked against naive DFT), rather than accepting a round-trip alone.
AW1/AW4 three-field square residues additionally reconstruct the exact
schoolbook negacyclic coefficients.

The inherited square suite checks zero, -1, wrap, maximal and random cases,
including full N65536, against an independent whole-integer modular square;
full-size fused and unfused schedules agree. All four operations, exact cycle
and traffic counters, twenty targeted reset injections per field, host
interference, completion/read-valid pulses and RAM collision assertions are
covered. Four mutants exercise twiddle direction, output address tags,
arithmetic prefix alignment and DIF subtraction. Build, vector and run logs
plus source hashes remain in the artifact directory.

`artifacts/difdit-full-v1/report.json` reports **passed**, including all four
rejected mutants. Candidate RTL SHA256:
`6196cde6befc6a1c35265ab3eb30d139f9eba971dbb745a460bca483460356cd`.

Integration should change only the forward-transform `dif` choice and the
engine module after the candidate passes; inverse and pointwise phase tables
remain unchanged. Re-run repeated autonomous square tests and a vendor fit
before promoting it or changing the clock-qualified performance estimate.
