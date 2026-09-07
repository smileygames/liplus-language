"""Behavioural coverage for host-supplied string comparisons across the ports.

Target = the values the *host* puts into a hook payload, as opposed to the
values `Li+config.md` puts there (issue #1804, pinned by
`tests/test_config_value_parity.py`). Two of them reach a comparison:

  the SessionStart `source` / matcher — `startup` / `resume` / `clear` /
  `compact` / `fork` — compared by the three `adapter/*/hooks/on-session-start.*`
  ports;

  the PostToolUse `tool_name` — `Bash` — compared by the three
  `adapter/*/hooks/post-tool-use.*` ports.

Issue #1884. The defect is #1804's class on a second axis: PowerShell's `-eq` /
`-ne` / `-in` are case-insensitive by default while `case` and `[[ x == y ]]` in
the two bash ports are not, so one payload produced two different behaviours
depending on which host adapter read it.

  `source: "Resume"` — the bash ports matched no `case` branch and fell to the
  `startup` default, running the full orientation walkthrough; the PowerShell
  `-in` accepted it, `-eq 'startup'` then read false, and the port took the
  continuous-session path instead. One session start, two orientations.

  `tool_name: "bash"` — the bash ports rejected it and exited; the PowerShell
  `-ne 'Bash'` read false, so the port went on to call `gh` and could rewrite a
  PR body from a payload the other two ports declined to act on.

The casing is not the point of dispute and neither port is being asked to accept
a spelling the other rejects. The Claude Code hooks reference enumerates the
`source` literals in lower case and the tool names in PascalCase, but fixes
neither as a guarantee, and no such guarantee is documented on the Codex side
either. So the repair is the one #1804 took: every port compares
case-sensitively, and an off-spec casing lands on the documented default on all
three rather than splitting them.

`Li+config.md`'s 方向3 (name the unrecognized value) is deliberately not carried
over. These values are host-generated, so an unknown one reports a host
specification change, not a configuration mistake the human can correct — a
different axis, and nothing here asserts a warning.

What is pinned and what is not
------------------------------
Both cases read the judgment out of an observable side effect rather than out of
wording. The matcher case reads which branch ran off the diff-only set — whether
the emission carried material that moved since the previous run, and whether the
state baseline was rewritten — because the branch is specified
(`rules/evolution/cold-start-synthesis.md` Hook Emission Contract) while the
banner text around it is an adapter choice. The tool-name case reads whether
`gh` was invoked at all, via a stub that logs its own calls: the guard under
test is the one standing between the payload and that call, and everything past
it (which endpoint, what it returns, what gets appended) belongs to other tests.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path

from test_on_session_start_observation_surface import (
    ADAPTERS,
    BASH,
    HOOK_TIMEOUT,
    NODE,
    PWSH,
    ROOT,
    Workspace,
    posix_path,
    require_runtime,
    slash_path,
)


# ---------------------------------------------------------------------------
# SessionStart matcher
# ---------------------------------------------------------------------------

# Off-spec spellings of the documented literals. Every one of them must resolve
# to the `startup` default on every port: `Startup` included, since a port that
# accepted it into `$matcher` and then compared that value case-sensitively
# would take the continuous-session branch on what the other two ports run as a
# cold start.
MIXED_CASE_MATCHERS = ("Resume", "RESUME", "Compact", "cLear", "Startup")

# The lower-case control. Held to `resume` alone: this file is about casing, and
# which of the documented literals each port accepts is
# `test_on_session_start_observation_surface.py`'s (the codex ports carry no
# `fork` because Codex documents no such SessionStart source — see the Matcher
# notes in `adapter/codex/hooks-config.md` — so that difference is not a casing
# split either).
LOWER_CASE_CONTROL = "resume"

FIRST_TOKEN = "QQCASEDIFFONEQQ"
SECOND_TOKEN = "QQCASEDIFFTWOQQ"


class MatcherCaseTestCase(unittest.TestCase):
    """The `source` value the three on-session-start ports branch on."""

    def prepared_workspace(self, adapter: str) -> tuple[Workspace, bytes]:
        """A workspace that has already taken one startup run.

        The startup run is what creates the diff-only baseline; without it every
        port is in its first-run full-emit mode, where the startup and
        non-startup branches cannot be told apart by what they emit. A fresh
        workspace per adapter is required because the two codex ports share one
        state-file path.
        """
        if adapter in ("claude_sh", "codex_sh") and not NODE:
            require_runtime("node", "diff-only state handling in the shell hooks")
        workspace = Workspace()
        self.addCleanup(workspace.cleanup)
        workspace.seed_coldstart_rule("QQANCHORQQ")
        self.write_self_eval(workspace, FIRST_TOKEN)

        startup = workspace.run(adapter)
        self.assertIn(
            FIRST_TOKEN,
            startup,
            f"{adapter} did not emit the diff-only set on its first run; every "
            "assertion below would then pass without observing a branch",
        )
        state = workspace.state_file(adapter)
        self.assertTrue(
            state.is_file(),
            f"{adapter} did not persist {state}; the baseline-moved assertion "
            "has nothing to compare",
        )

        # Move the diff-only set. A port that re-evaluated it emits the new
        # token; one that took the continuous-session branch cannot.
        self.write_self_eval(workspace, SECOND_TOKEN)
        return workspace, state.read_bytes()

    @staticmethod
    def write_self_eval(workspace: Workspace, token: str) -> None:
        workspace.write(
            workspace.shared_memory,
            "self-evaluation_log.md",
            f"# Self-Evaluation Log\n\n## entry\n{token}\n",
        )

    def run_hook(self, workspace: Workspace, adapter: str, matcher: str) -> str:
        """Run one hook, discarding a run that straddled local midnight.

        Same guard the observation-surface suite applies: the fixture's dates
        are offsets from `date.today()` while the hooks read their own clock.
        """
        started_on = date.today()
        output = workspace.run(adapter, matcher)
        if date.today() != started_on:
            self.skipTest("local date rolled over mid-test; fixture offsets are stale")
        return output

    def test_lower_case_matcher_takes_the_continuous_session_branch(self) -> None:
        """The control the case assertions are read against.

        Without it, a port that ran the startup branch under every input would
        satisfy every assertion in the next test by accident.
        """
        for adapter in ADAPTERS:
            with self.subTest(adapter=adapter):
                workspace, baseline = self.prepared_workspace(adapter)
                emission = self.run_hook(workspace, adapter, LOWER_CASE_CONTROL)
                self.assertNotIn(
                    SECOND_TOKEN,
                    emission,
                    f"{adapter} re-evaluated the diff-only set on the documented "
                    f"{LOWER_CASE_CONTROL!r} matcher",
                )
                self.assertEqual(
                    baseline,
                    workspace.state_file(adapter).read_bytes(),
                    f"{adapter} moved the diff baseline on a continuous session",
                )

    def test_off_spec_casing_falls_to_startup_on_every_port(self) -> None:
        """#1884: `-in` / `-eq` accepted a casing `case` rejected.

        The two directions are not symmetric. The bash ports fall to `startup`,
        which re-orients a session that did not need it — noise. The PowerShell
        port fell to the continuous-session branch, which skips the orientation
        of a session that did need it, and skips it silently.
        """
        for adapter in ADAPTERS:
            for matcher in MIXED_CASE_MATCHERS:
                with self.subTest(adapter=adapter, matcher=matcher):
                    workspace, baseline = self.prepared_workspace(adapter)
                    emission = self.run_hook(workspace, adapter, matcher)
                    self.assertIn(
                        SECOND_TOKEN,
                        emission,
                        f"{adapter} took the continuous-session branch on "
                        f"matcher {matcher!r}; off-spec casing is not a "
                        "documented literal on any port, so it resolves to the "
                        "startup default",
                    )
                    self.assertNotEqual(
                        baseline,
                        workspace.state_file(adapter).read_bytes(),
                        f"{adapter} left the diff baseline untouched on matcher "
                        f"{matcher!r}; a startup run rewrites it",
                    )


# ---------------------------------------------------------------------------
# PostToolUse tool_name
# ---------------------------------------------------------------------------

POST_TOOL_USE = {
    "claude_sh": ROOT / "adapter" / "claude" / "hooks" / "post-tool-use.sh",
    "codex_sh": ROOT / "adapter" / "codex" / "hooks" / "post-tool-use.sh",
    "codex_ps1": ROOT / "adapter" / "codex" / "hooks" / "post-tool-use.ps1",
}

# Off-spec spellings of the one tool name the hooks act on.
MIXED_CASE_TOOL_NAMES = ("bash", "BASH", "bAsh")

ORIGIN_URL = "https://github.com/Liplus-Project/liplus-language.git"


class PostToolUseFixture:
    """A workspace shaped like a project whose `gh pr create` just returned.

    The hook chain past the tool-name guard reaches `gh`, so a stub that records
    its own invocations reports whether the guard let the payload through. The
    stub returns nothing, which stops the chain immediately afterwards: what the
    endpoints return, and what the hook appends, are other tests' subject.
    """

    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="liplus-ptu-"))
        self.home = self.root / "home"
        self.project = self.root / "project"
        self.liplus = self.project / "liplus-language"
        self.liplus.mkdir(parents=True)
        self.stub_bin = self.home / ".local" / "bin"
        self.stub_bin.mkdir(parents=True)
        self.gh_log = self.root / "gh-calls.log"
        self._write_gh_stub()
        self._init_clone()

    def _write_gh_stub(self) -> None:
        unix_log = posix_path(self.gh_log)
        unix_stub = self.stub_bin / "gh"
        unix_stub.write_text(
            f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{unix_log}"\nexit 0\n',
            encoding="utf-8",
        )
        os.chmod(unix_stub, 0o755)
        (self.stub_bin / "gh.cmd").write_text(
            f'@echo off\r\n>>"{self.gh_log}" echo %*\r\nexit /b 0\r\n',
            encoding="ascii",
        )

    def _init_clone(self) -> None:
        """A real repository, because the hooks read `origin` through `git`.

        `repo_from_origin` runs before the first `gh` call on every port, so a
        directory that is not a repository would stop the chain short of the
        probe and make the guard unobservable.
        """
        env = dict(os.environ)
        env["GIT_CONFIG_GLOBAL"] = str(self.root / "gitconfig-absent")
        env["GIT_CONFIG_SYSTEM"] = str(self.root / "gitconfig-absent")
        for args in (
            ["init", "-q"],
            ["remote", "add", "origin", ORIGIN_URL],
        ):
            subprocess.run(
                ["git", "-C", str(self.liplus), *args],
                check=True,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    def gh_was_called(self) -> bool:
        return self.gh_log.is_file() and self.gh_log.read_text(
            encoding="utf-8", errors="replace"
        ).strip() != ""

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def run(self, adapter: str, tool_name: str) -> None:
        if adapter in ("claude_sh", "codex_sh"):
            if not BASH:
                require_runtime("bash", "claude / codex shell hooks")
            if not NODE:
                require_runtime("node", "payload parsing in the shell hooks")
        if adapter == "codex_ps1" and not PWSH:
            require_runtime("pwsh", "codex PowerShell hook")

        hook = POST_TOOL_USE[adapter]
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": tool_name,
            "tool_input": {"command": "gh pr create --fill"},
            "tool_response": {
                "output": "https://github.com/Liplus-Project/liplus-language/pull/4242"
            },
        }
        env = dict(os.environ)
        env.pop("CODEX_PROJECT_DIR", None)
        env.pop("CLAUDE_PROJECT_DIR", None)
        if adapter == "codex_ps1":
            payload["cwd"] = slash_path(self.project)
            command = [PWSH, "-NoProfile", "-NonInteractive", "-File", str(hook)]
            env["PATH"] = str(self.stub_bin) + os.pathsep + env.get("PATH", "")
        else:
            payload["cwd"] = posix_path(self.project)
            command = [BASH, posix_path(hook)]
            env["HOME"] = posix_path(self.home)
            if adapter == "claude_sh":
                # The claude port resolves the project root from the host
                # environment variable; only the codex ports read `cwd`.
                env["CLAUDE_PROJECT_DIR"] = posix_path(self.project)

        subprocess.run(
            command,
            input=json.dumps(payload).encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            timeout=HOOK_TIMEOUT,
        )


class ToolNameCaseTestCase(unittest.TestCase):
    """The `tool_name` value the three post-tool-use ports guard on."""

    def fixture(self) -> PostToolUseFixture:
        fixture = PostToolUseFixture()
        self.addCleanup(fixture.cleanup)
        return fixture

    def test_documented_tool_name_reaches_the_gh_call(self) -> None:
        """The control. Without it the next test passes on a broken chain."""
        for adapter in ADAPTERS:
            with self.subTest(adapter=adapter):
                fixture = self.fixture()
                fixture.run(adapter, "Bash")
                self.assertTrue(
                    fixture.gh_was_called(),
                    f"{adapter} never reached `gh` on the documented tool name; "
                    "the guard under test is then unobservable",
                )

    def test_off_spec_casing_is_rejected_on_every_port(self) -> None:
        """#1884: `-ne 'Bash'` read false on `bash`, so the port acted on it.

        The consequence is not confined to the hook: past this guard the chain
        PATCHes a pull request body, so the port that accepted the payload
        wrote to GitHub on input the other two declined.
        """
        for adapter in ADAPTERS:
            for tool_name in MIXED_CASE_TOOL_NAMES:
                with self.subTest(adapter=adapter, tool_name=tool_name):
                    fixture = self.fixture()
                    fixture.run(adapter, tool_name)
                    self.assertFalse(
                        fixture.gh_was_called(),
                        f"{adapter} acted on tool name {tool_name!r}; the guard "
                        "compares case-sensitively on every port",
                    )


if __name__ == "__main__":
    unittest.main()
