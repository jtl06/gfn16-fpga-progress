// Native-only canonical-image checks.  The expected image is obtained by
// constructing the complete integer X and reducing it modulo b^N+1; this is
// deliberately independent of the controller's serial carry passes.
// v2 replaces the unavailable Boost dependency with native uint32_t limbs;
// vectors, protocol checks and successful/negative outcome contracts match v1.
#include "Vgenefer_stream27_canonical_image_localbase_v1.h"
#include "verilated.h"
#include <algorithm>
#include <array>
#include <cstdint>
#include <functional>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

#ifndef CANON_AW
#error CANON_AW must match the native build's -GAW
#endif
#ifndef CANON_P
#error CANON_P must match the native build's -GP
#endif
#ifndef CANON_ORACLE_CHECKSUM
#error CANON_ORACLE_CHECKSUM must bind the independent Python corpus checksum
#endif
static_assert(CANON_AW == 5 || CANON_AW == 8,
              "this finite native harness qualifies only AW5/AW8");
static_assert(CANON_P == 8 || CANON_P == 16, "native canonical P8/P16");
static_assert(uint64_t(CANON_ORACLE_CHECKSUM) < 1000000007ULL,
              "independent oracle checksum range");

namespace {
constexpr unsigned AW = CANON_AW;
constexpr unsigned P = CANON_P;
constexpr unsigned N = 1u << AW;
constexpr unsigned T = N / P;
constexpr int32_t K = 2 * N + 24 * P;
constexpr uint32_t BASE_MAX = 1000000000u;
constexpr uint32_t BASE_MIN_PRECISION = 2 * N + 5;
constexpr uint32_t BASE_MIN_CORRECTION = (2 * uint32_t(K) + 2) / 3 + 1;
constexpr uint32_t BASE_MIN = BASE_MIN_PRECISION > BASE_MIN_CORRECTION
                                ? BASE_MIN_PRECISION : BASE_MIN_CORRECTION;
static_assert(T >= 2, "correction supports must be distinct");

enum ErrorCode : uint8_t {
    CONFLICT = 1,
    LOAD_ORDER = 2,
    BASE_RANGE = 3,
    CORRECTION_RANGE = 4,
    NOT_READY = 5,
    DIGIT_RANGE = 6,
    INTERNAL_RANGE = 7
};

void need(bool ok, const std::string& why) {
    if (!ok) throw std::runtime_error(why);
}

struct Trial {
    std::string name;
    uint32_t base = BASE_MIN;
    bool expected_special = false;
    std::vector<uint32_t> digits = std::vector<uint32_t>(N, 0);
    std::array<int32_t, P> c0{};
    std::array<int32_t, P> c1{};
};

// Little-endian radix-2^32 magnitude arithmetic.  This implementation has no
// dependency on Boost, GMP, a SystemVerilog model, or the base-b carry passes.
struct LimbUnsigned {
    std::vector<uint32_t> words;

    explicit LimbUnsigned(uint32_t value = 0) {
        if (value) words.push_back(value);
    }

    bool zero() const { return words.empty(); }

    void trim() {
        while (!words.empty() && words.back() == 0) words.pop_back();
    }

    int compare(const LimbUnsigned& other) const {
        if (words.size() != other.words.size())
            return words.size() < other.words.size() ? -1 : 1;
        for (size_t i = words.size(); i > 0; --i) {
            if (words[i - 1] != other.words[i - 1])
                return words[i - 1] < other.words[i - 1] ? -1 : 1;
        }
        return 0;
    }

    void add(const LimbUnsigned& other) {
        const size_t count = std::max(words.size(), other.words.size());
        words.resize(count, 0);
        uint64_t carry = 0;
        for (size_t i = 0; i < count; ++i) {
            const uint64_t sum = uint64_t(words[i]) + carry +
                                 (i < other.words.size() ? other.words[i] : 0u);
            words[i] = uint32_t(sum);
            carry = sum >> 32;
        }
        if (carry) words.push_back(uint32_t(carry));
    }

    void subtract(const LimbUnsigned& other) {
        need(compare(other) >= 0, "CANON_IMAGE_LIMB_SUBTRACT_ORDER");
        uint64_t borrow = 0;
        for (size_t i = 0; i < words.size(); ++i) {
            const uint64_t subtrahend = borrow +
                                       (i < other.words.size() ? other.words[i] : 0u);
            const uint64_t original = words[i];
            words[i] = uint32_t(original - subtrahend);
            borrow = original < subtrahend;
        }
        need(!borrow, "CANON_IMAGE_LIMB_SUBTRACT_BORROW");
        trim();
    }

    void multiply_small(uint32_t factor) {
        if (!factor) { words.clear(); return; }
        uint64_t carry = 0;
        for (auto& word : words) {
            const uint64_t product = uint64_t(word) * factor + carry;
            word = uint32_t(product);
            carry = product >> 32;
        }
        if (carry) words.push_back(uint32_t(carry));
    }

