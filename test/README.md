# Processor tests

Install cocotb once from the repository root:

```sh
python3 -m venv .venv-tt
.venv-tt/bin/pip install -r test/requirements.txt
make test
```

- `tests/rv32.py`: independent RV32I instruction encoder and execution reference.
- `tests/test_core.py`: compares every retired PC/instruction/register write, stores and traps. Exercises one-cycle fetches, request backpressure, variable memory latency, bypassing, flushes, and precise exceptions.
- `test/test.py`: serves instruction and data memory through Tiny Tapeout pins and compares final memory, store stream, and trap state. Also checks disabled commands and reset cancellation.

`make core-test` and `make tt-test` run them separately. Tiny Tapeout's `gl_test` action runs the same pin-level test with the hardened gate-level netlist and PDK cell models. General registers are not reset; programs initialize registers before use. The old ALU tests have been removed.
