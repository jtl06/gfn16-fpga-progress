// Native-only old/new cell comparison plus an independent ordinary modular
// Montgomery-R^-1 oracle. No implementation of the sparse reduction pipe.
#include "Vgenefer_a10_upper_sum_pair_v2.h"
#include "verilated.h"
#include <array>
#include <cstdint>
#include <deque>
#include <iostream>
#include <stdexcept>
#include <string>

#ifndef A10_UPPER_P
#error A10_UPPER_P must match native -GP
#endif
#ifndef A10_UPPER_FIELD
#error A10_UPPER_FIELD must bind field0/1/2
#endif
namespace {
using DUT = Vgenefer_a10_upper_sum_pair_v2;
constexpr uint32_t P = A10_UPPER_P;
constexpr unsigned FIELD = A10_UPPER_FIELD;
static_assert((FIELD == 0 && P == 104857601) || (FIELD == 1 && P == 69206017) ||
              (FIELD == 2 && P == 67239937), "canonical three-field basis");
constexpr unsigned LATENCY = 5;

void need(bool ok, const std::string& why) { if (!ok) throw std::runtime_error(why); }
uint32_t mul(uint32_t a, uint32_t b) { return uint32_t(uint64_t(a) * b % P); }
uint32_t power(uint32_t value, uint32_t exponent) {
    uint32_t result = 1;
    while (exponent) {
        if (exponent & 1) result = mul(result, value);
        value = mul(value, value); exponent >>= 1;
    }
    return result;
}
uint64_t random_word(uint64_t& seed) {
    seed ^= seed << 13; seed ^= seed >> 7; seed ^= seed << 17; return seed;
}

struct Request {
    bool valid = false, gs = false, normalized = false;
    uint32_t u = 0, v = 0, w = 0, normalization = 0;
    unsigned mode = 0;
};
struct Answer { uint32_t y0, y1; };

Answer oracle(const Request& request) {
    static const uint32_t inverse_R = power(uint32_t((uint64_t(1) << 32) % P), P - 2);
    const auto mont = [&](uint32_t a, uint32_t b) { return mul(mul(a, b), inverse_R); };
    if (!request.gs) {
        const uint32_t product = mont(request.v, request.w);
        return {uint32_t((uint64_t(request.u) + product) % P),
                uint32_t((uint64_t(request.u) + P - product) % P)};
    }
    const uint32_t sum = uint32_t((uint64_t(request.u) + request.v) % P);
    const uint32_t difference = uint32_t((uint64_t(request.u) + P - request.v) % P);
    return {request.normalized ? mont(sum, request.normalization) : sum,
            mont(difference, request.w)};
}

struct Outputs {
    unsigned valid, error, old_valid, old_error;
    uint32_t y0, y1, old_y0, old_y1;
    bool operator==(const Outputs& other) const {
        return valid == other.valid && error == other.error && old_valid == other.old_valid &&
               old_error == other.old_error && y0 == other.y0 && y1 == other.y1 &&
               old_y0 == other.old_y0 && old_y1 == other.old_y1;
    }
};
Outputs outputs(const DUT& dut) {
    return {unsigned(dut.out_valid), unsigned(dut.out_error), unsigned(dut.old_valid),
            unsigned(dut.old_error), uint32_t(dut.y0), uint32_t(dut.y1),
            uint32_t(dut.old_y0), uint32_t(dut.old_y1)};
}
struct Token { uint64_t due; Answer answer; unsigned mode; };
struct Counters {
    uint64_t cycles = 0, accepted = 0, outputs = 0, ct = 0, gs = 0, normalized = 0;
    uint64_t bubbles = 0, resets = 0, cancelled = 0;
};

class Harness {
public:
    VerilatedContext& context;
    DUT& dut;
    std::deque<Token> pending;
    Counters total;
    bool negative, flipped = false;
    Harness(VerilatedContext& c, DUT& d, bool n) : context(c), dut(d), negative(n) {
        dut.clk = 1; dut.rst_n = 0; dut.in_valid = dut.gs = dut.normalize_upper = 0;
        dut.u = dut.v = dut.w = dut.normalization = 0; dut.eval();
    }
    void check(bool ok, const std::string& tag) const {
        need(ok, tag + " field=" + std::to_string(FIELD) + " edge=" + std::to_string(total.cycles));
    }
    void reset_async() {
        dut.rst_n = 0; dut.eval();
        total.cancelled += pending.size(); pending.clear(); ++total.resets;
        check(!dut.out_valid && !dut.out_error && !dut.old_valid && !dut.old_error,
              "A10_UPPER_SUM_ASYNC_RESET_ELIGIBILITY");
    }
    void step(const Request& request = Request{}, bool rst = true) {
        check(request.u < P && request.v < P && request.w < P && request.normalization < P &&
              (!request.normalized || request.gs), "A10_UPPER_SUM_CANONICAL_INPUT");
        const Outputs before = outputs(dut);
        dut.rst_n = rst; dut.in_valid = request.valid; dut.gs = request.gs;
        dut.normalize_upper = request.normalized; dut.u = request.u; dut.v = request.v;
        dut.w = request.w; dut.normalization = request.normalization; dut.eval();
        if (rst) check(outputs(dut) == before, "A10_UPPER_SUM_PRE_EDGE_LEAK");
        else check(!dut.out_valid && !dut.out_error && !dut.old_valid && !dut.old_error,
                   "A10_UPPER_SUM_RESET_HELD");
        const Outputs before_falling = outputs(dut);
        dut.clk = 0; context.timeInc(1); dut.eval();
        check(outputs(dut) == before_falling, "A10_UPPER_SUM_FALLING_EDGE_LEAK");
        dut.clk = 1; context.timeInc(1); dut.eval(); ++total.cycles;
        if (rst && request.valid) {
            pending.push_back({total.cycles + LATENCY, oracle(request), request.mode});
            ++total.accepted;
        } else if (rst) ++total.bubbles;
        const bool valid = rst && !pending.empty() && pending.front().due == total.cycles;
        check(bool(dut.out_valid) == valid && bool(dut.old_valid) == valid &&
              !dut.out_error && !dut.old_error, "A10_UPPER_SUM_EXACT_K_PLUS_FIVE");
        if (valid) {
            const Token token = pending.front(); pending.pop_front();
            const Outputs actual = outputs(dut);
            check(actual.old_y0 == token.answer.y0 && actual.old_y1 == token.answer.y1,
                  "A10_UPPER_SUM_OLD_MODULAR_ORACLE");
            check(actual.y0 == actual.old_y0 && actual.y1 == actual.old_y1,
                  "A10_UPPER_SUM_NEW_OLD_NUMERIC");
            Answer expected = token.answer;
            // First verify real old/new/oracle agreement; change exactly ONE
            // local expected word afterward. DUT inputs and state are intact.
            if (negative && !flipped) { expected.y0 ^= 1u; flipped = true; }
            if (actual.y0 != expected.y0 || actual.y1 != expected.y1)
                throw std::runtime_error(negative ? "A10_UPPER_SUM_NEGATIVE_ORACLE_REJECT" :
                                                   "A10_UPPER_SUM_MODULAR_ORACLE");
            ++total.outputs;
            if (token.mode == 0) ++total.ct;
            else if (token.mode == 1) ++total.gs;
            else ++total.normalized;
        }
        check(pending.empty() || pending.front().due > total.cycles,
              "A10_UPPER_SUM_LATE_OR_DUPLICATE_TOKEN");
    }
    void drain() {
        for (unsigned i = 0; i < 6; ++i) {
            Request bubble;
            bubble.gs = i % 2; bubble.u = (i + 1) % P; bubble.v = P - 1;
            bubble.w = i % P; bubble.normalization = P - 1 - i;
            step(bubble);
        }
        check(pending.empty() && !dut.out_valid && !dut.old_valid,
              "A10_UPPER_SUM_DRAIN_OR_RESET_LEAK");
    }
};

Request request(unsigned mode, uint32_t u, uint32_t v, uint32_t w, uint32_t norm) {
    return {true, mode != 0, mode == 2, u, v, w, norm, mode};
}

Request random_request(uint64_t& seed, unsigned mode) {
    // Sequence RNG consumption explicitly; function-argument evaluation order
    // must not choose different input vectors on different native compilers.
    const uint32_t u = uint32_t(random_word(seed) % P);
    const uint32_t v = uint32_t(random_word(seed) % P);
    const uint32_t w = uint32_t(random_word(seed) % P);
    const uint32_t norm = uint32_t(random_word(seed) % P);
    return request(mode, u, v, w, norm);
}

void run(Harness& h) {
    h.reset_async(); h.step(Request{}, false); h.step();
    const std::array<uint32_t, 7> boundary = {0, 1, 2, P / 2, P / 2 + 1, P - 2, P - 1};
    // Alternating CT/GS/final normalized GS at II1; every sum boundary and w.
    for (unsigned u = 0; u < boundary.size(); ++u)
        for (unsigned v = 0; v < boundary.size(); ++v)
            for (unsigned w = 0; w < boundary.size(); ++w)
                for (unsigned mode = 0; mode < 3; ++mode)
                    h.step(request(mode, boundary[u], boundary[v], boundary[w],
                                   boundary[(u + 2 * v + 3 * w + mode) % boundary.size()]));
    uint64_t seed = 0x41313053554d5632ULL ^ (uint64_t(P) << 1) ^ FIELD;
    for (unsigned i = 0; i < 2048; ++i)
        h.step(random_request(seed, i % 3));
    h.drain();
    // Consecutive normalized requests vary the RHS, rather than assuming a
    // field/stage normalization constant across the input launch register.
    for (unsigned i = 0; i < 64; ++i)
        h.step(request(2, uint32_t(uint64_t(i) * 2654435761u % P), P - 1 - i,
                       boundary[i % boundary.size()], uint32_t((uint64_t(i) * 104729 + 37) % P)));
    h.drain();
    for (unsigned i = 0; i < 128; ++i) {
        Request sample = random_request(seed, i % 3);
        sample.valid = i % 5 != 1 && i % 5 != 4; h.step(sample);
    }
    h.drain();
    const Request held = request(2, P - 1, P - 1, 1, P - 1);
    for (unsigned i = 0; i < 8; ++i) h.step(held);
    h.drain();
    for (unsigned age = 0; age <= 6; ++age) {
        h.step(request(2, P - 1 - age, P - 1, 1 + age, P - 1 - 2 * age));
        for (unsigned elapsed = 1; elapsed <= age; ++elapsed) h.step();
        // Age0 resets just after accepted k, before k+1. Ages5/6 reset
        // on/after the checked output edge, testing cancellation and no replay.
        h.reset_async(); h.step(Request{}, false); h.drain();
        for (unsigned mode = 0; mode < 3; ++mode)
            h.step(request(mode, age + 1, P - 1 - age, 2 + age, 3 + age));
        h.drain();
    }
    h.check(h.total.cycles == 3443 && h.total.accepted == 3254 && h.total.outputs == 3249 &&
            h.total.ct == 1059 && h.total.gs == 1058 && h.total.normalized == 1132 &&
            h.total.bubbles == 181 && h.total.resets == 8 && h.total.cancelled == 5,
            "A10_UPPER_SUM_EXACT_EVENT_LEDGER");
    if (h.negative) throw std::runtime_error("A10_UPPER_SUM_NEGATIVE_ORACLE_MISSED");
}
} // namespace

