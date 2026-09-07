#!/usr/bin/env python3
"""Put one probe to several disposable workspaces and record whether a Skill fired.

Companion to `scripts/measure_rule_effect.py`, and built on the same structures:
one exclusive lock, a fixed working path under the system temp directory, two
cleanup layers, and arms materialized from the live workspace's always-loaded
surface. What differs is the question. That harness contrasts two on-disk rule
states against one probe and leaves the reading to a judge. This one holds the
rule text fixed and asks a prior question: does the host invoke a skill at all,
at a moment the skill's own `description` names.

The observable is external. A run captures `claude -p --output-format stream-json`
and counts `tool_use` blocks named `Skill`. Nothing in the probe refers to skills,
so a firing is the host's own semantic match rather than an instruction followed -
and the guard below is what keeps that true: a probe carrying skill vocabulary is
refused, on every arm except the one declared as the detector control.

Why the control is not optional. A tree in which no arm fires is indistinguishable
from a tree in which the detector is broken. The control arm puts the invocation in
the prompt explicitly; if it too returns zero, the run reports nothing about firing
and says so, rather than handing back a zero that reads as a finding.

Each arm names its own `hooks` condition, and nothing defaults it. In the harness
this one borrows from, hook removal is unconditional and deliberately so - a
session-start hook's injected text lands in one arm's context and not the other's,
which is a second difference between arms that are supposed to differ in one place.
Here the presence of hooks is the measured variable itself, so it is carried per arm
and written into the run record.

Budget is structural, not a note in a comment. Every `claude -p` launch spends real
money, so the plan declares its total and the harness refuses a plan whose arms do
not add up to it, or whose total exceeds the ceiling below.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

from measure_rule_effect import (  # noqa: E402
    STALE_LOCK_SECONDS,
    HarnessError,
    LockUnavailable,
    acquire_lock,
    find_workspace_root,
    file_digests,
    harness_root,
    launch,
    materialize_arm,
    release_lock,
    remove_tree,
    reset_work_dir,
)

ARMS_DIRNAME = "arms"
SKILL_TOOL_NAME = "Skill"

# A ceiling, not a target. Raising it is a budget decision belonging to the human
# who granted the spend, so it sits here as one literal rather than being passed
# in per run.
MAX_INVOCATIONS = 10

# Words that would turn the probe into an instruction. The measurement asks whether
# the host reaches a skill unprompted, so a probe naming one - or naming the
# mechanism - has answered its own question before it is put.
SKILL_VOCABULARY = re.compile(
    r"(?<![a-z])skills?(?![a-z])"
    r"|スキル"
    r"|(?<![a-z])(?:model|evolution|operations|task)-[a-z][a-z-]+(?![a-z])",
    re.IGNORECASE,
)


class PlanError(HarnessError):
    """The run plan does not describe a valid measurement."""


@dataclass(frozen=True)
class ArmPlan:
    name: str
    probe: str
    hooks: bool
    repetitions: int
    control: bool


@dataclass(frozen=True)
class Plan:
    model: str
    invocation_budget: int
    arms: tuple[ArmPlan, ...]


def _require_str(data: dict[str, Any], key: str, where: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PlanError(f"{where} field {key!r} must be a non-empty string")
    return value


def _require_bool(data: dict[str, Any], key: str, where: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise PlanError(f"{where} field {key!r} must be present and a boolean")
    return value


def load_plan(data: Any) -> Plan:
    """Validate a run plan and return it, or raise `PlanError`.

    Three constraints are enforced here rather than left to the operator's care:
    the total spend, the probe's silence about skills, and the presence of a
    detector control. Each of them, left unenforced, produces a run that completes
    and reports something false.
    """
    if not isinstance(data, dict):
        raise PlanError("plan must be a JSON object")

    model = _require_str(data, "model", "plan")

    budget = data.get("invocation_budget")
    if not isinstance(budget, int) or isinstance(budget, bool) or budget < 1:
        raise PlanError("plan field 'invocation_budget' must be an integer of at least 1")
    if budget > MAX_INVOCATIONS:
        raise PlanError(
            f"plan declares {budget} invocations, above the ceiling of {MAX_INVOCATIONS}"
        )

    raw_arms = data.get("arms")
    if not isinstance(raw_arms, list) or not raw_arms:
        raise PlanError("plan field 'arms' must be a non-empty list")

    arms: list[ArmPlan] = []
    names: set[str] = set()
    for raw in raw_arms:
        if not isinstance(raw, dict):
            raise PlanError("each arm must be a JSON object")
        name = _require_str(raw, "name", "arm")
        if name in names:
            raise PlanError(f"arm name {name!r} is used twice")
        names.add(name)

        probe = _require_str(raw, "probe", f"arm {name!r}")
        hooks = _require_bool(raw, "hooks", f"arm {name!r}")
        control = raw.get("control", False)
        if not isinstance(control, bool):
            raise PlanError(f"arm {name!r} field 'control' must be a boolean")
        if not control:
            _reject_skill_vocabulary(name, probe)

        repetitions = raw.get("repetitions", 1)
        if (
            not isinstance(repetitions, int)
            or isinstance(repetitions, bool)
            or repetitions < 1
        ):
            raise PlanError(
                f"arm {name!r} field 'repetitions' must be an integer of at least 1"
            )

        arms.append(
            ArmPlan(
                name=name,
                probe=probe,
                hooks=hooks,
                repetitions=repetitions,
                control=control,
            )
        )

    if not any(arm.control for arm in arms):
        raise PlanError(
            "the plan carries no control arm; a run with no detector control cannot "
            "tell a true zero from a broken tree"
        )

    total = sum(arm.repetitions for arm in arms)
    if total != budget:
        raise PlanError(f"the arms total {total} invocations but the plan declares {budget}")

    return Plan(model=model, invocation_budget=budget, arms=tuple(arms))


def _reject_skill_vocabulary(arm_name: str, probe: str) -> None:
    hit = SKILL_VOCABULARY.search(probe)
    if hit:
        raise PlanError(
            f"arm {arm_name!r} probe names the mechanism it measures: {hit.group(0)!r}; "
            "declare the arm as 'control' if the naming is deliberate"
        )


RULES_SUBTREE = Path(".claude") / "rules"


def tree_digest(root: Path) -> str | None:
    """One sha256 over every file under `root`, path and content both.

    `None` when the subtree is absent, which is a fact about the arm rather than an
    error - the caller writes it down as absent instead of omitting the field.
    """
    if not root.exists():
        return None
    per_file = file_digests(root)
    joined = "\n".join(f"{name}:{per_file[name]}" for name in sorted(per_file))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def arm_provenance(arm_root: Path, materialized_at: datetime) -> dict[str, Any]:
    """What this arm actually copied, and when it copied it.

    The first run of this harness recorded neither, and a concurrent edit to the
    shared source tree then left it undecidable which arms had carried the edited
    file - the times had to be reconstructed afterwards from session directories
    that happened to survive. Both fields are cheap and neither can be recovered
    once the arm is wiped, so they are taken at materialization rather than
    inferred later.

    `rules_digest` is carried beside the whole-arm one because the two answer
    different questions. Arms differ in their hooks by design, so the whole-arm
    digest is expected to differ between a hooks-on and a hooks-off arm and says
    nothing on its own; the rules subtree is the part that must be identical
    across every arm of one run, and a mismatch there is the contamination this
    field exists to make visible.
    """
    return {
        "materialized_at": materialized_at.isoformat(),
        "arm_digest": tree_digest(arm_root),
        "rules_digest": tree_digest(arm_root / RULES_SUBTREE),
    }


def arm_command(probe: str, model: str) -> list[str]:
    """Command line for one arm. `stream-json` is what makes the tool calls visible.

    A separate process, never a subagent, for the reason the companion harness
    records: a subagent reads the rule text as it stood when its parent session
    started, so the arm's own on-disk state would not reach it.
    """
    return [
        "claude",
        "-p",
        probe,
        "--output-format",
        "stream-json",
        "--verbose",
        "--model",
        model,
    ]


def skill_invocations(stdout: str) -> list[dict[str, Any]]:
    """Every `Skill` tool_use in a stream-json capture, in the order it appeared."""
    found: list[dict[str, Any]] = []
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        message = event.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and block.get("name") == SKILL_TOOL_NAME:
                found.append({"id": block.get("id"), "input": block.get("input")})
    return found


def terminal_result(stdout: str) -> dict[str, Any] | None:
    """The stream's own closing verdict, reduced to the fields that explain a failure.

    Measured: two arms exited non-zero with an empty stderr and a readable stream, and
    the record kept nothing that said why. `stderr_tail` catches a launch that never
    started; a session that started and then ended badly reports it inside the stream,
    in the closing `result` event, and that is the only place it is written down. An
    arm whose reason for failing is not in the record cannot be re-run deliberately -
    the operator re-runs it blind, and pays for the same failure again.
    """
    latest: dict[str, Any] | None = None
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("type") == "result":
            latest = event
    if latest is None:
        return None
    return {
        key: latest.get(key)
        for key in ("subtype", "is_error", "num_turns", "duration_ms", "result")
        if key in latest
    }


def stream_is_readable(stdout: str) -> bool:
    """At least one line parsed as a JSON object.

    A capture nothing could be read out of is not a zero firing count. It is an
    absent observation, and the two have to stay distinguishable in the record.
    """
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            if isinstance(json.loads(line), dict):
                return True
        except ValueError:
            continue
    return False


def run_arm(
    arm_root: Path,
    probe: str,
    model: str,
    timeout: float | None = None,
    runner: Any = None,
) -> dict[str, Any]:
    """Launch one arm and reduce its stream to the observable. Not run in CI."""
    command = arm_command(probe, model)
    execute = runner or launch
    completed = execute(
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
    invocations = skill_invocations(completed.stdout)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stream_readable": stream_is_readable(completed.stdout),
        "terminal_result": terminal_result(completed.stdout),
        "skill_tool_use_count": len(invocations),
        "skill_tool_uses": invocations,
        "stderr_tail": completed.stderr[-2000:],
    }


def tally(results: Sequence[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Per-arm counts: how many invocations ran, fired, and returned nothing readable.

    `unreadable` is carried beside `fired` rather than folded into it. An arm whose
    stream could not be read has produced no observation at all, and a summary that
    reports it as a non-firing invocation is the false zero this harness exists to
    keep out of the record.
    """
    per_arm: dict[str, dict[str, int]] = {}
    for entry in results:
        bucket = per_arm.setdefault(
            entry["arm"], {"runs": 0, "fired": 0, "unreadable": 0}
        )
        bucket["runs"] += 1
        if entry.get("skill_tool_use_count"):
            bucket["fired"] += 1
        if entry.get("stream_readable") is False:
            bucket["unreadable"] += 1
    return per_arm


