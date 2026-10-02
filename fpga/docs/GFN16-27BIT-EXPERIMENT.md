# Isolated 27-bit NTT field experiment

The user authorized trying DSP-native-width arithmetic. This experiment does
not replace the existing Genefer-derived field constants or integrated RTL.
`reference/ntt27_experiment.py` searches prime moduli of the form
`k * 131072 + 1`, retaining exactly 27-bit moduli and a three-field product
large enough for the full supported coefficient domain. Selection favors sparse
constant bit patterns, then larger CRT range; this is a heuristic, not a proven
minimum-DSP selection.

## Selected basis

| Field | Prime P | Positive inverse Q mod 2^32 | Primitive generator | R² mod P |
|---|---:|---:|---:|---:|
| 1 | 104857601 | 4190109697 | 3 | 45971250 |
| 2 | 69206017 | 4225761281 | 5 | 50081300 |
| 3 | 67239937 | 4227727361 | 10 | 63576045 |

Primality is checked by deterministic trial division; primitive generators are
checked against every prime factor of P−1. Each field supports every required
power-of-two root through order 131072, including negacyclic N=65536.

For canonical digits and an optional doubling, the uniform bound is
`B = 2 * 65536 * (10^9 - 1)^2 = 131071999737856000131072`.
The new CRT product is `487945222748036195811329`, strictly greater than `2B`.
The centered-range margin is approximately 1.86136 at the worst supported
base/length. This proof does not authorize larger bases or transform lengths.

New CRT constants: P1×P2=`7256776917385217`, P1 inverse mod P2=`44780362`,
and (P1×P2) inverse mod P3=`10355480`. P1 < 2P2 preserves the existing
single-subtract first-residue reduction condition. These values have not yet
been integrated into a new RTL CRT pipeline.

## Conversion caveat

The27-bit modulus/operand width does NOT change the Montgomery radix: it remains
R=2^32 for all original, native27 and sparse27 helpers. Q is the positive inverse
modulo2^32, and root/conversion seeds must use that same R/R². New field-probe
manifests record `montgomery_radix_bits:32`; existing frozen fit manifests are
not rewritten. A planning assumption of R=2^27 was caught in peer review before
any RTL/root change, and the next27-bit NTT regression will assert R explicitly.

Digits can be as large as 999999999, exceeding both the field moduli and a
27-bit bus. **Do not truncate input digits to 27 bits.** Keep full-width input
conversion, and narrow only canonical field residues inside the NTT.

For positive-inverse Montgomery conversion, `digit < 2^32` and `R² < P`
imply `digit * R² < P * 2^32`. The existing reduction formula therefore yields
a canonical result even for these unreduced input digits; explicit tests compare
it with ordinary modular arithmetic. However, this is wider than the documented
canonical-input contract of the frozen multiplier. Any integrated converter
must expose and validate its own appropriate contract rather than silently
violating the 27-bit helper's input assertion.

## Evidence and next steps

The aethia run `artifacts/ntt27-math-v1/report.json` in the parent fit workspace
passed 24 square/double cases across N=2,16,256,65536: random digits, all-max
digits at base10^9, and special−1. Ordinary-arithmetic NTT, centered CRT and
carry normalization match independent whole-integer modular squaring. The
all-max case additionally checks every coefficient against its closed form.
This is mathematical/reference evidence, **not an RTL or fitted throughput result**.

Next isolated component is an explicit 27×27 variable-product Montgomery
pipeline, preserving the four-register-stage / II1 schedule. Test all three
fields before comparing raw DSP blocks and packing-adjusted requirements.
Only then integrate field-specific roots, conversion, CRT and NTT components.
No RAM saving is assumed merely from smaller field values: current banks and
host words remain 32 bits, and physical M20K packing is discrete.

## First matched physical comparison

Field1 (P104857601, identical Q) completed paired standalone fits with5 ns
constraints. Both helpers passed the identical canonical-input vectors before
comparison. Native27 explicit variable width reduces raw DSPs5→3, packing-adjusted
need4→3, raw ALMs152→114 and registers216→128. Reported Fmax is essentially
unchanged:192.38 MHz for the original32-bit helper versus192.05 MHz for native27.
Both miss200 MHz, so this is an area result, not200 MHz closure or a clock gain.

