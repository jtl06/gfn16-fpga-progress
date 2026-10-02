create_clock -name kernel_clk -period 14.000 [get_ports {clk}]
derive_clock_uncertainty
