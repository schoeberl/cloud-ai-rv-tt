.PHONY: dev rtl synth gds smoke
dev:
	./tools/dev
rtl:
	./tools/dev ./tools/sbt 'runMain Generate'
synth: rtl
	./tools/librelane --to Yosys.Synthesis librelane/config.json
gds: rtl
	./tools/librelane librelane/config.json
smoke:
	./tools/librelane --smoke-test

.PHONY: alu-rtl alu-test alu-synth alu-gds
alu-rtl:
	./tools/dev ./tools/sbt 'runMain GenerateAlu'
alu-test: alu-rtl
	./tools/dev bash -e -c 'python3 tests/alu_vectors.py; iverilog -g2012 -s alu_tb -o build/alu-test.vvp build/rtl/Rv32Alu.sv tests/alu_tb.sv; vvp build/alu-test.vvp'
alu-synth: alu-test
	./tools/librelane --to Yosys.Synthesis librelane/alu/config.json
alu-gds: alu-test
	./tools/librelane librelane/alu/config.json

ALU_RUN ?= librelane/alu/runs/alu-20ns
.PHONY: alu-timing
alu-timing:
	./tools/dev python3 scripts/alu_timing.py $(ALU_RUN)

.PHONY: alu-fast-rtl alu-fast-test alu-fast-gds
alu-fast-rtl:
	./tools/dev ./tools/sbt 'runMain GenerateAluFast'
alu-fast-test: alu-fast-rtl
	./tools/dev bash -e -c 'python3 tests/alu_vectors.py; iverilog -g2012 -DALU_DUT=Rv32AluFast -s alu_tb -o build/alu-fast-test.vvp build/rtl/Rv32AluFast.sv tests/alu_tb.sv; vvp build/alu-fast-test.vvp'
alu-fast-gds: alu-fast-test
	./tools/librelane librelane/alu-fast/config.json

.PHONY: tt-rtl tt-test
tt-rtl:
	./tools/dev ./tools/sbt 'runMain GenerateTinyTapeout'
tt-test:
	./tools/dev bash -e -c '$(MAKE) -C test PATH="$$PWD/.venv-tt/bin:$$PATH"; .venv-tt/bin/python -m cocotb_tools.check_results test/results.xml'
