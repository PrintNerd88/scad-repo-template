# Getting started

## Requirements

- **OpenSCAD**, ideally the nightly build: `sudo snap install openscad-nightly`, or a
  development snapshot from <https://openscad.org/downloads.html>. Its manifold backend
  renders CSG-heavy parts much faster; a stable `openscad` works too.
- **make** and **git**.
- **uv**, which runs the Python tooling:
  <https://docs.astral.sh/uv/getting-started/installation/>.
- **pre-commit**: `uv tool install pre-commit`.
- **Xvfb**, only to render PNG previews without a display: `sudo apt install xvfb`.

On Windows, run everything from Git Bash, with OpenSCAD's install directory on `PATH`.

## Install

```bash
git clone --recurse-submodules <repository-url>
cd scad-repo-template
pre-commit install
make toolchain      # which OpenSCAD was found, its version and backend
make test
make stl            # -> out/*.stl
```

Cloned without `--recurse-submodules`? Run `git submodule update --init`.

To read this documentation locally, run `make docs-serve` and open
<http://127.0.0.1:8000>.
