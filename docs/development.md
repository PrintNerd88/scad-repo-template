# Development

Everything runs through `make` from the repository root; `make help` lists the targets.

## Build

| Command | Result |
|---|---|
| `make` / `make stl` | Renders every part in `src/` to `out/*.stl` |
| `make png` | Renders previews of the parts and the assembly into `out/` (needs a display; see below) |
| `make test` | Runs `tests/*.scad`, and fails if the assembly no longer evaluates cleanly |
| `make docs` | Builds the documentation into `site/`, failing on any warning |
| `make docs-serve` | Serves the documentation at <http://127.0.0.1:8000>, rebuilding on every save |
| `make clean` | Removes `out/` and `site/` |
| `make toolchain` | Prints the resolved OpenSCAD binary, version, and backend |
| `make help` | Lists the targets |

`clean`, `help`, `toolchain` and the docs targets work with no OpenSCAD installed; the
render targets fail straight away with an actionable message instead of a confusing
render error.

PNG export needs a display on most OpenSCAD builds. Without one, run it under Xvfb:
`xvfb-run make png`.

### Choosing the OpenSCAD binary

An explicit `OPENSCAD=` wins; otherwise the Makefile uses the first of
`openscad-nightly openscad` found on `PATH`, and passes `--backend=manifold` when that
binary supports it.

```bash
make OPENSCAD=openscad                   # force the stable build
make OPENSCAD=/path/to/openscad          # non-PATH install
make OPENSCAD_CANDIDATES='foo bar'       # change the auto-detect search order
make FLAGS='--export-format=binstl'      # force flags (skips the manifold probe)
```

## Parts, measurements and the assembly

`src/` holds one file per printed part, and two more that aren't parts:

- `params.scad` holds every measurement, in the Customizer format: grouped under
  `/* [Group] */` headers, with a range in a trailing comment and a description above.
  Each part `include`s it, so parts that have to fit each other read the same values.
  Change a measurement there, never in a part file. It draws nothing, so `make` builds
  nothing from it.
- `assembly.scad` `use`s the parts and places them together, giving each its own
  `color()`, to check how they fit. It is never printed, so `make stl` skips it.
  `make png` previews it, rather than rendering it, so each part keeps its colour and any
  `%` reference geometry stays visible. `make test` evaluates it and fails on any error
  or warning, which catches an assembly that a change to a part has broken. A
  single-part project can delete it.

A part file keeps only its render quality in its own Customizer block, and wraps its
geometry in a module whose arguments default to the values in `params.scad`.

OpenSCAD's Customizer panel only shows the opened file's own parameters, so it doesn't
show the measurements when a part is open. Edit `params.scad` instead.

## Variants

To build a part with different measurements, override them with `-D`. String values
need their quotes:

```bash
openscad -D 'plate_length=120' -D 'hole_size="M5"' -o out/plate-long.stl src/plate.scad
```

Add an explicit Makefile target for each variant you want built, rather than
generalising the pattern rule:

```make
stl: out/plate-long.stl
out/plate-long.stl: src/plate.scad src/params.scad $(DEPS) | out
	$(OPENSCAD) $(FLAGS) -D 'plate_length=120' -o $@ $<
```

The Customizer's JSON presets don't work here: on the nightly, a preset only reaches
parameters in the opened file, never those in `params.scad`. `-D` does, on both
toolchains.

## Tests

`tests/*.scad` assert on the functions in `src/lib/`. Test functions, not geometry — there is
no good automated STL diff in the standard toolchain. For geometry regressions, CI
renders PNGs on every push and uploads them with the STLs; compare them by eye in the
pull request.

OpenSCAD exits 0 even when an `assert()` fails (verified on both 2021.01 and the 2026.08
nightly), so `make test` searches the echo output for `ERROR`, `WARNING` and `TRACE`
instead of trusting the exit code.

## Pre-commit hooks

Run `pre-commit install` once per clone; the hooks then check every commit, and
`pre-commit run --all-files` checks the whole tree on demand. They fix trailing
whitespace and missing final newlines, reject files over 500 KB (usually an STL
committed by accident), check that JSON files parse, scan for credentials, and
evaluate every changed `.scad` file outside `vendor/` with OpenSCAD.

That last check is a full render, which gets slow on large parts;
`.pre-commit-config.yaml` shows how to narrow it to `src/lib/` and `tests/`.

## Third-party libraries

Libraries are vendored as git submodules under `vendor/` and referenced by relative path,
never through `OPENSCADPATH`:

```bash
git submodule add https://github.com/BelfrySCAD/BOSL2.git vendor/BOSL2
git commit -m "build: add BOSL2 submodule"
```

Bump deliberately:

```bash
git submodule update --remote vendor/BOSL2
git commit -am "build(vendor): bump BOSL2"
```

`vendor/` is never edited by hand.

## Documentation

This site is the Markdown in `docs/`, built by MkDocs with the Material theme. Page order
is the `nav` list in `mkdocs.yml`; add new pages there.

`make docs` builds with `--strict`, so a broken link, a missing heading anchor, or a page
left out of `nav` fails the build. uv runs MkDocs and the theme from the `docs`
dependency group in `pyproject.toml`, at the versions locked in `uv.lock`, installing
them into `.venv/`. To bump them, run `uv lock --upgrade`, then check that `make docs`
still passes.

The `docs` workflow builds the site on every push and pull request, and publishes it to
GitHub Pages from `main`. Once the repository is on GitHub, publishing needs two one-time
steps:

1. In the repository's **Settings → Pages**, set **Source** to **GitHub Actions**.
2. In `mkdocs.yml`, uncomment `site_url` and `repo_url` and replace `<GITHUB USER>` with
   the account or organisation that owns the repository.

A project gets a site like this one only if it takes the `docs` option when it is
created (see [Create a new project](getting-started.md#create-a-new-project)), and it
starts from generic pages rather than these.

## Releases

`out/` is gitignored. Attach STLs to a GitHub release from a tag-triggered job instead of
committing binaries.
