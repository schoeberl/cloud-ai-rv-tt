// Copyright (c) 2026 Martin Schoeberl
// SPDX-License-Identifier: BSD-2-Clause
import chisel3._
import chisel3.util._
import _root_.circt.stage.ChiselStage
import java.nio.file.{Files, Paths}

class InstructionPort extends Bundle {
  val reqValid = Output(Bool()); val reqReady = Input(Bool())
  val address = Output(UInt(32.W))
  val respValid = Input(Bool()); val respData = Input(UInt(32.W)); val respError = Input(Bool())
}
class DataPort extends InstructionPort {
  val write = Output(Bool()); val writeData = Output(UInt(32.W)); val writeMask = Output(UInt(4.W))
}
class FetchedInstruction extends Bundle {
  val pc = UInt(32.W); val instruction = UInt(32.W); val fault = Bool()
}
class DecodedInstruction extends Bundle {
  val legal = Bool(); val writeRd = Bool(); val immediate = UInt(32.W)
  val aluOp = UInt(4.W); val useImmediate = Bool()
  val load = Bool(); val store = Bool(); val branch = Bool()
  val lui = Bool(); val auipc = Bool(); val jal = Bool(); val jalr = Bool()
  val fenceI = Bool(); val ecall = Bool(); val ebreak = Bool()
}

/** RV32I: fetch, decode/register-read/address-generation, execute/memory/writeback.
  * Wildcat ThreeCats architectural reference, independent Chisel 7 implementation.
  * Harvard request/response ports allow one outstanding request each; responses
  * arrive no earlier than the cycle after acceptance. Memory words are little-endian.
  */
class WildcatThreeStage extends Module {
  val io = IO(new Bundle {
    val imem = new InstructionPort; val dmem = new DataPort
    val halted = Output(Bool()); val trapPc = Output(UInt(32.W))
    val trapCause = Output(UInt(5.W)); val trapValue = Output(UInt(32.W))
    val retireValid = Output(Bool()); val retirePc = Output(UInt(32.W))
    val retireInstruction = Output(UInt(32.W)); val retireWrite = Output(Bool())
    val retireRd = Output(UInt(5.W)); val retireData = Output(UInt(32.W))
  })
  val halted = RegInit(false.B)
  val trapPc = RegInit(0.U(32.W)); val trapCause = RegInit(0.U(5.W)); val trapValue = RegInit(0.U(32.W))
  io.halted := halted; io.trapPc := trapPc; io.trapCause := trapCause; io.trapValue := trapValue

  val redirect = WireDefault(false.B); val target = WireDefault(0.U(32.W))
  val trapNow = WireDefault(false.B); val cause = WireDefault(0.U(5.W)); val trapData = WireDefault(0.U(32.W))
  val fetchPc = RegInit(0.U(32.W)); val fetchPending = RegInit(false.B)
  val pendingPc = RegInit(0.U(32.W)); val discardFetch = RegInit(false.B)
  // Two IF entries reserve space for an outstanding memory response during stalls.
  val queue = withReset(reset.asBool || redirect || trapNow) {
    Module(new Queue(new FetchedInstruction, 2, pipe = true))
  }

