# Isolated cached-root NTT27 routing pipeline

This candidate addresses the RAM-to-butterfly routing chain seen in the fitted
FAST16 core. It is not selected by a square core, and its clock benefit has not
been measured. The existing cached-root and generated-root engines are unchanged.

The new `genefer_ntt_banked27_routepipe_engine` registers the root permutation
after XOR/rotation, before broadcast and the data-bank XOR/pair selection. Data
operands and pointwise roots are delayed alongside that register. Pairing,
orientation, stage/broadcast metadata, request valids, and RAM writeback address
and bank-half tags are advanced consistently. The arithmetic helper itself is
the frozen butterfly in `genefer_ntt_banked27_engine.sv`.

RAM read-to-write latency grows from seven to eight clocks. Issuing remains one
group per clock. Scalar/vector host read latency and cached-root upload contracts
are unchanged. Montgomery radix remains 2^32, with the same three27-bit fields;
all host inputs must be canonical residues, not raw radix digits.

Expected extra busy cycles are one per transform stage and one per pointwise
pass. A full-N five-phase square therefore adds35 cycles, structurally projecting
L16 arithmetic78101→78136 and L64 arithmetic19733→19768. These are scheduling
predictions until the full-N gate finishes, not measured speedups. Registers and
physical routing may offset any timing gain; fitting is required to decide.

The first full-N L16/P1 run now measures32,912 cycles per unnormalized transform
and4,104 per pointwise pass, confirming78,136 arithmetic cycles per five-phase
square for that configuration. It passed20 operations and1,310,720 coefficient
checks, plus the independent N65536 direction/order and reset tests. Other
fields/lane widths and mutation gates remain pending; this is not a full freeze.

The initial N16/L16/P1 gate passed all six steps, including cached squares,
independent transform directions/orders, canonical input rejection and host
fuzzing. The report is archived under
`results/throughput-20260929/ntt27-routepipe/quick-report.json`.
The full gate is running on aethia, covering L16/L64, all three fields,
AW1/AW4/AW16 and all runtime sizes, whole-integer CRT squares, maximum base,
reset aborts and injected arithmetic/routing/tag faults. Mutation fixtures use
N1024 so multiple rows and both bank halves are actually exercised. No full
validation or physical-fit claim is made while this run is pending.

Independent read-only review confirmed the edge alignment: read at t, route
registers at t+1, butterfly consumption at t+2, actual RAM writeback at t+8.
Stage/operation descriptors remain stable through the final writeback. Reset
invalidates both route and arithmetic valids, so unreset operand registers cannot
commit stale data. This review supplements, but does not replace, the full gates.

Candidate identities at full-gate launch:

- RTL: `69a665dd60f725a6e401ed5e0aee7457f260080be16531e5e83e256c312c8154`
- Bench: `4d8c4e7e1d35b8694cc7a287761f5d2055d5978b641afe2ddb43819c8f52821c`
- Full-gate harness: `a7e80c520a14337cbb434474bbbc49105b9567153d59d356265ad439c5536101`

The smoke report contains its own earlier harness identity; RTL and bench are
unchanged. Remote run directory:
`/home/jtl/gfn-fpga-lab/agent-work/ntt27-routepipe/fpga/artifacts/full-v1`.
Synthesis targets `ntt27_routepipe16` and `ntt27_routepipe64` merely prepare fresh
source snapshots. Do not fit them until the matching correctness gate is complete.

The L16 full gate is now complete and passed, including all three fields,
AW1/AW4/AW16, every runtime transform size, whole-integer reconstruction,
reset/host/canonical checks and all eleven injected faults. Its report is
archived in `results/throughput-20260929/ntt27-routepipe/lanes16/report.json`.
The L16 source-matched 5 ns physical project is prepared but not launched;
L64 validation is still running. No fitted timing gain is claimed.
