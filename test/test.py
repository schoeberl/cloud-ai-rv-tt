# Copyright (c) 2026 Martin Schoeberl
# SPDX-License-Identifier: BSD-2-Clause
"""Tiny Tapeout pin-level processor test and external-memory host model."""
import random
import sys
from pathlib import Path
import cocotb
from cocotb.triggers import Timer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from rv32 import Reference, Trap, program, trap_cases, demo_program

async def tick(d,cmd=0,data=0,index=0,enabled=True):
    d.clk.value=0;d.ena.value=int(enabled);d.ui_in.value=data
    d.uio_in.value=(index<<4)|cmd
    await Timer(50,unit='ns');d.clk.value=1;await Timer(50,unit='ns')
    assert int(d.uio_oe.value)==0 and int(d.uio_out.value)==0
    if not enabled:assert int(d.uo_out.value)==0
    return int(d.uo_out.value)

async def read(d,cmd,index=0):
    d.uio_in.value=(index<<4)|cmd
    await Timer(10,unit='ns')
    return int(d.uo_out.value)

async def read_word(d,first):
    return sum([(await read(d,first+n))<<(8*n) for n in range(4)])

async def debug_word(d,cmd):
    return sum([(await read(d,cmd,n))<<(8*n) for n in range(4)])

async def reset(d):
    d.rst_n.value=0
    for _ in range(3):await tick(d)
    d.rst_n.value=1
    assert await tick(d)==0x40

@cocotb.test()
async def processor_over_tt_pins(d):
    for label,words,ifault,dfault in [('demo',demo_program(),(),()),('program',program(),(),()),*trap_cases()]:
        memory=Reference(words,ifault,dfault)
        expected_trap=None
        reference=Reference(words,ifault,dfault)
        retired=0
        for _ in range(10000):
            try:reference.step();retired+=1
            except Trap as trap:
                expected_trap=(trap.cause,trap.pc,trap.value)
                break
        assert expected_trap is not None, 'Reference program did not terminate'
        await reset(d)
        assert await tick(d,0xc,enabled=False)==0
        assert await tick(d)==0x40, 'START ignored while unselected'
        await tick(d,0xc)
        rng=random.Random(33);requests=0
        for _ in range(30000):
            status=await read(d,0)
            if status&0x10:
                cause=(await read(d,9))>>4
                pc=await debug_word(d,0xe);value=await debug_word(d,0xf)
                assert (cause,pc,value)==expected_trap,(label,(cause,pc,value),expected_trap)
                assert memory.stores==reference.stores,(label,'store stream mismatch')
                for address in reference.memory:
                    assert memory.memory.get(address,0)==reference.memory[address],(label,'memory mismatch',address)
                d._log.info('%s: %d retired instructions in reference, %d host requests',label,retired,requests)
                break
            if not status&2:
                await tick(d);continue
            address=await read_word(d,1)
            is_instruction=bool(status&8);is_write=bool(status&4)
            assert address&3==0
            if requests==0:
                # Disabled ACK cannot consume a pending request.
                await tick(d,0xb,enabled=False)
                await tick(d)
                assert await read(d,0)&2
                assert await read_word(d,1)==address
            for _ in range(rng.randrange(3)):
                await tick(d)
                assert await read_word(d,1)==address,'Request must remain stable until ACK'
            error=address in (ifault if is_instruction else dfault)
            if is_write:
                assert not is_instruction
                data=await read_word(d,5);mask=(await read(d,9))&15
                if not error:
                    memory.stores.append((address,data,mask))
                    for byte in range(4):
                        if mask&(1<<byte):memory.memory[address+byte]=(data>>(8*byte))&255
            data=memory.word(address)
            if not is_write:
                for byte in range(4):await tick(d,0xa,(data>>(8*byte))&255,byte)
            await tick(d,0xb,int(error))
            await tick(d)
            requests+=1
        else:raise AssertionError((label,'host service timeout'))
        assert await tick(d,0xd)==0x40,'RESET returns to monitor without START'

    # Reset also cancels an outstanding instruction request, without ACK.
    await tick(d,0xc)
    for _ in range(10):
        if await tick(d)&2:break
    else:raise AssertionError('No initial fetch request')
    assert await tick(d,0xd)==0x40
    for _ in range(4):assert await tick(d)==0x40
