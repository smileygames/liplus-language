"""The pure logic of `scripts/probe_skill_firing.py` holds its structural guarantees.

Spec source: issue #1854, the measurement design in its second comment.

Scope. The arm launch (`claude -p`) is an external dependency that consumes external
budget, so it never runs in CI. What is exercised is everything the design turned
from a procedure into a structure - the parts that, when they regress, let a run
complete and report something false:

- the invocation ceiling and the declared budget, which replace "do not exceed ten
  arms" with a plan that cannot ask for an eleventh;
- the skill-vocabulary guard, which replaces "remember not to name the skill in the
  probe" with a probe that is refused for naming it;
- the mandatory control arm, without which a tree where the detector is broken and a
  tree where nothing fires produce the same zero;
- the reading of the observable: a `Skill` tool_use counted from the stream, and an
  unreadable stream kept distinct from a zero count;
- the hooks condition reaching `materialize_arm` per arm, which is the one place this
  harness departs from the companion it borrows from.

`rules/model/subtractive-structural-beauty.md` puts a procedure whose execution is not
guaranteed on the replace-with-a-structure side. These assertions are what keeps those
structures from decaying back into procedures without anything reporting it.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import measure_rule_effect  # noqa: E402
import probe_skill_firing as module  # noqa: E402


def valid_plan_data(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "model": "opus",
        "invocation_budget": 4,
        "arms": [
            {
                "name": "a-on",
                "probe": "Cloudflare Workers の subrequest 上限、いまの最新値は？",
                "hooks": True,
                "repetitions": 3,
            },
            {
                "name": "d",
                "probe": "model-review-output-partition を読んで要約して。",
                "hooks": True,
                "repetitions": 1,
                "control": True,
            },
        ],
    }
    data.update(overrides)
    return data


def stream(*events: dict[str, Any]) -> str:
    return "".join(json.dumps(event, ensure_ascii=False) + "\n" for event in events)


def assistant_tool_use(name: str, tool_id: str = "t1", payload: Any = None) -> dict[str, Any]:
    return {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "text", "text": "thinking out loud"},
                {"type": "tool_use", "id": tool_id, "name": name, "input": payload or {}},
            ]
        },
    }


class PlanValidationTest(unittest.TestCase):
    def test_a_valid_plan_loads(self) -> None:
        plan = module.load_plan(valid_plan_data())
        self.assertEqual(plan.model, "opus")
        self.assertEqual(plan.invocation_budget, 4)
        self.assertEqual([arm.name for arm in plan.arms], ["a-on", "d"])

    def test_the_model_has_no_default(self) -> None:
        data = valid_plan_data()
        del data["model"]
        with self.assertRaises(module.PlanError):
            module.load_plan(data)

    def test_the_declared_budget_must_match_the_arms(self) -> None:
        with self.assertRaises(module.PlanError):
            module.load_plan(valid_plan_data(invocation_budget=5))

    def test_a_budget_above_the_ceiling_is_refused(self) -> None:
        data = valid_plan_data(invocation_budget=module.MAX_INVOCATIONS + 1)
        arms = data["arms"]
        assert isinstance(arms, list)
        arms[0]["repetitions"] = module.MAX_INVOCATIONS
        with self.assertRaises(module.PlanError) as caught:
            module.load_plan(data)
        self.assertIn("ceiling", str(caught.exception))

    def test_the_ceiling_is_ten(self) -> None:
        self.assertEqual(module.MAX_INVOCATIONS, 10)

    def test_a_plan_at_the_ceiling_still_loads(self) -> None:
        data = valid_plan_data(invocation_budget=module.MAX_INVOCATIONS)
        arms = data["arms"]
        assert isinstance(arms, list)
        arms[0]["repetitions"] = module.MAX_INVOCATIONS - 1
        plan = module.load_plan(data)
        self.assertEqual(plan.invocation_budget, module.MAX_INVOCATIONS)

    def test_the_hooks_condition_has_no_default(self) -> None:
        data = valid_plan_data()
        arms = data["arms"]
        assert isinstance(arms, list)
        del arms[0]["hooks"]
        with self.assertRaises(module.PlanError):
            module.load_plan(data)

    def test_a_plan_without_a_control_arm_is_refused(self) -> None:
        data = valid_plan_data(invocation_budget=3)
        arms = data["arms"]
        assert isinstance(arms, list)
        data["arms"] = [arms[0]]
        with self.assertRaises(module.PlanError) as caught:
            module.load_plan(data)
        self.assertIn("control", str(caught.exception))

    def test_duplicate_arm_names_are_refused(self) -> None:
        data = valid_plan_data()
        arms = data["arms"]
        assert isinstance(arms, list)
        arms[1]["name"] = arms[0]["name"]
        with self.assertRaises(module.PlanError):
            module.load_plan(data)

    def test_repetitions_must_be_a_positive_integer(self) -> None:
        data = valid_plan_data()
        arms = data["arms"]
        assert isinstance(arms, list)
        arms[0]["repetitions"] = 0
        with self.assertRaises(module.PlanError):
            module.load_plan(data)


class ProbeVocabularyTest(unittest.TestCase):
    """A probe naming the mechanism has answered its own question before it is put."""

    def _plan_with_probe(self, probe: str) -> dict[str, object]:
        data = valid_plan_data(invocation_budget=2)
        arms = data["arms"]
        assert isinstance(arms, list)
        arms[0]["probe"] = probe
        arms[0]["repetitions"] = 1
        return data

    def test_an_english_skill_mention_is_refused(self) -> None:
        with self.assertRaises(module.PlanError):
            module.load_plan(self._plan_with_probe("Which skill applies here?"))

    def test_a_japanese_skill_mention_is_refused(self) -> None:
        with self.assertRaises(module.PlanError):
            module.load_plan(self._plan_with_probe("どのスキルを使った？"))

    def test_a_skill_name_is_refused(self) -> None:
        with self.assertRaises(module.PlanError):
            module.load_plan(self._plan_with_probe("model-agentic-search について教えて"))

    def test_an_ordinary_probe_passes(self) -> None:
        plan = module.load_plan(
            self._plan_with_probe("この設計のリスクを洗い出して。cron が外部 API を叩く。")
        )
        self.assertEqual(plan.arms[0].repetitions, 1)

    def test_the_control_arm_may_name_the_mechanism(self) -> None:
        plan = module.load_plan(valid_plan_data())
        self.assertTrue(plan.arms[1].control)
        self.assertIn("model-review-output-partition", plan.arms[1].probe)

    def test_an_unrelated_hyphenated_word_is_not_a_skill_name(self) -> None:
        plan = module.load_plan(self._plan_with_probe("well-known な上限値を教えて"))
        self.assertEqual(plan.arms[0].name, "a-on")


class ObservableReadingTest(unittest.TestCase):
    def test_a_skill_tool_use_is_counted(self) -> None:
        captured = stream(
            {"type": "system", "subtype": "init"},
            assistant_tool_use("Skill", "t9", {"skill": "model-source-check"}),
            {"type": "result", "subtype": "success"},
        )
        found = module.skill_invocations(captured)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["id"], "t9")
        self.assertEqual(found[0]["input"], {"skill": "model-source-check"})

    def test_another_tool_is_not_counted(self) -> None:
        captured = stream(assistant_tool_use("WebSearch"), assistant_tool_use("ToolSearch"))
        self.assertEqual(module.skill_invocations(captured), [])

    def test_several_firings_keep_their_order(self) -> None:
        captured = stream(
            assistant_tool_use("Skill", "first"),
            assistant_tool_use("WebSearch", "middle"),
            assistant_tool_use("Skill", "second"),
        )
        self.assertEqual([hit["id"] for hit in module.skill_invocations(captured)], ["first", "second"])

    def test_a_non_json_line_does_not_stop_the_read(self) -> None:
        captured = "warning: something\n" + stream(assistant_tool_use("Skill"))
        self.assertEqual(len(module.skill_invocations(captured)), 1)

    def test_an_unreadable_stream_is_not_a_zero(self) -> None:
        self.assertFalse(module.stream_is_readable(""))
        self.assertFalse(module.stream_is_readable("Error: spend limit reached\n"))
        self.assertTrue(module.stream_is_readable(stream({"type": "result"})))

    def test_the_tally_keeps_unreadable_apart_from_not_fired(self) -> None:
        counts = module.tally(
            [
                {"arm": "a", "skill_tool_use_count": 0, "stream_readable": True},
                {"arm": "a", "skill_tool_use_count": 0, "stream_readable": False},
                {"arm": "a", "skill_tool_use_count": 2, "stream_readable": True},
            ]
        )
        self.assertEqual(counts["a"], {"runs": 3, "fired": 1, "unreadable": 1})


class TerminalResultTest(unittest.TestCase):
    """An arm that failed must say why in the record, or it is re-run blind."""

    def test_the_closing_result_event_is_kept(self) -> None:
        captured = stream(
            {"type": "system", "subtype": "init"},
            {
                "type": "result",
                "subtype": "error_max_turns",
                "is_error": True,
                "num_turns": 12,
                "duration_ms": 41000,
            },
        )
        self.assertEqual(
            module.terminal_result(captured),
            {
                "subtype": "error_max_turns",
                "is_error": True,
                "num_turns": 12,
                "duration_ms": 41000,
            },
        )

    def test_a_stream_with_no_result_event_reports_none(self) -> None:
        self.assertIsNone(module.terminal_result(stream(assistant_tool_use("Skill"))))
        self.assertIsNone(module.terminal_result(""))

    def test_the_last_result_event_wins(self) -> None:
        captured = stream(
            {"type": "result", "subtype": "success", "is_error": False},
            {"type": "result", "subtype": "error_during_execution", "is_error": True},
        )
        verdict = module.terminal_result(captured)
        assert verdict is not None
        self.assertEqual(verdict["subtype"], "error_during_execution")


class RunArmTest(unittest.TestCase):
    def test_the_arm_is_a_separate_process_with_a_named_model(self) -> None:
        command = module.arm_command("probe text", "opus")
        self.assertEqual(command[0], "claude")
        self.assertIn("--model", command)
        self.assertEqual(command[command.index("--model") + 1], "opus")
        self.assertEqual(command[command.index("--output-format") + 1], "stream-json")
        self.assertIn("--verbose", command)

    def test_an_injected_runner_removes_the_external_dependency_entirely(self) -> None:
        """The seam is the whole launch, PATH resolution included.

        Measured on CI: resolving ahead of the injected runner raised
        `'claude' was not found on PATH` on a host that launches nothing.
        """
        seen: dict[str, Any] = {}

        def runner(command, **kwargs):  # type: ignore[no-untyped-def]
            seen["command"] = command
            return SimpleNamespace(returncode=0, stdout=stream({"type": "result"}), stderr="")

        with mock.patch.object(
            measure_rule_effect.shutil, "which", side_effect=AssertionError("resolved")
        ):
            module.run_arm(Path("."), "probe", "opus", runner=runner)

        self.assertEqual(seen["command"], module.arm_command("probe", "opus"))

    def test_the_result_carries_the_observable_and_not_the_whole_stream(self) -> None:
        captured = stream(
            assistant_tool_use("Skill", "t3"),
            {"type": "result", "subtype": "success", "is_error": False},
        )

        def runner(*_args: Any, **_kwargs: Any) -> SimpleNamespace:
            return SimpleNamespace(returncode=0, stdout=captured, stderr="")

        result = module.run_arm(Path("."), "probe", "opus", runner=runner)
        self.assertEqual(result["skill_tool_use_count"], 1)
        self.assertTrue(result["stream_readable"])
        self.assertNotIn("stdout", result)
        self.assertIn("terminal_result", result)


class ArmSelectionTest(unittest.TestCase):
    def test_no_selection_runs_every_arm(self) -> None:
        plan = module.load_plan(valid_plan_data())
        self.assertEqual(module.select_arms(plan, None), plan.arms)

    def test_a_single_arm_can_be_re_run_alone(self) -> None:
        plan = module.load_plan(valid_plan_data())
        selected = module.select_arms(plan, ["d"])
        self.assertEqual([arm.name for arm in selected], ["d"])

    def test_an_unknown_arm_name_is_refused(self) -> None:
        plan = module.load_plan(valid_plan_data())
        with self.assertRaises(module.PlanError):
            module.select_arms(plan, ["b-on"])

    def test_the_record_names_what_the_run_was_narrowed_to(self) -> None:
        plan = module.load_plan(valid_plan_data())
        selected = module.select_arms(plan, ["d"])
        record = module.build_run_record(
            plan,
            Path("/source"),
            selected,
            [{"arm": "d", "skill_tool_use_count": 1, "stream_readable": True}],
            module.datetime.now(module.timezone.utc),
        )
        self.assertEqual(record["selected_arms"], ["d"])
        self.assertEqual(len(record["arms"]), 2)
        self.assertEqual(record["model"], "opus")


class HooksConditionTest(unittest.TestCase):
    """The one place this harness departs from the companion it borrows from."""

    def temp_path(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)

    def make_source_root(self) -> Path:
        root = self.temp_path() / "workspace"
        hooks = root / ".claude" / "hooks"
        hooks.mkdir(parents=True)
        (hooks / "on-user-prompt.sh").write_text("echo gate\n", encoding="utf-8")
        (root / ".claude" / "settings.json").write_text(
            json.dumps({"outputStyle": "character_Instance", "hooks": {"UserPromptSubmit": []}}),
            encoding="utf-8",
        )
        (root / "CLAUDE.md").write_text("# host instruction\n", encoding="utf-8")
        (root / "Li+config.md").write_text("LI_PLUS_MODE=clone\n", encoding="utf-8")
        return root

    def test_the_default_still_removes_hooks(self) -> None:
        source = self.make_source_root()
        arm = self.temp_path() / "arm"
        measure_rule_effect.materialize_arm(source, arm)
        self.assertFalse((arm / ".claude" / "hooks").exists())
        settings = json.loads((arm / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertNotIn("hooks", settings)

    def test_an_arm_can_keep_its_hooks(self) -> None:
        source = self.make_source_root()
        arm = self.temp_path() / "arm"
        measure_rule_effect.materialize_arm(source, arm, neutralize=False)
        self.assertTrue((arm / ".claude" / "hooks" / "on-user-prompt.sh").is_file())
        settings = json.loads((arm / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertIn("hooks", settings)


if __name__ == "__main__":
    unittest.main()
