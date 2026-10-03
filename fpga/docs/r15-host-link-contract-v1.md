# R15 host link — draft implementation contract

Scope: private direct-cold endpoint and software backend. This is not an
implemented PCIe link, generated-IP interface, CDC sign-off or board timing
claim. `direct_cold=0,pcie_shell=0` must preserve literal captured FIELD100.

## Payload and authority

The first direct path writes **N raw ordinary signed32 digits**, block-major
natural address, then16 signed c0 and16 signed c1. No residue planes and no
Montgomery/lazy words. Digits are -1 or [0,base); abs(c0)<=base-1;
abs(c1)<=2N+384. Full uint32 is validated before any write. Downstream reducers
remain. Wire header has base,generation,K,modes,context and prospective owner;
the six old R96/A77 DWORD positions are RESERVED ZERO, not imported arithmetic
proof. The software Profile object may retain those calculated reference values,
but they must not be serialized into these reserved fields. Original core
START/PROFILE freshly computes and validates R96/A77 before cold launch.
No extra setup unit or setup-removal credit. The captured guard's legacy port
`profile_ok` means the wrapper's immutable HEADER validation predicate only.
K is uint32,1..max in feed mode,<=32 in nonfeed batch,1 in nonbatch.
Core snapshots firstepoch=next_epoch and newgen=oldgen+1 (old ff refuses).
Expected final full56 owner is {K-1,firstepoch+(K-1) modulo16,newgen}.

`stream27_r15_host_link_model_v1.py` is the executable transport contract.
BEGIN captures context/fullowner/profile and obtains a core lease. Every data
record contains explicit session+lease+owner+index; stale PCIe data must NOT
be relabeled from a newer BEGIN. DATA record is32bytes/8 LE DWORDs:

| DWORD | Meaning |
|---|---|
|0|0x52315000 OR context (0/1)|
|1|session32|
|2|lease32|
|3|owner low32|
|4|owner high24; upper8 zero|
|5|word index,0..N+31, strictly increasing|
|6|raw full32 word|
|7|zero, reserved|

Records require32-byte alignment, full32-byte enable and exact record size.
Burst length/address legality will bind to actual generated DMA ports; this
record is NOT the vendor DMA descriptor. No PCIe BAR number/base is assigned
yet. The executable MMIO offsets are relative to a future non-prefetchable
application-control window; they are not adopted community BAR assignments.

BEGIN=1,COMMIT=2,CANCEL=3 at COMMAND. Profile/owner registers are locked from
accepted BEGIN through termination. BEGIN/COMMIT responses occur only after
core-domain acknowledgement, not a posted-write completion. ACCEPTED counts
transport ingress; APPLIED counts actual destination writes. COMMIT requires
both equal N+32, transport empty, current lease/owner/idle and header validation.
It atomically publishes header+image authority, NOT arithmetic profile readiness.
No partial image can start. START must match committed K/base/modes/corrections
and context, and cannot coincide with BEGIN/write/drain.
MMIO register encoding for finite tokens/status/error remains to be bound with
the actual generated bridge; unknown/reserved accesses must fault, not alias.

## Physical destination and reset

Retained banks are `contexts[c].natural_blocks[b].image_ram`, each32×N/16,
with separate leaves for each context. Digit address gives b=addr>>(AW-4),
row=addr mod(N/16). Corrections use small context-owned registers. They are
not writes to shared field/commutator pipeline memory. Existing priority is
commit > raw capture > row read > scalar host. Private ACK leaf exposes actual
host_write_ready and one-edge host_write_ack without changing arbitration.
The core alone grants physical bank/port access; an idle address range is not
a port grant. No acceptance may stall a live fixed-calendar peer.

Cancel or reset invalidates publication, discards pending input and requires
complete reload; already-applied payload need not be erased or rolled back.
Both CDC domains and all issued writes must acknowledge drain before token
reuse or new admission. Finite session/lease wrap is prohibited until that
drain/no-stale-transport condition. A PCIe reset/FLR must participate in this
barrier, not silently reset token counters and accept stale posted writes.

The first raw-loader RTL uses a stricter reset policy: the trusted session is
latched on the first link-drained edge after common reset. Any later session
change or loss of link-drained is a global sticky abort requiring common reset;
it cannot revive an already loaded image. Conflicting commands are rejected
before a physical write. The v2 wrapper masks read/ready/done/command/operation
authority and blocks new descriptor ingress on this error. Already admitted
private core work may drain; this does not claim a field-pipeline flush.

## Backpressure and export

Input uses a bounded command/data CDC FIFO and propagates waitrequest while
full. No N-sized ingress buffer. Payload stays stable until accepted. Internal
compute starts only after publication and descriptor readiness; descriptor
underflow is typed abort. Output DMA must read retained completed/captured
data, or use an independently proven maximum service gap. A tiny FIFO alone
cannot absorb arbitrary host stalls; overflow aborts without successful result
publication. Checkpoint/final ownership survives host stalls and cancellation.

The initial direct wrapper exports format A: retained parent canonical signed96
readback plus full56 owner. It retains the protected final materialization and
COPY_DRAIN barrier; host software must NOT run R14 raw finalization on format A.
Requested format B (raw signed32 carry rows plus c0/c1) needs a separate passive
tap/export and storage/overflow proof. It is not supplied by canonical readback.

NEXT_GENERATION at relative offset0x58 is prospective old-generation+1 as a
uint32, range1..256. The value256 is exhausted and must be refused, never wrapped.
The pure `header()` helper expects the old value, so adapters pass this register
minus1. NEXT_EPOCH is the core's current next_epoch snapshot, not host authority.

## Vendor/board evidence still required

Pinned community PCIe1 project at dc125eab is20.1 Standard PIO, not26.1 DMA.
`config/r15-pcie-reference-v1.json` records source pins and unverified physical
card identity. Current vendor guide683425 describes ReadDMA as host-memory
read→Avalon writes and WriteDMA as Avalon reads→host-memory writes, both with
waitrequest. Its clock table requires100MHz refclk and permits125/250MHz
application clocks; the actual Gen3x8 generated configuration must determine
the chosen clock/ports. No invented generated clock or blanket false path.

Actual26.1 installed20.2.3 HIP parameter query v4 passed Gen3/x8/256 using
non-derived `wrala_hwtcl=0`; earlier writes to derived rate/width were overwritten
by default mode7. This is not a generated-IP/license/timing pass. The guide's
recommended Gen3x8/256/250 speed grades are -1/-2; the current E3 target caveat
remains and must be resolved by actual device/IP/physical evidence, not a silent
part upgrade.

References: [pinned board](https://github.com/tow3rs/catapult-v3-smartnic-re/tree/dc125eab3ea1d2c3e4fa62543868977a0142e019/Projects/PCIe/PCIe1),
[official Avalon-MM DMA guide](https://docs.altera.com/r/docs/683425/current).
