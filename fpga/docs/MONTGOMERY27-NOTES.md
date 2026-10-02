# Standalone 27 bit Montgomery multiplier

`genefer_montgomery_mul27_pipe.sv` is a separately validated helper for canonical
residues below an odd modulus P<2^27. It retains the frozen 32-bit helper's 32-bit
input/output ports, four registered stages, and initiation interval of one
clock. Its variable multiplication is explicitly 27x27, not an unchecked
32-bit product followed by truncation. No existing multiplier, NTT, CRT, digit
converter, or square core was modified by this experiment.

## Contract and width proof

Let R=2^32. Inputs must satisfy `0<=a,b<P`, with odd `3<=P<2^27` and the
positive inverse `Q=P^-1 mod R`. The output is `a*b*R^-1 mod P`, canonical in
`[0,P)`. This is the positive-inverse subtraction convention used by the frozen
helper, not the negative-inverse addition convention of some Montgomery APIs.

The first product `t=a*b<P^2<2^54` fits exactly in 54 bits. Its upper word
`floor(t/R)` occupies at most 22 bits. The reduction word
`m=(t_low32*Q) mod R` still requires all 32 bits. The product
`m*P<R*P<2^59` fits exactly in 59 bits and its upper word is below P.

Because `m*P` and t have identical low 32 bits, the integer

```
k = (t-m*P)/R = floor(t/R)-floor(m*P/R)
```

lies strictly between -P and P. Subtracting the two upper words and adding P
only for a negative difference therefore produces the exact canonical result.
The selected branch's arithmetic fits in 32 bits because P<2^27. The helper
uses explicit 27-bit input wires, a 54-bit first-product register, and a
59-bit m-times-P register. It deliberately does not narrow m to 27 bits.

## Pipeline and misuse protection

An input sampled at edge k produces its result and out_valid after edge k+3.
The stages are variable product, reduction word, m-times-P, and corrected
result. Consecutive valid requests are accepted every clock. Result holds on
invalid output cycles; reset clears it and cancels all pending requests.

Simulation assertions check the modulus range/parity, the positive inverse,
and both full 32-bit inputs against P before accepting a valid request. Inactive
and reset cycles may contain arbitrary 32-bit garbage and do not trigger the
input assertion. These assertions are synthesis-off contract checks, not a
hardware error interface or an automatic residue converter.

**Radix digits are not valid inputs merely because they fit in 32 bits.**
GFN digits can exceed all three proposed moduli. A future integration must
reduce each full-width digit correctly before this multiplier is used. This
experiment performs no such conversion and does not change the existing core's
prime profile. CRT range/centering and NTT-root integration remain separate work.

## Validated fields

| Field | P | Positive inverse Q |
|---|---:|---:|
| 1 | 104857601 | 4190109697 |
| 2 | 69206017 | 4225761281 |
| 3 | 67239937 | 4227727361 |

The test oracle computes `(a*b*pow(2^32,-1,P)) % P` with Python whole integers,
independently of the RTL reduction sequence. Every field includes zero/one,
P-neighbor values, half-modulus values, bit26 boundaries, Montgomery one,
random canonical pairs, bubbles, pipeline-occupancy resets, and noncanonical
values on ignored cycles. Both reduction branches are covered for every field.

## Evidence and physical limits

Final report has status `passed`:
`/home/jtl/gfn-fpga-lab/agent-work/montgomery27/fpga/artifacts/mont27-v2-final/report.json`.

Each field passed 25,506 exact outputs, 318 reset-canceled requests, and 4,718
invalid-cycle result-hold checks: 76,518 outputs and 14,154 hold checks overall.
Twelve invalid-input probes and two invalid-parameter probes triggered their
intended assertions. Eight mutations were independently rejected in every
field, for 24 mutation checks: lost variable high bit, corrupted reduction,
wrong equality correction, missing negative correction, wrong valid latency,
reset leakage, invalid-cycle result mutation, and missing input assertion.

All tests ran on aethia with at most two build threads. The frozen RTL hash is
`4c8d9f32654c902f80274d160d01ae0bd80f41854ac6529da5a76fa347f9384a`.
The helper has no RTL dependencies. The earlier mont27-v1 evidence is retained;
v2 tests the same RTL and extends all mutations to all three fields.

No Quartus run was performed by this agent. Physical DSP packing, ALMs, timing,
and useful NTT/PRP throughput must be measured separately. An explicit 27x27
operation does not by itself establish a particular resource count or speedup;
raw DSP mode totals and packing-adjusted block estimates must remain distinct.
