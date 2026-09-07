"""Provenance capture in `scripts/probe_skill_firing.py` records what an arm carried.

Spec source: issue #1854. The first run of that harness recorded neither the digest
of what each arm copied nor when it copied it. A concurrent edit to the shared source
tree during the run then left it undecidable from the record which arms had carried
the edited file; the times had to be reconstructed afterwards from session
directories that happened to survive the harness cleanup.

Both facts are destroyed by the cleanup that follows every run, so they cannot be
recovered later - which is why they are asserted here rather than trusted to be
taken. What is exercised:

- a digest that answers to content and to path, so neither an edit nor a move is
  invisible to it;
- the rules-subtree digest kept apart from the whole-arm one, because arms differ in
  their hooks by design and only the rules subtree must match across a run;
- an absent subtree recorded as absent rather than omitted.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import probe_skill_firing as module  # noqa: E402


MOMENT = datetime(2026, 9, 7, 4, 30, 0, tzinfo=timezone.utc)


class TreeDigestTest(unittest.TestCase):
    def temp_path(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)

    def make_tree(self, body: str = "canonical\n") -> Path:
        root = self.temp_path() / "arm"
        rules = root / ".claude" / "rules" / "operations"
        rules.mkdir(parents=True)
        (rules / "main-agent-procedures.md").write_text(body, encoding="utf-8")
        return root

    def test_identical_trees_digest_alike(self) -> None:
        self.assertEqual(
            module.tree_digest(self.make_tree()), module.tree_digest(self.make_tree())
        )

    def test_an_edited_file_changes_the_digest(self) -> None:
        """The contamination this field exists to make visible is a one-file edit."""
        self.assertNotEqual(
            module.tree_digest(self.make_tree()),
            module.tree_digest(self.make_tree("draft body\n")),
        )

    def test_a_moved_file_changes_the_digest(self) -> None:
        """Content alone would miss a rename; the path is folded in for that."""
        moved = self.make_tree()
        target = moved / ".claude" / "rules" / "operations"
        (target / "main-agent-procedures.md").rename(target / "renamed.md")
        self.assertNotEqual(module.tree_digest(self.make_tree()), module.tree_digest(moved))

    def test_an_absent_subtree_is_recorded_as_absent(self) -> None:
        self.assertIsNone(module.tree_digest(self.temp_path() / "never-existed"))


class ArmProvenanceTest(TreeDigestTest):
    def test_the_record_carries_the_time_and_both_digests(self) -> None:
        record = module.arm_provenance(self.make_tree(), MOMENT)
        self.assertEqual(record["materialized_at"], MOMENT.isoformat())
        self.assertIsNotNone(record["arm_digest"])
        self.assertIsNotNone(record["rules_digest"])

    def test_the_rules_digest_ignores_a_difference_outside_the_rules(self) -> None:
        """Arms differ in their hooks by design, so only the rules digest must match."""
        with_hooks = self.make_tree()
        hooks = with_hooks / ".claude" / "hooks"
        hooks.mkdir(parents=True)
        (hooks / "on-user-prompt.sh").write_text("echo gate\n", encoding="utf-8")
        without_hooks = self.make_tree()

        left = module.arm_provenance(with_hooks, MOMENT)
        right = module.arm_provenance(without_hooks, MOMENT)

        self.assertNotEqual(left["arm_digest"], right["arm_digest"])
        self.assertEqual(left["rules_digest"], right["rules_digest"])

    def test_a_contaminated_rules_body_shows_up_on_the_rules_digest(self) -> None:
        left = module.arm_provenance(self.make_tree(), MOMENT)
        right = module.arm_provenance(self.make_tree("draft body\n"), MOMENT)
        self.assertNotEqual(left["rules_digest"], right["rules_digest"])


class RunRecordTest(unittest.TestCase):
    def test_the_run_record_carries_the_provenance_block(self) -> None:
        plan = module.load_plan(
            {
                "model": "opus",
                "invocation_budget": 1,
                "arms": [
                    {
                        "name": "d",
                        "probe": "model-review-output-partition を呼び出して。",
                        "hooks": True,
                        "repetitions": 1,
                        "control": True,
                    }
                ],
            }
        )
        provenance = {"d": {"materialized_at": MOMENT.isoformat(), "arm_digest": "abc"}}
        record = module.build_run_record(
            plan, Path("/source"), plan.arms, [], MOMENT, provenance
        )
        self.assertEqual(record["provenance"], provenance)

    def test_a_record_built_without_provenance_carries_an_empty_block(self) -> None:
        plan = module.load_plan(
            {
                "model": "opus",
                "invocation_budget": 1,
                "arms": [
                    {
                        "name": "d",
                        "probe": "model-review-output-partition を呼び出して。",
                        "hooks": True,
                        "repetitions": 1,
                        "control": True,
                    }
                ],
            }
        )
        record = module.build_run_record(plan, Path("/source"), plan.arms, [], MOMENT)
        self.assertEqual(record["provenance"], {})


if __name__ == "__main__":
    unittest.main()
