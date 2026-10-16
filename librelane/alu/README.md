# Registered RV32I ALU benchmark

The Chisel source is `src/main/scala/Rv32Alu.scala`. The counter example and its flow are preserved separately.

## Interface and pipeline

`io_a` and `io_b` are 32-bit operands, `io_op` selects an operation, and `io_validIn` marks a request. Input operands, operation and valid are registered. The combinational ALU feeds registered result, comparison flags and valid. A request sampled at rising edge N appears at the outputs immediately after edge N+1. Throughput is one request per cycle; there is no stall or ready signal. All registers use synchronous active-high reset. Payload outputs can change when valid is false.

```text
(a, b, op, validIn) -> input registers -> ALU -> output registers -> (result, flags, validOut)
```

The ALU has a shared ADD/SUB datapath and a shared barrel shifter. Shifts use only operand B's low five bits. Arithmetic wraps modulo 2^32. Comparison results are zero-extended to 32 bits. The flags `equal`, `lessSigned`, and `lessUnsigned` compare the registered A and B independently of the selected operation and are aligned with the registered result.

| io_op | Operation | RV32I use |
|---|---|---|
| 0 | ADD | ADD, ADDI; load/store effective addresses; AUIPC; PC-relative targets and link addresses |
| 1 | SUB | SUB |
| 2 | SLL | SLL, SLLI |
| 3 | SLT | SLT, SLTI |
| 4 | SLTU | SLTU, SLTIU |
| 5 | XOR | XOR, XORI |
| 6 | SRL | SRL, SRLI |
| 7 | SRA | SRA, SRAI |
| 8 | OR | OR, ORI |
| 9 | AND | AND, ANDI |
| 10 | COPY_B | LUI with the already shifted U-immediate |
| 11 | JALR | (A + B) with bit 0 cleared |
| 12–15 | Reserved | Deterministic zero result |

BEQ/BNE use `equal`/its inverse, BLT/BGE use `lessSigned`/its inverse, and BLTU/BGEU use `lessUnsigned`/its inverse. Instruction decode, sign extension and immediate formation, PC/operand selection, the register file, memory and control flow are outside this ALU. This is a datapath benchmark rather than a complete RV32I processor. Multiplication/division belong to the M extension and are not included.

## Reproduce

From the repository root:

```sh
make alu-test       # Generate RTL and simulate against an independent Python model
make alu-synth      # Test, then SKY130 synthesis
make alu-gds        # Test, then the complete Classic flow
make alu-timing ALU_RUN=librelane/alu/runs/alu-20ns
```

`tests/alu_vectors.py` generates 22,308 cycles of directed boundary values and deterministic random tests, all 16 opcodes, arithmetic overflow, sign comparisons, shift masking, pipeline transactions, valid bubbles, and mid-stream reset. Icarus checks the generated RTL against the expected output on every cycle.

`config.json` uses `sky130A` / `sky130_fd_sc_hd`, a 250 x 250 micrometer die, a 20 ns initial target, and explicit implementation/signoff SDC. I/O delays are fixed at 2 ns maximum and 0.2 ns minimum, input transition is 0.15 ns, output load is 0.033442 pF, and clock uncertainty is 0.25 ns. Normal-operation analysis holds synchronous reset inactive. No additional OCV timing derate is specified. LibreLane handles ideal clocks before CTS and propagated clocks for extracted analysis.

`scripts/alu_timing.py` reads the post-route STA reports for all nine process/voltage/temperature and RC combinations. It selects only flip-flop-to-flip-flop paths, then computes `Tmin = period - worst_setup_slack` and `Fmax_MHz = 1000/Tmin`. Cell setup time, extracted wiring, clock skew, and the clock uncertainty are included. The slowest corner is the estimate for this placed-and-routed netlist. Port timing and synchronous reset assertion are excluded from that register-only estimate. The extracted design must also be rechecked at periods around the predicted limit; this does not re-optimize the placement or routing for a faster clock.

## Baseline results

Run: `librelane/alu/runs/alu-20ns`. RTL simulation passed all 22,308 test cycles. The complete physical flow passed DRC, LVS and antenna checks. Slow-corner slew and capacitance warnings remain, so setup/hold closure alone is not full electrical signoff.

