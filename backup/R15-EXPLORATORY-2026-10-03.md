# R15 exploratory source checkpoint — 2026-10-03

R15 is exploratory and NOT adopted. FIELD100 seed2 remains the accepted record; its unchanged [technical summary](CURRENT-TECHNICAL-SUMMARY.json) binds own11.840ns PASS /11.838ns adjacentFAIL and95.7689143912s/test amortized internal projection, not individual latency or measured fullPRP. Historical pre-R6 HOLD and upstream notices remain unchanged.

This incremental snapshot adds exact captured60-source R15 compute AW8/full-normal bundles, portable authored host/interface code and tests, and source provenance. The own compute-only bracket is11.728ns PASS /11.726ns FAIL; it does not become the shell clock. The real shell physical fit is PENDING. Current editable source snapshots are not interchangeable with captured qualification sources.

The own2/100/1000 ledger keeps its conditional/model-only full-sample flags. Lean host GL is assumed rather than an RTL fault-coverage claim. Software checkpoint/rollback and mock transport/VFIO tests are bounded software evidence, not physical DMA, device binding, board operation or BOINC project qualification. No board/PrimeGrid submission is performed.

## Restore and legal boundaries

Run `node backup/verify.mjs` for all file/source-closure hashes. Portable pure tests are listed in the publication receipt; separately obtained GMP/BOINC/toolchains are not included. Existing per-file notices and `fpga/host/THIRD-PARTY-NOTICES` are preserved. No blanket Apache2 license or vendor/upstream relicensing is added. Generated Altera/BOINC prerequisite source, proprietary tools/licenses/binaries/QDBs/layouts, credentials, private operational/financial data and root workspace Git history are excluded. Public reports/RTL cannot restore a saved QDB.
