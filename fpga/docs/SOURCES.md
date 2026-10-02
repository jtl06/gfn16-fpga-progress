# Source lock and evidence boundary

Preparation is based on these inspectable upstream snapshots:

| Material | Pinned revision | Used for |
| --- | --- | --- |
| [galloty/genefer22](https://github.com/galloty/genefer22) | `d5060c61090942f42a908492628eba13ebd7cd82` | NTT length, RNS-selection rule, primes, Montgomery constants, buffer formulas |
| [jimjiang2/catapult-microsoft-pcie](https://github.com/jimjiang2/catapult-microsoft-pcie) | `7a5ab269bb5f79d8251bb47a637fddb8f4545850` | Provisional Longs Peak component, clock, JTAG, PCIe, and pinout information |
| [Intel Arria 10 documentation](https://www.intel.com/content/www/us/en/products/details/fpga/arria/10/docs.html) | vendor-maintained | Device architecture and future Quartus constraints |
| [tow3rs/catapult-v3-smartnic-re](https://github.com/tow3rs/catapult-v3-smartnic-re) | `dc125eab3ea1d2c3e4fa62543868977a0142e019` | User-selected Catapult v3 board reference, 2026-09-29; metadata in `config/board-reference.json` |

The newly selected reference covers both Longs Peak PCIe and Dragontails Peak
OCP cards, including different FPGA variants. It reports a custom `10AXF40GAA`
marking and a provisional equivalence to `10AX115N4F40E3SG`. That is not an
identity check of the user's card. DDR4 and onboard programming are documented,
but no board shell or community pin assignments are incorporated into our RTL.

The Genefer values reproduced in `reference/rns_reference.py` come from
`src/transformGPU.h`, `src/transform_ocl.cpp`, and `ocl/kernel.cl`.  Genefer is
MIT licensed.  The reference code here is a small independent Python
translation of the arithmetic equations, not a copy of its transform engine.
Exact commits and source-file SHA-256 values are recorded in
`config/upstreams.lock.json` and checked by `reference/verify_upstreams.py`.

## Evidence boundary

Confirmed from the pinned Genefer source:

- Transform length is `1 << n`, therefore GFN-16 uses 65,536 elements.
- The GPU implementation dynamically selects two or three RNS primes and a
  signed/unsigned family according to base size.
- The three signed-family primes and Montgomery constants in this lab match
  the upstream definitions.
- The upstream `mulmod` computes Montgomery-domain multiplication with a
  32-bit radix.

Not yet confirmed for the physical card:

- The listing really is the PCIe Longs Peak variant rather than an OCP card.
- The exact FPGA marking, board revision, oscillator population, DDR health,
  FT232H wiring, JTAG chain, and shared effects of a missing Mellanox device.
- Which Quartus release accepts that exact device identifier and closes timing
  reproducibly.

Community board files are useful evidence, but they are not safe to apply
blindly to an unknown used card.  No pin assignment should become trusted
until card photographs and a non-programming JTAG scan agree with it.
