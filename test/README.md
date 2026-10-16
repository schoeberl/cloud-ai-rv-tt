# Tiny Tapeout pin-level tests

`test.py` drives only public Tiny Tapeout pins and runs with RTL or the gate-level netlist. It covers all operations, boundary values, shifts 0-63, 256 seeded random transactions, byte ordering, status, reset, CLEAR, busy writes, and disable behavior.

Local setup from the repository root:

```sh
python3 -m venv .venv-tt
.venv-tt/bin/pip install -r test/requirements.txt
make tt-test
```

`make tt-test` uses the existing Nix shell for Icarus and the local virtual environment for cocotb. Generate the submitted RTL with `make tt-rtl`. Tiny Tapeout's gate-level workflow supplies the extracted netlist and PDK cell models automatically.