def build_run_record(
    plan: Plan,
    source_root: Path,
    selected: Sequence[ArmPlan],
    results: Sequence[dict[str, Any]],
    started_at: datetime,
    provenance: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """The only thing that outlives the run, and it is written outside the work dir."""
    return {
        "started_at": started_at.isoformat(),
        "source_root": str(source_root),
        "model": plan.model,
        "invocation_budget": plan.invocation_budget,
        "selected_arms": [arm.name for arm in selected],
        "provenance": provenance or {},
        "arms": [
            {
                "name": arm.name,
                "probe": arm.probe,
                "hooks": arm.hooks,
                "repetitions": arm.repetitions,
                "control": arm.control,
            }
            for arm in plan.arms
        ],
        "tally": tally(results),
        "results": list(results),
    }


def select_arms(plan: Plan, only: Sequence[str] | None) -> tuple[ArmPlan, ...]:
    """Narrow a plan to the named arms, refusing a name the plan does not carry.

    A re-run of one failed arm must not silently become a re-run of none. The budget
    the plan declares stays the whole run's; a narrowed run spends less, and the run
    record names what it was narrowed to rather than passing for a full measurement.
    """
    if not only:
        return plan.arms
    wanted = list(dict.fromkeys(only))
    known = {arm.name: arm for arm in plan.arms}
    missing = [name for name in wanted if name not in known]
    if missing:
        raise PlanError(f"plan carries no arm named {', '.join(repr(n) for n in missing)}")
    return tuple(known[name] for name in wanted)


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
    parser.add_argument("--timeout", type=float, default=None, help="per-invocation timeout")
    parser.add_argument(
        "--only",
        action="append",
        default=None,
        metavar="ARM",
        help="run only the named arm (repeatable); for re-running a single failed arm",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="build the arms and show the commands without launching them",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    started_at = datetime.now(timezone.utc)

    try:
        plan = load_plan(json.loads(args.plan.read_text(encoding="utf-8")))
        selected = select_arms(plan, args.only)
        source_root = (args.source_root or find_workspace_root(Path.cwd())).resolve()
    except (OSError, ValueError, HarnessError) as error:
        print(f"probe_skill_firing: {error}", file=sys.stderr)
        return 2

    root = harness_root(args.base_dir)
    try:
        lock_dir = acquire_lock(root, started_at, args.stale_after)
    except LockUnavailable as error:
        print(f"probe_skill_firing: {error}", file=sys.stderr)
        return 3

    try:
        arms_dir = reset_work_dir(root)
        results: list[dict[str, Any]] = []
        provenance: dict[str, dict[str, Any]] = {}
        for arm in selected:
            arm_root = arms_dir / arm.name
            materialize_arm(source_root, arm_root, neutralize=not arm.hooks)
            provenance[arm.name] = arm_provenance(arm_root, datetime.now(timezone.utc))
            for index in range(arm.repetitions):
                entry: dict[str, Any] = {
                    "arm": arm.name,
                    "run": index + 1,
                    "hooks": arm.hooks,
                }
                if args.dry_run:
                    entry["command"] = arm_command(arm.probe, plan.model)
                else:
                    entry.update(run_arm(arm_root, arm.probe, plan.model, args.timeout))
                results.append(entry)

        record = build_run_record(
            plan, source_root, selected, results, started_at, provenance
        )
    except HarnessError as error:
        print(f"probe_skill_firing: {error}", file=sys.stderr)
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