    uint32_t divide_small(uint32_t divisor) {
        need(divisor != 0, "CANON_IMAGE_LIMB_DIVIDE_ZERO");
        uint64_t remainder = 0;
        for (size_t i = words.size(); i > 0; --i) {
            const uint64_t numerator = (remainder << 32) | words[i - 1];
            words[i - 1] = uint32_t(numerator / divisor);
            remainder = numerator % divisor;
        }
        trim();
        return uint32_t(remainder);
    }
};

void limb_self_checks() {
    LimbUnsigned carry(0xffffffffu);
    carry.add(LimbUnsigned(1));
    need(carry.words == std::vector<uint32_t>({0, 1}),
         "CANON_IMAGE_LIMB_SELFTEST_ADD");
    carry.subtract(LimbUnsigned(1));
    need(carry.words == std::vector<uint32_t>({0xffffffffu}),
         "CANON_IMAGE_LIMB_SELFTEST_SUBTRACT");
    LimbUnsigned borrow;
    borrow.words = {0, 0, 0, 1};
    borrow.subtract(LimbUnsigned(1));
    need(borrow.words == std::vector<uint32_t>({0xffffffffu, 0xffffffffu, 0xffffffffu}),
         "CANON_IMAGE_LIMB_SELFTEST_LONG_BORROW");
    borrow.add(LimbUnsigned(1));
    need(borrow.words == std::vector<uint32_t>({0, 0, 0, 1}),
         "CANON_IMAGE_LIMB_SELFTEST_LONG_CARRY");
    LimbUnsigned product(0xffffffffu);
    product.multiply_small(0xffffffffu);
    need(product.words == std::vector<uint32_t>({1, 0xfffffffeu}),
         "CANON_IMAGE_LIMB_SELFTEST_MULTIPLY");
    need(product.divide_small(0xffffffffu) == 0 &&
         product.words == std::vector<uint32_t>({0xffffffffu}),
         "CANON_IMAGE_LIMB_SELFTEST_DIVIDE");
    LimbUnsigned dividend;
    dividend.words = {0xffffffffu, 0x12345678u};
    const uint64_t known = 0x12345678ffffffffULL;
    const uint32_t remainder = dividend.divide_small(BASE_MAX);
    const uint64_t quotient = known / BASE_MAX;
    LimbUnsigned expected{uint32_t(quotient)};
    if (quotient >> 32) expected.words.push_back(uint32_t(quotient >> 32));
    need(remainder == known % BASE_MAX && dividend.compare(expected) == 0,
         "CANON_IMAGE_LIMB_SELFTEST_NONZERO_REMAINDER");
    dividend.multiply_small(0);
    need(dividend.zero(), "CANON_IMAGE_LIMB_SELFTEST_ZERO");
}

// Build positive and negative magnitudes of the WHOLE integer independently.
// There is no per-block normalization or model of a controller pass here.
std::vector<int64_t> whole_integer_oracle(const Trial& trial) {
    need(trial.base >= BASE_MIN && trial.base <= BASE_MAX &&
         2 * uint64_t(K) <= 3 * uint64_t(trial.base - 1),
         "CANON_IMAGE_ORACLE_BASE");
    LimbUnsigned positive, negative, power(1);
    for (unsigned i = 0; i < N; ++i) {
        need(trial.digits[i] < trial.base, "CANON_IMAGE_ORACLE_DIGIT");
        LimbUnsigned digit_term = power;
        digit_term.multiply_small(trial.digits[i]);
        positive.add(digit_term);
        if (i % T == 0) {
            const unsigned block = i / T;
            need(int64_t(trial.c0[block]) >= -int64_t(trial.base - 1) &&
                 int64_t(trial.c0[block]) <= int64_t(trial.base - 1) &&
                 int64_t(trial.c1[block]) >= -int64_t(K) &&
                 int64_t(trial.c1[block]) <= int64_t(K),
                 "CANON_IMAGE_ORACLE_CORRECTION");
            auto add_correction = [&](int32_t correction, bool times_base) {
                LimbUnsigned term = power;
                const uint32_t magnitude = uint32_t(correction < 0
                                                   ? -int64_t(correction)
                                                   : int64_t(correction));
                term.multiply_small(magnitude);
                if (times_base) term.multiply_small(trial.base);
                (correction < 0 ? negative : positive).add(term);
            };
            add_correction(trial.c0[block], false);
            add_correction(trial.c1[block], true);
        }
        power.multiply_small(trial.base);
    }
    LimbUnsigned modulus = power;
    modulus.add(LimbUnsigned(1));
    const bool is_negative = positive.compare(negative) < 0;
    LimbUnsigned residue = is_negative ? negative : positive;
    residue.subtract(is_negative ? positive : negative);

    // D<b^N. With B=b-1, T>=2 and K<=3B/2:
    // |C| <= (B+Kb) sum_k b^(kT)
    //     < (B+Kb)b^N/(b^T-1) <= (1+Kb/B)b^N/(b+1) < 3b^N/2.
    // Thus |X|<5b^N/2<3M, M=b^N+1, so at most TWO whole-M subtractions.
    // This whole-integer modulo is unrelated to RTL's three base-b passes.
    LimbUnsigned triple_modulus = modulus;
    triple_modulus.multiply_small(3);
    need(residue.compare(triple_modulus) < 0, "CANON_IMAGE_ORACLE_MAGNITUDE_BOUND");
    unsigned subtractions = 0;
    while (residue.compare(modulus) >= 0) {
        residue.subtract(modulus);
        need(++subtractions <= 2, "CANON_IMAGE_ORACLE_MODULO_BOUND");
    }
    if (is_negative && !residue.zero()) {
        LimbUnsigned euclidean = modulus;
        euclidean.subtract(residue);
        residue = euclidean;
    }
    std::vector<int64_t> result(N, 0);
    if (residue.compare(power) == 0) {
        result[0] = -1;
        return result;
    }
    for (unsigned i = 0; i < N; ++i)
        result[i] = residue.divide_small(trial.base);
    need(residue.zero(), "CANON_IMAGE_ORACLE_REMAINDER");
    return result;
}

uint64_t random_word(uint64_t& state) {
    state ^= state << 13;
    state ^= state >> 7;
    state ^= state << 17;
    return state;
}

std::vector<Trial> deterministic_trials() {
    std::vector<Trial> trials;
    for (uint32_t base : {BASE_MIN, BASE_MAX}) {
        Trial zero;
        zero.name = "zero_b" + std::to_string(base);
        zero.base = base;
        trials.push_back(zero);
        Trial dense = zero;
        dense.name = "natural_block_order_b" + std::to_string(base);
        for (unsigned i = 0; i < N; ++i)
            dense.digits[i] = uint32_t((uint64_t(i) * 104729 +
                                       uint64_t(i / T) * 31 + 17) % base);
        trials.push_back(dense);
        Trial maximum = zero;
        maximum.name = "all_max_b" + std::to_string(base);
        std::fill(maximum.digits.begin(), maximum.digits.end(), base - 1);
        trials.push_back(maximum);
        Trial minus_one = zero;
        minus_one.name = "special_zero_c0_minus_one_b" + std::to_string(base);
        minus_one.expected_special = true;
        minus_one.c0[0] = -1;
        trials.push_back(minus_one);
        Trial positive_special = maximum;
        positive_special.name = "special_all_max_c0_plus_one_b" + std::to_string(base);
        positive_special.expected_special = true;
        positive_special.c0[0] = 1;
        trials.push_back(positive_special);
        Trial extreme_positive = maximum;
        extreme_positive.name = "positive_carry_two_b" + std::to_string(base);
        extreme_positive.c0.fill(int32_t(base - 1));
        extreme_positive.c1.fill(K);
        trials.push_back(extreme_positive);
        Trial extreme_negative = zero;
        extreme_negative.name = "negative_carry_two_b" + std::to_string(base);
        extreme_negative.c0.fill(-int32_t(base - 1));
        extreme_negative.c1.fill(-K);
        trials.push_back(extreme_negative);
        Trial alternating = dense;
        alternating.name = "alternating_extreme_corrections_b" + std::to_string(base);
        for (unsigned block = 0; block < P; ++block) {
            alternating.c0[block] = (block & 1) ? -int32_t(base - 1) : int32_t(base - 1);
            alternating.c1[block] = (block & 1) ? K : -K;
        }
        trials.push_back(alternating);
        // A correction at the final natural block exercises x^N = -1.
        Trial wrap = maximum;
        wrap.name = "last_block_wrap_b" + std::to_string(base);
        wrap.c0[P - 1] = int32_t(base - 1);
        wrap.c1[P - 1] = K;
        trials.push_back(wrap);
    }
    uint64_t seed = 0x43414e4f4e563100ULL ^ (uint64_t(AW) << 8) ^ P;
    for (unsigned test = 0; test < 24; ++test) {
        Trial trial;
        trial.name = "bounded_random_" + std::to_string(test);
        trial.base = test % 3 == 0 ? BASE_MIN :
                     test % 3 == 1 ? BASE_MAX :
                     BASE_MIN + uint32_t(random_word(seed) % (BASE_MAX - BASE_MIN + 1));
        for (auto& digit : trial.digits)
            digit = uint32_t(random_word(seed) % trial.base);
        for (unsigned block = 0; block < P; ++block) {
            trial.c0[block] = int32_t(int64_t(random_word(seed) %
                                     (2 * uint64_t(trial.base - 1) + 1)) - (trial.base - 1));
            trial.c1[block] = int32_t(int64_t(random_word(seed) % (2 * uint64_t(K) + 1)) - K);
        }
        trials.push_back(trial);
    }
    return trials;
}

void check_oracle_checksum(const std::vector<Trial>& trials) {
    uint64_t checksum = 0;
    for (const auto& trial : trials) {
        for (int64_t digit : whole_integer_oracle(trial)) {
            need(digit >= -1 && digit < int64_t(BASE_MAX),
                 "CANON_IMAGE_ORACLE_CHECKSUM_DIGIT");
            checksum = (checksum * 65599 + uint64_t(digit + 1)) % 1000000007;
        }
    }
    need(checksum == uint64_t(CANON_ORACLE_CHECKSUM),
         "CANON_IMAGE_ORACLE_CHECKSUM expected=" +
         std::to_string(uint64_t(CANON_ORACLE_CHECKSUM)) +
         " actual=" + std::to_string(checksum));
}

std::array<uint32_t, 3> signed_read96(const Vgenefer_stream27_canonical_image_localbase_v1& dut) {
    return {uint32_t(dut.read_data[0]), uint32_t(dut.read_data[1]),
            uint32_t(dut.read_data[2])};
}

std::array<uint32_t, 3> expected_signed96(int64_t value) {
    // Conversion of a negative signed integer to uint64_t is defined modulo 2^64.
    return {uint32_t(uint64_t(value)), uint32_t(uint64_t(value) >> 32),
            value < 0 ? 0xffffffffu : 0u};
}

std::string read_word_text(const std::array<uint32_t, 3>& words) {
    return std::to_string(words[2]) + ":" + std::to_string(words[1]) +
           ":" + std::to_string(words[0]);
}

struct Outputs {
    unsigned busy, done, error, error_code, image_valid, read_valid, read_address;
    uint64_t cycles;
    std::array<uint32_t, 3> read_data;
    bool operator==(const Outputs& other) const {
        return busy == other.busy && done == other.done && error == other.error &&
               error_code == other.error_code && image_valid == other.image_valid &&
               read_valid == other.read_valid && read_address == other.read_address &&
               cycles == other.cycles && read_data == other.read_data;
    }
};

Outputs outputs(const Vgenefer_stream27_canonical_image_localbase_v1& dut) {
    return {unsigned(dut.busy), unsigned(dut.done), unsigned(dut.error),
            unsigned(dut.error_code), unsigned(dut.image_valid),
            unsigned(dut.read_valid), unsigned(dut.read_address_out),
            uint64_t(dut.cycles), {uint32_t(dut.read_data[0]),
                                uint32_t(dut.read_data[1]), uint32_t(dut.read_data[2])}};
}

struct Counters {
    uint64_t cases = 0, reads = 0, normal = 0, special = 0, cycles = 0;
};

class Harness {
public:
    VerilatedContext& context;
    Vgenefer_stream27_canonical_image_localbase_v1& dut;
    Counters totals;
    std::string where;

