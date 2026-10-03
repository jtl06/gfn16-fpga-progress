// Shared simulation context contract. This header is not production RTL.
#ifndef GFN16_NATIVE_RUNTIME_CONTEXT_V1_H
#define GFN16_NATIVE_RUNTIME_CONTEXT_V1_H

#include "verilated.h"
#include <iostream>

#ifndef GFN16_RUNTIME_THREADS
#define GFN16_RUNTIME_THREADS 1
#endif

namespace gfn16_runtime {
constexpr unsigned threads = GFN16_RUNTIME_THREADS;
static_assert(threads == 1 || threads == 2 || threads == 4 || threads == 8,
              "runtime threads must be one, two, four or eight");

inline void configure(VerilatedContext& context, int argc, char** argv) {
    // This must precede construction of every model using this context.
    context.threads(threads);
    context.commandArgs(argc, argv);
}

template<class Model>
inline bool matches(const VerilatedContext& context, const Model& model) {
    return context.threads() == threads && model.threads() == threads;
}

template<class Model>
inline int probe(const VerilatedContext& context, const Model& model) {
    std::cout << "{\"context_threads\":" << context.threads()
              << ",\"model_threads\":" << model.threads()
              << ",\"expected_threads\":" << threads << "}\n";
    return matches(context, model) ? 0 : 2;
}
}  // namespace gfn16_runtime
#endif
