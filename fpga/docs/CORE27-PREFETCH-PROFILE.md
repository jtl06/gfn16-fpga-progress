# Atomic27 square core with autonomous prefetch profiles

`genefer_square_core27_stream_prefetch` is an isolated candidate derived from
the frozen precision-stream core. It replaces cached root tables with the
verified generated-root prefetch engine and an autonomous compact-profile ROM
upload. The small whole-core, expanded fault, adapter, and full-size gates pass.
A whole-core physical fit remains pending.

The supported candidate profile is AW1 through AW16, 64 NTT arithmetic lanes,
and 16 conversion, CRT, and carry lanes. It preserves the original 61-stage
CRT, precision streaming carry, canonical digit reducers, and Montgomery input
converters. It does not combine pair CRT, input R² fusion, tiled routing, or
adjacent-stage fusion. All three fields retain Montgomery radix 2^32.

## Profile ownership and loading

Each field has a constant ROM producer and the frozen child's compact profile
RAM. A format1 profile has `(2*AW+2)*(4*64+1)` words: 8,738 at AW16. Both ROM
and uploaded RAM count toward memory use. Before implementation rounding,
each set occupies 838,848 bits across three fields; recurrence seeds and
control storage are additional. This is not a zero-storage root generator.

The profile carries phase0 Montgomery twist seeds, stage-specific forward and
inverse Montgomery seeds, ordinary phase3 inverse/postconversion seeds, and
their recurrence steps. The autonomous ROM uses the exact frozen field and
generator constants. No raw host digits are sent directly to the 27-bit
arithmetic: the existing full-row digit guard, reducer, and converter remain.

After the final conversion write, streaming carry starts as in the ancestor.
If the profile is already valid, the core starts the first NTT operation.
Otherwise it performs this sequence:

| State | Action |
| --- | --- |
| PROFILE_BEGIN | Pulse all three child profile-begin inputs. |
| PROFILE_ROM_START | Check loading state and start all three ROM producers. |
| PROFILE_STREAM | Consume equal, consecutive valid addresses across fields. |
| PROFILE_COMMIT | Commit on a separate edge after the final write. |
| PROFILE_CHECK | Require loaded, not loading, correct size and final address. |
| NTT_START | Start only after successful profile validation. |

ROM `done` means the last word has become available. On the following
PROFILE_STREAM edge, the child consumes that word and the core enters COMMIT.
The commit signal is therefore sampled one further edge later. It never
competes with the final profile write. Hardware guards detect field-valid,
done, address, size, canonical-word and child-profile errors; they clear the
cache flag and enter FAILED. Reset and digit reload are required after error.

A completed bundle survives all five arithmetic operations, later squareDup
starts, and base changes. Reset invalidates both producer eligibility and child
profile validity. Partial profiles cannot be reused after reset or failure.

## Narrow host adapter

`genefer_ntt_banked27_prefetch_host_engine` validates the original 16-aligned
address before rounding it down to a 64-word child beat. It shifts data and
mask into the selected quarter and captures that quarter for the registered
read response. Small-N clipping and zero-mask semantics remain unchanged.

An explicit profile request takes priority over all ordinary scalar or vector
host activity, including malformed requests. An invalid vector request still
suppresses scalar fallback when no profile request is present. Start and busy
retain the frozen child's suppression/rejection rules. The adapter has no
`root_we` compatibility alias: profile begin, write and commit are separate
ports with explicit format, field and size metadata.

## Counters and evidence interpretation

The five phase counters still sum exactly to `cycles`. `root_cycles` now counts
only the autonomous compact-profile loading states, not old full-table loads.
The separate diagnostics are:

- `profile_cache_valid`: complete coherent bundle available in all fields.
- `profile_loads` and `profile_hits`: per-square values zero or one.
- `profile_words_loaded`: accepted words per field, not three times that count.
- `seed_setup_cycles`: the sum of one field's completed child setup counters;
  all three values must agree at each operation completion.

Internal seed setup is already included in `ntt_cycles`. Adding the setup
diagnostic again would double-count it. Cold loading measures `WORDS+5` clocks;
warm loading has zero profile clocks and no profile writes.

The first passed small gate measured:

| N | Cold total | Warm total | Conversion | Warm roots | NTT | Warm CRT | Carry |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2 | 1,232 | 222 | 10 | 0 | 74 | 86 | 52 |
| 32 | 3,463 | 374 | 11 | 0 | 246 | 64 | 53 |

