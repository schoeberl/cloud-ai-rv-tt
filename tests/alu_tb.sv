`timescale 1ns/1ps
`ifndef ALU_DUT
`define ALU_DUT Rv32Alu
`endif
module alu_tb;
  reg clock = 0;
  always #5 clock = ~clock;
  reg reset;
  reg [31:0] a, b;
  reg [3:0] op;
  reg validIn;
  wire [31:0] result;
  wire equal, lessSigned, lessUnsigned, validOut;
  `ALU_DUT dut(.clock(clock), .reset(reset), .io_a(a), .io_b(b), .io_op(op),
    .io_validIn(validIn), .io_result(result), .io_equal(equal),
    .io_lessSigned(lessSigned), .io_lessUnsigned(lessUnsigned), .io_validOut(validOut));
  integer fd, fields, cycle = 0;
  reg [31:0] expectedResult;
  reg expectedEqual, expectedSigned, expectedUnsigned, expectedValid;
  initial begin
    fd = $fopen("build/alu-vectors.hex", "r");
    if (fd == 0) $fatal(1, "Cannot open test vectors");
    while (!$feof(fd)) begin
      @(negedge clock);
      fields = $fscanf(fd, "%h %h %h %h %h %h %h %h %h %h\n",
        reset, a, b, op, validIn, expectedResult, expectedEqual,
        expectedSigned, expectedUnsigned, expectedValid);
      if (fields != 10) $fatal(1, "Malformed vector at cycle %0d", cycle);
      @(posedge clock); #1;
      if ({result,equal,lessSigned,lessUnsigned,validOut} !==
          {expectedResult,expectedEqual,expectedSigned,expectedUnsigned,expectedValid})
        $fatal(1, "Mismatch cycle %0d: got %h %b%b%b %b, expected %h %b%b%b %b",
          cycle,result,equal,lessSigned,lessUnsigned,validOut,
          expectedResult,expectedEqual,expectedSigned,expectedUnsigned,expectedValid);
      cycle = cycle + 1;
    end
    $fclose(fd);
    $display("PASS: %0d cycles, all ALU operations, comparison flags, pipeline latency and reset",cycle);
    $finish;
  end
endmodule
