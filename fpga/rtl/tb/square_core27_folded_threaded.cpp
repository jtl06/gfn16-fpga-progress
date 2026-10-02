// New opt-in adapter; the validated oracle/bench below remains unchanged.
#define main frozen_core27_main
#include "square_core27_folded.cpp"
#undef main

#ifndef CORE27_RUNTIME_THREADS
#define CORE27_RUNTIME_THREADS 1
#endif
static_assert(CORE27_RUNTIME_THREADS == 1 || CORE27_RUNTIME_THREADS == 8,
              "supported runtime thread counts are one and eight");

int main(int argc, char** argv) {
    const bool probe = argc == 2 && std::string(argv[1]) == "--runtime-probe";
    const bool override_probe = argc == 3 && std::string(argv[1]) == "--probe-context";
    unsigned requested = CORE27_RUNTIME_THREADS;
    if (override_probe) {
        const std::string value(argv[2]);
        if (value != "1" && value != "8") {
            std::cerr << "unsupported probe context\n";
            return 2;
        }
        requested = value == "1" ? 1 : 8;
    }
    Verilated::threadContextp()->threads(requested);
    if (probe || override_probe) {
        // Probe is a separate process, never a cached correctness result.
        Vgenefer_square_core27_folded dut;
        const unsigned context = Verilated::threadContextp()->threads();
        const unsigned model = dut.threads();
        std::cout << "{\"context_threads\":" << context
                  << ",\"model_threads\":" << model
                  << ",\"expected_threads\":" << CORE27_RUNTIME_THREADS << "}\n";
        return context == CORE27_RUNTIME_THREADS && model == CORE27_RUNTIME_THREADS ? 0 : 2;
    }
    const int result = frozen_core27_main(argc, argv);
    if (Verilated::threadContextp()->threads() != CORE27_RUNTIME_THREADS) return 97;
    return result;
}
