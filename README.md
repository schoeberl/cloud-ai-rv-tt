# cloud-ai-rv-tt — three-stage RV32I processor

A Chisel RV32I processor for Tiny Tapeout SKY26d, with a three-stage pipeline inspired by Martin Schoeberl's [Wildcat ThreeCats](https://github.com/schoeberl/wildcat/blob/3594f0d49b873bdc54116a4017cf3f97ecf4fd11/src/main/scala/wildcat/pipeline/ThreeCats.scala). This is an independent Chisel 7 implementation of the pipeline organization, rather than a vendored copy of Wildcat. The previous standalone ALU examples and tests have been removed; they remain in Git history.

## Processor

```text
PC / instruction fetch -> decode / register read / address generation -> execute / memory / writeback
     two-entry IF queue             writeback bypass                       variable-latency stalls
```

- All RV32I integer instructions: arithmetic, logic, shifts, comparisons, LUI/AUIPC, JAL/JALR, all six branches, five loads, three stores, FENCE, ECALL and EBREAK.
- Also implements FENCE.I (Zifencei) by flushing/refetching the instruction stream.
- Full 32-register integer register file; x0 is hardwired to zero. Other registers are unspecified after reset and must be initialized by software.
- Same-cycle writeback-to-decode forwarding, including load-use, store-address/data and branch dependencies.
- In-order issue/retirement, branch/jump flushing and suppression of stale speculative fetch responses.
- One outstanding request per Harvard memory port, with request backpressure and arbitrary response waits. The TT wrapper multiplexes them onto a host-served byte interface.
- Aligned little-endian 32-bit instruction/data addresses and byte write strobes. Misaligned halfword/word accesses raise precise exceptions; byte accesses are unrestricted.
- Exceptions halt the core and expose cause, PC and value to the host monitor. No privileged ISA, interrupt controller, CSR instructions, M/A/C/F/D extensions, on-chip program/data RAM, or operating-system environment is included. This is a processor core with a monitor execution environment, not a complete autonomous SoC.

At reset PC=0. With one-cycle instruction responses, no data stalls and straight-line code, the pipeline can retire one instruction per cycle. The TT byte protocol substantially limits delivered instruction bandwidth; the CPU stalls safely until the host supplies memory responses.

## Tiny Tapeout

| Field | Value |
|---|---|
| Title | Wildcat-style RV32I CPU |
| Author | Martin Schoeberl |
| Top module | `tt_um_schoeberl_rv32i` |
| Shuttle | SKY26d / SKY130 |
| Declared footprint | 6x2 tiles (12 tiles), increased after the 4x2 placement failure |
| Operating clock target | 10 MHz |
| Program/data memory | External host, via the byte protocol |

[Pin protocol and datasheet](docs/info.md) · [Metadata](info.yaml) · [Builds and tests](https://github.com/schoeberl/cloud-ai-rv-tt/actions)

**Submission status:** the processor replaces the previous ALU submission candidate. Processor RTL tests, Chisel consistency and datasheet generation pass. The first CPU physical run failed during diode insertion because the 4x2 floorplan was too crowded; a 6x2 physical run is required to validate the revised footprint. Check the linked Actions results for the current status. Previous ALU acceptance checks and Fmax estimates do not validate this CPU. Website registration remains postponed and has not been completed.

## Build and test

Requirements: x86-64 Linux, Git, curl, network access, and either Nix with flakes enabled or support for nix-portable's bubblewrap runtime. The bootstrap downloads pinned tools and requires several GB of disk space.

```sh
git clone https://github.com/schoeberl/cloud-ai-rv-tt.git
cd cloud-ai-rv-tt
./tools/bootstrap
python3 -m venv .venv-tt
.venv-tt/bin/pip install -r test/requirements.txt
make test
```

```sh
./tools/dev     # Interactive Nix shell
make rtl        # Regenerate src/WildcatThreeStage.sv from Chisel
make core-test  # Differential execution, trace, pipeline and fault tests
make tt-test    # Complete processor execution through public TT pins
```

The checked-in generated RTL lets Tiny Tapeout build without installing Scala. CI regenerates it to detect drift, runs both processor test suites, generates the datasheet, and executes the SKY26d GDS, gate-level simulation and precheck workflows. The optional layout viewer is enabled with `ENABLE_LAYOUT_VIEWER=true` after configuring GitHub Pages.

The independent Python model checks retired PC/instruction, destination register/value, stores and exceptions. A 367-instruction program covers all base integer instruction groups, forwarding, taken/untaken/backward branches, byte lanes, self-modifying code with FENCE.I, and seeded random arithmetic/memory instructions. Core tests run it under three memory timing profiles; the fast profile reaches 193 consecutive one-per-cycle retirements. Separate fault programs check illegal encodings, alignment, bus errors, ECALL/EBREAK, load faults targeting x0, and suppression of speculative faults and younger stores. Pin-level tests also check host-request stability, disable handling and reset cancellation. These are functional regression tests, not a claim of official RISC-V architectural certification.

## External memory host

Use `ui_in` for response bytes, `uio_in` for commands, and `uo_out` for request/status readback. All bidirectional pins remain inputs. START releases the CPU from reset; the host then services each instruction or data request until the CPU traps. No fixed ROM limits the program, and all 32 address bits are transported. The host must provide the program/data memory and acknowledge stores exactly once.

See [docs/info.md](docs/info.md) for the complete protocol and [software/](software/) for a small RV32I demonstration and host-service example.

## Repository layout

| Path | Purpose |
|---|---|
| `src/main/scala/WildcatThreeStage.scala` | Processor and generated-RTL entry point |
| `src/WildcatThreeStage.sv` | Submitted Chisel-generated core |
| `src/tt_um_schoeberl_rv32i.v` | TT monitor and external-memory bridge |
| `tests/` | Independent instruction model and core differential tests |
| `test/` | TT pin-level RTL/gate-level tests |
| `software/` | Demo program and generic memory-host service |
| `info.yaml`, `docs/info.md` | Submission metadata and datasheet |
| `src/config.json` | SKY26d physical configuration, 100 ns clock target |
| `nix/`, `tools/` | Reproducible development environment and launchers |

Tool versions: Chisel 7.16.0, Scala 2.13.18, sbt 1.10.7, Java 21, LibreLane 3.0.16 in the local Nix environment. The shuttle workflow uses the versions selected by `TinyTapeout/tt-gds-action@ttsky26d`. PDKs, downloaded tools and generated runs are excluded from Git. Original project code is BSD-2-Clause; adapted Tiny Tapeout scaffolding retains its Apache-2.0 notice.
