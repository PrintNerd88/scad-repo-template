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
# <template-only feature="docs">
NO_SCAD_GOALS += docs docs-serve
# </template-only>
# <template-only>
NO_SCAD_GOALS += template-validate template-test template-check template-update template-new
# </template-only>
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

# Every file directly in src/ is a part, rendered to out/<name>.stl, except two.
# params.scad holds the parts' measurements and draws nothing, so it gets no
# STL and no PNG. assembly.scad places the parts together to check how they
# fit, and is never printed, so it gets a preview and a check in `make test`,
# but no STL. Either may be missing. src/lib/ is not searched for parts: it
# holds the definitions they share, so everything built depends on it.
PARAMS   := $(wildcard src/params.scad)
ASSEMBLY := $(wildcard src/assembly.scad)
PARTS    := $(patsubst src/%.scad,%,$(filter-out $(PARAMS) $(ASSEMBLY),$(wildcard src/*.scad)))
STLS     := $(addprefix out/,$(addsuffix .stl,$(PARTS)))
PNGS     := $(addprefix out/,$(addsuffix .png,$(PARTS)))
TESTS    := $(wildcard tests/*.scad)
DEPS     := $(wildcard src/lib/*.scad)

.PHONY: all stl png test clean help toolchain
all: stl

stl: $(STLS)
png: $(PNGS) $(ASSEMBLY:src/%.scad=out/%.png)

out/%.stl: src/%.scad $(DEPS) | out
	$(OPENSCAD) $(FLAGS) -o $@ $<

# PNG export needs a display on most builds: use `xvfb-run make png` if headless.
out/%.png: src/%.scad $(DEPS) | out
	$(OPENSCAD) --render --imgsize=1200,900 --colorscheme=Tomorrow -o $@ $<

# The assembly is previewed rather than rendered: a render drops each part's
# color() on the CGAL backend, and drops % reference geometry on every backend.
out/assembly.png: src/assembly.scad $(PARTS:%=src/%.scad) $(DEPS) | out
	$(OPENSCAD) --preview --imgsize=1200,900 --colorscheme=Tomorrow -o $@ $<

# Every part takes its measurements from params.scad, and so does the assembly.
$(STLS) $(PNGS) out/assembly.png: $(PARAMS)

# OpenSCAD's whole test framework is assert() and echo(). Every version tested
# (2021.01 and the 2026.08 nightly) exits 0 even when an assert fails, reporting
# it only in the echo stream, so grep the output instead of trusting the exit
# code. This is not a legacy workaround — do not reduce it to relying on $$?.
#
# The assembly is evaluated here too, since `make stl` never builds it. This is
# what catches it broken by a change to a part: a renamed module, a moved file
# or a failed assert is likewise only a WARNING or ERROR in the echo stream.
# Each log lands at the source's path under out/, minus src/.
test: $(TESTS) $(ASSEMBLY) | out
	@fail=0; \
	for t in $(TESTS) $(ASSEMBLY); do \
		echo "== $$t"; \
		log=out/$${t#src/}; log=$${log%.scad}.echo; \
		mkdir -p $$(dirname $$log); \
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

# <template-only feature="docs">
# ---------------------------------------------------------------------------
# Documentation
#
# uv runs MkDocs and its theme from the docs dependency group in pyproject.toml,
# at the versions locked in uv.lock, in .venv/.
# ---------------------------------------------------------------------------
MKDOCS := uv run --group docs mkdocs

.PHONY: docs docs-serve
docs:
	$(MKDOCS) build --strict

docs-serve:
	$(MKDOCS) serve
# </template-only>

help:
	@echo "make            build STLs into out/ (same as 'make stl')"
	@echo "make png        render previews of the parts and the assembly into out/"
	@echo "make test       run tests/*.scad and check the assembly still evaluates"
# <template-only feature="docs">
	@echo "make docs       build the documentation into site/"
	@echo "make docs-serve preview the documentation at http://127.0.0.1:8000"
# </template-only>
	@echo "make toolchain  show which OpenSCAD is in use"
	@echo "make clean      remove build output"
	@echo
	@echo "Override the binary with: make OPENSCAD=openscad"

out:
	mkdir -p out

clean:
	rm -rf out
# <template-only feature="docs">
	rm -rf site
# </template-only>
# <template-only>
# Template maintenance. Everything between these markers is stripped from
# children by scripts/template_sync.py, which never ships to them either.
#   make template-validate           template.toml classifies every tracked file
#   make template-test               unit tests for the sync tool
#   make template-new CHILD=path     create a project from this template
#   make template-check CHILD=path   report a child's drift and pending updates
#   make template-update CHILD=path  apply template changes to a child
# Extra flags go in ARGS, e.g. ARGS='--set project=foo -y'.
CHILD ?=
ARGS  ?=
.PHONY: template-validate template-test template-new template-check template-update
template-validate:
	uv run scripts/template_sync.py validate
template-test:
	PYTHONDONTWRITEBYTECODE=1 uv run scripts/template_sync_test.py
template-new template-check template-update: template-%:
	@test -n "$(CHILD)" || { echo "usage: make template-$* CHILD=path/to/child [ARGS='...']"; exit 2; }
	uv run scripts/template_sync.py $* $(CHILD) $(ARGS)
# </template-only>
