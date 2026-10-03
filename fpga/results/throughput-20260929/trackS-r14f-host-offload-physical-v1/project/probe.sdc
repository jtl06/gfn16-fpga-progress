create_clock -name kernel_clk -period 12.000 [get_ports {clk}]
derive_clock_uncertainty
