# Getting started

## Requirements

- **OpenSCAD nightly**: `sudo snap install openscad-nightly`, or the development
  snapshot from <https://openscad.org/downloads.html> on other platforms. Its manifold
  backend renders CSG-heavy parts much faster than CGAL.
- **make** and **git**.
- **uv**, which installs and runs all the Python tooling:
  <https://docs.astral.sh/uv/getting-started/installation/>.
- **pre-commit**: `uv tool install pre-commit`.
- **Xvfb**, to render PNG previews on a machine without a display:
  `sudo apt install xvfb`.

On Windows, run everything from Git Bash, with OpenSCAD's install directory on `PATH`.

## Clone the template

```bash
git clone --recurse-submodules <repository-url>
cd scad-repo-template
```

## Create a new project

From the template checkout:

```bash
uv run scripts/template_sync.py new ../myproject
```

It asks for each value and option below, then:

1. copies every file a project gets. That leaves out `template.toml`, the sync tool, and
   the template's own README, documentation and preview image: a project gets the generic
   README in `child/` instead, and, if it takes the documentation site, the generic pages
   in `child/docs/`;
2. replaces the template's name and the `LICENSE` placeholder with your values;
3. removes template-only sections, and the sections for options you didn't take;
4. runs `git init` on a `main` branch and adds each `vendor/` submodule at the commit
   the template pins;
5. writes `.template.toml`, recording the template commit the project was created
   from, your values and your options; and
6. stages everything. It never commits.

| Value | Replaces | Default |
|---|---|---|
| `project` | `scad-repo-template`: the README and documentation titles, the site name, the `pyproject.toml` project name | The new directory's name |
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

Nothing in a new project mentions the template or the demo, apart from `.template.toml`
and the demo parts: `src/plate.scad`, `src/cap.scad`, `src/params.scad` and
`src/assembly.scad`. Delete those and you have a blank slate, with the build system and
its documentation still in place.

1. Review `git status`, then make the first commit with a Conventional Commits message.
2. `pre-commit install`.
3. Confirm the toolchain: `make toolchain`, then `make test` and `make stl`.
4. Check that `out/` is ignored: `git status` shows no STL after step 3.
5. Replace the demo parts: put your own measurements in `src/params.scad`, and replace
   `src/plate.scad` and `src/cap.scad` with one file per part. Then either rewrite
   `src/assembly.scad` to place your own parts, or, for a single-part project, delete
   it; nothing else refers to it.
6. Fill in the placeholders in `README.md` and, with the documentation site, the pages in
   `docs/`: `git grep -n FIXME` lists them.
7. Check the copyright holder in `LICENSE`.
8. With the documentation site, publish it: see
   [Documentation](development.md#documentation).
