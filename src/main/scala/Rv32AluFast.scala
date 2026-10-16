import chisel3._
import chisel3.util._
import _root_.circt.stage.ChiselStage
import java.nio.file.{Files, Paths}

/** Operand/immediate selection and instruction decoding are performed upstream. */

/** Input registers -> one combinational ALU stage -> output registers.
  * Accepts one transaction per cycle. A request sampled at edge N appears at
  * the outputs immediately after edge N+1. No stalls or ready handshake.
  */
class Rv32AluFast extends Module {
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
  // Decode before the input boundary so high-fanout control is registered.
  val selected = RegInit(VecInit(Seq.fill(12)(false.B)))
  selected := VecInit((0 until 12).map(i => io.op === i.U))
  val valid = RegNext(io.validIn, false.B)

  // Shared 32-bit adder/subtractor; overflow wraps modulo 2^32.
  val subtract = selected(AluOp.SUB)
  val sum = a + (b ^ Fill(32, subtract)) + subtract.asUInt
  val eq = a === b
  val lt = a.asSInt < b.asSInt
  val ltu = a < b

  // A shared barrel shifter. Reversal implements left shift using right shift.
  val left = selected(AluOp.SLL)
  val shiftInput = Mux(left, Reverse(a), a)
  val sign = selected(AluOp.SRA) && a(31)
  val shifted = (Cat(sign, shiftInput).asSInt >> b(4, 0)).asUInt
  val shiftResult = Mux(left, Reverse(shifted(31, 0)), shifted(31, 0))

  // Parallel one-hot selection avoids a priority chain after the datapaths.
  val addSelected = selected(AluOp.ADD) || selected(AluOp.SUB) || selected(AluOp.JALR)
  val shiftSelected = selected(AluOp.SLL) || selected(AluOp.SRL) || selected(AluOp.SRA)
  val sumResult = Cat(sum(31, 1), sum(0) && !selected(AluOp.JALR))
  val result = Mux1H(Seq(
    addSelected -> sumResult,
    shiftSelected -> shiftResult,
    selected(AluOp.SLT) -> Cat(0.U(31.W), lt),
    selected(AluOp.SLTU) -> Cat(0.U(31.W), ltu),
    selected(AluOp.XOR) -> (a ^ b),
    selected(AluOp.OR) -> (a | b),
    selected(AluOp.AND) -> (a & b),
    selected(AluOp.COPY_B) -> b
  ))

  io.result := RegNext(result, 0.U(32.W))
  io.equal := RegNext(eq, false.B)
  io.lessSigned := RegNext(lt, false.B)
  io.lessUnsigned := RegNext(ltu, false.B)
  io.validOut := RegNext(valid, false.B)
}

object GenerateAluFast extends App {
  val rtl = ChiselStage.emitSystemVerilog(new Rv32AluFast,
    firtoolOpts = Array("-disable-all-randomization", "-strip-debug-info",
      "--default-layer-specialization=disable",
      "--lowering-options=disallowLocalVariables,disallowPackedArrays"))
  Files.createDirectories(Paths.get("build/rtl"))
  Files.writeString(Paths.get("build/rtl/Rv32AluFast.sv"), rtl)
}
