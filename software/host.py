"""Transport-neutral Tiny Tapeout memory monitor.

Provide a `pins` adapter with synchronous methods:
  read(command, index=0) -> byte: set UIO and sample UO after settling, no edge
  tick(command=0, data=0, index=0): drive UIO/UI, then one rising clock edge
The adapter must assert ena, configure UIO as inputs to the chip, and implement
clock setup/hold timing. No particular demo-board firmware API is assumed here.
"""
class MemoryHost:
    def __init__(self, pins, words, error_for=None):
        self.pins=pins
        self.memory={}
        self.error_for=error_for or (lambda address,instruction,write:False)
        for index,word in enumerate(words):
            for byte in range(4):self.memory[index*4+byte]=(word>>(8*byte))&255

    def word(self,address):
        return sum(self.memory.get((address+n)&0xffffffff,0)<<(8*n) for n in range(4))

    def read_word(self,command,indexed=False):
        return sum(self.pins.read(command if indexed else command+n,n if indexed else 0)<<(8*n) for n in range(4))

    def start(self):
        self.pins.tick(0xd)
        self.pins.tick(0xc)
        self.pins.tick()

    def service(self):
        status=self.pins.read(0)
        if status&0x10:
            return dict(cause=self.pins.read(9)>>4,pc=self.read_word(0xe,True),value=self.read_word(0xf,True))
        if not status&2:
            self.pins.tick()
            return None
        address=self.read_word(1)
        instruction=bool(status&8);write=bool(status&4)
        error=self.error_for(address,instruction,write)
        if write and not error:
            data=self.read_word(5);mask=self.pins.read(9)&15
            for byte in range(4):
                if mask&(1<<byte):self.memory[(address+byte)&0xffffffff]=(data>>(8*byte))&255
        if not write:
            data=self.word(address)
            for byte in range(4):self.pins.tick(0xa,(data>>(8*byte))&255,byte)
        self.pins.tick(0xb,int(error))
        self.pins.tick()
        return None

    def run(self,limit=100000):
        self.start()
        for _ in range(limit):
            trap=self.service()
            if trap is not None:return trap
        raise TimeoutError('Processor did not halt within host service limit')
