# Folded NTT27 root routing

The separately pipelined root-routing candidate still had two BANKS-wide XOR
permutation networks. This new candidate removes the last one algebraically,
while retaining the same eight-clock RAM writeback distance and arithmetic.
No existing engine or square-core selection is changed.

Let b be the destination physical data bank, B its group-dependent data-bank
contribution, R the group-dependent root-bank contribution, r the stage rotation,
and M the broadcast mask. M is `(1<<stage)-1` on early stages and all KW bits
on later stages. It is not the physical root-read enable mask.

The original selected root bank is

`R XOR rol((b XOR B) AND M, r)`.

Bit masking and rotation distribute over XOR, giving

`[R XOR rol(B AND M, r)] XOR rol(b AND M, r)`.

The bracketed contribution is captured on the RAM read edge. The first root
permutation uses that folded contribution; rotation, the existing pipeline
register, broadcast and physical pair selection follow. The final data-bank
XOR permutation is absent. Pointwise roots bypass this machinery exactly as
before. Data operands, valids, output-kind tags and all writeback tags retain
their routing-pipeline alignment.

`reference/ntt27_folded_routing.py` checks all bank/data-contribution pairs,
rotations and broadcast masks for index widths1..7:1,126,248 checks. The common
arbitrary R cancels from the equality, so no enumeration of that redundant
dimension is necessary. This proves the index identity only, not RTL timing,
handshake behavior or the arithmetic datapath.

The initial N16/L16/P1 smoke gate passed6 steps, including independent transforms,
cached squares, host fuzzing and canonical-input rejects. Full L16/L64, all-field,
AW1/AW4/AW16, every-runtime-size and whole-integer gates are running, with13
fault variants including wrong folded contribution, rotation direction and use
of the incorrect physical root-read mask. The full gate is required before fit.

Expected cycle counts are unchanged from the routepipe candidate:78,136 atL16
and19,768 atL64 for a full-N five-phase arithmetic square. No fitted ALM/DSP/RAM,
Fmax or whole-core throughput gain is claimed. Moving work into the narrow
bank-control path can introduce a different critical path, which also needs fit.

RTL candidate identity:
`475a7500e58485c943961729334f8c03e35eb52095657813f8c770d29cb5167c`.
Files are the new `genefer_ntt_banked27_folded_engine.sv`, the C++ bench
`ntt_banked27_folded_engine.cpp` and `reference/ntt27_folded_regression.py`. The frozen native27 file is
included only for its unchanged butterfly definition, alongside sparseMont27
and SDP RAM. Remote gate:
`/home/jtl/gfn-fpga-lab/agent-work/ntt27-folded/fpga/artifacts/full-v1`.
Smoke report is archived in `results/throughput-20260929/ntt27-folded/`.

Independent read-only RTL review confirmed that the folded bank contribution
uses read-edge metadata, the mask is the broadcast mask rather than the
physical read mask, and the route register, pointwise bypass and writeback
metadata retain their prior alignment. No correction was required by review.