int main(int argc, char** argv) {
    try {
        VerilatedContext context; context.threads(1); context.commandArgs(argc, argv);
        DUT dut{&context};
        if (argc == 2 && std::string(argv[1]) == "--runtime-probe") {
            std::cout << "{\"context_threads\":" << context.threads()
                      << ",\"model_threads\":" << dut.threads() << ",\"expected_threads\":1}\n";
            return context.threads() == 1 && dut.threads() == 1 ? 0 : 2;
        }
        const bool negative = argc == 2 && std::string(argv[1]) == "--negative-oracle";
        need(argc == 1 || negative, "A10_UPPER_SUM_ARGUMENTS");
        Harness h(context, dut, negative); run(h);
        need(context.threads() == 1 && dut.threads() == 1, "A10_UPPER_SUM_THREAD_DRIFT");
        std::cout << "A10_UPPER_SUM_PASS field=" << FIELD << " modulus=" << P
                  << " cycles=" << h.total.cycles << " accepted=" << h.total.accepted
                  << " outputs=" << h.total.outputs << " ct=" << h.total.ct << " gs=" << h.total.gs
                  << " normalized=" << h.total.normalized << " bubbles=" << h.total.bubbles
                  << " resets=" << h.total.resets << " cancelled=" << h.total.cancelled
                  << " before_checks=" << 2 * h.total.cycles << " latency=5 ii=1\n";
        dut.final(); return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << "\n"; return 1; }
}
