// A-next command-host soak: same donor checkpoint protocol, distinct cycle/ABI contract.
#include "Vgenefer_anext_point_core_v1.h"
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
using Core = Vgenefer_anext_point_core_v1;
static void require(bool ok, const std::string& message) {
    if (!ok) throw std::runtime_error(message);
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
            && base >= std::max(2*n+5,(2*(2*n+384)+2)/3+1) && base <= 1000000000 && start < end && end <= 4096
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
        d.cmd_valid=0;d.rsp_ready=0;d.cmd_opcode=0;d.cmd_address=0;
        d.cmd_word=0;d.cmd_base=base;d.cmd_double=0;
        auto command=[&](unsigned opcode,unsigned address,int32_t word,bool bit){
            require(d.cmd_ready && !d.rsp_valid,"SOAK_COMMAND_READY");
            d.cmd_opcode=opcode;d.cmd_address=address;d.cmd_word=word;
            d.cmd_base=base;d.cmd_double=bit;d.cmd_valid=1;tick();d.cmd_valid=0;
            uint64_t waited=0;while(!d.rsp_valid && waited<65536+uint64_t(64)*n){
                require(!d.cmd_ready,"SOAK_COMMAND_BACKPRESSURE");tick();++waited;
            }
            require(d.rsp_valid && !d.rsp_error && !d.fault_sticky && d.rsp_opcode==opcode,"SOAK_COMMAND_RESPONSE");
            if(opcode==5)require(waited==d.square_cycles+2,"SOAK_COMMAND_CYCLE_ALIGNMENT");
            const int32_t result=int32_t(d.rsp_word);const auto generation=d.rsp_generation;
            tick();require(d.rsp_valid && d.rsp_generation==generation && int32_t(d.rsp_word)==result && !d.rsp_error,"SOAK_RESPONSE_HOLD");
            d.rsp_ready=1;tick();d.rsp_ready=0;return result;
        };
        d.rst_n=0;tick();d.rst_n=1;tick();
        require(!d.busy && !d.rsp_valid && !d.image_valid && !d.prefill_valid,"SOAK_RESET");
        command(0,0,0,false);
        for(unsigned i=0;i<n;++i){
            auto value=checks.front().digits[i];
            if(negative_load && i==0)value=value==-1?0:(value+1)%base;
            command(1,i,int32_t(value),false);
        }
        unsigned readbacks = 0;
        auto readback = [&](const Check& check, bool corrupt_expected) {
            require(!d.busy && !d.fault_sticky,"SOAK_READBACK_IDLE");
            std::vector<int64_t> actual(n);
            for(unsigned i=0;i<n;++i){
                const int32_t value=command(2,i,0,false);
                require(value>=-1 && int64_t(value)<int64_t(base),"SOAK_READ_DIGIT_RANGE");
                actual[i]=value;
            }
            require(!d.prefill_valid,"SOAK_CANONICAL_READ_INVALIDATES_PREFILL");
            canonical(actual, base);
            std::cout << "ANEXT_SOAK_CHECK {\"case_id\":\"" << case_id << "\",\"step\":" << check.step << ",\"digits\":[";
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
        unsigned next_check = 1, doubles = 0, cold_prefill = 0;
        for (unsigned k = 0; k < bits.size(); ++k) {
            const bool cold=!d.prefill_valid;
            command(5,0,0,bits[k]=='1');
            const uint64_t elapsed=d.square_cycles;
            const uint64_t groups=std::max(uint64_t(1),uint64_t(n)/128);
            const uint64_t expected_ntt=2*uint64_t(aw)*(groups+9)+std::max(uint64_t(1),uint64_t(n)/64)+14;
            const uint64_t expected_post=n/16+62;
            const uint64_t expected_prefill=cold?n/16+10:0;
            const uint64_t expected_control=cold?7:5;
            require(d.image_valid && d.prefill_valid && d.profile_loads==(k==0) && d.profile_hits==(k!=0),"SOAK_PERSISTENT_PROFILE_CACHE");
            require(d.ntt_cycles==expected_ntt && d.post_cycles==expected_post && d.prefill_cycles==expected_prefill && d.root_cycles==(k==0?9u:0u) && d.seed_setup_cycles==0,"SOAK_ANEXT_PHASES");
            require(elapsed==d.prefill_cycles+d.root_cycles+d.ntt_cycles+d.post_cycles+expected_control,"SOAK_ANEXT_ACCOUNTING");
            const unsigned step=start+k+1;cold_prefill+=cold;
            std::cout << "ANEXT_SOAK_STEP {\"case_id\":\"" << case_id << "\",\"step\":" << step
                << ",\"bit\":" << (bits[k]=='1') << ",\"cycles\":" << elapsed
                << ",\"prefill\":" << d.prefill_cycles << ",\"roots\":" << d.root_cycles
                << ",\"ntt\":" << d.ntt_cycles << ",\"post\":" << d.post_cycles << ",\"control\":" << expected_control
                << ",\"profile_loads\":" << unsigned(d.profile_loads) << ",\"profile_hits\":" << unsigned(d.profile_hits) << "}\n";
            total_cycles += elapsed; doubles += bits[k] == '1';
            if (step == checks[next_check].step) {
                readback(checks[next_check], negative_boundary && next_check == 1); ++next_check;
            }
            // No reset/reload between operations. Canonical readback preserves
            // roots and digit image, but invalidates field prefill by contract.
        }
        require(next_check == count && readbacks == count, "SOAK_BOUNDARY_COVERAGE");
        require(!(negative_boundary || negative_load), "SOAK_NEGATIVE_NOT_DETECTED");
        require(gfn16_runtime::matches(context, d), "SOAK_RUNTIME_THREADS");
        std::cout << "ANEXT_SOAK_PASS {\"case_id\":\"" << case_id << "\",\"mode\":\"" << mode << "\",\"start\":" << start
            << ",\"end\":" << end << ",\"operations\":" << bits.size() << ",\"doubles\":" << doubles
            << ",\"readbacks\":" << readbacks << ",\"cycles\":" << total_cycles << ",\"resets\":1,\"loaded_digits\":" << n
            << ",\"cold_prefill\":" << cold_prefill << ",\"warm_prefill\":" << bits.size()-cold_prefill
            << ",\"cache_cold\":1,\"cache_warm\":" << bits.size()-1 << "}\n";
        d.final(); return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << "\n"; return 1; }
}
