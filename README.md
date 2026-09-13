# scad-repo-template

Baseline shape and setup for OpenSCAD projects. Opinionated where OpenSCAD itself is
not: the language has no package manager, no project file, and no formal repo
convention, so this is a self-contained repo that renders headlessly and reproducibly.

It gives a project a fixed layout, a Makefile that renders STLs and previews with
whichever OpenSCAD is installed, assert-based tests, pre-commit hooks, CI on both the
nightly and stable toolchains, a README, and optionally a documentation site built with
MkDocs for GitHub Pages. Projects created from the template can pull in its later
changes with a small sync tool.

The included part is a demo — a parametric mounting plate, annotated section by
section with the convention it illustrates. Replace it.

![preview](docs/preview.png)

## Documentation

Start at [docs/index.md](docs/index.md): repository shape, tools, installation, building
and testing, and syncing with the template.

## License

MIT — see [LICENSE](LICENSE).
