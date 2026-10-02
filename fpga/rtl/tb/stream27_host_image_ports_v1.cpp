// Native component/idle-T5b host checks only; no start/arithmetic claim.
#include "Vgenefer_stream27_host_image_ports_pair_v1.h"
#include "verilated.h"
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

#ifndef HOST_IMAGE_AW
#error HOST_IMAGE_AW must match -GAW
#endif
#ifndef HOST_IMAGE_P
#error HOST_IMAGE_P must match -GP
#endif
static_assert(HOST_IMAGE_AW == 5 || HOST_IMAGE_AW == 8, "finite native geometry");
static_assert(HOST_IMAGE_P == 8 || HOST_IMAGE_P == 16, "native natural-block banks");

namespace {
using DUT = Vgenefer_stream27_host_image_ports_pair_v1;
constexpr unsigned AW = HOST_IMAGE_AW, P = HOST_IMAGE_P, N = 1u << AW, T = N / P;
constexpr std::array<uint32_t, 8> SIGNED_WORDS =
    {0, 1, 0x7fffffffu, 0x80000000u, 0xffffffffu, 0xfffffffeu, 0x40000000u, 0xc0000000u};

void need(bool ok, const std::string& message) {
    if (!ok) throw std::runtime_error(message);
}

std::array<uint32_t, 3> extended96(uint32_t word) {
    const uint32_t extension = word & 0x80000000u ? 0xffffffffu : 0;
    return {word, extension, extension};
}

uint32_t value_for(unsigned address, unsigned generation) {
    if (address < SIGNED_WORDS.size()) return SIGNED_WORDS[(address + generation) % SIGNED_WORDS.size()];
    return uint32_t(uint64_t(address + 1) * 2654435761u + uint64_t(generation) * 104729u);
}

struct Inputs {
    bool rst = true, access = true, load = false, read = false, row = false, commit = false;
    unsigned address = 0, row_address = 0, commit_address = 0;
    uint32_t word = 0, commit_word = 0;
};

struct Outputs {
    bool scalar, row, parent_scalar, parent_busy, parent_done, parent_error;
    std::array<uint32_t, 3> scalar_word, parent_word;
    std::array<uint32_t, P> row_words;
    bool operator==(const Outputs& other) const {
        return scalar == other.scalar && row == other.row && parent_scalar == other.parent_scalar &&
               parent_busy == other.parent_busy && parent_done == other.parent_done &&
               parent_error == other.parent_error && scalar_word == other.scalar_word &&
               parent_word == other.parent_word && row_words == other.row_words;
    }
};

Outputs outputs(const DUT& dut) {
    Outputs result{bool(dut.read_valid), bool(dut.row_read_valid), bool(dut.parent_read_valid),
                   bool(dut.parent_busy), bool(dut.parent_done), bool(dut.parent_error),
                   {uint32_t(dut.read_data[0]), uint32_t(dut.read_data[1]), uint32_t(dut.read_data[2])},
                   {uint32_t(dut.parent_read_data[0]), uint32_t(dut.parent_read_data[1]),
                    uint32_t(dut.parent_read_data[2])}, {}};
    for (unsigned bank = 0; bank < P; ++bank) result.row_words[bank] = dut.row_read_data[bank];
    return result;
}

struct Counters {
    uint64_t edges = 0, scalar = 0, rows = 0, row_words = 0, host_writes = 0;
    uint64_t commits = 0, ignored = 0, write_priority = 0, resets = 0;
};

class Harness {
public:
    VerilatedContext& context;
    DUT& dut;
    // The reference is a FLAT memory, not an RTL bank/lane/address model.
    std::vector<uint32_t> flat = std::vector<uint32_t>(N, 0);
    std::vector<bool> known = std::vector<bool>(N, false);
    Counters total;
    bool negative, flipped = false;

    Harness(VerilatedContext& c, DUT& d, bool n) : context(c), dut(d), negative(n) {
        dut.clk = 1;
        dut.rst_n = 0;
        dut.host_access = dut.load_we = dut.read_en = dut.row_read_req = dut.commit_we = 0;
        dut.host_addr = dut.row_read_address = dut.commit_address = 0;
        dut.write_data = dut.commit_word = 0;
        dut.eval();
    }

    void check(bool ok, const std::string& tag) const {
        need(ok, tag + " edge=" + std::to_string(total.edges) + " aw=" +
             std::to_string(AW) + " p=" + std::to_string(P));
    }

