# Track A A4 integration ledger

Owner: Codex Track A integration agent. This is a live working ledger; immutable
source/native snapshots and review receipts remain the evidence authority.
Scope: GFN16/Catapult v3 compute only. Scoped native cycle measurements exist;
no A4 whole-core clock/throughput promotion.

## Components and current bindings

| Component | Source / evidence | State |
|---|---|---|
| Arithmetic and schedule | `reference/track_a4_blockcarry_model.py`; `briefs/replies/2026-10-01-B20260930A-A4-blockcarry-independent-v1.json` | Independent planning pass;24712 datapath estimate |
| Carry lane | `rtl/kernel/genefer_track_a4_blockcarry_lane_v1.sv`, SHA07be83b090375ddb721b00c3effe5b44e81dd89fb174708a52a14bfdcc816b02 | AW5/AW8 native gates independently passed; setup/wrapper/fault codes5–10 separate |
| Block route | v1 preserved; `genefer_track_a4_blockroute_v2.sv`, SHA0d292ef6072f250f9255b758319e0754b0265a3d26be694601bb96b25a9e1cfa | v1 native build failed SIDEEFFECT before simulation; v2 AW5 and AW8 native gates independently passed |
| Whole64 engine route adapters | `*_blockroute_v2_engine.sv`; guard `reference/track_a4_blockroute_source_v2.py` | Additive engine c4d66bf9... / adapter9b49d383... bind route v2 hash0d292ef6; full-engine native equivalence remains separate |
| Shared setup and canonical cell | `genefer_track_a4_setup_v1.sv`, `genefer_track_a4_canonical_cell_v1.sv` | Native AW5/AW16 prep receipt5858e6b3; no native result yet |
| Canonical pass controller | `genefer_track_a4_canonical_controller_v2.sv`, SHAf8d8e523ac934dfd3df2b697fe03be14250a584da2aaca761779feaf03f3fbba | Explicit bank-width successor; standalone prep44cb09aa and independent source GO d4de763d; exercised inside AW5 host shell v2 |
| Digit image frontend | `genefer_track_a4_digit_image_v1.sv`, SHA606e807d3a845697038deec169ef5b8aea572c85e4d2bf622444cd03700372f6 | Authored by component agent; shell bound to this exact source; native prep separate |
| Host FSM and word service | `genefer_track_a4_control_fsm_v2.sv`, `genefer_track_a4_host_word_v1.sv` | v2 removes impossible two-bit >3 check while retaining zero-pass rejection; AW5 shell native passed |
| Runnable host shell | `genefer_track_a4_host_shell_v2.sv`, SHAf62dab985ebb34f760e9d568b835ce17bc52fd37fdd3b71c0f0a99ae182058da | v1 warning-fatal build archive preserved. v2 AW5 independently PASS, receipt29e36dd2:155 commands,13 readbacks,5 expected errors,310 holds,2219 ticks,max latency100. Square external and disabled |
| Post-NTT service | `genefer_track_a4_post_ntt_v1.sv`, SHA742b21c1025e65704378f144a7f088efcd2daae261c4c9005a7ef28ea226c903 | Executable real CRT/carry/route/image/reducer gate, ticket8399ad72;20 small-N cases, two local tests pass. Unretimed arithmetic baseline, not r13 fit candidate |
| Three-field sequencer | `genefer_track_a4_ntt_sequencer_v1.sv`, SHAf5ba08a60c0ebae30aa00c3485fefc0c6376d7901d6cf5e47d1baf8b8627cbe0 | Aethia isolated native reported PASS:10 transforms,1440 words,NTT246/seed122/cold roots3089; reporta10c62df, independent result review pending |
| Whole64 square service | `genefer_track_a4_core_v3.sv`, `genefer_track_a4_square_backend_v3.sv` | v2 failed build preserved. v3 AW5 independently PASS091e31d6:14 squares/256 read words/808 holds; warm314 backend/316 host, cold328/330 or3417/3419; no full-N promotion |
| Larger native gates | AW8 existing v3 bench; AW16 representative harness897e1ffd | AW8 package manifest2992d812/archive822027e0 ready; AW16 independently PASS6f0040de:16 squares,524288 read words,1572904 holds. Warm24720/24722, cold cached28828/28830, loaded37571/37573; deterministic representative scope only |
| P4 provisional fit | `track-a4-p4-provisional64-aws-fit-v1` | Project manifest7fe6e455; exact29 SV,AW16/10ns/seed1/6workers. Routed raw result: setup−5.292ns, reported65.39MHz. Image correction/range-check→quiet/start control→NTT RAM enable failed; no100MHz promotion |
| Registered admission successor | `genefer_track_a4_square_backend_v4.sv` SHAaf1e4bb2 / core877e6bea | Ticket e3ca5d11; isolated+1edge NTT admission register. AW5 normal independently native PASS f9a7458e; five boundary controls native PASS a65a2182, independent replay parallel; AW16 running, typed mutants queued/prepared, new fit pending |

