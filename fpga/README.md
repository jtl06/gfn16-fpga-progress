# GFN16 / GFN17 FPGA preparation lab

Selected direction (2026-09-23): GFN16 is the correctness milestone;
GFN17 Mega is the intended PrimeGrid discovery target. See
[the memory and integration plan](docs/GFN17-PLAN.md). This is a planning
update, not a working GFN17 implementation. Hardware work remains deferred;
compute-only vendor synthesis and fitting are now authorized. On 2026-09-29 the user requested pre-hardware RTL work on
aethia; see [the aethia work record](docs/AETHIA-RTL.md).

This directory prepares the PrimeGrid Genefer/Arria-10 experiment before any
hardware is purchased. Results include **simulation and standalone vendor fits,
not hardware measurements**. The user has approved provisional compute-only
Quartus synthesis and fitting.
Quartus Pro 26.1 and Arria 10 support are installed on aethia. The 30-day
evaluation is active through the reported expiry of 2026-10-29, and the
multiplier, full-size NTT, CRT and carry standalone probes fit and meet a
100 MHz internal constraint (not an integrated or board-timing-closed design). There
is still no JTAG, PCIe enumeration or device-programming flow. See
[toolchain setup](docs/TOOLCHAIN-SETUP.md).
See the [optimization audit](docs/OPTIMIZATION-AUDIT.md) for RAM-inference fixes,
sequential CRT/carry arithmetic, fused square scheduling, and measured limitations.

The subsequent aethia milestone adds a complete simulated modular-square
path at GFN16 size (NTT, pointwise square, CRT and carry), with host orchestration.
See [engine results and limitations](docs/ENGINE-RESULTS.md). This is not a
complete PRP engine, integrated fitted design, or PrimeGrid-compatible worker.

An active subsequent throughput effort adds an **autonomous three-field square
core**, with on-chip roots and retained outputs between starts. Its 384-case
oracle suite passes, including nine full-size squares; integrated vendor fits
are underway. See [the goal journal](docs/THROUGHPUT-GOAL-LOG.md) and
[square-core evidence](docs/SQUARE-CORE-NOTES.md). The next experiments remove
transform reordering, widen butterflies, and replace serial carry propagation.
The user's current target is GFN16 throughput comparable to a same-era weak GPU;
[the qualified comparison targets](docs/GFN16-GPU-TARGET.md) make clear that
CPU/GPU parity is **not demonstrated** and remains a substantial design challenge.

## What works now

- A Python reference for the three 31-bit NTT primes and the exact Montgomery
  multiplication convention used by Genefer's OpenCL kernel.
- Deterministic JSONL and plain-hex vectors suitable for Python and future
  SystemVerilog testbenches.
- A simple Montgomery multiplier baseline, validated on aethia with the
  existing 531-vector SystemVerilog testbench and a streaming scoreboard.
- A four-register-stage Montgomery multiplier and five-register-stage radix-2
  NTT butterfly, tested in Verilator for all three S3 fields. The regression
  checks one input per cycle, fixed latency, bubbles, output holds and reset
  cancellation against independent Python big-integer vectors. Simulation is
  not FPGA timing closure or a resource-fit measurement.
- A reproducible regression runner with three random seeds, exact vector
  counts, negative tests, logs and source hashes. See the
  [aethia results](docs/AETHIA-RTL.md).
- A resumable mock experiment ledger and a deny-by-default lexical RTL
  prefilter. The future hardware security boundary is a parsed/netlist audit
  plus an operator-owned broker, not regular expressions.
- Source locks and a hardware bring-up checklist that keep unverified board
  assumptions out of the trusted shell.

Python reference commands (run on aethia, not the Mac, for this work):

```bash
make -C fpga verify
make -C fpga full-check
make -C fpga mock
```

Run these commands from the repository parent with Python 3.11 or newer.
`verify` runs the normal oracle/vector/policy suite; `full-check` additionally
runs a complete 65,536-point transform round trip for all three S3 primes.
`full-check` is software-only. The separate engine regression exercises the
full-size RTL transform and modular-square path. `make rtl-baseline` and `make rtl-check` run the RTL
tests with Verilator. `python3 -m reference.rtl_regression` runs the complete
multi-seed regression; see the aethia record for its isolated tool paths.
`python3 -m reference.engine_regression --output artifacts/engine-run --phase all`
runs the newer transform, CRT/carry, square and RTL mutation tests.

The mock score is only a plumbing test. It is explicitly not a speed,
resource, or success prediction. Its `lanes` and `pipeline_stages` values are
requested/mock metadata and do not yet parameterize the RTL.

## Confirmed target facts

At pinned Genefer commit `d5060c61090942f42a908492628eba13ebd7cd82`,
GFN-16 uses `N = 2^16 = 65,536` transform elements.  Genefer selects two or
three RNS primes based on the candidate base; large current-range bases use
three.  The three signed-family primes are:

| Name | Prime |
| --- | ---: |
| P1 | 2,130,706,433 |
| P2 | 2,113,929,217 |
| P3 | 2,013,265,921 |

For a three-prime, four-register GFN-16 transform, Genefer reports a 4.25 MiB
working-set estimate in its default no-`USE_WI` path and 4.625 MiB with
`USE_WI`. Its OpenCL code actually allocates 4.625 MiB of `z`, multiplicand,
root, and carry buffers in either case; the smaller report discounts
unused/derived root storage. Register count and transform family change both
figures, so neither should be treated as a universal hot-state requirement.

The used-card documentation is community reverse engineering, not Microsoft
board documentation.  It identifies Longs Peak as a PCIe Catapult-v3 board
with an Arria-10-class custom-marked FPGA and onboard FT232H JTAG, but the exact
card revision and device must be photographed and JTAG-scanned before a board
project is generated.

See [docs/SOURCES.md](docs/SOURCES.md) for provenance and
[docs/BRINGUP.md](docs/BRINGUP.md) for the arrival-day procedure.  The desktop
purchase target is in [docs/HOST.md](docs/HOST.md).

## Deliberately absent until the card arrives

- Pin assignments, device ordering code, oscillator selection, and board QSF.
- A callable hardware programmer.
- PCIe, DMA, DDR4, flash, BMC, transceiver, or network logic.
- PrimeGrid account access or automatic work submission.

Those omissions are safety properties.  The first physical build will be a
reviewed clock/reset/JTAG-to-memory shell with all unused pins left in a known
safe state.  The autonomous agent will only be allowed to edit
`rtl/kernel/`; it will never own the shell or programming command line.

## Before buying anything

1. Send the candidate card listing or screenshots so the PCIe/OCP variant,
   component population, heatsink, and visible damage can be checked.
2. Inventory the desktop's CPU, RAM, PSU model, case clearance, motherboard,
   and the electrical width of its free PCIe slot.
3. Confirm access to Quartus Pro 26.1 plus Arria-10 device support; do not
   assume the required compile flow is license-free.
4. Choose whether to try the community FT232H bridge or budget for a genuine
   Intel/Altera USB-Blaster on J5.
5. Do not create a board-specific QSF until photographs and a read-only JTAG
   scan agree on the exact card.

The upstream file locks are machine-readable in
`config/upstreams.lock.json`. Given checked-out copies, verify them with:

```bash
cd fpga
python3 -m reference.verify_upstreams \
  --genefer-root /path/to/genefer22 \
  --catapult-root /path/to/catapult-microsoft-pcie
```
