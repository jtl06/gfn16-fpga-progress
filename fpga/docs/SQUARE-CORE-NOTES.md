# Autonomous three-field modular-square core

`rtl/kernel/genefer_square_core.sv` integrates three streaming NTT lanes, three
root generators, three input Montgomery converters, one II=1 CRT pipeline, and
one reciprocal carry unit. It computes `x <- x*x*(double_bit ? 2 : 1)` modulo
`base^(2^AW)+1`. The normalized result remains in carry RAM; another `start`
uses that result directly, with no host reload, root-table upload, or coefficient
transfer. This is a modular-square core, not yet a full exponent/proof controller.

The opt-in parameter `DIFDIT=1` selects `genefer_ntt_difdit_engine`; default
`DIFDIT=0` retains the original streaming engine. DIF is asserted only for the
forward transform. Its bit-reversed spectrum is squared in place and passed
directly to the inverse DIT, which returns natural-order digits. Twist and
postmultiply retain natural ordering; root directions remain caller-selected.
`NTT_LANES` defaults to one. With `DIFDIT=1` and `NTT_LANES>1`, the core instead
selects `genefer_ntt_parallel_engine`; the validated integration below uses four
lanes per field. Without DIFDIT the original streaming engine remains selected.
Root generation/loading and host conversion stay scalar in this version.
`PREFIX_CARRY=1` additionally selects the exact two-pass prefix carry candidate;
default zero retains general reciprocal carry. This is compile-time selection,
not simultaneous carry engines with duplicate coefficient RAM.
`ROOT_CACHE=1` selects the cached-phase NTT engine (requires `DIFDIT=1`). Four
per-phase validity bits track initialized roots; cached contents survive starts
and radix changes because transform length is fixed at elaboration. Default zero
preserves the original root-generation-per-operation behavior.
`BANKED_NTT=1` selects the bank-centric cached engine and requires both ROOT_CACHE
and DIFDIT. `CARRY_LANES>1` selects the banked wide prefix carry and requires
PREFIX_CARRY. Both flags default off/one, preserving previously tested modes.
Lane counts must be powers of two; the CLI and controller reject unsupported
static combinations rather than silently selecting another architecture.
The current banked and wide-carry branches instantiate
`genefer_ntt_banked_modulemem_engine` and `genefer_carry_prefix_wide_ram`.
Their RAM arrays live in explicit `genefer_sdp_ram32` / `genefer_sp_ram` leaf
modules. This preserves scheduling, ports and cycles while making Quartus RAM
inference practical; the older inline-array modules remain separate evidence
and are no longer selected by these branches.
`VECTOR_IO=1` optionally widens only the internal carry-to-NTT conversion and
NTT-to-carry CRT boundaries. It requires BANKED_NTT, ROOT_CACHE, DIFDIT,
PREFIX_CARRY and matching NTT_LANES/CARRY_LANES greater than one, except for the
explicitly supported FAST_ARITH64-NTT/16-carry profile below. The external
host interface stays scalar. It selects the separately validated
`genefer_ntt_banked_vector_engine` and `genefer_carry_prefix_vector_ram`;
these are not the newer predecode/narrow/pipelined experimental variants.
There are three Montgomery converters and one CRT pipeline per vector word.
Lane zero occupies the low packed bits and maps to the aligned base address.
For N smaller than lane width, only the first N words are active; counters
advance by min(N,width), which also avoids narrow-address counter overflow.
`FAST_ARITH=1` requires VECTOR_IO and separately selects
`genefer_ntt_banked_shared_engine` plus `genefer_carry_prefix_vector_pipe_v2`.
It targets resource/critical-path improvements through shared NTT multipliers,
registered stage setup and pipelined, width-bounded carry arithmetic. The
baseline vector engines remain the default. This option adds a small fixed
cycle overhead; the name does not establish improved elapsed time until a
separate physical timing result is available.
With FAST_ARITH=1, NTT_LANES=64 and CARRY_LANES=16, the core selects
`genefer_ntt_banked_host_engine` around the verified wide engine. Vector IO
width follows CARRY_LANES, so this profile still has sixteen CRT pipelines and
forty-eight input converters. It maps each aligned sixteen-word beat into a
quarter of a sixty-four-word child transaction and captures the read quarter
without adding response latency. Other unequal profiles remain rejected.

## Host contract

The transform size is fixed at elaboration: `N=2^AW`, supported `AW=1..16`.
While idle, host `load_we/host_addr/write_data` writes sign-extended signed32
digits to carry RAM. The intended format is ordinary radix digits `0..base-1`,
or special residue `[-1,0,...]`. Load every digit after reset. `read_en/host_addr`
returns signed96 `read_data` with synchronous `read_valid`; simultaneous write
takes priority over read. All host memory requests and start pulses are ignored
while busy. Base and `double_bit` are latched at start.

`done` pulses for one cycle. `busy` spans the operation. Invalid base outside
`2..1,000,000,000`, invalid digit other than -1 or `0..base-1`, and child errors
set `error` and quarantine the controller until reset; reset cancels in-flight
work. Host must reload all digits after a reset or error. Canonical -1 placement
is a caller precondition rather than a complete memory-content validation pass.
The prefix variant has the stricter domain `base > 2*N+4`; smaller bases are
explicitly rejected at start, not silently processed or sent through a fallback.
Root cache validity clears on reset and any reported core error. Errors require
reset before further work; every phase is refilled afterward, even if some RAM
contents survived. A validity bit is set only when that phase's root stream
completes, no earlier than its final accepted root write. A subsequent NTT-start
edge is separate. Compact half-length phases ignore the stream's unused upper
half rather than aliasing those addresses onto valid entries.

