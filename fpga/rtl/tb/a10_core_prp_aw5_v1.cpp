// A10 E2E-1: exact parent host driver/oracle, additive merged RTL lineage.
#include "Vgenefer_square_core27_a10_crtmont_v1.h"
#include "verilated.h"
#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using Core = Vgenefer_square_core27_a10_crtmont_v1;
using I = __int128_t;
static void require(bool ok, const std::string& message) {
    if (!ok) throw std::runtime_error(message);
}
template<class T> static I signed96(const T& a) {
    const __uint128_t value = __uint128_t(a[0]) | (__uint128_t(a[1]) << 32) | (__uint128_t(a[2]) << 64);
    return a[2] & 0x80000000u ? I(value) - (I(1) << 96) : I(value);
}
int main(int argc, char** argv) {
    try {
        VerilatedContext context;
        context.threads(1); context.commandArgs(argc, argv);
        Core d{&context};
        if (argc == 2 && std::string(argv[1]) == "--runtime-probe") {
            std::cout << "{\"context_threads\":" << context.threads() << ",\"model_threads\":" << d.threads()
                      << ",\"expected_threads\":1}\n";
            return context.threads() == 1 && d.threads() == 1 ? 0 : 2;
        }
        require(argc == 2 || (argc == 3 && std::string(argv[2]) == "--negative-comparator"), "E2E_ARGUMENTS");
        const bool negative = argc == 3;
        std::ifstream input(argv[1]); require(bool(input), "E2E_MISSING_CORPUS");
        std::string magic; unsigned aw, count;
        require(bool(input >> magic >> aw >> count) && magic == "GFNPRP1" && aw == 5 && count == 8, "E2E_HEADER");
        constexpr unsigned n = 32;
        auto tick = [&]() { d.clk = 0; d.eval(); d.clk = 1; d.eval(); };
        auto idle = [&]() { d.start = 0; d.load_we = 0; d.read_en = 0; };
        uint64_t operations = 0, doubles = 0, total_cycles = 0;
        for (unsigned index = 0; index < count; ++index) {
            std::string tag, classification, bits;
            unsigned id, base, steps, ones;
            require(bool(input >> tag >> id >> base >> classification >> steps >> ones >> bits)
                    && tag == "CASE" && id == index && base >= 69 && base <= 1000000000
                    && (classification == "prime" || classification == "composite")
                    && bits.size() == steps && steps > 0 && steps <= 957 && bits.front() == '1'
                    && bits.find_first_not_of("01") == std::string::npos
                    && unsigned(std::count(bits.begin(), bits.end(), '1')) == ones, "E2E_CASE");
            std::vector<int64_t> expected(n), actual(n);
            for (auto& value : expected) require(bool(input >> value), "E2E_EXPECTED_EXTENT");
            idle(); d.base = base; d.double_bit = 0; d.rst_n = 0; tick(); d.rst_n = 1; tick();
            require(!d.busy && !d.done && !d.error && !d.read_valid && !d.profile_cache_valid, "E2E_RESET");
            for (unsigned i = 0; i < n; ++i) {
                d.host_addr = i; d.write_data = i == 0 ? 1 : 0; d.load_we = 1; tick();
            }
            idle(); tick();
            uint64_t case_cycles = 0;
            for (unsigned k = 0; k < steps; ++k) {
                d.base = base; d.double_bit = bits[k] == '1'; d.start = 1; tick(); d.start = 0;
                require(d.busy && !d.done && !d.error, "E2E_START");
                uint64_t elapsed = 0;
                while (!d.done && elapsed < 65536) { tick(); ++elapsed; }
                require(d.done && !d.busy && !d.error && d.cycles == elapsed, "E2E_COMPLETION");
                require(d.cycles == d.conversion_cycles + d.root_cycles + d.ntt_cycles + d.crt_cycles + d.carry_cycles,
                        "E2E_PHASE_ACCOUNTING");
                require(d.profile_cache_valid && d.profile_loads == (k == 0 ? 1 : 0)
                        && d.profile_hits == (k == 0 ? 0 : 1), "E2E_COLD_WARM_CACHE");
                case_cycles += elapsed;
                // No intermediate readback/reload: the exponent drives one uninterrupted chain.
            }
            for (unsigned i = 0; i < n; ++i) {
                d.host_addr = i; d.read_en = 1; tick();
                const I value = signed96(d.read_data);
                require(d.read_valid && value >= -1 && value < I(base), "E2E_FINAL_DIGIT_RANGE");
                actual[i] = int64_t(value);
            }
            idle(); tick(); require(!d.read_valid && !d.done, "E2E_PULSE_CLEAR");
            const bool minus_one = actual[0] == -1;
            for (unsigned i = 0; i < n; ++i)
                require(minus_one ? actual[i] == (i == 0 ? -1 : 0) : actual[i] >= 0, "E2E_CANONICAL_ENCODING");
            const bool prp = actual[0] == 1 && std::all_of(actual.begin() + 1, actual.end(), [](int64_t v) { return v == 0; });
            std::cout << "E2E_RESULT case=" << index << " base=" << base << " class=" << classification
                      << " steps=" << steps << " doubles=" << ones << " cycles=" << case_cycles << " prp=" << prp << " digits=";
            for (unsigned i = 0; i < n; ++i) std::cout << (i ? "," : "") << actual[i];
            std::cout << "\n";
            if (negative && index == 0) expected[0] = (expected[0] + 1) % base;
            for (unsigned i = 0; i < n; ++i)
                require(actual[i] == expected[i], "E2E_RESIDUE_MISMATCH case=" + std::to_string(index) + " digit=" + std::to_string(i));
            require(classification != "prime" || prp, "E2E_PROVEN_PRIME_NOT_PRP");
            operations += steps; doubles += ones; total_cycles += case_cycles;
        }
        std::string trailing; require(!(input >> trailing) && input.eof(), "E2E_TRAILING_INPUT");
        require(!negative, "E2E_NEGATIVE_NOT_DETECTED");
        std::cout << "E2E_PASS aw=5 cases=" << count << " operations=" << operations << " doubles=" << doubles
                  << " readbacks=" << count << " cycles=" << total_cycles << "\n";
        d.final(); return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << "\n"; return 1; }
}