    void step(const Inputs& in) {
        check(in.address < N && in.commit_address < N && in.row_address < T,
              "HOST_IMAGE_INPUT_ADDRESS");
        const Outputs before = outputs(dut);
        dut.rst_n = in.rst;
        dut.host_access = in.access;
        dut.load_we = in.load;
        dut.read_en = in.read;
        dut.host_addr = in.address;
        dut.write_data = in.word;
        dut.row_read_req = in.row;
        dut.row_read_address = in.row_address;
        dut.commit_we = in.commit;
        dut.commit_address = in.commit_address;
        dut.commit_word = in.commit_word;
        dut.eval();
        if (in.rst) check(outputs(dut) == before, "HOST_IMAGE_PRE_EDGE_LEAK");
        else check(!dut.read_valid && !dut.row_read_valid && !dut.parent_read_valid,
                   "HOST_IMAGE_ASYNC_RESET_ELIGIBILITY");
        const Outputs before_falling = outputs(dut);
        dut.clk = 0;
        context.timeInc(1);
        dut.eval();
        check(outputs(dut) == before_falling, "HOST_IMAGE_FALLING_EDGE_LEAK");
        dut.clk = 1;
        context.timeInc(1);
        dut.eval();
        ++total.edges;

        const bool commit = in.rst && in.commit;
        const bool row = in.rst && !in.commit && in.row;
        const bool host = in.rst && !in.commit && !in.row && in.access;
        const bool scalar = host && !in.load && in.read;
        check(bool(dut.read_valid) == scalar && bool(dut.parent_read_valid) == scalar &&
              bool(dut.row_read_valid) == row,
              "HOST_IMAGE_ACTUAL_E0_ELIGIBILITY");
        check(!dut.parent_busy && !dut.parent_done && !dut.parent_error,
              "HOST_IMAGE_PARENT_IDLE_ONLY");
        if ((in.load || in.read) && !host) ++total.ignored;
        if (!in.rst) { ++total.resets; return; }
        if (commit) {
            flat[in.commit_address] = in.commit_word;
            known[in.commit_address] = true;
            ++total.commits;
        } else if (row) {
            for (unsigned bank = 0; bank < P; ++bank) {
                const unsigned address = bank * T + in.row_address;
                check(known[address], "HOST_IMAGE_REFERENCE_UNINITIALIZED_ROW");
                check(uint32_t(dut.row_read_data[bank]) == flat[address],
                      "HOST_IMAGE_NATURAL_ROW_E0 bank=" + std::to_string(bank));
            }
            ++total.rows;
            total.row_words += P;
        } else if (host && in.load) {
            flat[in.address] = in.word;
            known[in.address] = true;
            ++total.host_writes;
            if (in.read) ++total.write_priority;
        } else if (scalar) {
            check(known[in.address], "HOST_IMAGE_REFERENCE_UNINITIALIZED_SCALAR");
            const Outputs actual = outputs(dut);
            auto expected = extended96(flat[in.address]);
            // First establish real T5b/new/flat numeric agreement. A negative
            // control then changes ONE local expected word, never numeric RAM.
            check(actual.parent_word == expected, "HOST_IMAGE_T5B_SIGNED96_E0");
            check(actual.scalar_word == actual.parent_word, "HOST_IMAGE_T5B_PAIR_SIGNED96_E0");
            if (negative && !flipped) { expected[0] ^= 1u; flipped = true; }
            if (actual.scalar_word != expected)
                throw std::runtime_error(negative ? "HOST_IMAGE_NEGATIVE_ORACLE_REJECT" :
                                                   "HOST_IMAGE_FLAT_SIGNED96_E0");
            ++total.scalar;
        }
    }

    void quiet(unsigned count) {
        for (unsigned i = 0; i < count; ++i) step(Inputs{});
    }

    void load_all(unsigned generation) {
        for (unsigned address = 0; address < N; ++address) {
            if (address && address % 17 == 0) quiet(1);
            Inputs in;
            in.load = true;
            in.address = address;
            in.word = value_for(address, generation);
            step(in);
        }
    }

    void scalar_all() {
        for (unsigned address = 0; address < N; ++address) {
            Inputs in;
            in.read = true;
            in.address = address;
            step(in); // Consecutive accepted requests/responses prove II1/E0.
        }
    }

    void row_all() {
        for (unsigned row = 0; row < T; ++row) {
            Inputs in;
            in.row = true;
            in.row_address = row;
            step(in);
        }
    }

    void read_one(unsigned address) {
        Inputs in;
        in.read = true;
        in.address = address;
        step(in);
    }

