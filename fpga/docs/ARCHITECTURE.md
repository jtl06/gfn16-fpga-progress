# Arithmetic and backend architecture

Selected direction (2026-09-23): validate GFN16 first, then implement GFN17
Mega. [GFN17-PLAN.md](GFN17-PLAN.md) records the memory budget, open design
questions, and PrimeGrid proof compatibility requirements. The buffer sizes
below describe the pinned upstream layout; they are not a fitted FPGA design.

## Mathematical contract

For GFN-16, `N = 65,536` and the candidate is:

```text
M = b^N + 1
```

The Fermat PRP residue is `2^(M-1) mod M`.  Genefer scans the bits of
`b^N = M-1` from most significant to least significant and repeatedly applies:

```text
r = r^2 mod M           when bit = 0
r = 2*r^2 mod M         when bit = 1
```

At the digit level, multiplication is a negacyclic convolution because
`x^N = -1`, followed by CRT reconstruction and radix-`b` carry normalization.
The reference package supplies a conventional twisted negacyclic NTT.  Its
intermediate layout is intentionally hardware-neutral and will not match
Genefer's optimized right-angle/z-transform stages; canonical digits and final
residues are the differential-test boundaries.

## Initial fixed target

Current-range GFN-16 bases use the `s3` profile: three signed-family primes.
The first RTL should therefore optimize `s3` only while the software reference
keeps all four upstream selection profiles testable.

### Why GFN-16 before GFN-17

Both live PrimeGrid ranges currently select S3, so GFN-17 does not reduce the
number or width of modular fields.  It only doubles the transform:

| Property | GFN-16 | GFN-17 Mega |
| --- | ---: | ---: |
| Transform elements | 65,536 | 131,072 |
| One S3 register | 0.75 MiB | 1.5 MiB |
| Upstream three-register no-`USE_WI` reported estimate | 3.5 MiB | 7.0 MiB |
| Actual OpenCL buffers (`z` + multiplicand + roots + carry) | 3.875 MiB | 7.75 MiB |
| Current candidate size | about 575k digits | about 1.14M digits |

An Arria-10 GX1150 has 2,713 M20Ks: 53.0 Mib, or 6.625 MiB, plus about
12.7 Mib (1.59 MiB) of MLAB memory.
GFN-16 leaves useful M20K margin for banking and FIFOs. The equivalent GFN-17
buffer set already exceeds M20K capacity before replication/banking overhead;
packing only used roots, using MLABs, recomputing roots, or external memory may
rescue it, but each makes the first implementation harder.

At the current live leading-edge bases, GFN-17 has about 1.98 times as many
exponent steps.  Each textbook transform has about 2.125 times as much
`N log N` work, yielding roughly 4.2 times the arithmetic per task.  The roots
and primes support both sizes, so this is a fit/risk decision, not a
mathematical incompatibility.  Keep the architecture parameterized for 17,
but prove and optimize 16 first.

Sources: [live PrimeGrid subproject ranges](https://www.primegrid.com/server_status_subprojects.php),
[Arria 10 product table](https://cdrdv2-public.intel.com/714167/arria-10-product-table.pdf).

Across all three S3 primes, a complete prime-major transform state occupies:

```text
3 * 65,536 * 4 bytes = 786,432 bytes
```

Three hot arithmetic registers plus roots/scratch are plausible in Arria-10
embedded RAM, but exact banking and replication—not aggregate bit count—will
decide feasibility.

## Backend ABI, version 1

The eventual FPGA engine must expose these semantic operations:

```text
set(register, scalar)
copy(destination, source)
square_dup(register, exponent_bit)
square_mul(register, scalar)
prepare_multiplicand(source_register)
multiply_prepared(destination_register)
load_canonical(register, unbalanced_digits)
store_canonical(register) -> unbalanced_digits
read_counters() -> cycles, stalls, watchdog, checksum
```

Version 1 transports canonical unbalanced radix-`b` digits (`0..b-1`, with
the unique residue `-1` encoded as `[-1, 0, ...]`) at the host boundary.
NTT/RNS/Montgomery layout stays private to the engine.  This gives us freedom
to replace the textbook transform with Genefer's fused z-transform later.

## Proof/checkpoint memory

Quick/Gerbicz operation needs three hot registers.  Upstream proof mode for
`n <= 17` uses fast checkpoints; at default depth 7 it requests
`3 + 2^7 = 131` registers, roughly 100 MiB for GFN-16/S3.  That does not fit in
embedded RAM.

The ABI therefore treats proof checkpoints as host-spilled canonical digits:
128 checkpoints * 65,536 signed 32-bit digits = exactly 32 MiB per task. They
are transferred infrequently, so the first JTAG-only implementation can prove
correctness without making DDR4 a prerequisite. Moving 32 MiB through FT232H
JTAG may still be performance-significant; competitive proof-mode work will
likely require the later reviewed PCIe transport.

## Development ladder

1. Montgomery multiplier and exact upstream vectors.
2. Butterfly and independent naive-DFT checks.
3. Small cyclic and negacyclic transforms.
4. Full 65,536-element S3 transform in simulation.
5. CRT and radix carry against toy big-int `square_dup` oracles.
6. Full canonical-digit differential checks against pinned Genefer.
7. Three-register Gerbicz-capable engine.
8. JTAG-only physical validation and internal cycle measurements.
9. Host-spilled proof checkpoints.
10. Separately reviewed PCIe shell only if the kernel is already worthwhile.

The strongest full-size positive canary is the published GFN-16 prime
`604832956^65536 + 1`.  A deliberately constructed independent composite
canary is `604980544^65536 + 1`, divisible by 786433 and known to fail the
base-2 Fermat residue.  Neither is claimed as implemented until a canonical
full-size square/carry engine and upstream differential runner exist.
