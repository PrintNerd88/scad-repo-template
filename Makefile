# ---------------------------------------------------------------------------
# Toolchain resolution
#
# Prefer openscad-nightly: it has the manifold backend, which renders CSG-heavy
# parts far faster than CGAL (0.33 s vs 33 s on this repo's benchmark part).
# Fall back to a stable `openscad` when the nightly isn't installed, and let an
# explicit OPENSCAD=... override both.
#
#   make                              # nightly if present, else openscad
#   make OPENSCAD=openscad            # force the stable build
#   make OPENSCAD=/opt/x/bin/openscad # force an arbitrary binary
#   make toolchain                    # show what was picked, and why
# ---------------------------------------------------------------------------
OPENSCAD_CANDIDATES ?= openscad-nightly openscad
OPENSCAD_AUTO := $(firstword $(foreach c,$(OPENSCAD_CANDIDATES),\
                   $(if $(shell command -v $(c) 2>/dev/null),$(c))))
OPENSCAD ?= $(OPENSCAD_AUTO)

# Goals that never shell out to OpenSCAD, so they must work with none installed.
NO_SCAD_GOALS := clean help toolchain
ifneq ($(filter-out $(NO_SCAD_GOALS),$(or $(MAKECMDGOALS),all)),)
  ifeq ($(strip $(OPENSCAD)),)
    $(error No OpenSCAD found on PATH. Looked for: $(OPENSCAD_CANDIDATES). \
            Install one, or run 'make OPENSCAD=/path/to/openscad'. See 'make toolchain'.)
  endif
  ifeq ($(shell command -v $(OPENSCAD) 2>/dev/null),)
    $(error OPENSCAD is set to '$(OPENSCAD)', which is not executable. See 'make toolchain'.)
  endif
endif

# --backend=manifold exists only on OpenSCAD >= 2025.x (or a 2023+ dev
# snapshot), so probe rather than assume. Older builds just render slower.
MANIFOLD := $(if $(strip $(OPENSCAD)),\
              $(shell $(OPENSCAD) --help 2>&1 | grep -q -- '--backend' && echo --backend=manifold))
FLAGS    ?= $(MANIFOLD) --export-format=binstl

PARTS    := $(patsubst src/%.scad,%,$(wildcard src/*.scad))
STLS     := $(addprefix out/,$(addsuffix .stl,$(PARTS)))
PNGS     := $(addprefix out/,$(addsuffix .png,$(PARTS)))
TESTS    := $(wildcard tests/*.scad)
DEPS     := $(wildcard lib/*.scad)

.PHONY: all stl png test clean help toolchain
all: stl

stl: $(STLS)
png: $(PNGS)

out/%.stl: src/%.scad $(DEPS) | out
	$(OPENSCAD) $(FLAGS) -o $@ $<

# PNG export needs a display on most builds: use `xvfb-run make png` if headless.
out/%.png: src/%.scad $(DEPS) | out
	$(OPENSCAD) --render --imgsize=1200,900 --colorscheme=Tomorrow -o $@ $<

# OpenSCAD's whole test framework is assert() and echo(). Every version tested
# (2021.01 and the 2026.08 nightly) exits 0 even when an assert fails, reporting
# it only in the echo stream, so grep the output instead of trusting the exit
# code. This is not a legacy workaround — do not reduce it to relying on $$?.
test: $(TESTS) | out
	@fail=0; \
	for t in $(TESTS); do \
		echo "== $$t"; \
		log=out/$$(basename $$t .scad).echo; \
		$(OPENSCAD) --export-format=echo -o $$log $$t || fail=1; \
		[ -s $$log ] && sed 's/^/   /' $$log; \
		grep -qE '^(ERROR|WARNING|TRACE)' $$log 2>/dev/null && fail=1; \
	done; \
	if [ $$fail -ne 0 ]; then echo "FAILED"; exit 1; fi; \
	echo "all tests passed"

toolchain:
	@if [ -z "$(strip $(OPENSCAD))" ]; then \
		echo "binary   : NOT FOUND (looked for: $(OPENSCAD_CANDIDATES))"; \
		echo "           install one, or set OPENSCAD=/path/to/openscad"; \
		exit 1; \
	fi
	@echo "binary   : $(OPENSCAD) -> $$(command -v $(OPENSCAD) 2>/dev/null || echo 'NOT EXECUTABLE')"
	@echo "version  : $$($(OPENSCAD) --version 2>&1 | head -1)"
ifeq ($(strip $(MANIFOLD)),)
	@echo "backend  : CGAL (no --backend support; CSG-heavy parts render slowly)"
	@echo "           install openscad-nightly for the manifold backend"
else
	@echo "backend  : manifold (fast)"
endif
	@echo "flags    : $(strip $(FLAGS))"

help:
	@echo "make            build STLs into out/ (same as 'make stl')"
	@echo "make png        render previews into out/"
	@echo "make test       run tests/*.scad"
	@echo "make toolchain  show which OpenSCAD is in use"
	@echo "make clean      remove out/"
	@echo
	@echo "Override the binary with: make OPENSCAD=openscad"

out:
	mkdir -p out

clean:
	rm -rf out