## Edge and ownership contract

All children reset valid/eligibility; physical RAM is not reset. Outputs with
valid propose writes and do not alone establish image completion. The outer
controller publishes eligibility only after counts, generations and child-error
tails agree. All source lengths below are proposed until their native gate passes.

| Path | Local edge contract | Outer handling |
|---|---|---|
| Block lane | coefficient E0 → digit E25 → boundary E28 → done E29 | Sixteen contiguous blocks; rotate and negate final wrap outside lane |
| Field block route | read E0 → registered RAM/tag/mask after E0 → CRT consumes E1 | Independent read/write offsets/masks; same-address collision rejected |
| Shared setup | begin E0 → result/check E97 | One exact reciprocal/A calculation per accepted reload/base change |
| Canonical cell | accepted edge registers digit and carry | Host envelope differs from S3; carry[−2,2] |
| Canonical controller | begin E0 → first read E1 → pass done E(N+3) | Up to3passes; special−1 materialization addsN/16+1 |
| Host-word service | begin E0 → RAM access E1 → response/check E2 | Signed word overwrite clears its correction in frontend |
| Outer FSM | START/WAIT adds2edges per child invocation | RELOAD setup additionally waits one cancel-guard edge |

The24712 planning model describes the original combined NTT/carry/patch
schedule, before r13 transfer-register requirements. The conventional outer
square-service wrapper adds2edges around its child. Neither24712 nor24714 is
a current retimed integration target: source/destination transfer registers and
their final-write/error drains must first be budgeted and measured. Native shell
reports command latencies without substituting model estimates.

The executable v2/v3 source-derived event budget is captured by
`reference/track_a4_registered_schedule_v1.py`: source read E0, field RAM read E2,
CRT consumes E5, first digit E46, first field RAM write E54. Thus actual RAM-to-RAM
displacement is52, not48 (source launch-to-write is54). Post v1's internal count
becomesT+62; the backend's destination drains/check make start-post through
completion T+65 counted edges. Assuming the inherited NTT phase counter20558,
warm backend cycles24720 and host latency24722 were predictions. The AW16 v3
representative archive independently confirms those measurements, NTT20558,
post4158, cold prefill4106 and cold-backend penalty4108. AW5 independently
confirms post64,warm314/316,cold prefill12 and cold penalty14. Neither scoped
native result establishes PRP/soak/fault completion or a routed clock.

In-place host canonicalization invalidates field-prefill eligibility. The next
square pays the planned4102 conversion clocks at AW16. Uninterrupted dependent
squares and squares following host readback must be reported separately. This
4102 estimate also predates r13 and will gain the explicitly derived transfer
pipeline/drain overhead in the executable backend.
The current source-derived replacement is4108 extra backend cycles at AW16,
including a4106-cycle cold-prefill child and its two outer handoff edges.

## r13 timing rule

Every top-level datapath transfer needs source and destination registers with
aligned valid/address/mask/generation. The T5 prefill RAM-to-reducer-to-field-RAM
path failed timing; its routing success is not a clock promotion. A4 post v1 is
retained as an unretimed functional reference. Integration will add explicit
field-local transfer registers before any fit and rederive the original48-edge
read/write displacement. A delayed final write cannot be called complete until
the destination's registered error tail has been observed.

## v3 admission repair