At successful completion `cycles` equals the sum of five 64-bit phase counters:
`conversion_cycles`, `root_cycles`, `ntt_cycles`, `crt_cycles`, `carry_cycles`.
Counters include state transition/drain overhead, not just arithmetic work.

## Sequence and integration details

1. Sequentially read carry RAM; convert each digit into three Montgomery fields
   and write the three NTT memories concurrently. Special -1 maps to `P-1`.
2. Generate/load phase-0 `psi^i*R` roots in parallel; run twist multiply.
3. Generate/load phase-1 `omega^i*R` roots; run forward transforms.
4. Run pointwise squares on all three lanes.
5. Generate/load phase-2 `omega^-i*R` roots; run transforms with `inverse=0`
   to omit the engine's separate normalization pass.
6. Generate/load phase-3 ordinary `psi^-i/N` roots; multiply for fused inverse
   normalization, untwist and conversion to ordinary residues.
7. Read three residue memories together; stream into CRT; optionally double the
   centered coefficients before writing carry RAM.
8. Normalize carry and leave canonical digits resident for another start.

Input/output write addresses use independent sequential counters; there is no
assumption that pipeline latency equals one clock. A separate NTT-start state
ensures the root generator's final root write is accepted before NTT start.
Similarly, carry starts one edge after the final CRT coefficient write. Checks
assert that conversion, residue, root-completion and NTT-completion lanes align.
Vector mode additionally checks word-valid and response-mask alignment. All
active input words are checked against the canonical digit range, not just the
first word. A child vector host error quarantines the core until reset. No
external vector host arbitration is exposed: host requests remain suppressed
while busy and on the initial start edge, and only the controller issues vector
transfers. The expanded harness alternates busy start pulses high/low and tests
invalid digits at every small-N position, plus full-N first/last positions.

## Complete-core measured cycle counts

Measured in Verilator on aethia, `AW=16`, `base=604832956`, random canonical
initial digits. Five consecutive squares use the actual previous RTL output,
with double bits `0,1,1,0,1`. All five match independent Python whole-integer
modular squaring and use the same total:

| Phase | Clocks per square |
|---|---:|
| Carry-RAM read and Montgomery conversion | 65,541 |
| Four generated root-table loads | 262,152 |
| Three parallel fields: twist, forward, square, inverse, postmultiply | 1,441,753 |
| Residue read, streaming CRT, coefficient write | 65,598 |
| Carry including setup and two passes | 589,936 |
| **Total** | **2,424,980** |

Two additional full-size successive squares starting from -1 (double bits 1,0)
pass with 2,031,750 clocks each; carry takes 196,706 clocks and one pass. Thus
the carry contribution is data-dependent; five random steps do not establish a
worst-case bound or a complete-PRP average.

A no-reset reload at base 1,000,000,000 with every digit 999,999,999 stresses
the full-size coefficient range: the first square passes at 2,424,980 clocks,
and its subsequent doubled square passes at 2,031,750 clocks.

At hypothetical 100 MHz, 2,424,980 clocks is 24.25 ms/square, or roughly 12.9
hours for 1.91 million exponent steps. This is not an achieved clock claim:
integrated placement/timing must determine the frequency. The estimate excludes
proof/checkpoint work and exponent scheduling, but unlike earlier standalone
summations includes actual three-field integration, on-FPGA root generation,
conversion, transfers between the arithmetic stages, and controller overhead.

### Opt-in DIF/DIT integration

The same complete-core tests with `DIFDIT=1` measure **2,228,660 clocks** for
each full random square and the base-1e9 all-max first square. NTT phases shrink
from 1,441,753 to 1,245,433 clocks; other phases are unchanged. This saves
196,320 clocks, **8.10% of total**, without an explicit bit-reversal pass.
The sparse/minus-one cases take 1,835,430 clocks. These remain cycle counts,
not timing-closed performance promises.

The earlier DIFDIT-only core snapshot SHA-256 is
`07a40a884b567d58d39167230cb16f6ee76a004ced01588670170d694b202296`;
the reused DIF/DIT engine SHA-256 is
`6196cde6befc6a1c35265ab3eb30d139f9eba971dbb745a460bca483460356cd`.
The original fit snapshot used the pre-parameter core; new fits must record the
parameter and these current source hashes rather than silently reusing it.

### Opt-in four-lane integration

With `DIFDIT=1, NTT_LANES=4`, the expanded complete-core regression measures:

| Full N=65,536 case | Total clocks | NTT clocks | Carry clocks |
|---|---:|---:|---:|
| Five consecutive random squarings, b=604832956 | 1,294,772 each | 311,545 | 589,936 |
| Two sparse/minus-one squarings, b=604832956 | 901,542 each | 311,545 | 196,706 |
| All-max digits, b=1000000000 | 1,294,772 | 311,545 | 589,936 |
| Subsequent doubled square of that result | 901,542 | 311,545 | 196,706 |

This mode passes all 384 cases and four injected-fault checks, including N=2
smaller than its configured lane count. The other phases retain their original
cycle counts; four NTT lanes do not imply a fourfold whole-core speedup. At this
point carry and scalar root loading dominate much of the remaining runtime.

The earlier three-engine-mode core snapshot SHA-256:
`e2df6e0d02da4f33bc12ab5687317a2fd6335bd33c2c408c78537a86d4b7aa9b`.
Parallel engine SHA-256:
`f02c37af212208974430dceb93f9002772bb55f3d0b3514bfd4f92f80e5fd8d1`.
No prefix carry or resident-root cache is integrated in this snapshot.

### Opt-in prefix carry integration