    Harness(VerilatedContext& c, Vgenefer_stream27_canonical_image_localbase_v1& d)
        : context(c), dut(d) {
        dut.clk = 1;
        dut.rst_n = 0;
        clear_requests();
        dut.base = BASE_MIN;
        dut.load_row = 0;
        dut.read_address = 0;
        for (unsigned block = 0; block < P; ++block)
            dut.load_data[block] = dut.c0[block] = dut.c1[block] = 0;
        dut.eval();
    }

    void check(bool condition, const std::string& tag) const {
        need(condition, tag + " aw=" + std::to_string(AW) + " p=" +
             std::to_string(P) + " case=" + where);
    }

    void clear_requests() {
        dut.load_valid = 0;
        dut.begin_canonical = 0;
        dut.read_req = 0;
    }

    void edge() {
        const Outputs before = outputs(dut);
        dut.eval();
        if (dut.rst_n) check(outputs(dut) == before, "CANON_IMAGE_COMBINATIONAL_LEAK");
        const Outputs before_falling = outputs(dut);
        dut.clk = 0;
        context.timeInc(1);
        dut.eval();
        check(outputs(dut) == before_falling, "CANON_IMAGE_FALLING_EDGE_LEAK");
        dut.clk = 1;
        context.timeInc(1);
        dut.eval();
    }