The first whole-core v2 build failed before simulation with the exact loop
`post.fault -> post_write -> backend.fault -> start_post -> post.fault`.
The collected build log is preserved in
`results/throughput-20260929/track-a4-core-v2-aw5-aethia-v1`.
v3 does not suppress the warning or edit v2. Prefill source writes are admitted
only in COLD_WAIT; post writes only POST_WAIT; post reads NTT_WAIT/POST_WAIT.
An illegal token rejects both source transfers and sets a registered sticky
admission error. The raw violation also overrides same-edge CHECK completion
in sequential priority, while cancel wins last. Child start controls never
depend on child combinational write-valid through the fault signal. Transfer
pipeline and DRAIN/CHECK edges are unchanged. Source guard/tests are not a
substitute for the next native compile and end-to-end run.

## Fixed RAM frontend contract

Sixteen32-bit1R1W banks, bank=block and row=offset. Unified independent masked
row read/write ports return signed33 effective words with captured correction,
tag and generation. A natural address uses one selected bank; cold prefill uses
all16. Same-row intersecting masks reject both operations; no forwarding.

`configure` is exclusive with RAM/metadata actions. Clear-image configuration
clears corrections and shadow validity; preserving configuration retags an image
or applies a previously validated base change. Configure overlaps a service's
begin edge, since canonical/host RAM requests follow one edge later. Warm square
may clear/retag digit metadata while launching an already-prefilled NTT.

STREAM writes capture the first two digits; CANON/HOST overwrites invalidate the
selected shadow validity. HOST writes clear the selected correction at offsets0/1.
Metadata actions are exclusive: clear corrections, set canonical−1, or commit
all16 terminal boundary pairs with rotation and final-wrap sign.

## v4 registered admission repair

P4 STA's ten worst reported paths share corrected image RAM output through
`cold_prefill.input_legal -> fault -> field_write_en -> admitted_write ->
transfers.busy/quiet -> start_ntt -> sequencer block-port gate -> RAM ena`.
The combinational `busy` term includes current source write proposals even
though normal FSM ownership makes cold-prefill and NTT-start mutually exclusive.
The raw path is15.225ns (10.638 wire,2.417 cell,2.170 RAM clock-to-out),12 logic
levels and fanout2323 at the global start gate. This is not a reducer data path.

v4 captures `seq_ready && transfer_quiet && !fault` into a preserved
`ntt_admission` register while in NTT_START. A new NTT_LAUNCH state presents that
token on the following edge; only registered child/admission errors and external
cancel/busy-begin can inhibit it. Raw ownership faults still reject both source
transfers immediately and win sequential failure, without reconnecting raw
image legality to the global launch gate. The token defaults clear every edge
and explicitly clears on reset/fault/cancel; its configuration is the existing
operation-latched base/generation. Cold image configure is aligned with the
actual launch token. Payload checking, arithmetic and all transfer/tail stages
are unchanged.

Native v4 cost is+1 backend/+1 host edge per square: AW16 warm24721/24723,
cold cached28829/28831 or loaded37572/37574. Child phase counts and52-edge RAM
displacement remain unchanged. Full-size representative owner replay6d6d40c1
now confirms these cycle values; independent replay4106cd4b is closed.
The simulation-only boundary probe uses real host/NTT/RAM children and a true
completed warm-up square before injecting faults at the next admission. It
checks actual read/write masks on the coincident raw-fault/start edge and after
registered cancellation; five typed mutants target bypass, late fault, stale
token, raw re-gating and unowned-write admission. Native control validation now
passes as recorded below; typed mutant executions remain pending.

