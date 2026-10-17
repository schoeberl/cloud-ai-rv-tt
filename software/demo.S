# RV32I, little-endian, linked at address 0. No runtime or privileged CSRs.
.section .text
.globl _start
_start:
    lui  x1, 0x4          # result address = 0x4000
    addi x2, x0, 0        # sum
    addi x3, x0, 10       # counter
loop:
    add  x2, x2, x3
    addi x3, x3, -1
    bne  x3, x0, loop
    sw   x2, 0(x1)        # store 55
    ebreak                # monitor halts at PC 0x1c, cause 3
