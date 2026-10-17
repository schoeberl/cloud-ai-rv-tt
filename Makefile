.PHONY: dev rtl test core-test tt-rtl tt-test smoke

dev:
	./tools/dev
rtl tt-rtl:
	./tools/dev ./tools/sbt 'runMain GenerateTinyTapeout'
core-test:
	./tools/dev bash -e -c '$(MAKE) -C tests PATH="$$PWD/.venv-tt/bin:$$PATH"; .venv-tt/bin/python -m cocotb_tools.check_results tests/results.xml'
tt-test:
	./tools/dev bash -e -c '$(MAKE) -C test PATH="$$PWD/.venv-tt/bin:$$PATH"; .venv-tt/bin/python -m cocotb_tools.check_results test/results.xml'
test: core-test tt-test
smoke:
	./tools/librelane --smoke-test
