`default_nettype none
`timescale 1ns/1ps
module core_tb;
  reg clock, reset;
  reg ir, iv, ie, dr, dv, de;
  reg [31:0] idata, ddata;
  wire iq, dq, dw, halted, rv, rw;
  wire [31:0] ia, da, wd, pc, ins, data, tpc, tval;
  wire [3:0] mask;
  wire [4:0] rd, cause;
  WildcatThreeStage cpu (
    .clock(clock),.reset(reset),
    .io_imem_reqValid(iq),.io_imem_reqReady(ir),.io_imem_address(ia),
    .io_imem_respValid(iv),.io_imem_respData(idata),.io_imem_respError(ie),
    .io_dmem_reqValid(dq),.io_dmem_reqReady(dr),.io_dmem_address(da),
    .io_dmem_write(dw),.io_dmem_writeData(wd),.io_dmem_writeMask(mask),
    .io_dmem_respValid(dv),.io_dmem_respData(ddata),.io_dmem_respError(de),
    .io_halted(halted),.io_trapPc(tpc),.io_trapCause(cause),.io_trapValue(tval),
    .io_retireValid(rv),.io_retirePc(pc),.io_retireInstruction(ins),
    .io_retireWrite(rw),.io_retireRd(rd),.io_retireData(data));
endmodule