With `DIFDIT=1, NTT_LANES=4, PREFIX_CARRY=1`, all nine full-size test operations
take **836,026 clocks**, including random recurrence, -1/sparse inputs, all-max
base-1e9 input and subsequent doubling. The phase breakdown is conversion
65,541; roots 262,152; NTT 311,545; CRT 65,598; carry **131,190**. Carry includes
the standalone `2N+116` clocks plus two controller edges. Its two full passes
are deterministic over the supported coefficient/base domain.

The prefix suite passes **1,201 squares**, 15 reset-abort cases, invalid-base
and invalid-digit/quarantine checks, and five injected-fault checks. It includes
six complete small-N Fermat exponentiation chains: N=2 bases 10 and 11, N=8 bases
22 and 23, and N=32 bases 70 and 71. Starting at one, each scans every bit of
`b^N` using squareDup with actual preceding RTL output; every step is checked
and the final residue independently agrees with `pow(2,b^N,b^N+1)`. These bounded
chains are not full GFN-16 PRP runs. Complete chain metadata and final residues
are recorded in each vector entry's `fermat_chains` report field.

The earlier prefix-capable core snapshot SHA-256:
`ef9f7c1904465e4b7d68f0af98aa9712400dd8d3283738d62e741c3648d89923`.
Dependencies are `genefer_carry_prefix.sv` SHA-256
`7d45ed60e56ad3d489e30a239b8af5c49274a3ccba42c7a37543820596270b31` and
`genefer_div96_recip_prefix.sv` SHA-256
`7fb975d75e27e5d66c97b02a2784cba8ed7dde3de624555859b8e8893a71a3b9`.
No resident-root cache is included yet.

### Opt-in resident root cache

With `DIFDIT=1, NTT_LANES=4, PREFIX_CARRY=1, ROOT_CACHE=1`, the first full-size
square after reset still costs **836,026 clocks**. Subsequent squares cost
**573,874 clocks**: conversion 65,541; roots **0**; NTT 311,545; CRT 65,598;
carry 131,190. This holds for the tested random sequence, doubling, special -1
and full reload from radix 604832956 to radix 1000000000 without reset.

The cold iteration generates all four phases. Warm iterations bypass both root
controller states entirely; there are no root writes or generator restarts.
`root_cache_valid[3:0]`, `root_phases_loaded[2:0]`, and `root_cache_hits[2:0]`
expose the lifecycle. The scoreboard requires cold `(mask-before=0, loads=4,
hits=0)` and warm `(mask-before=15, loads=0, hits=4)`, and independently checks
that root-cycle totals equal `loads*(N+2)`.

The cached-prefix suite passes **1,255 squares**, eight intentional mutants and
27 reset-abort tests. In addition to the normal controller abort points, it
aborts during partial fills of each root phase 0,1,2,3, then reloads operand RAM
without a second reset and verifies a cold square followed by a warm square.
Cache-specific mutants cover stale validity after reset, marking all phases valid
after just one fill, and accidentally reloading phase zero on a warm start.
Complete small-N Fermat chains run with retained root tables between every step.
Cached general-carry compatibility passes another 551 squares and seven mutants;
the original uncached/default engine passes 551 squares and four mutants on the
same core revision, retaining its original full-size cycle counts.

The earlier cache-capable core snapshot SHA-256:
`a03a09d3de0ba19f21fab6f083ec8262cbc5edb21a60e1b8e7d01e96d1f13004`.
Cached NTT engine SHA-256:
`b9b330c1d6a42e8025df2824796b8448b59440f4140fe336a5755ce899eb4d84`.
This snapshot still uses scalar prefix carry; the separate wide-carry candidate
is not integrated here.

### Bank-centric NTT and four-lane carry

The opt-in combination BANKED_NTT=1, NTT_LANES=4, CARRY_LANES=4, PREFIX_CARRY=1,
ROOT_CACHE=1, DIFDIT=1 passes 1,255 squares and eight mutation checks. Full-size
cold squares take **737,722 clocks**, warm squares **475,570**. The NTT phase
remains 311,545 clocks, confirming that the bank-centric routing change preserves
the arithmetic schedule. Carry shrinks to **32,886 clocks** including controller
overhead (32,884 in the standalone unit). Conversion and CRT remain scalar;
their 65,541 and 65,598 clocks are not reduced by wider internal carry.

One-change-at-a-time checks separate banked NTT with scalar prefix carry from the
old cached NTT with wide carry. No fallback coefficient RAM is duplicated; only
the compile-time-selected carry engine is elaborated. This is simulation evidence,
not proof that the combined architecture fits or reaches a requested clock.

Current banked/wide-capable core SHA-256:
`f8a4b3936e11cd08865ea0fcb7812dc75fc950a2ab67b0fd8eff5ee9550eacf8`.
Bank-centric NTT SHA-256:
`5f7c0b4d5afc2c55df4432ac05edcf5f348a248c4b81d187eef2a17eca43cd5e`.
Pipelined wide-carry SHA-256:
`ed3861413e2122c8243189c0688c4e806901d416fd6e6d6440c667de4c1b3fd6`.
Transfer-tree SHA-256:
`b18e39ebcaf2a1b514e0b617170dc1491a576772fe94ff3cf55316feee09971c`.

## Independent regression and evidence

The oracle builds `x` directly from radix digits using Python arbitrary-precision
integers, computes `x*x*2^bit mod (base^N+1)`, and converts back to canonical
digits. It shares no RNS, NTT, Garner, or reciprocal-carry algorithm with RTL.
The host checks every output digit but never writes those oracle digits back
between consecutive RUN commands; subsequent runs consume actual device RAM.

Expanded suite, seed 20260929 (384 completed squares):

- N=2: 145 modular squares, including exhaustive residues modulo `2^2+1` and
  `3^2+1`, five reset-abort points.
