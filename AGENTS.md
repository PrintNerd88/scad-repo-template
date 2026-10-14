# AGENTS.md

## Rules

- `src/lib/` files contain definitions only, take every input as a parameter, and read no
  globals; never add top-level geometry there.
- Relative imports only; never `OPENSCADPATH`.
- Prefer `$fa`/`$fs` over a global `$fn`. `$fn` on a single small feature is fine.
- One top-level call at the bottom of a part file, wrapped in a module.
- Run `make test` and `make stl` before proposing changes; do not commit anything under `out/`.
- Keep the documentation in step with the code: a change to documented behaviour updates it in
  the same commit.
- Do not hardcode `openscad-nightly` or `openscad` — use `$(OPENSCAD)` in the Makefile and
  `make toolchain` to check what resolved. Changes must keep working on both.
- Do not edit `vendor/`.

## Commits

- Use: https://www.conventionalcommits.org
- Write proposed commit messages to a file in .local/, open the file in the code
  editor, wait for user approval before committing. Re-read the file after
  approval in case the user changed anything.