    void reset() {
        clear_requests();
        dut.rst_n = 0;
        edge();
        check(!dut.busy && !dut.done && !dut.error && !dut.error_code &&
              !dut.image_valid && !dut.read_valid && !dut.cycles,
              "CANON_IMAGE_RESET_FLAGS");
        dut.rst_n = 1;
        dut.base = BASE_MIN;
        dut.load_row = 0;
        dut.read_address = 0;
        for (unsigned block = 0; block < P; ++block)
            dut.load_data[block] = dut.c0[block] = dut.c1[block] = 0;
        edge();
        check(!dut.busy && !dut.done && !dut.error && !dut.image_valid &&
              !dut.read_valid, "CANON_IMAGE_RESET_RELEASE_LEAK");
    }

    void correction_inputs(const Trial& trial) {
        dut.base = trial.base;
        for (unsigned block = 0; block < P; ++block) {
            dut.c0[block] = uint32_t(trial.c0[block]);
            dut.c1[block] = uint32_t(trial.c1[block]);
        }
    }

    void load_row(const Trial& trial, unsigned row) {
        clear_requests();
        dut.base = trial.base;
        dut.load_valid = 1;
        dut.load_row = row;
        // Host lanes are NATURAL blocks, not the transform's mirrored lanes.
        for (unsigned block = 0; block < P; ++block)
            dut.load_data[block] = trial.digits[block * T + row];
        edge();
        check(!dut.error && !dut.busy && !dut.done && !dut.image_valid &&
              !dut.read_valid, "CANON_IMAGE_LOAD_OR_INVALIDATION");
        dut.load_valid = 0;
    }