N2 cold CRT takes 63 clocks; its warm CRT phase takes 86 because it waits for
the still-running carry setup. The setup diagnostic is 22 at N2 and 122 at
N32, already included in the NTT column. These are RTL clocks, not wall-clock
benchmark results or fitted hardware throughput.

The immutable first small gate has 1,089 squares, 1,075 readbacks and 25 reset
aborts. Its report and exact source snapshot are under
`results/throughput-20260929/core27-stream-prefetch-small-v1/`. The independent
adapter gate has 159 steps and nine models, covering all three fields at AW1,
AW5 and AW8, profile and host arbitration, transforms, resets, size changes,
and combined whole-integer squares. Its archive is
`results/throughput-20260929/ntt27-prefetch-host-small-v1/`.

The expanded gate passes: 1,097 squares, 1,083 readbacks and 29 aborts, including
resets after the last profile word becomes available, after consumption, after
commit, and after the loaded check. Its 85 steps also include 12 AW7 adapter
control squares, 12 explicit child-error quarantine cases and 22 rejected
mutations: 20 core-control/arithmetic faults, an old-basis CRT, and an incorrect
adapter quarter. The archive is
`results/throughput-20260929/core27-stream-prefetch-small-v2/`; its raw report
SHA256 is `a183ab70855f59fde56cd48f2027350cffdfa9b3c90c1ba5f415f41e1bac804e`.
All 25 source, bench and helper hashes were rechecked before archiving. Full
N65536 testing used this same source snapshot, runtime eight-thread models
within a four-CPU-equivalent scope, and serialized two-worker builds. This is
correctness testing, not a wall-time benchmark.

The full-size gate passed all 12 squares and 10 readbacks: five recurrent random
cases, two special-minus-one cases, two maximum-digit base-1,000,000,000 cases
after a no-reset reload, and three autonomous steps with no intermediate host
readback. Reset boundaries alone divide the two simulation segments; the
changed-base reload and dependent chains were not split. Both segments used
the same verified executable and preserved all case IDs.

| N65536 state | Total | Conversion | Profile upload | NTT | CRT | Carry |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Cold | 41,711 | 4,105 | 8,743 | 20,558 | 4,158 | 4,147 |
| Warm | 32,968 | 4,105 | 0 | 20,558 | 4,158 | 4,147 |

The measured seed-setup diagnostic is 815 clocks, already included in NTT.
Warm profiles require no writes; cold profiles load 8,738 words per field.
Compared with the frozen cached precision-stream core's 32,153 warm clocks,
this candidate spends 815 additional warm clocks (about 2.5%). Its intended
benefit is reduced root-storage routing, not a lower warm cycle count. Only a
matched whole-core fit can establish whether the clock/resource tradeoff wins.

The final archive is `results/throughput-20260929/core27-stream-prefetch-full-v1/`.
Raw report SHA256:
`7f76432ccfd5778e75d65d5a3d1d7e8798cf3a9baaaf9b971f2ed1b958a43334`.
Normalized report SHA256:
`65156cf658ff8bddc1d729da30dc1a3257e606434adbf9a95e9cb61bdd3e1ef7`.
Its exact source archive is byte-identical to the small/fault gate's archive,
SHA256 `749734d79b018a79e26204450dfca329ea2e40e6422dd9f07306afa19857564f`.

## Source boundary

The core candidate SHA256 is
`9824a29d3b5e12f29f6e1793d84dde554d91037c0c054f070ba6fbc8cbaed540`;
the adapter is
`b9248c7201d64b6f1e5ef63d5f9c44edd7711df092cef055450ada3554a0a605`.
They select frozen prefetch engine `9381ff17...51c4a9c` and profile ROM
`072487e0...f1c754`, with the unchanged arithmetic and carry dependencies listed
in `reference/square_core27_stream_prefetch_regression.py`.

The separate report normalizer validates the exact architecture, atomic basis,
measured profile words/load/hit counters, phase sum and case coverage. It emits
`profile_cache_warm`, not the old cached-table `root_cache_warm` field, and
preserves the raw report with its SHA256. No cached-root result may be relabeled
as a prefetch result.

The standalone ROM's compile-time initialization needs the verified global
Quartus constant-loop limit of 10,000 at AW16. No RTL arithmetic replacement
is needed for that elaboration setting. A completed standalone ROM fit is not
evidence that the whole prefetch core meets timing or fits the device.
