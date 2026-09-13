# Syncing with the template

Projects created from the template keep receiving its improvements — CI fixes, new
Makefile targets, tooling updates — without copying files by hand and without losing
their own changes. Syncing is a pull: a project gets nothing until someone runs the sync
tool on it, so each project moves to a newer template when it is ready.

## How it works

Every file a project gets from the template has an owner, set in the template's
`template.toml`:

| Strategy | Owner | For example | On sync |
|---|---|---|---|
| `managed` | The template | CI workflows, `.gitignore`, the pre-commit config | Made to match the template; an edit in the project is reported as drift |
| `merge` | Both | `Makefile`, `AGENTS.md`, `mkdocs.yml` | The template's changes are merged with the project's, as in a git merge |
| `seed` | The project | Parts, libraries, tests, the README and documentation pages | Left alone once the project is created |

A project's `.template.toml` pins the template commit it last synced with. Comparing the
template at the pin, the template now, and the project's own copy is how the tool tells a
template change from a local edit, so one arrives without overwriting the other. Each
sync moves the pin to the template's current commit.

## Sync a child project

Commit the project's work first: `update` won't run over uncommitted changes, so each
sync is a single reviewable diff. Then, from the project, with the template checked out
beside it:

```bash
# pull the latest version of the template
git -C ../template pull

# check what would change
uv run ../template/scripts/template_sync.py check .

# apply changes
uv run ../template/scripts/template_sync.py update .
```

If the template has gained an option the project hasn't chosen yet, such as the
documentation site, `update` asks about it first and records the answer in
`.template.toml`.

Review the result and commit it. The output lists every file that isn't up to date; two
outcomes need your attention:

- **Conflict:** the template and the project changed the same lines of a shared file,
  which is written with conflict markers. Resolve them as after a git merge.
- **Drift:** a file the template owns was edited in the project, and `update` restores
  the template's version. Make the change in the template instead, or take the file over.

Vendored libraries are compared, never changed: a submodule at a different commit from
the template's is reported, and bumping it stays a deliberate commit — see
[Third-party libraries](development.md#third-party-libraries).

## Taking a file over

When a project's copy of a file needs to part ways with the template, change how that file
is synced under `[overrides]` in `.template.toml`: `merge` to keep local edits to a file
the template owns, or `ignore` to stop syncing it altogether. The file has examples.

## Maintaining the template

A change to the template reaches every project at its next sync, so deciding how a file
is shared is part of adding it. `template.toml` gives each tracked file a strategy or keeps
it out of projects, and `make template-validate` fails on any file it doesn't cover.

The template is a working project too, and some of it is for the template alone: its
README and this site, the sync tool, the `template-*` make targets. Excluded files,
template-only sections marked in comments, and the generic stand-ins under `child/` keep
all of that out of projects. The rules for each — markers, tokens, `child/`, and when to
bump the manifest format — are in the template-maintenance section of `AGENTS.md`.

To see what a change does to projects, create a throwaway project before making it, then
check that project as you go:

```bash
make template-new CHILD=../scratch ARGS=-y    # before the change
make template-check CHILD=../scratch          # what projects would receive
make template-validate                        # every file classified, markers balanced
make template-test                            # the sync tool's tests
```

CI runs the last two on every push.