    void load(const Trial& trial, bool gaps = true, unsigned first = 0) {
        correction_inputs(trial);
        for (unsigned row = first; row < T; ++row) {
            if (gaps && row && (row == 1 || row == T / 2)) {
                clear_requests();
                edge();
                check(!dut.error && !dut.busy && !dut.image_valid && !dut.read_valid,
                      "CANON_IMAGE_LOAD_GAP");
            }
            load_row(trial, row);
        }
    }

    void begin(const Trial& trial) {
        clear_requests();
        correction_inputs(trial);
        dut.begin_canonical = 1;
        edge();
        dut.begin_canonical = 0;
        check(dut.busy && !dut.done && !dut.error && !dut.image_valid &&
              !dut.read_valid && !dut.cycles, "CANON_IMAGE_BEGIN_L_PLUS_ONE");
    }

    void hostile_busy_inputs() {
        dut.load_valid = dut.begin_canonical = dut.read_req = 1;
        dut.base = 0xffffffffu;
        dut.load_row = T - 1;
        dut.read_address = N - 1;
        for (unsigned block = 0; block < P; ++block) {
            dut.load_data[block] = 0xffffffffu;
            dut.c0[block] = 0x80000000u;
            dut.c1[block] = 0x7fffffffu;
        }
    }

    void complete(const Trial& trial, const std::vector<int64_t>& reference,
                  bool hostile = true) {
        const bool special = reference[0] == -1;
        const unsigned latency = (special ? 10 : 9) * N;
        for (unsigned age = 1; age <= latency; ++age) {
            if (hostile) hostile_busy_inputs();
            else clear_requests();
            edge();
            check(!dut.error && !dut.read_valid && uint64_t(dut.cycles) == age,
                  "CANON_IMAGE_BUSY_OR_CYCLE age=" + std::to_string(age));
            if (age < latency)
                check(dut.busy && !dut.done && !dut.image_valid,
                      "CANON_IMAGE_EARLY_PUBLICATION age=" + std::to_string(age));
            else
                check(!dut.busy && dut.done && dut.image_valid,
                      "CANON_IMAGE_LATENCY_OR_FINAL_COMMIT age=" + std::to_string(age));
        }
        clear_requests();
        correction_inputs(trial);
        ++(special ? totals.special : totals.normal);
        totals.cycles += latency;
    }

    void check_read(unsigned address, int64_t expected, bool negative = false) {
        check(dut.read_valid && unsigned(dut.read_address_out) == address &&
              dut.image_valid && !dut.busy && !dut.error,
              "CANON_IMAGE_READ_PIPELINE address=" + std::to_string(address));
        const auto actual = signed_read96(dut);
        if (actual != expected_signed96(expected)) {
            const std::string tag = negative ? "CANON_IMAGE_NEGATIVE_ORACLE_REJECT" :
                                               "CANON_IMAGE_ORACLE_MISMATCH";
            throw std::runtime_error(tag + " aw=" + std::to_string(AW) +
                " p=" + std::to_string(P) + " case=" + where +
                " address=" + std::to_string(address) +
                " expected=" + std::to_string(expected) +
                " actual=" + read_word_text(actual));
        }
        ++totals.reads;
    }

    // Leaves no pending E0 request.  The last response was on the last edge,
    // so a mutation on the next edge also checks the legal E2 transition.
    void read_all(const std::vector<int64_t>& reference, bool negative = false) {
        std::vector<int64_t> expected = reference;
        const unsigned flipped_address = N / 2;
        if (negative) ++expected[flipped_address]; // Change only one expectation.
        clear_requests();
        dut.read_req = 1;
        dut.read_address = 0;
        edge();
        check(!dut.read_valid && !dut.done, "CANON_IMAGE_READ_E0_OR_DONE_PULSE");
        for (unsigned address = 1; address < N; ++address) {
            dut.read_address = address;
            edge();
            check_read(address - 1, expected[address - 1],
                       negative && address - 1 == flipped_address);
        }
        dut.read_req = 0;
        edge();
        check_read(N - 1, expected[N - 1], negative && N - 1 == flipped_address);
        if (negative) throw std::runtime_error("CANON_IMAGE_NEGATIVE_ORACLE_MISSED");
    }

    void valid_case(const Trial& trial, bool negative = false, bool gaps = true) {
        where = trial.name;
        ++totals.cases;
        const auto reference = whole_integer_oracle(trial);
        check((reference[0] == -1) == trial.expected_special,
              "CANON_IMAGE_ORACLE_SPECIAL_CLASSIFICATION");
        load(trial, gaps);
        begin(trial); // Last load at L; begin is accepted at L+1.
        complete(trial, reference);
        read_all(reference, negative);
    }

