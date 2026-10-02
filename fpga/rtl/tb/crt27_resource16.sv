// Matched resource probe only; never a board top or an arithmetic profile.
// The two modes differ solely in the selected CRT implementation.
module crt27_resource16 #(
    parameter integer USE_MONT = 0
) (
    input logic clk, rst_n, in_valid,
    input logic [511:0] r1, r2, r3,
    output logic ready,
    output logic [15:0] out_valid,
    output logic [1535:0] coefficient
);
    wire [15:0] lane_ready;
    assign ready = &lane_ready;
    for(genvar lane=0;lane<16;lane=lane+1)begin: lanes
        if(USE_MONT==1)begin: mont
            genefer_crt3_27_mont_pipe crt (
                .clk,.rst_n,.in_valid,
                .r1(r1[lane*32+:32]),.r2(r2[lane*32+:32]),.r3(r3[lane*32+:32]),
                .ready(lane_ready[lane]),.out_valid(out_valid[lane]),
                .coefficient(coefficient[lane*96+:96])
            );
        end else begin: frozen
            genefer_crt3_27_pipe crt (
                .clk,.rst_n,.in_valid,
                .r1(r1[lane*32+:32]),.r2(r2[lane*32+:32]),.r3(r3[lane*32+:32]),
                .ready(lane_ready[lane]),.out_valid(out_valid[lane]),
                .coefficient(coefficient[lane*96+:96])
            );
        end
    end
    // synthesis translate_off
    initial if(USE_MONT!=0 && USE_MONT!=1)$fatal(1,"invalid CRT resource probe mode");
    // synthesis translate_on
endmodule