- N=8: 115 squares, five reset-abort points.
- N=32: 115 squares, five reset-abort points.
- N=65,536: nine full-size squares in three sequences.
- Small cases cover bases 2, 3, 97, 604832956 and 1,000,000,000; zero, one,
  negative one, maximum digits, alternating digits, high monomials and random
  input; both doubling values; sustained real output reuse.
- Every busy cycle presents hostile host read/write/start requests and changes
  base/double_bit. All are ignored correctly. Phase totals equal elapsed clocks.
- Repeated full reloads change base across 2, 604832956, 1,000,000,000 and 97
  without any reset. Consecutive starts immediately follow the final host read
  edge, with no idle bubble. Invalid digit -2 and a digit equal to base are
  rejected; attempted activity after error stays quarantined until reset.
- A second seed 137 passes another 107 N=8 squares.
- Four separately compiled controller mutants are detected: omitted doubling,
  forward instead of inverse root table, CRT write-address shift, and incorrect
  input Montgomery conversion constant.

Remote evidence is in
`/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/core-boundaries/`,
with source SHA-256 values, complete logs, exact vector files and `report.json`.
Earlier successful snapshots remain in `core-01/`, `core-02/` and `core-final/`.
Reports include machine-readable `metrics` entries for every completed case:
`aw`, `n`, `case`, `cycles`, `conversion`, `roots`, `ntt`, `crt`, `carry`, `passes`.
`--summarize-only` adds these entries to an existing report without rerunning
simulation, retaining original source hashes and recording the parser hash.
Current reports additionally record explicit per-case `base` and
`configuration.difdit`; three-mode reports add `configuration.ntt_lanes`.
Prefix-capable reports also record `configuration.prefix_carry`.
Cached reports add `configuration.root_cache` and per-case `cache_before`,
`root_cache_warm`, `root_loads`, `root_hits`. Cold setup must not be confused
with steady-state root costs when extrapolating a full exponentiation.
Banked/wide reports additionally record `configuration.banked_ntt` and
`configuration.carry_lanes`.
The opt-in full regression (384 cases and all four
mutants) is in `core-difdit-v2/`; default-mode revalidation of the parameterized
core is recorded separately in `core-stream-default-v2/`. Older logs without
explicit bases produce `base: null` rather than guessing from a case label.
Four-lane evidence is in `core-parallel4-v1/`. Both single-lane modes for the
same three-mode core revision are separately recorded in
`core-difdit-default-v3/` and `core-stream-default-v3/`.
Prefix evidence is in `core-prefix4-v1/`; general-carry compatibility on the same
prefix-capable core is recorded separately in `core-general4-v4/`.
Resident-cache evidence is in `core-cache-prefix4-v1/`, with cached general-carry
compatibility in `core-cache-general4-v1/` and original uncached/default-engine
compatibility in `core-stream-default-v5/`.
Banked-four/wide-four evidence is in `core-banked4-carry4-v1/`. One-change
configurations are `core-banked4-carry1-v1/` and `core-cached4-carry4-v1/`;
preserved-default compatibility is in `core-stream-default-v6/`.
The original inline-memory sixteen-lane integration is independently recorded
in `core-banked16-carry16-v1/`: all 1,255 whole-integer cases and eight mutation
checks passed. At N=65,536 the first square takes 479,674 clocks and warm squares
217,522 clocks: conversion 65,541, roots 262,152 cold / zero warm, NTT 78,073,
CRT 65,598 and carry 8,310. All nine full-size samples pass, including recurrent
random squares and a no-reset reload from radix 604832956 to 1,000,000,000.
These are cycle measurements, not an integrated placement or frequency claim.

The module-memory core snapshot is
`80851bdfc16f90dc7c343f67496d253ab59c5fbde1c6311d7e18231c82acd9e5`.
Its fresh four-/sixteen-lane regressions are in
`core-modulemem4-carry4-v1/` and `core-modulemem16-carry16-v1/`. The four-lane
suite passed all 1,255 cases and eight mutants, with exactly the prior 737,722
cold / 475,570 warm clocks. The sixteen-lane suite also passed all 1,255 cases
and eight mutants, preserving 479,674 cold / 217,522 warm clocks. Each directory
contains an exact `source-snapshot.tar.gz` matching the report's source hashes.
No arithmetic or
controller change is included in this snapshot, only the two module selections
and their explicit dependencies.

The opt-in vector-boundary core snapshot is
`18fe0ae9b5a278b084e1ff53bc1ad54c94a9e8fcede78f6117822647e9bf2f06`.
`core-vector4-v1/` passed all 1,255 cases and thirteen injected-fault checks.
Full N=65,536 measures 639,418 cold / 377,266 warm clocks: conversion 16,389,
roots 262,152 cold / zero warm, NTT 311,545, CRT 16,446 and carry 32,886.
The five new faults cover duplicated conversion words, duplicated CRT words,
checking only the first input word, accepting scalar writes on the initial
start edge, and exposing internal reads to the host while busy. These are
in addition to the earlier arithmetic, domain and cache mutations.
This is a simulated cycle improvement, not a timing/resource fit claim.
`core-vector16-v2/` also passed all 1,255 cases and thirteen mutation checks.
Its full-N cold / warm totals are 356,794 / 94,642 clocks: conversion 4,101,
roots 262,152 / zero, NTT 78,073, CRT 4,158 and carry 8,310. Both vector reports
retain exact source archives. Disabled-option compatibility is recorded in
separate reports; only status `passed` indicates completed validation.
The vector-off banked-four/carry-four suite `core-vector-off4-v1/` passed 728
cases with unchanged 737,722 cold / 475,570 warm clocks. Original default mode
`core-stream-default-v7/` passed 334 cases and four mutants, retaining 2,424,980
clocks for the full random case. These use the expanded start/busy host tests.
The initial `core-vector16-v1/` run passed normal arithmetic but stopped at an
equivalent fault case: its N=8 address was advanced by eight and truncated back
to the same address. It is not a passed mutation suite. The revised harness
uses mutation N at least twice the vector width (N=32 for sixteen lanes), records
`mutation_aw`, and reruns in `core-vector16-v2/` without changing the RTL.
The standalone `vector-config-reject-v1/` harness also passes six missing-flag
or mismatched-lane configurations and checks error quarantine after rejection.

