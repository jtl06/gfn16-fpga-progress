# Atomic27 folded-routing core experiment

This is an isolated routing substitution, not a new arithmetic profile. The new
`genefer_square_core27_folded` is cloned from frozen atomic27 core
`47f61c263ddcfe6f707ab65fdaadf5a412528692f99a3c9bd3dc123137b435ce`.
Only the top/private-root names and the selected host wrapper change. The new
`genefer_ntt_banked27_folded_host_engine` has the original scalar/root/vector
interface and selects frozen folded NTT engine
`475a7500e58485c943961729334f8c03e35eb52095657813f8c770d29cb5167c`.

The regression verifies byte-exact equivalence after these explicit renames.
The baseline and precision-stream core are not edited. Parameters remain AW
1..16 and NTT_LANES 16 or 64; host/conversion/CRT/carry width remains 16.

## Unchanged arithmetic and scheduling

- P = 104857601, 69206017, 67239937; Montgomery radix remains 2^32.
- Checked digit reducer followed by sparse Montgomery conversion; no raw digit
  truncation, no input-conversion fusion.
- Four cached root phases with the same formats and reset invalidation.
- Frozen CRT27 and nonstreaming carry-prefix-vector-pipe-v2.
- Ordered last conversion write, separate NTT start, CRT, then carry.
- Whole-row domain checking, reset abort, failure quarantine, no-host chaining.
- The private root generator still uses the generic32 multiplier; this experiment
  does not claim all multipliers are sparse27.

## Verified cycle accounting

For N = 2^AW and L arithmetic lanes, the five NTT operations have combined core
phase count

`2*AW*(ceil(N/(2*L)) + 9) + 3*(ceil(N/L) + 8) + 10`.

The extra registered routing edge adds `2*AW+3` clocks versus the frozen cached
atomic27 baseline. Other phase counts should be unchanged. At N=65536 this is
35 clocks: measured warm totals 94,721 (16/16) and 36,353 (64/16), with unchanged
262,152-clock cold root fill. Measured cold totals are 356,873 and 298,505.
All 2,168 normal small/full cases match the frozen baseline in every other
phase, cache count, base, carry-pass count and readback decision.

## Evidence and scope

The pre-existing standalone folded64 gate was independently checked on aethia:
`agent-work/ntt27-folded/fpga/artifacts/full-v1/lanes64/report.json`, passed 84
steps, report SHA256
`d1c98dfe54405ddbc8f5972aa5da7805e8f04c3aab2a2c75dc90c91d1e749261`.

The private integration harness uses the unchanged whole-integer oracle,
equivalent renamed bench, explicit VerilatedContext/model thread identity,
source snapshots, fresh output directories, exact source/cache keys, and fresh
oracle execution. Full-N vectors split only at validated resetting LOAD
boundaries, preserving all LOAD_KEEP chains. Builds use two workers and 6 GiB;
runtime threads 1 (default) or 8 are independent settings.

Completed gates: small and full-N 16/16 and 64/16, cold/warm repeated and doubled
squares, max-base and special-minus-one inputs, reset recovery, host arbitration,
no-host chains, inherited atomic-profile mutations, and three folded-routing
mutations. Routing mutations need AW10 rather than AW7 at 64 lanes, so multiple
groups and nontrivial rotations occur; an unmodified AW10 control runs first.

Final evidence lives under aethia
`/home/jtl/gfn-fpga-lab/agent-work/square-core27-folded/fpga/artifacts/`:

- `small16-v1/report.json`: 1,072 squares, 18 reset aborts; SHA256
  `b63ec6cb5a7e7688d4a3fa3aebab76430b70d0dd5669a83a22e71ee47d260677`.
- `full16-v1/report.json`: 12 full-N squares; SHA256
  `ebf2a7c94a7e43938ccbff34efed91c6252f6e25478e09fb1f8a7eb48b4d7664`.
- `full64-v1/report.json`: 1,084 normal squares, 18 reset aborts, 24 additional
  unmodified control squares, 18 distinct rejected faults; SHA256
  `0c61e172211bdf48ffafe73773868cc3551de562d66dec83b7fcb2561b2f1f5a`.
- `final-gate-v1.json`: consolidated source/executable checks, 2,168 exact
  baseline comparisons, all 18 fault identities; SHA256
  `19756dd563fe1dae93f41d8c237d2f87e253e719281f54cc7d903ce8d91f736d`.

Passed-only normalized reports retain a SHA link to raw evidence. Ancestor
proof files are under `ancestor_sources`, not the 14-file compiled RTL closure.
Readback is strictly normalized from bool or integer zero/one; cache state,
load/hit counts, root cycles and phase accounting are validated. Five dedicated
normalizer tests passed. Raw and early normalized reports were preserved.

Frozen top SHA256:
`081d352e44b848ea28c920da7c3e0733291fb7e5dc504927d7fce8f686715c70`.
Frozen host-wrapper SHA256:
`dced5fb3e8eebe6ee1679153ef6b977e61e5f2c208a3f3262fd27fd57115ffc3`.

No integrated area, clock, or throughput improvement is claimed before physical
implementation. The folded16 standalone comparison showed lower ALMs than the
routepipe16 candidate, not a measured saving for this full64 core. The baseline
core uses the earlier seven-clock engine, so this substitution includes both the
registered route boundary and folded XOR routing.

## Whole16 physical result, 2026-09-30

The four-worker100MHz probe completed successfully as a tool flow, but missed
setup: reported Fmax86.36MHz, setup-1.579ns, hold+0.017ns. Raw placement:
188959ALMs,946DSPs,132283registers,30670848RAMbits and1675M20Ks. Adjusted
ALMs171861 andDSPs692 are distinct packing estimates.

`results/throughput-20260929/core27-folded-ntt16-fit/` preserves the source,
execution context/result, reports and strict matched comparison. Its warm
94721 clocks are35 more than the original cached16 core. At explicit assumed
planning clocks80→85MHz, the projected chain throughput ratio is1.0621074.
This is not an85MHz refit or board measurement. The precision-stream16 core is
the stronger current whole16 result; no new16-lane optimization campaign is
implied. There is still no folded whole64 fitted-clock claim.
