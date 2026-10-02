# Trusted shell placeholder

There is intentionally no board top level or QSF here yet.  Creating one before
observing the used card would turn uncertain pin/device assumptions into an
electrical risk.

After arrival, this directory will contain a human-reviewed, hash-locked
JTAG-only shell exposing a narrow kernel contract:

```text
clock, reset, start
on-chip input/output RAM request-response ports
busy, done, fault
cycle counter and watchdog trip
```

The shell will own clock generation/gating and reset.  Kernel candidates will
not instantiate device primitives or touch external pins.

