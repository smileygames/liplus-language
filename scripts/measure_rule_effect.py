#!/usr/bin/env python3
"""Materialize two contrasting workspaces and run one probe in each.

Stage 2 of the load-bearing measurement (`skills/evolution-rule-effect-measurement`).
Two arms are built from the live workspace, one place is changed in exactly one of
them, and the same probe is put to a separate `claude -p` process in each. The
harness moves the arms; reading the difference between their outputs is the judge's
job and is deliberately not implemented here.

Nothing durable is produced. A run holds an exclusive lock, works under a fixed path
in the system temp directory, and removes both on the way out. Two layers cover the
removal: the `finally` block catches ordinary failure, and the unconditional wipe at
the head of the run catches what `finally` cannot (kill, power loss). The fixed path
is what makes the second layer possible - a per-run unique name would accumulate
debris and turn cleanup back into a procedure.

Accepted tradeoff: the lock carries a timestamp and no PID, so a run lasting longer
than the stale threshold has its lock read as abandoned and another run may enter.
A PID would close it and costs more than the hole is worth; the threshold is set far
above the expected run time instead. Recorded as a hole that is accepted, not as an
absence of holes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

HARNESS_DIRNAME = "liplus-rule-effect"
LOCK_DIRNAME = "lock"
LOCK_STAMP_FILENAME = "acquired-at"
ARMS_DIRNAME = "arms"
STALE_LOCK_SECONDS = 6 * 60 * 60
COPIED_ENTRIES = (".claude", "CLAUDE.md", "Li+config.md")
REQUIRED_ENTRIES = (".claude",)
SETTINGS_FILENAMES = ("settings.json", "settings.local.json")
ARM_COUNT = 2
EDIT_BUDGET = 1

# Applied to text an edit inserts, never to text that was already in the tree.
# An arm that reads "this file is an experimental variant" inside its own rules
# changes the frame it judges in, so the label goes in the run record instead.
SELF_DECLARING_WORD = re.compile(
    r"(?<![a-z])(experiment\w*|variant\w*|test\w*|probe\w*|harness\w*)(?![a-z])",
    re.IGNORECASE,
)
SELF_DECLARING_SUBSTRINGS = ("実験", "変種", "テスト", "検証用", "試験")


class HarnessError(RuntimeError):
    """Base class for every failure this module raises deliberately."""


class LockUnavailable(HarnessError):
    """Another run holds the lock, and it is not old enough to be abandoned."""


class PlanError(HarnessError):
    """The run plan does not describe a valid contrast."""


class EditError(HarnessError):
    """The one place to change could not be located exactly once."""


@dataclass(frozen=True)
class Edit:
    """One change against one copied file. `replace_with` empty means deletion."""

    path: str
    drop: str
    replace_with: str = ""


@dataclass(frozen=True)
class ArmPlan:
    name: str
    edits: tuple[Edit, ...]


@dataclass(frozen=True)
class Plan:
    probe: str
    model: str
    repetitions: int
    arms: tuple[ArmPlan, ...]


def _require_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PlanError(f"plan field {key!r} must be a non-empty string")
    return value


def load_plan(data: Any) -> Plan:
    """Validate a run plan and return it, or raise `PlanError`.

    Two constraints are enforced here rather than left to the operator's care.
    `model` has no default: the arm's model is an experimental condition that the
    run record has to name, and a defaulted one is a condition nobody chose. And
    the edits across both arms must total exactly one, which is the contrast
    principle - two arms differing in more than one place cannot attribute a
    difference in their outputs to any of them.
    """
    if not isinstance(data, dict):
        raise PlanError("plan must be a JSON object")

    probe = _require_str(data, "probe")
    model = _require_str(data, "model")

    repetitions = data.get("repetitions", 1)
    if not isinstance(repetitions, int) or isinstance(repetitions, bool) or repetitions < 1:
        raise PlanError("plan field 'repetitions' must be an integer of at least 1")

    raw_arms = data.get("arms")
    if not isinstance(raw_arms, list) or len(raw_arms) != ARM_COUNT:
        raise PlanError(f"plan field 'arms' must list exactly {ARM_COUNT} arms")

    arms: list[ArmPlan] = []
    names: set[str] = set()
    for raw in raw_arms:
        if not isinstance(raw, dict):
            raise PlanError("each arm must be a JSON object")
        name = _require_str(raw, "name")
        if name in names:
            raise PlanError(f"arm name {name!r} is used twice")
        names.add(name)
        arms.append(ArmPlan(name=name, edits=_load_edits(raw.get("edits", []))))

    total_edits = sum(len(arm.edits) for arm in arms)
    if total_edits != EDIT_BUDGET:
        raise PlanError(
            f"the two arms must differ in exactly {EDIT_BUDGET} place, "
            f"but the plan carries {total_edits}"
        )

    return Plan(probe=probe, model=model, repetitions=repetitions, arms=tuple(arms))


def _load_edits(raw_edits: Any) -> tuple[Edit, ...]:
    if not isinstance(raw_edits, list):
        raise PlanError("arm field 'edits' must be a list")

    edits: list[Edit] = []
    for raw in raw_edits:
        if not isinstance(raw, dict):
            raise PlanError("each edit must be a JSON object")
        path = _require_str(raw, "path")
        drop = _require_str(raw, "drop")
        replace_with = raw.get("replace_with", "")
        if not isinstance(replace_with, str):
            raise PlanError("edit field 'replace_with' must be a string")
        _reject_relative_escape(path)
        _reject_uncopied_target(path)
        _reject_self_declaring(replace_with)
        edits.append(Edit(path=path, drop=drop, replace_with=replace_with))
    return tuple(edits)


def _reject_relative_escape(path: str) -> None:
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise PlanError(f"edit path {path!r} must be relative and stay inside the arm")


def _reject_uncopied_target(path: str) -> None:
    head = Path(path).parts[0]
    if head not in COPIED_ENTRIES:
        raise PlanError(
            f"edit path {path!r} targets {head!r}, which the arm does not carry; "
            f"copied entries are {', '.join(COPIED_ENTRIES)}"
        )


def _reject_self_declaring(text: str) -> None:
    """Refuse inserted text that tells the arm what it is standing in.

    Measured: an arm that read such a note in its own source added a caveat that
    its verdict was not for production use. The label belongs in the run record
    and the issue, outside the artifact the arm reads.
    """
    hit = SELF_DECLARING_WORD.search(text)
    if hit:
        raise PlanError(f"inserted text names the run itself: {hit.group(0)!r}")
    for marker in SELF_DECLARING_SUBSTRINGS:
        if marker in text:
            raise PlanError(f"inserted text names the run itself: {marker!r}")


def harness_root(base_dir: Path | None = None) -> Path:
    """Fixed working path. Under temp, so no debris sits in anybody's project root."""
    base = base_dir or Path(tempfile.gettempdir())
    return base / HARNESS_DIRNAME


