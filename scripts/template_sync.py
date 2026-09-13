#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Create projects from this template and keep them in sync with it.

Runs from a template checkout (the directory holding ``template.toml``) and
acts on a child project given as an argument. Nothing here ships to children:
a child carries only ``.template.toml`` -- which template it came from, the
template commit it was last synced to, its token values, feature choices and
per-file overrides. Standard library only, run through uv (the metadata above
asks it for Python >= 3.11); git on PATH.

    uv run scripts/template_sync.py validate            # template self-check
    uv run scripts/template_sync.py new    ../child     # create a project
    uv run scripts/template_sync.py check  ../child     # report drift / updates
    uv run scripts/template_sync.py update ../child     # apply updates, bump the pin

Every tracked template file is classified in template.toml as one of:

    managed  the template owns it: always brought to the template's version;
             local edits are drift (an error).
    merge    both sides edit it: 3-way merged (git merge-file) against the
             template commit the child was last synced to; conflicts are
             written with markers, like git.
    seed     copied when the project is created and never looked at again.

plus ``exclude`` for files that never ship (this script, its test, the
manifest). A child may override any file's strategy in ``[overrides]``,
including ``ignore``.

Template text is normalised before it is compared with, copied to, or merged
into a child: ``<template-only>`` blocks are stripped (always, or -- when
tagged ``feature="x"`` -- only when the child declined that feature), and each
``[tokens]`` literal is replaced by the child's value, in contents and paths.
A marker is a line holding nothing but the tag and the file's comment syntax,
e.g. ``# <template-only>`` or ``<!-- </template-only> -->``.

Exit codes: 0 clean / applied; 1 drift, conflicts, or (``check --strict``)
pending updates; 2 configuration or usage error.
"""

from __future__ import annotations

import argparse
import os
import re
import stat
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

MANIFEST_NAME = "template.toml"
CHILD_CONFIG_NAME = ".template.toml"
MANIFEST_FORMAT = 1
STRATEGIES = ("managed", "merge", "seed")
RULE_KINDS = STRATEGIES + ("exclude",)
CHILD_STRATEGIES = STRATEGIES + ("ignore",)
GITLINK_MODE = "160000"
EXIT_OK, EXIT_DRIFT, EXIT_CONFIG = 0, 1, 2

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_HEX_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")
# Leftover conflict markers from an earlier update. Only the labelled forms:
# a bare "=======" is a legitimate setext heading in Markdown.
_CONFLICT_RE = re.compile(rb"^(?:<{7}|>{7}) ", re.MULTILINE)


class ConfigError(Exception):
    """A fatal problem with a manifest, a child config, or a repository."""


# ---------------------------------------------------------------------------
# git
# ---------------------------------------------------------------------------


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and proc.returncode != 0:
        raise ConfigError(f"git {' '.join(args)} failed in {root}:\n{proc.stderr.strip()}")
    return proc


def git_out(root: Path, *args: str) -> str:
    return git(root, *args).stdout.strip()


def is_git_repo(root: Path) -> bool:
    return git(root, "rev-parse", "--show-toplevel", check=False).returncode == 0


def has_head(root: Path) -> bool:
    return git(root, "rev-parse", "--verify", "-q", "HEAD", check=False).returncode == 0


@dataclass(frozen=True)
class Tracked:
    path: str
    gitlink: bool


def tracked_files(root: Path) -> list[Tracked]:
    """Every path in the index, with submodules flagged (mode 160000)."""
    out = git(root, "ls-files", "-s", "-z").stdout
    result = []
    for rec in out.split("\0"):
        if rec:
            meta, path = rec.split("\t", 1)
            result.append(Tracked(path, meta.split()[0] == GITLINK_MODE))
    return result


def tracked_at(root: Path, commit: str) -> dict[str, bool]:
    """Every path in ``commit``'s tree -> whether it is a submodule."""
    out = git(root, "ls-tree", "-r", "-z", commit).stdout
    result = {}
    for rec in out.split("\0"):
        if rec:
            meta, path = rec.split("\t", 1)
            result[path] = meta.split()[0] == GITLINK_MODE
    return result


def show_at(root: Path, commit: str, path: str) -> bytes:
    proc = subprocess.run(["git", "-C", str(root), "show", f"{commit}:{path}"], capture_output=True)
    if proc.returncode != 0:
        raise ConfigError(f"git show {commit[:7]}:{path} failed:\n{proc.stderr.decode(errors='replace').strip()}")
    return proc.stdout


def head_commit(root: Path) -> str:
    return git_out(root, "rev-parse", "HEAD")


def commit_exists(root: Path, sha: str) -> bool:
    return git(root, "cat-file", "-e", f"{sha}^{{commit}}", check=False).returncode == 0


def is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    return git(root, "merge-base", "--is-ancestor", ancestor, descendant, check=False).returncode == 0


def dirty_tracked(root: Path) -> list[str]:
    """Tracked paths with uncommitted changes (untracked files don't count)."""
    out = git(root, "status", "--porcelain", "--untracked-files=no", "-z").stdout
    return [rec[3:] for rec in out.split("\0") if rec]


