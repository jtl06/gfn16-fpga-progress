# NTT27 tiled control registers

`genefer_ntt_banked27_tiled_engine` is an isolated control-replication experiment
derived from frozen `genefer_ntt_banked27_folded_engine`. It targets measured
control fanout and routing delay without changing arithmetic, RAM addressing,
root-network wiring, register stages, host protocol, or operation cycle counts.
No existing engine or core selects this candidate automatically.

## Measured paths motivating the change

The archived folded64 timing report shows `pairing_e[1]` to butterfly lane 37
`pre_w[10]` taking 11.890 ns through three logic levels. Interconnect accounts
for 11.240 ns, or 95 percent; the source reports fanout 3,670. A separate
root-RAM output to `root_rotated[78][26]` path takes 11.783 ns through seven
logic levels, with 71 percent in interconnect. The route report warns about
congestion and estimates peak long-interconnect demand at 156 percent.
These figures come from
`results/throughput-20260929/ntt27-folded64-fit/project/output_files/`.

The same fit has a separate −0.096 ns hold violation between butterfly lane 24
`prefix_pipe[2][28]` and `[3][28]`. This experiment does not change that pipeline
or any timing exception. A setup improvement would not establish a passing
fit if hold still fails.

## Exact replica partition

At 64 arithmetic lanes there are eight logical tiles. Tile t supplies controls
to arithmetic lanes `8*t` through `8*t+7` and destination root-network banks
`16*t` through `16*t+15`. This is a consumer partition, not a physical floorplan;
cross-tile data and root-network connections remain unchanged.

- Each tile's `pairing_e` and `orientation_e` drive only its eight lanes' u, v,
  and w selection. They capture `pairing_d` and `orientation_d` on the original
  routing-register edge.
- Each tile's `folded_root_bank_d` drives root XOR-stage muxes selected by the
  destination bank's tile, not by the source bank. It captures the original
  `root_base_bank ^ rol(base_bank & folding_mask,rotation)` expression on the
  original RAM-read edge.
- Each tile's `rotation_d` drives its sixteen `root_rotated` selection muxes
  and captures the original `rotation` on the original RAM-read edge.

All four registers retain asynchronous active-low reset to zero. No replica
captures another replica's output. The former four global registers are removed;
`pairing_d`, `orientation_d`, all valids, writeback tags, and datapath registers
remain unchanged.

For L64, widths are 3+1+7+3 = 14 bits per tile: 112 declared bits replace 14,
adding 98 register bits. For L16, two 12-bit tiles replace 12 bits, adding 12.
For L≤8 there is one tile. These are RTL counts, not post-fit resource results.

## Quartus preservation attributes