The complete modular multiplier still uses three DSP blocks for this field;
only its variable27×27 product is intrinsically one block. Constant reduction
operations consume additional resources. Changing the prime basis also changes
constant-multiplier costs, so this matched result must not be represented as a
40% saving over the original31-bit S3 basis or as a full-core throughput gain.
All three matched field comparisons are now complete. Actual integrated mapping
remains pending.

| Field | Generic32 raw DSP / Fmax MHz | Native27 raw DSP / Fmax MHz |
|---|---|---|
| P104857601 | 5 / 192.38 | 3 / 192.05 |
| P69206017 | 5 / 180.18 | 3 / 187.97 |
| P67239937 | 5 / 181.95 | 3 / 190.88 |

All six used the same 5 ns requested period; none closes 200 MHz. Generic32
packing-adjusted DSP need is four, versus three for native27. These are paired
standalone results on the new basis, not speedups over the original S3 design.

## Explicit sparse-constant reduction experiment

Separate `genefer_montgomery_mul27_sparse_pipe` retains the native27 variable
product and replaces the two constant products with shifts/adds. It supports
only these three primes, not arbitrary 27-bit moduli:

- P1 = 1 + 2^26 + 2^25 + 2^22.
- P2 = 1 + 2^26 + 2^21.
- P3 = 1 + 2^26 + 2^17.

For each, `(P-1)^2` is divisible by 2^32, hence the positive Montgomery inverse
is `Q = 2-P mod 2^32`. The low32 correction product can therefore be formed
by subtracting shifted copies; the full `m*P` product uses additions of shifted
copies in a 59-bit container. Canonical input, four-stage latency, II1 and reset
contracts stay unchanged. The design hopes to reduce DSP use, but mapping and
clock impact require actual fits; there is no one-DSP measured claim yet.

The first preflight (`mont27-sparse-v1`) rejected an incorrect P1 decomposition
missing 2^22 before running RTL. The corrected v2 run preserves that failure,
checks the identities, reuses the frozen independent arithmetic vectors and
scoreboard, and injects reduction/width/latency/reset defects. Corrected v2
passed:30,009 independent identity checks;76,518 exact RTL outputs;954 canceled
transactions;14,154 invalid-cycle hold checks;12 invalid-input probes;two bad
parameter probes;19 non-equivalent injected faults. All three fields preserve
four-stage latency and II1. Frozen source SHA256:
`501d0ce309a3915f7aed0f3bde14ba1ee8d56ddc5f6abef1f2f5bb572d64db4b`.
Three source-matched5 ns fit projects were prepared and are now running in order.
Twenty-six preparation/summary/integrated-estimate tests passed after adding the
probe; the subsequently expanded full Python suite passes64 tests.

First sparse physical result (P1): rawDSP1 /needed1, rawALM138 /needed179,
154 registers, Fmax244.38 MHz, setup+0.908 ns, hold+0.064 ns: the requested
200 MHz internal timing PASSES. Against native27 on the identical field and
5 ns constraint, this replaces two DSPs with24 additional rawALMs and improves
reported Fmax192.05→244.38 MHz. It preserves four-stage latency/II1.

All three sparse fits are complete and pass the requested200 MHz:

| Field | Raw DSPs | Raw ALMs | Fmax MHz | Setup ns | Hold ns |
|---|---:|---:|---:|---:|---:|
| P104857601 | 1 | 138 | 244.38 | +0.908 | +0.064 |
| P69206017 | 1 | 111 | 250.13 | +1.002 | +0.017 |
| P67239937 | 1 | 116 | 245.64 | +0.929 | +0.066 |

These are separate standalone virtual-I/O fits, not an integrated-core clock or
throughput claim. NTT/core integration must retain R=2^32, canonical operands,
matching roots and atomic selection of the matching27-bit CRT basis.
