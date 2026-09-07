"""Behavioural coverage for the cold-start prior-baseline read-back.

Target = the three `adapter/*/hooks/on-session-start.*` implementations
(claude bash / codex bash / codex PowerShell). Issue #1910.

`last_emit_at` was written by every port and read by none. The contract that
gives it a reader is `rules/evolution/cold-start-synthesis.md` Hook Emission
Contract, diff-only bullet, and this file asserts the three ports implement it
identically.

What is pinned and what is not
------------------------------
The contract fixes the emission state the line appears in (diff-only only, not
full emit and not the no-new-material marker), that the stamp it reports is the
one the state file carried, and that an absent or malformed stamp drops the line
without becoming a fail-safe reason. Presentation stays an adapter choice, as it
does for the two date-driven surfaces, so the assertions read the stamp out of
the emission and locate the section by topic rather than matching the banner
text or the sentence around it.

The fixture and the hook runner are reused from
`test_on_session_start_observation_surface` for the reason that file states: a
second copy of that harness would be the copy that drifts.
"""

from __future__ import annotations

import json
import unittest

from test_on_session_start_observation_surface import (
    ADAPTERS,
    FAIL_SAFE_MARK,
    NO_NEW_MATERIAL,
    Workspace,
    emitted_sections,
)


# A stamp planted into the state file between the two runs, so every port is
# asserted against one known value instead of against its own wall clock.
PLANTED_STAMP = "2026-05-11T04:05:06Z"


def baseline_section(hook_output: str) -> str | None:
    """Body of the prior-baseline section, or None when the hook stayed silent.

    Located by topic rather than by exact banner text, for the same reason the
    observation-surface module does it: the banner is an adapter choice.
    """
    for banner, body in emitted_sections(hook_output):
        if "baseline" in banner.lower():
            return body
    return None


def marker_body(hook_output: str) -> str | None:
    """The no-new-material marker body, or None when it was not emitted."""
    for _banner, body in emitted_sections(hook_output):
        if NO_NEW_MATERIAL in body:
            return body
    return None