    void assert_quarantine(ErrorCode code) {
        check(dut.error && unsigned(dut.error_code) == code && !dut.busy &&
              !dut.done && !dut.image_valid && !dut.read_valid,
              "CANON_IMAGE_TYPED_ERROR code=" + std::to_string(code));
        const uint64_t frozen_cycles = dut.cycles;
        for (unsigned age = 0; age < 4; ++age) {
            hostile_busy_inputs();
            edge();
            check(dut.error && unsigned(dut.error_code) == code && !dut.busy &&
                  !dut.done && !dut.image_valid && !dut.read_valid &&
                  uint64_t(dut.cycles) == frozen_cycles,
                  "CANON_IMAGE_STICKY_QUARANTINE code=" + std::to_string(code));
        }
        clear_requests();
    }

    void fault_case(const std::string& name, ErrorCode code,
                    const std::function<void()>& action, const Trial& recovery,
                    bool delayed = false) {
        where = name;
        ++totals.cases;
        reset();
        action();
        if (delayed) {
            for (unsigned age = 0; age < 2 * N + 2 && !dut.error; ++age) {
                clear_requests();
                edge();
                check(!dut.done && !dut.image_valid && !dut.read_valid,
                      "CANON_IMAGE_DELAYED_FAULT_PUBLICATION");
            }
        }
        assert_quarantine(code);
        reset();
        Trial restored = recovery;
        restored.name = name + "_reset_full_reload";
        valid_case(restored);
    }
};

void protocol_and_range_cases(Harness& h, const Trial& recovery) {
    auto request_conflict = [&](const std::string& name, unsigned mask) {
        h.fault_case(name, CONFLICT, [&]() {
            h.correction_inputs(recovery);
            h.dut.load_row = 0;
            for (unsigned block = 0; block < P; ++block) h.dut.load_data[block] = 0;
            h.dut.load_valid = mask & 1;
            h.dut.begin_canonical = (mask >> 1) & 1;
            h.dut.read_req = (mask >> 2) & 1;
            h.edge();
        }, recovery);
    };
    request_conflict("idle_load_begin_conflict", 3);
    request_conflict("idle_load_read_conflict", 5);
    request_conflict("idle_begin_read_conflict", 6);
    request_conflict("idle_all_requests_conflict", 7);
    h.fault_case("first_row_one", LOAD_ORDER, [&]() {
        h.dut.load_valid = 1;
        h.dut.load_row = 1;
        h.edge();
    }, recovery);
    h.fault_case("duplicate_row_zero", LOAD_ORDER, [&]() {
        h.load_row(recovery, 0);
        h.dut.load_valid = 1;
        h.dut.load_row = 0;
        h.edge();
    }, recovery);
    if (T > 2) {
        h.fault_case("skipped_row_one", LOAD_ORDER, [&]() {
            h.load_row(recovery, 0);
            h.dut.load_valid = 1;
            h.dut.load_row = 2;
            h.edge();
        }, recovery);
    }
    for (uint32_t base : {0u, 1u, BASE_MIN - 1, BASE_MAX + 1, 0xffffffffu}) {
        h.fault_case("bad_load_base_" + std::to_string(base), BASE_RANGE, [&]() {
            h.dut.base = base;
            h.dut.load_valid = 1;
            h.dut.load_row = 0;
            for (unsigned block = 0; block < P; ++block) h.dut.load_data[block] = 0;
            h.edge();
        }, recovery);
        h.fault_case("bad_begin_base_" + std::to_string(base), BASE_RANGE, [&]() {
            h.load(recovery);
            h.dut.base = base;
            h.dut.begin_canonical = 1;
            h.edge();
        }, recovery);
    }
    for (unsigned block : {0u, P - 1}) {
        for (uint32_t bad : {recovery.base, recovery.base + 1, 0xffffffffu}) {
            h.fault_case("bad_load_digit_b" + std::to_string(block) + "_v" +
                         std::to_string(bad), DIGIT_RANGE, [&]() {
                h.dut.base = recovery.base;
                h.dut.load_valid = 1;
                h.dut.load_row = 0;
                for (unsigned lane = 0; lane < P; ++lane) h.dut.load_data[lane] = 0;
                h.dut.load_data[block] = bad;
                h.edge();
            }, recovery);
        }
    }
    h.fault_case("bad_base_during_partial_load", BASE_RANGE, [&]() {
        h.load_row(recovery, 0);
        h.dut.load_valid = 1;
        h.dut.load_row = 1;
        h.dut.base = BASE_MIN - 1;
        for (unsigned block = 0; block < P; ++block) h.dut.load_data[block] = 0;
        h.edge();
    }, recovery);
    h.fault_case("bad_digit_on_last_load_row", DIGIT_RANGE, [&]() {
        for (unsigned row = 0; row + 1 < T; ++row) h.load_row(recovery, row);
        h.dut.load_valid = 1;
        h.dut.load_row = T - 1;
        for (unsigned block = 0; block < P; ++block)
            h.dut.load_data[block] = recovery.digits[block * T + T - 1];
        h.dut.load_data[P - 1] = recovery.base;
        h.edge();
    }, recovery);
    for (unsigned row : {0u, T - 1}) {
        h.fault_case("begin_base_recheck_row_" + std::to_string(row), DIGIT_RANGE, [&]() {
            Trial loaded = recovery;
            loaded.base = BASE_MAX;
            loaded.digits.assign(N, 0);
            loaded.digits[(P - 1) * T + row] = BASE_MIN;
            h.load(loaded);
            h.correction_inputs(recovery);
            h.dut.begin_canonical = 1;
            h.edge();
            h.dut.begin_canonical = 0;
            h.check(h.dut.busy && !h.dut.error, "CANON_IMAGE_RECHECK_NOT_AT_BEGIN");
        }, recovery, true);
    }
    for (bool second : {false, true}) {
        const int32_t bound = second ? K : int32_t(recovery.base - 1);
        for (int32_t bad : {bound + 1, -bound - 1,
                            std::numeric_limits<int32_t>::max(),
                            std::numeric_limits<int32_t>::min()}) {
            h.fault_case(std::string(second ? "bad_c1_" : "bad_c0_") +
                         std::to_string(bad), CORRECTION_RANGE, [&]() {
                h.load(recovery);
                h.correction_inputs(recovery);
                if (second) h.dut.c1[P - 1] = uint32_t(bad);
                else h.dut.c0[P - 1] = uint32_t(bad);
                h.dut.begin_canonical = 1;
                h.edge();
            }, recovery);
        }
    }
    h.fault_case("begin_without_load", NOT_READY, [&]() {
        h.dut.begin_canonical = 1;
        h.edge();
    }, recovery);
    h.fault_case("begin_partial_load", NOT_READY, [&]() {
        h.load_row(recovery, 0);
        h.dut.begin_canonical = 1;
        h.edge();
    }, recovery);
    h.fault_case("read_after_reset", NOT_READY, [&]() {
        h.dut.read_req = 1;
        h.edge();
    }, recovery);
    h.fault_case("read_partial_load", NOT_READY, [&]() {
        h.load_row(recovery, 0);
        h.dut.read_req = 1;
        h.edge();
    }, recovery);
    h.fault_case("read_raw_complete_unpublished", NOT_READY, [&]() {
        h.load(recovery);
        h.dut.read_req = 1;
        h.edge();
    }, recovery);
    h.fault_case("read_after_first_raw_mutation", NOT_READY, [&]() {
        h.valid_case(recovery);
        h.where = "read_after_first_raw_mutation";
        h.load_row(recovery, 0);
        h.dut.read_req = 1;
        h.edge();
    }, recovery);
    h.fault_case("repeat_begin_without_full_reload", NOT_READY, [&]() {
        h.valid_case(recovery);
        h.where = "repeat_begin_without_full_reload";
        h.dut.begin_canonical = 1;
        h.edge();
    }, recovery);
    for (bool load_mutation : {false, true}) {
        const std::string name = load_mutation ? "pending_read_load_conflict" :
                                                "pending_read_begin_conflict";
        h.fault_case(name, CONFLICT, [&]() {
            h.valid_case(recovery);
            h.where = name;
            h.dut.read_req = 1;
            h.dut.read_address = N - 1;
            h.edge();
            h.check(!h.dut.read_valid, "CANON_IMAGE_PENDING_READ_E0");
            h.dut.read_req = 0;
            h.dut.load_row = 0;
            h.dut.load_valid = load_mutation;
            h.dut.begin_canonical = !load_mutation;
            h.edge(); // E1 conflict suppresses the pending response.
        }, recovery);
    }
}

void legal_mutation_cases(Harness& h, const Trial& recovery) {
    Trial source = recovery;
    source.name = "legal_read_e2_load_source";
    h.valid_case(source);
    const auto reference = whole_integer_oracle(source);
    h.dut.read_req = 1;
    h.dut.read_address = N - 1;
    h.edge(); // E0
    h.check(!h.dut.read_valid, "CANON_IMAGE_LEGAL_MUTATION_READ_E0");
    h.dut.read_req = 0;
    h.edge(); // E1
    h.check_read(N - 1, reference[N - 1]);
    Trial replacement = recovery;
    replacement.name = "legal_load_e2_after_response";
    replacement.digits[0] = (replacement.digits[0] + 1) % replacement.base;
    h.where = replacement.name;
    ++h.totals.cases;
    h.load_row(replacement, 0); // E2: one edge after the response.
    h.load(replacement, true, 1);
    const auto replaced_reference = whole_integer_oracle(replacement);
    h.begin(replacement);
    h.complete(replacement, replaced_reference);
    h.read_all(replaced_reference);

    // Row zero may restart a fully loaded raw image before begin.
    Trial discarded = recovery;
    discarded.name = "complete_raw_restart_row_zero";
    h.where = discarded.name;
    h.load(discarded);
    Trial restart = recovery;
    restart.name = discarded.name;
    restart.digits[N - 1] = (restart.digits[N - 1] + 7) % restart.base;
    h.valid_case(restart);
    h.clear_requests();
    h.edge();
    h.check(!h.dut.read_valid && !h.dut.done && h.dut.image_valid && !h.dut.error,
            "CANON_IMAGE_READ_VALID_ONE_EDGE");
}

void reset_cases(Harness& h, const Trial& recovery, const Trial& special) {
    const std::vector<unsigned> normal_ages =
        {1, 2 * N - 1, 2 * N, 2 * N + 1, 4 * N - 1,
         4 * N, 4 * N + 1, 6 * N - 1, 6 * N};
    const std::vector<unsigned> special_ages =
        {2 * N, 4 * N, 6 * N - 1, 6 * N, 6 * N + 1, 7 * N - 1, 7 * N};
    for (bool is_special : {false, true}) {
        const auto& ages = is_special ? special_ages : normal_ages;
        const Trial& trial = is_special ? special : recovery;
        for (unsigned age : ages) {
            h.where = std::string(is_special ? "reset_special_age_" : "reset_normal_age_") +
                      std::to_string(age);
            const std::string name = h.where;
            ++h.totals.cases;
            h.reset();
            h.load(trial);
            h.begin(trial);
            for (unsigned cycle = 1; cycle < age; ++cycle) {
                h.hostile_busy_inputs();
                h.edge();
                h.check(h.dut.busy && !h.dut.done && !h.dut.error &&
                        !h.dut.image_valid && !h.dut.read_valid,
                        "CANON_IMAGE_RESET_PRECONDITION");
            }
            h.reset(); // Cancels the boundary/final-write edge itself.
            for (unsigned cycle = 0; cycle < 2 * N + 2; ++cycle) {
                h.clear_requests();
                h.edge();
                h.check(!h.dut.busy && !h.dut.done && !h.dut.error &&
                        !h.dut.image_valid && !h.dut.read_valid,
                        "CANON_IMAGE_PRE_RESET_TOKEN_LEAK");
            }
            Trial restored = recovery;
            restored.name = name + "_full_reload";
            h.valid_case(restored);
        }
    }
    for (bool after_response : {false, true}) {
        const std::string name = after_response ? "reset_read_e1_with_next_pending" :
                                                  "reset_read_e0_pending";
        h.where = name;
        ++h.totals.cases;
        h.reset();
        h.valid_case(recovery);
        h.where = name;
        const auto reference = whole_integer_oracle(recovery);
        h.dut.read_req = 1;
        h.dut.read_address = 0;
        h.edge();
        h.check(!h.dut.read_valid, "CANON_IMAGE_RESET_READ_E0");
        if (after_response) {
            h.dut.read_address = N - 1;
            h.edge();
            h.check_read(0, reference[0]);
        }
        h.reset();
        for (unsigned cycle = 0; cycle < N + 2; ++cycle) {
            h.clear_requests();
            h.edge();
            h.check(!h.dut.read_valid && !h.dut.done && !h.dut.image_valid &&
                    !h.dut.error, "CANON_IMAGE_RESET_READ_PIPELINE_LEAK");
        }
        Trial restored = recovery;
        restored.name = name + "_full_reload";
        h.valid_case(restored);
    }
}
} // namespace

