"""The pure logic of `scripts/measure_rule_effect.py` holds its structural guarantees.

Spec source: issue #1848, and `skills/evolution-rule-effect-measurement/SKILL.md`.

Scope. The arm launch (`claude -p`) is an external dependency that consumes external
budget, so it is not exercised here and never runs in CI. What is exercised is
everything the design turned from a procedure into a structure, which is exactly the
part that fails silently when it regresses:

- the lock, which replaces "take care not to run two at once" with "the second one
  cannot start", including the stale-lock takeover the accepted tradeoff names;
- the two cleanup layers, the unconditional wipe at the head of a run and the
  `finally` removal, and the fact that the wipe does not take the lock with it;
- the contrast principle, held in two places - the plan's edit budget, and the
  verification against the arms as built;
- the guards that turn a silently-wrong run into a refused one: an anchor that
  matches zero or several times, and inserted text that tells the arm what it is
  standing in.

`rules/model/subtractive-structural-beauty.md` puts a procedure whose execution is not
guaranteed on the replace-with-a-structure side. These assertions are what keeps those
structures from decaying back into procedures without anything reporting it.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from unittest import mock
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import measure_rule_effect as module


NOW = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)


def valid_plan_data(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "probe": "A governance restructure with no observable behavior change. Version type?",
        "model": "opus",
        "repetitions": 3,
        "arms": [
            {"name": "a", "edits": []},
            {
                "name": "b",
                "edits": [
                    {"path": ".claude/rules/model/sample.md", "drop": "the anchor line"}
                ],
            },
        ],
    }
    data.update(overrides)
    return data


class TempDirCase(unittest.TestCase):
    def temp_path(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)

    def make_source_root(self, body: str = "keep\nthe anchor line\ntail\n") -> Path:
        root = self.temp_path() / "workspace"
        rules = root / ".claude" / "rules" / "model"
        rules.mkdir(parents=True)
        (rules / "sample.md").write_text(body, encoding="utf-8")
        (root / "CLAUDE.md").write_text("# host instruction\n", encoding="utf-8")
        (root / "Li+config.md").write_text("LI_PLUS_MODE=clone\n", encoding="utf-8")
        return root


class PlanValidationTest(unittest.TestCase):
    def test_a_valid_plan_loads(self) -> None:
        plan = module.load_plan(valid_plan_data())
        self.assertEqual(plan.model, "opus")
        self.assertEqual(plan.repetitions, 3)
        self.assertEqual([arm.name for arm in plan.arms], ["a", "b"])
        self.assertEqual(plan.arms[1].edits[0].replace_with, "")

    def test_the_two_arms_must_differ_in_exactly_one_place(self) -> None:
        """The contrast principle, on the asked-for side."""
        second_edit = {"path": "CLAUDE.md", "drop": "host"}
        too_many = valid_plan_data()
        too_many["arms"][1]["edits"].append(second_edit)  # type: ignore[index]
        with self.assertRaises(module.PlanError):
            module.load_plan(too_many)

        none_at_all = valid_plan_data()
        none_at_all["arms"][1]["edits"] = []  # type: ignore[index]
        with self.assertRaises(module.PlanError):
            module.load_plan(none_at_all)

    def test_the_edit_may_sit_on_either_arm(self) -> None:
        """Which arm carries the change is the operator's call; the budget is not."""
        data = valid_plan_data()
        data["arms"][0]["edits"] = data["arms"][1]["edits"]  # type: ignore[index]
        data["arms"][1]["edits"] = []  # type: ignore[index]
        plan = module.load_plan(data)
        self.assertEqual(len(plan.arms[0].edits), 1)
        self.assertEqual(plan.arms[1].edits, ())

    def test_the_arm_model_has_no_default(self) -> None:
        """Measured: leak rate reversed with the arm's model, so it is a condition."""
        data = valid_plan_data()
        del data["model"]
        with self.assertRaises(module.PlanError):
            module.load_plan(data)

    def test_arm_count_is_fixed_at_two(self) -> None:
        for arms in ([valid_plan_data()["arms"][0]], []):  # type: ignore[index]
            with self.subTest(count=len(arms)):
                with self.assertRaises(module.PlanError):
                    module.load_plan(valid_plan_data(arms=arms))

    def test_duplicate_arm_names_are_refused(self) -> None:
        data = valid_plan_data()
        data["arms"][1]["name"] = "a"  # type: ignore[index]
        with self.assertRaises(module.PlanError):
            module.load_plan(data)

    def test_repetitions_must_be_a_positive_integer(self) -> None:
        for value in (0, -1, "3", 1.5, True):
            with self.subTest(value=value):
                with self.assertRaises(module.PlanError):
                    module.load_plan(valid_plan_data(repetitions=value))

    def test_edit_paths_stay_inside_the_arm(self) -> None:
        for path in ("../outside.md", "/etc/passwd", ".claude/../../escape.md"):
            with self.subTest(path=path):
                data = valid_plan_data()
                data["arms"][1]["edits"][0]["path"] = path  # type: ignore[index]
                with self.assertRaises(module.PlanError):
                    module.load_plan(data)

    def test_edit_paths_must_target_a_copied_entry(self) -> None:
        data = valid_plan_data()
        data["arms"][1]["edits"][0]["path"] = "rules/model/sample.md"  # type: ignore[index]
        with self.assertRaises(module.PlanError):
            module.load_plan(data)

    def test_inserted_text_may_not_name_the_run_itself(self) -> None:
        """Measured: an arm reading such a note downgraded its own verdict."""
        for text in (
            "this file is an experimental copy",
            "variant B",
            "test fixture",
            "この節は実験用",
            "検証用の記述",
        ):
            with self.subTest(text=text):
                data = valid_plan_data()
                data["arms"][1]["edits"][0]["replace_with"] = text  # type: ignore[index]
                with self.assertRaises(module.PlanError):
                    module.load_plan(data)

    def test_ordinary_replacement_text_passes(self) -> None:
        """The guard reads whole words, so `latest` and `contest` are not hits."""
        data = valid_plan_data()
        data["arms"][1]["edits"][0]["replace_with"] = (  # type: ignore[index]
            "the latest release wins the contest"
        )
        plan = module.load_plan(data)
        self.assertIn("latest", plan.arms[1].edits[0].replace_with)