Every generated control declaration uses `(* preserve, dont_merge *)`.
The official Pro 26.1 documentation distinguishes preservation of a register
against removal or retiming from prevention of merging duplicate registers.
Both are required here. This uses those attributes directly, not the broader
debug-preservation feature or a project-wide optimization disable.
[Altera Pro26.1 attribute definitions](https://docs.altera.com/r/docs/683819/26.1/quartus-prime-pro-edition-user-guide/preserve-for-debug-overview)

The settings reference also describes the register-merging prohibition.
Every replica has real RTL consumers, so fanout-free retention is not the
purpose of this change.
[Altera register merging reference](https://docs.altera.com/r/docs/683296/25.3/quartus-prime-pro-edition-settings-file-reference-manual/dont_merge_register?contentId=HLN9wy_HsgpeEMHypzAtZQ)

Attributes and logical partitioning do not prove physical locality. Added
registers also add load to their common data sources and reset. A later fit
must verify that the attributes were honored, all eight replicas remain,
and their actual consumers/fanouts follow the intended partition. Merely seeing
extra unused registers would not validate this experiment.

## Equivalence and validation

After reset, each replica equals the former global register. On every following
edge it uses the same predecessor expression and reset condition, so induction
preserves that equality. Substituting equal-valued drivers leaves every mux
output unchanged; no clock edge is inserted. Measured full-size five-phase
arithmetic counts remain 78,136 at L16 and 19,768 at L64.

The structural gate reconstructs the entire new source from the pinned folded
ancestor using only declared control substitutions. It rejects changes to
data routing, tags, capture edges, reset values, attributes, or tile selection.
In particular, routing every consumer to tile0 is arithmetic-equivalent but
defeats the physical goal; it is rejected structurally rather than falsely
claimed as detectable by an arithmetic oracle.

Independent review found no functional or latency discrepancy. Initial static
tests pass, including ten negative structural cases. The separate aethia-only
RTL gate checks canonical residues, host arbitration, exact cycle accounting,
both transform orders, reset cancellation, all three fields, and whole-integer
negacyclic squares. Quick P1 validation passed at L16 and L64 with AW1, AW4,
and AW10: 13 steps and 21 square samples per lane profile.

The final all-field gate passed at L16 and L64, with AW1, AW4, and AW16;
the AW16 models also checked every runtime power-of-two size from 2 through
65,536. Its 206 recorded steps include 36 combined whole-integer squares,
115 field-square samples (including seven AW10 fault-control samples), and
17 rejected RTL mutants. Four mutants specifically corrupt the last tile's
pairing, orientation, root-bank, or rotation control. The ten negative
structural cases separately enforce capture, reset, attributes, and partition
intent, including arithmetic-equivalent changes that value tests cannot detect.

For every full-size case and field, measured phase counts are:

| Lanes | Twist | Forward | Square | Inverse | Post | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 16 | 4,104 | 32,912 | 4,104 | 32,912 | 4,104 | 78,136 |
| 64 | 1,032 | 8,336 | 1,032 | 8,336 | 1,032 | 19,768 |

These are arithmetic-engine clocks, not complete modular-square latency or
hardware throughput. No physical fit was launched as part of this gate;
physical preservation, placement benefit, and timing closure remain unverified.

Final evidence is under
`/home/jtl/gfn-fpga-lab/agent-work/ntt27-tiled/fpga/artifacts/full-v1/`.
All source hashes recorded by the reports were rechecked before archiving.

| Artifact | SHA256 |
| --- | --- |
| `report.json` | `ce5a67aa4a573e1ebbb6ca83e25e149f67a39f104c4b6745d5803234b5772be1` |
| `lanes16/report.json` | `3d935df1a448c73430813b760a2757fefc4db676d33b5bfbb04c0e3d27d4e934` |
| `lanes64/report.json` | `f0aa3765eaab099dc098c76355e58fa77218019d3bdffa3a0289c8e1b1a826f2` |
| `source-snapshot.tar.gz` | `03bdef840efb87109aeeba8d1f9269049ed584b89224357f3a0e94670327631f` |

Frozen folded ancestor SHA256:
`475a7500e58485c943961729334f8c03e35eb52095657813f8c770d29cb5167c`.
Frozen, fully gated tiled candidate SHA256:
`d3dbaa6fe626e7e926b589f92b84959381b6c7aff74cb21a2d9f1d8d25353af0`.

## Prepared post-fit audit (not executed on a fitted design)

`synthesis/tiled_control_audit.tcl` only queries an already loaded Timing
Analyzer netlist. It does not open a project, load a netlist, launch a fit,
alter constraints, or write assignments. After the matched tiled fit completes,
the fit owner can source it in that project's post-fit Timing Analyzer session
and capture stdout. Set `tile_audit_pattern` to one engine instance when the
project contains several; the default is `*control_tiles*`.

The exporter retains automatically duplicated registers. It emits each control
register's name and location, immediate timing-graph fanout edges, and reachable
keeper endpoints with their locations. The official command references verify
the distinction between immediate edges and reachable registers/ports:
[register selection](https://docs.altera.com/r/docs/683432/26.1/quartus-prime-pro-edition-user-guide/get_registers-quartus-sdc_ext?contentId=QZelWLOWr9aErdYY5Uf63A),
[node properties](https://resources.altera.com/quartushelp/17.0/tafs/tafs/tcl_pkg_sta_ver_1.0_cmd_get_node_info.htm),
[edge destinations](https://docs.altera.com/r/docs/683432/26.1/quartus-prime-pro-edition-user-guide-scripting/get_edge_info-quartus-sta?contentId=Qxmw92BreY781K~H4xsGVA),
and [reachable fanouts](https://resources.altera.com/quartushelp/17.0/tafs/tafs/tcl_pkg_sdc_ext_ver_1.0_cmd_get_fanouts.htm).
The node/fanout definitions above are archived official help; current online
26.1 pages for those two commands were unavailable. Actual tool execution is
still a future gate, not established by syntax review.

From the `fpga` directory, parse a future capture with:

```sh
python3 -m synthesis.tiled_control_audit /absolute/path/capture.log --lanes 64
```

The parser rejects truncated captures, malformed records, and combined engine
instances. It lists missing control bits, tool duplicates, unknown names,
registers without observed consumers, and pairing/orientation endpoints outside
their intended arithmetic tile. Root-network endpoints are not subjected to
that last rule: XOR stages cross tiles, even though their mux controls are
partitioned by destination bank. Unknown naming must be investigated rather
than automatically reported as register merging.

Per-tile X/Y bounding boxes describe observed placement only. A complete set of
control names does not prove that the physical fitter honored the intended
consumer partition, and small bounding boxes do not prove shorter routes.
Compare actual fanout, endpoint placement, setup/hold paths, resource usage,
and fitter warnings against the matched folded fit. Verify the captured
project's manifest and completed-fit identity separately; the parser leaves
fit provenance, locality, and timing closure explicitly unproven.

Seven local tooling tests pass using explicitly synthetic fixtures and mocked
Tcl commands. They test serialization, duplicate visibility, geometry,
missing/truncated data, and consumer classification. They neither invoke
Quartus nor invent an observed tiled netlist or physical result.

`synthesis/postfit_tiled_audit.tcl` now supplies a separate lifecycle wrapper:
it requires a successful existing fitter summary and the isolated tiled top,
loads the post-fit timing netlist, invokes the exporter, then closes with
`-dont_export_assignments`. It contains no fit, assembler or assignment-changing
commands. The caller still must verify the terminal receipt and exact source
identity, reserve compute resources, and preserve capture provenance. Four
mocked Tcl tests cover success, failed-fit refusal, wrong-top refusal and cleanup
on query failure. Actual Quartus execution remains pending the tiled fit; these
tests do not establish tool-API compatibility or physical locality.

## Actual folded-baseline audit, 2026-09-30

The wrapper now also permits the isolated folded baseline and selects its four
global control families. Actual Pro26.1 Timing Analyzer execution completed
twice on that finished fit (exit0, no warnings/errors, about15seconds each).
The source, constraints and all pre-existing report hashes were identical
before/after. Logs, receipts and exact scripts are preserved under
`ntt27-folded64-fit/control-audit-v1` and `control-audit-v2`.

The second capture SHA256 is
`71d89cca4f3470273da368c699f82ab1d8f1b247cd16f4213e2f5ed7a996897c`.
All14 expected logical control bits are present as22 physical registers,
including8 automatic duplicates. The observed duplicates share their parent's
X/Y coordinates in adjacent FF slots; this is not evidence of eight distributed
consumer-local control groups. `pairing_e[1]` is atFF_X67_Y106_N52, has no
observed automatic duplicate, and reaches5504 keeper nodes through combinational
logic. That number is NOT direct net fanout and is not substituted for the
separate STA path's3670 reported fanout.

Actual-tool inspection also exposed a timing-graph distinction: the immediate
register edge goes to its Q pin, whose next hop generally goes through an
internal LAB output node. The updated exporter separately records register
edges, Q-pin edges and transitive reachable keepers; the parser must not call
any of these identical measures of physical fanout. Fourteen local parser/
wrapper tests pass. The tiled candidate's preservation and physical placement
are still pending its own completed fit/audit. Baseline query success is not
tiled timing closure.

## Completed tiled64 physical result and audit

The P1/AW16/L64 four-worker10ns fit completed08:29:42UTC with both compiler
and summary exit0. Exact sources, control hashes and execution receipt were
verified and archived under `ntt27-tiled64-fit/`.

| Quantity | Folded baseline | Tiled controls |
| --- | ---: | ---: |
| Reported Fmax |87.89MHz|99.40MHz|
| Setup at100MHz |-1.378ns|-0.060ns|
| Hold |-0.096ns|+0.018ns|
| Raw ALMs |114528|117514|
| Adjusted ALMs |109145|112007|
| Registers |47720|47403|
| Raw DSPs |64|64|
| RAM bits / M20K |7405568 /512|7405568 /512|

This is a useful timing trade-off, not a passing100MHz result. Raw ALMs rise
2986. Both full-size simulation gates and all QSF controls excluding source/top,
SDC, QPF, flow, processor count, field and tool version match. The diagnostic
comparison records those hashes; the strict speedup comparator remains rejected
because baseline hold fails. The13.1percent reported-Fmax increase is not an
established hardware-throughput increase, especially from one seed/component.

Actual tiled netlist audit SHA256
`808952d8107142b41a49e1f67b47ca02964fa8b1319b220f7aa3f0c0e547224e`
contains all112 intended logical control bits as179 physical registers,
including67 automatic duplicates. Every observed register has consumers;
pairing/orientation have zero arithmetic keeper endpoints outside their assigned
eight-lane tiles. Maximum reachable keeper count per pairing register falls
5504→688; orientation3937→688; rotation3564→437. These are transitive keeper
counts, not net pin fanout. Root-bank-control reach remains high3626→3483,
consistent with cross-tile XOR routing. Tile bounding boxes overlap and are
not evidence of physically compact regions.

The worst path is now twist RAM bank8→root_rotated[90][13],10.110ns:
7.224ns interconnect,0.716ns logic,2.170ns RAM output. Its first RAM-to-XOR
wire alone takes3.600ns, fromEC_X70_Y103 toLABCELL_X79_Y175. Other top paths
include butterfly output→data RAM. Thus explicit control replication removed
the prior dominant global-pairing path, but root/data placement and routing
remain limiting. Further pipeline/locality work must target these measured
paths; a small clock-constraint change is not itself an RTL speedup.
