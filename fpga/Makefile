PYTHON ?= python3
VERILATOR ?= verilator
IVERILOG ?= iverilog
IVERILOG_FLAGS ?=
VVP ?= vvp
VVP_FLAGS ?=
RTL_BUILD ?= $(CURDIR)/artifacts/rtl-stream
RTL_SEED ?= 0x47464e16
.DEFAULT_GOAL := verify

.PHONY: verify full-check vectors mock clean-generated rtl-check rtl-baseline rtl-icarus

rtl-icarus: vectors
	mkdir -p $(RTL_BUILD)/icarus
	$(IVERILOG) $(IVERILOG_FLAGS) -g2012 -s genefer_montgomery_mul32_tb -o $(RTL_BUILD)/icarus/baseline.vvp rtl/kernel/genefer_montgomery_mul32.sv rtl/tb/genefer_montgomery_mul32_tb.sv
	$(VVP) $(VVP_FLAGS) $(RTL_BUILD)/icarus/baseline.vvp +VECTORS=$(CURDIR)/vectors/montgomery_mul32.hex

# Simulation only: these targets never invoke vendor tools or access hardware.
rtl-baseline: vectors
	mkdir -p $(RTL_BUILD)/baseline
	$(VERILATOR) --binary --timing --top-module genefer_montgomery_mul32_tb --Mdir $(RTL_BUILD)/baseline -Wno-TIMESCALEMOD rtl/kernel/genefer_montgomery_mul32.sv rtl/tb/genefer_montgomery_mul32_tb.sv
	$(RTL_BUILD)/baseline/Vgenefer_montgomery_mul32_tb +VECTORS=$(CURDIR)/vectors/montgomery_mul32.hex

rtl-check:
	$(PYTHON) -m reference.rtl_vectors --output $(RTL_BUILD)/vectors.txt --seed $(RTL_SEED)
	$(VERILATOR) --cc --exe --build -j 2 --top-module genefer_arithmetic_top --Mdir $(RTL_BUILD)/obj rtl/kernel/genefer_montgomery_mul32.sv rtl/kernel/genefer_montgomery_mul32_pipe.sv rtl/kernel/genefer_ntt_butterfly32.sv rtl/tb/genefer_arithmetic_top.sv $(CURDIR)/rtl/tb/arithmetic_stream.cpp
	$(RTL_BUILD)/obj/Vgenefer_arithmetic_top $(RTL_BUILD)/vectors.txt

verify: vectors
	$(PYTHON) -m unittest discover -s tests -v

full-check:
	$(PYTHON) -m reference.full_ntt_check

vectors:
	$(PYTHON) -m reference.generate_vectors --jsonl vectors/montgomery_mul32.jsonl --hex vectors/montgomery_mul32.hex

mock: vectors
	$(PYTHON) -m autolab.runner --workspace . --candidate candidates/baseline-montgomery.json

clean-generated:
	rm -f vectors/montgomery_mul32.jsonl vectors/montgomery_mul32.hex artifacts/experiments.sqlite3