def origin_url(root: Path) -> str:
    proc = git(root, "remote", "get-url", "origin", check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def gitlink_sha(root: Path, treeish: str, path: str) -> str | None:
    proc = git(root, "ls-tree", treeish, "--", path, check=False)
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    meta = proc.stdout.split("\t", 1)[0].split()
    return meta[2] if meta[0] == GITLINK_MODE else None


def submodule_entries(root: Path) -> list[tuple[str, str, str]]:
    """(name, path, url) for every entry in ``.gitmodules``."""
    if not (root / ".gitmodules").is_file():
        return []
    proc = git(root, "config", "-f", ".gitmodules", "--get-regexp", r"^submodule\..*\.(path|url)$", check=False)
    entries: dict[str, dict[str, str]] = {}
    for line in proc.stdout.splitlines():
        m = re.match(r"^submodule\.(.+)\.(path|url) (.*)$", line)
        if m:
            entries.setdefault(m.group(1), {})[m.group(2)] = m.group(3)
    return [(name, e["path"], e["url"]) for name, e in entries.items() if "path" in e and "url" in e]


# ---------------------------------------------------------------------------
# Normalisation: <template-only> markers and tokens
# ---------------------------------------------------------------------------

_MARKER_OPEN_RE = re.compile(r'^<template-only(?:\s+feature="([A-Za-z_][A-Za-z0-9_]*)")?>$')
_MARKER_CLOSE = "</template-only>"
_COMMENT_LEAD_RE = re.compile(r"^(?:#+|//+|<!--|/\*+|\*+|;+|--)\s*")
_COMMENT_TAIL_RE = re.compile(r"\s*(?:-->|\*/)$")


def marker_on(line: str) -> tuple[str, str | None] | None:
    """Return ``("open", feature)`` or ``("close", None)`` if the whole line is a marker.

    The line may carry the file's comment syntax and nothing else, so prose
    that merely mentions a marker (in backticks, mid-sentence) never counts.
    """
    core = _COMMENT_LEAD_RE.sub("", line.strip(), count=1)
    core = _COMMENT_TAIL_RE.sub("", core, count=1).strip()
    if core == _MARKER_CLOSE:
        return ("close", None)
    m = _MARKER_OPEN_RE.match(core)
    return ("open", m.group(1)) if m else None


def apply_markers(text: str, enabled: frozenset[str] | None, *, where: str) -> tuple[str, set[str]]:
    """Strip marker lines and the template-only blocks that don't apply to a child.

    An untagged block is always dropped; a ``feature="x"`` block is dropped
    unless ``x`` is in ``enabled``. ``enabled=None`` is validation mode: the
    text is returned unchanged, but balance is still checked and the set of
    referenced feature names is returned.
    """
    out: list[str] = []
    seen: set[str] = set()
    open_at: int | None = None
    open_feature: str | None = None
    swallow_blank = False  # a dropped block sat between blank lines: keep only one
    for n, line in enumerate(text.split("\n"), 1):
        marker = marker_on(line)
        if marker is None:
            in_block = open_at is not None
            keep_block = enabled is None or (open_feature is not None and open_feature in enabled)
            if not in_block or keep_block:
                if not (swallow_blank and line == ""):
                    out.append(line)
                swallow_blank = False
            continue
        kind, feature = marker
        if kind == "open":
            if open_at is not None:
                raise ConfigError(f"{where}:{n}: <template-only> opened inside the block opened at line {open_at}")
            open_at, open_feature = n, feature
            if feature:
                seen.add(feature)
        else:
            if open_at is None:
                raise ConfigError(f"{where}:{n}: </template-only> with no open block")
            dropped = enabled is not None and not (open_feature is not None and open_feature in enabled)
            swallow_blank = dropped and (not out or out[-1] == "")
            open_at = open_feature = None
        if enabled is None:
            out.append(line)
    if open_at is not None:
        raise ConfigError(f"{where}:{open_at}: <template-only> block is never closed")
    return "\n".join(out), seen


def substitute(text: str, tokens: dict[str, str], values: dict[str, str]) -> str:
    """Replace every token literal in one pass, longest literal first."""
    if not tokens:
        return text
    pattern = "|".join(re.escape(lit) for lit in sorted(tokens, key=len, reverse=True))
    return re.sub(pattern, lambda m: values[tokens[m.group(0)]], text)


def is_binary(data: bytes) -> bool:
    return b"\0" in data[:8192]


def normalise(
    data: bytes,
    manifest: Manifest,
    values: dict[str, str],
    enabled: frozenset[str],
    *,
    where: str,
) -> bytes:
    """Template bytes -> what the child should hold (markers, tokens, LF)."""
    if is_binary(data):
        return data
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise ConfigError(f"{where}: not UTF-8 ({e})") from None
    text = text.replace("\r\n", "\n")
    text, _ = apply_markers(text, enabled, where=where)
    if text.endswith("\n"):
        # A stripped block can leave blank lines at EOF; keep the single
        # newline that end-of-file-fixer enforces on the child's side.
        text = text.rstrip("\n") + "\n"
    return substitute(text, manifest.tokens, values).encode("utf-8")


def map_path(path: str, manifest: Manifest, values: dict[str, str]) -> str:
    return substitute(path, manifest.tokens, values)


# ---------------------------------------------------------------------------
# template.toml
# ---------------------------------------------------------------------------


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Path glob -> regex: ``*``/``?`` stop at ``/``; ``**`` spans directories."""
    out = []
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    return re.compile("^" + "".join(out) + "$")


@dataclass(frozen=True)
class Feature:
    name: str
    description: str
    default: bool
    requires: tuple[str, ...]


@dataclass(frozen=True)
class Rule:
    pattern: str
    kind: str  # managed | merge | seed | exclude
    feature: str | None  # None for [base] and exclude
    regex: re.Pattern[str] = field(repr=False, compare=False)

    def matches(self, path: str) -> bool:
        return self.regex.match(path) is not None

    @property
    def where(self) -> str:
        table = "exclude" if self.kind == "exclude" else f"[{'base' if self.feature is None else 'features.' + self.feature}].{self.kind}"
        return f"{table} {self.pattern!r}"


@dataclass(frozen=True)
class Manifest:
    root: Path
    tokens: dict[str, str]  # literal -> value key
    features: dict[str, Feature]
    rules: tuple[Rule, ...]

    @property
    def value_keys(self) -> list[str]:
        return sorted(set(self.tokens.values()))


def _table(raw: object, where: str) -> dict:
    if not isinstance(raw, dict):
        raise ConfigError(f"{where}: expected a table")
    return raw


def _str_list(raw: object, where: str) -> list[str]:
    if not isinstance(raw, list) or not all(isinstance(x, str) and x for x in raw):
        raise ConfigError(f"{where}: expected a list of non-empty strings")
    return raw


def _reject_unknown(raw: dict, allowed: Iterable[str], where: str) -> None:
    unknown = sorted(set(raw) - set(allowed))
    if unknown:
        raise ConfigError(f"{where}: unknown key(s) {', '.join(unknown)}; allowed: {', '.join(allowed)}")


def load_manifest(root: Path) -> Manifest:
    path = root / MANIFEST_NAME
    if not path.is_file():
        raise ConfigError(f"{path}: not found -- is {root} a template checkout?")
    return parse_manifest(path.read_text("utf-8"), root, where=MANIFEST_NAME)


def parse_manifest(text: str, root: Path, *, where: str) -> Manifest:
    try:
        raw = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{where}: {e}") from None
    w = where
    _reject_unknown(raw, ("manifest_format", "tokens", "exclude", "base", "features"), w)
    if raw.get("manifest_format") != MANIFEST_FORMAT:
        raise ConfigError(
            f"{w}: manifest_format = {raw.get('manifest_format')!r}; this tool understands {MANIFEST_FORMAT}"
        )

    tokens: dict[str, str] = {}
    for literal, key in _table(raw.get("tokens", {}), f"{w}: [tokens]").items():
        if not literal or not isinstance(key, str) or not _IDENT_RE.match(key):
            raise ConfigError(f"{w}: [tokens] {literal!r}: value must be an identifier naming a child [values] key")
        tokens[literal] = key

    rules: list[Rule] = []
    for pat in _str_list(raw.get("exclude", []), f"{w}: exclude"):
        rules.append(Rule(pat, "exclude", None, glob_to_regex(pat)))
    base = _table(raw.get("base", {}), f"{w}: [base]")
    _reject_unknown(base, STRATEGIES, f"{w}: [base]")
    for kind in STRATEGIES:
        for pat in _str_list(base.get(kind, []), f"{w}: [base].{kind}"):
            rules.append(Rule(pat, kind, None, glob_to_regex(pat)))

    features: dict[str, Feature] = {}
    for name, tbl in _table(raw.get("features", {}), f"{w}: [features]").items():
        fw = f"{w}: [features.{name}]"
        if not _IDENT_RE.match(name):
            raise ConfigError(f"{fw}: feature names must be identifiers")
        tbl = _table(tbl, fw)
        _reject_unknown(tbl, ("description", "default", "requires", *STRATEGIES), fw)
        description = tbl.get("description", "")
        default = tbl.get("default", True)
        if not isinstance(description, str) or not isinstance(default, bool):
            raise ConfigError(f"{fw}: description must be a string and default a boolean")
        requires = tuple(_str_list(tbl.get("requires", []), f"{fw}.requires"))
        features[name] = Feature(name, description, default, requires)
        for kind in STRATEGIES:
            for pat in _str_list(tbl.get(kind, []), f"{fw}.{kind}"):
                rules.append(Rule(pat, kind, name, glob_to_regex(pat)))

    for f in features.values():
        for req in f.requires:
            if req not in features:
                raise ConfigError(f"{w}: [features.{f.name}] requires unknown feature {req!r}")
    _check_no_cycles(features, w)
    return Manifest(root, tokens, features, tuple(rules))


def _check_no_cycles(features: dict[str, Feature], where: str) -> None:
    state: dict[str, int] = {}  # 1 = on the current path, 2 = done

    def visit(name: str, path: list[str]) -> None:
        if state.get(name) == 2:
            return
        if state.get(name) == 1:
            cycle = path[path.index(name):] + [name]
            raise ConfigError(f"{where}: feature requires cycle: {' -> '.join(cycle)}")
        state[name] = 1
        for req in features[name].requires:
            visit(req, path + [name])
        state[name] = 2

    for name in features:
        visit(name, [])


@dataclass(frozen=True)
class Classified:
    path: str
    kind: str
    feature: str | None
    rule: Rule


def classify_one(manifest: Manifest, path: str) -> Classified | None:
    """The single rule matching ``path``; ``None`` if none; error if several."""
    hits = [r for r in manifest.rules if r.matches(path)]
    if len(hits) > 1:
        raise ConfigError(f"{path}: matched by several rules: " + "; ".join(r.where for r in hits))
    if not hits:
        return None
    return Classified(path, hits[0].kind, hits[0].feature, hits[0])


def classify(manifest: Manifest, paths: Iterable[str]) -> dict[str, Classified]:
    """Classify every path, reporting all unclassified/ambiguous ones at once."""
    result: dict[str, Classified] = {}
    problems: list[str] = []
    for path in paths:
        try:
            cl = classify_one(manifest, path)
        except ConfigError as e:
            problems.append(str(e))
            continue
        if cl is None:
            problems.append(f"{path}: not classified -- add it to {MANIFEST_NAME} (managed, merge, seed, or exclude)")
        else:
            result[path] = cl
    if problems:
        raise ConfigError("\n".join(problems))
    return result


def effective_features(manifest: Manifest, chosen: dict[str, bool]) -> tuple[frozenset[str], list[str]]:
    """Resolve a child's feature choices: defaults, then ``requires`` forcing dependents off."""
    on = {name: f.default for name, f in manifest.features.items()}
    on.update(chosen)
    notes: list[str] = []
    changed = True
    while changed:
        changed = False
        for name, f in manifest.features.items():
            missing = [r for r in f.requires if not on[r]]
            if on[name] and missing:
                on[name] = False
                changed = True
                notes.append(f"feature {name} turned off: it requires {', '.join(missing)}")
    return frozenset(n for n, v in on.items() if v), notes


# ---------------------------------------------------------------------------
# .template.toml
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChildConfig:
    root: Path
    url: str
    commit: str
    values: dict[str, str]
    features: dict[str, bool]
    overrides: dict[str, str]


def child_config_skeleton(manifest: Manifest) -> str:
    return render_child_config(
        manifest,
        url="",
        commit="<template commit this project was created from>",
        values={k: "" for k in manifest.value_keys},
        features={},
    )


def load_child_config(root: Path, manifest: Manifest) -> ChildConfig:
    path = root / CHILD_CONFIG_NAME
    if not path.is_file():
        raise ConfigError(
            f"{path}: not found. Was this project created with `template_sync.py new`? "
            f"If not, write one by hand:\n\n{child_config_skeleton(manifest)}"
        )
    try:
        raw = tomllib.loads(path.read_text("utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: {e}") from None
    w = str(path)
    _reject_unknown(raw, ("template", "values", "features", "overrides"), w)
    t = _table(raw.get("template", {}), f"{w}: [template]")
    _reject_unknown(t, ("url", "commit"), f"{w}: [template]")
    url = t.get("url", "")
    commit = t.get("commit", "")
    if not isinstance(url, str) or not isinstance(commit, str) or not _HEX_RE.match(commit):
        raise ConfigError(f"{w}: [template] needs url (string) and commit (a template commit hash)")

    values = _table(raw.get("values", {}), f"{w}: [values]")
    missing = [k for k in manifest.value_keys if k not in values]
    if missing:
        raise ConfigError(f"{w}: [values] missing {', '.join(missing)} (every template token needs a value)")
    _reject_unknown(values, manifest.value_keys, f"{w}: [values]")
    if not all(isinstance(v, str) for v in values.values()):
        raise ConfigError(f"{w}: [values] must all be strings")

    features = _table(raw.get("features", {}), f"{w}: [features]")
    _reject_unknown(features, manifest.features, f"{w}: [features]")
    if not all(isinstance(v, bool) for v in features.values()):
        raise ConfigError(f"{w}: [features] must all be booleans")

    overrides = _table(raw.get("overrides", {}), f"{w}: [overrides]")
    for p, s in overrides.items():
        if s not in CHILD_STRATEGIES:
            raise ConfigError(f"{w}: [overrides] {p!r} = {s!r}; expected one of {', '.join(CHILD_STRATEGIES)}")
    return ChildConfig(root, url, commit, dict(values), dict(features), dict(overrides))


def toml_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_child_config(
    manifest: Manifest,
    *,
    url: str,
    commit: str,
    values: dict[str, str],
    features: dict[str, bool],
) -> str:
    lines = [
        f"# {CHILD_CONFIG_NAME} -- which template this project came from and how it is",
        "# kept in sync. Written by the template's scripts/template_sync.py; `update`",
        "# rewrites `commit`. Edit [values], [features] and [overrides] by hand.",
        "",
        "[template]",
        f"url = {toml_str(url)}",
        f"commit = {toml_str(commit)}",
        "",
        "[values]",
        "# One entry per token the template substitutes, in file contents and paths.",
        *[f"{k} = {toml_str(values[k])}" for k in manifest.value_keys],
        "",
        "[features]",
    ]
    if manifest.features:
        lines.append("# Optional template features; a declined feature's files are not tracked.")
        for name, f in manifest.features.items():
            if f.description:
                lines.append(f"# {f.description}")
            lines.append(f"{name} = {'true' if features.get(name, f.default) else 'false'}")
    else:
        lines.append("# (the template declares no optional features)")
    lines += [
        "",
        "[overrides]",
        "# Per-file strategy overrides, keyed by path as listed in the template's",
        "# template.toml: managed, merge, seed, or ignore. For example:",
        '#   ".gitignore" = "merge"    # I add my own ignores; merge template changes in',
        '#   "Makefile" = "ignore"     # forked for good; stop tracking it',
        "",
    ]
    return "\n".join(lines)


def bump_pin(path: Path, commit: str) -> None:
    text = path.read_text("utf-8")
    new, n = re.subn(r'(?m)^(\s*commit\s*=\s*)"[^"]*"', lambda m: m.group(1) + toml_str(commit), text, count=1)
    if n != 1:
        raise ConfigError(f"{path}: could not find the `commit = ...` line to update")
    path.write_text(new, "utf-8")


# ---------------------------------------------------------------------------
# Planning a sync
# ---------------------------------------------------------------------------


@dataclass
class FileResult:
    path: str  # template-relative
    child_path: str  # after token substitution
    strategy: str
    status: str = "ok"
    note: str = ""
    content: bytes | None = None  # what `update` writes (None = nothing, or a delete)
    executable: bool = False
    error: bool = False  # exit 1 from `check`
    change: bool = False  # `update` would write or delete


@dataclass
class SyncPlan:
    head: str
    pin: str
    behind: int | None  # commits from pin to HEAD; None if pin is not an ancestor
    notes: list[str]
    results: list[FileResult]
    submodules: list[str]

    @property
    def errors(self) -> list[FileResult]:
        return [r for r in self.results if r.error]

    @property
    def changes(self) -> list[FileResult]:
        return [r for r in self.results if r.change]


def merge_file(mine: bytes, base: bytes, theirs: bytes, labels: tuple[str, str, str]) -> tuple[bytes, int]:
    """3-way merge via ``git merge-file``; returns (result, conflict count)."""
    with tempfile.TemporaryDirectory(prefix="template_sync-") as d:
        paths = []
        for name, data in (("mine", mine), ("base", base), ("theirs", theirs)):
            p = Path(d) / name
            p.write_bytes(data)
            paths.append(str(p))
        proc = subprocess.run(
            ["git", "merge-file", "-p", "--diff3", "-L", labels[0], "-L", labels[1], "-L", labels[2], *paths],
            capture_output=True,
        )
    if proc.returncode < 0 or proc.returncode > 127:
        raise ConfigError(f"git merge-file failed: {proc.stderr.decode(errors='replace').strip()}")
    return proc.stdout, proc.returncode


def decide(
    r: FileResult,
    base: bytes | None,
    theirs: bytes | None,
    mine: bytes | None,
    labels: tuple[str, str, str],
) -> FileResult:
    """Fill in status/content for one file from its three normalised versions.

    ``base``  = template at the child's pin, ``theirs`` = template now,
    ``mine`` = the child's file; ``None`` = absent.
    """
    if r.strategy == "seed":
        if theirs is not None and mine is None and base is None:
            r.status, r.content = "seed-available", theirs
            r.note = "added to the template since the pin; install with --seed"
        return r

    if r.strategy == "merge" and mine is not None and not is_binary(mine) and _CONFLICT_RE.search(mine):
        r.status, r.error, r.note = "markers", True, "unresolved conflict markers from an earlier update"
        return r

    if theirs is None:  # removed from the template since the pin
        if mine is None:
            return r
        if mine == base:
            r.status, r.change, r.note = "delete", True, "removed from the template"
        elif r.strategy == "managed":
            r.status, r.error, r.note = "drift", True, "removed from the template, but edited locally; delete it or override"
        else:
            r.status, r.note = "removed-upstream", "removed from the template; kept because it was edited locally"
        return r

    if mine is None:
        if base is None:
            r.status, r.change, r.content = "new", True, theirs
        elif r.strategy == "managed":
            r.status, r.error, r.content, r.note = "drift", True, theirs, "missing; update restores it"
        else:
            r.status = "local"
            r.note = "deleted locally" + (" (changed in the template since)" if theirs != base else "")
        return r

    if mine == theirs:
        return r

    if r.strategy == "managed":
        r.content = theirs
        if base is not None and mine == base:
            r.status, r.change = "update", True
        else:
            r.status, r.error = "drift", True
            r.note = "edited locally; update overwrites it"
            if base is not None and theirs != base:
                r.note += " (also changed in the template)"
        return r

    # merge
    if base is None:
        r.status, r.note = "local", "added to the template since the pin, and differs from your copy (no base to merge)"
        return r
    if mine == base:
        r.status, r.change, r.content = "update", True, theirs
        return r
    if theirs == base:
        r.status, r.note = "local", "edited locally"
        return r
    if is_binary(mine) or is_binary(base) or is_binary(theirs):
        r.status, r.error, r.note = "conflict", True, "binary; changed on both sides, cannot merge"
        return r
    merged, conflicts = merge_file(mine, base, theirs, labels)
    if conflicts:
        r.status, r.error, r.change, r.content = "conflict", True, True, merged
        r.note = f"{conflicts} conflict(s); update writes the file with markers"
    elif merged == mine:
        r.note = "already contains the template's changes"
    else:
        r.status, r.change, r.content, r.note = "merged", True, merged, "changed on both sides; merges cleanly"
    return r


def child_file_set(
    manifest: Manifest,
    pin_manifest: Manifest,
    cfg: ChildConfig,
    head_paths: dict[str, Classified],
    pin_paths: Iterable[str],
    enabled: frozenset[str],
) -> list[tuple[str, str, str]]:
    """(template path, child path, strategy) for every file the child tracks.

    Paths that exist only at the pin (removed from the template since) are
    classified with the manifest as it was at the pin -- the rules the child
    received them under; unclassifiable ones are skipped.
    """
    result = []
    seen = set(head_paths)
    ordered: list[tuple[str, Classified | None]] = [(p, cl) for p, cl in head_paths.items()]
    for p in pin_paths:
        if p not in seen:
            ordered.append((p, classify_one(pin_manifest, p)))
    for path, cl in sorted(ordered):
        if cl is None or cl.kind == "exclude" or (cl.feature and cl.feature not in enabled):
            continue
        child_path = map_path(path, manifest, cfg.values)
        strategy = cfg.overrides.get(path, cfg.overrides.get(child_path, cl.kind))
        result.append((path, child_path, strategy))
    return result


def build_plan(manifest: Manifest, cfg: ChildConfig, *, include_seed: bool) -> SyncPlan:
    root = manifest.root
    head = head_commit(root)
    if not commit_exists(root, cfg.commit):
        raise ConfigError(
            f"{CHILD_CONFIG_NAME}: pinned template commit {cfg.commit} is not in {root} "
            "(shallow clone, rewritten history, or the wrong template?)"
        )
    pin = git_out(root, "rev-parse", f"{cfg.commit}^{{commit}}")
    behind = int(git_out(root, "rev-list", "--count", f"{pin}..{head}")) if is_ancestor(root, pin, head) else None

    enabled, notes = effective_features(manifest, cfg.features)
    tracked = tracked_files(root)
    head_paths = classify(manifest, [t.path for t in tracked if not t.gitlink])
    at_pin = {p for p, gl in tracked_at(root, pin).items() if not gl}
    try:
        pin_manifest = parse_manifest(
            show_at(root, pin, MANIFEST_NAME).decode("utf-8"), root, where=f"{pin[:7]}:{MANIFEST_NAME}"
        )
    except (ConfigError, UnicodeDecodeError):
        pin_manifest = manifest
        notes.append(
            f"no readable {MANIFEST_NAME} at the pin {pin[:7]}; files removed from the template since "
            "then are classified with the current rules"
        )
    known = set(head_paths) | at_pin
    for p in cfg.overrides:
        if p not in known and p not in {map_path(k, manifest, cfg.values) for k in known}:
            notes.append(f"[overrides] {p!r} matches no template file")

    labels = ("yours", f"template@{pin[:7]}", f"template@{head[:7]}")
    results = []
    for path, child_path, strategy in child_file_set(manifest, pin_manifest, cfg, head_paths, at_pin, enabled):
        r = FileResult(path, child_path, strategy)
        if strategy == "ignore":
            r.status, r.note = "ignored", "by [overrides]"
            results.append(r)
            continue
        theirs = base = mine = None
        if path in head_paths:
            src = root / path
            theirs = normalise(src.read_bytes(), manifest, cfg.values, enabled, where=path)
            r.executable = bool(src.stat().st_mode & stat.S_IXUSR)
        if path in at_pin:
            base = normalise(show_at(root, pin, path), manifest, cfg.values, enabled, where=f"{pin[:7]}:{path}")
        dst = cfg.root / child_path
        if dst.is_file():
            mine = dst.read_bytes()
            if not is_binary(mine):
                mine = mine.replace(b"\r\n", b"\n")
        results.append(decide(r, base, theirs, mine, labels))
        if r.status == "seed-available":
            r.change = include_seed

    submodules = []
    child_has_head = is_git_repo(cfg.root) and has_head(cfg.root)
    urls = {spath: url for _name, spath, url in submodule_entries(root)}
    for t in tracked:
        if not t.gitlink:
            continue
        tsha = gitlink_sha(root, "HEAD", t.path) or "?"
        csha = gitlink_sha(cfg.root, "HEAD", t.path) if child_has_head else None
        if csha is None:
            submodules.append(f"submodule {t.path}: not in the child (git submodule add {urls.get(t.path, '<url>')} {t.path})")
        elif csha != tsha:
            submodules.append(f"submodule {t.path}: template at {tsha[:7]}, child at {csha[:7]} -- bump deliberately")
        else:
            submodules.append(f"submodule {t.path}: in sync at {tsha[:7]}")
    return SyncPlan(head, pin, behind, notes, results, submodules)


def write_result(child_root: Path, r: FileResult) -> None:
    assert r.content is not None
    dst = child_root / r.child_path
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(r.content)
    mode = dst.stat().st_mode
    want = mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH if r.executable else mode & ~(stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    if want != mode:
        os.chmod(dst, want)


def print_plan(plan: SyncPlan, *, show_all: bool) -> None:
    if plan.pin == plan.head:
        where = f"template @ {plan.head[:7]} (child pin is current)"
    elif plan.behind is None:
        where = f"template @ {plan.head[:7]}; child pinned at {plan.pin[:7]}, which is not an ancestor of HEAD"
    else:
        where = f"template @ {plan.head[:7]}; child pinned at {plan.pin[:7]}, {plan.behind} commit(s) behind"
    print(where)
    for n in plan.notes:
        print(f"  note: {n}")
    for r in plan.results:
        if r.status == "ok" and not show_all:
            continue
        loc = r.path if r.path == r.child_path else f"{r.path} -> {r.child_path}"
        print(f"  {r.status:<15} {loc}" + (f"  -- {r.note}" if r.note else ""))
    for s in plan.submodules:
        if show_all or "in sync" not in s:
            print(f"  {s}")
    ok = sum(1 for r in plan.results if r.status == "ok")
    hidden = " (--all lists them)" if ok and not show_all else ""
    print(f"{ok} up to date{hidden}; {len(plan.changes)} pending change(s); {len(plan.errors)} error(s)")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def default_template_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_child(arg: str, manifest: Manifest) -> Path:
    root = Path(arg).resolve()
    if not root.is_dir():
        raise ConfigError(f"{root}: not a directory")
    if root == manifest.root.resolve():
        raise ConfigError(f"{root} is the template itself, not a child (use `validate` here)")
    return root


def require_clean_template(root: Path, *, force: bool, warn_only: bool = False) -> None:
    dirty = dirty_tracked(root)
    if not dirty:
        return
    msg = (
        f"template has uncommitted changes to tracked files ({', '.join(dirty[:5])}"
        f"{', ...' if len(dirty) > 5 else ''}); the pin records HEAD, so what is copied must be what HEAD contains"
    )
    if warn_only:
        print(f"warning: {msg}", file=sys.stderr)
    elif not force:
        raise ConfigError(msg + " -- commit them, or pass --force")


def cmd_validate(args: argparse.Namespace, root: Path) -> int:
    manifest = load_manifest(root)
    tracked = tracked_files(root)
    classified = classify(manifest, [t.path for t in tracked if not t.gitlink])
    errors: list[str] = []
    warnings: list[str] = []

    used = {cl.rule for cl in classified.values()}
    for rule in manifest.rules:
        if rule not in used:
            warnings.append(f"{rule.where} matches no tracked file")

    shipped_text: list[str] = []
    for path, cl in sorted(classified.items()):
        if cl.kind == "exclude":
            continue
        data = (root / path).read_bytes()
        if is_binary(data):
            if cl.kind == "merge":
                errors.append(f"{path}: binary files cannot be `merge` (use managed or seed)")
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            errors.append(f"{path}: not UTF-8")
            continue
        shipped_text.append(text + "\n" + path)
        try:
            _, feats = apply_markers(text, None, where=path)
        except ConfigError as e:
            errors.append(str(e))
            continue
        for f in sorted(feats - set(manifest.features)):
            errors.append(f'{path}: <template-only feature="{f}"> names an undeclared feature')

    for literal in manifest.tokens:
        if not any(literal in t for t in shipped_text):
            warnings.append(f"[tokens] {literal!r} appears in no shipped file or path")

    if errors:
        raise ConfigError("\n".join(errors))
    counts = {k: sum(1 for cl in classified.values() if cl.kind == k) for k in RULE_KINDS}
    gitlinks = [t.path for t in tracked if t.gitlink]
    print(f"{MANIFEST_NAME}: ok -- {len(classified)} tracked files classified: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    if gitlinks:
        print(f"  submodules (managed via .gitmodules): {', '.join(gitlinks)}")
    if manifest.features:
        print("  features: " + ", ".join(f"{n} (default {'on' if f.default else 'off'})" for n, f in manifest.features.items()))
    for w in warnings:
        print(f"  warning: {w}")
    return EXIT_OK


def cmd_check(args: argparse.Namespace, root: Path) -> int:
    manifest = load_manifest(root)
    child_root = resolve_child(args.child, manifest)
    cfg = load_child_config(child_root, manifest)
    require_clean_template(root, force=False, warn_only=True)
    origin = origin_url(root)
    if cfg.url and origin and cfg.url != origin:
        print(f"warning: child was created from {cfg.url}, this template's origin is {origin}", file=sys.stderr)
    plan = build_plan(manifest, cfg, include_seed=False)
    print_plan(plan, show_all=args.all)
    if plan.errors:
        return EXIT_DRIFT
    pending = plan.changes or any(r.status == "seed-available" for r in plan.results)
    return EXIT_DRIFT if args.strict and pending else EXIT_OK


def cmd_update(args: argparse.Namespace, root: Path) -> int:
    manifest = load_manifest(root)
    child_root = resolve_child(args.child, manifest)
    cfg = load_child_config(child_root, manifest)
    require_clean_template(root, force=args.force)
    if not is_git_repo(child_root):
        raise ConfigError(f"{child_root}: not a git repository; update needs one so the result is reviewable")
    dirty = dirty_tracked(child_root)
    if dirty and not args.force:
        raise ConfigError(
            f"child has uncommitted changes ({', '.join(dirty[:5])}{', ...' if len(dirty) > 5 else ''}); "
            "commit or stash them so the update is one reviewable diff, or pass --force"
        )
    plan = build_plan(manifest, cfg, include_seed=args.seed)
    markers = [r.child_path for r in plan.results if r.status == "markers"]
    if markers:
        raise ConfigError("resolve the conflict markers left by the previous update first: " + ", ".join(markers))

    applied = 0
    for r in plan.results:
        if r.status == "delete":
            (child_root / r.child_path).unlink()
            applied += 1
        elif r.content is not None and (r.change or r.status == "drift"):
            write_result(child_root, r)
            applied += 1
    if plan.head != plan.pin:
        bump_pin(child_root / CHILD_CONFIG_NAME, plan.head)
    print_plan(plan, show_all=args.all)
    conflicts = [r for r in plan.results if r.status == "conflict"]
    pin_note = f"; pin {plan.pin[:7]} -> {plan.head[:7]}" if plan.head != plan.pin else ""
    print(f"applied {applied} change(s){pin_note}")
    if conflicts:
        print("resolve the conflict markers, then commit:", ", ".join(r.child_path for r in conflicts))
        return EXIT_DRIFT
    return EXIT_OK


def parse_assignments(items: list[str], allowed: Iterable[str], flag: str) -> dict[str, str]:
    allowed = list(allowed)
    result = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep or key not in allowed:
            raise ConfigError(f"{flag} {item!r}: expected KEY=VALUE with KEY one of {', '.join(allowed) or '(none)'}")
        result[key] = value
    return result


def resolve_values(manifest: Manifest, given: dict[str, str], target: Path, *, yes: bool) -> dict[str, str]:
    """Token values for a new child: --set, else prompt, else the default.

    The default for ``project`` is the target directory's name; for any other
    key it is the template's own literal, so an unset placeholder stays a
    visible placeholder rather than being guessed.
    """
    defaults: dict[str, str] = {}
    for literal, key in manifest.tokens.items():
        defaults.setdefault(key, literal)
    if "project" in defaults:
        defaults["project"] = target.name
    interactive = not yes and sys.stdin.isatty()
    values = {}
    for key in manifest.value_keys:
        if key in given:
            values[key] = given[key]
        elif interactive:
            values[key] = input(f"{key} [{defaults[key]}]: ").strip() or defaults[key]
        else:
            values[key] = defaults[key]
    return values


def cmd_new(args: argparse.Namespace, root: Path) -> int:
    manifest = load_manifest(root)
    target = Path(args.child).resolve()
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise ConfigError(f"{target}: exists and is not an empty directory")
    if target == root.resolve():
        raise ConfigError("target is the template itself")
    require_clean_template(root, force=args.force)
    head = head_commit(root)
    values = resolve_values(manifest, parse_assignments(args.set, manifest.value_keys, "--set"), target, yes=args.yes)
    chosen_raw = parse_assignments(args.feature, manifest.features, "--feature")
    chosen = {}
    for k, v in chosen_raw.items():
        if v.lower() not in ("true", "false"):
            raise ConfigError(f"--feature {k}={v}: expected true or false")
        chosen[k] = v.lower() == "true"
    enabled, notes = effective_features(manifest, chosen)

    tracked = tracked_files(root)
    classified = classify(manifest, [t.path for t in tracked if not t.gitlink])
    gitlinks = [t.path for t in tracked if t.gitlink]
    add_submodules = bool(gitlinks) and not args.no_submodules

    target.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for path, cl in sorted(classified.items()):
        if cl.kind == "exclude" or (cl.feature and cl.feature not in enabled):
            continue
        if path == ".gitmodules" and add_submodules:
            continue  # written after `git submodule add`, which rewrites it
        src = root / path
        r = FileResult(path, map_path(path, manifest, values), cl.kind)
        r.content = normalise(src.read_bytes(), manifest, values, enabled, where=path)
        r.executable = bool(src.stat().st_mode & stat.S_IXUSR)
        write_result(target, r)
        written.append(r.child_path)

    git(target, "init", "-q")
    git(target, "symbolic-ref", "HEAD", "refs/heads/main")
    sub_notes: list[str] = []
    if add_submodules:
        for _name, spath, url in submodule_entries(root):
            sha = gitlink_sha(root, "HEAD", spath)
            git(target, "submodule", "--quiet", "add", url, spath)
            if sha:
                git(target / spath, "fetch", "--quiet", "origin", sha, check=False)
                git(target / spath, "checkout", "--quiet", "--detach", sha)
                git(target, "add", spath)
            sub_notes.append(f"submodule {spath} @ {(sha or '?')[:7]}")
        if ".gitmodules" in classified and classified[".gitmodules"].kind != "exclude":
            r = FileResult(".gitmodules", ".gitmodules", "managed")
            r.content = normalise((root / ".gitmodules").read_bytes(), manifest, values, enabled, where=".gitmodules")
            write_result(target, r)
            written.append(".gitmodules")
    elif gitlinks:
        sub_notes.append(
            "submodules not added (--no-submodules); run: "
            + "; ".join(f"git submodule add {url} {p}" for _n, p, url in submodule_entries(root))
        )

    (target / CHILD_CONFIG_NAME).write_text(
        render_child_config(
            manifest,
            url=origin_url(root),
            commit=head,
            values=values,
            features={n: n in enabled for n in manifest.features},
        ),
        "utf-8",
    )
    git(target, "add", "-A")

    print(f"created {target} from template @ {head[:7]}: {len(written)} files, {CHILD_CONFIG_NAME} written")
    print("  values: " + ", ".join(f"{k}={v!r}" for k, v in values.items()))
    if manifest.features:
        print("  features on: " + (", ".join(sorted(enabled)) or "(none)"))
    for n in notes + sub_notes:
        print(f"  {n}")
    print("everything is staged and nothing is committed: review `git status`, then commit")
    return EXIT_OK


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="template_sync.py",
        description=__doc__.split("\n\n", 1)[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Strategies: managed (template owns it), merge (3-way), seed (copied once).",
    )
    parser.add_argument(
        "--template",
        metavar="DIR",
        help=f"template checkout to act from (default: the one holding this script)",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    p = sub.add_parser("validate", help=f"check {MANIFEST_NAME} classifies every tracked file, markers balance, etc.")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("check", help="report a child's drift and pending updates; writes nothing")
    p.add_argument("child", help="path to the child project")
    p.add_argument("--all", action="store_true", help="also list up-to-date files")
    p.add_argument("--strict", action="store_true", help="exit 1 when updates are pending, not only on drift")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("update", help="apply the template's changes to a child and bump its pin")
    p.add_argument("child", help="path to the child project")
    p.add_argument("--seed", action="store_true", help="also install seed files added to the template since the pin")
    p.add_argument("--force", action="store_true", help="proceed despite uncommitted changes in either repo")
    p.add_argument("--all", action="store_true", help="also list up-to-date files")
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("new", help="create a project from the template")
    p.add_argument("child", help="directory to create (must not exist, or be empty)")
    p.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="token value (repeatable); unset keys default to the directory name for `project`, else the template's literal",
    )
    p.add_argument("--feature", action="append", default=[], metavar="NAME=true|false", help="feature choice (repeatable)")
    p.add_argument("-y", "--yes", action="store_true", help="never prompt; use defaults for unset values")
    p.add_argument("--no-submodules", action="store_true", help="skip `git submodule add` (no network)")
    p.add_argument("--force", action="store_true", help="proceed despite uncommitted changes in the template")
    p.set_defaults(func=cmd_new)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        root = Path(args.template).resolve() if args.template else default_template_root()
        return args.func(args, root)
    except ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_CONFIG


if __name__ == "__main__":
    sys.exit(main())
