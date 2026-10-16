# cloude-ai-rv-tt

A Chisel and LibreLane hardware development project using Nix, with an 8-bit counter and two registered 32-bit RISC-V ALU implementations. The ALUs explore timing and implementation tradeoffs in the open SKY130 high-density standard-cell library.

This is an ALU benchmark, not a complete RISC-V processor or a Tiny Tapeout submission.

## Quick start

Requirements: x86-64 Linux, Git, curl, and either Nix with flakes enabled or support for unprivileged user namespaces and bubblewrap. Allow several GB of disk space and network access for the EDA tools and SKY130 PDK.

```sh
git clone https://github.com/schoeberl/cloude-ai-rv-tt.git
cd cloude-ai-rv-tt
./tools/bootstrap
make alu-test
make alu-fast-test
```

`tools/bootstrap` uses an installed Nix or downloads a checksum-verified nix-portable v012. It also downloads the pinned sbt launcher. `./tools/dev` enters the development shell; the shell includes Java, LibreLane, Yosys, OpenROAD, Magic, KLayout, Icarus Verilog, and Verilator.

```sh
./tools/dev          # Interactive Nix development shell
make rtl             # Generate counter SystemVerilog
make gds             # Run counter implementation
make alu-gds         # Test and implement the baseline ALU
make alu-fast-gds    # Test and implement the revised ALU
```

LibreLane automatically downloads its compatible SKY130 PDK on the first implementation run. Runs are saved beneath each design's `librelane/.../runs/` directory. Final GDS and other views are in the run's `final/` directory. GUI tools require a display setup.

## ALU operations and pipeline

Both ALUs implement ADD, SUB, SLL, SLT, SLTU, XOR, SRL, SRA, OR, and AND, plus COPY_B for LUI and addition with bit zero cleared for JALR. Registered equality, signed-less-than, and unsigned-less-than flags support branch comparisons. Register/immediate forms share the same datapath; instruction decoding, immediate formation, PC selection, memory, and the register file are external.

```text
Operands + operation + valid
            |
      Input registers
            |
   Combinational 32-bit ALU
            |
      Output registers
            |
    Result + flags + valid
```

A request sampled at rising edge N appears at the outputs immediately after edge N+1. Both designs accept one request per cycle, with synchronous active-high reset and no stalls. The revised version registers decoded controls and uses parallel result selection while retaining all operations and the same latency.

See the [ALU documentation](librelane/alu/README.md) for opcode values, constraints, critical paths, and reproduction commands.

## Measured results

Both ALUs passed 22,308 simulation cycles against an independent Python reference model and completed the LibreLane Classic physical flow with zero Magic/KLayout DRC, LVS, and antenna errors.

| Register-to-register timing estimate | Baseline | Revised |
|---|---:|---:|
| Worst corner: slow cells, 1.60 V, 100 C, maximum RC | 86.3 MHz | 108.0 MHz |
| Nominal corner: typical cells, 1.80 V, 25 C, nominal RC | 168.8 MHz | 216.1 MHz |
| Worst-corner minimum period | 11.5841 ns | 9.2572 ns |
| Sequential cells | 105 | 113 |

The revised ALU improves worst-corner Fmax by about 25% without removing functionality. Extracted timing rechecks bracketed the baseline limit between 11.5 and 11.6 ns and the revised limit between 9.2 and 9.3 ns.

Both layouts used a 20 ns implementation target on a 250 x 250 micrometer die, with 0.25 ns clock uncertainty, propagated post-CTS clocks, extracted parasitics, and fixed I/O budgets. The register-only estimates include setup time and clock skew. No additional OCV derate was applied, and synchronous reset was held inactive for normal-operation timing.

**Slew and capacitance violations remain at slow corners.** These results are provisional performance estimates rather than complete electrical signoff or silicon measurements. Implementation at a tighter target may produce different results.

The baseline critical path runs from opcode control through SUB decode, arithmetic carry logic, and result selection to result bit 31. The revised critical path moves to SLL control through the shared barrel shifter and result logic to result bit 0. Detailed measurements are retained in [results/alu-comparison.json](results/alu-comparison.json).

## Project layout

| Path | Contents |
|---|---|
| `src/main/scala/` | Counter, baseline ALU, revised ALU, and RTL generators |
| `tests/` | Independent Python reference vectors and SystemVerilog testbench |
| `librelane/` | Physical implementation configurations and timing constraints |
| `scripts/` | Timing report extraction and clock-period rechecks |
| `nix/` | Development shell and locked Nix inputs |
| `tools/` | Bootstrap, Nix, sbt, and LibreLane launchers |
| `results/` | Small retained measurement summaries |

Tool caches, PDKs, generated RTL, and physical runs are excluded from Git. Recreate them using the commands above.

## Pinned tools

- LibreLane 3.0.16
- Chisel 7.16.0 and Scala 2.13.18
- sbt 1.10.7 and Java 21
- Chisel-resolved CIRCT firtool 1.160.0
- SKY130 PDK revision `8afc8346a57fe1ab7934ba5a6056ea8b43078e71`

`nix/flake.lock` pins LibreLane, nix-eda, Nixpkgs, and their Nix dependencies. The launchers configure the official FOSSi signed binary cache and preserve proxy/CA settings. For a standard Nix installation, `nix develop ./nix` also opens the shell after enabling flakes and configuring that cache. Managed containers may require expanded execution permissions for the Nix namespace runtime.
