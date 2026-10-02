# GFN16 validation and GFN17 Mega discovery plan

Decision: 2026-09-23. Build a Genefer-compatible arithmetic backend for the
Catapult v3 / Arria-10 experiment. Validate a complete GFN16 candidate first;
GFN17 Mega is the eventual discovery target. Preserve the earlier GIMPS TF
experiment as reference work. Physical fit, speed, and PrimeGrid acceptance
are not yet established. Heavy development remains deferred to the Linux PC.

## Memory budget

The pinned Genefer commit is recorded in `../config/upstreams.lock.json`.
For S3, N = 131072, and three arithmetic registers, its OpenCL allocation is:

| Buffer | Formula | GFN17 logical size |
| --- | --- | ---: |
| Arithmetic registers z | 3 registers * 3 fields * N * 4 bytes | 4.50 MiB |
| Prepared multiplicand zp | 3 fields * N * 4 bytes | 1.50 MiB |
| Transform roots w | 3 fields * N * 4 bytes | 1.50 MiB |
| Carry scratch c | N / 4 * 8 bytes | 0.25 MiB |
| Total | | 7.75 MiB |

The same three-register allocation is 3.875 MiB at GFN16. Four arithmetic
registers increase these totals to 9.25 MiB and 4.625 MiB respectively.
These figures exclude proof checkpoint storage, host buffers, and FPGA
transport/banking overhead; they are not a mathematical minimum.

The provisional GX1150 offers approximately 6.625 MiB in M20Ks and 1.59 MiB
in distributed MLABs. These are not one interchangeable memory pool: port
requirements, width/depth choices, replication, and routing determine usable
capacity and bandwidth. The three-register GFN17 layout exceeds nominal
M20K capacity by 1.125 MiB before those overheads.

## Layout experiments in order

1. Preserve the three arithmetic registers on-chip where feasible. Establish
   their exact lifetimes and access schedule through squaring, Gerbicz checks,
   proof construction, and checkpoint restore.
2. Evaluate staged root generation or smaller root tables. Removing a full
   1.50 MiB table would reduce logical allocation to 6.25 MiB, but replacement
   tables, arithmetic, FIFOs, and physical memory packing may exceed the
   remaining margin. This is a hypothesis to fit, not an achieved design.
3. Evaluate whether the prepared multiplicand can share storage with buffers
   whose lifetimes do not overlap. Do not alias memory until the complete
   operation schedule proves that no live value is overwritten.
4. Use MLABs selectively for suitable small tables and FIFOs. Packing 31-bit
   values instead of 32-bit words saves only 3.125% of those arrays and may
   save no physical blocks; it cannot by itself close the capacity gap.
5. If necessary, use board DDR for selected buffers or blocked transforms.
   Count bytes transferred per modular square and model sustained throughput.
   Capacity is ample; recurring transfer bandwidth and controller bring-up
   are the costs. Host RAM is suitable for infrequent checkpoints, not a
   substitute for fast local storage at every butterfly.

At the existing depth-7 planning setting, 128 canonical GFN17 checkpoints
at N * 4 bytes each occupy 64 MiB. The plan spills these to host RAM (or later
board DDR) rather than retaining every checkpoint in on-chip RNS form.
Conversion and transfer costs still need measurement; 64 MiB is the canonical
checkpoint payload, not a guarantee of total proof or runtime memory size.

## PrimeGrid allocation and proof compatibility

Use BOINC's assigned candidates and deadlines. Do not independently select
live candidates already assigned to other volunteers. Keep the queue small
until measured runtime is known; expired or failed work can be reissued.

Prefer adding an FPGA arithmetic backend to Genefer while preserving its
host-side BOINC handling, error checks, proof schedule, serialization, and
checkpoint/restart semantics. A correct final residue alone is insufficient
for the intended proof-enabled integration.

Genefer 22+ uses Gerbicz-Li error checking and Pietrzak-Li modular-exponentiation
proofs. These let a verifier check the computation with substantially less
work than a complete independent rerun. A computation proof does not itself
turn a probable-prime result into a primality proof; promising hits still go
through the project's primality-confirmation procedure.

Qualification uses offline known cases and the stock Genefer verifier first.
Then seek a coordinated small pilot with PrimeGrid before production use.
The target is normal project verification overhead, with no extra full reruns
caused by missing proofs, invalid results, or expired assignments. No pilot,
contact, work request, or submission has been performed by this planning step.

## Next concrete gate

On the Linux build host: produce an explicit bank/port/lifetime map for GFN16
and GFN17, then a Quartus fit for the chosen memory architecture and arithmetic
lane count. Measure modular-square latency and verify complete residues and
proofs against Genefer. Only then estimate candidates/day or discovery odds.

## Sources

- [Pinned Genefer buffer allocation](https://github.com/galloty/genefer22/blob/d5060c61090942f42a908492628eba13ebd7cd82/src/transformGPU.h)
- [Existing hardware and arithmetic analysis](ARCHITECTURE.md)
- [Genefer proof scheme and BOINC interface](https://github.com/galloty/genefer22)
- [PrimeGrid Genefer application testing precedent](https://www.primegrid.com/forum_thread.php?id=11303&menu=top)
- [PrimeGrid explanation of computation proofs in LLR2](https://www.primegrid.com/forum_thread.php?id=9303)
- [PrimeGrid GFN certificate/primality validation pipeline](https://www.primegrid.com/forum_thread.php?id=13687&menu=left)