The next opt-in fast-arithmetic core snapshot is
`9ccea541ec1beaad1331da60e30c83b6d53a607b18eb962d087e694db0413b1a`.
Its new dependencies are the shared NTT
`f8fb1ca640e6fbf9d6194738f83d9923396260c14dc30eb877d9e02029660054`,
vector carry pipe-v2
`cd95a89e1b5a5221e7159c2492919e6607ecb6ec004fcd0ac782527c87ade3ea`,
and narrow reciprocal helper
`eef327cee81d41895a068b746a3715daba95d43bea919edbddf9b498ecfc38bf`.
`core-fast4-v1/` passed all 1,255 cases and thirteen mutants, and retains an
exact source archive. Full-N cold / warm totals are 639,458 / 377,306 clocks;
NTT takes 311,583 and carry 32,888, while conversion, root and CRT phases are
unchanged. This is exactly forty extra clocks, not a claimed wall-time speedup.
`core-fast16-v1/` also passed all 1,255 cases and thirteen mutants, with an exact
source archive. Full-N cold / warm totals are 356,834 / 94,682 clocks; NTT takes
78,111 and carry 8,312, while the other phases retain their vector-sixteen
counts. Both profiles therefore add forty clocks. Physical timing and resource
results, rather than this small cycle increase alone, decide their usefulness.
The FAST_ARITH=0 compatibility suite `core-fast-off4-v1/` passed 728 cases,
preserving baseline vector-four counts. `core-stream-default-v8/` passed 334
cases and four mutants, preserving the original full-random 2,424,980 clocks.
Seven standalone invalid-vector/fast configurations and post-error quarantine
also pass in `vector-fast-config-reject-v1/`.

The asymmetric64/16 candidate core snapshot is
`c6dad925fe58c17074722aabfee1d757232552465ecf0026fcc078373e08d5db`.
Its added dependencies are host wrapper
`a49b2e6fa979f86be5d365fd9bdff147bdfb5a43e27935406969b3a3ce76fa94`
and wide engine
`038b496b97d231417c406c334e57c6f21cb0c0f45d7619430630a22d8cb815af`.
The expanded harness adds short chains with immediate starts after done and no
intermediate host reads, followed by a final whole-integer comparison. Existing
per-step-readback and complete small Fermat tests remain intact. Metrics now
record `readback` (null for older logs); unobserved intermediate chain states
must not be reported as individually checked residues. A new immediate-start
mutant requires done to clear before accepting start and must be rejected.
The asymmetric normal/mutation gate has passed in `core-host64-full-v1/`
(AW5/AW16, 547 operations, 538 direct readbacks and fourteen rejected faults),
together with `core-host64-quick-v1/` (AW1/AW3, 735 operations and 721 readbacks).
The reports share identical RTL sources; the full report adds a test-only C++
optimization override for faulty models. Combined coverage is 1,282 operations,
1,259 direct readbacks and 27 reset/abort recoveries. Full N=65,536 measures
298,466 cold / 36,314 warm clocks: conversion 4,101, roots 262,152 / zero,
NTT 19,743, CRT 4,158 and carry 8,312. The full report retains its exact source
archive. Equal-sixteen compatibility passed in `core-host64-fast16-compat-v1/`
(747 operations, 731 direct readbacks), retaining 356,834 / 94,682 clocks.
Default compatibility passed in `core-stream-default-v9/` (353 operations,
337 direct readbacks and five mutants), retaining 2,424,980 full-random clocks.
Both compatibility reports also retain exact source archives. All ten invalid
vector/fast/asymmetric configurations and post-error quarantine pass in
`host64-config-reject-v1/`. These cycle measurements are not a physical timing
claim.
To reproduce the full latest suite in a fresh remote output directory:

```sh
. /home/jtl/gfn-fpga-lab/fpga/tools/aethia-env.sh
python3 -m reference.square_core_regression --output artifacts/core-new-run --aw 1 3 5 16 --mutations
python3 -m reference.square_core_regression --output artifacts/core-new-difdit --aw 1 3 5 16 --difdit --mutations
python3 -m reference.square_core_regression --output artifacts/core-new-parallel4 --aw 1 3 5 16 --difdit --lanes 4 --mutations
python3 -m reference.square_core_regression --output artifacts/core-new-prefix4 --aw 1 3 5 16 --difdit --lanes 4 --prefix-carry --mutations
python3 -m reference.square_core_regression --output artifacts/core-new-cache4 --aw 1 3 5 16 --difdit --lanes 4 --prefix-carry --root-cache --mutations
python3 -m reference.square_core_regression --output artifacts/core-new-banked4 --aw 1 3 5 16 --difdit --lanes 4 --prefix-carry --root-cache --banked-ntt --carry-lanes 4 --mutations
```

### Input-conversion fusion candidate

