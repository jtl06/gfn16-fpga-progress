# Isolated generated-root 27-bit NTT

This candidate replaces the full root memories in `genefer_ntt_banked27_engine` with a compact, explicitly uploaded seed profile and the frozen four-context `genefer_root_recurrence27` generator. It is a separate top, not selected by the square core. The frozen engine, recurrence generator and arithmetic helpers remain unchanged. No physical resource, timing or end-to-end speedup claim is made here.

## Contract

`genefer_ntt_banked27_generated_engine` retains the scalar/vector **data** host interface, operation selection, DIF/DIT ordering, optional inverse normalization, and operation counters. It deliberately has no arbitrary `root_we` interface. A root profile is coherent with the compile-time field and a single runtime transform size:

- Pulse `profile_begin` with `profile_size_log2` in 1..AW, `profile_modulus == P`, and `profile_format == 1`. This invalidates the old committed profile and starts an ordered upload.
- Write every profile word in exact address order, starting at zero, using `profile_we`, `profile_addr`, and full-width canonical `profile_data < P`. `profile_next_addr` identifies the next expected address.
- Pulse `profile_commit` after the last write. `profile_loaded` and `profile_loaded_size` then authorize rooted operations of that size.
- Bad begin metadata leaves the previous profile untouched. Bad writes pulse `profile_error`, do not mutate memory, and do not advance the address. An incomplete commit fails but permits completing the upload. Reset invalidates all profile metadata, without clearing RAM.
- Profile requests while busy pulse `profile_error` and are ignored. Idle `start` has priority and suppresses simultaneous profile requests. The separate data host ports retain their previous idle arbitration; they do not address the profile memory.

Within idle profile traffic, begin has priority over write, which has priority over commit. Data words retain the frozen engine's canonical `<P` caller contract, checked by simulation assertions; the data interface is not a raw radix-digit reducer. In particular, a digit near one billion must be reduced before entering this 27-bit-field engine.

The producer must supply mathematically coherent seeds and steps. Canonical values and metadata alone cannot prove a primitive root, a seed exponent, or a normalization factor. The supplied reference producer derives all roots from the selected field's generator. This is an explicit specialized API, not a reinterpretation of an arbitrary root cache.

The tested five-phase square starts with Montgomery-form data and returns ordinary residues after the ordinary post-root multiply. Format 1 does not fuse raw-digit Montgomery conversion into twist; doing so would require an explicitly different phase-0 representation/profile contract.

Operation 0 requires root phase 1 or 2 and a matching committed profile. Operation 2 requires phase 0 or 3 and the profile. Operation 1 (square) and operation 3 (scale) are root-free. Phase, DIF/DIT order, and inverse normalization remain independent controls. A normalized inverse operation 0 appends a root-free scale pass, even though its latched operation remains zero. Normalization/scale operands must be canonical.

## Profile layout and representation

Each key occupies `4*LANES + 1` 32-bit words. Context q, lane j is at `q*LANES+j`; the final word is the common recurrence step. All allocated words must be uploaded, including unused stage/lane entries, which can be zero.

| Key | Meaning | Seed representation |
| --- | --- | --- |
| 0 | Twist | `R * psi^(q*LANES+j)` |
| 1+s | Forward stage s | `R * omega^(B(q)+v(j)*2^h)` |
| 1+AW+s | Inverse stage s | `R * omega^-(B(q)+v(j)*2^h)` |
| 1+2*AW | Post-normalize and untwist | `N^-1 * psi^-(q*LANES+j)` — ordinary, not Montgomery |

Here `R=2^32`, `K=log2(2*LANES)`, `h=log2(N)-1-s`, and all values are reduced modulo P. For low stages `s<K`, B=0 and v=j. Otherwise `v=insert_zero(j,s mod K)` and

`B(g) = ((g & 1)*2^(s mod K) + ((g >> 1) mod 2^(s-K))*2^K)*2^h`.

The stage period is 1 for low stages and `2^(s-K+1)` otherwise. Seed contexts use q modulo that period. Periods at most four use an identity Montgomery step; longer periods use `R * alpha^(2^(K+h+1))`, alpha being the forward or inverse N-th root. The recurrence reseeds all four contexts after wrap, avoiding the otherwise incorrect minus-one factor. Pointwise steps are `R*psi^(+/-4*LANES)`, including the ordinary post-seed case.

At AW16 the uncompressed table is 2,210 words for LANES16 and 8,738 for LANES64. This is per field and includes all stage keys for one runtime N; changing N requires a fresh committed upload.

## Scheduling and alignment

Before each rooted stage/phase, the controller clears one recurrence seed bank, serially reads just the required contexts and active lanes from a single-port module-scoped profile RAM, reads the step, then starts the recurrence on a **separate** edge after the final seed write. Context requirements are the minimum of four, the group count and the nonzero period.

The recurrence output registers and data RAM q both update after the accepted group-request edge k. The butterfly consumes both on edge k+1. Logical roots are broadcast for low-stage reuse, then XOR-routed to the existing physical arithmetic lanes. BF and operation 2 advance data reads/group tags only on `issue_fire`; root-free paths do not wait for recurrence readiness. The original seven-clock data writeback drain is retained. Recurrence's four-clock drain completes inside it, before another stage's seed setup.

With U required seed words, the added serialized setup is U+4 clocks per rooted stage: one clear, U seed reads, one step read, one synchronous read-response drain, and one start. No recurrence bubbles are permitted during an issued stage. The bench checks exact cycles as well as every output, so a hidden recurring bubble fails accounting. `seed_setup_cycles` counts this addition; `wait_cycles` continues to count only the original seven-clock writeback drains. `root_reads` now counts generated root operands consumed, not full-root RAM accesses.

