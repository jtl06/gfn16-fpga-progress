# R15 application CDC constraint scope

Source contract, not a fitted CDC or board PASS. The immutable application v2
contains literal DIRECT65, the v6 Avalon endpoint, two eight-word512-bit FIFOs,
and a reset/session fence. It does not execute a vendor HIP simulation model.

The PCIe reference and board oscillator are independent100MHz inputs. Actual
generated HIP and IOPLL clocks must resolve to4ns and12ns respectively; never
rewrite either input clock to12ns. The standalone PLL's native M=10,N=bypass,
C=12 implements the exact5/6 ratio; final-system generation must confirm it.

`synthesis/r15_application_cdc_v1.sdc` selects clocks from actual command-FIFO
pointer registers, refuses missing/ambiguous/wrong-period clocks, and groups
only those two domains asynchronous. Crossings are limited to:

- Command and response FIFO payloads, each behind synchronized Gray pointers.
  No full-image buffer or direct active arithmetic cross-domain bus exists.
- Two-stage reset-release acknowledgements in each direction.
- The retained32-bit session, changed only while both domains are held reset;
  both releases and the peer acknowledgement precede any command authority.
- Common asynchronous reset assertion, with independent two-edge application
  reset deassertion. PCIe PERST is used only as reset authority, not payload.

Every Gray launch→first-meta bus gets the vendor-recommended0.8-source-period
skew and0.8-destination-period maximum net delay. Same-domain meta→second-stage
paths stay timed. The accompanying QSF preserves those chains and identifies
only their first synchronizers. PERST is the sole explicit external false-path
source. Vendor-generated exceptions remain unchanged and separately inventoried.

This follows [Altera dual-clock FIFO constraints](https://docs.altera.com/r/docs/683082/25.1/quartus-prime-pro-edition-user-guide/dual-clock-fifo-timing-constraints)
and [synchronizer identification](https://docs.altera.com/r/docs/683082/25.1/quartus-prime-pro-edition-user-guide/identifying-synchronizers-for-metastability-analysis).
The first actual mapping must verify endpoint counts, all scoped crossings,
clock identities, constraint coverage and metastability reports. Unknown
hierarchy/optimized-away matches are errors, not reasons to broaden exceptions.
Native event tests cannot prove metastability, FPGA placement or board timing.

An already captured response cannot be retroactively revoked across clocks.
Every A32 record carries session/full56 owner/index; host publication additionally
requires a coherent terminal error/owner/session fence. Common reset invalidates
queued records and leases. Session exhaustion refuses service; FPGA
reconfiguration requires host DMA-arena teardown before a new session namespace.