The opt-in `FUSE_INPUT_MONT=1` candidate selects `genefer_root_stream32_r2` and
requires FAST_ARITH plus VECTOR_IO. Default zero preserves every prior profile.
It changes only phase-zero roots from `psi^i R` to `psi^i R^2`,
where **R is still 2^32**. Loading ordinary canonical residues `d` then gives
`Mont(d, psi^i R^2) = d psi^i R`, exactly the original converted-and-twisted
representation. Phase-one/two roots remain Montgomery and phase-three roots
remain ordinary `psi^-i/N`; changing those formats would be incorrect.

Its four phase-zero seeds are `R^2 psi^j`, j=0..3, while the recurrence multiplier
is still `R psi^4`. Thus each feedback multiplication advances four exponents
without changing the R-squared format. The separate oracle checks every root
in all four phases and compares the fused-twist identity using ordinary modular
arithmetic, including zero, one, the largest supported digit and field minus one.
The existing root module and its source snapshots are unchanged.
The separate unit gate `root-r2-v1/` passed all three fields at N=2,4,8,16,65536
and all six injected faults. It retains an exact source archive; the new module
hash is `7ca72dbdec54ab0cf7ff0f914b3f764f7751295e4ce60580eee5bd734eef210f`.
This validates the root profile; the integrated option has its own gate.
The integrated candidate core hash is
`3aaaeb18bca6c80722d87ad3defaa274f69c0798d5be08eeb83c0cc154fe9c05`.
Its primary `core-fused64-v1/` gate passed 1,282 operations, 1,259 direct readbacks,
27 reset/abort recoveries and all fourteen injected faults. The conversion fault
now pairs ordinary inputs with the old R-scaled root producer, rather than
mutating an inactive converter. An exact source archive is retained. Full-N
measurements are 298,463 cold / 36,311 warm clocks: conversion 4,098, roots
262,152 / zero, NTT 19,743, CRT 4,158 and carry 8,312. Compatibility and static
configuration checks remain separate gates; no resource or clock claim follows
from these cycle measurements.
Those compatibility gates also passed and retain source archives:
`core-fused16-v1/` has 747 operations / 731 readbacks and measures 356,831 cold /
94,679 warm full-N clocks; `core-fused4-small-v1/` has 735 operations / 721
readbacks at N2/N8 (not a full-N four-lane benchmark). `core-fused-off64-v1/`
has 533 operations / 524 readbacks with unchanged 298,466 / 36,314 clocks.
`core-stream-default-v10/` has 353 operations / 337 readbacks and five rejected
faults, retaining 2,424,980 full-random clocks. Both invalid fusion profiles and
post-error quarantine pass in `fusion-config-reject-v1/`.

The input path retains a one-stage ordinary-residue register boundary.
This removes the three converter multipliers per I/O lane, but **does not remove
any carry-to-NTT transfer beats**. Compared with a four-stage converter, the
expected fill-time reduction is only three clocks. This profile is scoped to the
current 31-bit fields, whose moduli exceed the maximum supported radix digit.
A future 27-bit field profile must reduce ordinary digits canonically first;
truncation or merely replacing modulus constants is not valid.

### Opt-in executable build cache

`--build-cache DIR` enables the separately verified cache utility. The default
remains uncached. Keys include ordered actual RTL/C++ paths and content (including
each mutant), all build flags and parameters, compiler/Verilator/binutils/Perl
fingerprints, runtime/header closure and relevant environment. Unsupported custom
tool/include/preload/make overrides fail closed in cached mode. Generated `.d`
dependencies are checked before publication; undeclared external dependencies
prevent a cache entry from being published.

Cached artifacts are frozen, hashed and verified under a per-key lock. Each
report records hit/build/repair provenance and executable SHA separately from the
normal test steps. Every normal, adversarial and injected-fault oracle still
executes; cached correctness results are never accepted. Changes to source,
parameters, flags or toolchain correctly miss, so this is a repeat/recovery-build
optimization rather than a promise to accelerate every new architecture.
Final hook smoke evidence is in `core-cache-hook-cold-v2/`,
`core-cache-hook-warm-v2/` and `core-cache-hook-off-v2/`, each with source archive.
Cold and warm runs each passed 341 operations / 327 direct readbacks; warm
reused both verified executables but reran the oracles. Five same-size faulty
models were independently compiled and rejected under distinct keys. Uncached
mode separately passed 178 operations / 171 readbacks. The hardened runtime
closure includes full Verilator scripts/runtime, Python standard library, Perl
module trees and the dynamic shared libraries of build tools. All eighteen
cache utility tests passed in both cached runs.

### Isolated streaming-carry integration candidate

The first component remains frozen `genefer_carry_prefix_stream`
`67ab9b601a83b9d8bb3d6425daefb786f6eb7359d2f1827fa16be298f9184071`.
Later pipelined/divider experiments are separate candidates, not implicit swaps.
The new `STREAM_CARRY=1` option requires FAST_ARITH, VECTOR_IO and four or sixteen
carry/I/O lanes; default zero preserves previous modes. Candidate core hash is
`204388900f84fea154ccb2a673b48cb5467779854905942f696f64b533a81201`;
its complete integration and compatibility gate is now frozen and passed.
It starts carry on the final conversion commit so its 97-clock setup overlaps NTT
work. It waits for stream-ready before issuing residue reads, then feeds ordered
complete CRT groups through its dedicated stream ports (not vector digit writes).
The component guarantees continuous acceptance after setup until all N
coefficients arrive. Any CRT-valid without ready or any child error must
quarantine the operation. After the last accepted CRT group, wait for carry-done
without starting it again. Result digits remain in its signed32 RAM and continue
to use the existing sign-extended96 host interface.

