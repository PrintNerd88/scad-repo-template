# AGENTS.md

## Rules

- `src/lib/` is for common files. Parts should live in `src`
- Do not edit `vendor/`.
- Keep the documentation in step with the code: a change to documented behaviour updates it in
  the same commit.
- Measurements belong only in the parameters: their values and Customizer range annotations.
  Do not repeat them in the README, comments, `echo()` literals or commit messages.
- Do not describe complex shapes in detailed prose; nobody can picture them from words. Show a
  render instead.

## Commits

- Use: https://www.conventionalcommits.org
- Write proposed commit messages to a file in .local/, open the file in the code
  editor, wait for user approval before committing. Re-read the file after
  approval in case the user changed anything.
