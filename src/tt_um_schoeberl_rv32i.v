// Copyright (c) 2026 Martin Schoeberl
// SPDX-License-Identifier: BSD-2-Clause
`default_nettype none
module tt_um_schoeberl_rv32i (
    input wire [7:0] ui_in, output wire [7:0] uo_out,
    input wire [7:0] uio_in, output wire [7:0] uio_out,
    output wire [7:0] uio_oe, input wire ena, input wire clk, input wire rst_n
);
    wire [3:0] command = uio_in[3:0];
    wire [1:0] byte_index = uio_in[5:4];
    wire soft_reset = ena && command == 4'hd;
    reg running, pending, instruction_request, write_request, retire_toggle;
    reg [31:0] address, write_data, response_buffer, response_data, last_pc;
    reg [3:0] write_mask;
    reg i_response, d_response, response_error;
    wire i_valid, d_valid, d_write, halted, retire_valid;
    wire [31:0] i_address, d_address, d_data, retired_pc, trap_pc, trap_value;
    wire [3:0] d_mask;
    wire [4:0] trap_cause;
    wire i_ready = running && !pending && !halted && !d_valid;
    wire d_ready = running && !pending && !halted;
    WildcatThreeStage cpu (
        .clock(clk), .reset(!rst_n || !running || soft_reset),
        .io_imem_reqValid(i_valid), .io_imem_reqReady(i_ready), .io_imem_address(i_address),
        .io_imem_respValid(i_response), .io_imem_respData(response_data), .io_imem_respError(response_error),
        .io_dmem_reqValid(d_valid), .io_dmem_reqReady(d_ready), .io_dmem_address(d_address),
        .io_dmem_write(d_write), .io_dmem_writeData(d_data), .io_dmem_writeMask(d_mask),
        .io_dmem_respValid(d_response), .io_dmem_respData(response_data), .io_dmem_respError(response_error),
        .io_halted(halted), .io_trapPc(trap_pc), .io_trapCause(trap_cause), .io_trapValue(trap_value),
        .io_retireValid(retire_valid), .io_retirePc(retired_pc),
        .io_retireInstruction(), .io_retireWrite(), .io_retireRd(), .io_retireData()
    );
    always @(posedge clk) begin
        i_response <= 0; d_response <= 0;
        if (!rst_n || soft_reset) begin
            running <= 0; pending <= 0; instruction_request <= 0; write_request <= 0;
            retire_toggle <= 0; last_pc <= 0;
            address <= 0; write_data <= 0; write_mask <= 0;
            response_buffer <= 0; response_data <= 0; response_error <= 0;
        end else begin
            if (running && retire_valid) begin
                last_pc <= retired_pc; retire_toggle <= !retire_toggle;
            end
            if (ena && command == 4'hc) running <= 1;
            if (ena && command == 4'ha)
                response_buffer[byte_index*8 +: 8] <= ui_in;
            if (halted) pending <= 0;
            else if (pending) begin
                if (ena && command == 4'hb) begin
                    pending <= 0; response_data <= response_buffer; response_error <= ui_in[0];
                    i_response <= instruction_request; d_response <= !instruction_request;
                end
            end else if (running) begin
                // Harvard ports share one externally visible transaction; data has priority.
                if (d_valid && d_ready) begin
                    pending <= 1; instruction_request <= 0; write_request <= d_write;
                    address <= d_address; write_data <= d_data; write_mask <= d_mask;
                end else if (i_valid && i_ready) begin
                    pending <= 1; instruction_request <= 1; write_request <= 0;
                    address <= i_address; write_data <= 0; write_mask <= 0;
                end
            end
        end
    end
    wire visible = pending && running && !halted;
    wire [7:0] status = {1'b0,1'b1,retire_toggle,halted,
        visible && instruction_request,visible && write_request,visible,running && !halted};
    wire [31:0] debug_pc = halted ? trap_pc : last_pc;
    reg [7:0] output_data;
    always @* begin
        case (command)
            4'h1: output_data = address[7:0];
            4'h2: output_data = address[15:8];
            4'h3: output_data = address[23:16];
            4'h4: output_data = address[31:24];
            4'h5: output_data = write_data[7:0];
            4'h6: output_data = write_data[15:8];
            4'h7: output_data = write_data[23:16];
            4'h8: output_data = write_data[31:24];
            4'h9: output_data = {trap_cause[3:0],write_mask};
            4'he: output_data = debug_pc[byte_index*8 +: 8];
            4'hf: output_data = trap_value[byte_index*8 +: 8];
            default: output_data = status;
        endcase
    end
    assign uo_out = ena ? output_data : 8'h00;
    assign uio_out = 0;
    assign uio_oe = 0;
    wire _unused = &{uio_in[7:6],1'b0};
endmodule
`default_nettype wire
