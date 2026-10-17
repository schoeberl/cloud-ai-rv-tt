SIM ?= icarus
TOPLEVEL_LANG = verilog
VERILOG_SOURCES = $(CURDIR)/../src/WildcatThreeStage.sv $(CURDIR)/core_tb.sv
TOPLEVEL = core_tb
COCOTB_TEST_MODULES = test_core
include $(shell cocotb-config --makefiles)/Makefile.sim
