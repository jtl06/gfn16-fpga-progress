// F2 one-field integration: immutable parent/candidate outputs and counters,
// five independent phase vectors, reset quarantine and typed oracle negative.
#include "Vroot_lookahead_engine_pair_v1.h"
#include "verilated.h"
#include "native_runtime_context_v1.h"
#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#ifndef F2_TEST_AW
#define F2_TEST_AW 5
#endif
#ifndef F2_TEST_P
#define F2_TEST_P 104857601
#endif
static void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}
int main(int argc, char** argv) {try {
    VerilatedContext context;
    gfn16_runtime::configure(context, argc, argv);
    Vroot_lookahead_engine_pair_v1 d{&context}; d.eval();
    if (argc == 2 && std::string(argv[1]) == "--runtime-probe")
        return gfn16_runtime::probe(context, d);
    bool negative = argc == 3 && std::string(argv[2]) == "--negative-oracle";
    require(argc == 2 || negative, "F2_FIELD_ARGS");
    constexpr unsigned aw = F2_TEST_AW, n = 1u << aw;
    constexpr uint32_t p = F2_TEST_P;
    std::ifstream in(argv[1]);
    std::string magic; unsigned file_aw, file_p, words, cases;
    require(bool(in >> magic >> file_aw >> file_p >> words >> cases), "F2_FIELD_HEADER_SHORT");
    require(magic == "F2FIELD2" && file_aw == aw && file_p == p && cases == 4 &&
            words == (2*aw+2)*257, "F2_FIELD_HEADER");
    std::vector<uint32_t> profile(words), first_input(n);
    for (auto& x : profile) require(bool(in >> x), "F2_FIELD_PROFILE_SHORT");
    auto compare = [&]() { require(!d.pair_mismatch, "F2_FIELD_PAIR_MISMATCH"); };
    auto tick = [&]() { d.clk=0; d.eval(); compare(); d.clk=1; d.eval(); compare(); };
    auto idle = [&]() {
        d.load_we=0; d.read_en=0; d.vector_load_we=0; d.vector_read_en=0;
        d.profile_begin=0; d.profile_we=0; d.profile_commit=0; d.start=0;
    };
    auto reset = [&]() {
        idle(); d.rst_n=0; tick(); d.rst_n=1; tick();
        require(!d.busy && !d.done && !d.error && !d.profile_loaded &&
                !d.read_valid && !d.vector_read_valid, "F2_FIELD_RESET");
    };
    auto load_profile = [&]() {
        idle(); d.size_log2=aw; d.profile_begin=1; d.profile_size_log2=aw;
        d.profile_modulus=p; d.profile_format=2; tick(); idle();
        require(d.profile_loading && !d.profile_error, "F2_FIELD_PROFILE_BEGIN");
        for (unsigned a=0; a<words; ++a) {
            d.profile_we=1; d.profile_addr=a; d.profile_data=profile[a]; tick();
            require(!d.profile_error && d.profile_next_addr==a+1, "F2_FIELD_PROFILE_WRITE");
        }
        idle(); d.profile_commit=1; tick(); idle();
        require(d.profile_loaded && !d.profile_error && d.profile_loaded_size==aw,
                "F2_FIELD_PROFILE_COMMIT");
    };
    auto load_data = [&](const std::vector<uint32_t>& values) {
        for (unsigned a=0; a<n; ++a) {
            d.load_we=1; d.host_addr=a; d.write_data=values[a]; tick();
        }
        idle(); tick();
    };
    auto start_phase = [&](unsigned step) {
        d.root_phase=step==0 ? 0 : step==1 ? 1 : step==3 ? 2 : 3;
        d.op=step==0 || step==4 ? 2 : step==2 ? 1 : 0;
        d.dif=step==1; d.inverse=0; d.scale=0; d.start=1; tick(); idle();
    };
    unsigned operations=0, readbacks=0, aborts=0, faults=0;
    std::array<uint64_t,5> phase_cycles{};
    reset(); d.size_log2=aw; d.profile_begin=1; d.profile_size_log2=aw;
    d.profile_modulus=p; d.profile_format=1; tick(); idle();
    require(d.profile_error && !d.profile_loaded && !d.profile_loading, "F2_FIELD_PROFILE_FAULT"); faults++;
    for (unsigned c=0; c<cases; ++c) {
        reset(); load_profile();
        std::vector<uint32_t> input(n);
        for (auto& x : input) require(bool(in >> x), "F2_FIELD_INPUT_SHORT");
        if (c==0) first_input=input;
        load_data(input);
        for (unsigned step=0; step<5; ++step) {
            start_phase(step);
            unsigned elapsed=0;
            while (!d.done) {
                tick(); require(++elapsed < 200000, "F2_FIELD_TIMEOUT");
            }
            require(!d.error && !d.busy && d.cycles>0, "F2_FIELD_RUN");
            if (c==0) phase_cycles[step]=d.cycles;
            else require(phase_cycles[step]==d.cycles, "F2_FIELD_DATA_DEPENDENT_CYCLES");
            operations++;
            for (unsigned a=0; a<n; ++a) {
                uint32_t expected;
                require(bool(in >> expected), "F2_FIELD_EXPECTED_SHORT");
                if (negative && c==0 && step==0 && a==0) expected=(expected+1)%p;
                d.read_en=1; d.host_addr=a; tick();
                require(d.read_valid && d.read_data==expected && d.read_data<p,
                        "F2_FIELD_INTEGER_ORACLE"); readbacks++;
            }
            idle(); tick();
        }
    }
    std::string extra; require(!(in >> extra) && in.eof(), "F2_FIELD_TRAILING_INPUT");
    // Reset during each operation at two occupancies. Reset clears profile
    // eligibility; a fresh host canary then detects late writes from old work.
    for (unsigned step=0; step<5; ++step) for (unsigned age : {0u,4u}) {
        reset(); load_profile(); load_data(first_input); start_phase(step);
        // Root setup varies by phase/N. Wait for an actual accepted data read;
        // resetting at a fixed early cycle could only exercise seed loading.
        unsigned issue_wait=0;
        while (d.data_reads==0 && !d.done) {
            tick(); require(++issue_wait<20000, "F2_FIELD_ABORT_ISSUE_TIMEOUT");
        }
        require(d.data_reads>0 && !d.done, "F2_FIELD_ABORT_ACCEPTED_WORK");
        for (unsigned a=0; a<age && !d.done; ++a) tick();
        reset(); d.load_we=1; d.host_addr=0; d.write_data=111; tick(); idle();
        for (unsigned a=0; a<20; ++a) {
            tick(); require(!d.busy && !d.done && !d.profile_loaded, "F2_FIELD_RESET_QUARANTINE");
        }
        d.read_en=1; d.host_addr=0; tick();
        require(d.read_valid && d.read_data==111, "F2_FIELD_RESET_LATE_WRITE");
        idle(); tick(); aborts++;
        d.op=0; d.root_phase=1; d.dif=1; d.inverse=0; d.start=1; tick(); idle();
        require(d.done && d.error && !d.busy, "F2_FIELD_RESET_ELIGIBILITY"); faults++;
    }
    require(operations==20 && readbacks==20*n && aborts==10 && faults==11,
            "F2_FIELD_COVERAGE");
    require(gfn16_runtime::matches(context,d), "F2_FIELD_RUNTIME_THREADS");
    std::cout << "F2_FIELD_PASS aw=" << aw << " p=" << p << " cases=" << cases
              << " operations=" << operations << " readbacks=" << readbacks
              << " aborts=" << aborts << " faults=" << faults << " phase_cycles=";
    for (unsigned step=0; step<5; ++step) std::cout << (step ? "," : "") << phase_cycles[step];
    std::cout << " threads=" << context.threads() << "\n";
    return 0;
} catch (const std::exception& e) { std::cerr << e.what() << "\n"; return 1; }}
