// Additive T5b E2E-2 driver: same frozen host loop, separately pinned model.
#include "Vgenefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill_pipe_v1.h"
#include "native_runtime_context_v1.h"
#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

#ifndef GFN16_SOAK_AW
#define GFN16_SOAK_AW 16
#endif
using Core = Vgenefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill_pipe_v1;
using I = __int128_t;
static void require(bool ok, const std::string& message) {
    if (!ok) throw std::runtime_error(message);
}
template<class T> static I signed96(const T& a) {
    const __uint128_t value = __uint128_t(a[0]) | (__uint128_t(a[1]) << 32) | (__uint128_t(a[2]) << 64);
    return a[2] & 0x80000000u ? I(value) - (I(1) << 96) : I(value);
}
struct Check { unsigned step; std::vector<int64_t> digits; };
static void canonical(const std::vector<int64_t>& digits, unsigned base) {
    const bool minus_one = digits.front() == -1;
    for (unsigned i = 0; i < digits.size(); ++i)
        require(minus_one ? digits[i] == (i == 0 ? -1 : 0) : digits[i] >= 0 && uint64_t(digits[i]) < base,
                "SOAK_CANONICAL_ENCODING");
}
int main(int argc, char** argv) {
    try {
        VerilatedContext context;
        gfn16_runtime::configure(context, argc, argv);
        Core d{&context};
        if (argc == 2 && std::string(argv[1]) == "--runtime-probe")
            return gfn16_runtime::probe(context, d);
        require(argc == 2 || (argc == 3 && (std::string(argv[2]) == "--negative-boundary"
                || std::string(argv[2]) == "--negative-loaded-state")), "SOAK_ARGUMENTS");
        const bool negative_boundary = argc == 3 && std::string(argv[2]) == "--negative-boundary";
        const bool negative_load = argc == 3 && std::string(argv[2]) == "--negative-loaded-state";
        std::ifstream input(argv[1]); require(bool(input), "SOAK_MISSING_CORPUS");
        std::string magic, mode, case_id, tag, bits;
        unsigned aw, base, start, end, count;
        constexpr unsigned n = 1u << GFN16_SOAK_AW;
        require(bool(input >> magic >> aw >> base >> start >> end >> count >> mode >> case_id)
            && magic == "GFNSOAK1" && aw == GFN16_SOAK_AW && aw >= 5 && aw <= 16
            && base >= 2*n+5 && base <= 1000000000 && start < end && end <= 4096
            && count >= 2 && count <= end-start+1 && (mode == "continuous" || mode == "chunk")
            && (aw <= 8 || count <= 64)
            && (mode != "continuous" || start == 0) && case_id.size() == 64
            && case_id.find_first_not_of("0123456789abcdef") == std::string::npos, "SOAK_HEADER");
        require(bool(input >> tag >> bits) && tag == "BITS" && bits.size() == end-start
            && bits.find_first_not_of("01") == std::string::npos, "SOAK_BITS");
        std::vector<Check> checks;
        for (unsigned c = 0; c < count; ++c) {
            Check check; check.digits.resize(n);
            require(bool(input >> tag >> check.step) && tag == "CHECK" && check.step >= start && check.step <= end
                && (c == 0 ? check.step == start : check.step > checks.back().step), "SOAK_CHECK_SCHEDULE");
            for (auto& value : check.digits) require(bool(input >> value), "SOAK_CHECK_DIGITS");
            canonical(check.digits, base); checks.push_back(std::move(check));
        }
        require(checks.back().step == end, "SOAK_FINAL_CHECK_REQUIRED");
        std::string trailing; require(!(input >> trailing) && input.eof(), "SOAK_TRAILING_CORPUS");
        auto tick = [&]() { d.clk = 0; d.eval(); d.clk = 1; d.eval(); };
        auto idle = [&]() { d.start = 0; d.load_we = 0; d.read_en = 0; };
        idle(); d.base = base; d.double_bit = 0; d.rst_n = 0; tick(); d.rst_n = 1; tick();
        require(!d.busy && !d.done && !d.error && !d.read_valid && !d.profile_cache_valid, "SOAK_RESET");
        for (unsigned i = 0; i < n; ++i) {
            auto value = checks.front().digits[i];
            if (negative_load && i == 0) value = value == -1 ? 0 : (value+1) % base;
            d.host_addr = i; d.write_data = int32_t(value); d.load_we = 1; tick();
        }
        idle(); tick();
        unsigned readbacks = 0;
        auto readback = [&](const Check& check, bool corrupt_expected) {
            require(!d.busy && !d.error, "SOAK_READBACK_IDLE");
            std::vector<int64_t> actual(n);
            for (unsigned i = 0; i < n; ++i) {
                d.host_addr = i; d.read_en = 1; tick();
                const I value = signed96(d.read_data);
                require(d.read_valid && value >= -1 && value < I(base), "SOAK_READ_DIGIT_RANGE");
                actual[i] = int64_t(value);
            }
            idle(); tick(); require(!d.read_valid && !d.done, "SOAK_PULSE_CLEAR");
            canonical(actual, base);
            std::cout << "SOAK_CHECK {\"case_id\":\"" << case_id << "\",\"step\":" << check.step << ",\"digits\":[";
            for (unsigned i = 0; i < n; ++i) std::cout << (i ? "," : "") << actual[i];
            std::cout << "]}\n" << std::flush;
            for (unsigned i = 0; i < n; ++i) {
                auto expected = check.digits[i];
                if (corrupt_expected && i == 0) expected = expected == -1 ? 0 : (expected+1) % base;
                require(actual[i] == expected, "SOAK_BOUNDARY_MISMATCH step="+std::to_string(check.step)+" digit="+std::to_string(i));
            }
            ++readbacks;
        };
        readback(checks.front(), false);
        uint64_t total_cycles = 0;
        unsigned next_check = 1, doubles = 0;
        const uint64_t timeout_cycles = 65536+uint64_t(64)*n;
        for (unsigned k = 0; k < bits.size(); ++k) {
            d.base = base; d.double_bit = bits[k] == '1'; d.start = 1; tick(); d.start = 0;
            require(d.busy && !d.done && !d.error, "SOAK_START");
            uint64_t elapsed = 0;
            while (!d.done && elapsed < timeout_cycles) { tick(); ++elapsed; }
            require(d.done && !d.busy && !d.error && d.cycles == elapsed, "SOAK_COMPLETION");
            require(d.cycles == d.conversion_cycles+d.root_cycles+d.ntt_cycles+d.crt_cycles+d.carry_cycles,
                    "SOAK_PHASE_ACCOUNTING");
            require(d.profile_cache_valid && d.profile_loads == (k == 0 ? 1 : 0)
                && d.profile_hits == (k == 0 ? 0 : 1), "SOAK_PERSISTENT_PROFILE_CACHE");
            const unsigned step = start+k+1;
            std::cout << "SOAK_STEP {\"case_id\":\"" << case_id << "\",\"step\":" << step
                << ",\"bit\":" << (bits[k] == '1') << ",\"cycles\":" << elapsed
                << ",\"conversion\":" << d.conversion_cycles << ",\"roots\":" << d.root_cycles
                << ",\"ntt\":" << d.ntt_cycles << ",\"crt\":" << d.crt_cycles << ",\"carry\":" << d.carry_cycles
                << ",\"profile_loads\":" << unsigned(d.profile_loads) << ",\"profile_hits\":" << unsigned(d.profile_hits) << "}\n";
            total_cycles += elapsed; doubles += bits[k] == '1';
            if (step == checks[next_check].step) {
                readback(checks[next_check], negative_boundary && next_check == 1); ++next_check;
            }
            // No reset or host reload between operations. Readbacks preserve
            // controller/cache state; the uninterrupted gate uses this loop.
        }
        require(next_check == count && readbacks == count, "SOAK_BOUNDARY_COVERAGE");
        require(!(negative_boundary || negative_load), "SOAK_NEGATIVE_NOT_DETECTED");
        require(gfn16_runtime::matches(context, d), "SOAK_RUNTIME_THREADS");
        std::cout << "SOAK_PASS {\"case_id\":\"" << case_id << "\",\"mode\":\"" << mode << "\",\"start\":" << start
            << ",\"end\":" << end << ",\"operations\":" << bits.size() << ",\"doubles\":" << doubles
            << ",\"readbacks\":" << readbacks << ",\"cycles\":" << total_cycles << ",\"resets\":1,\"loaded_digits\":" << n
            << ",\"cold\":1,\"warm\":" << bits.size()-1 << "}\n";
        d.final(); return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << "\n"; return 1; }
}