| Corner | Register-only minimum period | Estimated Fmax |
|---|---:|---:|
| Maximum RC, slow cells, 1.60 V, 100 C | 11.5841 ns | 86.325 MHz |
| Nominal RC, typical cells, 1.80 V, 25 C | 5.9255 ns | 168.762 MHz |
| Maximum RC, fast cells, 1.95 V, -40 C | 3.7510 ns | 266.595 MHz |

The baseline limit was rechecked with extracted STA: at 11.6 ns the worst register setup slack is +0.015891 ns, while at 11.5 ns it is -0.084109 ns. These are timing rechecks of the same layout, not additional physical implementations.

The worst path starts at the registered opcode bit `op[0]` and ends at the output register for `io_result[31]`. It passes through SUB decode, high-fanout control buffering, operand-B inversion, the adder carry logic, and the result-selection network. Approximately 3.2 ns is spent launching/decoding/distributing control, 5.3 ns in the arithmetic path, and 2.5 ns in final selection. It does not traverse the barrel shifter.

To repeat the boundary checks with new run directories:

```sh
./tools/dev python3 scripts/alu_sweep.py librelane/alu/runs/alu-20ns 11.6 11.5
```

The timing sweep stops after STA and deliberately does not use the complete-flow setup/hold checkers; assess the reported slacks, not just the command exit code.

## Timing-focused variant

`src/main/scala/Rv32AluFast.scala` preserves the operation set, flags, and pipeline contract. It registers decoded one-hot controls and replaces priority result selection with parallel one-hot selection. The independent reference tests are reused through the `ALU_DUT` testbench parameter.

```sh
make alu-fast-test
make alu-fast-gds
make alu-timing ALU_RUN=librelane/alu-fast/runs/alu-fast-20ns
```

The tradeoff is additional control flip-flops and potentially larger control fanout, rather than dropped instructions or an extra pipeline stage. It moves instruction decode ahead of the input timing boundary; comparisons with the baseline therefore measure this registered interface and not a complete CPU execute stage including decode.

### Measured comparison

Both layouts used the same 20 ns implementation target and identical die, PDK, I/O constraints and clock uncertainty. Both passed all 22,308 simulation cycles, Magic/KLayout DRC, LVS, antenna checks, and setup/hold at the implementation target.

| Metric | Baseline | Predecoded, parallel selection |
|---|---:|---:|
| Worst-corner register Fmax estimate | 86.325 MHz | 108.024 MHz |
| Nominal-corner register Fmax estimate | 168.762 MHz | 216.080 MHz |
| Worst register minimum period | 11.5841 ns | 9.2572 ns |
| Sequential cells | 105 | 113 |
| Standard-cell area, including physical support cells | 14,218.6 um² | 14,059.7 um² |
| Worst-corner maximum slew violations | 118 | 66 |
| Worst-corner maximum capacitance violations | 3 | 2 |

The revised variant improves worst-corner Fmax by 25.1% without removing an operation or adding latency. Its boundary check gives +0.042835 ns register setup slack at 9.3 ns (107.527 MHz) and -0.057165 ns at 9.2 ns (108.696 MHz). All register hold slacks remain positive. This remains a timing estimate because the electrical violations above are not closed.

The revised critical path is `selected_2` (registered SLL control) through the shared barrel shifter/result logic to `io_result[0]`. Its launch register drives 64 loads and roughly 0.308 pF, with 1.35 ns output slew at the slowest corner. A hold-repair delay cell also contributes about 1.12 ns on this path. Further work should address control fanout and clock/hold repair, then consider separate left/right shifters or an extra pipeline stage. Removing shift functionality would require software emulation or a multi-cycle shifter to retain RV32I behavior.

```sh
./tools/dev python3 scripts/alu_sweep.py \
  librelane/alu-fast/runs/alu-fast-20ns 9.3 9.2 \
  --config librelane/alu-fast/config.json
```

Detailed timing summaries are in `build/alu-timing.json` and `build/alu-fast-timing.json`. Logs are `build/alu-flow.log`, `build/alu-fast-flow.log`, `build/alu-sweep.log`, and `build/alu-fast-sweep.log`. Layouts are under each run's `final/gds/` directory. These are baseline implementations, not an exhaustive search for SKY130's performance limit; a tighter implementation target and different datapath/clock architectures may improve the result.
