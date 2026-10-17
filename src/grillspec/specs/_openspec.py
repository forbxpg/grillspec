"""OpenSpec rules: proposal, deltas against living specs, IDs across changes."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, cast

from grillspec.council import resolve_cli, run_tree

from ._parse import parse_markdown
from ._report import ERROR, WARNING, Finding
from ._rules import (
    duplicate_ids,
    log_findings,
    missing_sections,
    relative,
    requirement_findings,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ._parse import Document

CHANGES = Path("openspec") / "changes"
LIVING = Path("openspec") / "specs"
MIN_WHY, MAX_WHY = 50, 1000
MIN_PURPOSE = 50
MAX_DELTAS = 10
ADDED = "ADDED Requirements"
MODIFIED = "MODIFIED Requirements"
REMOVED = "REMOVED Requirements"
RENAMED = "RENAMED Requirements"
_DELTAS = (ADDED, MODIFIED, REMOVED, RENAMED)
_SKIP_SPECS = re.compile(r"^skip_specs:\s*true\s*$", re.MULTILINE)
_FROM = re.compile(r"^\s*[-*]?\s*FROM:", re.MULTILINE)
_RENAME = re.compile(
    r"^\s*[-*]?\s*(FROM|TO):\s*`?\s*#{0,3}\s*(?:Requirement:)?\s*(.*?)\s*`?\s*$",
    re.MULTILINE,
)
_TO = re.compile(r"^\s*[-*]?\s*TO:", re.MULTILINE)


def _key(name: str) -> str:
    """Normalise a requirement name the way OpenSpec matches headers.

    Args:
        name: str - Requirement header text.

    Returns:
        str - Name with runs of whitespace collapsed.

    """
    return " ".join(name.split())


def _capability(path: Path, specs: Path) -> str:
    """Return a spec file's capability: its directory relative to ``specs/``.

    Args:
        path: Path - A ``spec.md`` file.
        specs: Path - The ``specs`` directory it lives under.

    Returns:
        str - The capability path, such as ``identity/user-auth``.

    """
    return path.parent.relative_to(specs).as_posix()


def _spec_files(specs: Path) -> list[Path]:
    """List Markdown files under a ``specs`` directory.

    Args:
        specs: Path - The directory.

    Returns:
        list[Path] - Files in sorted order; empty when it does not exist.

    """
    return sorted(specs.glob("**/*.md")) if specs.is_dir() else []


def living_requirements(root: Path) -> dict[str, set[str]]:
    """Index the requirement names of every living spec.

    Args:
        root: Path - Project root.

    Returns:
        dict[str, set[str]] - Capability to normalised requirement names.

    """
    index: dict[str, set[str]] = {}
    for path in _spec_files(root / LIVING):
        names = {_key(req.name) for req in parse_markdown(path).requirements}
        index[_capability(path, root / LIVING)] = names
    return index


def living_scenarios(root: Path) -> dict[str, tuple[str, str]]:
    """Index the scenario IDs of every living spec.

    Args:
        root: Path - Project root.

    Returns:
        dict[str, tuple[str, str]] - ID to (capability, requirement name).

    """
    index: dict[str, tuple[str, str]] = {}
    for path in _spec_files(root / LIVING):
        capability = _capability(path, root / LIVING)
        for req in parse_markdown(path).requirements:
            for scenario in req.scenarios:
                if scenario.scenario_id:
                    index[scenario.scenario_id] = (capability, _key(req.name))
    return index


def living_unnamed(root: Path) -> dict[tuple[str, str], set[str]]:
    """Index living scenarios that have no ID (written before grillspec).

    Args:
        root: Path - Project root.

    Returns:
        dict[tuple[str, str], set[str]] - (capability, requirement) to the
            exact names of its scenarios without an ID.

    """
    index: dict[tuple[str, str], set[str]] = {}
    for path in _spec_files(root / LIVING):
        capability = _capability(path, root / LIVING)
        for req in parse_markdown(path).requirements:
            names = {s.name for s in req.scenarios if s.scenario_id is None}
            if names:
                index[capability, _key(req.name)] = names
    return index


def _legacy(
    doc: Document,
    capability: str,
    unnamed: dict[tuple[str, str], set[str]],
    findings: list[Finding],
    root: Path,
) -> list[Finding]:
    """Downgrade ``scenario-id`` for MODIFIED scenarios kept from a pre-grillspec spec.

    OpenSpec requires a MODIFIED block to keep its living scenario names exactly, so
    a living scenario without an ID cannot gain one in a delta.

    Args:
        doc: Document - One delta file.
        capability: str - Its capability path.
        unnamed: dict[tuple[str, str], set[str]] - Living scenarios without IDs.
        findings: list[Finding] - Findings for this file.
        root: Path - Project root.

    Returns:
        list[Finding] - The findings, with those scenarios as warnings.

    """
    renamed = {new: old for old, new in renames(doc).items()}
    legacy: set[int] = set()
    for req in doc.requirements:
        if req.section != MODIFIED:
            continue
        name = _key(req.name)
        kept = unnamed.get((capability, renamed.get(name, name)), set())
        legacy.update(s.line for s in req.scenarios if s.name in kept)
    path = relative(doc.path, root)
    why = "kept from a living spec written before grillspec, so it has no ID"
    message = f"{why}; plans can cite it only once openspec/specs gives it one"
    return [
        Finding(WARNING, path, f.line, "scenario-id-legacy", message)
        if f.rule == "scenario-id" and f.path == path and f.line in legacy
        else f
        for f in findings
    ]


def _other_change_ids(
    root: Path, change_id: str, living: dict[str, tuple[str, str]]
) -> dict[str, Path]:
    """Index the scenario IDs that other active changes introduce.

    A MODIFIED scenario that keeps its living ID is not an introduction, so two
    changes may both modify one living requirement.

    Args:
        root: Path - Project root.
        change_id: str - The change being checked (skipped).
        living: dict[str, tuple[str, str]] - Living scenario IDs.

    Returns:
        dict[str, Path] - ID to the file that uses it, relative to the root.

    """
    index: dict[str, Path] = {}
    changes = root / CHANGES
    if not changes.is_dir():
        return index
    for folder in sorted(changes.iterdir()):
        if not folder.is_dir() or folder.name in {"archive", change_id}:
            continue
        for path in _spec_files(folder / "specs"):
            doc = parse_markdown(path)
            capability = _capability(path, folder / "specs")
            renamed = renames(doc)
            for req in doc.requirements:
                for scenario in req.scenarios:
                    scenario_id = scenario.scenario_id
                    if scenario_id is None or (
                        req.section == MODIFIED
                        and scenario_id in living
                        and _kept(req.name, capability, living[scenario_id], renamed)
                    ):
                        continue
                    _ = index.setdefault(scenario_id, relative(path, root))
    return index


def renames(doc: Document) -> dict[str, str]:
    """Read a delta file's RENAMED pairs.

    Args:
        doc: Document - One delta file.

    Returns:
        dict[str, str] - Normalised old name to normalised new name.

    """
    body = doc.sections.get(RENAMED, (0, ""))[1]
    pairs: dict[str, str] = {}
    old: str | None = None
    for match in _RENAME.finditer(body):
        kind, name = match.group(1), match.group(2)
        if kind == "FROM":
            old = _key(name)
        elif old is not None:
            pairs[old] = _key(name)
            old = None
    return pairs


def _kept(
    req_name: str,
    capability: str,
    living_owner: tuple[str, str],
    renamed: dict[str, str],
) -> bool:
    """Tell whether a MODIFIED scenario keeps the ID its living requirement has.

    Args:
        req_name: str - The MODIFIED requirement's name.
        capability: str - Its capability path.
        living_owner: tuple[str, str] - (capability, requirement) owning the ID
            in the living specs.
        renamed: dict[str, str] - This file's RENAMED pairs.

    Returns:
        bool - True when the ID belongs to this requirement, under its old or
            new name.

    """
    owner_cap, owner_req = living_owner
    name = _key(req_name)
    return owner_cap == capability and name in {owner_req, renamed.get(owner_req)}


def _proposal(path: Path, root: Path) -> list[Finding]:
    """Check ``proposal.md``: a Why of 50-1000 characters and a What Changes.

    Args:
        path: Path - The proposal.
        root: Path - Project root.

    Returns:
        list[Finding] - Problems.

    """
    where = relative(path, root)
    if not path.is_file():
        return missing_sections(None, where, ())
    sections = parse_markdown(path).sections
    line, why = sections.get("Why", (0, ""))
    findings: list[Finding] = []
    if not MIN_WHY <= len(why) <= MAX_WHY:
        findings.append(
            Finding(
                ERROR,
                where,
                line,
                "why-length",
                f"'## Why' has {len(why)} characters; it needs {MIN_WHY}-{MAX_WHY}",
            )
        )
    line, what = sections.get("What Changes", (0, ""))
    if not what:
        findings.append(
            Finding(
                ERROR, where, line, "what-changes-empty", "'## What Changes' is empty"
            )
        )
    return findings


def _delta_targets(
    doc: Document, capability: str, living: dict[str, set[str]], root: Path
) -> Iterable[Finding]:
    """Check MODIFIED/REMOVED targets, REMOVED reasons and RENAMED pairs.

    Args:
        doc: Document - One delta file.
        capability: str - Its capability path.
        living: dict[str, set[str]] - Living requirement names per capability.
        root: Path - Project root.

    Yields:
        Finding - Each problem.

    """
    path = relative(doc.path, root)
    known = living.get(capability, set()) | set(renames(doc).values())
    for req in doc.requirements:
        if req.section in {MODIFIED, REMOVED} and _key(req.name) not in known:
            yield Finding(
                ERROR,
                path,
                req.line,
                "delta-target",
                f"{req.name!r} is not in openspec/specs/{capability}/spec.md",
            )
        if req.section == REMOVED and not (
            "**Reason**" in req.text and "**Migration**" in req.text
        ):
            yield Finding(
                ERROR,
                path,
                req.line,
                "removed-reason",
                f"removed {req.name!r} needs **Reason** and **Migration**",
            )
    if RENAMED in doc.sections:
        line, body = doc.sections[RENAMED]
        if not (_FROM.search(body) and _TO.search(body)):
            yield Finding(
                ERROR,
                path,
                line,
                "renamed-from-to",
                "each rename needs a FROM: line and a TO: line",
            )


def _clashes(
    doc: Document,
    capability: str,
    living: dict[str, tuple[str, str]],
    others: dict[str, Path],
    root: Path,
) -> Iterable[Finding]:
    """Find scenario IDs already used by living specs or other changes.

    A MODIFIED scenario may keep the ID its requirement has in the living spec.

    Args:
        doc: Document - One delta file.
        capability: str - Its capability path.
        living: dict[str, tuple[str, str]] - Living scenario IDs.
        others: dict[str, Path] - IDs used by other active changes.
        root: Path - Project root.

    Yields:
        Finding - Each clash.

    """
    path = relative(doc.path, root)
    renamed = renames(doc)
    for req in doc.requirements:
        for scenario in req.scenarios:
            scenario_id = scenario.scenario_id
            if scenario_id is None:
                continue
            if scenario_id in others:
                used = others[scenario_id].as_posix()
                yield Finding(
                    ERROR,
                    path,
                    scenario.line,
                    "scenario-id-clash",
                    f"{scenario_id} is already used by {used}",
                )
            elif scenario_id in living and not (
                req.section == MODIFIED
                and _kept(req.name, capability, living[scenario_id], renamed)
            ):
                owner = living[scenario_id][0]
                yield Finding(
                    ERROR,
                    path,
                    scenario.line,
                    "scenario-id-clash",
                    f"{scenario_id} is already used by openspec/specs/{owner}/spec.md",
                )


def _purpose(doc: Document, capability: str, root: Path) -> Iterable[Finding]:
    """Warn when a new capability's Purpose is missing or too brief.

    Args:
        doc: Document - A delta file for a new capability.
        capability: str - Its capability path.
        root: Path - Project root.

    Yields:
        Finding - The warning, if any.

    """
    line, purpose = doc.sections.get("Purpose", (0, ""))
    need = f"a '## Purpose' of at least {MIN_PURPOSE} characters"
    if len(purpose) < MIN_PURPOSE:
        yield Finding(
            WARNING,
            relative(doc.path, root),
            line,
            "purpose",
            f"new capability {capability!r} needs {need}",
        )


def validate_openspec(root: Path, change_id: str) -> list[Finding]:
    """Check an OpenSpec change folder.

    Args:
        root: Path - Project root.
        change_id: str - Change id.

    Returns:
        list[Finding] - Every problem.

    """
    folder = root / CHANGES / change_id
    findings = _proposal(folder / "proposal.md", root)
    design = folder / "design.md"
    if design.is_file():
        design_doc = parse_markdown(design)
        findings.extend(log_findings(design_doc, design_doc, root))
    deltas = [
        doc
        for doc in map(parse_markdown, _spec_files(folder / "specs"))
        if any(title in doc.sections for title in _DELTAS)
    ]
    findings.extend(_deltas_present(folder, deltas, root))
    living_reqs = living_requirements(root)
    living_ids = living_scenarios(root)
    unnamed = living_unnamed(root)
    others = _other_change_ids(root, change_id, living_ids)
    count = 0
    for doc in deltas:
        capability = _capability(doc.path, folder / "specs")
        findings.extend(
            _legacy(doc, capability, unnamed, requirement_findings(doc, root), root)
        )
        findings.extend(_delta_targets(doc, capability, living_reqs, root))
        findings.extend(_clashes(doc, capability, living_ids, others, root))
        if capability not in living_reqs:
            findings.extend(_purpose(doc, capability, root))
        count += len(doc.requirements)
        count += len(_FROM.findall(doc.sections.get(RENAMED, (0, ""))[1]))
    findings.extend(duplicate_ids(deltas, root))
    if count > MAX_DELTAS:
        findings.append(
            Finding(
                WARNING,
                relative(folder, root),
                0,
                "delta-count",
                f"{count} deltas; consider splitting above {MAX_DELTAS}",
            )
        )
    return findings


def _deltas_present(folder: Path, deltas: list[Document], root: Path) -> list[Finding]:
    """Require deltas, or ``skip_specs: true`` instead of them, never both.

    Args:
        folder: Path - The change folder.
        deltas: list[Document] - Its delta files.
        root: Path - Project root.

    Returns:
        list[Finding] - The error, if any.

    """
    meta = folder / ".openspec.yaml"
    skip = meta.is_file() and bool(_SKIP_SPECS.search(meta.read_text(encoding="utf-8")))
    if deltas and skip:
        message = "skip_specs is set but delta specs exist; remove one of them"
    elif not deltas and not skip:
        hint = "set skip_specs: true when no behaviour changes"
        message = f"no delta: add specs/<capability>/spec.md, or {hint}"
    else:
        return []
    return [Finding(ERROR, relative(meta, root), 0, "deltas", message)]


ADVICE_TIMEOUT = 30


def _unavailable(reason: str) -> tuple[Finding, ...]:
    """Report that the OpenSpec CLI gave no usable answer.

    Args:
        reason: str - Why.

    Returns:
        tuple[Finding, ...] - One warning.

    """
    return (
        Finding(WARNING, Path("openspec"), 0, "openspec", f"unavailable ({reason})"),
    )


def _field(value: object, key: str) -> object:
    """Read a field of a decoded JSON object.

    Args:
        value: object - Decoded value.
        key: str - Field name.

    Returns:
        object - The field, or None when the value is not an object.

    """
    return (
        cast("dict[str, object]", value).get(key) if isinstance(value, dict) else None
    )


def _issues(data: object) -> list[dict[str, object]] | None:
    """Collect the issues of ``openspec validate --json`` output.

    Args:
        data: object - Decoded output.

    Returns:
        list[dict[str, object]] | None - Every issue object; None when the output
            has no ``items`` list.

    """
    items = _field(data, "items")
    if not isinstance(items, list):
        return None
    found: list[dict[str, object]] = []
    for item in cast("list[object]", items):
        issues = _field(item, "issues")
        listed = cast("list[object]", issues) if isinstance(issues, list) else []
        found.extend(
            cast("dict[str, object]", i) for i in listed if isinstance(i, dict)
        )
    return found


def openspec_advice(root: Path, change_id: str) -> tuple[Finding, ...]:
    """Ask an installed ``openspec`` CLI for its own findings, as warnings only.

    Args:
        root: Path - Project root.
        change_id: str - Change id.

    Returns:
        tuple[Finding, ...] - One warning per OpenSpec issue; one ``unavailable``
            warning when the CLI fails, times out or prints something else; none
            when it is not installed.

    """
    executable = resolve_cli("openspec")
    if executable is None:
        return ()
    argv = [executable, "validate", change_id, "--strict", "--json", "--no-interactive"]
    try:
        done = run_tree(argv, stdin=None, timeout=ADVICE_TIMEOUT, cwd=root)
    except OSError as error:
        return _unavailable(str(error))
    if done.returncode is None:
        return _unavailable(f"timeout after {ADVICE_TIMEOUT}s")
    try:
        data = cast("object", json.loads(done.stdout.decode("utf-8", "replace")))
    except ValueError:
        return _unavailable(f"exit {done.returncode}, output is not JSON")
    issues = _issues(data)
    if issues is None:
        return _unavailable("no items in its JSON")
    findings: list[Finding] = []
    for issue in issues:
        where = str(issue.get("path", ""))
        message = f"{issue.get('level', '')} {where}: {issue.get('message', '')}"
        folder = CHANGES / change_id
        path = folder / "specs" / where if where.endswith("spec.md") else folder / where
        findings.append(Finding(WARNING, path, 0, "openspec", message))
    return tuple(findings)
