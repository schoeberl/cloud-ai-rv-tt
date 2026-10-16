import chisel3._
import chisel3.util._
import _root_.circt.stage.ChiselStage
import java.nio.file.{Files, Paths}

/** Operand/immediate selection and instruction decoding are performed upstream. */
object AluOp {
  val ADD = 0; val SUB = 1; val SLL = 2; val SLT = 3; val SLTU = 4
  val XOR = 5; val SRL = 6; val SRA = 7; val OR = 8; val AND = 9
  val COPY_B = 10; val JALR = 11
}

/** Input registers -> one combinational ALU stage -> output registers.
  * Accepts one transaction per cycle. A request sampled at edge N appears at
  * the outputs immediately after edge N+1. No stalls or ready handshake.
  */
class Rv32Alu extends Module {
  val io = IO(new Bundle {
    val a = Input(UInt(32.W))
    val b = Input(UInt(32.W))
    val op = Input(UInt(4.W))
    val validIn = Input(Bool())
    val result = Output(UInt(32.W))
    val equal = Output(Bool())
    val lessSigned = Output(Bool())
    val lessUnsigned = Output(Bool())
    val validOut = Output(Bool())
  })

  val a = RegInit(0.U(32.W))
  a := io.a
  val b = RegInit(0.U(32.W))
  b := io.b
  val op = RegInit(0.U(4.W))
  op := io.op
  val valid = RegNext(io.validIn, false.B)

  // Shared 32-bit adder/subtractor; overflow wraps modulo 2^32.
  val subtract = op === AluOp.SUB.U
  val sum = a + (b ^ Fill(32, subtract)) + subtract.asUInt
  val eq = a === b
  val lt = a.asSInt < b.asSInt
  val ltu = a < b

  // A shared barrel shifter. Reversal implements left shift using right shift.
  val left = op === AluOp.SLL.U
  val shiftInput = Mux(left, Reverse(a), a)
  val sign = op === AluOp.SRA.U && a(31)
  val shifted = (Cat(sign, shiftInput).asSInt >> b(4, 0)).asUInt
  val shiftResult = Mux(left, Reverse(shifted(31, 0)), shifted(31, 0))

  val result = WireDefault(0.U(32.W))
  switch(op) {
    is(AluOp.ADD.U)    { result := sum }
    is(AluOp.SUB.U)    { result := sum }
    is(AluOp.SLL.U)    { result := shiftResult }
    is(AluOp.SLT.U)    { result := lt.asUInt }
    is(AluOp.SLTU.U)   { result := ltu.asUInt }
    is(AluOp.XOR.U)    { result := a ^ b }
    is(AluOp.SRL.U)    { result := shiftResult }
    is(AluOp.SRA.U)    { result := shiftResult }
    is(AluOp.OR.U)     { result := a | b }
    is(AluOp.AND.U)    { result := a & b }
    is(AluOp.COPY_B.U) { result := b }
    is(AluOp.JALR.U)   { result := Cat(sum(31, 1), 0.U(1.W)) }
  }

  io.result := RegNext(result, 0.U(32.W))
  io.equal := RegNext(eq, false.B)
  io.lessSigned := RegNext(lt, false.B)
  io.lessUnsigned := RegNext(ltu, false.B)
  io.validOut := RegNext(valid, false.B)
}

object GenerateAlu extends App {
  val rtl = ChiselStage.emitSystemVerilog(new Rv32Alu,
    firtoolOpts = Array("-disable-all-randomization", "-strip-debug-info",
      "--default-layer-specialization=disable",
      "--lowering-options=disallowLocalVariables,disallowPackedArrays"))
  Files.createDirectories(Paths.get("build/rtl"))
  Files.writeString(Paths.get("build/rtl/Rv32Alu.sv"), rtl)
}