    void reset_and_check_retention(bool all_requests) {
        Inputs reset;
        reset.rst = false;
        reset.read = true;
        reset.load = reset.row = reset.commit = all_requests;
        reset.address = N - 1;
        reset.row_address = T - 1;
        reset.commit_address = N - 1;
        reset.word = reset.commit_word = 0x12345678u;
        step(reset);
        quiet(1); // Release with no accepted request.
        quiet(4); // No pre-reset delayed valid may appear.
        scalar_all();
        row_all(); // RAM retention is observed before the following full reload.
    }
};

void run(Harness& h) {
    Inputs initial_reset;
    initial_reset.rst = false;
    h.step(initial_reset);
    h.quiet(1);
    h.load_all(0);
    h.scalar_all();
    if (h.negative) throw std::runtime_error("HOST_IMAGE_NEGATIVE_ORACLE_MISSED");
    h.quiet(2);
    h.row_all();
    h.quiet(2);
    for (unsigned bank = 0; bank < P; ++bank) {
        const unsigned address = bank * T + bank % T;
        Inputs both;
        both.load = both.read = true;
        both.address = address;
        both.word = SIGNED_WORDS[bank % SIGNED_WORDS.size()];
        h.step(both); // LOAD WINS: no old-data read-valid promise.
        h.read_one(address);
        Inputs ignored = both;
        ignored.access = false;
        ignored.word ^= 0xffffffffu;
        h.step(ignored);
        h.read_one(address);
        Inputs row = both;
        row.row = true;
        row.row_address = bank % T;
        row.word ^= 0x5a5a5a5au;
        h.step(row); // Internal row wins over both host requests.
        h.read_one(address);
        Inputs commit = row;
        commit.commit = true;
        commit.commit_address = address;
        commit.commit_word = value_for(address, 1);
        commit.address = (address + 1) % N;
        commit.word = 0xdeadbeefu;
        h.step(commit); // Internal commit wins over row and host.
        h.read_one(address);
        h.quiet(1);
    }
    for (unsigned row = 0; row < T; ++row) {
        Inputs in;
        in.access = false;
        in.load = in.read = in.row = true;
        in.row_address = row;
        in.address = (row * P) % N;
        in.word = 0xabcdef01u;
        h.step(in); // Internal rows remain usable while host_access is false.
    }
    // Explicit N-edge scalar canonical/shadow copy cost (not a warm-square cost).
    for (unsigned address = 0; address < N; ++address) {
        Inputs in;
        in.access = false;
        in.load = in.read = in.row = in.commit = true;
        in.address = (address + 1) % N;
        in.word = 0x87654321u;
        in.row_address = address % T;
        in.commit_address = address;
        in.commit_word = value_for(address, 1);
        h.step(in);
    }
    h.scalar_all();
    h.row_all();
    h.reset_and_check_retention(true); // Reset cancels row response eligibility.
    h.load_all(2);
    h.scalar_all();
    h.row_all();
    h.quiet(3);
    h.read_one(N - 1);
    h.reset_and_check_retention(false); // Reset cancels scalar eligibility.
    h.load_all(3);
    h.scalar_all();
    h.row_all();
    h.quiet(3);
    const uint64_t gaps = (N - 1) / 17;
    h.check(h.total.edges == 10 * N + 3 * gaps + 7 * T + 9 * P + 25 &&
            h.total.scalar == 6 * N + 4 * P + 1 && h.total.rows == 7 * T + P &&
            h.total.row_words == 7 * N + P * P && h.total.host_writes == 3 * N + P &&
            h.total.commits == N + P && h.total.ignored == N + T + 3 * P + 2 &&
            h.total.write_priority == P && h.total.resets == 3,
            "HOST_IMAGE_EXACT_EVENT_LEDGER");
}
} // namespace

int main(int argc, char** argv) {
    try {
        VerilatedContext context;
        context.threads(1);
        context.commandArgs(argc, argv);
        DUT dut{&context};
        if (argc == 2 && std::string(argv[1]) == "--runtime-probe") {
            std::cout << "{\"context_threads\":" << context.threads()
                      << ",\"model_threads\":" << dut.threads() << ",\"expected_threads\":1}\n";
            return context.threads() == 1 && dut.threads() == 1 ? 0 : 2;
        }
        const bool negative = argc == 2 && std::string(argv[1]) == "--negative-oracle";
        need(argc == 1 || negative, "HOST_IMAGE_ARGUMENTS");
        Harness h(context, dut, negative);
        run(h);
        need(context.threads() == 1 && dut.threads() == 1, "HOST_IMAGE_THREAD_DRIFT");
        std::cout << "HOST_IMAGE_PORTS_PASS aw=" << AW << " p=" << P
                  << " edges=" << h.total.edges << " scalar=" << h.total.scalar
                  << " rows=" << h.total.rows << " row_words=" << h.total.row_words
                  << " host_writes=" << h.total.host_writes << " commits=" << h.total.commits
                  << " ignored=" << h.total.ignored << " write_priority=" << h.total.write_priority
                  << " resets=" << h.total.resets << " before_checks=" << 2 * h.total.edges
                  << " shadow_bits=" << 32 * N << " copy_cycles=" << N << " read_edge=E0\n";
        dut.final();
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << "\n";
        return 1;
    }
}