class PriorBaselineReadBackTest(unittest.TestCase):
    """Two-run fixture: the first run seeds the state, the second reads it back.

    Every case builds one workspace per adapter. `codex_sh` and `codex_ps1`
    share a state-file path, so a shared fixture would put the second of them
    into diff-only mode on what has to be its first run.
    """

    def fixture(self) -> Workspace:
        ws = Workspace()
        self.addCleanup(ws.cleanup)
        ws.seed_coldstart_rule("anchor-token")
        ws.write(ws.shared_memory, "self-evaluation_log.md", "# log\n\n## first entry\n")
        return ws

    def seed_run(self, ws: Workspace, adapter: str) -> str:
        """First run: no state file exists, so this is the fail-safe full emit."""
        output = ws.run(adapter)
        self.assertIn(
            FAIL_SAFE_MARK,
            output,
            f"{adapter}: first run against an empty workspace is not a full emit",
        )
        return output

    def rewrite_state(self, ws: Workspace, adapter: str, stamp: object) -> None:
        """Patch the stamp in the state file the seed run left behind.

        Section fingerprints are kept as written: they are what puts the second
        run into diff-only rather than back into fail-safe. `stamp` of None
        removes the field entirely.
        """
        path = ws.state_file(adapter)
        state = json.loads(path.read_text(encoding="utf-8"))
        if stamp is None:
            state.pop("last_emit_at", None)
        else:
            state["last_emit_at"] = stamp
        path.write_text(json.dumps(state), encoding="utf-8")

    def change_one_section(self, ws: Workspace) -> None:
        """Move one section's body, which is what makes the next run diff-only."""
        ws.write(ws.shared_memory, "self-evaluation_log.md", "# log\n\n## second entry\n")

    def diff_only_run(self, ws: Workspace, adapter: str) -> str:
        output = ws.run(adapter)
        self.assertNotIn(
            FAIL_SAFE_MARK,
            output,
            f"{adapter}: second run fell back to full emit; the state read failed",
        )
        self.assertIsNone(
            marker_body(output),
            f"{adapter}: second run reached the no-new-material marker; "
            "the fixture change did not move a section",
        )
        return output

    # -- the three emission states the contract distinguishes -----------------

    def test_diff_only_reads_back_the_planted_stamp(self) -> None:
        for adapter in ADAPTERS:
            with self.subTest(adapter=adapter):
                ws = self.fixture()
                self.seed_run(ws, adapter)
                self.rewrite_state(ws, adapter, PLANTED_STAMP)
                self.change_one_section(ws)
                section = baseline_section(self.diff_only_run(ws, adapter))
                self.assertIsNotNone(
                    section,
                    f"{adapter}: no prior-baseline section in the diff-only emission",
                )
                self.assertIn(PLANTED_STAMP, section)

    def test_full_emit_carries_no_read_back(self) -> None:
        # Nothing was suppressed, so the prior time is not judgment material.
        for adapter in ADAPTERS:
            with self.subTest(adapter=adapter):
                ws = self.fixture()
                self.assertIsNone(baseline_section(self.seed_run(ws, adapter)))

    def test_no_new_material_marker_carries_no_read_back(self) -> None:
        # The marker already states the session boundary in one line.
        for adapter in ADAPTERS:
            with self.subTest(adapter=adapter):
                ws = self.fixture()
                self.seed_run(ws, adapter)
                self.rewrite_state(ws, adapter, PLANTED_STAMP)
                output = ws.run(adapter)  # nothing changed since the seed run
                self.assertIsNotNone(
                    marker_body(output),
                    f"{adapter}: an unchanged second run did not reach the marker state",
                )
                self.assertIsNone(baseline_section(output))

    def test_unusable_stamp_drops_the_line_without_fail_safe(self) -> None:
        # The fail-safe set is fixed (state missing / unreadable / sha256 / node);
        # an unusable stamp is not on it and does not join it.
        cases = {
            "absent": None,
            "empty": "",
            "not-a-string": 1747000000,
            "wrong-shape": "2026-05-11 04:05:06",
            "trailing-text": "2026-05-11T04:05:06Z extra",
        }
        for adapter in ADAPTERS:
            for label, value in cases.items():
                with self.subTest(adapter=adapter, stamp=label):
                    ws = self.fixture()
                    self.seed_run(ws, adapter)
                    self.rewrite_state(ws, adapter, value)
                    self.change_one_section(ws)
                    output = self.diff_only_run(ws, adapter)
                    self.assertIsNone(
                        baseline_section(output),
                        f"{adapter}: a {label} stamp still produced a read-back line",
                    )

    def test_ports_agree_on_the_emitted_body(self) -> None:
        # Parity is a constraint of its own: a one-port implementation splits
        # what the three adapters report from identical state.
        bodies: dict[str, str | None] = {}
        for adapter in ADAPTERS:
            ws = self.fixture()
            self.seed_run(ws, adapter)
            self.rewrite_state(ws, adapter, PLANTED_STAMP)
            self.change_one_section(ws)
            bodies[adapter] = baseline_section(self.diff_only_run(ws, adapter))
        reference = bodies["claude_sh"]
        self.assertIsNotNone(reference)
        for adapter, body in bodies.items():
            with self.subTest(adapter=adapter):
                self.assertEqual(
                    body,
                    reference,
                    f"{adapter} disagrees with claude_sh on identical state",
                )

    def test_state_file_still_carries_no_identifier(self) -> None:
        # The read-back can only report what the state holds. A new field there
        # would be the change that lets the line start naming a writer, which
        # the issue's constraint set rules out.
        for adapter in ADAPTERS:
            with self.subTest(adapter=adapter):
                ws = self.fixture()
                self.seed_run(ws, adapter)
                state = json.loads(
                    ws.state_file(adapter).read_text(encoding="utf-8")
                )
                self.assertEqual(set(state), {"sections", "last_emit_at"})


if __name__ == "__main__":
    unittest.main()
