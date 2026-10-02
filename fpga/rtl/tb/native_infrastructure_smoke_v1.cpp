#include "Vnative_infrastructure_smoke_v1.h"
#include "verilated.h"
#include <cstdint>
#include <iostream>
#include <string>

int main(int argc, char **argv) {
    VerilatedContext context;
    context.threads(1);
    context.commandArgs(argc, argv);
    Vnative_infrastructure_smoke_v1 model{&context};
    if (argc == 2 && std::string(argv[1]) == "--runtime-probe") {
        std::cout << "{\"context_threads\":" << context.threads()
                  << ",\"model_threads\":" << model.threads()
                  << ",\"expected_threads\":1}\n";
        return (context.threads() == 1 && model.threads() == 1) ? 0 : 1;
    }
    if (argc != 1) return 2;
    uint32_t expected = 0;
    unsigned accepted = 0, resets = 0;
    for (unsigned tick = 0; tick < 257; ++tick) {
        const bool reset = tick % 37 == 0;
        const bool valid = tick % 5 != 0;
        const uint32_t value = 0x1020304u * tick + 19u;
        model.clk = 0;
        model.rst_n = !reset;
        model.valid = valid;
        model.data_in = value;
        model.eval();
        model.clk = 1;
        model.eval();
        if (reset) { expected = 0; ++resets; }
        else if (valid) { expected = value ^ 0xa5c39e71u; ++accepted; }
        if (model.out_valid != (!reset && valid) || model.data_out != expected) {
            std::cerr << "NATIVE_SMOKE_MISMATCH tick=" << tick << '\n';
            return 1;
        }
    }
    model.final();
    std::cout << "NATIVE_SMOKE_PASS ticks=257 accepted=" << accepted << " resets=" << resets << '\n';
    return 0;
}
