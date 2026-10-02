# Vector-host prefix carry

`genefer_carry_prefix_vector.sv` is a separate candidate derived from frozen
wide-v3. The carry arithmetic, internal scheduling, output write register,
banking, and scalar ports are unchanged. Only idle host arbitration and vector
access were added. The frozen wide/scalar modules and core are not edited here.

## Agreed interface

Parameters are AW and LANES; validation passed at LANES=4 and16. Existing
scalar ports remain. New ports are:

| Port | Direction and width | Meaning |
|---|---|---|
| vector_load_we, vector_read_en | input, one bit each | Vector write/read request |
| vector_addr | input, AW bits | Aligned logical coefficient address, not bank row |
| vector_lane_mask | input, LANES bits | Requested read or write lanes |
| vector_write_data | input, LANES*96 bits | Lane g is bits `[96*g+:96]`, logical address `vector_addr+g` |
| vector_read_valid | output, one bit | Registered accepted vector-read response |
| vector_read_mask | output, LANES bits | Actual valid response lanes, zero without read-valid |
| vector_read_data | output, LANES*96 bits | Same packing; consume only response-mask lanes |
| host_error | output, one bit | Registered invalid vector-request indication; independent of arithmetic error |

In idle, live `size_log2` defines N. A vector request requires
`1<=size_log2<=AW`, `vector_addr % LANES == 0`, and `vector_addr < N`.
The effective mask is the request mask intersected with `vector_addr+g < N`.
This supports N<LANES, including separately elaborated AW1/N2 at sixteen lanes.

Priority is vector write, vector read, scalar write, scalar read. **Any vector
request suppresses scalar fallback, even when the vector request is invalid.**
An invalid vector request performs no RAM operation, has no read-valid, and
sets host_error for that sampled request. Consecutive invalid requests can keep
host_error asserted on consecutive cycles. A zero-effective-mask request is
accepted: writes do nothing; reads return read-valid with mask0 and no RAM read.

Scalar addressing retains the original raw physical-address contract; the new
active-N validation applies only to vector requests. All scalar/vector requests
are ignored while busy or on a start edge, including malformed vector requests:
neither host_error nor a read response is emitted. The separate arithmetic
error/done behavior is unchanged. Tying both new request inputs low preserves
the old scalar access path.

Read requests sampled at an edge produce registered valid/mask/data during the
following clock interval, matching the existing synchronous scalar RAM read.
Consecutive reads are accepted every clock. Start may directly follow the final
write or read edge; no additional idle bubble is required. Reset clears both
read-valids, the vector response mask, and host_error, but does not clear RAM.
After an aborted carry operation the active coefficient array must be reloaded.

## Arithmetic and throughput

The bounded-domain contract is unchanged: N is a power of two, N>=2, N<=2^AW;
`2N+4 < base <= 10^9`; every coefficient satisfies `|a_i|<=2N(base-1)^2`.
Domain violations are rejected explicitly. See CARRY-PREFIX-NOTES.md for the
Euclidean decomposition and five-state negacyclic fixed-point proof, and
CARRY-PREFIX-WIDE-NOTES.md for bank grouping and registered output scheduling.

Final simulation measured the same carry busy duration as frozen wide-v3:
`2*ceil(N/LANES)+116` clocks, including 32,884 clocks for N65536/LANES4 and
8,308 for N65536/LANES16. The vector interface accepts a full group of writes
or reads per idle clock; it does not permit simultaneous read and write, and
does not overlap host access with carry computation. An integrated upstream
CRT/conversion pipeline must actually supply/consume those groups before any
complete-square or PRP speedup can be claimed. No fit, achieved-frequency,
resource, power, or GPU-parity claim is made here.

## Validation

Final report has status `passed`:
`/home/jtl/gfn-fpga-lab/agent-work/carry-prefix-vector/fpga/artifacts/vector-v2-final/report.json`.
The initial vector-v1 suite passed with the same RTL; v2 strengthens the tests
to independently vary start during busy and mutate those two suppressions.

| Configuration | Successful carry runs | Domain rejections | Reset aborts | Host scoreboard checks |
|---|---:|---:|---:|---:|
| LANES4, AW16 | 3,309 | 66 | 6 | 5,098,947 |
| LANES4, AW1 | 2,697 | 11 | 0 | 9,117 |
| LANES16, AW16 | 3,309 | 66 | 6 | 3,703,410 |
| LANES16, AW1 | 2,697 | 11 | 0 | 9,117 |

All builds and simulation ran on aethia, with at most two build threads and
without warning suppression. LANES8 is supported by the parameterization but
was not separately simulated for this new vector-host variant.

The C++ host scoreboard models registered request arbitration, mask clipping,
address alignment/range checks, payload packing, and unchanged arithmetic error.
Each configuration includes 4,000 randomized back-to-back host requests with
size changes, invalid descriptors, simultaneous scalar/vector traffic, partial
and empty masks, then reads back storage to detect unintended writes. Normal
loads alternate scalar, full-vector, and complementary masked-vector writes.
Results alternate vector and scalar reads. Busy traffic toggles start and drives
malformed vector and scalar requests, independently checking both suppressions.

The arithmetic vectors are the preserved independent Python big-int/prefix-model
oracle data from wide-v3, identified by SHA256 in each report. They include
exhaustive small signed cases, full-domain-bound extrema, negative chains,
canonical -1, random coefficients, recurrent square/double steps, full N65536
square/double coefficients, domain rejections, and six reset-abort phases.
Every valid initial load is followed by two canonical-output carry reruns
without reset/reload. Configurations change base and size without reset.

Eight host-specific mutants were rejected, targeting priority, alignment, range, request mask,
lane packing, returned active mask, busy suppression, and start suppression.
The ten arithmetic/output-tag mutants already passed against frozen wide-v3;
the arithmetic section is byte-for-byte unchanged in this candidate.

Frozen RTL dependencies:

- `genefer_carry_prefix_vector.sv`: `cf910b9f0a72a209b0983b3dbeb8a3828295a7757df8615d723523c0bd85fdf0`
- `genefer_carry_transfer_tree.sv`: `b18e39ebcaf2a1b514e0b617170dc1491a576772fe94ff3cf55316feee09971c`
- `genefer_div96_recip_prefix.sv`: `7fb975d75e27e5d66c97b02a2784cba8ed7dde3de624555859b8e8893a71a3b9`

Frozen scalar-host wide-v3 remains
`ed3861413e2122c8243189c0688c4e806901d416fd6e6d6440c667de4c1b3fd6`.
