# Isolated NTT with three 27 bit primes

`genefer_ntt_banked27_engine.sv` is a separate arithmetic experiment. It
preserves the frozen wide engine's cached-root API, natural host addressing,
bit-reversed spectral layout, stage setup, lane scheduling and counters. A new
six-stage DIF/DIT butterfly calls the validated four-stage sparse Montgomery
helper. Frozen 31-bit engines, host wrappers and the square core are unchanged.

## Representation and input contract

The modulus and canonical operands have 27 bits, but the Montgomery radix is
still **R=2^32**, not 2^27. Ports and RAM words remain 32 bits. The positive
inverse is Q=P^-1 modulo 2^32, and multiplication returns a*b*R^-1 modulo P.
The reference regression explicitly asserts this radix and records
`radix_bits: 32`; it obtains the basis from `reference/ntt27_experiment.py`
without replacing any frozen prime globals.

| Field | P | Q | Primitive generator |
| --- | ---: | ---: | ---: |
| 1 | 104857601 | 4190109697 | 3 |
| 2 | 69206017 | 4225761281 | 5 |
| 3 | 67239937 | 4227727361 | 10 |

Data, roots and any used normalization scale must be canonical residues below
P. Raw GFN digits can exceed P and must be reduced by a separately validated
converter before entering this engine; truncating their upper bits is invalid.
Simulation assertions check accepted data/root writes and valid butterfly
inputs. These are synthesis-off preconditions, not hardware rejection logic.
Production integration must enforce the domain in its input path.

Host mask, priority and busy/start rules are unchanged. Masked-off or ignored
requests may contain noncanonical words; active writes may not. Pointwise
requests still use DIT(0,lhs,rhs), retaining y0, so the shared multiplier and
seven-clock RAM writeback tags are unchanged. Generic modular add/subtract
remains valid because its operands and multiplier outputs stay below P.

Root phases0/1/2 contain Montgomery values. Phase3 contains plain
psi^-i*N^-1 residues so its pointwise multiply converts data out of Montgomery
representation. Changing this final table to Montgomery values would add an
unwanted factor R.

## Validation and integration limits

The quick P1/AW4/sixteen-lane regression passed cached repeated squares,
normalized DIF/DIT, host arbitration and active noncanonical data/root/vector
rejection. The masked-noncanonical test passed without an assertion. Full
sixteen/sixty-four-lane tests passed for all fields, AW1/AW4/AW16,
every runtime N2 through N65536, reset transitions, repeated bigint squares
and four reduction/root mutations. Full-size cases include maximum digits at
base1e9 in addition to base2 and recurrent base604832956 squares.

All four reduction/root mutants were rejected, and eighteen active
noncanonical-write probes triggered their intended assertions. The frozen
RTL SHA256 is
`7ae89e702b671e3fbe8a1f90beb99ea595c832729e5e94232bf82515f1d74fe9`.
Its frozen sparse-helper dependency is
`501d0ce309a3915f7aed0f3bde14ba1ee8d56ddc5f6abef1f2f5bb572d64db4b`.
The dedicated regression is `reference/ntt27_engine_regression.py`; evidence
is on aethia at `agent-work/ntt27/fpga/artifacts/ntt27-full-v1/report.json`,
with both lane variants marked passed.
It retains the 6 GiB per-process limit and two build workers. A full physical
host scoreboard runs for each cached-square field/build; arithmetic sweeps
omit only that duplicate prelude, retaining their complete arithmetic oracle.

The sparse helper has separate component fit evidence, but this NTT has no
measured DSP count or clock frequency yet. Its measured warm arithmetic costs
are 78101 clocks at sixteen lanes and 19733 at sixty-four, unchanged from the
frozen shared engine.
Those counts exclude conversion, CRT/carry, initialization and host transfers.
Any core integration must switch the prime profile, roots, digit conversion
and CRT together. The existing sixteen-host wrapper is still a 31-bit-profile
module; it is not silently retargeted by this experiment.
