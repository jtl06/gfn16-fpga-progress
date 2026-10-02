# Four-point shared-butterfly component

Status: full source-hashed component gate passed. This is
an isolated dependency-ordered four-point datapath, **not a banked NTT**.
It is not selected by any engine or square core. No physical timing, area,
power, or end-to-end throughput result follows from this gate.

## Scope and unchanged dependencies

`genefer_ntt_pair4_datapath.sv` reuses two actual frozen six-stage
`genefer_ntt_difdit_butterfly27` instances for both layers. Each butterfly
contains the frozen four-stage sparse Montgomery27 multiplier. The radix is
2^32, not 2^27. Only P/Q change between the three supported atomic27 fields;
the test oracle supplies explicit primitive generators 3/5/10.

- Schedule: `genefer_ntt_pair_schedule.sv`, SHA256
  `89c17cad846d9db0fa44e768a2f052b193d657fe633f425c77e9441b0512aa81`.
- Butterfly-containing source: `genefer_ntt_banked27_engine.sv`, SHA256
  `7ae89e702b671e3fbe8a1f90beb99ea595c832729e5e94232bf82515f1d74fe9`.
- Sparse multiplier: `genefer_montgomery_mul27_sparse_pipe.sv`, SHA256
  `501d0ce309a3915f7aed0f3bde14ba1ee8d56ddc5f6abef1f2f5bb572d64db4b`.

These files are unchanged. The containing banked engine is not instantiated;
only its butterfly submodule is elaborated by this component.

## Interface and temporal contract

Words `[a,b,c,d]` are in four-point dependency order, lane0 in the low32 bits.
They are not physical RAM-bank order. The caller provides canonical<P words
in Montgomery format. Every root word is also canonical and R-scaled.
The component assumes the existing canonical-input contract; it does not add
a raw-digit reducer or a production input-validation interface.

Data and roots must be available before their requested sampled read edge.
Separate internal input/root registers model the one-clock response boundary.
There is no external response-valid, ready or stall protocol. A real banked
RAM/controller integration must account for this contract rather than add a
second unplanned response cycle.

For group g, relative to its operation's first sampled read edge:

| Event | Edge |
| --- | ---: |
| Read first-layer data and roots | 2g |
| Accept first-layer butterfly inputs | 2g+1 |
| Hold first-layer result; read second-layer roots | 2g+7 |
| Accept second-layer inputs | 2g+8 |
| Commit final four-point result | 2g+14 |

There is one held four-word intermediate frame, overwritten every two clocks
and consumed one clock after capture. First/second issues occupy opposite
clock parities. Group initiation interval is two clocks, not one. An operation
with G groups has exactly 2G+13 active edges, plus the preceding start/setup
edge. Counts 1..2^GROUP_AW are supported; zero and larger counts reject.
GROUP_AW defaults to12, permitting4096 groups. Widths1/4/12 are gated.

Busy-time start, count and mode changes do not alter the active operation.
Done is a one-clock pulse. Reset discards all pending eligibility and tags.
An idle start clears sticky datapath fault, matching the schedule's recovery
contract; the gate tests immediate no-reset restarts as well as reset recovery.

## Arithmetic/layout oracle

The C++ scoreboard uses ordinary uint64 modular multiplication and addition,
independent of the hardware Montgomery reduction. DIF first pairs (a,c)/(b,d)
and then pairs the first-layer sums and differences. DIT first pairs
(a,b)/(c,d), then pairs the sums and differences with strided final placement.
Both use four ordinary radix2 butterfly evaluations; only initial pairing and
final placement differ. The redundant mode ternaries in the original draft's
second-layer oracle were removed.

Even-numbered groups use actual adjacent top-stage roots for N65536, with both
forward and inverse signs. Odd groups use arbitrary canonical roots, including
zero/one/P−1. Canonical data includes zero/P−1 groups and reproducible random
values. Outputs are compared after independent R encoding. This does not test
whole-transform ordering, negacyclic twist, CRT, carry, or integer squaring.

## Fail-closed commit and negative tests

Write eligibility checks the current schedule commit, both butterfly result
valids, delayed token valid/kind, matching group tag, no sticky datapath fault,
and no schedule error. Merely checking last cycle's sticky fault would allow
one wrong-token write before the error is latched.

Three positive fault-injection variants corrupt the terminal group, kind or
valid tag only for second-layer DIF results. The scoreboard checks write_valid
*before* the prospective commit edge, requires zero writes, then observes the
sticky error. A DIT operation restarts cleanly without reset. Each corresponding
negative variant removes its same-edge guard and must be rejected specifically
for an unsafe write, not a later generic error.

Additional mutants cover final write tag, held/write/input layout, root lane,
mode, shortened tag delay, root-response tag and reset fault. No frozen schedule
or arithmetic helper is mutated. These tests demonstrate specific faults, not
exhaustive formal safety for arbitrary corruption.

## Reproduction and evidence boundary

Run on aethia only from the isolated fpga directory:

```
python3 -m reference.ntt_pair4_datapath_regression \
  --output artifacts/full-v1 \
  --compile-lock /home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/compile.lock
```

The runner uses fresh output roots, j2, runtime1, a6 GiB address-space cap and
a10 GiB free-disk guard. The enclosing scope sets CPU200% and MemoryMax6G.
Each build independently acquires/releases the shared lock; lock wait is
separate from its240-second command timeout. Reports preserve source/tool/
executable/log hashes and failed runs. No cached correctness result is used.

Physical bank mapping, root-port scheduling, routing registers, stage changes,
small-N fallback, full-engine reset contracts and exact full-transform results
remain future integration work. Lower modeled RAM traffic is not measured
speedup and does not establish the feasibility of a spatially doubled array.

## Frozen completed gate

Remote report:
`/home/jtl/gfn-fpga-lab/agent-work/ntt-pair4/fpga/artifacts/full-v1/report.json`.
Its SHA256 is
`381b16f2a08f7ac3dcb5a1f45ecc17d0ccbfe4294a00a4b7c67ee4b3538866aa`.
Exact source snapshot SHA256:
`1e711f3688a48df44eacb2916132d0ef0367f75698e0a3773909e94ba86e11f0`.

All 50 recorded steps passed, including 24 builds and 12 expected negative
tests. The nine ordinary models cover all three fields at widths 1/4/12;
three additional fault-injection models prove same-edge containment and
restart. Aggregate evidence is 645 completed operations (including three
intentionally faulted operations), 348 reset boundaries/aborts, 83,127 checked
four-word commits, 18 invalid-count rejections, and 1,202,088 scoreboard checks.
At G=4096 the checked counter is 8,205 active clocks, or 8,206 edges including
the initial start/setup edge. This is component timing, not whole-NTT timing.

Final source identities:

- Datapath:
  `3976fb0586cb01c14f15da80dd70f42aff3a0d7f5f912eeb29fc4ca7b1ea10d3`.
- Bench:
  `2c59a390d2deea28bf6bc516ffeff7c979ac55be1fe152fadc937a2017638f6b`.
- Harness:
  `65ef202e202c29ce80fe1555ec699c17ebebda67f575452e17c56c31cd4f4d4e`.

After completion, all reported source, executable, log, mutation and snapshot
hashes were independently rechecked on aethia. A separate read-only review
confirmed the commit guard and unchanged DIF/DIT mappings/tag alignment.
No candidate or frozen RTL changed after this completed gate.
