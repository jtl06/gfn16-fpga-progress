# Opt-in core27 simulator runtime threads

`reference/square_core27_threaded_regression.py` is a new harness; it does not
edit the frozen core, existing bench, earlier harnesses, or prior reports.
`--runtime-threads 1` is the default. The only other accepted value is 8.
The new `rtl/tb/square_core27_threaded.cpp` includes the original bigint-oracle
bench unchanged and sets `VerilatedContext` before any DUT is constructed.

These are simulation runtime threads, not Quartus workers, compiler workers,
NTT lanes, or an FPGA clock/performance setting. Compiles remain `-j 2`; the
per-process address-space limit remains 6 GiB. Full-N compile misses reject when
less than 10 GiB disk space remains. Host scheduling and CPU quota are separate
from model thread count; the parent chooses when an eight-thread job may run.

## Identity and safety

Each cached or uncached model executes a fresh runtime probe before its oracle.
The probe checks compiled model threads, actual context threads, and the
wrapper's expected count. Probe-only override inputs exercise insufficient and
excess context sizing without allowing an override during a correctness run.

The executable cache is optional. Its identity includes the actual ordered RTL
list, including any mutant file; wrapper and original bench; explicit Verilator
`--threads` and context macro; parameters, optimization flags, and working
directory; audited cache-helper source; compiler/tool/runtime/header/library
fingerprints and relevant environment. The existing shared cache-context
helper is imported unchanged and custom untracked compiler overrides fail
closed. Compiler-discovered dependencies must belong to that tracked closure.
One-thread and eight-thread binaries cannot share a key. The model probe also
rejects an executable whose runtime count disagrees with the requested profile.

Only build products are reused. Context rejection checks and bigint correctness
oracles execute afresh on cache hits. Cache provenance, executable hashes, build
flags, runtime count, and compiler-worker count remain distinct report fields.

## Preserved arithmetic gates

The harness independently checks primality/root order, all profile constants,
radix 2^32, and the centered CRT bound before compilation. It retains the same
whole-integer vector generator and all 15 RTL fault mechanisms from the frozen
core27 gate. A matching unmutated AW7 control accompanies the host-quarter
fault. Initial RTL assertions remain in actual oracle runs; the thread probe
constructs a model without evaluating RTL.

Full-N vectors are split only at resetting LOAD boundaries using the validated
recovery segmenter. Concatenating segments reproduces the original command
bytes; LOAD_KEEP chains remain indivisible and completed case IDs must match
the original sequence. This avoids making a longer process timeout part of the
threading feature. Every command retains the 600-second cap, including optional
compile-lock waiting; lock-wait duration is not a simulation-speed measurement.

Typical future invocation on aethia, after the host scheduler permits it:

```sh
python3 -m reference.square_core27_threaded_regression \
  --output artifacts/new-unique-run --aw 16 --lanes 64 \
  --runtime-threads 8 --build-cache artifacts/core27-runtime-cache-v1 \
  --compile-lock /home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/compile.lock
```

Add `--thread-contract-tests` for mismatch/domain probes and focused cache-key
unit tests; add `--mutations` for the 15 distinct RTL fault gates. Eight-thread
selection is explicit, never inferred from build-worker count or host CPU count.

## Completed verification

All six reports passed under the aethia isolated directory
`/home/jtl/gfn-fpga-lab/agent-work/square-core27/fpga/artifacts/`:

- `runtime1-cold-v1` / `runtime1-warm-v1`: one build then an exact cache hit.
- `runtime8-cold-v1` / `runtime8-warm-v1`: a different build key, then its exact hit.
- `runtime-default-uncached-v1`: omitting both runtime selection and cache uses
  one thread, compiles freshly, and produces the same complete oracle output.
- `runtime8-full-v1`: 55 steps, all 12 N65,536 squares, a 12-square AW7 control,
  all 15 distinct RTL faults, and 17 distinct executable-cache identities.

Each small-N run independently executed 529 squares, 522 readbacks, and nine
reset aborts. All five small-N outputs are byte-identical; counters also match
the earlier frozen gate. Every relevant context/model probe executed again,
including on warm cache hits. Both undersized and oversized contexts reject,
as does unsupported context size 2. The five targeted unit tests cover invalid
counts, flag/report mismatches, actual executable probe mismatch, independent
compiler/memory bounds, and cache isolation under thread/RTL/wrapper changes.

The new full-N report's metrics exactly match the prior frozen gate: 36,318
warm and 298,470 cold clocks at 64 NTT / 16 IO lanes. Its SHA256 is
`de6bf16f14c76e8c630fffc91ae0198007b2606adfad0d818476efa18c8b49a1`.
These correctness runs shared the host with other regression work and are not
additional simulation-speed measurements. The earlier quiet benchmark remains
the separate evidence for the measured 3.20x full-N simulation improvement.

Frozen new-source identities:

- Harness: `09d5a77025c62e88cc4d8df7d829f602fa7053e572ae29515842c414022624fb`.
- Wrapper: `9968b50130c5718fc1937bac12f5d1e789da72d6d594b7873f7e9095ca429c20`.
- Tests: `ac93debee0ec1cba4b2ee438dc2d201955012a8086ed80fb1435e8ee6f84a3fb`.

An independent read-only review found no context-ordering or build-cache
identity issue. No original RTL, oracle bench, generic core harness, cache
utility, production default, or earlier report was changed.