class LockTest(TempDirCase):
    def test_the_second_run_cannot_start(self) -> None:
        root = self.temp_path() / "harness"
        first = module.acquire_lock(root, NOW)
        self.assertTrue(first.is_dir())
        with self.assertRaises(module.LockUnavailable):
            module.acquire_lock(root, NOW)

    def test_the_lock_carries_a_timestamp_and_no_pid(self) -> None:
        """Accepted tradeoff: no PID, so a long run's lock can be read as abandoned."""
        root = self.temp_path() / "harness"
        lock_dir = module.acquire_lock(root, NOW)
        entries = sorted(path.name for path in lock_dir.iterdir())
        self.assertEqual(entries, [module.LOCK_STAMP_FILENAME])
        stamp = (lock_dir / module.LOCK_STAMP_FILENAME).read_text(encoding="utf-8")
        self.assertEqual(datetime.fromisoformat(stamp), NOW)

    def test_a_lock_older_than_the_threshold_is_taken_over(self) -> None:
        root = self.temp_path() / "harness"
        module.acquire_lock(root, NOW)
        later = NOW + timedelta(seconds=module.STALE_LOCK_SECONDS + 1)
        retaken = module.acquire_lock(root, later)
        stamp = (retaken / module.LOCK_STAMP_FILENAME).read_text(encoding="utf-8")
        self.assertEqual(datetime.fromisoformat(stamp), later)

    def test_a_lock_at_the_threshold_is_still_held(self) -> None:
        root = self.temp_path() / "harness"
        module.acquire_lock(root, NOW)
        at_threshold = NOW + timedelta(seconds=module.STALE_LOCK_SECONDS)
        with self.assertRaises(module.LockUnavailable):
            module.acquire_lock(root, at_threshold)

    def test_a_lock_with_no_stamp_falls_back_to_directory_mtime(self) -> None:
        """A run killed between mkdir and the stamp write must not wedge the harness."""
        root = self.temp_path() / "harness"
        lock_dir = module.acquire_lock(root, NOW)
        (lock_dir / module.LOCK_STAMP_FILENAME).unlink()
        age = module.lock_age_seconds(lock_dir, datetime.now(timezone.utc))
        self.assertGreaterEqual(age, 0.0)
        retaken = module.acquire_lock(
            root, datetime.now(timezone.utc), stale_after=-1.0
        )
        self.assertTrue((retaken / module.LOCK_STAMP_FILENAME).is_file())

    def test_release_removes_the_lock(self) -> None:
        root = self.temp_path() / "harness"
        lock_dir = module.acquire_lock(root, NOW)
        module.release_lock(lock_dir)
        self.assertFalse(lock_dir.exists())
        module.release_lock(lock_dir)  # idempotent: `finally` may run after a failure

    def test_release_of_a_never_taken_lock_is_silent(self) -> None:
        module.release_lock(self.temp_path() / "absent" / "lock")


