# Source this file on aethia: . tools/aethia-env.sh
# Does not install software, activate licenses, or run any hardware command.
export VERILATOR_ROOT=/home/jtl/gfn-fpga-lab/tools/verilator/usr/share/verilator
export IVERILOG_FLAGS="-B /home/jtl/gfn-fpga-lab/tools/iverilog/usr/lib/x86_64-linux-gnu/ivl"
export VVP_FLAGS="-M /home/jtl/gfn-fpga-lab/tools/iverilog/usr/lib/x86_64-linux-gnu/ivl"
export PATH="/home/jtl/gfn-fpga-lab/tools/verilator/usr/bin:/home/jtl/gfn-fpga-lab/tools/iverilog/usr/bin:$PATH"
# Quartus was removed from aethia with user approval on2026-09-30.
# Physical fits run on the authorized cloud workers; simulators remain local.
