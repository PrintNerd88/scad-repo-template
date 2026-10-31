# scad-repo-template

<!-- FIXME: what this project makes, and what it's for, in a sentence or two. -->

<!-- FIXME: a render of it. Run `make png`, copy out/<part>.png to docs/, and link it here: ![<part>](docs/<part>.png) -->

<!-- <template-only feature="docs"> -->
## Quick start

```bash
git clone --recurse-submodules <repository-url>
cd scad-repo-template
make test
make stl            # -> out/*.stl
```

The documentation, from requirements to development, starts at
[docs/index.md](docs/index.md).
<!-- </template-only> -->
<!-- <template-only feature="!docs"> -->
## Parts

<!-- FIXME: one row per file in src/. -->

| File | What it makes |
|---|---|
| `src/<part>.scad` | FIXME |

## Getting started

You need:

- **OpenSCAD**, ideally the nightly build: `sudo snap install openscad-nightly`, or a
  development snapshot from <https://openscad.org/downloads.html>. Its manifold backend
  renders CSG-heavy parts much faster; a stable `openscad` works too.
- **make** and **git**.
- **pre-commit**, installed with [uv](https://docs.astral.sh/uv/):
  `uv tool install pre-commit`.
- **Xvfb**, only to render PNG previews without a display: `sudo apt install xvfb`.

On Windows, run everything from Git Bash, with OpenSCAD's install directory on `PATH`.

```bash
git clone --recurse-submodules <repository-url>
cd scad-repo-template
pre-commit install
make toolchain      # which OpenSCAD was found, its version and backend
make test
make stl            # -> out/*.stl
```

Cloned without `--recurse-submodules`? Run `git submodule update --init`.

## Development

Everything runs through `make` from the repository root.

| Command | Result |
|---|---|
| `make` / `make stl` | Renders every part in `src/` to `out/*.stl` |
| `make png` | Renders previews of the parts, and of `src/assembly.scad` if it exists, into `out/`; without a display, `xvfb-run make png` |
| `make test` | Runs `tests/*.scad`, and fails if `src/assembly.scad` exists and no longer evaluates cleanly |
| `make toolchain` | Shows which OpenSCAD is in use |
| `make clean` | Removes `out/` |
| `make help` | Lists the targets |

`make OPENSCAD=openscad` picks a specific binary. OpenSCAD exits 0 even when an
`assert()` fails, so `make test` fails on any `ERROR`, `WARNING` or `TRACE` in its output
instead.

Third-party libraries are git submodules under `vendor/`, never edited. Bump one
deliberately:

```bash
git submodule update --remote vendor/<library>
git commit -am "build(vendor): bump <library>"
```
<!-- </template-only> -->

## License

MIT — see [LICENSE](LICENSE).
