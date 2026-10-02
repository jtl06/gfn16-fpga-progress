// One adapter for legacy benches that use Verilated::threadContextp().
// GFN16_RUNTIME_BENCH is a quoted include path, GFN16_RUNTIME_MODEL a type.
// Explicit-context benches should use native_runtime_context_v1.h directly.
#include "native_runtime_context_v1.h"
#include <string>
#if !defined(GFN16_RUNTIME_BENCH) || !defined(GFN16_RUNTIME_MODEL)
// A tiny pinned selection header changes the included bench/model; the
// adapter itself is shared by every implicit-context qualification bench.
#include "native_runtime_selection_v1.h"
#endif
#ifndef GFN16_RUNTIME_BENCH
#error "GFN16_RUNTIME_BENCH must name the frozen underlying bench"
#endif
#ifndef GFN16_RUNTIME_MODEL
#error "GFN16_RUNTIME_MODEL must name the generated model type"
#endif

#define main gfn16_runtime_legacy_main
#include GFN16_RUNTIME_BENCH
#undef main

int main(int argc, char** argv) {
    VerilatedContext& context = *Verilated::threadContextp();
    gfn16_runtime::configure(context, argc, argv);
    if (argc == 2 && std::string(argv[1]) == "--runtime-probe") {
        GFN16_RUNTIME_MODEL model{&context};
        return gfn16_runtime::probe(context, model);
    }
    const int result = gfn16_runtime_legacy_main(argc, argv);
    return context.threads() == gfn16_runtime::threads ? result : 97;
}
