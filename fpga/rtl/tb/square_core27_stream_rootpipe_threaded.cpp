// One-thread integration adapter; --runtime-probe does not evaluate RTL.
#define main rootpipe_core_main
#include "square_core27_stream_rootpipe.cpp"
#undef main
int main(int argc, char** argv) {
    Verilated::threadContextp()->threads(1);
    if (argc == 2 && std::string(argv[1]) == "--runtime-probe") {
        Vgenefer_square_core27_stream_rootpipe dut;
        const unsigned context = Verilated::threadContextp()->threads();
        const unsigned model = dut.threads();
        std::cout << "{\"context_threads\":" << context
                  << ",\"model_threads\":" << model << ",\"expected_threads\":1}\n";
        return context == 1 && model == 1 ? 0 : 2;
    }
    return rootpipe_core_main(argc, argv);
}
