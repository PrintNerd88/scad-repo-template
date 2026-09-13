# AGENTS.md

Conventions for coding agents working in this repo. Humans should read these too.

## Layout

| Dir | Rule |
|---|---|
| `src/` | Each file instantiates geometry at top level. Parameters at the top in Customizer format. Imports from `lib/` and `vendor/` via `use <>`. |
| `lib/` | Definitions only — `module` and `function`. No top-level geometry, no reliance on globals; all inputs are parameters. Safe to `use <>` from anywhere. |
| `vendor/` | Never edited. Pinned via submodule commit. Referenced by relative path, never `OPENSCADPATH`. |
| `presets/` | Customizer JSON. Selected at build time with `-p presets/x.json -P setname`. |
| `tests/` | Files that `assert()` on function outputs. |
| `docs/` | Documentation, and the images it uses. |
| `out/` | Build products only. Gitignored. Attach to GitHub releases instead. |

## Rules

- `lib/` files contain definitions only; never add top-level geometry there.
- Use `use <>` unless the library documents that it needs `include <>` (BOSL2 requires `include <BOSL2/std.scad>`).
- Relative imports only; never `OPENSCADPATH`. It resolves at process start against the
  user's environment, not the opened file, so it breaks for anyone who clones the repo or
  double-clicks a `.scad` in a file manager.
- New parameters go in the Customizer block at the top of the part file, with a
  `/* [Group] */` header and a `// [min:max]` range annotation.
- Prefer `$fa`/`$fs` over a global `$fn`. `$fn` on a single small feature is fine.
- One top-level call at the bottom of a part file, wrapped in a module, so the file can
  also be `use`d by `src/assembly.scad`.
- Run `make test` and `make stl` before proposing changes; do not commit anything under `out/`.
- Keep the documentation in step with the code: a change to documented behaviour updates it in
  the same commit.
- The build prefers `openscad-nightly` and falls back to stable `openscad`. Do not
  hardcode either binary — use `$(OPENSCAD)` in the Makefile and `make toolchain` to
  check what resolved. Changes must keep working on both; CI builds both.
- Do not edit `vendor/`.
<!-- <template-only feature="docs"> -->
- The documentation site is built with MkDocs from `docs/`, in the page order of `nav` in
  `mkdocs.yml`. Run `make docs` after touching either; it fails on warnings, such as a
  broken link or a page missing from `nav`.
<!-- </template-only> -->

## Commits

Conventional Commits. Suggested scopes: `part`, `lib`, `build`, `vendor`.

## Toolchain gotchas

These are load-bearing; do not "simplify" them away.

- **`assert()` does not fail the build — on any version tested.** Both 2021.01 and the
  2026.08 nightly exit 0 when an assert fails under `--export-format=echo`; the failure
  appears only in the echo stream. `make test` therefore greps the output for
  `ERROR`/`WARNING`/`TRACE` rather than trusting the exit code. This is not an
  old-version workaround — do not "simplify" it back to relying on `$?`.
- **`-o /dev/null` needs an explicit `--export-format`** (both versions). OpenSCAD infers
  the export type from the file suffix and `/dev/null` has none.
- **`use <>` does not propagate `include`d globals.** A file that calls a BOSL2-based
  module must `include <../vendor/BOSL2/std.scad>` itself, even if it only does
  `use <other_part.scad>`: BOSL2's `diff()`/`tag()` machinery reads globals like
  `$tags_shown` that `use` will not import. Symptom is an empty render on 2021.01 or an
  assert inside `attachments.scad` on 2025+.
- **`$parent_modules` is `undef` at file scope**, so `if ($parent_modules == 0)` guards
  render nothing at all. No guard is needed — `use <>` already skips top-level geometry.
- **BOSL2 anchors: `FRONT` is the `-Y` face**, so `anchor = BOTTOM+LEFT+FRONT` makes a
  part extend into `+X/+Y/+Z`. Anchoring `BACK` puts it in `-Y`, where any hole grid
  computed over `[0, w]` silently misses the part.
- **`--backend=manifold` only exists on OpenSCAD >= 2025.x** (or a 2023+ dev snapshot).
  The Makefile probes for it and omits it on older builds; override with `make FLAGS=...`.
  It is worth having: on a CSG-heavy part it renders in 0.33 s versus 33 s under CGAL,
  which is why `openscad-nightly` is preferred by default.
- **A snap-installed OpenSCAD cannot see the host `/tmp`.** It has a private mount
  namespace, so passing it a path under `/tmp` looks like a missing file — and a missing
  file exits 1, which is easy to misread as a test failure. Keep scratch `.scad` files
  inside the repo.

<!-- <template-only> -->
## Template maintenance

This repo is a template. `scripts/template_sync.py` creates child projects from it
and keeps them in sync; children never receive the script, only a `.template.toml`.
This whole section is stripped from children.

- Every tracked file must be classified in `template.toml` as `managed`, `merge`,
  `seed`, or `exclude`. `make template-validate` enforces it; run that and
  `make template-test` before proposing changes.
- Anything that must not reach children — template-only Makefile targets, CI jobs,
  this section — goes between marker lines written in the file's comment syntax,
  `# <template-only>` … `# </template-only>` (or `<!-- … -->` in Markdown). A marker
  must be the only thing on its line; blocks must be balanced and cannot nest.
- Content only for children that take an optional feature goes in a block tagged
  `feature="docs"`; content only for those that decline it, in one tagged `feature="!docs"`.
  The template keeps both, so use negated blocks only in files the template doesn't use
  itself, such as those under `child/`.
- `scad-repo-template` and `<COPYRIGHT HOLDER>` are tokens (`[tokens]` in
  `template.toml`), replaced by each child's values in contents and paths. Do not
  reword them, and do not introduce the project name in other spellings.
- Template-specific knowledge belongs in `template.toml`, never in the script.
- `manifest_format` in `template.toml` is the version of the format it and the markers are
  written in. A change an older sync tool couldn't read — a new key, a new kind of marker —
  bumps it together with `MANIFEST_FORMAT` in the script: record there what the format
  adds, and make `validate` reject that in a manifest declaring an older format. The tool
  must keep reading every older format, because it parses the manifest at each child's pin.
- `README.md` and `docs/*.md` document the template and never ship. Children get the
  generic versions in `child/` instead — `child/README.md`, and `child/docs/` if they take
  the `docs` feature — which `[paths]` in `template.toml` moves to the child's root. When
  a change alters what children receive, update those too.
- A page for the template's own site goes in `docs/` and in the template-only part of
  `nav` in `mkdocs.yml`; a page for children goes in `child/docs/` and in `nav` above that
  part. `docs/template-sync.md` documents `scripts/template_sync.py`; change them together.
<!-- </template-only> -->
