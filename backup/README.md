# Curated FPGA source and evidence backup

This branch preserves a stable byte-for-byte snapshot of independently written FPGA RTL, arithmetic references, tests, tools, technical notes and compact record evidence. The chart on `main` remains a separate history. The live source snapshot is work in progress; filenames and presence in this branch do not establish qualification.

Read the [two-context correctness correction](CORRECTNESS-2026-10-02.md): older full-GFN16 two-context projections and promotion readiness are withdrawn after a repeated 32-bit cold-correction condition was found. Finite tests and scoped clocks are preserved; the R6 fix has separate, still-incomplete qualification.

The adopted internal compute-only record is P16 timing7, one context, canonical pipeline1: root `0011468ec67d7ca7ebb86fac88103fd19ea0207dc75685289da64d508228ea28`, projected cold compute time 178.632348730264 seconds at the selected audited 11.044 ns period. The printed setup reserve is only 1 ps. This is neither measured complete PRP/board runtime nor board timing sign-off. Exact adoption and independent-review receipts are under `fpga/results/throughput-20260929/`; retained fallbacks include the P16 baseline, P8 and F3.

The original two-context storage2 candidate has an immutable 53-source physical project under `fpga/results/throughput-20260929/trackS-c2-storage2-route14-v1/project`. Its structural inventory is retained separately. It has no inherited timing7 clock or promotion. The new storage2 + packed delays + root register + term lookahead composition was still being prepared when this snapshot was taken; its exact qualified candidate capture is pending. General generator source here is labeled WIP.

`manifest.json` lists retained paths, byte sizes and SHA-256 identities, the source closures for captured physical projects, archive identities for exact extracted timing members, and per-path omissions. Every retained original file was compared before copying and against the source after copying. Original files are not silently sanitized. Raw private manifests with personal/account paths are omitted; the newly generated public manifest explicitly indexes the exact unchanged sources instead.

Four timing archives contribute exact raw four-corner summaries, clocks, effective constraints, checks and retained source/control files under `backup/timing/`. They cover current P16 timing7 11.044 ns, its adjacent failing audit, and selected P16 baseline/P8 fallback audits. Retained receipts preserve numerical/cycle conclusions and source pins. The source files can be restored and resynthesized with separately obtained tools; the public snapshot cannot recreate the original saved placement database.

This is a curated backup, not a complete evidence archive. Full native archives, large vectors and path lists, binaries, PCH/object/cache output, QDBs, private queue operational logs, account/access/budget configuration, proprietary installers/vendor license text and machine evaluation state remain local or on retained worker disks. Some operational scripts and manifests containing personal/admin markers are omitted whole. No authorization to delete these retained witnesses follows from this branch.

No third-party implementation repository or vendor tool is vendored. Existing source notices are preserved, the upstream lock and `fpga/docs/SOURCES.md` record provenance, and no new license is applied to upstream material. Tool availability, device support and licenses are prerequisites supplied separately.

To verify a restored checkout:

```sh
node backup/verify.mjs
PYTHONPATH=fpga python3 -m unittest fpga.tests.test_reference fpga.tests.test_montgomery27_canonical_structure
```

The selected 23 pure reference/source tests passed in the isolated copied checkout. They check restored arithmetic/source behavior; they do not constitute native RTL, physical or board validation.
