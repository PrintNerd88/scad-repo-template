# scad-repo-template

What this project makes, and what it's for, in a sentence or two.

![Rendered preview](docs/preview.png)

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

| File | What it makes |
|---|---|
| `src/params.scad` | The measurements of every part, which each one includes |
| `src/plate.scad` | A demo mounting plate, to replace with your own parts |
| `src/cap.scad` | A demo cap that fits over the plate's boss, likewise |
| `src/assembly.scad` | The parts together, to check how they fit; not printed |

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
| `make png` | Renders previews of the parts and of `src/assembly.scad` into `out/`; without a display, `xvfb-run make png` |
| `make test` | Runs `tests/*.scad`, and fails if `src/assembly.scad` no longer evaluates cleanly |
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

## Syncing with the template

This project was created from a template; `.template.toml` records the template commit
it was last synced with. To bring in the template's later changes, commit your work,
then run the template's sync tool from a checkout of it — here, `../template`:

```bash
uv run ../template/scripts/template_sync.py check .     # what would change
uv run ../template/scripts/template_sync.py update .    # apply it, then review and commit
```
<!-- </template-only> -->

## License

MIT — see [LICENSE](LICENSE).