Cold profile upload is separate from operation busy time: the minimal upload is PROFILE_WORDS writes plus begin/commit edges. Warm repeated operations reuse that committed profile but still pay the serialized per-stage seed setup in this initial candidate. Future inactive-bank prefetch could hide some setup, but it is not implemented or credited here.

Measured full-N (65,536) arithmetic cycles in the initial gate:

| LANES | Unnormalized BF transform | Twist or post pass | Square pass | Complete warm five-phase square |
| --- | ---: | ---: | ---: | ---: |
| 16 | 33,663 (767 seed setup) | 4,171 (68 setup) | 4,103 | 79,771 |
| 64 | 10,687 (2,367 seed setup) | 1,291 (260 setup) | 1,031 | 24,987 |

The LANES64 frozen full-root engine's corresponding arithmetic count is 19,733. Thus this serialized candidate adds 5,254 clocks per warm square; it is not a throughput improvement by itself. It makes a different RAM/arithmetic tradeoff that may permit a feasible full system. The table excludes host data transfer, profile upload, CRT, carry and any physical clock penalty. Optional normalized inverse adds one root-free scale pass (1,031 clocks at LANES64).

## Storage and arithmetic tradeoff

The candidate retains N data words/field and replaces 3N root words with `(2*AW+2)*(4*LANES+1)` profile words. At AW16/LANES64, root RAM bits fall structurally from 6,291,456 to 279,616 per field, before FPGA packing. The recurrence additionally has two four-context seed banks, four live contexts, output registers and pipelines; these are not counted as profile RAM savings. It adds LANES sparse Montgomery pipelines per field. The exact RAM/DSP/register mapping and achievable clock require synthesis/fitting; none is inferred from these source-level counts.

## Validation status

The initial aethia full gate passed for all three fields, LANES16/64, explicit AW1/AW16, and every runtime N2..65,536. Each lane report has 69 passed steps, including all four forward/inverse and DIF/DIT combinations, inverse normalization, repeated five-phase negacyclic squares, malformed/stale profile rejection, busy host suppression, vector/scalar arbitration, reset aborts, and independent CRT/whole-integer checks. Reports are under `/home/jtl/gfn-fpga-lab/agent-work/ntt27-generated/fpga/artifacts/full-v1/lanes{16,64}/report.json`.

The final snapshot adds independent accepted-group/root-mask assertions, simultaneous start/profile controls, no-reset size/profile replacement, and expanded reset timing. The hardened full gate passed **72 steps per lane count**, totaling 1,242 completed operations, 11,016,012 per-coefficient checks, 924 reset aborts and 441,228 explicit host-fuzz checks. It includes no-reset N2→N32→N8→N2 profile replacement and first/last pipeline drain boundaries. Both lane reports passed the independent whole-integer CRT checks at AW1 and AW16.

Final full reports: `/home/jtl/gfn-fpga-lab/agent-work/ntt27-generated-final/fpga/artifacts/full-v2/lanes{16,64}/report.json`. The separate AW10/LANES16 gate passed all 29 steps under `artifacts/mutations-v2/lanes16/report.json`, including rejection of all ten injected faults: stale profile size, delayed bank routing, recurrence step, pointwise routing, inverse profile key, period wrap, seed-response tag, group advancement, incomplete commit and phase guard. Its N1,024 fixture exercises actual period-eight wrap, not only periods one/two/four. The candidate and dependencies below are now frozen for physical evaluation; no baseline core selection was changed.

The two regression invocations are `python3 -m reference.ntt27_generated_regression --output artifacts/full-v2` and `python3 -m reference.ntt27_generated_regression --quick --mutants --output artifacts/mutations-v2`, from the isolated FPGA directory after sourcing `tools/aethia-env.sh` from the main aethia lab. Both were run sequentially in a 6 GiB memory / zero-swap / 200% CPU scope, with two build workers. The script rejects simulation on other hosts. No Quartus run was performed for this candidate by this agent.

Source hashes for the final snapshot:

| File | SHA-256 |
| --- | --- |
| `genefer_ntt_banked27_generated_engine.sv` | `e21c86e5decde7b4e14a4cdd138c10f02b95c8beb147729d52ebf52d9bbefd1f` |
| `ntt_banked27_generated_engine.cpp` | `9dbd8e8ab3b2e2af0b20e706a7b11d5ef25c8e68bb3a8f93204ddb2f9f7f2aa3` |
| `ntt27_generated_regression.py` | `eff34190204798c696a961c718f038e709a96b21b622d725fafb33fbc8836736` |
| Frozen sparse Montgomery helper | `501d0ce309a3915f7aed0f3bde14ba1ee8d56ddc5f6abef1f2f5bb572d64db4b` |
| Frozen original banked27 engine/butterfly | `7ae89e702b671e3fbe8a1f90beb99ea595c832729e5e94232bf82515f1d74fe9` |
| Frozen `genefer_sdp_ram32.sv` | `993567fb68fdc216b9ff04489d1810f743b86564434e4b48261ad606b25d53b0` |
| Frozen `genefer_sp_ram.sv` | `b97d2f43db1b1e1aa60b9b7fc2b720af1e302bd5ff9e35854c89b30e5fb610df` |
| Frozen `genefer_root_recurrence27.sv` | `c8adc265915192807efee46799a782f1649a4408313098baaed8b4a808afeb9e` |

Dependencies are the frozen sparse Montgomery helper, frozen original banked27 source (for its butterfly definition only), `genefer_sdp_ram32`, `genefer_sp_ram`, and `genefer_root_recurrence27`. Select this candidate explicitly as top; including the frozen engine source does not instantiate its root memories.
