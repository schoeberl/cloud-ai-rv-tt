// Copyright (c) 2026 Martin Schoeberl
// SPDX-License-Identifier: BSD-2-Clause
`default_nettype none
module tt_um_schoeberl_rv32alu (
    input wire [7:0] ui_in, output wire [7:0] uo_out,
    input wire [7:0] uio_in, output wire [7:0] uio_out,
    output wire [7:0] uio_oe, input wire ena, input wire clk, input wire rst_n
);
    wire [3:0] command = uio_in[3:0];
    wire clear = ena && command == 4'hf;
    reg [31:0] operand_a, operand_b, result;
    reg equal_flag, signed_flag, unsigned_flag;
    reg busy, done, invalid_op;
    wire launch = ena && !busy && command == 4'h9;
    wire [31:0] alu_result;
    wire alu_equal, alu_signed, alu_unsigned, alu_valid;
    Rv32AluFast alu (
        .clock(clk), .reset(!rst_n || clear),
        .io_a(operand_a), .io_b(operand_b), .io_op(uio_in[7:4]),
        .io_validIn(launch), .io_result(alu_result),
        .io_equal(alu_equal), .io_lessSigned(alu_signed),
        .io_lessUnsigned(alu_unsigned), .io_validOut(alu_valid)
    );
    always @(posedge clk) begin
        if (!rst_n || clear) begin
            operand_a <= 0; operand_b <= 0; result <= 0;
            equal_flag <= 0; signed_flag <= 0; unsigned_flag <= 0;
            busy <= 0; done <= 0; invalid_op <= 0;
        end else begin
            if (alu_valid && busy) begin
                result <= alu_result;
                equal_flag <= alu_equal; signed_flag <= alu_signed;
                unsigned_flag <= alu_unsigned; busy <= 0; done <= 1;
            end
            if (ena && !busy) begin
                case (command)
                    4'h1: operand_a[7:0]   <= ui_in;
                    4'h2: operand_a[15:8]  <= ui_in;
                    4'h3: operand_a[23:16] <= ui_in;
                    4'h4: operand_a[31:24] <= ui_in;
                    4'h5: operand_b[7:0]   <= ui_in;
                    4'h6: operand_b[15:8]  <= ui_in;
                    4'h7: operand_b[23:16] <= ui_in;
                    4'h8: operand_b[31:24] <= ui_in;
                    4'h9: begin
                        busy <= 1; done <= 0;
                        invalid_op <= uio_in[7:4] >= 4'hc;
                    end
                    default: begin end
                endcase
            end
        end
    end
    wire [7:0] status = {2'b10, invalid_op, done, busy,
                         unsigned_flag, signed_flag, equal_flag};
    reg [7:0] read_data;
    always @* begin
        case (command)
            4'ha: read_data = result[7:0];
            4'hb: read_data = result[15:8];
            4'hc: read_data = result[23:16];
            4'hd: read_data = result[31:24];
            default: read_data = status;
        endcase
    end
    assign uo_out = ena ? read_data : 8'h00;
    assign uio_out = 8'h00;
    assign uio_oe = 8'h00;
endmodule
`default_nettype wire
