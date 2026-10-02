#include "Vgenefer_arithmetic_top.h"
#include "verilated.h"
#include <array>
#include <cstdint>
#include <deque>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>

struct Vector {
    unsigned field = 0;
    uint32_t a = 0, b = 0, w = 0, mul = 0, y0 = 0, y1 = 0;
    bool valid = false;
};

int main(int argc, char** argv) {
    try {
        if (argc != 2) throw std::runtime_error("expected vector-file argument");
        std::ifstream file(argv[1]);
        if (!file) throw std::runtime_error("cannot open vectors");
        Vgenefer_arithmetic_top dut;
        std::deque<Vector> history;
        std::array<uint32_t, 3> old_base{}, old_pipe{}, old_y0{}, old_y1{};
        uint64_t cycles = 0, vectors = 0, bubbles = 0, resets = 0;
        std::array<uint64_t, 3> base_checks{}, pipe_checks{}, butterfly_checks{};
        std::array<uint64_t, 3> flushed_pipe{}, flushed_butterfly{};
        const auto fail = [&](const std::string& why) {
            throw std::runtime_error("cycle " + std::to_string(cycles) + ": " + why);
        };
        const auto step = [&](Vector input, bool reset) {
            ++cycles;
            dut.clk = 0;
            dut.rst_n = !reset;
            dut.in_valid = input.valid ? (1u << input.field) : 0;
            dut.a = input.a; dut.b = input.b; dut.w = input.w;
            dut.eval();
            if (reset) {
                ++resets;
                // Previously submitted transactions not yet delivered at reset.
                for (size_t i = 0; i < history.size(); ++i) {
                    if (history[i].valid) {
                        if (i < 3) ++flushed_pipe[history[i].field];
                        if (i < 4) ++flushed_butterfly[history[i].field];
                    }
                }
                history.clear();
                if (dut.baseline_valid || dut.pipe_valid || dut.butterfly_valid)
                    fail("asynchronous reset did not clear valid flags");
                for (unsigned f = 0; f < 3; ++f)
                    if (dut.baseline_result[f] || dut.pipe_result[f] || dut.y0[f] || dut.y1[f])
                        fail("asynchronous reset did not clear data");
            } else {
                history.push_front(input);
                if (history.size() > 5) history.pop_back();
            }
            dut.clk = 1;
            dut.eval();
            const auto expected = [&](unsigned age, unsigned f) -> const Vector* {
                if (age >= history.size() || !history[age].valid || history[age].field != f)
                    return nullptr;
                return &history[age];
            };
            for (unsigned f = 0; f < 3; ++f) {
                const Vector* base = expected(0, f);
                const Vector* pipe = expected(3, f);
                const Vector* bf = expected(4, f);
                if (bool((dut.baseline_valid >> f) & 1) != bool(base) ||
                    bool((dut.pipe_valid >> f) & 1) != bool(pipe) ||
                    bool((dut.butterfly_valid >> f) & 1) != bool(bf))
                    fail("valid/latency mismatch in field " + std::to_string(f));
                if (base) {
                    ++base_checks[f];
                    if (dut.baseline_result[f] != base->mul) fail("baseline value mismatch");
                } else if (dut.baseline_result[f] != (reset ? 0 : old_base[f]))
                    fail("baseline data changed without valid");
                if (pipe) {
                    ++pipe_checks[f];
                    if (dut.pipe_result[f] != pipe->mul) fail("pipeline value mismatch");
                } else if (dut.pipe_result[f] != (reset ? 0 : old_pipe[f]))
                    fail("pipeline data changed without valid");
                if (bf) {
                    ++butterfly_checks[f];
                    if (dut.y0[f] != bf->y0 || dut.y1[f] != bf->y1) fail("butterfly value mismatch");
                } else if (dut.y0[f] != (reset ? 0 : old_y0[f]) || dut.y1[f] != (reset ? 0 : old_y1[f]))
                    fail("butterfly data changed without valid");
                old_base[f] = dut.baseline_result[f];
                old_pipe[f] = dut.pipe_result[f];
                old_y0[f] = dut.y0[f]; old_y1[f] = dut.y1[f];
            }
        };
        step({}, true);
        step({}, false);
        Vector record;
        std::string line;
        while (std::getline(file, line)) {
            std::istringstream row(line);
            std::string extra;
            if (!(row >> record.field >> record.a >> record.b >> record.w >> record.mul >> record.y0 >> record.y1) ||
                (row >> extra)) fail("malformed vector row");
            if (record.field > 2) fail("invalid field index");
            record.valid = true;
            // Long uninterrupted bursts plus deterministic isolated/clustered bubbles.
            if ((vectors % 257) >= 240) {
                Vector bubble = record;
                bubble.valid = false; // nonzero/changing data while invalid
                step(bubble, false);
                ++bubbles;
            }
            step(record, false);
            ++vectors;
            if (vectors % 997 == 0) {
                step({}, true); // deliberately interrupt a live pipeline
                step({}, false);
            }
        }
        if (!file.eof()) fail("malformed vectors");
        if (vectors != 13317) fail("incomplete vector set");
        for (unsigned i = 0; i < 8; ++i) step({}, false);
        for (unsigned f = 0; f < 3; ++f) {
            if (base_checks[f] != 4439 || pipe_checks[f] + flushed_pipe[f] != base_checks[f] ||
                butterfly_checks[f] + flushed_butterfly[f] != base_checks[f] ||
                flushed_butterfly[f] == 0)
                fail("incomplete field coverage or transaction accounting");
            std::cout << "field=" << f + 1 << " baseline=" << base_checks[f]
                      << " pipeline=" << pipe_checks[f] << " butterfly=" << butterfly_checks[f]
                      << " flushed_pipeline=" << flushed_pipe[f]
                      << " flushed_butterfly=" << flushed_butterfly[f] << '\n';
        }
        dut.final();
        std::cout << "PASS vectors=" << vectors << " cycles=" << cycles
                  << " bubbles=" << bubbles << " resets=" << resets << '\n';
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "FAIL: " << e.what() << '\n';
        return 1;
    }
}
