# NTT vector access and control optimization

Three separate candidates extend the banked, cached DIF/DIT engine without
changing frozen predecessors. Vector access removes the scalar host bottleneck;
registered stage setup moves control decoding off the issue path; shared
arithmetic removes the dedicated pointwise Montgomery pipeline from each lane.
None changes the modulus, transform ordering, root-cache contents, or lane limit
of sixteen. Board operation and fitted speed remain separate validation steps.

## Vector host contract

`genefer_ntt_banked_vector_engine.sv` uses a vector width equal to LANES.
Lane h occupies bits `[32*h+:32]` and addresses `vector_addr+h` in natural
host order. The address must be LANES-aligned and below N, with live idle
`size_log2` in 1..AW. Masks clip lanes beyond N, including N smaller than LANES.

Vector writes take priority over vector reads; either request suppresses all
scalar traffic, including root writes, even when the vector descriptor is
invalid. Invalid descriptors pulse `host_error` without memory effects. Empty
effective writes do nothing; empty reads return registered valid with mask zero.
Response data is meaningful only in masked lanes. Busy or start suppresses all
host requests and responses. Scalar physical addressing retains its old rules.

The full regression passed for all three fields at four and sixteen lanes,
AW1, AW4 and AW16, including repeated cached integer squares, 4000 randomized
host requests per executable invocation, resets and nine interface mutants.
The frozen RTL SHA256 is
`023495bcac6d2ce23c54e25739aba00b0c4d1209db3325b38632068d5c956d0d`.

## Registered stage control

`genefer_ntt_banked_predecode_engine.sv` adds one STAGE_SETUP clock before each
transform stage. It registers pairing, root rotation and shift, masks, fixed
address-bit source indices, and the physical root-read increment. The increment
is `min(LANES,2^stage_bit)` per issued group; simulation independently compares
it with the number of enabled root-bank ports. Pointwise root reads are N for
op2 and zero otherwise. The setup subtraction is explicitly five bits wide
before constant modulo, avoiding unnecessary signed 32-bit setup arithmetic.

For N=2^L, B=LANES and G=ceil(N/(2B)), an unnormalized transform costs
`L*(G+8)` clocks: G issue clocks, one setup clock and seven drain clocks per
stage. The wait counter counts drain only, so it stays `7L`. Pointwise work
still costs `ceil(N/B)+5` clocks. Normalized inverse adds one pointwise pass.

The frozen SHA256 is
`3694e9e2c0ab11866736754eeedbd65f2449e451dc275e0f3e98e7838af7f8f1`.
Full tests passed all three fields at four and sixteen lanes, AW1/AW4/AW16,
every runtime size N2 through N65536, repeated cached CRT and bigint squares,
host arbitration, resets and four stage-control mutants. Reproduce on aethia:

```sh
python3 -m reference.ntt_predecode_regression --output artifacts/predecode-full
```

The completed report is in the isolated aethia workspace
`agent-work/ntt-predecode-v2/fpga/artifacts/predecode-full-v2/report.json`.
The coordinated field1 AW16 four-lane diagnostic fit reported 107.40 MHz Fmax,
setup +0.689 ns at 100 MHz and hold +0.021 ns. It used 7191 needed ALMs
(7382 raw), 4082 registers and 512 M20Ks; raw DSP blocks were 24 and
packing-adjusted DSPBlocksNeeded was 16. This is a diagnostic fit, not measured
board operation. The packed predecessor reported 95.01 MHz and 6069 needed
ALMs, but lacks vector ports, so the difference cannot be attributed solely
to predecode. A vector-only fit would provide the isolated comparison.

## Shared arithmetic candidate

`genefer_ntt_banked_shared_engine.sv` reuses the unchanged six-stage DIF/DIT
butterfly for pointwise requests by selecting DIT with u=0, v=lhs and w=rhs.
Its y0 output is the Montgomery product; y1 is discarded for pointwise work.
The selection uses the request kind, not active_op: op0 normalized inverse
must transition from butterflies into pointwise normalization correctly.

A six-clock request-kind tag separates butterfly and pointwise output valids.
Both operations now use RAM row and bank-half tags at index six, giving seven
clocks from a RAM read edge to its write edge. Pointwise drain increases from
five to seven clocks. Stages drain completely before the next stage starts;
no RAM replication or additional mixed-port collision dependency is introduced.

Full-size warm arithmetic clocks, excluding external transfers and CRT/carry:

| Candidate | Four lanes | Sixteen lanes |
| --- | ---: | ---: |
| Frozen vector | 311535 | 78063 |
| Frozen predecode | 311567 | 78095 |
| Shared candidate | 311573 | 78101 |

Sharing removes one RTL Montgomery pipeline per lane. It does not establish a
proportional fitted DSP saving: vendor raw fixed-point DSP usage and
packing-adjusted DSPBlocksNeeded must be reported separately. Input muxes can
also affect timing. Full tests passed all three fields at four and sixteen
lanes, AW1/AW4/AW16, every runtime N2 through N65536, repeated cached CRT and
bigint squares, host arbitration, exact transition and drain resets, and all
six sharing mutants. Its frozen
SHA256 is `f8fb1ca640e6fbf9d6194738f83d9923396260c14dc30eb877d9e02029660054`.
The dedicated regression is `reference/ntt_shared_regression.py`; it adds exact
reset points around the transform-to-normalization transition and final drains.
The completed report is in the isolated aethia workspace
`agent-work/ntt-shared/fpga/artifacts/shared-full-v1/report.json`.
