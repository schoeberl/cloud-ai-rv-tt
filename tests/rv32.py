"""Independent RV32I instruction encoder/reference model; no RTL imports."""
from dataclasses import dataclass
import random
MASK = 0xffffffff

def sx(value, bits):
    value &= (1 << bits)-1
    return value-(1 << bits) if value & (1 << (bits-1)) else value

def i(op, rd, f3, rs1, imm):
    return ((imm&4095)<<20)|(rs1<<15)|(f3<<12)|(rd<<7)|op

def r(rd, f3, rs1, rs2, f7=0):
    return (f7<<25)|(rs2<<20)|(rs1<<15)|(f3<<12)|(rd<<7)|0x33

def s(f3, rs1, rs2, imm=0):
    return (((imm>>5)&127)<<25)|(rs2<<20)|(rs1<<15)|(f3<<12)|((imm&31)<<7)|0x23

def b(f3, rs1, rs2, offset):
    return (((offset>>12)&1)<<31)|(((offset>>5)&63)<<25)|(rs2<<20)|(rs1<<15)|(f3<<12)|(((offset>>1)&15)<<8)|(((offset>>11)&1)<<7)|0x63

def j(rd, offset):
    return (((offset>>20)&1)<<31)|(((offset>>1)&1023)<<21)|(((offset>>11)&1)<<20)|(((offset>>12)&255)<<12)|(rd<<7)|0x6f

def u(op, rd, value):
    return (value&0xfffff000)|(rd<<7)|op

def load_imm(rd, value):
    value &= MASK
    upper = (value+0x800)&0xfffff000
    return [u(0x37, rd, upper), i(0x13, rd, 0, rd, sx(value&4095,12))]

class Trap(Exception):
    def __init__(self, cause, pc, value=0):
        self.cause,self.pc,self.value = cause,pc,value&MASK
        super().__init__(f'trap {cause} at {pc:08x}, value={self.value:08x}')

class Reference:
    def __init__(self, words, instruction_errors=(), data_errors=()):
        self.reg=[0]*32;self.pc=0;self.memory={};self.stores=[]
        self.instruction_errors=set(instruction_errors);self.data_errors=set(data_errors)
        for n,w in enumerate(words): self.put_word(n*4,w)
        self.put_word(0x4000,0x80ff7f01)
    def put_word(self,address,value):
        for n in range(4): self.memory[(address+n)&MASK]=(value>>(8*n))&255
    def word(self,address):
        return sum(self.memory.get((address+n)&MASK,0)<<(8*n) for n in range(4))
    def step(self):
        pc=self.pc
        if pc in self.instruction_errors:raise Trap(1,pc,pc)
        ins=self.word(pc);op=ins&127;rd=(ins>>7)&31;f3=(ins>>12)&7
        a=self.reg[(ins>>15)&31];v=self.reg[(ins>>20)&31];f7=ins>>25
        imm=sx(ins>>20,12);result=None;nxt=(pc+4)&MASK
        def illegal():raise Trap(2,pc,ins)
        if op==0x37:result=ins&0xfffff000
        elif op==0x17:result=pc+(ins&0xfffff000)
        elif op==0x6f:
            off=sx(((ins>>31)<<20)|(((ins>>12)&255)<<12)|(((ins>>20)&1)<<11)|(((ins>>21)&1023)<<1),21)
            nxt=(pc+off)&MASK;result=pc+4
            if nxt&3:raise Trap(0,pc,nxt)
        elif op==0x67:
            if f3:illegal()
            nxt=(a+imm)&0xfffffffe;result=pc+4
            if nxt&3:raise Trap(0,pc,nxt)
        elif op==0x63:
            tests={0:a==v,1:a!=v,4:sx(a,32)<sx(v,32),5:sx(a,32)>=sx(v,32),6:a<v,7:a>=v}
            if f3 not in tests:illegal()
            off=sx(((ins>>31)<<12)|(((ins>>7)&1)<<11)|(((ins>>25)&63)<<5)|(((ins>>8)&15)<<1),13)
            if tests[f3]:
                nxt=(pc+off)&MASK
                if nxt&3:raise Trap(0,pc,nxt)
        elif op in [0x03,0x23]:
            store=op==0x23
            if (store and f3 not in [0,1,2]) or (not store and f3 not in [0,1,2,4,5]):illegal()
            if store:imm=sx(((ins>>25)<<5)|((ins>>7)&31),12)
            addr=(a+imm)&MASK;size=1<<(f3&3)
            if addr&(size-1):raise Trap(6 if store else 4,pc,addr)
            aligned=addr&~3
            if aligned in self.data_errors:raise Trap(7 if store else 5,pc,addr)
            if store:
                mask=((1<<size)-1)<<(addr&3);data=(v<<(8*(addr&3)))&MASK
                self.stores.append((aligned,data,mask))
                for n in range(size):self.memory[(addr+n)&MASK]=(v>>(8*n))&255
            else:
                val=sum(self.memory.get((addr+n)&MASK,0)<<(8*n) for n in range(size))
                result=sx(val,size*8) if f3<4 else val
        elif op in [0x13,0x33]:
            immediate=op==0x13
            v=(imm&MASK) if immediate else v
            if immediate:
                if f3==1 and f7!=0:illegal()
                if f3==5 and f7 not in [0,0x20]:illegal()
            elif not (f7==0 or (f7==0x20 and f3 in [0,5])):illegal()
            sh=v&31
            if f3==0:result=a-v if not immediate and f7==0x20 else a+v
            elif f3==1:result=a<<sh
            elif f3==2:result=int(sx(a,32)<sx(v,32))
            elif f3==3:result=int(a<v)
            elif f3==4:result=a^v
            elif f3==5:result=sx(a,32)>>sh if f7==0x20 else a>>sh
            elif f3==6:result=a|v
            elif f3==7:result=a&v
        elif op==0x0f:
            if f3 not in [0,1]:illegal()
        elif op==0x73:
            if ins==0x73:raise Trap(11,pc)
            if ins==0x100073:raise Trap(3,pc)
            illegal()
        else:illegal()
        write=result is not None and rd!=0
        value=(result or 0)&MASK
        if write:self.reg[rd]=value
        self.reg[0]=0;self.pc=nxt
        return pc,ins,write,rd,value