def lock_age_seconds(lock_dir: Path, now: datetime) -> float:
    """Age of a held lock, from its timestamp file, falling back to directory mtime.

    The fallback covers a run killed between taking the directory and writing the
    stamp. Without it that window wedges the harness permanently, and unwedging it
    would be a manual procedure - the shape this design replaces with structure.
    """
    stamp = lock_dir / LOCK_STAMP_FILENAME
    try:
        acquired = datetime.fromisoformat(stamp.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        try:
            mtime = lock_dir.stat().st_mtime
        except OSError:
            return 0.0
        acquired = datetime.fromtimestamp(mtime, tz=timezone.utc)
    if acquired.tzinfo is None:
        acquired = acquired.replace(tzinfo=timezone.utc)
    return (now - acquired).total_seconds()


def acquire_lock(
    root: Path,
    now: datetime | None = None,
    stale_after: float = STALE_LOCK_SECONDS,
) -> Path:
    """Take the exclusive lock, or raise `LockUnavailable`.

    `mkdir` is the whole mechanism: it either creates the directory or raises. That
    turns "take care not to run two of these at once" into "the second one cannot
    start". The lock holds a timestamp and no PID (see the module docstring's
    accepted tradeoff).
    """
    moment = now or datetime.now(timezone.utc)
    root.mkdir(parents=True, exist_ok=True)
    lock_dir = root / LOCK_DIRNAME

    try:
        lock_dir.mkdir()
    except FileExistsError:
        age = lock_age_seconds(lock_dir, moment)
        if age <= stale_after:
            raise LockUnavailable(
                f"{lock_dir} is held (age {age:.0f}s, stale threshold {stale_after:.0f}s)"
            ) from None
        shutil.rmtree(lock_dir, ignore_errors=True)
        try:
            lock_dir.mkdir()
        except FileExistsError:
            raise LockUnavailable(f"{lock_dir} could not be retaken") from None

    (lock_dir / LOCK_STAMP_FILENAME).write_text(moment.isoformat(), encoding="utf-8")
    return lock_dir


def release_lock(lock_dir: Path) -> None:
    shutil.rmtree(lock_dir, ignore_errors=True)


def _force_writable_and_retry(func: Any, path: str, _exc: BaseException) -> None:
    """Clear what made the entry unremovable, then try the removal again.

    Measured on this harness: an arm's copied `.claude` refused `rmdir` with
    WinError 5 while sitting empty, and the same path removed cleanly from a shell.
    The live `.claude` carries the Windows read-only attribute; `copytree` copies
    file metadata, so every arm inherits it, and Windows refuses to unlink a
    read-only entry. Nothing about it is transient - a retry alone waits forever,
    so the handler is a chmod rather than a sleep.

    Both the entry and its parent are cleared, because the two platforms put the
    obstacle in different places. On Windows the read-only attribute sits on the
    entry being removed. On POSIX a file is unlinked through its directory, so a
    copied-off write bit on the parent is what refuses, and clearing the child
    alone would leave the removal failing for the same reason it already did.
    """
    parent = Path(path).parent
    for candidate in (parent, Path(path)):
        try:
            os.chmod(candidate, stat.S_IRWXU)
        except OSError:
            pass
    func(path)


def remove_tree(path: Path) -> None:
    """Remove a directory tree, including entries the copy marked read-only.

    The two cleanup layers this module rests on are only as good as their ability
    to actually delete. A wipe that raises at the head of a run aborts it before it
    launches anything and hands the operator a manual `rm -rf` - the procedure this
    design replaces with structure.
    """
    if not path.exists():
        return
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_force_writable_and_retry)
    else:  # pragma: no cover - exercised only on hosts below 3.12
        shutil.rmtree(
            path,
            onerror=lambda func, target, _info: _force_writable_and_retry(
                func, target, RuntimeError()
            ),
        )


