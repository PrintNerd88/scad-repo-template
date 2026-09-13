# Getting started

## Requirements

- **OpenSCAD nightly**: `sudo snap install openscad-nightly`, or the development
  snapshot from <https://openscad.org/downloads.html> on other platforms. Its manifold
  backend renders the benchmark part in 0.33 s, against 33 s under CGAL.
- **make** and **git**.
- **uv**, which installs and runs all the Python tooling:
  <https://docs.astral.sh/uv/getting-started/installation/>.
- **pre-commit**: `uv tool install pre-commit`.
- **Xvfb**, to render PNG previews on a machine without a display:
  `sudo apt install xvfb`.

On Windows, run everything from Git Bash, with OpenSCAD's install directory on `PATH`.

## Install

```bash
git clone --recurse-submodules <repository-url>
cd <repository>
pre-commit install
make toolchain      # which OpenSCAD was found, its version and backend
make test
make stl            # -> out/*.stl
```

To read this documentation locally, run `make docs-serve` and open
<http://127.0.0.1:8000>.

<!-- <template-only> -->

## Create a new project

From the template checkout:

```bash
uv run scripts/template_sync.py new ../myproject
```

It asks for each value below, then:

1. copies every file the template ships — everything except `template.toml` and the
   sync tool;
2. replaces the template's name and the `LICENSE` placeholder with your values, in file
   contents and file names;
3. removes template-only sections, such as this one;
4. runs `git init` on a `main` branch and adds each `vendor/` submodule at the commit
   the template pins;
5. writes `.template.toml`, recording the template commit the project was created
   from; and
6. stages everything. It never commits.

| Value | Replaces | Default |
|---|---|---|
| `project` | `scad-repo-template`: the README and documentation titles, the site name, the workspace file name | The new directory's name |
| `copyright_holder` | `<COPYRIGHT HOLDER>` in `LICENSE` | Left as the placeholder |

Keeping the project up to date afterwards is covered in
[Syncing with the template](template-sync.md).

<!-- </template-only> -->

## First steps in a new project

1. Review `git status`, then make the first commit with a Conventional Commits message.
2. `pre-commit install`.
3. Confirm the toolchain: `make toolchain`, then `make test` and `make stl`.
4. Check that `out/` is ignored: `git status` shows no STL after step 3.
5. Replace the demo part: rename `src/example.scad` and its `mounting_plate()` module,
   update `presets/example.json` to match, and describe your parts in
   [Parts](parts.md).
6. Rewrite the overview in `README.md` and at the top of the
   [documentation home page](index.md).
7. Replace `docs/preview.png`: `make png && cp out/<part>.png docs/preview.png`.
8. Check the copyright holder in `LICENSE`.
9. Publish the documentation: see [Documentation](development.md#documentation).
