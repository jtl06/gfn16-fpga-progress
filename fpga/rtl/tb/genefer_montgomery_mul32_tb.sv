`timescale 1ns/1ps

module genefer_montgomery_mul32_tb;
    logic clk = 1'b0;
    logic rst_n = 1'b0;
    logic in_valid = 1'b0;
    logic in_valid1, in_valid2, in_valid3;
    logic [31:0] lhs = '0;
    logic [31:0] rhs = '0;
    logic valid1, valid2, valid3;
    logic [31:0] result1, result2, result3;

    integer fd;
    integer rc;
    integer prime_index;
    integer tests = 0;
    integer failures = 0;
    integer prime1_tests = 0;
    integer prime2_tests = 0;
    integer prime3_tests = 0;
    reg [31:0] expected;
    string vector_path;
    // Header buffer is discarded; scan numeric records directly from the file
    // to avoid simulator differences in packed-buffer-to-string conversion.
    reg [2047:0] line;

    always #5 clk = ~clk;

    assign in_valid1 = in_valid && (prime_index == 1);
    assign in_valid2 = in_valid && (prime_index == 2);
    assign in_valid3 = in_valid && (prime_index == 3);

    genefer_montgomery_mul32 #(.P(32'd2130706433), .Q(32'd2164260865)) dut1 (
        .clk, .rst_n, .in_valid(in_valid1), .lhs, .rhs, .out_valid(valid1), .result(result1)
    );
    genefer_montgomery_mul32 #(.P(32'd2113929217), .Q(32'd2181038081)) dut2 (
        .clk, .rst_n, .in_valid(in_valid2), .lhs, .rhs, .out_valid(valid2), .result(result2)
    );
    genefer_montgomery_mul32 #(.P(32'd2013265921), .Q(32'd2281701377)) dut3 (
        .clk, .rst_n, .in_valid(in_valid3), .lhs, .rhs, .out_valid(valid3), .result(result3)
    );

    initial begin
        if (!$value$plusargs("VECTORS=%s", vector_path)) begin
            vector_path = "vectors/montgomery_mul32.hex";
        end
        fd = $fopen(vector_path, "r");
        if (fd == 0) $fatal(1, "cannot open vector file %s", vector_path);
        repeat (2) begin
            rc = $fgets(line, fd);
            if (rc == 0) $fatal(1, "missing vector header");
        end

        repeat (3) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;

        while (!$feof(fd)) begin
            rc = $fscanf(fd, "%d %h %h %h", prime_index, lhs, rhs, expected);
            if (rc != -1 && !(rc == 0 && $feof(fd))) begin
                if (rc == 4) begin
                    @(negedge clk);
                    in_valid = 1'b1;
                    @(posedge clk);
                    #1;
                    in_valid = 1'b0;
                    tests = tests + 1;
                    case (prime_index)
                        1: begin
                            prime1_tests = prime1_tests + 1;
                            if (!valid1 || result1 !== expected) failures = failures + 1;
                        end
                        2: begin
                            prime2_tests = prime2_tests + 1;
                            if (!valid2 || result2 !== expected) failures = failures + 1;
                        end
                        3: begin
                            prime3_tests = prime3_tests + 1;
                            if (!valid3 || result3 !== expected) failures = failures + 1;
                        end
                        default: $fatal(1, "invalid prime index");
                    endcase
                end else begin
                    $fatal(1, "malformed vector record after %0d tests", tests);
                end
            end
        end
        $fclose(fd);
        if (tests != 531 || prime1_tests != 177 || prime2_tests != 177 || prime3_tests != 177) begin
            $fatal(1, "incomplete vector set: total=%0d p1=%0d p2=%0d p3=%0d",
                tests, prime1_tests, prime2_tests, prime3_tests);
        end
        if (failures != 0) $fatal(1, "%0d of %0d vectors failed", failures, tests);
        $display("PASS: %0d Montgomery vectors", tests);
        $finish;
    end
endmodule