  // Decode and register read (stage 2).
  val instr = queue.io.deq.bits.instruction
  val opcode = instr(6,0); val funct3 = instr(14,12); val funct7 = instr(31,25)
  val rs1 = instr(19,15); val rs2 = instr(24,20)
  val dec = WireDefault(0.U.asTypeOf(new DecodedInstruction))
  val immI = Cat(Fill(20,instr(31)),instr(31,20))
  val immS = Cat(Fill(20,instr(31)),instr(31,25),instr(11,7))
  val immB = Cat(Fill(19,instr(31)),instr(31),instr(7),instr(30,25),instr(11,8),0.U(1.W))
  val immU = Cat(instr(31,12),0.U(12.W))
  val immJ = Cat(Fill(11,instr(31)),instr(31),instr(19,12),instr(20),instr(30,21),0.U(1.W))
  val baseAlu = MuxLookup(funct3,0.U(4.W))(Seq(
    0.U -> 0.U, 1.U -> 2.U, 2.U -> 3.U, 3.U -> 4.U,
    4.U -> 5.U, 5.U -> 6.U, 6.U -> 8.U, 7.U -> 9.U))
  switch(opcode) {
    is("h37".U) { dec.legal := true.B; dec.writeRd := true.B; dec.lui := true.B; dec.immediate := immU }
    is("h17".U) { dec.legal := true.B; dec.writeRd := true.B; dec.auipc := true.B; dec.immediate := immU }
    is("h6f".U) { dec.legal := true.B; dec.writeRd := true.B; dec.jal := true.B; dec.immediate := immJ }
    is("h67".U) { dec.legal := funct3 === 0.U; dec.writeRd := true.B; dec.jalr := true.B; dec.immediate := immI }
    is("h63".U) {
      dec.legal := funct3 === 0.U || funct3 === 1.U || funct3 >= 4.U
      dec.branch := true.B; dec.immediate := immB
    }
    is("h03".U) {
      dec.legal := funct3 === 0.U || funct3 === 1.U || funct3 === 2.U || funct3 === 4.U || funct3 === 5.U
      dec.load := true.B; dec.writeRd := true.B; dec.immediate := immI
    }
    is("h23".U) { dec.legal := funct3 <= 2.U; dec.store := true.B; dec.immediate := immS }
    is("h13".U) {
      dec.legal := true.B; dec.writeRd := true.B; dec.useImmediate := true.B
      dec.immediate := immI; dec.aluOp := baseAlu
      when(funct3 === 1.U) { dec.legal := funct7 === 0.U }
      when(funct3 === 5.U) {
        dec.legal := funct7 === 0.U || funct7 === "h20".U
        dec.aluOp := Mux(instr(30),7.U,6.U)
      }
    }
    is("h33".U) {
      dec.legal := funct7 === 0.U || (funct7 === "h20".U && (funct3 === 0.U || funct3 === 5.U))
      dec.writeRd := true.B; dec.aluOp := baseAlu
      when(funct3 === 0.U && instr(30)) { dec.aluOp := 1.U }
      when(funct3 === 5.U && instr(30)) { dec.aluOp := 7.U }
    }
    is("h0f".U) {
      dec.legal := funct3 === 0.U || funct3 === 1.U
      dec.fenceI := funct3 === 1.U // Also implements Zifencei by draining/refetching IF.
    }
    is("h73".U) {
      dec.ecall := instr === "h00000073".U; dec.ebreak := instr === "h00100073".U
      dec.legal := dec.ecall || dec.ebreak
    }
  }

  // Execute/memory/writeback stage registers.
  val xValid = RegInit(false.B)
  val xPc = Reg(UInt(32.W)); val xInstr = Reg(UInt(32.W)); val xFault = Reg(Bool())
  val xDec = Reg(new DecodedInstruction); val xA = Reg(UInt(32.W)); val xB = Reg(UInt(32.W))
  val xAddress = Reg(UInt(32.W)); val memoryStarted = RegInit(false.B)
  val rd = xInstr(11,7); val xf3 = xInstr(14,12)
  val aluB = Mux(xDec.useImmediate,xDec.immediate,xB)
  val sub = xDec.aluOp === 1.U
  val addSub = xA + (aluB ^ Fill(32,sub)) + sub.asUInt
  val alu = MuxLookup(xDec.aluOp,addSub)(Seq(
    2.U -> (xA << aluB(4,0))(31,0),
    3.U -> Cat(0.U(31.W),xA.asSInt < aluB.asSInt),
    4.U -> Cat(0.U(31.W),xA < aluB), 5.U -> (xA ^ aluB),
    6.U -> (xA >> aluB(4,0)), 7.U -> (xA.asSInt >> aluB(4,0)).asUInt,
    8.U -> (xA | aluB), 9.U -> (xA & aluB)))
  val branchTaken = MuxLookup(xf3,false.B)(Seq(
    0.U -> (xA === xB), 1.U -> (xA =/= xB),
    4.U -> (xA.asSInt < xB.asSInt), 5.U -> (xA.asSInt >= xB.asSInt),
    6.U -> (xA < xB), 7.U -> (xA >= xB)))
  val jump = xDec.jal || xDec.jalr || (xDec.branch && branchTaken)
  val jumpTarget = Mux(xDec.jalr,(xA+xDec.immediate) & "hfffffffe".U,xPc+xDec.immediate)
  val mem = xDec.load || xDec.store
  val misaligned = (xf3(1,0) === 1.U && xAddress(0)) || (xf3(1,0) === 2.U && xAddress(1,0) =/= 0.U)
  val immediateTrap = xFault || !xDec.legal || xDec.ecall || xDec.ebreak ||
    (jump && jumpTarget(1,0) =/= 0.U) || (mem && misaligned)
  val memoryDone = memoryStarted && io.dmem.respValid
  val complete = xValid && !halted && !reset.asBool && (immediateTrap || !mem || memoryDone)
  trapNow := complete && (immediateTrap || (mem && io.dmem.respError))
  when(xFault) { cause := 1.U; trapData := xPc }
    .elsewhen(!xDec.legal) { cause := 2.U; trapData := xInstr }
    .elsewhen(xDec.ecall) { cause := 11.U }
    .elsewhen(xDec.ebreak) { cause := 3.U }
    .elsewhen(jump && jumpTarget(1,0) =/= 0.U) { cause := 0.U; trapData := jumpTarget }
    .elsewhen(mem && misaligned) { cause := Mux(xDec.store,6.U,4.U); trapData := xAddress }
    .elsewhen(mem && io.dmem.respError) { cause := Mux(xDec.store,7.U,5.U); trapData := xAddress }
  redirect := complete && !trapNow && (jump || xDec.fenceI)
  target := Mux(xDec.fenceI,xPc+4.U,jumpTarget)