def reset_work_dir(root: Path) -> Path:
    """Wipe and recreate the arms directory unconditionally, leaving the lock alone.

    This is the second of the two cleanup layers. It runs before anything is built,
    so a previous run that died where `finally` could not reach still leaves nothing
    behind for this one to read.
    """
    arms_dir = root / ARMS_DIRNAME
    if arms_dir.exists():
        remove_tree(arms_dir)
    arms_dir.mkdir(parents=True)
    return arms_dir


def find_workspace_root(start: Path) -> Path:
    """Nearest ancestor of `start` holding a `.claude/` directory."""
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".claude").is_dir():
            return candidate
    raise HarnessError(f"no workspace root with a .claude directory at or above {start}")


def materialize_arm(
    source_root: Path, arm_root: Path, *, neutralize: bool = True
) -> list[str]:
    """Copy the always-loaded surface of `source_root` into a fresh arm.

    `.git` is not among the copied entries, so the arm has no remote by
    construction rather than by a step that removes one.

    `neutralize` defaults to removing the arm's hooks, which is what this module's
    own contrast requires and what `neutralize_hooks` gives its reason for. It is a
    keyword rather than a fixture because a measurement whose variable *is* the
    presence of hooks cannot have them removed from both arms
    (`scripts/probe_skill_firing.py`). The default carries the contrast principle;
    the parameter carries the one case that principle does not cover.
    """
    for entry in REQUIRED_ENTRIES:
        if not (source_root / entry).exists():
            raise HarnessError(f"{source_root} carries no {entry}")

    arm_root.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for entry in COPIED_ENTRIES:
        source = source_root / entry
        if not source.exists():
            continue
        destination = arm_root / entry
        if source.is_dir():
            shutil.copytree(source, destination, symlinks=True)
        else:
            shutil.copy2(source, destination)
        copied.append(entry)

    if neutralize:
        neutralize_hooks(arm_root)
    return copied