int main(int argc, char** argv) {
    try {
        VerilatedContext context;
        context.threads(1);
        context.commandArgs(argc, argv);
        Vgenefer_stream27_canonical_image_localbase_v1 dut{&context};
        if (argc == 2 && std::string(argv[1]) == "--runtime-probe") {
            std::cout << "{\"context_threads\":" << context.threads()
                      << ",\"model_threads\":" << dut.threads()
                      << ",\"expected_threads\":1}\n";
            return context.threads() == 1 && dut.threads() == 1 ? 0 : 2;
        }
        const bool negative = argc == 2 && std::string(argv[1]) == "--negative-oracle";
        need(argc == 1 || negative,
             "CANON_IMAGE_USAGE [--negative-oracle | --runtime-probe]");
        limb_self_checks();
        Harness h(context, dut);
        h.where = "initial_reset";
        h.reset();
        const auto trials = deterministic_trials();
        check_oracle_checksum(trials);
        if (negative) {
            h.valid_case(trials[1], true);
            throw std::runtime_error("CANON_IMAGE_NEGATIVE_ORACLE_MISSED");
        }
        for (const auto& trial : trials) h.valid_case(trial);
        h.check(context.threads() == 1 && dut.threads() == 1,
                "CANON_IMAGE_THREAD_DRIFT");
        std::cout << "CANON_LOCALBASE_PASS aw=" << AW << " p=" << P
                  << " cases=" << h.totals.cases << " reads=" << h.totals.reads
                  << " normal=" << h.totals.normal << " special=" << h.totals.special
                  << " cycles=" << h.totals.cycles << "\n";
        dut.final();
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << "\n";
        return 1;
    }
}