class WorkDirTest(TempDirCase):
    def test_the_head_of_a_run_wipes_what_the_previous_one_left(self) -> None:
        root = self.temp_path() / "harness"
        arms = root / module.ARMS_DIRNAME
        (arms / "a" / ".claude").mkdir(parents=True)
        (arms / "a" / "debris.md").write_text("left behind\n", encoding="utf-8")

        recreated = module.reset_work_dir(root)
        self.assertEqual(recreated, arms)
        self.assertEqual(list(recreated.iterdir()), [])

    def test_a_read_only_entry_does_not_wedge_the_wipe(self) -> None:
        """The copy carries the live tree's read-only attribute; the wipe clears it.

        Measured: an arm's copied `.claude` refused removal while sitting empty, and
        the wipe that raises does so at the *head* of the next run - aborting it
        before it launches anything.
        """
        root = self.temp_path()
        arms = root / module.ARMS_DIRNAME
        nested = arms / "a-off" / ".claude"
        nested.mkdir(parents=True)
        (nested / "settings.json").write_text("{}", encoding="utf-8")
        module.os.chmod(nested / "settings.json", module.stat.S_IREAD)
        module.os.chmod(nested, module.stat.S_IREAD | module.stat.S_IEXEC)

        module.reset_work_dir(root)

        self.assertTrue(arms.is_dir())
        self.assertEqual(list(arms.iterdir()), [])

    def test_removing_an_absent_tree_is_silent(self) -> None:
        module.remove_tree(self.temp_path() / "never-existed")

    def test_the_wipe_does_not_take_the_lock_with_it(self) -> None:
        """The two are siblings on purpose; wiping the lock would defeat it."""
        root = self.temp_path() / "harness"
        lock_dir = module.acquire_lock(root, NOW)
        module.reset_work_dir(root)
        self.assertTrue(lock_dir.is_dir())
        self.assertTrue((lock_dir / module.LOCK_STAMP_FILENAME).is_file())

    def test_the_work_path_is_fixed_under_temp(self) -> None:
        base = self.temp_path()
        self.assertEqual(module.harness_root(base), base / module.HARNESS_DIRNAME)
        self.assertEqual(module.harness_root(base), module.harness_root(base))