def program():
    p=[i(0x13,n,0,0,n) for n in range(1,32)]
    p += load_imm(20,0x4000)+load_imm(1,MASK)+load_imm(2,0x80000000)
    p += [i(0x13,0,0,0,99),i(0x13,3,0,0,31)]
    for f3 in range(8):
        p.append(r(4,f3,2,3))
        if f3 in [0,5]:p.append(r(5,f3,2,3,0x20))
        imm=31 if f3 in [1,5] else -17
        p.append(i(0x13,6,f3,1,imm))
        if f3==5:p.append(i(0x13,7,5,2,0x400|31))
    p += [u(0x17,8,0x12345000)]
    p += load_imm(9,0x8001)
    p += [s(0,20,1,1),s(1,20,9,2)]
    for f3,off in [(0,1),(4,1),(1,2),(5,2),(2,0)]:p.append(i(3,10,f3,20,off))
    p += [i(0x13,11,0,10,1),s(2,20,11,4),i(3,12,2,20,4),r(13,0,12,11)]
    # Taken branches skip a poison illegal instruction. Untaken branches must retire the ADDI.
    for f3,rs1,rs2 in [(0,1,1),(1,1,0),(4,1,0),(5,0,1),(6,0,1),(7,1,0)]:
        p += [b(f3,rs1,rs2,12),s(2,20,0,144),0,i(0x13,14,0,14,1)]
    for f3,rs1,rs2 in [(0,1,0),(1,1,1),(4,0,1),(5,1,0),(6,1,0),(7,0,1)]:
        p += [b(f3,rs1,rs2,8),i(0x13,14,0,14,1),i(0x13,15,0,14,1)]
    p += [i(0x13,16,0,0,5),i(0x13,16,0,16,-1),b(1,16,0,-4)]
    p += [j(17,8),0,i(0x13,18,0,17,1)]
    pc=len(p)*4
    p += [i(0x13,6,0,0,(pc+12)|1),i(0x67,7,0,6,0),0,i(0x13,8,0,7,1)]
    p += [0x0ff0000f] # FENCE
    target=len(p)*4+24
    p += load_imm(21,target)+load_imm(22,i(0x13,29,0,0,42))
    p += [s(2,21,22),0x100f,i(0x13,29,0,0,0)] # self-modifying code + FENCE.I
    rng=random.Random(0x33525649)
    regs=[n for n in range(1,32) if n!=20]
    for _ in range(192):
        rd=rng.choice(regs);a=rng.randrange(32);v=rng.randrange(32);f=rng.randrange(8)
        if rng.randrange(2):
            f7=0x20 if f in [0,5] and rng.randrange(2) else 0
            p.append(r(rd,f,a,v,f7))
        else:
            imm=rng.randrange(32) if f in [1,5] else rng.randrange(-2048,2048)
            if f==5 and rng.randrange(2):imm|=0x400
            p.append(i(0x13,rd,f,a,imm))
    for _ in range(48):
        if rng.randrange(2):
            f=rng.randrange(3);off=rng.randrange(128)&~((1<<f)-1)
            p.append(s(f,20,rng.randrange(32),off))
        else:
            f=rng.choice([0,1,2,4,5]);off=rng.randrange(128)&~((1<<(f&3))-1)
            p.append(i(3,rng.choice(regs),f,20,off))
    p += [s(2,20,29,128),0x100073]
    return p


def trap_cases():
    cases=[('illegal',[0],(),()),('ecall',[0x73],(),()),('ebreak',[0x100073],(),()),
      ('M-extension',[r(1,0,0,0,1)],(),()),('bad-shift',[i(0x13,1,1,0,64)],(),()),
      ('bad-load',[i(3,1,3,0,0)],(),()),('bad-store',[s(3,0,0)],(),()),
      ('bad-branch',[b(2,0,0,4)],(),()),('bad-jalr',[i(0x67,1,1,0,0)],(),()),
      ('CSR-not-implemented',[0x30001073],(),()),('jal-alignment',[j(1,2)],(),()),
      ('jalr-alignment',[i(0x67,1,0,0,3)],(),()),('branch-alignment',[b(0,0,0,2)],(),()),
      ('lw-alignment',[i(3,0,2,0,1)],(),()),('lh-alignment',[i(3,1,1,0,1)],(),()),
      ('sw-alignment',[s(2,0,0,2)],(),()),('sh-alignment',[s(1,0,0,1)],(),()),
      ('instruction-fault',[j(0,0x100)],(0x100,),()),
      ('load-fault',[i(3,0,2,0,0)],(),(0,)),
      ('load-fault-flush-store',[i(3,1,2,0,0),s(2,0,0,4)],(),(0,)),('store-fault',[s(2,0,0)],(),(0,)),
      ('discard-speculative-fault',[j(0,16),0,0,0,0x100073],(4,),()),
      ('untaken-misaligned-branch',[b(1,0,0,2),0x100073],(),())]
    return cases


def demo_program():
    from pathlib import Path
    return [int(line,16) for line in (Path(__file__).resolve().parents[1]/'software/demo.hex').read_text().splitlines() if line.strip()]
