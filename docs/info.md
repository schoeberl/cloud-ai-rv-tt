## How it works

This project is a 32-bit RV32I arithmetic/logic unit written in Chisel and wrapped in a byte-wide Tiny Tapeout interface. It implements ADD, SUB, SLL, SLT, SLTU, XOR, SRL, SRA, OR and AND, plus COPY_B for LUI and JALR address calculation. Equality, signed-less-than and unsigned-less-than flags support branch comparisons. It is an ALU rather than a complete processor; instruction decoding and memory are external.

The core has registered inputs and outputs. The host loads two 32-bit operands one byte at a time, starts an operation, then reads a snapshotted result. The interface runs at 10 MHz. The declared footprint is 2x2 tiles for SKY26d; the shuttle's GDS and precheck workflows determine physical acceptance. Earlier standalone benchmark Fmax numbers do not establish this wrapper's signoff timing.

### Pin interface

- `ui_in[7:0]`: operand byte to write.
- `uio_in[3:0]`: command, sampled on the rising clock edge for writes and execution.
- `uio_in[7:4]`: operation code, sampled only with EXEC.
- `uo_out[7:0]`: selected result byte or status.
- `uio_out` and `uio_oe`: always zero. All bidirectional pins are used as inputs.
- `rst_n`: active-low synchronous reset; keep low for at least two rising clock edges.
- `ena`: enable host commands and output visibility. When low, output pins read zero and writes/EXEC are ignored. A previously launched operation can finish internally.

### Commands

| Command (hex) | Action |
|---|---|
| 0 | NOP; read status |
| 1, 2, 3, 4 | Write A bytes 0, 1, 2, 3 respectively |
| 5, 6, 7, 8 | Write B bytes 0, 1, 2, 3 respectively |
| 9 | EXEC using opcode from `uio_in[7:4]` |
| A, B, C, D | Read result bytes 0, 1, 2, 3 respectively |
| E | Read status |
| F | CLEAR operands, result, flags, and pending operation |

Byte 0 is bits 7:0; byte 3 is bits 31:24. Read commands are combinational and do not require a clock edge. Writes and EXEC are ignored while busy. CLEAR remains accepted while busy and cancels the operation. Keep control/data stable around each rising edge and issue EXEC for exactly one cycle, followed by NOP. Holding EXEC high can start another operation once the current operation completes.

### Opcodes

| Opcode (hex) | Operation |
|---|---|
| 0 | ADD, modulo 2^32 |
| 1 | SUB, modulo 2^32 |
| 2 | SLL |
| 3 | SLT, signed |
| 4 | SLTU, unsigned |
| 5 | XOR |
| 6 | SRL |
| 7 | SRA |
| 8 | OR |
| 9 | AND |
| A | COPY_B (LUI datapath) |
| B | JALR: `(A + B) & 0xfffffffe` |
| C-F | Reserved: zero result and invalid-op status |

Shift amounts use B[4:0]. Comparison flags always describe A versus B, independent of opcode. LUI requires the host to form the already shifted U-immediate; immediate instructions otherwise use the same datapath as register instructions.

### Status byte

| Bit | Meaning |
|---|---|
| 7:6 | Signature `10` |
| 5 | Last launched opcode was reserved |
| 4 | Done (sticky until next EXEC, CLEAR or reset) |
| 3 | Busy |
| 2 | A < B, unsigned |
| 1 | A < B, signed |
| 0 | A == B |

Status is returned for all commands except A-D. On reset it is `0x80`. EXEC at rising edge N sets busy immediately. The result snapshot and done flag update just after rising edge N+2. Until then, result bytes and flags retain the previous completed transaction. A new EXEC may be accepted at edge N+3.

## How to test

To compute `0x12345678 + 9`:

1. Assert reset low for two clock edges, then release it.
2. Write A using commands 1-4 and data bytes `78, 56, 34, 12` (hex).
3. Write B using commands 5-8 and data bytes `09, 00, 00, 00`.
4. Drive `uio_in = 0x09` for one rising edge: opcode ADD (0), command EXEC (9).
5. Drive NOP and supply two rising edges; status should have done=1 and busy=0.
6. Select read commands A-D. Output bytes should be `81, 56, 34, 12`.

The cocotb suite in `test/test.py` exercises every opcode, reserved opcodes, signed boundaries, shift masking, byte order, valid latency, busy write rejection, disable handling, reset and CLEAR. The same suite is used for RTL and gate-level simulations. GitHub Actions build the layout, run Tiny Tapeout precheck, generate this datasheet and run both simulation modes.

## External hardware

A Tiny Tapeout demo board or any controller capable of synchronous 3.3 V GPIO is sufficient. Configure all eight bidirectional pins as controller outputs. A microcontroller or FPGA can drive the byte protocol; no external arithmetic hardware is required. Obey the demo board's I/O voltage and setup/hold requirements.
