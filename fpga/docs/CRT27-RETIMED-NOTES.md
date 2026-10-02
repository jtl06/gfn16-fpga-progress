# Retimed CRT27 modular differences

This isolated candidate targets the dependent arithmetic at the CRT input,
motivated by the fitted FAST16 RAM-to-delta2 critical path. It does not replace
the frozen CRT27 or change any square-core selection. A physical timing benefit
is unproven until fitting and eventual integration.

The initial canonical r1 reduction modulo P2 is registered along with r2 and
the original r1/r3 payload. The next edge registers the difference r2-r1_mod2
in28 bits; the following edge corrects a negative difference by adding P2.
Relative to the frozen implementation, this adds two stages before multiplication.
The later delta3 subtraction and sign correction are similarly separated by
one additional register, with x12 payload and valid delayed identically.

Differences of two canonical27-bit residues lie strictly between -2^27 and
2^27, so signed28-bit representation is exact. The sign bit selects a single
modulus addition; corrected residues are in [0,P). Simulation checks the bounds
at the corresponding valid edges. All CRT constants, multipliers, modular
reducers, reconstruction and centered-output convention are unchanged.

Latency is64 stages: input accepted at edge k produces a registered response
after edge k+63, versus k+60 previously. Initiation interval remains one.
Added input and delta3 valid registers reset alongside the existing pipeline;
payload registers may be unspecified when invalid. Invalid-cycle output holds
and immediate reset cancellation preserve the public interface.

The initial independent integer-oracle test passed25,833 outputs,4,891 canceled
tokens and11,470 invalid-cycle hold checks across37,303 clocks. It includes
canonical corners, centered-modulus boundaries, exact r1 moduloP2 boundaries,
random residues, bubbles and resets after every pipeline age1..65. All nine
noncanonical input probes were rejected. The subsequently completed mutation
gate and frozen source identities are recorded below.

Files: `rtl/kernel/genefer_crt3_27_retimed_pipe.sv`,
`rtl/tb/crt3_27_retimed_pipe.cpp`, and
`reference/crt27_retimed_regression.py`. Sole RTL dependency is the frozen
`genefer_mod64_pipe.sv`. Remote gate:
`/home/jtl/gfn-fpga-lab/agent-work/crt27-retimed/fpga/artifacts/full-v1`.

Final gate: all45 steps passed, including rejection of all17 injected faults.
The report and baseline oracle log are archived in
`results/throughput-20260929/crt27-retimed/`. Independent read-only review found
the28-bit signed differences, payload tags, valid propagation and reset behavior
consistent with64-stage latency. No RTL correction was needed during the gate.

Frozen identities:

- RTL: `f38bb21304104b63b44513a9b21816a97b1448bc4293fac48868f408134e4479`
- Reducer dependency: `e582dba87dce51794a38039fd02574f443c53750bcafc8fcb1f4d0d50fc60839`
- Bench: `05717320fcf0e609fa71167c5e68ca50ef193fedc6f41c8cdeed5b76674bce00`
- Harness: `8b5875fbde8820b880384fe1de3df74fc0a3a6b916f0a9b3ff4c8a8d45532beb`

The source-matched `crt27_retimed-200-v1` project is prepared at5ns but not
launched. The82-test synthesis/evidence suite passed. Timing, resources and
whole-core impact remain unmeasured for this candidate.