  io.dmem.reqValid := xValid && !halted && !reset.asBool && xDec.legal && mem && !immediateTrap && !memoryStarted
  io.dmem.address := xAddress & "hfffffffc".U
  io.dmem.write := xDec.store
  val byteShift = Cat(xAddress(1,0),0.U(3.W))
  io.dmem.writeData := (xB << byteShift)(31,0)
  val mask = MuxLookup(xf3(1,0),15.U(4.W))(Seq(0.U -> 1.U(4.W),1.U -> 3.U(4.W)))
  io.dmem.writeMask := Mux(xDec.store,(mask << xAddress(1,0))(3,0),0.U)
  val loaded = io.dmem.respData >> byteShift
  val loadResult = MuxLookup(xf3,io.dmem.respData)(Seq(
    0.U -> Cat(Fill(24,loaded(7)),loaded(7,0)),
    1.U -> Cat(Fill(16,loaded(15)),loaded(15,0)),
    4.U -> Cat(0.U(24.W),loaded(7,0)), 5.U -> Cat(0.U(16.W),loaded(15,0))))
  val result = MuxCase(alu,Seq(
    xDec.lui -> xDec.immediate, xDec.auipc -> (xPc+xDec.immediate),
    (xDec.jal || xDec.jalr) -> (xPc+4.U), xDec.load -> loadResult))
  val writeback = complete && !trapNow && xDec.writeRd && rd =/= 0.U
  // General registers are architecturally unspecified after reset; x0 is hardwired.
  val registers = Mem(32,UInt(32.W))
  when(writeback) { registers.write(rd,result) }
  def readRegister(index: UInt): UInt = Mux(index === 0.U,0.U,
    Mux(writeback && rd === index,result,registers.read(index)))
  val a = readRegister(rs1); val b = readRegister(rs2)
  val advance = queue.io.deq.valid && (!xValid || complete) && !redirect && !trapNow && !halted
  queue.io.deq.ready := (!xValid || complete) && !redirect && !trapNow && !halted
  when(complete) { xValid := false.B; memoryStarted := false.B }
  when(io.dmem.reqValid && io.dmem.reqReady) { memoryStarted := true.B }
  when(advance) {
    xValid := true.B; xPc := queue.io.deq.bits.pc; xInstr := instr; xFault := queue.io.deq.bits.fault
    xDec := dec; xA := a; xB := b; xAddress := a + dec.immediate
    memoryStarted := false.B
  }
  when(trapNow) {
    halted := true.B; trapPc := xPc; trapCause := cause; trapValue := trapData
    xValid := false.B; memoryStarted := false.B
  }

  // Stage 1: PC/fetch and a two-entry F/D queue, with stale-response suppression.
  val reservations = queue.io.count +& fetchPending.asUInt
  io.imem.reqValid := !halted && !reset.asBool && !redirect && !trapNow &&
    (!fetchPending || io.imem.respValid) && (reservations < 2.U || queue.io.deq.fire)
  io.imem.address := fetchPc
  queue.io.enq.valid := fetchPending && io.imem.respValid && !discardFetch && !redirect && !trapNow && !halted
  queue.io.enq.bits.pc := pendingPc; queue.io.enq.bits.instruction := io.imem.respData
  queue.io.enq.bits.fault := io.imem.respError
  when(fetchPending && io.imem.respValid) { fetchPending := false.B; discardFetch := false.B }
  when(io.imem.reqValid && io.imem.reqReady) {
    fetchPending := true.B; pendingPc := fetchPc; fetchPc := fetchPc+4.U; discardFetch := false.B
  }
  when(redirect) {
    fetchPc := target
    discardFetch := fetchPending && !io.imem.respValid
  }
  when(trapNow) { discardFetch := true.B }
  io.retireValid := complete && !trapNow
  io.retirePc := xPc; io.retireInstruction := xInstr
  io.retireWrite := writeback; io.retireRd := rd; io.retireData := result
}

object GenerateTinyTapeout extends App {
  val rtl = ChiselStage.emitSystemVerilog(new WildcatThreeStage,
    firtoolOpts=Array("-disable-all-randomization","-strip-debug-info",
      "--default-layer-specialization=disable","--lowering-options=disallowLocalVariables,disallowPackedArrays"))
  Files.writeString(Paths.get("src/WildcatThreeStage.sv"),
    "// Generated from src/main/scala/WildcatThreeStage.scala; do not edit.\n"+rtl.stripTrailing()+"\n")
}
