# Syncing with the template

A project created from the template remembers where it came from, so the template's
later changes — CI fixes, new Makefile targets, documentation updates — can be pulled
into it without copying files by hand, and without losing the project's own edits.

## How it works

- The **template** holds `template.toml`, which gives every file it ships a *strategy*,
  and the sync tool, `scripts/template_sync.py`. Neither is copied into projects.
- A **project** holds `.template.toml`: where the template lives, the template commit the
  project was last synced with (the *pin*), the values that replaced the template's
  placeholders, and any per-file overrides.
- The tool runs from a checkout of the template and is pointed at a project. For each
  file it compares three versions — the template at the pin, the template now, and the
  project's copy — which is how it tells a template change apart from a local edit.

## Strategies

| Strategy | Files | On update |
|---|---|---|
| `managed` | `.gitignore`, `.gitmodules`, `.pre-commit-config.yaml`, both CI workflows, `docs/requirements.txt`, and this page | The template owns these. They are always brought to the template's version, and a local edit is reported as drift — make the change in the template instead. |
| `merge` | `Makefile`, `AGENTS.md`, `mkdocs.yml`, and the Home, Getting started and Development pages | Yours to extend. Template changes are 3-way merged in; where both sides changed the same lines, the file gets conflict markers to resolve, as in a git merge. |
| `seed` | Everything in `src/`, `lib/`, `tests/` and `presets/`, `README.md`, `LICENSE`, the Parts page, `docs/preview.png`, and the workspace file | Copied once when the project is created, then never touched again. |

The template's `template.toml` lists every file.

## Before you start

You need uv, git, and an up-to-date clone of the template. The project's
`.template.toml` records the template's URL.

```bash
git clone <template-url> ../template      # the first time
git -C ../template pull                   # afterwards
```

Commit your work in the project first: `update` refuses to run on uncommitted changes,
so that each sync is one reviewable diff.

## Check

```bash
uv run ../template/scripts/template_sync.py check .
```

`check` writes nothing. It lists each file that isn't up to date, compares each
submodule's commit with the template's, and ends with a summary.

| Status | Meaning | What `update` does |
|---|---|---|
| `update` | Changed in the template, untouched in the project | Takes the template's version |
| `merged` | Changed on both sides, in different places | Writes the merged file |
| `conflict` | Changed on both sides, in the same place | Writes the file with conflict markers |
| `new` | Added to the template | Adds it |
| `delete` | Removed from the template, unchanged in the project | Deletes it |
| `drift` | A `managed` file edited in the project | Overwrites it with the template's version |
| `local` | Edited only in the project | Nothing |
| `removed-upstream` | Removed from the template, but edited in the project | Nothing; the file is kept |
| `seed-available` | A `seed` file added to the template | Adds it only with `--seed` |
| `markers` | Conflict markers left from an earlier update | Refuses to run until they are resolved |
| `ignored` | Skipped by `[overrides]` | Nothing |

`--all` also lists the files that are up to date. `check` exits `0` when nothing is wrong
— pending updates alone are fine — `1` on drift, a conflict or leftover markers, and `2`
on a configuration error; `--strict` also exits `1` while updates are pending.

## Update

```bash
uv run ../template/scripts/template_sync.py update .
git status && git diff                      # review what changed
git add -A && git commit -m "chore: sync with template"
```

`update` makes every change in the table above, then moves the pin in `.template.toml`
to the template's current commit. It exits `0` when everything applied cleanly, `1` when
some files have conflicts, and `2` when it refused to run.

### Conflicts

A conflicted file holds git-style conflict markers around three versions of each
disputed passage: `yours` (the project's), `template@<old pin>` (the common ancestor),
and `template@<new pin>` (the template now). Edit each passage down to the text you
want, then commit. The pin has already moved, so the change isn't offered again;
`check` reports any markers you missed, and `update` won't run until they are gone.

## Overrides

A project can change how any file is treated, in `.template.toml`:

```toml
[overrides]
".gitignore" = "merge"     # keep my own ignores, and merge the template's changes in
"Makefile" = "ignore"      # forked for good; stop tracking it
```

Keys are paths as the template names them; values are `managed`, `merge`, `seed`, or
`ignore`.

## Values, features and submodules

- **`[values]`** holds what replaced the template's placeholders when the project was
  created: its name, and the copyright holder in `LICENSE`. Every sync applies them to
  the template's text before comparing, so template changes arrive already renamed.
  Change a value only together with renaming it throughout the project.
- **`[features]`** records which of the template's optional features the project kept.
  A declined feature's files are not tracked.
- **Submodules** are compared, never changed: `check` reports a vendored library pinned
  at a different commit from the template's, and bumping it stays a deliberate commit —
  see [Third-party libraries](development.md#third-party-libraries).

<!-- <template-only> -->

## Maintaining the template

This section is about changing the template itself, and is left out of projects.

### Every tracked file needs a rule

`template.toml` classifies each tracked file as `managed`, `merge`, `seed`, or `exclude`
(kept in the template, never shipped). `make template-validate` fails on a file that
matches no rule, or more than one, so adding a file forces the decision. A new page in
`docs/` also needs an entry in `nav` in `mkdocs.yml`.

### Template-only content

Anything that must not reach projects — the `template-*` Makefile targets, the CI job
that validates the manifest, this section — goes between marker lines. `new` and
`update` remove the markers and everything between them:

```text
# <template-only>                   ← opens a block (Makefile, YAML, TOML)
<!-- <template-only> -->            ← the same, in Markdown
# <template-only feature="name">    ← removed only from projects that decline the feature
# </template-only>                  ← closes a block
```

A marker must be alone on its line apart from the file's comment syntax, and blocks
can't nest. (The lines above aren't markers, because of the notes after them.)

### Tokens

`[tokens]` maps literal text in the template to a project's values: `scad-repo-template`
becomes the project's name and `<COPYRIGHT HOLDER>` its copyright holder, in file
contents and file names. Don't reword either, and don't write them anywhere that ships
unless they should be replaced there too.

### Testing a change

```bash
make template-validate                        # every file classified, markers balanced
make template-test                            # the sync tool's unit tests
make template-new CHILD=../scratch ARGS=-y    # a throwaway project to try changes on
make template-check CHILD=../scratch          # what that project would receive
```

CI runs the first two on every push.

<!-- </template-only> -->
