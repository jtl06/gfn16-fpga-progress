"""A4 explicit host/control contract; small-N arithmetic, full-N events only.

No old immediate-read/load/start timing is inherited. In-place canonicalization
invalidates the NTT image; a later square then pays its separate prefill cost.
All cycle counts are proposed schedules, not native measurements.
"""
from dataclasses import dataclass

from fpga.reference import track_a4_blockcarry_model as carry


def canonicalize(values, base):
    """At most3 serial passes; no whole-integer modulo in this implementation.

Each pass yields D+q*b^N. Fold q by using next-pass initial carry -q.
q==1,D==0 and q==-1,D==b^N-1 are both the canonical exceptional -1.
Without recognizing them, zero and all-(b-1) arrays alternate forever.
"""
    n = len(values)
    if n > 256:
        raise ValueError("local canonical arithmetic limited to N<=256")
    proof = carry.bounds(n, base)
    k = proof["c1_abs_max"]
    if any(type(v) is not int or not -k <= v <= base-1+k for v in values):
        # c0 can be larger than K at large bases, so admit its separately
        # proven signed digit interval as well; the resulting q bound is2.
        if any(type(v) is not int or not -max(k, base-1) <= v <= max(base-1+k, 2*(base-1)) for v in values):
            raise ValueError("effective signed digit outside profile envelope")
    digits = list(values)
    initial = 0
    traces = []
    for iteration in range(3):
        q, output = initial, []
        for value in digits:
            q, digit = divmod(value+q, base)
            if not -2 <= q <= 2:
                raise AssertionError("canonical carry bound")
            output.append(digit)
        zero, maximal = not any(output), all(d == base-1 for d in output)
        special = (q == 1 and zero) or (q == -1 and maximal)
        traces.append(dict(initial_carry=initial, terminal_carry=q, all_zero=zero, all_max=maximal))
        if special:
            return dict(digits=[-1]+[0]*(n-1), special=True, passes=iteration+1, traces=traces)
        if q == 0:
            return dict(digits=output, special=False, passes=iteration+1, traces=traces)
        digits, initial = output, -q
    raise AssertionError("canonicalization must terminate within3passes")


