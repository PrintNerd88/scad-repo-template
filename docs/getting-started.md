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

## Create a new project

From the template checkout:

```bash
uv run scripts/template_sync.py new ../myproject
```

It asks for each value and option below, then:

1. copies every file a project gets. That leaves out `template.toml`, the sync tool, and
   the template's own README and documentation: a project gets the generic README in
   `child/` instead, and, if it takes the documentation site, the generic pages in
   `child/docs/`;
2. replaces the template's name and the `LICENSE` placeholder with your values, in file
   contents and file names;
3. removes template-only sections, and the sections for options you didn't take;
4. runs `git init` on a `main` branch and adds each `vendor/` submodule at the commit
   the template pins;
5. writes `.template.toml`, recording the template commit the project was created
   from, your values and your options; and
6. stages everything. It never commits.

| Value | Replaces | Default |
|---|---|---|
| `project` | `scad-repo-template`: the README and documentation titles, the site name, the workspace file name | The new directory's name |
| `copyright_holder` | `<COPYRIGHT HOLDER>` in `LICENSE` | Left as the placeholder |

| Option | Adds | Default |
|---|---|---|
| `docs` | A documentation site: Home, Getting started and Development pages built with MkDocs, `make docs` and `make docs-serve`, and a workflow that publishes the site to GitHub Pages. Without it, the README covers the same ground. | Off |

`-y` skips the questions, taking the default for anything not given with
`--set KEY=VALUE` or `--feature docs=true|false`.

Decide on the documentation site now: adding or removing it later is mostly done by
hand. Keeping the project up to date afterwards is covered in
[Syncing with the template](template-sync.md).

## First steps in a new project

1. Review `git status`, then make the first commit with a Conventional Commits message.
2. `pre-commit install`.
3. Confirm the toolchain: `make toolchain`, then `make test` and `make stl`.
4. Check that `out/` is ignored: `git status` shows no STL after step 3.
5. Replace the demo part: rename `src/example.scad` and its `mounting_plate()` module,
   and update `presets/example.json` to match. Then either rewrite the demo assembly,
   `src/assemblies/example.scad`, to place your own parts, or, for a single-part project,
   delete it; nothing else refers to it.
6. Rewrite `README.md` and, with the documentation site, the pages in `docs/`. They start
   out generic: a placeholder where the project's description goes, and the demo part in
   the parts table.
7. Replace `docs/preview.png`: `make png && cp out/<part>.png docs/preview.png`.
8. Check the copyright holder in `LICENSE`.
9. With the documentation site, publish it: see
   [Documentation](development.md#documentation).
