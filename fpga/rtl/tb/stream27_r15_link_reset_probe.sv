// Passive two-instance probe of literal author reset leaf. No compute/IP taps.
module stream27_r15_link_reset_probe(
 input logic pcie_clk,core_clk,external_reset_n,
 output logic normal_common_reset_n,normal_pcie_reset_n,normal_core_reset_n,
 output logic normal_pcie_ready,normal_core_ready,normal_exhausted,
 output logic [31:0] normal_session,
 output logic limit_common_reset_n,limit_pcie_reset_n,limit_core_reset_n,
 output logic limit_pcie_ready,limit_core_ready,limit_exhausted,
 output logic [31:0] limit_session
);
 genefer_stream27_r15_link_reset_v2 normal(
  .pcie_clk,.core_clk,.external_reset_n,.common_reset_n(normal_common_reset_n),
  .pcie_reset_n(normal_pcie_reset_n),.core_reset_n(normal_core_reset_n),
  .pcie_ready(normal_pcie_ready),.core_ready(normal_core_ready),
  .session(normal_session),.exhausted(normal_exhausted));
 genefer_stream27_r15_link_reset_v2 #(.SESSION_SEED(32'hfffffffe)) limit(
  .pcie_clk,.core_clk,.external_reset_n,.common_reset_n(limit_common_reset_n),
  .pcie_reset_n(limit_pcie_reset_n),.core_reset_n(limit_core_reset_n),
  .pcie_ready(limit_pcie_ready),.core_ready(limit_core_ready),
  .session(limit_session),.exhausted(limit_exhausted));
endmodule
