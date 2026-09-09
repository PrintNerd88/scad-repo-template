# scad-repo-template

Baseline shape and setup for OpenSCAD projects. Opinionated where OpenSCAD itself is
not: the language has no package manager, no project file, and no formal repo
convention, so this is a self-contained repo that renders headlessly and reproducibly.

The included part is a demo — a parametric mounting plate, annotated section by
section with the convention it illustrates. Replace it.

![preview](docs/preview.png)

## Getting started

```bash
git clone --recurse-submodules <this-repo> myproject
cd myproject
make test
make stl        # -> out/*.stl
```

Already cloned without `--recurse-submodules`? Run `git submodule update --init`.

If you used GitHub's **Use this template** button, submodules are not copied — run
`git submodule update --init` after the first clone.

### Requirements

- **OpenSCAD.** The build prefers `openscad-nightly` and falls back to a stable
  `openscad`; anything from 2021.01 onward works. Run `make toolchain` to see which was
  picked. The nightly is strongly recommended — it has the manifold backend, which
  renders this repo's benchmark part in 0.33 s against 33 s under CGAL. Install it with
  `sudo snap install openscad-nightly`, or from <https://openscad.org/downloads.html>.
- **make**, and **git** for the vendored library.
- On Windows, run from Git Bash, or add `C:\Program Files\OpenSCAD\` to `PATH`.
- Headless PNG export usually needs a display: `xvfb-run make png`.

Nothing here requires the nightly: with only a stable `openscad` installed, every target
still works, just slower. CI builds both.

## Layout

```
src/                 # printable parts / assemblies — one .scad per output file
lib/                 # project-local reusable modules/functions (definitions only)
vendor/              # third-party libraries as git submodules
presets/             # Customizer parameter sets (.json), one per variant
tests/               # assert()-based .scad files, run headlessly
out/                 # rendered STL/PNG — gitignored
scripts/             # helper scripts if the Makefile isn't enough
docs/                # tracked images for this README
```

See [AGENTS.md](AGENTS.md) for the rule attached to each directory.

## Build

| Command | Result |
|---|---|
| `make` / `make stl` | Renders every `src/*.scad` to `out/*.stl` |
| `make png` | Renders previews to `out/*.png` (needs a display) |
| `make test` | Runs `tests/*.scad` |
| `make clean` | Removes `out/` |
| `make toolchain` | Prints the resolved binary, version, and backend |
| `make help` | Lists the targets |

`clean`, `help` and `toolchain` work even with no OpenSCAD installed; the build targets
fail immediately with an actionable message instead of a confusing render error.

Overrides:

```bash
make OPENSCAD=openscad                   # force the stable build
make OPENSCAD=/path/to/openscad          # non-PATH install
make OPENSCAD_CANDIDATES='foo bar'       # change the auto-detect search order
make FLAGS='--export-format=binstl'      # force flags (skips the manifold probe)
```

Resolution order: an explicit `OPENSCAD=` wins; otherwise the first of
`openscad-nightly openscad` found on `PATH`.

Variants — add explicit targets rather than generalising the pattern rule:

```bash
openscad -D 'plate_length=120' -o out/plate-long.stl src/example.scad
openscad -p presets/example.json -P large-m5 -o out/plate-large.stl src/example.scad
```

## Customizer parameters

Open the part in OpenSCAD and use **Window → Customizer**, or edit the block at the top
of `src/example.scad`.

| Parameter | Default | Range | Meaning |
|---|---|---|---|
| `plate_length` | 60 | 20–200 | Plate length (mm) |
| `plate_width` | 40 | 20–200 | Plate width (mm) |
| `plate_thick` | 3 | 1.5–10, step 0.5 | Plate thickness (mm) |
| `corner_round` | 4 | 0–10, step 0.5 | Vertical corner radius (mm) |
| `hole_count_x` | 2 | 1–6 | Holes along X |
| `hole_count_y` | 2 | 1–6 | Holes along Y |
| `hole_size` | `M3` | M2…M5 | Screw size; drives clearance diameter |
| `hole_margin` | 6 | — | Edge to hole centre (mm) |
| `add_boss` | `true` | bool | Add the centred boss |
| `boss_od` | 12 | 6–30 | Boss outer diameter (mm) |
| `boss_height` | 8 | 2–30 | Boss height (mm) |
| `boss_style` | `round` | round, hex | Boss profile |

Saved sets live in `presets/example.json` (`default`, `large-m5`, `plain`).

## Tests

`tests/*.scad` assert on the functions in `lib/`. Test functions, not geometry — there
is no good automated STL diff in the standard toolchain. For geometry regressions, CI
renders PNGs on every push; diff them by eye in the PR.

Note that OpenSCAD exits 0 even when an `assert()` fails (verified on both 2021.01 and
the 2026.08 nightly), so `make test` inspects the echo output rather than the exit code.
See AGENTS.md.

## Third-party libraries

Vendored as git submodules under `vendor/`, referenced by relative path:

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

## Print settings

Fill in per project: material, layer height, orientation, supports, infill.

## Releases

`out/` is gitignored. Attach STLs to a GitHub release from a tag-triggered job instead of
committing binaries.

## New project checklist

1. `git clone --recurse-submodules <template> <name>`.
2. Rename `src/example.scad` and its `mounting_plate()` module; update this README's title,
   purpose, and parameter table.
3. Update `presets/example.json` to match.
4. `pre-commit install`.
5. Confirm the toolchain: `make toolchain`, then `make test` and `make stl`.
6. Verify `out/` is ignored: `git status` shows no STL after step 5.
7. Replace `docs/preview.png` (`make png && cp out/<part>.png docs/preview.png`).
8. Choose a license — the bundled `LICENSE` is MIT with a placeholder copyright holder.
9. First commit with a Conventional Commits scope.

## License

MIT — see [LICENSE](LICENSE). Update the copyright holder before publishing.
