import chisel3._
import circt.stage.ChiselStage
import java.nio.file.{Files, Paths}
class Counter extends Module {
  val io = IO(new Bundle {
    val enable = Input(Bool())
    val count = Output(UInt(8.W))
  })
  val count = RegInit(0.U(8.W))
  when(io.enable) { count := count + 1.U }
  io.count := count
}
object Generate extends App {
  val rtl = ChiselStage.emitSystemVerilog(new Counter,
    firtoolOpts = Array("-disable-all-randomization", "-strip-debug-info", "--default-layer-specialization=disable"))
  Files.createDirectories(Paths.get("build/rtl"))
  Files.writeString(Paths.get("build/rtl/Counter.sv"), rtl)
}