The v4 **normal AW5** native archive now confirms the isolated+1 contract:
warm315 backend/317 host, cold cached329/331, loaded3418/3420; childNTT246,
post64 and cold-prefill12 remain unchanged. Archive
`results/throughput-20260929/track-a4b-core-v4-aw5-gcp-v1`, report `f4b97dea…`,
contains14 squares,404 commands,256 readbacks and808 holds. Owner replay
`65a96f4a…` verifies16 artifacts/118 sources/146 generated files/gzipELF.
Independent receipt `f9a7458e…` closes the same scoped replay and nine altered-
output negatives; all14 rows differ from v3 by exactly+1 backend/+1 host cycle.
Boundary controls now pass natively: report `a65a2182…`, owner replay
`200a3064…`, five cases normal/raw/late/cancel/reset each36 commands and
raw/late/cancel/reset each12 no-RAM edges. Independent replay is parallel.
AW16 representative invocation `f300058099f445abb9d999a7282cdd52` completed
07:58:24–08:16:47UTC, reportc7e712c4. Owner replay6d6d40c1 verifies16 artifacts,
128 source files,155 generated files/gzip ELF and all16 strict schedule rows:
786452 commands,524288 readbacks,1572904 holds. Simulation1029.176s, below1800s
bound. Typed mutants are queued/running separately. These deterministic recipes
are not random/full-fault/PRP/1000-square-soak or routed timing qualification.
Independent AW16 receipt4106cd4b verifies16 native squares/eight full images and
524288 word comparisons;12 negative-output fixtures and4 pure tests pass. The
five directed admission mutants now all have native owner PASS (batch reply
`2026-10-01-A4b-admission-mutants-native-v1.md`); independent batch replay and
advisor verification remain promotion gates.

## Current policy and qualification update (r53)

All five actual admission mutants have independent scoped PASS28bf62af,
in addition to normalf9a7458e, boundaryf9ae178f and representative AW164106cd4b.
Adopted r53 makes the existing source structural949 check the only design
pre-screen for changed-RTL exploratory fits. DA/finite early-placement/graph
are post-fit diagnostics, not launch blockers. Inventory47469dff remains source
declarations and explicit justifications, not exhaustive netlist coverage.
The field-return immediate rejection cone remains a diagnostic target.
Fit_queue owns the isolated A4b physical run; no clock/promotion is inferred.

## Earlier next-work record (r47 policy superseded above)

The v4 ticket e3ca5d11 has independent source GO b8334b55. Under r25/r26/r27,
the A4b owner submits finite jobs through shared automated admission, without a
new main per-job release. Independent replay and advisor verification remain
promotion gates. The shared source/settings inventory checker94945704 has
independent scoped PASS d40706a4; this is not native netlist coverage. The A4b
nine-transfer/fifteen-stage inventory was source-only. Adopted r47 now replaces
the exhaustive-graph requirement with source-port justification, candidate
post-synthesis Design Assistant and early-placement top100 cross-block one-cycle
path screening. Additive inventory `track-a4b-prefit-source-v2/inventory.json`
SHA47469dff covers25 transfers/19 declared stages and every host/backend internal
core wire except unused square_busy, with explicit control/config exceptions.
The unchanged949 checker source_inventory passes and two tests reject omitted
port/exception cases. In particular, field response metadata→protocol_fault→
allow_transfer→RAMenable remains an explicit immediate-rejection control cone
for the early timing screen; no newly registered or exhaustive coverage claim.
Actual DA/early-placement evidence remains required. Exhaustive graph diagnostics
move to LATER and are no longer the fit gate.

The original normal AW5 and real-RAM boundary lint packets are preserved under
`artifacts/track-a4b-aw5-lint-packet-v1` and
`artifacts/track-a4b-boundary-lint-packet-v1`. Both were dispatched and retained
91 style warnings with no WIDTH/UNOPTFLAT. Separate frozen-v3 actual lint
matches all91 full warning records under exact lineage mapping; independent
receipts `d82832ae…` / `745bf442…` bind historical normal-AW5 debt. Its fresh
native packet then passed as reported above. Directly adopted r38 applies to
future style-class admission through the shared runner. GCP quota-v1 reads now
establish actual UID1001 tmpfs headroom; static byte/inode reservation checks
are refreshed before each job, never inferred from global free space alone.

1. Complete independent AW16 replay and collect the independent typed mutant gates (four queued GCP, one running F16). AW5, boundary controls and representative AW16 have native owner PASS. Recheck live jobs, PAUSE, source/tool identities, quota/resources, locks and budget before each dispatch.
2. Qualify remaining fault/mutation gates in parallel; fit v4 as the isolated admission change after reviewed AW16, r47 source/DA/early-placement gates and budget admission pass.
3. Audit the new routed path/register cut, resource changes and setup/hold margins; no clock is inferred from source intent.
4. Run full fault/recovery/mutation qualification, AW16 soak and r11 PRP gates before timing/throughput promotion.
5. Promote no profile/cycle/clock result until the complete native and independent evidence closes.