class MaterializeTest(TempDirCase):
    def test_an_arm_carries_the_always_loaded_surface_and_no_git(self) -> None:
        source = self.make_source_root()
        (source / ".git").mkdir()
        (source / ".git" / "config").write_text("[remote]\n", encoding="utf-8")
        (source / "unrelated.py").write_text("x = 1\n", encoding="utf-8")

        arm = self.temp_path() / "arm"
        copied = module.materialize_arm(source, arm)

        self.assertEqual(copied, [".claude", "CLAUDE.md", "Li+config.md"])
        self.assertTrue((arm / ".claude" / "rules" / "model" / "sample.md").is_file())
        self.assertFalse((arm / ".git").exists())
        self.assertFalse((arm / "unrelated.py").exists())

    def test_a_source_without_claude_is_refused(self) -> None:
        source = self.temp_path() / "bare"
        source.mkdir()
        with self.assertRaises(module.HarnessError):
            module.materialize_arm(source, self.temp_path() / "arm")

    def test_hooks_are_removed_from_the_arm(self) -> None:
        source = self.make_source_root()
        hooks = source / ".claude" / "hooks"
        hooks.mkdir()
        (hooks / "on-session-start.sh").write_text("echo material\n", encoding="utf-8")
        (source / ".claude" / "settings.json").write_text(
            json.dumps({"outputStyle": "character_Instance", "hooks": {"SessionStart": []}}),
            encoding="utf-8",
        )

        arm = self.temp_path() / "arm"
        module.materialize_arm(source, arm)

        self.assertFalse((arm / ".claude" / "hooks").exists())
        settings = json.loads((arm / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertNotIn("hooks", settings)
        self.assertEqual(settings["outputStyle"], "character_Instance")

    def test_unreadable_settings_stop_the_run(self) -> None:
        """Silently leaving a live hook in place would add a second difference."""
        source = self.make_source_root()
        (source / ".claude" / "settings.json").write_text("{not json", encoding="utf-8")
        with self.assertRaises(module.HarnessError):
            module.materialize_arm(source, self.temp_path() / "arm")

    def test_find_workspace_root_walks_up_to_the_claude_directory(self) -> None:
        source = self.make_source_root()
        nested = source / "a" / "b"
        nested.mkdir(parents=True)
        self.assertEqual(module.find_workspace_root(nested), source.resolve())

    def test_find_workspace_root_reports_when_there_is_none(self) -> None:
        """`.claude` is patched away rather than sought in a bare temp directory.

        A temp directory's own ancestors reach the user's home, which carries a
        `.claude` on a normal developer machine. A test asserting the walk finds
        nothing there would pass or fail on where the host puts its temp files.
        """
        with mock.patch.object(module.Path, "is_dir", return_value=False):
            with self.assertRaises(module.HarnessError):
                module.find_workspace_root(self.temp_path())


class EditTest(TempDirCase):
    def build_arm(self, body: str) -> Path:
        source = self.make_source_root(body)
        arm = self.temp_path() / "arm"
        module.materialize_arm(source, arm)
        return arm

    def test_an_edit_drops_its_anchor(self) -> None:
        arm = self.build_arm("keep\nthe anchor line\ntail\n")
        module.apply_edit(arm, module.Edit(path=".claude/rules/model/sample.md", drop="the anchor line\n"))
        text = (arm / ".claude" / "rules" / "model" / "sample.md").read_text(encoding="utf-8")
        self.assertEqual(text, "keep\ntail\n")

    def test_an_edit_may_replace_rather_than_delete(self) -> None:
        arm = self.build_arm("keep\nthe anchor line\ntail\n")
        module.apply_edit(
            arm,
            module.Edit(
                path=".claude/rules/model/sample.md",
                drop="the anchor line",
                replace_with="a shorter line",
            ),
        )
        text = (arm / ".claude" / "rules" / "model" / "sample.md").read_text(encoding="utf-8")
        self.assertIn("a shorter line", text)

    def test_an_anchor_that_matches_nothing_is_refused(self) -> None:
        """Zero matches would compare two identical arms and report no difference."""
        arm = self.build_arm("keep\ntail\n")
        with self.assertRaises(module.EditError):
            module.apply_edit(arm, module.Edit(path=".claude/rules/model/sample.md", drop="absent"))

    def test_an_ambiguous_anchor_is_refused(self) -> None:
        arm = self.build_arm("the anchor line\nthe anchor line\n")
        with self.assertRaises(module.EditError):
            module.apply_edit(
                arm, module.Edit(path=".claude/rules/model/sample.md", drop="the anchor line")
            )

    def test_a_missing_target_file_is_refused(self) -> None:
        arm = self.build_arm("keep\n")
        with self.assertRaises(module.EditError):
            module.apply_edit(arm, module.Edit(path="CLAUDE.md/nope.md", drop="x"))


class ContrastTest(TempDirCase):
    def build_pair(self, edits: bool = True) -> list[Path]:
        source = self.make_source_root()
        base = self.temp_path() / "arms"
        roots = []
        for name in ("a", "b"):
            arm = base / name
            module.materialize_arm(source, arm)
            roots.append(arm)
        if edits:
            module.apply_edit(
                roots[1], module.Edit(path=".claude/rules/model/sample.md", drop="the anchor line\n")
            )
        return roots

    def test_the_built_arms_differ_in_exactly_one_file(self) -> None:
        """The contrast principle, verified against what was built, not what was asked."""
        roots = self.build_pair()
        self.assertEqual(
            module.assert_single_contrast(roots), [".claude/rules/model/sample.md"]
        )

    def test_identical_arms_are_refused(self) -> None:
        roots = self.build_pair(edits=False)
        with self.assertRaises(module.HarnessError):
            module.assert_single_contrast(roots)

    def test_a_second_difference_is_refused(self) -> None:
        roots = self.build_pair()
        (roots[1] / "CLAUDE.md").write_text("# drifted\n", encoding="utf-8")
        with self.assertRaises(module.HarnessError):
            module.assert_single_contrast(roots)

    def test_a_file_only_one_arm_holds_counts_as_a_difference(self) -> None:
        roots = self.build_pair(edits=False)
        (roots[1] / ".claude" / "extra.md").write_text("added\n", encoding="utf-8")
        self.assertEqual(module.differing_paths(*roots), [".claude/extra.md"])


class CommandAndRecordTest(TempDirCase):
    def test_the_arm_is_a_separate_process_with_a_named_model(self) -> None:
        command = module.arm_command("what is the version type?", "opus")
        self.assertEqual(command[:2], ["claude", "-p"])
        self.assertIn("what is the version type?", command)
        self.assertIn("--output-format", command)
        self.assertIn("opus", command)

    def test_the_executable_is_resolved_against_path_before_launch(self) -> None:
        """npm ships `claude.CMD` on Windows; the extensionless sibling will not start.

        Asserted through a stubbed `which` rather than a real binary, so the check
        holds on a host that has no `claude` installed - which is every CI runner.
        """
        with mock.patch.object(
            module.shutil, "which", return_value=r"C:\npm\claude.CMD"
        ):
            argv = module.launch_argv(["claude", "-p", "probe"])
        self.assertEqual(argv, [r"C:\npm\claude.CMD", "-p", "probe"])

    def test_an_unresolvable_executable_is_refused_by_name(self) -> None:
        with mock.patch.object(module.shutil, "which", return_value=None):
            with self.assertRaises(module.HarnessError) as caught:
                module.launch_argv(["claude", "-p", "probe"])
        self.assertIn("claude", str(caught.exception))

    def test_resolution_happens_inside_the_launch_seam(self) -> None:
        """A caller that substitutes the launch must lose the PATH dependency with it.

        Measured: resolution sitting ahead of an injected runner raised on CI, where
        nothing was ever going to be launched.
        """
        seen: dict[str, object] = {}

        def fake_run(argv, **kwargs):  # type: ignore[no-untyped-def]
            seen["argv"] = argv
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with mock.patch.object(
            module.shutil, "which", return_value="/usr/bin/claude"
        ), mock.patch.object(module.subprocess, "run", fake_run):
            module.launch(["claude", "-p", "probe"], capture_output=True)

        self.assertEqual(seen["argv"], ["/usr/bin/claude", "-p", "probe"])

    def test_the_run_record_names_the_model_and_the_contrast(self) -> None:
        plan = module.load_plan(valid_plan_data())
        record = module.build_run_record(
            plan,
            Path("/workspace"),
            [".claude/rules/model/sample.md"],
            [{"arm": "a", "run": 1}],
            NOW,
        )
        self.assertEqual(record["model"], "opus")
        self.assertEqual(record["repetitions"], 3)
        self.assertEqual(record["differing_paths"], [".claude/rules/model/sample.md"])
        self.assertEqual(record["started_at"], NOW.isoformat())
        json.dumps(record)  # the record has to survive serialization


class MainTest(TempDirCase):
    def write_plan(self, data: dict[str, object]) -> Path:
        path = self.temp_path() / "plan.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def full_plan(self) -> dict[str, object]:
        data = valid_plan_data()
        data["repetitions"] = 2
        data["arms"][1]["edits"][0]["drop"] = "the anchor line\n"  # type: ignore[index]
        return data

    def test_a_dry_run_builds_the_arms_and_leaves_nothing_behind(self) -> None:
        source = self.make_source_root()
        base = self.temp_path()
        out = self.temp_path() / "record.json"
        code = module.main(
            [
                str(self.write_plan(self.full_plan())),
                "--source-root",
                str(source),
                "--base-dir",
                str(base),
                "--out",
                str(out),
                "--dry-run",
            ]
        )
        self.assertEqual(code, 0)

        record = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(record["differing_paths"], [".claude/rules/model/sample.md"])
        self.assertEqual(len(record["results"]), 4)
        self.assertEqual(record["results"][0]["command"][:2], ["claude", "-p"])

        root = module.harness_root(base)
        self.assertFalse((root / module.ARMS_DIRNAME).exists())
        self.assertFalse((root / module.LOCK_DIRNAME).exists())

    def test_a_failing_run_still_releases_the_lock(self) -> None:
        """The removal sits in `finally`, not at the tail of the happy path."""
        source = self.make_source_root()
        base = self.temp_path()
        broken = self.full_plan()
        broken["arms"][1]["edits"][0]["drop"] = "no such anchor"  # type: ignore[index]

        code = module.main(
            [
                str(self.write_plan(broken)),
                "--source-root",
                str(source),
                "--base-dir",
                str(base),
                "--dry-run",
            ]
        )
        self.assertEqual(code, 2)

        root = module.harness_root(base)
        self.assertFalse((root / module.LOCK_DIRNAME).exists())
        self.assertFalse((root / module.ARMS_DIRNAME).exists())

    def test_a_held_lock_stops_the_run_before_it_builds_anything(self) -> None:
        source = self.make_source_root()
        base = self.temp_path()
        module.acquire_lock(module.harness_root(base), datetime.now(timezone.utc))

        code = module.main(
            [
                str(self.write_plan(self.full_plan())),
                "--source-root",
                str(source),
                "--base-dir",
                str(base),
                "--dry-run",
            ]
        )
        self.assertEqual(code, 3)
        self.assertFalse((module.harness_root(base) / module.ARMS_DIRNAME).exists())

    def test_an_invalid_plan_never_takes_the_lock(self) -> None:
        source = self.make_source_root()
        base = self.temp_path()
        invalid = valid_plan_data()
        del invalid["model"]

        code = module.main(
            [
                str(self.write_plan(invalid)),
                "--source-root",
                str(source),
                "--base-dir",
                str(base),
                "--dry-run",
            ]
        )
        self.assertEqual(code, 2)
        self.assertFalse((module.harness_root(base) / module.LOCK_DIRNAME).exists())


if __name__ == "__main__":
    unittest.main()
