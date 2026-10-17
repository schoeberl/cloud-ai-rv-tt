## How it works

This is a 32-bit RV32I processor written in Chisel. Its three-stage pipeline follows the organization of Wildcat ThreeCats:

1. **Fetch:** PC generation and variable-latency instruction requests, with a two-entry instruction queue.
2. **Decode:** instruction decoding, register-file reads and memory address calculation, with forwarding from writeback.
3. **Execute:** arithmetic, branches, memory access and in-order writeback. Memory operations stall until acknowledged.

The processor implements the full base integer instruction set: LUI/AUIPC; JAL/JALR; BEQ/BNE/BLT/BGE/BLTU/BGEU; LB/LH/LW/LBU/LHU; SB/SH/SW; register/immediate arithmetic, logic, comparisons and shifts; FENCE; ECALL; and EBREAK. FENCE.I is additionally implemented by flushing and refetching. JALR clears target bit zero. Shift amounts use five bits; arithmetic wraps modulo 2^32. x0 is always zero, while x1-x31 are unspecified after reset. Fetch starts at byte address zero.

Taken branches and jumps discard younger instructions and pending wrong-path fetch responses. Loads and stores are aligned and little-endian, with byte write enables. Data waits block younger execution. ECALL, EBREAK, illegal instructions, misalignment and external memory errors cause a precise halt, with no writeback or memory request for a faulting illegal/misaligned instruction. A host monitor reads the cause, faulting PC and trap value, then resets/restarts the core if desired. Privileged CSRs, interrupts and M/A/C/F/D extensions are not included.

The CPU has separate instruction and data interfaces internally. To fit Tiny Tapeout's pins, a bridge presents one host-served memory transaction at a time, prioritizing data over instruction fetch. All program and data storage is external. The 10 MHz operating target does not imply one instruction per cycle over this byte interface; host response bandwidth determines execution speed. The declared footprint is 4x2 tiles, subject to the new CPU's physical checks.

### Pin interface

| Pins | Direction | Meaning |
|---|---|---|
| ui_in[7:0] | Input | Memory response byte, or ACK error bit 0 |
| uio_in[3:0] | Input | Command |
| uio_in[5:4] | Input | Byte index for response/debug access |
| uio_in[7:6] | Input | Unused, drive zero |
| uo_out[7:0] | Output | Status, request or debug byte |
| uio_out / uio_oe | Output | Always zero; never drive host control pins |
| clk | Input | Clock, target 10 MHz |
| rst_n | Input | Active-low synchronous reset, hold for at least two rising edges |
| ena | Input | Host command/output enable; outputs are zero while low |

Commands that change state are sampled on rising edges. Read commands are combinational and need only settling time. Keep host data/control stable around clock edges. `ena` gates commands and output visibility; it does not clock-gate a running CPU, which may progress to its next memory wait.

### Commands

| Command (hex) | Action |
|---|---|
| 0 | Read status |
| 1,2,3,4 | Read current request address bytes 0,1,2,3 |
| 5,6,7,8 | Read current store data bytes 0,1,2,3 |
| 9 | Read `{trap_cause[3:0], write_mask[3:0]}` |
| A | Write response byte selected by `uio_in[5:4]`, data from ui_in |
| B | ACK pending request; ui_in[0]=1 reports a memory error |
| C | START: release CPU from reset at PC=0 |
| D | RESET: stop CPU and cancel pending transactions; START needed again |
| E | Read debug PC byte selected by `uio_in[5:4]` |
| F | Read trap-value byte selected by `uio_in[5:4]` |

Byte 0 is the least significant byte. While idle, the CPU is held in reset. START has no additional effect once running. RESET cancels outstanding memory requests and resets pipeline/debug state; general-register contents are not cleared. Debug PC is the last retired PC during execution and the faulting PC after a trap. Request address/data/mask are latched and remain stable until ACK. Read their values only when request-valid is set.

### Status byte

| Bit | Meaning |
|---|---|
| 7 | Zero |
| 6 | Signature one |
| 5 | Toggles on each retired instruction |
| 4 | Trap/halted |
| 3 | Current valid request is an instruction fetch |
| 2 | Current valid request is a store |
| 1 | Request valid |
| 0 | CPU running, not halted |

After reset status is `0x40`. Completed requests disappear after ACK; repeated ACKs without a pending request are ignored. Do not hold ACK while servicing a newly arriving request. No instruction/data request is externally visible after halt. A speculative instruction request may be served even though the CPU later discards its response.

### Memory service procedure

1. Load a program into the host's memory image at address zero. Initialize any registers the program uses.
2. Issue START for one rising edge, then NOP.
3. Poll status until request-valid or trap is set.
4. Read address bytes using commands 1-4. The exported address is always word-aligned and retains all 32 bits.
5. For instruction fetch or load, read a little-endian 32-bit word from host memory and write all four response bytes with command A and byte indices 0-3.
6. For a store, read commands 5-8 and the low nibble of command 9. Update only the memory byte lanes selected by the mask. Acknowledge once; no read data is needed for a store.
7. Issue ACK with error bit zero. To report an access fault, set ui_in[0]=1 and do not apply the store. The CPU distinguishes instruction, load and store faults.
8. Repeat until trap. Read cause, debug PC and trap value. RESET is required to leave the halted state.

A reply must follow an accepted request. A host can take any number of cycles to respond. A synchronous FPGA can implement the protocol at 10 MHz; a slower microcontroller can manually clock the design or service requests with long waits. There is no on-chip instruction/data RAM and no autonomous execution without the host.

### Trap causes

| Cause | Meaning | Trap value |
|---|---|---|
| 0 | Instruction target misaligned | Target address |
| 1 | Instruction access fault | Fetch address |
| 2 | Illegal instruction | Instruction word |
| 3 | EBREAK | Zero |
| 4 | Load address misaligned | Effective byte address |
| 5 | Load access fault | Effective byte address |
| 6 | Store address misaligned | Effective byte address |
| 7 | Store access fault | Effective byte address |
| 11 | ECALL (monitor execution environment) | Zero |

These causes are monitor outputs, not a claim of implemented machine-mode trap CSRs or privileged execution. Untaken branches do not fault on an unused misaligned target. Loads to x0 still perform memory access and can fault.

## How to test

The checked-in `software/demo.hex` adds the integers 1 through 10, stores 55 at byte address `0x4000`, and executes EBREAK. Serve its instructions and data through the protocol above. On completion the trap cause is 3, debug PC is 0x1c and host memory at 0x4000 contains 0x00000037.

`make core-test` checks the core's retired-instruction stream against an independent RV32I model under fast, delayed and heavily stalled memory. `make tt-test` serves memory through public pins, checking stores, resulting memory and precise traps. The pin suite is also used for the post-layout gate-level simulation. Fault programs exercise invalid instructions, misalignment, bus faults, ECALL/EBREAK, speculative fetch faults and younger-store suppression. RTL tests do not constitute official ISA certification or physical signoff.

The previous ALU's Fmax and passing GDS checks do not apply to this processor. The CPU must pass its own GDS, gate-level simulation and precheck workflows.

## External hardware

A Tiny Tapeout demo board and a microcontroller/FPGA memory host are required. Drive the eight UI and eight UIO inputs and sample the eight UO outputs; the bidirectional pins are always configured as inputs. The host supplies the clock or synchronizes its commands with it, stores the program/data image and acknowledges memory transactions. Use the board's specified I/O voltage, typically 3.3 V. No external UART or SPI memory controller is built into this design.
