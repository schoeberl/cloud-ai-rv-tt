# Copyright (c) 2026 Martin Schoeberl
# SPDX-License-Identifier: BSD-2-Clause
"""Pin-level tests shared by Tiny Tapeout RTL and gate-level workflows."""
import random
import cocotb
from cocotb.triggers import Timer

MASK = 0xFFFFFFFF

def signed(value):
    return value if value < 0x80000000 else value - 0x100000000

def model(a, b, op):
    shift = b & 31
    operations = {
        0: lambda: a + b, 1: lambda: a - b, 2: lambda: a << shift,
        3: lambda: int(signed(a) < signed(b)), 4: lambda: int(a < b),
        5: lambda: a ^ b, 6: lambda: a >> shift, 7: lambda: signed(a) >> shift,
        8: lambda: a | b, 9: lambda: a & b, 10: lambda: b,
        11: lambda: (a + b) & ~1,
    }
    value = operations.get(op, lambda: 0)() & MASK
    flags = int(a == b) | (int(signed(a) < signed(b)) << 1) | (int(a < b) << 2)
    return value, flags

async def cycle(dut, command=0, data=0, opcode=0, enabled=True):
    dut.clk.value = 0
    dut.ena.value = int(enabled)
    dut.ui_in.value = data
    dut.uio_in.value = (opcode << 4) | command
    await Timer(50, unit="ns")
    dut.clk.value = 1
    await Timer(50, unit="ns")
    assert int(dut.uio_oe.value) == 0, "Host control pins must never be driven"
    assert int(dut.uio_out.value) == 0
    return int(dut.uo_out.value)

async def reset(dut):
    dut.rst_n.value = 0
    for _ in range(3):
        await cycle(dut)
    dut.rst_n.value = 1
    status = await cycle(dut)
    assert status == 0x80

async def read_result(dut):
    result = 0
    for index in range(4):
        dut.uio_in.value = 0xA + index
        await Timer(10, unit="ns")
        result |= int(dut.uo_out.value) << (8 * index)
    dut.uio_in.value = 0xE
    await Timer(10, unit="ns")
    return result, int(dut.uo_out.value)

async def transaction(dut, a, b, op):
    for index in range(4):
        await cycle(dut, 1 + index, (a >> (8 * index)) & 255)
        await cycle(dut, 5 + index, (b >> (8 * index)) & 255)
    status = await cycle(dut, 9, opcode=op)
    assert status & 0x18 == 0x08, "Execute must set busy and clear done"
    status = await cycle(dut)
    assert status & 0x18 == 0x08, "Result must not appear early"
    status = await cycle(dut)
    assert status & 0x18 == 0x10, "Result must complete two cycles after execute"
    result, status = await read_result(dut)
    expected, flags = model(a, b, op)
    assert result == expected, f"op={op} A={a:08x} B={b:08x}: {result:08x} != {expected:08x}"
    assert status == 0x90 | flags | (0x20 if op >= 12 else 0)

@cocotb.test()
async def test_alu_protocol(dut):
    await reset(dut)
    boundary = [0, 1, 31, 32, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFE, MASK]
    cases = [(a, b) for a, b in zip(boundary, reversed(boundary))]
    cases += [(0, 0), (MASK, MASK), (0x80000000, 0x80000000), (0x7FFFFFFF, 1)]
    for op in range(16):
        for a, b in cases:
            await transaction(dut, a, b, op)
    for op in [2, 6, 7]:
        for shift in range(64):
            await transaction(dut, 0x80000001, shift, op)
    rng = random.Random(0x54545256)
    for _ in range(256):
        await transaction(dut, rng.getrandbits(32), rng.getrandbits(32), rng.randrange(16))

    # Writes and EXEC are ignored while disabled; outputs are quiet.
    await transaction(dut, 0x12345678, 9, 0)
    assert await cycle(dut, 1, 255, enabled=False) == 0
    assert await cycle(dut, 9, opcode=1, enabled=False) == 0
    await cycle(dut, 9, opcode=0)
    # An attempted operand write while busy must be ignored.
    await cycle(dut, 1, 255)
    await cycle(dut)
    value, _ = await read_result(dut)
    assert value == 0x12345681

    # CLEAR cancels an in-flight request and clears operands/status/result.
    await cycle(dut, 9, opcode=1)
    assert await cycle(dut, 15) == 0x80
    await cycle(dut)
    await cycle(dut)
    value, status = await read_result(dut)
    assert value == 0 and status == 0x80
    await cycle(dut, 9, opcode=0)
    await cycle(dut)
    await cycle(dut)
    value, status = await read_result(dut)
    assert value == 0 and status == 0x91
    # External reset must also cancel an in-flight transaction.
    await cycle(dut, 9, opcode=2)
    await reset(dut)
    await cycle(dut)
    value, status = await read_result(dut)
    assert value == 0 and status == 0x80
