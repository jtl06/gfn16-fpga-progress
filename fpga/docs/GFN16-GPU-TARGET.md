# GFN-16 target: same-era low-end GPU throughput

Research date: 2026-09-29. Stay with GFN-16. **A matched GTX 1050 Ti or GTX 750 Ti
benchmark at b≈604,832,956–612M was not located in this bounded survey.** No
BOINC tasks were requested. The numbers below separate published observations
from provisional engineering targets; none establishes FPGA/GPU parity.

## Best specific evidence found

### GTX 1050 Ti: approximately 300 seconds, historical and qualified

In PrimeGrid's April 21, 2024 troubleshooting thread, Robbie Klinkenberg
identifies his MSI GeForce GTX 1050 TI 4GT LP on Windows 7, reports 670 valid
tasks, and explicitly says successful normal runtimes were approximately five
minutes. Surrounding logs identify Genefer GPU 23.07.0, GFN-16, and bases around
382M, with both `-p` and `-c` tasks present. The successful task linked by the
owner is result 1748385645 on host 524021. These pages were not accessible
through the research tool, so its exact candidate, mode, and runtime could not
be independently recovered.

**Important trap:** 300 seconds in the failed-task log is an intentional
error-reporting delay, not computation. The useful evidence is the owner's
separate statement that successful runtimes were similar—not that failed log.
This is a contemporaneous owner report, not a clean matched main-PRP benchmark.
[Official forum thread, messages 171443–171451](https://www.primegrid.com/forum_thread.php?id=10535).

A stronger documented hardware example, but **not GFN-16**, is PrimeGrid's
June 17, 2018 GFN-18 discovery report: GTX 1050 Ti, i7-4790, Windows 7, candidate
5205422^262144+1 (1,760,679 digits), GeneferOCL5, approximately **43 minutes** for
the verification PRP. The report's 18-minute figure belongs to a GTX 1080,
not the 1050 Ti. Do not scale either time to GFN-16 without a model and matching
software.
[Official GFN-18 report](https://www.primegrid.com/download/GFN-5205422_262144.pdf).

### GTX 750 Ti: no defensible GFN-16 seconds figure recovered

The often-searchable **21 minutes per candidate** report from November 20,
2017 concerns **GFN-17-low**, with bases around 10M; it is not GFN-16.
Similarly, the GTX 750's 18-minute example in the 2015 status thread is
GFN-17-low and is not even the Ti model. Neither is used as our target.
[2017 challenge discussion](https://www.primegrid.com/forum_thread.php?id=7670),
[2015 status discussion](https://www.primegrid.com/forum_thread.php?id=6491).

PrimeGrid's current GPU ranking lists both requested cards under GFN-16, but
the displayed relative scores alone do not establish candidate size, main
versus proof-check mode, concurrency, or a time in seconds. No runtime was
back-calculated from those rankings.
[Official GPU ranking](https://www.primegrid.com/gpu_list.php).

## Provisional targets and the current engineering gap

Use **600 seconds per completed main GFN-16 PRP as an intermediate engineering
milestone**, then **300 seconds as a provisional GTX-1050-Ti-class target**.
The 600-second milestone is deliberately chosen, not a published GPU result;
the 300-second target is only loosely grounded in the qualified historical
report above. Replace both with a matched measured baseline before claiming
parity. No GTX-750-Ti-specific target is currently justified.

For the tested base 604832956, the exponent has approximately 1,911,814 bits.
At 2,424,980 cycles per square and assumed 100 MHz, the arithmetic-only model is
`1,911,814 * 2,424,980 / 100,000,000 = 46,361.1 s = 12.878 h`.

| Engineering milestone | Reduction from that model | Average cycles/square budget at 100 MHz |
|---|---:|---:|
| 1,200 seconds / 20 minutes | 38.6× | 62,768 |
| 600 seconds / 10 minutes | 77.3× | 31,384 |
| 300 seconds / 5 minutes | 154.5× | 15,692 |

These ratios compare a projected arithmetic model with **target times**, not
two measured systems. They exclude proof/checkpoint/controller overhead and
assume representative square cost over the complete exponentiation. They
illustrate why minor clock or controller changes alone cannot close the gap.
For a throughput-only target, independent replicated candidate engines can
count, but their summed resource use, power and completed-main-task throughput
must be measured; per-candidate latency is a different metric.

## Required matched comparison

Run a fixed test candidate at n=16 and b=604832956 (and optionally a
representative current-range base) offline on the GPU—no new project assignment
is needed. Record exact Genefer version, command line, transform, driver, card,
clocks/power cap, concurrency, full result/residue, and elapsed wall time.
Measure main PRP/proof generation separately from proof checking and from any
short built-in estimate. Include FPGA proof/checkpoint work in the equivalent
end-to-end comparison when implemented.

Version matters: the author describes the 2022 introduction of proof checking
and distinguishes the separate vectorized small-GFN app. The 2025 release
changes GPU memory accesses and improves newer hardware, so a 2024 observation
cannot simply be transplanted to current software or another transform.
[Author's application/proof explanation](https://www.primegrid.com/forum_thread.php?id=9538),
[Genefer 25.04 release and memory-access explanation](https://www.primegrid.com/forum_thread.php?id=11303).

The near-term conclusion is **minutes, not hours, as the performance direction**,
with an approximately two-order-of-magnitude design challenge relative to the
current 100 MHz model. Achievability on one Catapult card remains unproven.