def canonical_plan(n, passes, special=False):
    if n < 32 or n > 65536 or n & (n-1) or not 1 <= passes <= 3:
        raise ValueError("canonical event geometry")
    # Each pass: read0..N-1, normalize1..N, write2..N+1, checkN+2.
    rows = []
    edge = 0
    for index in range(passes):
        rows.append(dict(phase="canonical_pass", pass_index=index, start=edge,
                         first_read=edge, last_read=edge+n-1, last_write=edge+n+1,
                         error_check=edge+n+2, clocks=n+3))
        edge += n+3
    if special:
        # Canonical logical[-1,0,...] is stored as zero RAM plus c0[0]=-1.
        # Clear16 block banks in parallel; the last write has a check edge.
        rows.append(dict(phase="minus_one_materialize", start=edge, last_write=edge+n//16-1,
                         error_check=edge+n//16, clocks=n//16+1))
        edge += n//16+1
    return dict(clocks=edge, phases=rows, planning_only=True)


def shared_setup(n, base):
    proof = carry.bounds(n, base)
    return dict(base=base, n=n, coefficient_limit=proof["doubled_coefficient_bound"],
                reciprocal=(1 << 96)//base, clocks=97, qualified_exact=True)


@dataclass
class Response:
    opcode: str
    error: str | None = None
    word: int | None = None
    generation: int = 0


class Controller:
    """Executable handshake contract, not an RTL simulator.

request() returns False under backpressure and changes nothing. A response
holds until take_response(); no next command is accepted while it is held.
Commands and setup are snapshotted on acceptance. Reset/child_error cancels
every pending commit and cache eligibility. Reload_begin recovers quarantine.
"""
    def __init__(self, n=32, ntt_clocks=200):
        if n > 256:
            raise ValueError("local controller arithmetic limited to N<=256")
        carry.address_row(n, 0)
        self.n, self.ntt_clocks = n, ntt_clocks
        self.generation = 0
        self.reset()

    def reset(self):
        self.generation += 1
        self.state, self.image, self.base = "empty", None, None
        self.setup, self.pending, self.response = None, None, None
        self.cache_valid, self.canonical = False, False
        self.fault_sticky = False
        self.loaded = []

    @property
    def ready(self):
        return self.pending is None and self.response is None

    def take_response(self):
        result, self.response = self.response, None
        return result

    def _queue(self, opcode, clocks=1, *, image=None, base=None, setup=None,
               canonical=None, cache=False, next_state="ready", error=None, word=None, phases=()):
        self.pending = dict(opcode=opcode, remaining=clocks, total=clocks, image=image,
                            base=base, setup=setup, canonical=canonical, cache=cache,
                            state=next_state, error=error, word=word, phases=list(phases),
                            generation=self.generation)
        self.state = "busy"

    def _normalize(self):
        if self.canonical:
            return self.image.canonical(), 0, []
        result = canonicalize(self.image.effective(), self.base)
        plan = canonical_plan(self.n, result["passes"], result["special"])
        return result["digits"], plan["clocks"], plan["phases"]

    def _reject(self, opcode, code, clocks=1, phases=()):
        self.cache_valid = False
        self._queue(opcode, clocks, next_state="failed", error=code, phases=phases)

    def request(self, opcode, *, address=0, word=0, base=None, double=0):
        if not self.ready:
            return False
        if opcode == "RELOAD_BEGIN":
            try:
                setup = shared_setup(self.n, base)
            except (ValueError, TypeError):
                self._reject(opcode, "unsupported_base")
                return True
            self.generation += 1
            self.fault_sticky = False
            self.image, self.loaded, self.cache_valid, self.canonical = None, [], False, False
            self._queue(opcode, setup["clocks"], base=base, setup=setup, next_state="loading")
            return True
        if self.state == "loading":
            if opcode != "LOAD_WORD" or address != len(self.loaded) or type(word) is not int or not -1 <= word < self.base:
                self._reject(opcode, "reload_order_or_digit")
                return True
            self.loaded.append(word)
            if len(self.loaded) < self.n:
                self._queue(opcode, 2, base=self.base, setup=self.setup, next_state="loading")
            else:
                result = canonicalize(self.loaded, self.base)
                plan = canonical_plan(self.n, result["passes"], result["special"])
                image = carry.arithmetic.load(result["digits"], self.base, 16)
                self._queue(opcode, 2+plan["clocks"], image=image, base=self.base, setup=self.setup,
                            canonical=True, phases=[dict(phase="host_write_and_check", clocks=2)]+plan["phases"])
            return True
        if self.state != "ready" or self.image is None:
            self._reject(opcode, "image_not_ready")
            return True
        if opcode == "SQUARE":
            if type(double) is not int or double not in (0, 1):
                self._reject(opcode, "double_bit")
                return True
            if self.setup != shared_setup(self.n, self.base):
                self._reject(opcode, "setup_not_exact")
                return True
            self.generation += 1
            conversion = 0 if self.cache_valid else self.n//16+6
            self.cache_valid = False
            coefficients = carry.direct_square(self.image, double)
            image, _ = carry.arithmetic.proposal.carry_split(coefficients, self.base, 16)
            post = carry.schedule(self.n)["post_ntt_clocks"]
            self._queue(opcode, conversion+self.ntt_clocks+post, image=image, base=self.base,
                        setup=self.setup, canonical=False, cache=True,
                        phases=[dict(phase="prefill", clocks=conversion),
                                dict(phase="ntt", clocks=self.ntt_clocks),
                                dict(phase="crt_carry_patch_tail", clocks=post)])
            return True
        if opcode not in ("READ", "WRITE", "SET_BASE"):
            self._reject(opcode, "opcode")
            return True
        if opcode in ("READ", "WRITE") and not 0 <= address < self.n:
            self._reject(opcode, "host_address")
            return True
        digits, clocks, phases = self._normalize()
        self.cache_valid = False
        self.generation += 1
        if opcode == "READ":
            image = carry.arithmetic.load(digits, self.base, 16)
            self._queue(opcode, clocks+2, image=image, base=self.base, setup=self.setup,
                        canonical=True, word=digits[address], phases=phases+[dict(phase="host_read_and_capture", clocks=2)])
        elif opcode == "WRITE":
            if type(word) is not int or not -1 <= word < self.base:
                self._reject(opcode, "host_digit", clocks+1, phases)
                return True
            digits[address] = word
            result = canonicalize(digits, self.base)
            plan = canonical_plan(self.n, result["passes"], result["special"])
            image = carry.arithmetic.load(result["digits"], self.base, 16)
            self._queue(opcode, clocks+2+plan["clocks"], image=image, base=self.base, setup=self.setup,
                        canonical=True, phases=phases+[dict(phase="host_write_and_check", clocks=2)]+plan["phases"])
        else:
            try:
                setup = shared_setup(self.n, base)
            except (ValueError, TypeError):
                self._reject(opcode, "unsupported_base", clocks+1, phases)
                return True
            if any(d >= base for d in digits):
                self._reject(opcode, "new_base_digit_reject_reload_required", clocks+1, phases)
                return True
            image = carry.arithmetic.load(digits, base, 16)
            self._queue(opcode, clocks+setup["clocks"], image=image, base=base, setup=setup,
                        canonical=True, phases=phases+[dict(phase="shared_setup", clocks=setup["clocks"])])
        return True

    def tick(self, *, child_error=False):
        if child_error:
            opcode = self.pending["opcode"] if self.pending else "ASYNC_CHILD_ERROR"
            self.pending, self.image, self.cache_valid = None, None, False
            self.state = "failed"
            self.fault_sticky = True
            # A held response cannot change under backpressure. The separate
            # sticky fault output invalidates eligibility even in that case.
            if self.response is None:
                self.response = Response(opcode, "child_error", generation=self.generation)
            return
        if self.pending is None:
            return
        self.pending["remaining"] -= 1
        if self.pending["remaining"]:
            return
        token, self.pending = self.pending, None
        if token["generation"] != self.generation:
            raise AssertionError("stale generation completion")
        self.state, self.image = token["state"], token["image"]
        self.base, self.setup = token["base"], token["setup"]
        self.canonical, self.cache_valid = bool(token["canonical"]), token["cache"] and not token["error"]
        self.fault_sticky |= bool(token["error"])
        self.response = Response(token["opcode"], token["error"], token["word"], self.generation)

    def finish(self):
        while self.pending:
            self.tick()
        return self.take_response()
