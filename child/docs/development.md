# Development

Everything runs through `make` from the repository root.

## Build and test

| Command | Result |
|---|---|
| `make` / `make stl` | Renders every part in `src/` to `out/*.stl` |
| `make png` | Renders previews of the parts, and of `src/assembly.scad` if it exists, into `out/`; without a display, `xvfb-run make png` |
| `make test` | Runs `tests/*.scad`, and fails if `src/assembly.scad` exists and no longer evaluates cleanly |
| `make docs` | Builds this documentation into `site/`, failing on any warning |
| `make docs-serve` | Serves it at <http://127.0.0.1:8000>, rebuilding on every save |
| `make toolchain` | Shows which OpenSCAD is in use |
| `make clean` | Removes `out/` and `site/` |
| `make help` | Lists the targets |

`make OPENSCAD=openscad` picks a specific binary. OpenSCAD exits 0 even when an
`assert()` fails, so `make test` fails on any `ERROR`, `WARNING` or `TRACE` in its output
instead.

## Third-party libraries

Libraries are git submodules under `vendor/`, referenced by relative path and never
edited. Bump one deliberately:

```bash
git submodule update --remote vendor/<library>
git commit -am "build(vendor): bump <library>"
```

## Documentation

This site is the Markdown in `docs/`, built with MkDocs and the Material theme. Page
order is the `nav` list in `mkdocs.yml`; add new pages there.

The `docs` workflow builds the site on every push and pull request, and publishes it to
GitHub Pages from `main`. Publishing needs two one-time steps:

1. In the repository's **Settings → Pages**, set **Source** to **GitHub Actions**.
2. In `mkdocs.yml`, uncomment `site_url` and `repo_url`, and replace `<GITHUB USER>` with
   the account or organisation that owns the repository.
