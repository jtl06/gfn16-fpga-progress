# P16 baseline: conservative record verification request

- Status: needs-advisor-verification; 2026-10-02 02:06 UTC. Not adopted.
- Candidate: original P16 diet, CORR2/MONT1/shared-MLAB/canonical1, one context. Exact paired69 numerical source contains routed58; no timing7/packed/root-retiming inheritance.
- Selected conservative internal period **12.604 ns**, four-corner setup +.010 ns, hold +.005 ns, pulse width +5.652 ns. Same-layout12.592 ns fails−.002. The requested2ps bracket continues; this is not a fastest-clock claim.
- Sample base604832956/N65536/K1911814: cold668025+(K−1)×8459 = **16172694192 cycles**, **203.840637595968 s compute-only projection**. Cached roots subtract99cycles. Special final image adds65536cycles once. No measured full-size PRP or board runtime.
- Own small PRPs/short/100/field/host faults and uninterrupted1000 independently reviewed. Long run:1000 dependent operations,500doubles,65536 signed96 words equal independent reference, one reset/load/start/readback,9118566 cycles.
- Routed resources:314622needed/374930placedALMs,41915/42720LABs,581815registers,1911M20Ks,1300needed/1318physicalDSPs.98.12%LAB occupancy routed but leaves little margin.

Evidence: [clock/source/projection review](../../../results/throughput-20260929/s4-p16-diet-clock-independent-provisional-v1.json), [long review](../../../results/throughput-20260929/s4-p16-diet-long-independent-v1.json), [ledger review](../../../results/throughput-20260929/s4-p16-diet-ledger-independent-v1.json), [owner consolidation](../../../results/throughput-20260929/s4-p16-diet-consolidation-owner-v1/handoff.json).

Request: verify this conservative source-bound compute record; any tighter selected period gets its own reviewed delta. External configuration/load/readback and board interfaces are excluded;193inputs/797outputs are virtual/unconstrained, reset recovery/removal has no paths. P8 remains adopted until acceptance. R84 two-context and timing7 are separate unqualified variants.