Exclusive core phase counters must still sum to whole-square cycles. The child
carry's busy counter includes overlapping NTT/CRT work and producer bubbles, so
it must not be added to those phase counts. The new N32 abort resets at CRT-phase
clock63, after the first coefficient row has actually been accepted but before
remaining rows arrive. Cold root setup alone is longer than the 97-clock carry
setup in this test, so first acceptance uses the frozen61-stage CRT schedule.
Deadlock mutants use a conservative size-scaled harness limit
`min(50M,max(10k,2048*N))`; full N retains its prior cap.

The initial four-lane AW1/AW5 gate passed 1,058 completed operations, 1,044
direct result readbacks and 19 reset aborts, including the mid-CRT abort;
all seventeen injected faults were rejected. A separate static gate rejects
STREAM_CARRY with a scalar/default profile, a non-FAST vector profile, and an
otherwise legal eight-lane profile, and verifies error quarantine.

The separate sixteen-lane AW1/AW3/AW16 gate has also passed. Its twelve full-N
operations include ten direct result readbacks, successive squares, both double
choices, and a no-reset radix change to all-max base-1e9 digits. At N=65,536 it
measures 352,636 cold / 90,484 warm clocks: conversion 4,098, roots 262,152 / zero,
NTT 78,111, CRT 4,158 and the exclusive carry tail 4,117. These are simulation
cycles for this exact integration, not physical timing or FPGA throughput.
The 64-NTT/16-I/O normal AW1/AW3/AW5/AW16 oracles have passed too, including
the same twelve full-N operations. Full N measures 294,268 cold / 32,116 warm
clocks; only NTT changes, to 19,743 clocks. Its seventeen-mutant gate has now
passed through the explicit recovery reconciliation described below. Full-N
four-lane measurements also pass: 622,972 cold / 360,820 warm,
with conversion 16,386, roots 262,152 / zero, NTT 311,583, CRT 16,446 and carry
tail 16,405. Keeping STREAM_CARRY but disabling FUSE_INPUT_MONT also passes
533 operations / 524 readbacks / 9 aborts at 64/16; full N is 294,271 cold /
32,119 warm, with conversion 4,101 and all other phases unchanged. STREAM_CARRY-off
64/16 compatibility passes 533 operations / 524 readbacks / 9 aborts, preserving
298,463 cold / 36,311 warm clocks. Default compatibility passes 353 operations /
337 readbacks / 18 aborts and five injected faults; full random N remains
2,424,980 clocks. No existing architecture is silently switched to streaming.

Two long-lived SSH queue sessions exited with transport status255 after
successful compiler steps. Their original reports remain `failed`; this was
not reinterpreted as a complete passing gate. Detached log-backed recovery
keeps RTL, C++ and Python source identities unchanged, reruns missing tests and
fresh fault checks, and reuses completed full-N normal evidence without
gratuitous resimulation. A separate reconciliation record checks original
normal return codes, vector hashes, completion/readback/abort counts, executable
and cache-manifest identities, and exact log-derived phase metrics. It records
both original failed-report and fresh recovery-report hashes. Four-lane AW3
plus fresh AW16 evidence totals 226 operations / 217 readbacks; its separate
AW1/AW5 quick gate and seventeen faults are still retained independently.
The reconciled 64/16 gate contains 1,284 normal operations / 1,261 direct
readbacks / 28 reset aborts and all seventeen fresh fault rejections. A repeated
tiny AW1 baseline in the recovery run is checked for identical metrics but not
double-counted in these normal-case totals. The standalone validator's eleven
tests reject altered vectors, counts, return status, timeouts, commands,
executable/key/source identity and report metrics.

The regression's optional shared compile lock serializes its two-thread model
builds while allowing independent oracle execution to overlap. Command timeout
includes lock waiting. Timed-out commands terminate their own process group,
record the timeout and fail the gate rather than leaving orphaned compilers or
publishing a successful report. Neither caching nor the lock bypasses oracles.

The integration owns the core, its C++ driver, its Python regression and these
notes; the separate R-squared root experiment adds its own RTL, driver and
regression without editing the frozen root generator. No Quartus fitting, hardware access,
programming, or Mac simulation was performed by this subtask.

## Separate atomic27 precision-stream candidate

`genefer_square_core27_stream` is a new top, not a replacement of either frozen
core. Its only parameters are AW and NTT_LANES (16 or 64); internal IO and carry
remain sixteen words wide. It preserves the atomic27 ancestor's three fields,
Montgomery radix 2^32, digit reducer, sparse multiplier, cached NTT, 61-stage
CRT and R-scaled phase-0 roots. The embedded root generator still uses its three
generic32 multipliers. There is no input/twist fusion, generated-root engine or
CRT replacement in this experiment.

The new top selects `genefer_carry_prefix_stream_precision` and its W77/W47
reciprocal divider, with the scan helper from frozen `stream_pipe`. Division
precision 2^W is unrelated to the unchanged Montgomery radix. The final counted
conversion write starts carry setup after all digit-RAM reads have drained.
Ready-qualified residue requests reserve the nonstalling ordered CRT stream;
the last accepted row transitions directly to carry-wait. Child errors, early
done and CRT output without ready quarantine the core and invalidate roots.
Canonical digits reside in signed32 RAM and are sign-extended on the unchanged
signed96 host read interface.

