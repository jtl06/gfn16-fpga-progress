# PrimeGrid workload choices for the Catapult FPGA

Read-only engineering survey, 2026-09-29. **No demonstrated CPU or GPU speedup
exists for our FPGA implementation.** A workload being easy to implement does
not imply an advantage over tuned CPU/GPU software. No project selection,
account, work allocation, or RTL scope was changed by this survey.

## Recommendation

For a new performance experiment, investigate **compact-integer sieving** before
another giant-number primality test. This is an engineering hypothesis: smaller
per-lane state, many independent primes, custom-width modular arithmetic, and
interleaved pipelines may use this Arria 10 more effectively than a large
transform/normalization feedback loop. The specific winner remains unknown.

1. **SR5 sieve: investigate for a CPU-relative opportunity.** Current official
   applications list CPU builds, unlike GFN and FC's GPU builds. However its
   baby-step/giant-step algorithm adds table lookups and memory-management
   complexity: it is not just independent modular multiplies. PrimeGrid's
   developer explains that complexity depends on the exponent interval, not
   sqrt(p). Profile arithmetic versus lookup costs before designing lanes.
   [Applications](https://www.primegrid.com/apps.php),
   [SR5 algorithm discussion](https://www.primegrid.com/forum_thread.php?id=10515&menu=top).
2. **Factorial/compositorial sieve: investigate for a compact arithmetic kernel,
   but expect strong GPU competition.** Official description gives the current
   candidate-index interval as n=100,000..2,000,000 after sieve depth 250T, with
   the initial approximate depth target 3000–4000T. These target factors occupy
   about 52 bits, not millions of bits; this width is derived from that stated
   target, not a claim that today's exact frontier was retrieved. The app
   combines factorial and compositorial sieving and is already GPU-only.
   Its remaining project lifetime may be short, so confirm useful work remains
   before investing in a port.
   [Official FC introduction](https://primegrid.com/forum_thread.php?id=11654),
   [Project-lifetime discussion](https://www.primegrid.com/forum_thread.php?id=2727).
3. **GFN/LLR primality: best continuity with our existing work and direct
   large-prime objective, not currently the best-supported speedup claim.**
   Large repeated squarings, transform traffic, carries, and long dependency
   chains must compete against mature software. LLR uses Prime95's gwnum
   library; GFN has current CPU and GPU applications.
   [Official source index](https://www.primegrid.com/forum_thread.php?id=6359),
   [Applications](https://www.primegrid.com/apps.php).

This is an investigation order, **not a measured performance ranking**. Sieves
eliminate composite candidates; they do not themselves deliver the notable
large-prime discovery the user originally wanted.

## Tempting but unavailable historical targets

**Wieferich/Wall–Sun–Sun (WW)** has attractive small per-prime state and many
independent tests. However PrimeGrid completed its search below **2^64** in
December 2022; the administrator confirmed workunits were purged in January
2023. It is not a current allocation target. The mathematical tests involve
arithmetic modulo p², so a naive full-width implementation near that frontier
needs up to **128-bit residues**, not merely 64-bit modular arithmetic. A search
above 2^64 would be new search/software/coordination work, not plugging into an
existing WW queue. GPU implementations already existed.
[Official completion thread](https://www.primegrid.com/forum_thread.php?id=10037),
[Official mathematical definitions](https://primegrid.com/forum_thread.php?id=9436&menu=left),
[Official source index](https://www.primegrid.com/forum_thread.php?id=6359).

**PPS sieve** is also suspended. Its final announced target was 125P, or
1.25e17 (a 57-bit factor range); historical software and CUDA source are useful
references, not evidence of current BOINC work. Distinguish PPS *sieving* from
PPS/PPSE *primality testing*, which processes vastly larger candidate integers.
[Suspension announcement](https://www.primegrid.com/forum_thread.php?id=10422),
[Depth target and shutdown discussion](https://www.primegrid.com/forum_thread.php?id=10333&menu=top&nowrap=true),
[Author's PSieve-CUDA repository](https://github.com/Ken-g6/PSieve-CUDA).

## Benchmark gate before any pivot

Measure the same candidate/range, algorithm obligations, proof/checkpoint work,
and validation outputs on a tuned CPU, an appropriate GPU, and the FPGA.
Report separately:

- validated tasks/second or tested range/second;
- total-system joules per validated task, including host and board;
- comparable purchase cost and time-to-solution.

Do not infer acceleration from arithmetic frequency, DSP count, credit rates,
or comparing different task sizes. Parent research found a strong cautionary
baseline: PrimeGrid's official GFN-19 discovery report records a 3.737-million-
digit test in 15 minutes 23 seconds on an RTX 4080 SUPER. That is **not a matched
benchmark** against our projected approximately 13-hour GFN-16 run, but makes
claims of a present FPGA advantage over GPUs untenable without much better evidence.
[Official GFN-19 discovery report](https://www.primegrid.com/download/GFN-13427472_524288.pdf).

Source limitations: some public GitHub/source endpoints and live sieve-frontier
pages failed to load during this bounded survey. Current exact SR5/FC frontier
and low-level deployed kernels were therefore not independently audited here.
No numeric FPGA/CPU/GPU speedup is asserted.
