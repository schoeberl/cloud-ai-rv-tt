# Processor demonstration

`demo.S` is a standalone RV32I program linked at address zero. `demo.hex` contains its eight 32-bit instruction words, one word per line. It initializes the registers it uses, adds 1 through 10, stores 55 at byte address `0x4000`, and halts with EBREAK at PC `0x1c`. The hex file is already encoded; no cross-compiler is needed to run it.

`host.py` provides a transport-neutral `MemoryHost`. Supply a hardware adapter with `read(command,index)` and `tick(command,data,index)` methods as described in its docstring. It is not a ready-made driver for a particular board firmware. A microcontroller can manually clock the chip while servicing memory; an FPGA can synchronize the protocol at the target clock.

```python
from host import MemoryHost
words = [int(line, 16) for line in open('demo.hex') if line.strip()]
monitor = MemoryHost(pins, words)  # pins is your board-specific GPIO adapter
trap = monitor.run()
assert trap == {'cause': 3, 'pc': 0x1c, 'value': 0}
assert monitor.word(0x4000) == 55
```

The monitor's memory dictionary is the program/data memory. There is no on-chip RAM, ROM, bootloader, UART or QSPI engine. Uninitialized host memory reads as zero. An optional `error_for(address,instruction,write)` callback can report unmapped/protected addresses as faults. Before a new run, RESET cancels pending transactions; register-file contents other than x0 are unspecified after reset.