def neutralize_hooks(arm_root: Path) -> list[str]:
    """Remove the arm's hooks, so nothing injects material into its session.

    A live session-start hook emits orientation text of its own, which lands in one
    arm's context as readily as the other's but is not the one place the plan
    changed. Leaving it in place adds a second difference between runs.
    """
    removed: list[str] = []
    hooks_dir = arm_root / ".claude" / "hooks"
    if hooks_dir.exists():
        shutil.rmtree(hooks_dir)
        removed.append(str(Path(".claude") / "hooks"))

    for filename in SETTINGS_FILENAMES:
        settings = arm_root / ".claude" / filename
        if not settings.exists():
            continue
        try:
            data = json.loads(settings.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise HarnessError(f"{settings} could not be read as JSON: {error}") from None
        if isinstance(data, dict) and data.pop("hooks", None) is not None:
            settings.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            removed.append(str(Path(".claude") / filename))
    return removed


def apply_edit(arm_root: Path, edit: Edit) -> None:
    """Apply one edit, requiring its anchor to occur exactly once.

    Zero occurrences means the run would compare two identical arms and report no
    difference - a false negative indistinguishable from a real one. More than one
    means the change lands in several places, and the contrast principle is gone.
    Both are refused rather than reported afterwards.
    """
    target = arm_root / edit.path
    if not target.is_file():
        raise EditError(f"{edit.path} does not exist in {arm_root}")

    text = target.read_text(encoding="utf-8")
    occurrences = text.count(edit.drop)
    if occurrences != 1:
        raise EditError(
            f"anchor for {edit.path} occurs {occurrences} times, expected exactly 1"
        )
    target.write_text(text.replace(edit.drop, edit.replace_with), encoding="utf-8")


def file_digests(root: Path) -> dict[str, str]:
    """sha256 per file, keyed by path relative to `root`."""
    digests: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        digests[path.relative_to(root).as_posix()] = digest
    return digests


def differing_paths(left: Path, right: Path) -> list[str]:
    """Paths whose content differs between two arms, or that only one arm holds."""
    left_digests = file_digests(left)
    right_digests = file_digests(right)
    names = set(left_digests) | set(right_digests)
    return sorted(
        name for name in names if left_digests.get(name) != right_digests.get(name)
    )


def assert_single_contrast(arm_roots: Sequence[Path]) -> list[str]:
    """The built arms must differ in exactly one file. Verified, not assumed.

    The plan's edit budget constrains what was asked for; this constrains what was
    built. Hook neutralization, copy order and the source tree itself sit between
    the two, so the contrast is checked against the arms that will actually run.
    """
    if len(arm_roots) != ARM_COUNT:
        raise HarnessError(f"expected {ARM_COUNT} arms, got {len(arm_roots)}")
    differences = differing_paths(arm_roots[0], arm_roots[1])
    if len(differences) != EDIT_BUDGET:
        raise HarnessError(
            f"the built arms differ in {len(differences)} files "
            f"({', '.join(differences) or 'none'}), expected exactly {EDIT_BUDGET}"
        )
    return differences


def arm_command(probe: str, model: str) -> list[str]:
    """Command line for one arm. A separate process, never a subagent.

    Measured: a subagent reads the rule text as it stood when its parent session
    started, so an on-disk change made during the run reaches it in neither
    direction. Stage 2 exists to compare on-disk states, so the arm has to be a
    process of its own.
    """
    return ["claude", "-p", probe, "--output-format", "json", "--model", model]


def launch_argv(command: Sequence[str]) -> list[str]:
    """The command with its executable resolved against PATH, ready for `subprocess`.

    `claude` is installed by npm, which on Windows puts the executable at
    `claude.CMD` and leaves the extensionless `claude` as a shell script the Win32
    process loader cannot start. Launching without a shell therefore fails with
    WinError 2 while `which claude` in the operator's shell answers fine - the
    launch is refused for a reason the surrounding environment gives no sign of.
    Resolution happens here rather than in `arm_command` so the run record keeps
    naming the command as it was written, not as one host spells it, and it is
    reached only from `launch` below - the one place a process is actually started.
    A resolution done any earlier runs on hosts that launch nothing, which is every
    host running the tests: CI has no `claude` on PATH and does not need one, and a
    harness that raises there is asserting an external dependency the test seam was
    built to do without.
    """
    argv = list(command)
    resolved = shutil.which(argv[0])
    if resolved is None:
        raise HarnessError(f"{argv[0]!r} was not found on PATH")
    argv[0] = resolved
    return argv


def launch(command: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    """Start one arm process. The only caller of `launch_argv`, and the only seam.

    A harness caller that injects its own runner is testing what the surrounding
    function does with a result, not how a process is started, so it substitutes
    this whole function - PATH resolution included. Keeping the resolution inside
    means the substitution actually removes the external dependency instead of
    leaving half of it standing in front of the injected runner.
    """
    return subprocess.run(  # noqa: S603 - fixed argv, no shell
        launch_argv(command), **kwargs
    )


def run_arm(arm_root: Path, probe: str, model: str, timeout: float | None = None) -> dict[str, Any]:
    """Launch one arm and capture its output. External dependency; not run in CI."""
    command = arm_command(probe, model)
    completed = launch(
        command,
        cwd=str(arm_root),
        capture_output=True,
        text=True,
        # The arm answers in the workspace's own language, and the host console
        # codepage is not it. Left to the locale default, a Japanese reply raises
        # UnicodeDecodeError inside the reader thread and the run loses a paid
        # invocation to an encoding, not to anything it was measuring.
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def build_run_record(
    plan: Plan,
    source_root: Path,
    differences: Sequence[str],
    results: Sequence[dict[str, Any]],
    started_at: datetime,
) -> dict[str, Any]:
    """The only thing that outlives the run, and it is written outside the work dir."""
    return {
        "started_at": started_at.isoformat(),
        "source_root": str(source_root),
        "model": plan.model,
        "repetitions": plan.repetitions,
        "probe": plan.probe,
        "arms": [
            {"name": arm.name, "edits": [vars(edit) for edit in arm.edits]}
            for arm in plan.arms
        ],
        "differing_paths": list(differences),
        "results": list(results),
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("plan", type=Path, help="JSON run plan")
    parser.add_argument(
        "--source-root",
        type=Path,
        default=None,
        help="workspace root to copy from (default: nearest ancestor with .claude/)",
    )
    parser.add_argument("--base-dir", type=Path, default=None, help="override temp base")
    parser.add_argument("--out", type=Path, default=None, help="write the run record here")
    parser.add_argument(
        "--stale-after",
        type=float,
        default=STALE_LOCK_SECONDS,
        help="seconds after which a held lock is read as abandoned",
    )
    parser.add_argument("--timeout", type=float, default=None, help="per-arm timeout")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="build the arms and verify the contrast without launching them",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    started_at = datetime.now(timezone.utc)

    try:
        plan = load_plan(json.loads(args.plan.read_text(encoding="utf-8")))
        source_root = (args.source_root or find_workspace_root(Path.cwd())).resolve()
    except (OSError, ValueError, HarnessError) as error:
        print(f"measure_rule_effect: {error}", file=sys.stderr)
        return 2

    root = harness_root(args.base_dir)
    try:
        lock_dir = acquire_lock(root, started_at, args.stale_after)
    except LockUnavailable as error:
        print(f"measure_rule_effect: {error}", file=sys.stderr)
        return 3

    try:
        arms_dir = reset_work_dir(root)
        arm_roots: list[Path] = []
        for arm in plan.arms:
            arm_root = arms_dir / arm.name
            materialize_arm(source_root, arm_root)
            for edit in arm.edits:
                apply_edit(arm_root, edit)
            arm_roots.append(arm_root)

        differences = assert_single_contrast(arm_roots)

        results: list[dict[str, Any]] = []
        for arm, arm_root in zip(plan.arms, arm_roots):
            for index in range(plan.repetitions):
                entry: dict[str, Any] = {"arm": arm.name, "run": index + 1}
                if args.dry_run:
                    entry["command"] = arm_command(plan.probe, plan.model)
                else:
                    entry.update(run_arm(arm_root, plan.probe, plan.model, args.timeout))
                results.append(entry)

        record = build_run_record(plan, source_root, differences, results, started_at)
    except HarnessError as error:
        print(f"measure_rule_effect: {error}", file=sys.stderr)
        return 2
    finally:
        try:
            remove_tree(root / ARMS_DIRNAME)
        except OSError:
            pass
        release_lock(lock_dir)

    payload = json.dumps(record, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
