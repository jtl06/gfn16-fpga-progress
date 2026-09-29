# GFN-16 FPGA progress

Progress toward an FPGA implementation of GFN-16 modular arithmetic, with the
longer-term aspiration of throughput comparable to a low-end GPU from the same era.
This repository publishes the **progress chart, sanitized milestone data and plotting code**,
not the full RTL project or vendor tool outputs.

![GFN-16 projected time per candidate](progress.svg)

## What the chart means

Every point uses a **hypothetical common 100 MHz clock** to compare architectures:

```text
projected seconds = cycles per square × 1,911,814 / 100,000,000
```

The example candidate is `604832956^65536 + 1`. This approximates one modular
square/conditional-double per exponent bit. The clock is **not a verified operating
frequency**, and the plotted times are **not FPGA measurements or full PRP benchmarks**.

The first point is the earlier serial component-cycle model. Later points are
complete modular-square RTL simulations, including conversion, root loading,
three field engines, CRT reconstruction, carry handling and controller overhead.
Five consecutive full-size random squares reused the preceding RTL output at each
integrated milestone. Additional corner cases and deliberate fault-injection tests
were run, but five samples are not a full-PRP average or universal worst-case bound.

Proof generation/verification, checkpoints and board/host overhead are excluded.
The 5–10 minute band is a chosen engineering goal, **not demonstrated GPU parity**.
The x-axis shows milestone order, not elapsed development time.

## Reproduce the chart

Requires Python 3.10 or newer:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python plot_progress.py
python -m unittest discover -s tests
```

This regenerates `progress.svg` and `progress.png` from `progress.json`. It does
**not** reproduce the underlying hardware-design simulations. The data includes
hashes identifying private regression evidence and RTL snapshots; those hashes
are provenance identifiers, not a substitute for publicly inspectable test outputs.

## Update policy

Append an integrated milestone only after its full-size RTL output passes an
independent whole-integer oracle. Keep its cycle count, source hash, date, evidence
class and qualifications. Component-only experiments and unimplemented ideas do
not become integrated progress points. Regenerate both images after changing data.

When measured hardware data becomes available, add it as a separate evidence
class rather than relabelling these projections as measurements. Preserve historical
milestones; document corrections explicitly.

No credentials, machine addresses, tool licenses, installers, raw vendor reports,
or unrelated workspace material are included here. Publication does not imply
PrimeGrid endorsement or an operational PrimeGrid-compatible worker.