Candidate top hash is
`75eb580540fc6a7939f824182d244123e03e3b780e65e57722352564b145b648`.
The bounded sixteen-lane AW1/AW5 gate passed 1,089 operations, 1,075 direct
readbacks and 25 reset aborts. It includes six cold/warm resets one edge before,
on and after the final conversion commit, each followed by changed-base
recovery, plus N32 reset after the first accepted CRT row. Warm N2 explicitly
checks the ready-reservation interval (52 NTT + 108 CRT-phase clocks for these
frozen components). Full-N16 and full-N64 normal gates have passed twelve
operations each, including ten direct readbacks, successive squares, both
double choices, and a no-reset change to all-max base-1e9 digits. NTT16 measures
352,673 cold / 90,521 warm clocks; NTT64 measures 294,305 cold / 32,153 warm.
Both use conversion 4,105, roots 262,152 / zero, CRT 4,158 and exclusive carry
tail 4,147; the NTT phases are 78,111 and 19,743 respectively. These are exact
simulation-cycle measurements, not fitted clock rates or hardware throughput.
The completed 64-lane gate has 78 steps: 1,101 normal operations, 1,085 direct
readbacks and 25 reset aborts across AW1/AW5/AW16, plus a twelve-operation AW7
matching control. All nineteen distinct RTL faults were rejected. The bad
stream-mask model also passed two explicit child-error/quarantine checks;
normal arithmetic failure alone is not used as evidence of safe error handling.
The separate sixteen-lane AW1/AW5 and AW16 gates cover the same 1,101 normal
operations in total. An uncached/default-runtime1 AW1 gate passed 529 operations
and produced byte-identical oracle output/counters to the runtime8 AW1 gate.

The private thread adapter tests actual model/context thread counts, keys both
the generated-model flag and context macro, and runs fresh probes/oracles even
on cache hits. Compiler parallelism remains two; runtime8 uses an explicit
800% CPU/6GiB scope. An initial detached service was stopped with the entire
non-lingering user manager before its first model completed; it has no passing
report and is retained as interrupted infrastructure evidence. The successful
retry keeps its SSH session connected with keepalives and file-backed logs.
Separate normalized reports retain raw report paths/hashes, accept only integer
0/1 readback flags before converting to bool, and derive warm-cache status only
from coherent measured cache/load/hit/root-cycle counters.

## Isolated pair-step CRT follow-up

`genefer_square_core27_stream_pair` preserves the precision-stream top's ports,
parameters, fields, roots, conversion, carry and controller. Only the CRT child
changes to frozen `genefer_crt3_27_pair_pipe`; the private root module and top
are renamed to avoid collisions. The regression compares the entire executable
core/root body with the frozen 75eb ancestor after exactly those substitutions.
Its arithmetic profile is `sparse27-cached-stream-precision-pair-radix32-v1`.

Pair CRT has 96 stages and II1. This is **35** extra clocks versus the original
61-stage CRT actually present in the precision-stream ancestor; the separately
retimed 64-stage CRT would differ by32, but is not the comparison here. Residue
issue counts accepted memory requests, whereas write_count advances on CRT
out_valid. No fixed-latency address shift register exists in the controller.
Every issued request remains ordered, and the carry consumer keeps ready high
until the last ordered group is accepted. Therefore the longer drain cannot
reorder a row, start carry prematurely, or require extra output buffering.
Reset clears both controller and all CRT valid stages; the following operation
reloads digits and roots, while child-error quarantine still requires reset.

The private bench checks N32 cold/warm resets in the extended CRT interval,
immediately before first output, on last output, and during carry drain. Warm
N2 resets at the first accepted CRT input, specifically to expose a disconnected
CRT reset before its stale token finishes. Phase assertions expect full-size
CRT time ceil(N/16)+97 and warm N2 CRT time143. The initial AW1/AW5 gate passed
1,112 operations, 1,098 readbacks and34 reset aborts. Full-N NTT16 also passes
twelve operations/ten readbacks, measuring352,708 cold /90,556 warm clocks:
conversion4,105, roots262,152/zero, NTT78,111, CRT4,193 and carry4,147. The
extra35 clocks occur entirely in CRT drain, as expected. NTT64 also passes all
AW1/AW5/AW16 normal cases (1,124 operations, 1,108 readbacks, 34 resets), with
294,340 cold /32,188 warm full-size clocks; its NTT phase is19,743 and all other
phases equal NTT16. The final87-step gate passed all22 distinct RTL mutations,
a twelve-operation AW7 control and two explicit child-error quarantine cases.
The disconnected CRT-reset mutant passes earlier arithmetic but fails exactly
the new warm-N2 input-abort recovery at90 clocks, demonstrating that the test
detects an abandoned pipeline token. Same-arithmetic61-stage substitution and
one-edge-early valid are rejected by the explicit latency contract. The
uncached/default-runtime1 AW1 gate also passes532 operations,525 readbacks and
ten resets, with byte-identical output to runtime8. No fitted clock or speedup
is inferred from the isolated CRT's physical timing.

Frozen pair top SHA256 is
`a0f38ed2974be84a935c3c01ab33e3717bff0c5fdcce4eb8f664ee6fce7556b4`.
The final full64 raw report SHA256 is
`cc436768818b104f34cfa3b97ba663e5f683a076b2489d7f33d488f29fdc5aff`;
its strict normalized report retains that raw identity. Full16 and full64 use
the same source archive, SHA256
`6295448ae8e1c3093b2e67e82c2de7dc912d77fa03f5f4b0d9b0a47d40cd408f`.
The separate normalization tests reject either predecessor's CRT identity,
wrong stage count/type, incoherent cache metadata and altered arithmetic fields.

Two initial pair-gate preflights were rejected before any RTL model build: the
mechanical comparison first treated a final blank line as a logic change, then
the cache guard rejected an unkeyed PYTHONUNBUFFERED environment override.
The comparison now ignores trailing whitespace only, and the launcher uses
Python's command-line unbuffered option. Both rejected logs remain retained;
the successful small run is explicitly named `small16-v3`. Before the full
gate, its private harness additionally tightened the disk guard to reject
every new model build below10GiB, including non-full-size mutation models.
