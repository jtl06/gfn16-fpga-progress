# Autonomous hardware safety contract

The language model is an untrusted proposer.  Deterministic software controls
what can reach the FPGA.

## Immutable boundary

Once reviewed, the following are owned by the broker/operator, never by the
autonomous optimizer:

- top level, QSF, SDC, pin assignments, device ID, clocks, resets, watchdog;
- JTAG-to-Avalon transport and on-chip test RAM;
- allowed clock profiles, temperature/current limits, and artifact signing;
- the programmer executable and its arguments.

The optimizer may change only `rtl/kernel/` and bounded candidate parameters.
The current policy checker is a deliberately conservative **lexical
prefilter** for obvious PCIe, DDR/EMIF, transceiver, JTAG/reconfiguration,
Nios, flash, or source-boundary text. It is not a security parser and is not
claimed to stop macro obfuscation or every device primitive. Before hardware
mode exists, the broker must also enforce an exact parsed module/port
allowlist, compile a content-addressed immutable source snapshot, and audit the
post-elaboration/netlist primitive and I/O inventory.

Hardware admission must also reject combinational loops, unapproved clock
resources, excessive resource/toggle/power estimates, DPI or simulator file
access, and simulations lacking a trusted-runner authenticated result.
Candidate simulations run in a filesystem- and network-isolated process; an
exit code or candidate-generated `PASS` string is never sufficient.

## Programming policy

- Hardware mode remains disabled until a human verifies the card.
- `config/hardware-policy.toml` is declarative in this preparation tree. A
  future broker reads a root/operator-owned copy; editing agent-visible config
  can never grant hardware access.
- Only CI-produced, content-hashed `.sof` artifacts for the expected JTAG
  device ID may be loaded.
- `.pof`, `.jic`, `.rpd`, flash erase/write, fuse/security, BMC, and remote
  update operations are forbidden at the broker API and OS-permission levels.
- The model never receives USB device permissions or a raw `quartus_pgm`
  command surface.
- The initial shell contains no PCIe endpoint or DMA.  Internal counters make
  useful timing measurements possible over slow JTAG.

A `.sof` suffix is not proof of safety: volatile logic could still drive
unsafe pins. Admission depends on trusted compiler provenance, exact
shell/QSF/SDC and source-list hashes, plus post-fit pin and configuration-IP
audits.

## Recovery

1. Timeout or mismatch: gate the kernel clock, reset it, quarantine candidate.
2. Responsive JTAG: reload the known-good volatile `.sof`.
3. Dead target host/JTAG: a controller on another machine cold-cycles ATX
   power; BIOS restore-on-power returns the runner.
4. Thermal, current, fan, unexpected-device, or shell-hash trip: cut power and
   require inspection.  Do not automatically retry.

No autonomous PrimeGrid submission is permitted.  A winning kernel must pass
independent Genefer validation before account access is considered.
