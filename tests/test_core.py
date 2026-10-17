import random
import cocotb
from cocotb.triggers import Timer
from rv32 import Reference, Trap, program, trap_cases, demo_program

@cocotb.test()
async def processor_differential(d):
    for label,words,ifault,dfault in [('demo',demo_program(),(),()),('fast-program',program(),(),()),('wait-program',program(),(),()),('long-wait-program',program(),(),()),*trap_cases()]:
        ref=Reference(words,ifault,dfault);hw=Reference(words,ifault,dfault)
        d.clock.value=0;d.reset.value=1;d.ir.value=0;d.dr.value=0
        d.iv.value=0;d.dv.value=0;d.ie.value=0;d.de.value=0;d.idata.value=0;d.ddata.value=0
        for _ in range(3):
            await Timer(5,unit='ns');d.clock.value=1;await Timer(5,unit='ns');d.clock.value=0
        d.reset.value=0
        rng=random.Random(341);ip=None;dp=None;retired=0;held_i=None;held_d=None;consecutive=0;longest=0
        for cycle in range(15000):
            d.clock.value=0
            # The main program uses one-cycle instruction responses and random data waits.
            # Other cases add request backpressure and instruction response latency.
            d.ir.value=int(label=='fast-program' or rng.randrange(4)!=0)
            d.dr.value=int(rng.randrange(4)!=0)
            iresponse=ip is not None and ip[0]==cycle
            dresponse=dp is not None and dp[0]==cycle
            d.iv.value=int(iresponse);d.dv.value=int(dresponse)
            if iresponse:d.idata.value=ip[1];d.ie.value=ip[2]
            if dresponse:d.ddata.value=dp[1];d.de.value=dp[2]
            await Timer(5,unit='ns')
            if int(d.halted.value):
                try:ref.step()
                except Trap as t:
                    assert int(d.cause.value)==t.cause,(label,'cause',int(d.cause.value),t)
                    assert int(d.tpc.value)==t.pc,(label,'trap pc',t)
                    assert int(d.tval.value)==t.value,(label,'trap value',t)
                else:raise AssertionError((label,'unexpected halt',ref.pc))
                assert hw.stores==ref.stores,(label,'store side effects')
                break
            if int(d.rv.value):
                expected=ref.step()
                actual=(int(d.pc.value),int(d.ins.value),bool(int(d.rw.value)),int(d.rd.value),int(d.data.value) if int(d.rw.value) else 0)
                assert actual[:3]==expected[:3],(label,cycle,actual,expected)
                if expected[2]:assert actual[3:]==expected[3:],(label,cycle,actual,expected)
                retired+=1;consecutive+=1;longest=max(longest,consecutive)
            else:consecutive=0
            # Responses release the outstanding slot before accepting a new request.
            if iresponse:ip=None
            if dresponse:dp=None
            if int(d.iq.value):
                payload=int(d.ia.value)
                if held_i is not None:assert payload==held_i
                if int(d.ir.value):
                    assert ip is None
                    delay=1 if label=='fast-program' else rng.randrange(1,18 if label=='long-wait-program' else 5)
                    ip=(cycle+delay,hw.word(payload),int(payload in ifault));held_i=None
                else:held_i=payload
            else:held_i=None # Redirects may cancel an unaccepted speculative fetch.
            if int(d.dq.value):
                payload=(int(d.da.value),int(d.wd.value),int(d.mask.value),int(d.dw.value))
                if held_d is not None:assert payload==held_d
                if int(d.dr.value):
                    assert dp is None
                    addr,data,mask,write=payload;error=addr in dfault
                    if write and not error:
                        hw.stores.append((addr,data,mask))
                        for n in range(4):
                            if mask&(1<<n):hw.memory[addr+n]=(data>>(8*n))&255
                    dp=(cycle+rng.randrange(1,21 if label=='long-wait-program' else 7),hw.word(addr),int(error));held_d=None
                else:held_d=payload
            else:held_d=None
            d.clock.value=1
            await Timer(5,unit='ns')
        else:raise AssertionError((label,'processor timeout',ref.pc))
        if label=='fast-program':assert longest>=20, ('Pipeline did not reach one instruction per cycle',longest)
        d._log.info('%s: %d retired instructions, %d cycles, peak %d consecutive retires',label,retired,cycle,longest)
