import random
import unittest

from fpga.reference import track_a4_control_model_v1 as m


def integer_digits(values, base):
    n = len(values)
    modulus = base**n+1
    value = sum(x*base**i for i, x in enumerate(values)) % modulus
    if value == modulus-1:
        return [-1]+[0]*(n-1)
    result = []
    for _ in range(n):
        value, digit = divmod(value, base)
        result.append(digit)
    assert value == 0
    return result


def reload_image(controller, base, values):
    assert controller.request("RELOAD_BEGIN", base=base)
    assert controller.finish().error is None
    for address, word in enumerate(values):
        assert controller.request("LOAD_WORD", address=address, word=word)
        assert controller.finish().error is None


class A4ControlTests(unittest.TestCase):
    def test_canonicalizer_against_direct_integer_with_three_pass_cases(self):
        rng = random.Random(0xA4CA)
        max_passes = 0
        specials = 0
        for n in (32, 64, 256):
            for base in (m.carry.arithmetic.minimum_base(n, 16), 10**9):
                k = 2*n+24*16
                cases = [[0]*n, [base-1]*n, [-1]+[0]*(n-1)]
                for q in (-2, -1, 1, 2):
                    # Bounded terminal words exercising wrap under/overflow.
                    for digit in (0, base-1):
                        a = [digit]*n
                        a[-1] += q*base
                        if -max(k, base-1) <= a[-1] <= max(base-1+k, 2*(base-1)):
                            cases.append(a)
                for _ in range(100):
                    d = [rng.randrange(base) for _ in range(n)]
                    c0 = [rng.randrange(1-base, base) for _ in range(16)]
                    c1 = [rng.randrange(-k, k+1) for _ in range(16)]
                    state = m.carry.arithmetic.proposal.BlockState(tuple(d), base, tuple(c0), tuple(c1))
                    cases.append(state.effective())
                for values in cases:
                    result = m.canonicalize(values, base)
                    self.assertEqual(result["digits"], integer_digits(values, base))
                    self.assertLessEqual(result["passes"], 3)
                    max_passes = max(max_passes, result["passes"])
                    specials += result["special"]
        self.assertEqual(max_passes, 3)
        self.assertGreater(specials, 0)

    def test_minus_one_oscillation_counterexample_is_handled(self):
        base, n = 300, 32
        values = [base-1]*n
        values[0] -= 1
        values[-1] += base
        result = m.canonicalize(values, base)
        self.assertEqual(result["digits"], integer_digits(values, base))
        for values in ([-1]+[0]*(n-1), [0]*(n-1)+[base]):
            result = m.canonicalize(values, base)
            self.assertTrue(result["special"])
            self.assertEqual(result["digits"], [-1]+[0]*(n-1))

    def test_square_readback_mutation_and_base_change(self):
        c = m.Controller()
        reload_image(c, 1000, [999]*32)
        initial = c.image.canonical()
        self.assertFalse(c.cache_valid)
        self.assertTrue(c.request("SQUARE", double=1))
        first_cost = c.pending["total"]
        self.assertIsNone(c.finish().error)
        expected = integer_digits(m.carry.direct_square(m.carry.arithmetic.load(initial, 1000, 16), 1), 1000)
        self.assertEqual(c.image.canonical(), expected)
        self.assertTrue(c.cache_valid)
        self.assertTrue(c.request("SQUARE"))
        second_cost = c.pending["total"]
        self.assertEqual(first_cost-second_cost, 32//16+6)
        c.finish()
        expected = c.image.canonical()
        self.assertTrue(c.request("READ", address=3))
        self.assertFalse(c.cache_valid)
        response = c.finish()
        self.assertEqual(response.word, expected[3])
        self.assertTrue(c.canonical)
        self.assertTrue(c.request("WRITE", address=7, word=-1))
        changed = expected[:]
        changed[7] = -1
        c.finish()
        self.assertEqual(c.image.canonical(), integer_digits(changed, 1000))
        prior = c.image.canonical()
        self.assertTrue(c.request("SET_BASE", base=2000))
        c.finish()
        self.assertEqual(c.base, 2000)
        self.assertEqual(c.image.canonical(), prior)
        self.assertEqual(c.setup, m.shared_setup(32, 2000))
        self.assertFalse(c.cache_valid)

    def test_profile_floor_and_base_reject_require_reload(self):
        c = m.Controller()
        self.assertTrue(c.request("RELOAD_BEGIN", base=299))
        self.assertEqual(c.finish().error, "unsupported_base")
        self.assertEqual(c.state, "failed")
        reload_image(c, 1000, [999]*32)
        self.assertTrue(c.request("SET_BASE", base=300))
        self.assertEqual(c.finish().error, "new_base_digit_reject_reload_required")
        self.assertFalse(c.cache_valid)
        self.assertIsNone(c.image)
        reload_image(c, 300, [1]*32)
        self.assertFalse(c.fault_sticky)

    def test_ordered_reload_and_exact_shared_setup(self):
        c = m.Controller()
        c.request("RELOAD_BEGIN", base=300)
        self.assertEqual(c.pending["total"], 97)
        c.finish()
        c.request("LOAD_WORD", address=1, word=0)
        self.assertEqual(c.finish().error, "reload_order_or_digit")
        reload_image(c, 300, [2]*32)
        c.setup["reciprocal"] += 1
        c.request("SQUARE")
        self.assertEqual(c.finish().error, "setup_not_exact")

    def test_busy_backpressure_reset_and_last_child_error(self):
        for where in (0, 1, -2, -1):
            c = m.Controller()
            reload_image(c, 300, [299]*32)
            c.request("SQUARE", double=1)
            total = c.pending["total"]
            frozen = c.pending.copy()
            self.assertFalse(c.request("SET_BASE", base=1000))
            self.assertEqual(c.pending, frozen)
            edge = where if where >= 0 else total+where
            for _ in range(edge):
                c.tick()
            c.tick(child_error=True)
            self.assertEqual(c.state, "failed")
            self.assertFalse(c.cache_valid)
            self.assertIsNone(c.image)
            self.assertEqual(c.take_response().error, "child_error")
            c.reset()
            for _ in range(total+2):
                c.tick()
            self.assertIsNone(c.response)
            reload_image(c, 300, [0]*32)
        c = m.Controller()
        reload_image(c, 300, [1]*32)
        c.request("READ")
        c.tick()
        c.tick()
        held = c.response
        self.assertIsNotNone(held)
        self.assertFalse(c.request("WRITE", word=2))
        c.tick(child_error=True)
        self.assertIs(c.response, held)
        self.assertTrue(c.fault_sticky)
        self.assertEqual(c.state, "failed")

    def test_full_n_event_budget_only(self):
        plan = m.canonical_plan(65536, 3)
        self.assertEqual(plan["clocks"], 196617)
        self.assertEqual(m.canonical_plan(65536, 2, special=True)["clocks"], 135175)
        self.assertEqual(m.carry.schedule()["post_ntt_clocks"]+20558, 24712)
        with self.assertRaises(ValueError):
            m.Controller(65536)
        with self.assertRaises(ValueError):
            m.canonicalize([0]*65536, 131077)

    def test_reset_during_host_normalization_cancels_response_and_base_commit(self):
        for opcode, arguments in (("READ", {"address": 0}),
                                  ("WRITE", {"address": 2, "word": -1}),
                                  ("SET_BASE", {"base": 1000})):
            c = m.Controller()
            reload_image(c, 300, [299]*32)
            c.request("SQUARE", double=1)
            c.finish()
            old_base = c.base
            self.assertTrue(c.request(opcode, **arguments))
            self.assertEqual(c.base, old_base)
            total = c.pending["total"]
            for _ in range(total//2):
                c.tick()
            c.reset()
            for _ in range(total+2):
                c.tick()
            self.assertIsNone(c.response)
            self.assertIsNone(c.image)
            self.assertIsNone(c.base)
            self.assertFalse(c.cache_valid)


if __name__ == "__main__":
    unittest.main()
