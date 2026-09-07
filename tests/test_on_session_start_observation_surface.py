"""Behavioural coverage for the cold-start self-evolution observation surface.

Target = the three `adapter/*/hooks/on-session-start.*` implementations
(claude bash / codex bash / codex PowerShell). Issue #1562.

The first case set is the four behavioural defects brake 1 found on PR #1560:

  F2  PowerShell `-match` / `-ne` are case-insensitive by default while the awk
      ports are case-sensitive, so `Pending` / `PR:` / `Verdict_State:` split the
      three adapters on identical input.
  F4  An `## observation:` header with an empty descriptor was dropped by awk
      (`flush()` name guard) and surfaced by PowerShell.
  F3  The memory directory was resolved only when `self-evaluation_log.md`
      existed, so an unrelated file's absence silenced the observation surface.
  G2  The candidate scan stopped at the first *existing* directory rather than
      the first *populated* one, so an empty higher-precedence memory directory
      shadowed a populated lower-precedence one.

Each hook is executed as a real process against a filesystem fixture; there is
no external dependency (`gh` is stubbed, dates are relative to today).

What is pinned and what is not
------------------------------
The contract (`rules/evolution/cold-start-synthesis.md` Self-Evolution
Observation Surface) fixes the date conditions, the pending filter and the
overdue-wins fold; the presentation is explicitly delegated to the adapter
(same section, "Material gathering ... belong to the adapter"). So the
assertions here read the *judgment* out of the emission — which descriptor surfaces, under which
state, against which date, with which PR reference — and deliberately do not
match the banner text, the bullet prefix, the field names restated inside the
parentheses, the `[PR #N]` suffix notation, or the order of the entries. The
`DUE` / `OVERDUE (human judgment needed)` label words are matched, because those
are specified on the docs side (`docs/6.-Adapter.md:74`), not chosen here.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest
from datetime import date, timedelta
from pathlib import Path
from typing import NamedTuple


ROOT = Path(__file__).resolve().parents[1]

HOOKS = {
    "claude_sh": ROOT / "adapter" / "claude" / "hooks" / "on-session-start.sh",
    "codex_sh": ROOT / "adapter" / "codex" / "hooks" / "on-session-start.sh",
    "codex_ps1": ROOT / "adapter" / "codex" / "hooks" / "on-session-start.ps1",
}
ADAPTERS = tuple(HOOKS)

HOOK_TIMEOUT = 180

BASH = shutil.which("bash")
PWSH = shutil.which("pwsh")
NODE = shutil.which("node")

# Emission-mode probe. The shell hooks fall back to a full emit whenever the
# diff-only machinery cannot run; the marker path is reachable only from the
# other branch, so tests that need diff-only assert this string is absent.
FAIL_SAFE_MARK = "Fail-safe full emit"

# `rules/evolution/cold-start-synthesis.md` Hook Emission Contract — "A single
# 'No new orientation material since last session' line is emitted". The line is
# the contract; the banner it sits under is not.
NO_NEW_MATERIAL = "No new orientation material"


def require_runtime(binary: str, covered: str) -> None:
    """Skip locally, fail on CI.

    A developer host without `pwsh` should still be able to run the rest of the
    suite. On CI the same condition would silently drop the coverage this file
    exists to provide, so there it is an error instead.
    """
    message = f"{binary} is required to exercise the {covered}"
    if os.environ.get("CI"):
        raise AssertionError(f"{message}; it is missing on this CI runner")
    raise unittest.SkipTest(f"{message}; not available on this host")


def posix_path(path: Path) -> str:
    """Drive-letter path -> MSYS form, so it survives a `:`-separated PATH."""
    text = str(path).replace("\\", "/")
    match = re.match(r"^([A-Za-z]):/(.*)$", text)
    if match:
        return "/" + match.group(1).lower() + "/" + match.group(2)
    return text


def project_slug(path: Path) -> str:
    """The `~/.claude/projects/<slug>` name Claude Code derives from a path.

    Same derivation the claude hook applies to `CLAUDE_PROJECT_DIR`: the POSIX
    form of the path with `:`, `/` and the backslash all replaced by `-`.
    """
    return re.sub(r"[:/\\]", "-", posix_path(path))


def slash_path(path: Path) -> str:
    """Native path with forward slashes; accepted by PowerShell on every host."""
    return str(path).replace("\\", "/")


def iso(day_offset: int) -> str:
    return (date.today() + timedelta(days=day_offset)).isoformat()


# --------------------------------------------------------------------------
# Emission parsing
# --------------------------------------------------------------------------

def _is_section_rule(line: str) -> bool:
    return len(line) >= 10 and set(line) == {"━"}


def emitted_sections(hook_output: str) -> list[tuple[str, str]]:
    """(banner, body) for every rule-delimited section in the emission."""
    sections: list[tuple[str, str]] = []
    lines = hook_output.replace("\r\n", "\n").split("\n")
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("━━━ ") and line.endswith(" ━━━") and not _is_section_rule(line):
            banner = line[4:-4].strip()
            index += 1
            body: list[str] = []
            while index < len(lines) and not _is_section_rule(lines[index]):
                body.append(lines[index])
                index += 1
            sections.append((banner, "\n".join(body)))
        index += 1
    return sections


def observation_section(hook_output: str) -> str | None:
    """Body of the observation section, or None when the hook stayed silent.

    Located by topic rather than by exact banner text: the banner is an adapter
    choice, and pinning it made every assertion in this file depend on one
    string. A rename should fail the test that actually cares, not all of them.
    """
    for banner, body in emitted_sections(hook_output):
        if "observation" in banner.lower():
            return body
    return None


def anchor_section(hook_output: str) -> str | None:
    """Body of the cold-start rule anchor section, or None when absent.

    Located by topic for the same reason `observation_section` is. Scoping to
    the section matters here beyond banner independence: the codex ports also
    inject every `rules/**/*.md` body verbatim (Codex has no `.claude/rules`
    equivalent), so the whole rule file is present in the emission either way
    and only the anchor section can report what the cut did.
    """
    for banner, body in emitted_sections(hook_output):
        if "anchor" in banner.lower():
            return body
    return None


def no_new_material_marker(hook_output: str) -> str | None:
    """The no-new-material marker line, or None when it was not emitted."""
    for _banner, body in emitted_sections(hook_output):
        lines = [line for line in body.split("\n") if line.strip()]
        if len(lines) == 1 and NO_NEW_MATERIAL in lines[0]:
            return lines[0]
    return None


def self_eval_section(hook_output: str) -> str | None:
    """Body of the self-evaluation head section, or None when it was empty.

    Located by topic for the same reason `observation_section` is. An empty body
    is never emitted at all, so None is also how "no self-eval log resolved"
    reads.
    """
    for banner, body in emitted_sections(hook_output):
        if "self-evaluation" in banner.lower():
            return body
    return None


def promotion_section(hook_output: str) -> str | None:
    """Body of the promotion-candidates section, or None when it was empty.

    Located by topic for the same reason `observation_section` is: the banner
    wording is an adapter choice. An empty body is never emitted at all, so
    None is also how "every detector stayed silent" reads.
    """
    for banner, body in emitted_sections(hook_output):
        if "promotion" in banner.lower():
            return body
    return None


class PromotionSurface(NamedTuple):
    """The judgment reported by the three promotion-candidate detectors.

    Presentation is delegated to the adapter by `rules/evolution/evolution.md`
    ("Threshold values and concrete detection logic belong to the adapter"), so
    this reads out what was *judged* — which axis crossed the repeat threshold
    with what tally, which memory entries counted as recent, which entry/source
    pairs are adjacent over which tokens, and the totals each list declares —
    and not the bullet shape, the header wording or the order of the lines.
    """

    axis_misses: dict[str, int]
    recent_total: int | None
    recent_listed: frozenset[str]
    overlap_total: int | None
    overlap_listed: frozenset[tuple[str, str, frozenset[str]]]
    truncated: dict[str, int]


_AXIS_MISS_RE = re.compile(r'axis\s+"([^"]+)".*?(\d+)\s*$')
_TOTAL_RE = re.compile(r"(\d+)\s+(entries|pairs)")
_MORE_RE = re.compile(r"\.\.\.\s*and\s+(\d+)\s+more")
_ENTRY_RE = re.compile(r"(\S+\.md)\s*\[")
_TOKENS_RE = re.compile(r"\(tokens:([^)]*)\)")


def promotion_surface(section_body: str | None) -> PromotionSurface:
    """Parse a promotion section into its judgments, layout-agnostically."""
    axis_misses: dict[str, int] = {}
    recent_total: int | None = None
    recent_listed: set[str] = set()
    overlap_total: int | None = None
    overlap_listed: set[tuple[str, str, frozenset[str]]] = set()
    truncated: dict[str, int] = {}
    bucket = ""
    for line in (section_body or "").split("\n"):
        lowered = line.lower()
        if not line.startswith(" ") and lowered.strip():
            # A detector's own header line: it names the detector and, for the
            # two list-shaped ones, declares the full count.
            total = _TOTAL_RE.search(line)
            if "axis" in lowered:
                bucket = "axis"
            elif "recent memory" in lowered:
                bucket = "recent"
                recent_total = int(total.group(1)) if total else None
            elif "overlap" in lowered:
                bucket = "overlap"
                overlap_total = int(total.group(1)) if total else None
            else:
                bucket = ""
            continue
        more = _MORE_RE.search(line)
        if more:
            truncated[bucket] = int(more.group(1))
            continue
        if bucket == "axis":
            match = _AXIS_MISS_RE.search(line)
            if match:
                axis_misses[match.group(1)] = int(match.group(2))
        elif bucket == "recent":
            match = _ENTRY_RE.search(line)
            if match:
                recent_listed.add(match.group(1))
        elif bucket == "overlap":
            entry, _, source = line.partition("~")
            entry_match = _ENTRY_RE.search(entry)
            tokens = _TOKENS_RE.search(source)
            source_path = source.split("(tokens:")[0].strip()
            if entry_match and source_path:
                overlap_listed.add(
                    (
                        entry_match.group(1),
                        source_path,
                        frozenset(tokens.group(1).split()) if tokens else frozenset(),
                    )
                )
    return PromotionSurface(
        axis_misses=axis_misses,
        recent_total=recent_total,
        recent_listed=frozenset(recent_listed),
        overlap_total=overlap_total,
        overlap_listed=frozenset(overlap_listed),
        truncated=truncated,
    )


class SurfacedEntry(NamedTuple):
    """The judgment reported for one observation entry."""

    state: str  # "DUE" or "OVERDUE"
    date: str  # the ISO date the judgment was made against
    pr: str | None  # PR reference, or None when the entry carries none


_LABEL_RE = re.compile(r"(?<![A-Za-z])(OVERDUE|DUE)(?![A-Za-z])")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_PR_RE = re.compile(r"PR\D{0,3}(\d+)")
_HEADER_RE = re.compile(r"^##\s*observation:\s*(.*)$")


def declared_descriptors(lines) -> tuple[str, ...]:
    """Every non-empty descriptor an observation fixture declares."""
    found = []
    for line in lines:
        match = _HEADER_RE.match(line)
        if match and match.group(1).strip():
            found.append(match.group(1).strip())
    return tuple(found)


def surfaced_entries(
    section_body: str | None, descriptors: tuple[str, ...]
) -> dict[str, SurfacedEntry]:
    """Read the surfaced judgments out of a section body, layout-agnostically.

    `descriptors` is every descriptor the fixture wrote, so the returned mapping
    answers both directions at once: what surfaced, and what did not. A reported
    line that cannot be attributed to exactly one declared descriptor (an empty
    descriptor leaking through, for instance) is an error rather than a silent
    zero.
    """
    if section_body is None:
        return {}
    found: dict[str, SurfacedEntry] = {}
    for line in section_body.split("\n"):
        label = _LABEL_RE.search(line)
        if not label:
            continue
        names = [
            name
            for name in descriptors
            if re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", line)
        ]
        if len(names) != 1:
            raise AssertionError(
                f"surfaced line matches {len(names)} declared descriptors, expected 1: "
                f"{line!r} (declared: {list(descriptors)})"
            )
        if names[0] in found:
            raise AssertionError(f"descriptor {names[0]!r} surfaced more than once")
        date_match = _DATE_RE.search(line)
        pr_match = _PR_RE.search(line)
        found[names[0]] = SurfacedEntry(
            state=label.group(1),
            date=date_match.group(0) if date_match else "",
            pr=pr_match.group(1) if pr_match else None,
        )
    return found


class Workspace:
    """Filesystem fixture shaped like a Li+ host workspace."""

    # Diff-only state each hook leaves behind. A second run against the same
    # workspace reads it, which is the only way into the diff-only branch.
    # The two codex hooks intentionally share one path (they are two ports of
    # one adapter), so a two-run test must use a fresh workspace per adapter.
    STATE_RELATIVE = {
        "claude_sh": ".claude/state/last-cold-start-emit.json",
        "codex_sh": ".codex/state/last-cold-start-emit.json",
        "codex_ps1": ".codex/state/last-cold-start-emit.json",
    }

    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="liplus-hook-"))
        self.home = self.root / "home"
        self.workspace = self.root / "ws"
        self.liplus = self.workspace / "liplus-language"
        self.liplus.mkdir(parents=True)
        self.stub_bin = self.home / ".local" / "bin"
        self.stub_bin.mkdir(parents=True)
        self._write_gh_stub()

        # Memory directory candidates, in each adapter's own precedence order.
        self.claude_projects = self.home / ".claude" / "projects"
        self.claude_primary = self.slug_memory(self.workspace)
        self.shared_memory = self.workspace / "memory"
        self.codex_secondary = self.liplus / "memory"

    # -- fixture construction -------------------------------------------------

    def _write_gh_stub(self) -> None:
        """`gh` returns nothing: keeps the run offline and deterministic.

        The bash hooks prepend `$HOME/.local/bin` to PATH themselves; the
        PowerShell run gets the same directory prepended by `_env_for`.
        """
        unix_stub = self.stub_bin / "gh"
        unix_stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        os.chmod(unix_stub, 0o755)
        (self.stub_bin / "gh.cmd").write_text("@echo off\r\nexit /b 0\r\n", encoding="ascii")

    def write(self, directory: Path, name: str, content: str = "") -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / name
        target.write_text(content, encoding="utf-8")
        return target

    def seed_coldstart_rule(self, token: str, h2_token: str | None = None) -> Path:
        """Minimal `rules/evolution/cold-start-synthesis.md` in the fixture clone.

        The fixture's `liplus-language` directory is otherwise empty, so the
        always-emitted anchor has an empty body and "the rule anchor is
        re-emitted" cannot be observed at all. `token` is planted past the
        frontmatter and the H1 so it survives every port's strip.

        `h2_token` plants a second token inside an H2 section, which the anchor
        cut drops. Left None the file has no H2 at all, which is the
        emit-whole path.
        """
        h2 = ""
        if h2_token is not None:
            h2 = (
                "\n<hook-emission-contract>\n\n## Hook Emission Contract\n\n"
                f"{h2_token} contract body.\n\n</hook-emission-contract>\n"
            )
        return self.write(
            self.liplus / "rules" / "evolution",
            "cold-start-synthesis.md",
            "---\nalwaysApply: true\n---\n\n# Cold-start Synthesis\n\n"
            f"{token} anchor body.\n{h2}",
        )

    def slug_memory(self, path: Path) -> Path:
        """`~/.claude/projects/<slug>/memory` for an arbitrary directory.

        The slug derivation is the hook's own, applied here to paths other than
        the workspace so a test can plant a memory directory under a slug that
        encloses this session's project directory, or under one that belongs to
        a different workspace entirely.
        """
        return self.claude_projects / project_slug(path) / "memory"

    def memory_candidates(self, adapter: str) -> tuple[Path, Path]:
        """(higher precedence, lower precedence) memory directory for an adapter."""
        if adapter == "claude_sh":
            return self.claude_primary, self.shared_memory
        return self.shared_memory, self.codex_secondary

    def state_file(self, adapter: str) -> Path:
        return self.workspace / self.STATE_RELATIVE[adapter]

    def clear_state(self) -> None:
        """Remove every adapter's cold-start state file.

        `codex_sh` and `codex_ps1` map to one path, so leaving it behind makes
        the next adapter's first run look like a second run.
        """
        for adapter in ADAPTERS:
            path = self.state_file(adapter)
            if path.is_file():
                path.unlink()

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    # -- hook execution -------------------------------------------------------

    def _env_for(self, adapter: str, extra_env: dict[str, str] | None = None) -> dict[str, str]:
        env = dict(os.environ)
        env.pop("CODEX_PROJECT_DIR", None)
        if adapter == "claude_sh":
            env["HOME"] = posix_path(self.home)
            env["CLAUDE_PROJECT_DIR"] = posix_path(self.workspace)
        elif adapter == "codex_sh":
            env["HOME"] = posix_path(self.home)
        else:
            env["PATH"] = str(self.stub_bin) + os.pathsep + env.get("PATH", "")
        if extra_env:
            env.update(extra_env)
        return env

    def _command_and_stdin(self, adapter: str, matcher: str) -> tuple[list[str], str]:
        """Hook invocation plus the SessionStart payload the host actually sends.

        The shape is production's, not the hook's convenience. `matcher` is the
        settings.json filter key, not a payload field: the host reports how the
        session started in `source`, alongside a `hook_event_name` fixed at
        `"SessionStart"`. Feeding the claude hook a `{"matcher": ...}` object is
        what kept #1632 F1 green in CI — it read `payload.matcher` and fell back
        to `payload.hook_event_name`, so every production resume / clear /
        compact resolved to the startup default while the test passed.
        """
        hook = HOOKS[adapter]
        payload = {
            "session_id": "test-session",
            "hook_event_name": "SessionStart",
            "source": matcher,
        }
        if adapter == "claude_sh":
            payload["cwd"] = posix_path(self.workspace)
            payload["transcript_path"] = posix_path(self.root / "transcript.jsonl")
            return [BASH, posix_path(hook)], json.dumps(payload)
        if adapter == "codex_sh":
            payload["cwd"] = posix_path(self.workspace)
            return [BASH, posix_path(hook)], json.dumps(payload)
        payload["cwd"] = slash_path(self.workspace)
        return [PWSH, "-NoProfile", "-NonInteractive", "-File", str(hook)], json.dumps(payload)

    def run(
        self,
        adapter: str,
        matcher: str = "startup",
        extra_env: dict[str, str] | None = None,
    ) -> str:
        """Run one hook and return its emitted context text."""
        if adapter in ("claude_sh", "codex_sh") and not BASH:
            require_runtime("bash", "claude / codex shell hooks")
        if adapter == "codex_ps1" and not PWSH:
            require_runtime("pwsh", "codex PowerShell hook")

        command, stdin_payload = self._command_and_stdin(adapter, matcher)
        completed = subprocess.run(
            command,
            input=stdin_payload.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self._env_for(adapter, extra_env),
            timeout=HOOK_TIMEOUT,
        )
        stdout = completed.stdout.decode("utf-8", errors="replace")
        if adapter == "claude_sh":
            return stdout
        # Codex hooks wrap the whole emission in the SessionStart JSON envelope.
        try:
            envelope = json.loads(stdout)
        except json.JSONDecodeError as error:
            raise AssertionError(
                f"{adapter} did not emit JSON: {error}\nstdout={stdout!r}\n"
                f"stderr={completed.stderr.decode('utf-8', errors='replace')!r}"
            ) from error
        return envelope["hookSpecificOutput"]["additionalContext"]


class ObservationSurfaceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.observation_descriptors: tuple[str, ...] = ()
        self.new_workspace()

    def new_workspace(self) -> Workspace:
        """Fresh fixture; several tests need one per adapter layout."""
        self.ws = Workspace()
        self.addCleanup(self.ws.cleanup)
        return self.ws

    def observation_text(self, *lines: str) -> str:
        """Record the fixture's descriptors and render it as file content."""
        self.observation_descriptors = declared_descriptors(lines)
        return "\n".join(lines)

    def write_observation_file(self, *lines: str) -> None:
        """Observation fixture in the shared memory directory.

        `self-evaluation_log.md` is written alongside it so that the memory
        directory resolves through the primary (self-eval) path. That keeps the
        directory-resolution axis out of the way: tests in this shape observe
        parsing and classification only. Resolution has its own test case.
        """
        self.ws.write(self.ws.shared_memory, "self-evaluation_log.md", "# log\n")
        self.ws.write(
            self.ws.shared_memory,
            "self-evolution-observation.md",
            self.observation_text(*lines),
        )

    def run_hook(
        self,
        adapter: str,
        workspace: Workspace | None = None,
        matcher: str = "startup",
        extra_env: dict[str, str] | None = None,
    ) -> str:
        """Run a hook, guarding against a local-midnight rollover.

        Fixture dates are offsets from `date.today()` while the hooks read their
        own clock. A rollover between the two would silently reclassify the
        boundary entries, so the run is discarded instead of reported as a
        behavioural failure.
        """
        workspace = workspace if workspace is not None else self.ws
        started_on = date.today()
        output = workspace.run(adapter, matcher, extra_env)
        if date.today() != started_on:
            self.skipTest("local date rolled over mid-test; fixture offsets are stale")
        return output

    def sections_for_all_adapters(self) -> dict[str, str | None]:
        """Run every adapter against this fixture, one adapter at a time.

        `codex_sh` and `codex_ps1` share one state-file path (`STATE_RELATIVE`),
        so a previous adapter's run would put the next one into diff-only mode
        on what should be its first run. Clearing the state between adapters
        keeps each run a first run.
        """
        sections: dict[str, str | None] = {}
        for adapter in ADAPTERS:
            self.ws.clear_state()
            sections[adapter] = observation_section(self.run_hook(adapter))
        return sections

    def assert_adapters_agree(self, sections: dict[str, str | None]) -> None:
        reference = sections["claude_sh"]
        for adapter, section in sections.items():
            with self.subTest(adapter=adapter):
                self.assertEqual(
                    section,
                    reference,
                    f"{adapter} disagrees with claude_sh on identical input",
                )

    def require_section(self, hook_output: str) -> str:
        """Fail with the emitted banners listed, instead of a bare `None`."""
        section = observation_section(hook_output)
        if section is None:
            banners = [banner for banner, _body in emitted_sections(hook_output)]
            self.fail(f"no observation section was emitted; banners seen: {banners}")
        return section

    def surfaced(self, section_body: str | None) -> dict[str, SurfacedEntry]:
        return surfaced_entries(section_body, self.observation_descriptors)


class DueOverdueJudgmentTest(ObservationSurfaceTestCase):
    """Coverage area 3: due / overdue classification and silent skip."""

    def test_adapters_agree_on_due_overdue_and_skipped_entries(self) -> None:
        self.write_observation_file(
            "## observation: past-expiry",
            "pr: 1500",
            f"expires: {iso(-2)}",
            f"next_check: {iso(-9)}",
            "verdict_state: pending",
            "",
            "## observation: due-today",
            "pr: 1501",
            f"expires: {iso(7)}",
            f"next_check: {iso(0)}",
            "verdict_state: pending",
            "",
            "## observation: due-without-pr",
            f"expires: {iso(7)}",
            f"next_check: {iso(-1)}",
            "verdict_state: pending",
            "",
            "## observation: not-yet-due",
            "pr: 1503",
            f"expires: {iso(7)}",
            f"next_check: {iso(1)}",
            "verdict_state: pending",
            "",
            "## observation: already-settled",
            "pr: 1504",
            f"expires: {iso(-5)}",
            f"next_check: {iso(-5)}",
            "verdict_state: settle",
            "",
        )
        sections = self.sections_for_all_adapters()
        self.assert_adapters_agree(sections)
        self.assertEqual(
            self.surfaced(sections["claude_sh"]),
            {
                # past expiry folds into OVERDUE only, never reported twice
                "past-expiry": SurfacedEntry("OVERDUE", iso(-2), "1500"),
                # next_check == today is due (the comparison is <=, not <)
                "due-today": SurfacedEntry("DUE", iso(0), "1501"),
                # a missing pr field carries no PR reference
                "due-without-pr": SurfacedEntry("DUE", iso(-1), None),
                # not-yet-due and already-settled stay off the surface
            },
        )

    def test_expiry_exactly_today_is_not_yet_overdue(self) -> None:
        # `expires < today` is a strict comparison. Its `<=` sibling on
        # next_check is pinned above; this is the other half of that boundary.
        self.write_observation_file(
            "## observation: expiring-today",
            "pr: 2100",
            f"expires: {iso(0)}",
            f"next_check: {iso(0)}",
            "verdict_state: pending",
            "",
            "## observation: expiring-today-checked-later",
            "pr: 2101",
            f"expires: {iso(0)}",
            f"next_check: {iso(3)}",
            "verdict_state: pending",
            "",
        )
        sections = self.sections_for_all_adapters()
        self.assert_adapters_agree(sections)
        self.assertEqual(
            self.surfaced(sections["claude_sh"]),
            # DUE via next_check, not OVERDUE via expires; and with the check
            # window still shut, an expires-today entry does not surface at all.
            {"expiring-today": SurfacedEntry("DUE", iso(0), "2100")},
        )

    def test_absent_observation_file_is_a_silent_skip(self) -> None:
        # The memory directory resolves (self-evaluation_log.md is present) but
        # carries no observation file: no section at all, not an empty one.
        self.ws.write(self.ws.shared_memory, "self-evaluation_log.md", "# log\n")
        for adapter, section in self.sections_for_all_adapters().items():
            with self.subTest(adapter=adapter):
                self.assertIsNone(section)

    def test_no_open_check_window_is_a_silent_skip(self) -> None:
        self.write_observation_file(
            "## observation: future",
            "pr: 1600",
            f"expires: {iso(14)}",
            f"next_check: {iso(7)}",
            "verdict_state: pending",
            "",
            "## observation: resolved",
            "pr: 1601",
            f"expires: {iso(-14)}",
            f"next_check: {iso(-14)}",
            "verdict_state: settle",
            "",
        )
        for adapter, section in self.sections_for_all_adapters().items():
            with self.subTest(adapter=adapter):
                self.assertIsNone(section)


class AdapterParityTest(ObservationSurfaceTestCase):
    """Coverage area 1: identical output for identical input (PR #1560 F2 / F4)."""

    def test_verdict_state_case_variants_are_not_pending(self) -> None:
        self.write_observation_file(
            "## observation: capitalised-state",
            "pr: 1700",
            f"expires: {iso(7)}",
            f"next_check: {iso(-1)}",
            "verdict_state: Pending",
            "",
            "## observation: upper-state",
            "pr: 1701",
            f"expires: {iso(7)}",
            f"next_check: {iso(-1)}",
            "verdict_state: PENDING",
            "",
        )
        sections = self.sections_for_all_adapters()
        self.assert_adapters_agree(sections)
        self.assertEqual(self.surfaced(sections["claude_sh"]), {})

    def test_field_name_case_variants_are_not_recognised(self) -> None:
        self.write_observation_file(
            # Verdict_State is not the field name, so the entry has no
            # verdict_state at all and must not be treated as pending.
            "## observation: capitalised-field",
            "pr: 1800",
            f"expires: {iso(7)}",
            f"next_check: {iso(-1)}",
            "Verdict_State: pending",
            "",
            # PR is not the field name either: the entry is still due, but it
            # must be reported without a PR reference.
            "## observation: capitalised-pr-field",
            "PR: 1801",
            f"expires: {iso(7)}",
            f"next_check: {iso(-1)}",
            "verdict_state: pending",
            "",
        )
        sections = self.sections_for_all_adapters()
        self.assert_adapters_agree(sections)
        self.assertEqual(
            self.surfaced(sections["claude_sh"]),
            {"capitalised-pr-field": SurfacedEntry("DUE", iso(-1), None)},
        )

    def test_empty_descriptor_entry_is_dropped(self) -> None:
        self.write_observation_file(
            "## observation:",
            "pr: 1900",
            f"expires: {iso(7)}",
            f"next_check: {iso(-1)}",
            "verdict_state: pending",
            "",
            "## observation: well-formed",
            "pr: 1901",
            f"expires: {iso(7)}",
            f"next_check: {iso(-1)}",
            "verdict_state: pending",
            "",
        )
        sections = self.sections_for_all_adapters()
        self.assert_adapters_agree(sections)
        # A leaked empty-descriptor line cannot be attributed to any declared
        # descriptor, so `surfaced` raises rather than quietly returning one entry.
        self.assertEqual(
            self.surfaced(sections["claude_sh"]),
            {"well-formed": SurfacedEntry("DUE", iso(-1), "1901")},
        )


class MemoryDirResolutionTest(ObservationSurfaceTestCase):
    """Coverage area 2: memory directory resolution (PR #1560 F3 / G2)."""

    def setUp(self) -> None:
        super().setUp()
        self.observation_descriptors = ("reachable",)

    def due_entry(self, descriptor: str = "reachable", pr: str = "2000") -> str:
        return "\n".join(
            [
                f"## observation: {descriptor}",
                f"pr: {pr}",
                f"expires: {iso(7)}",
                f"next_check: {iso(-1)}",
                "verdict_state: pending",
                "",
            ]
        )

    def expected(self) -> dict[str, SurfacedEntry]:
        return {"reachable": SurfacedEntry("DUE", iso(-1), "2000")}

    def test_resolution_does_not_depend_on_self_evaluation_log(self) -> None:
        # No self-evaluation_log.md anywhere: the observation surface must still
        # find its own file rather than inherit an unrelated file's absence.
        self.ws.write(
            self.ws.shared_memory, "self-evolution-observation.md", self.due_entry()
        )
        sections = self.sections_for_all_adapters()
        self.assert_adapters_agree(sections)
        self.assertEqual(self.surfaced(sections["claude_sh"]), self.expected())

    def test_empty_higher_precedence_directory_does_not_shadow(self) -> None:
        for adapter in ADAPTERS:
            with self.subTest(adapter=adapter):
                workspace = self.new_workspace()
                higher, lower = workspace.memory_candidates(adapter)
                higher.mkdir(parents=True, exist_ok=True)
                workspace.write(lower, "self-evolution-observation.md", self.due_entry())
                section = self.require_section(self.run_hook(adapter, workspace))
                self.assertEqual(self.surfaced(section), self.expected())

    def test_higher_precedence_directory_without_marker_files_does_not_shadow(self) -> None:
        for adapter in ADAPTERS:
            with self.subTest(adapter=adapter):
                workspace = self.new_workspace()
                higher, lower = workspace.memory_candidates(adapter)
                workspace.write(higher, "notes.md", "unrelated\n")
                workspace.write(lower, "self-evolution-observation.md", self.due_entry())
                section = self.require_section(self.run_hook(adapter, workspace))
                self.assertEqual(self.surfaced(section), self.expected())

    def test_claude_glob_fallback_skips_unpopulated_project_slugs(self) -> None:
        """Third-stage fallback in `adapter/claude/hooks/on-session-start.sh`.

        Neither named candidate resolves, so the hook scans
        `~/.claude/projects/*/memory` newest-first. The populated-not-merely-
        existing rule applies there too, which the two named-candidate cases
        above cannot reach. Claude-only: the codex hooks have no glob stage.

        Both slugs here enclose the project directory, so the scope guard (#1796)
        admits both and the populated condition is what decides between them.
        That separation is the point: this case measures the populated condition
        alone, and the two cases below measure the scope guard alone.
        """
        workspace = self.new_workspace()
        populated = workspace.slug_memory(workspace.workspace.parent)
        empty = workspace.slug_memory(workspace.workspace.parent.parent)
        workspace.write(populated, "self-evolution-observation.md", self.due_entry())
        empty.mkdir(parents=True, exist_ok=True)
        # `ls -1td` orders by mtime, so make the empty slug strictly newer: it is
        # visited first and must be stepped over rather than claimed.
        now = time.time()
        os.utime(empty, (now, now))
        os.utime(populated, (now - 600, now - 600))

        section = self.require_section(self.run_hook("claude_sh", workspace))
        self.assertEqual(self.surfaced(section), self.expected())

    def test_claude_glob_fallback_prefers_an_enclosing_slug_over_a_newer_outsider(
        self,
    ) -> None:
        """Both edges of the #1796 scope, measured by one selection.

        Two populated memory directories, neither of them a named candidate: one
        under the slug of a directory containing this session's project
        directory, one under a sibling workspace's slug made strictly newer so
        that mtime order alone would take it. The guard has to reject the
        outsider *and* still admit the enclosing slug, and only one of the two
        can be selected, so a single assertion catches a guard that is missing
        and a guard narrowed to an exact slug match alike.

        Asserting only that the enclosing slug is reachable would not do that:
        pre-#1796 the fallback admitted every populated slug, so a fixture whose
        only populated directory is the enclosing one is satisfied before the
        change as well and measures nothing. The outsider is what supplies the
        discrimination — it gives the wrong implementations something to pick.
        """
        workspace = self.new_workspace()
        self.observation_descriptors = ("reachable", "outsider")
        enclosing = workspace.slug_memory(workspace.workspace.parent)
        outsider = workspace.slug_memory(workspace.workspace.parent / "elsewhere")
        workspace.write(enclosing, "self-evolution-observation.md", self.due_entry())
        workspace.write(enclosing, "self-evaluation_log.md", "# enclosing log\n")
        workspace.write(
            outsider,
            "self-evolution-observation.md",
            self.due_entry("outsider", "2001"),
        )
        workspace.write(outsider, "self-evaluation_log.md", "# outsider log\n")
        now = time.time()
        os.utime(outsider, (now, now))
        os.utime(enclosing, (now - 600, now - 600))

        output = self.run_hook("claude_sh", workspace)
        self.assertEqual(self.surfaced(self.require_section(output)), self.expected())
        self.assertIn("enclosing log", self_eval_section(output) or "")
        self.assertNotIn("outsider log", self_eval_section(output) or "")

    def test_claude_glob_fallback_does_not_cross_into_another_workspace(self) -> None:
        """#1796: the glob fallback stops at the project directory's own scope.

        The measured defect: this session's own memory directories exist but are
        empty, `memory_dir_populated` steps over both, and the glob then claims
        a sibling workspace's memory as this session's observe-stage input —
        promotion candidates and a self-eval head that were never observations
        of this workspace. An empty memory directory must read as "no material",
        which is a silent skip, not a search next door.

        The sibling is made strictly newest so mtime order alone would pick it,
        and it is populated so the populated condition alone would admit it: the
        scope guard is the only thing that can refuse it.
        """
        workspace = self.new_workspace()
        outsider = workspace.slug_memory(workspace.workspace.parent / "elsewhere")
        workspace.write(outsider, "self-evolution-observation.md", self.due_entry())
        workspace.write(outsider, "self-evaluation_log.md", "# outsider log\n")
        # This session's own candidates: present, empty, and older.
        workspace.claude_primary.mkdir(parents=True, exist_ok=True)
        workspace.shared_memory.mkdir(parents=True, exist_ok=True)
        now = time.time()
        os.utime(outsider, (now, now))
        for own in (workspace.claude_primary, workspace.shared_memory):
            os.utime(own, (now - 600, now - 600))

        output = self.run_hook("claude_sh", workspace)
        self.assertIsNone(
            observation_section(output),
            "another workspace's observation entry surfaced as this session's",
        )
        self.assertNotIn("outsider log", self_eval_section(output) or "")


class NoNewMaterialMarkerTest(ObservationSurfaceTestCase):
    """Coverage area 4: the marker's interaction with the observation surface.

    `rules/evolution/cold-start-synthesis.md` Hook Emission Contract — the
    marker fires when no section changed AND no observation entry was surfaced.
    Both halves live in the diff-only branch, which is entered only when a prior run left a state
    file behind, so each test here runs one hook twice against one workspace.
    """

    def prepared_workspace(self, adapter: str, observation: str | None) -> Workspace:
        workspace = self.new_workspace()
        # A stable non-empty section: it gives the second run a fingerprint to
        # compare, so "nothing changed" is a real comparison and not vacuous.
        workspace.write(workspace.shared_memory, "self-evaluation_log.md", "# log\n")
        if observation is not None:
            workspace.write(
                workspace.shared_memory, "self-evolution-observation.md", observation
            )
        return workspace

    def run_twice(self, adapter: str, observation: str | None) -> tuple[str, str]:
        if adapter in ("claude_sh", "codex_sh") and not NODE:
            require_runtime("node", "diff-only state handling in the shell hooks")
        workspace = self.prepared_workspace(adapter, observation)

        first = self.run_hook(adapter, workspace)
        self.assertIn(
            FAIL_SAFE_MARK, first, "first run should be the fail-safe full emit"
        )
        self.assertTrue(
            workspace.state_file(adapter).is_file(),
            f"{adapter} did not persist {workspace.state_file(adapter)}; "
            "the second run cannot reach diff-only mode",
        )

        started_on = date.today()
        second = self.run_hook(adapter, workspace)
        if date.today() != started_on:
            self.skipTest("local date rolled over between runs; fixture offsets are stale")
        self.assertNotIn(
            FAIL_SAFE_MARK,
            second,
            f"{adapter} fell back to a full emit on the second run, so the "
            "marker branch was never evaluated",
        )
        return first, second

    def test_marker_appears_when_nothing_changed_and_nothing_is_due(self) -> None:
        for adapter in ADAPTERS:
            with self.subTest(adapter=adapter):
                first, second = self.run_twice(adapter, observation=None)
                self.assertIsNone(
                    no_new_material_marker(first),
                    "the marker belongs to diff-only mode, not to the full emit",
                )
                self.assertIsNone(observation_section(second))
                self.assertIsNotNone(
                    no_new_material_marker(second),
                    "an unchanged session with nothing due must still mark the boundary",
                )

    def test_surfaced_observation_suppresses_the_marker(self) -> None:
        observation = self.observation_text(
            "## observation: still-open",
            "pr: 2200",
            f"expires: {iso(-3)}",
            f"next_check: {iso(-10)}",
            "verdict_state: pending",
            "",
        )
        for adapter in ADAPTERS:
            with self.subTest(adapter=adapter):
                _first, second = self.run_twice(adapter, observation=observation)
                section = self.require_section(second)
                self.assertEqual(
                    self.surfaced(section),
                    {"still-open": SurfacedEntry("OVERDUE", iso(-3), "2200")},
                    "the observation surface is outside the diff set and must "
                    "re-emit while the entry is unresolved",
                )
                self.assertIsNone(
                    no_new_material_marker(second),
                    "surfacing an overdue entry and declaring no new material in "
                    "the same emission is self-contradictory",
                )


class ColdstartAnchorCutTest(ObservationSurfaceTestCase):
    """The anchor cut: preamble in, H2 sections out, on all three ports (#1765).

    `rules/evolution/cold-start-synthesis.md` Hook Emission Contract (Anchor
    cut) — the rule file is always-on loaded, so re-emitting it whole put the
    same text in one session's context twice. The hook re-anchors the H1
    preamble and stops at the first H2 semantic tag.

    Read out of behaviour, not out of the cut's implementation: a token in the
    preamble stands for what must survive and a token inside an H2 section
    stands for what must not, so a port whose regex or loop bound drifts is
    caught by the emission rather than by a line-by-line port comparison. Three
    hand-ported implementations are exactly where a silently one-sided cut is
    possible.

    The emit-whole path is asserted on its own: it is what keeps a rule file
    that has no H2 section — or one whose section wrap changed shape — from
    losing the anchor entirely, which is the worse failure of the two.
    """

    PREAMBLE_TOKEN = "QQPREAMBLETOKENQQ"
    H2_TOKEN = "QQH2SECTIONTOKENQQ"

    def test_h2_sections_are_cut_and_the_preamble_survives(self) -> None:
        for adapter in ADAPTERS:
            with self.subTest(adapter=adapter):
                workspace = self.new_workspace()
                workspace.seed_coldstart_rule(self.PREAMBLE_TOKEN, self.H2_TOKEN)

                section = anchor_section(self.run_hook(adapter, workspace))

                self.assertIsNotNone(
                    section,
                    f"{adapter} emitted no anchor section at all",
                )
                self.assertIn(
                    self.PREAMBLE_TOKEN,
                    section or "",
                    f"{adapter} dropped the preamble; the anchor is the part the "
                    "AI applies at the step 3 moment",
                )
                self.assertNotIn(
                    self.H2_TOKEN,
                    section or "",
                    f"{adapter} anchored an H2 section; the rule file is already "
                    "in context once, which is what the cut exists to stop",
                )

    def test_a_file_with_no_h2_section_is_anchored_whole(self) -> None:
        for adapter in ADAPTERS:
            with self.subTest(adapter=adapter):
                workspace = self.new_workspace()
                workspace.seed_coldstart_rule(self.PREAMBLE_TOKEN)

                self.assertIn(
                    self.PREAMBLE_TOKEN,
                    anchor_section(self.run_hook(adapter, workspace)) or "",
                    f"{adapter} lost the anchor on a file with no H2 section",
                )

    def test_every_port_anchors_the_same_bytes(self) -> None:
        """Strict equality, not token containment, across the three ports.

        The cut is implemented three times by hand, and the two bash ports lean
        on command substitution stripping trailing newlines where the PowerShell
        port trims explicitly. Both land on the same value, and containment
        assertions would not have said so — they pass on any superset. This is
        the assertion that fails when one port is edited and the others are not.
        """
        sections: dict[str, str | None] = {}
        for adapter in ADAPTERS:
            workspace = self.new_workspace()
            workspace.seed_coldstart_rule(self.PREAMBLE_TOKEN, self.H2_TOKEN)
            sections[adapter] = anchor_section(self.run_hook(adapter, workspace))

        self.assert_adapters_agree(sections)


class MatcherResolutionTest(ObservationSurfaceTestCase):
    """Coverage area 5: SessionStart matcher resolution (#1632 F1 / F6).

    `rules/evolution/cold-start-synthesis.md` Hook Emission Contract — on a
    non-startup matcher "Only the cold-start rule anchor is re-emitted. The work
    context is continuous; the diff-only set is not re-evaluated"; the same line
    adds that the state file is not updated.

    Both halves are read out of behaviour rather than out of banner text. A
    token planted in the cold-start rule stands for the anchor, a token planted
    in the self-evaluation log stands for the diff-only set, and the state file
    is compared byte for byte. The diff-set token is *changed between the two
    runs* on purpose: an unchanged section is suppressed by diff-only mode
    anyway, so a still-startup hook would look identical to a correct one.
    Changing it makes the two paths diverge — a hook that resolved the matcher
    would stay silent, a hook that fell back to startup re-emits and rewrites.
    """

    # `fork` is claude-only. Codex documents no such SessionStart source, so
    # the codex ports carry three literals and not four — see the Matcher notes
    # in `adapter/codex/hooks-config.md` for the set Codex matches. The claude
    # entry is registered in the settings template (F6) against the documented
    # Claude SessionStart matcher set.
    NON_STARTUP = {
        "claude_sh": ("resume", "clear", "compact", "fork"),
        "codex_sh": ("resume", "clear", "compact"),
        "codex_ps1": ("resume", "clear", "compact"),
    }

    ANCHOR_TOKEN = "QQANCHORTOKENQQ"
    FIRST_TOKEN = "QQDIFFSETONEQQ"
    SECOND_TOKEN = "QQDIFFSETTWOQQ"

    def prepared_workspace(self, adapter: str) -> Workspace:
        if adapter in ("claude_sh", "codex_sh") and not NODE:
            require_runtime("node", "diff-only state handling in the shell hooks")
        workspace = self.new_workspace()
        workspace.seed_coldstart_rule(self.ANCHOR_TOKEN)
        self.write_self_eval(workspace, self.FIRST_TOKEN)
        return workspace

    def write_self_eval(self, workspace: Workspace, token: str) -> None:
        workspace.write(
            workspace.shared_memory,
            "self-evaluation_log.md",
            f"# Self-Evaluation Log\n\n## entry\n{token}\n",
        )

    def test_non_startup_matcher_reanchors_only_and_leaves_state_untouched(self) -> None:
        for adapter in ADAPTERS:
            for matcher in self.NON_STARTUP[adapter]:
                with self.subTest(adapter=adapter, matcher=matcher):
                    workspace = self.prepared_workspace(adapter)

                    startup = self.run_hook(adapter, workspace)
                    self.assertIn(
                        self.FIRST_TOKEN,
                        startup,
                        "the startup run must emit the diff-only set, otherwise "
                        "the non-startup assertion below is vacuous",
                    )
                    state = workspace.state_file(adapter)
                    self.assertTrue(
                        state.is_file(),
                        f"{adapter} did not persist {state}; the state-untouched "
                        "assertion has nothing to compare",
                    )
                    before = state.read_bytes()

                    # Move the diff-only set, so a hook that re-evaluated it
                    # cannot be mistaken for one that correctly stayed silent.
                    self.write_self_eval(workspace, self.SECOND_TOKEN)
                    emission = self.run_hook(adapter, workspace, matcher=matcher)

                    self.assertIn(
                        self.ANCHOR_TOKEN,
                        emission,
                        f"{adapter} did not re-anchor the cold-start rule "
                        f"literal on matcher {matcher!r}",
                    )
                    self.assertNotIn(
                        self.SECOND_TOKEN,
                        emission,
                        f"{adapter} re-evaluated the diff-only set on matcher "
                        f"{matcher!r}; the payload reports it in `source`, so a "
                        "hook reading `matcher` falls back to startup",
                    )
                    self.assertEqual(
                        before,
                        state.read_bytes(),
                        f"{adapter} rewrote the cold-start state file on matcher "
                        f"{matcher!r}; the diff baseline must not move on a "
                        "continuous session",
                    )


class PromotionCandidateDetectorTest(ObservationSurfaceTestCase):
    """Coverage area 6: the three promotion-candidate detectors (#1632 F3 / #1636).

    `rules/evolution/evolution.md` "Pattern Detection Surfacing At Cold-start"
    fixes the three detection targets — self-evaluation log repetition, recent
    memory additions, keyword overlap with Li+ source — and requires them to be
    surfaced as observable material rather than left to passive noticing. It
    delegates the threshold values and the concrete logic to the adapter, so the
    assertions below read the judgment out of the emission and leave the
    presentation alone (`promotion_surface`).

    Every case runs all three ports against one fixture. That is the shape the
    defect needed: #1635 repaired the claude port while both codex ports kept
    reading the flat `feedback.md` / `project.md` pair and the invented
    `root_cause:` line syntax, and a suite that exercised one port could not see
    it. The live host layout is one memory per file, so a fixture written in
    that layout is silent on every unrepaired port.
    """

    SOURCE_TOKEN_TEXT = "widget calibration harness notes\n"

    def seed_source(self, workspace: Workspace) -> None:
        """Two Li+ source files for the overlap detector to match against."""
        workspace.write(
            workspace.liplus / "rules" / "evolution",
            "widgets.md",
            f"# widgets\n\n{self.SOURCE_TOKEN_TEXT}",
        )
        workspace.write(
            workspace.liplus / "skills" / "sample-skill",
            "SKILL.md",
            "# sample\n\nwidget calibration notes\n",
        )

    def seed_entry(self, workspace: Workspace, filename: str, title: str) -> None:
        """One per-topic memory entry, titled through its frontmatter `name:`."""
        workspace.write(
            workspace.shared_memory,
            filename,
            f"---\nname: {title}\n---\n\nbody\n",
        )

    def seed_self_eval(self, workspace: Workspace, *entries: str) -> None:
        workspace.write(
            workspace.shared_memory,
            "self-evaluation_log.md",
            "# Self-Evaluation Log\n\n" + "\n\n".join(entries) + "\n",
        )

    def surfaces_for_all_adapters(self) -> dict[str, PromotionSurface]:
        surfaces: dict[str, PromotionSurface] = {}
        for adapter in ADAPTERS:
            self.ws.clear_state()
            surfaces[adapter] = promotion_surface(
                promotion_section(self.run_hook(adapter))
            )
        return surfaces

    def assert_ports_agree(self, surfaces: dict[str, PromotionSurface]) -> None:
        reference = surfaces["claude_sh"]
        for adapter, surface in surfaces.items():
            with self.subTest(adapter=adapter):
                self.assertEqual(
                    surface,
                    reference,
                    f"{adapter} disagrees with claude_sh on identical input",
                )

    def test_all_three_ports_read_the_live_memory_layout(self) -> None:
        """All three detectors fire, on the same input, in the same way.

        The fixture carries no flat `feedback.md` / `project.md` and no
        `root_cause:` line, which is what the live artifacts look like. A port
        still reading either format reports nothing at all here.
        """
        self.seed_source(self.ws)
        self.seed_self_eval(
            self.ws,
            "## entry 1\n**Axis tags**: character-drift: miss / source-check: hit",
            "## entry 2\n**Axis tags (10-axis)**:\n"
            "- character-drift: **miss (primary)**\n- frame-check: hit",
        )
        self.seed_entry(
            self.ws, "feedback_widget_calibration.md", "widget calibration harness"
        )
        self.seed_entry(self.ws, "project_alpha.md", "alpha unrelated topic")

        surfaces = self.surfaces_for_all_adapters()
        self.assert_ports_agree(surfaces)

        surface = surfaces["claude_sh"]
        self.assertEqual(
            surface.axis_misses,
            {"character drift": 2},
            "the repeated axis is the one the self-eval spec names as a weakness "
            "region; the inline and the bullet layout must both count. The key is "
            "the normal form of the skill's 'Axis name normal form', so the "
            "hyphenated spelling in the fixture lands on the canonical axis",
        )
        self.assertEqual(surface.recent_total, 2)
        self.assertEqual(
            surface.recent_listed,
            frozenset({"feedback_widget_calibration.md", "project_alpha.md"}),
            "one memory is one file, so every freshly written entry counts",
        )
        self.assertEqual(
            surface.overlap_listed,
            frozenset(
                {
                    (
                        "feedback_widget_calibration.md",
                        "rules/evolution/widgets.md",
                        frozenset({"widget", "calibration", "harness"}),
                    ),
                    (
                        "feedback_widget_calibration.md",
                        "skills/sample-skill/SKILL.md",
                        frozenset({"widget", "calibration"}),
                    ),
                }
            ),
            "the adjacent entry must be named against the source path, and the "
            "unrelated entry must not be reported",
        )
        self.assertEqual(surface.overlap_total, 2)
        self.assertEqual(surface.truncated, {})

    def test_single_observation_stays_below_every_threshold(self) -> None:
        """One occurrence is noise on all three axes, on all three ports."""
        self.seed_source(self.ws)
        self.seed_self_eval(
            self.ws,
            "## entry 1\n**Axis tags**: character-drift: miss / source-check: hit",
            "## entry 2\n**Axis tags**: source-check: hit / frame-check: hit",
        )
        # `widget` alone reaches the source files; one shared token is
        # coincidence at corpus scale, so the pair must not be reported.
        self.seed_entry(self.ws, "feedback_widget_only.md", "widget")

        surfaces = self.surfaces_for_all_adapters()
        self.assert_ports_agree(surfaces)

        surface = surfaces["claude_sh"]
        self.assertEqual(
            surface.axis_misses, {}, "an axis missed once is not a weakness region"
        )
        self.assertIsNone(
            surface.recent_total, "a single recent entry is below the threshold"
        )
        self.assertEqual(surface.overlap_listed, frozenset())

    def test_surface_cap_truncates_the_list_and_still_reports_the_total(self) -> None:
        """The cap bounds the list; the declared total keeps it honest.

        A consolidate pass rewrites every entry at once, so hitting the cap is
        normal operation rather than an edge case, and a truncated list that
        dropped the count would hide how much it left out.
        """
        for index in range(14):
            self.seed_entry(
                self.ws, f"reference_topic{index:02d}.md", f"topic {index:02d}"
            )

        surfaces = self.surfaces_for_all_adapters()
        self.assert_ports_agree(surfaces)

        surface = surfaces["claude_sh"]
        self.assertEqual(surface.recent_total, 14)
        self.assertLess(
            len(surface.recent_listed),
            14,
            "a list this long is past the point of being scannable; the cap "
            "exists so the orientation surface stays readable",
        )
        self.assertEqual(
            len(surface.recent_listed) + surface.truncated.get("recent", 0),
            14,
            "the surfaced entries plus the omitted count must add up to the "
            "declared total, or the omission is hiding something",
        )

    def test_empty_memory_directory_is_a_silent_skip(self) -> None:
        """No sources, no section — on every port."""
        self.ws.write(self.ws.shared_memory, "self-evaluation_log.md", "# log\n")
        for adapter in ADAPTERS:
            with self.subTest(adapter=adapter):
                self.ws.clear_state()
                self.assertIsNone(
                    promotion_section(self.run_hook(adapter)),
                    f"{adapter} emitted a promotion section with nothing to report",
                )


class AxisTagFormatTest(ObservationSurfaceTestCase):
    """Coverage area 7: the axis-tag line format the detector implements (#1651).

    The three ports were repaired together on PR #1650 and came out of brake 1
    sharing one ceiling rather than differing from each other: the axis tally
    keyed on the raw spelling, the inline layout let the last segment run to end
    of line, and no spec held the format the detector hardcodes. Each case below
    runs all three ports, because a fix landing on one port is what would open a
    new parity gap.

    Fixtures here deliberately carry the shapes the earlier ones did not: mixed
    spellings of one axis, a Japanese free-form trailer on the tag line, a ` / `
    inside a verdict parenthetical, and non-ASCII entry titles.
    """

    def seed_self_eval(self, workspace: Workspace, *entries: str) -> None:
        workspace.write(
            workspace.shared_memory,
            "self-evaluation_log.md",
            "# Self-Evaluation Log\n\n" + "\n\n".join(entries) + "\n",
        )

    def axis_misses_for_all_adapters(self) -> dict[str, dict[str, int]]:
        misses: dict[str, dict[str, int]] = {}
        for adapter in ADAPTERS:
            self.ws.clear_state()
            misses[adapter] = promotion_surface(
                promotion_section(self.run_hook(adapter))
            ).axis_misses
        return misses

    def assert_axis_misses(self, expected: dict[str, int]) -> None:
        """Every port must report `expected`, and must agree with the others."""
        misses = self.axis_misses_for_all_adapters()
        for adapter, reported in misses.items():
            with self.subTest(adapter=adapter):
                self.assertEqual(reported, expected)

    # -- item 2: axis-name normal form ---------------------------------------

    def test_spelling_variants_of_one_axis_tally_as_one(self) -> None:
        """`Character drift` / `Character` / `Character(pronoun)` are one axis.

        This is the live shape: the log names the primary axis four different
        ways across entries. Keyed on the raw spelling they are four tallies of
        one, and a weakness region that is in fact repeating stays under the
        threshold. `skills/evolution-self-eval/SKILL.md` "Axis name normal form"
        is what says they are one, and the ports implement that section.
        """
        self.seed_self_eval(
            self.ws,
            "## entry 1\n**Axis tags**: Character drift: **miss (primary)**",
            "## entry 2\n**Axis tags**: Character: **miss**(再発)",
            "## entry 3\n**Axis tags**: Character(pronoun): **miss**",
            "## entry 4\n**Axis tags (10-axis)**:\n- character_drift: miss",
        )
        self.assert_axis_misses({"character drift": 4})

    def test_a_name_outside_the_ten_axes_keeps_its_own_tally(self) -> None:
        """Normalization folds spellings, not distinct axes.

        The live log tags free-form axes (`Instrument validity`, `Frame check`)
        that the 10-axis list does not carry. Those must normalize like any
        other name and stay separate — collapsing them into a canonical axis
        would manufacture a repeat that was never observed.
        """
        self.seed_self_eval(
            self.ws,
            "## entry 1\n**Axis tags**: Instrument-validity: **miss (primary)** / "
            "Character: miss",
            "## entry 2\n**Axis tags**: Instrument validity: miss / Character drift: miss",
        )
        self.assert_axis_misses({"instrument validity": 2, "character drift": 2})

    # -- item 3: inline tag bleed --------------------------------------------

    def test_free_form_trailer_stays_out_of_the_last_verdict(self) -> None:
        """The inline list ends before the prose that follows it on the line.

        The live log writes `Root cause:` / `Domain:` on the same physical line
        as the tag list. With the last segment running to end of line, that
        prose reached the `miss` substring scan, so an axis tagged `hit` was
        counted as a miss whenever the sentence after it happened to discuss
        one — and the ` / ` inside a parenthetical in that prose split off a
        phantom axis. Both entries below tag `Request depth: hit`, so a reported
        miss on it can only have come from the trailer.
        """
        trailer = (
            "。Root cause: reading-drift (character application-moment / release gist)"
            "。Domain: character-binding, release-flow。"
        )
        self.seed_self_eval(
            self.ws,
            "## entry 1\n**Axis tags**: Loop entry: **miss** / Request depth: hit" + trailer,
            "## entry 2\n**Axis tags**: Loop entry: **miss** / Request depth: hit" + trailer,
        )
        self.assert_axis_misses({"loop entry": 2})

    def test_a_separator_inside_a_verdict_parenthetical_does_not_split(self) -> None:
        """` / ` between parentheses is verdict text, not a pair boundary.

        Splitting on every ` / ` cut this verdict in half and fed the tail to
        the pair reader, which is how a fragment of one verdict became an axis
        of its own.
        """
        self.seed_self_eval(
            self.ws,
            "## entry 1\n**Axis tags**: Gist vs literal: **miss** "
            "(release-scheme gist→行動前訂正 / wiki entry は literal 検証) / Loop entry: hit",
            "## entry 2\n**Axis tags**: Gist vs literal: **miss** "
            "(圧縮余地を印象で主張 / literal Read で訂正) / Loop entry: hit",
        )
        self.assert_axis_misses({"gist vs literal": 2})

    # -- #1653: the bracket class the separator scan tracks -------------------

    def test_full_width_brackets_bound_an_aside_like_ascii_ones(self) -> None:
        """`（` `）` and `(` `)` are one bracket class, on all three ports.

        The Japanese log writes its asides in full-width brackets, so a scan
        inspecting only the ASCII pair reads a `。` or a ` / ` inside such an
        aside as if it stood outside one: the pair list ends early and the axes
        written after the aside are never counted. `skills/evolution-self-eval/
        SKILL.md` "Axis tag line format" is what says the two kinds are one
        class. One fixture runs in every combination of the two kinds here, and
        the ASCII run is the reference the others have to match — same defect
        class as the parenthetical split #1650 repaired, reached through a
        different character. The mixed openings are what "one class" means: the
        spec names `（… / …)` as bounding an aside, so an implementation that
        pairs each kind only with its own would satisfy the two same-kind runs
        and still contradict that sentence.
        """

        def entries(opener: str, closer: str) -> tuple[str, ...]:
            aside = f"{opener}前提を確認せず。Root cause: 二度目 / 別軸: miss{closer}"
            line = (
                f"**Axis tags**: Loop entry: **miss** {aside} / "
                f"Character{opener}pronoun{closer}: **miss**"
            )
            return (f"## entry 1\n{line}", f"## entry 2\n{line}")

        for opener, closer in (
            ("(", ")"),
            ("（", "）"),
            ("(", "）"),
            ("（", ")"),
        ):
            with self.subTest(brackets=opener + closer):
                self.seed_self_eval(self.ws, *entries(opener, closer))
                self.assert_axis_misses({"loop entry": 2, "character drift": 2})

    def test_pairs_after_an_unmatched_bracket_are_still_counted(self) -> None:
        """A bracket with no partner is text, not the start of an aside.

        A stray `)` was always ignored, but a stray `(` raised the depth for the
        remainder of the line: no later ` / ` and no later terminator applied,
        so everything after it collapsed into one verdict and the axes written
        there went uncounted. That direction is a regression against the plain
        split this scan replaced, which counted them — which is why both
        orientations of the stray run here and must agree. Both kinds run as
        well: the full-width stray reaches the same code path only if the
        bracket class is what the scan tracks.
        """
        for stray in ("(", ")", "（", "）"):
            with self.subTest(stray=stray):
                line = (
                    f"**Axis tags**: Loop entry: **miss** {stray}再発 / "
                    "Character drift: **miss**"
                )
                self.seed_self_eval(
                    self.ws, f"## entry 1\n{line}", f"## entry 2\n{line}"
                )
                self.assert_axis_misses({"loop entry": 2, "character drift": 2})

    # -- item 1: sort locale --------------------------------------------------

    CULTURE_AWARE_ENV = {"LC_ALL": "en_US.UTF-8", "LC_COLLATE": "en_US.UTF-8", "LANG": "en_US.UTF-8"}

    def test_every_ordering_site_is_pinned_to_a_locale_independent_comparer(self) -> None:
        """No port may order on the ambient locale or culture.

        This is asserted on the source, because the divergence it guards is not
        observable on a host that has no culture-aware locale installed — and a
        behavioural check that silently degrades to "passes everywhere" is the
        weaker instrument here. GNU `sort` under a culture-aware locale is not
        bytewise and `Sort-Object` is culture-aware by default, so an unpinned
        site splits the ports on identical input. Because `SURFACE_CAP` truncates
        two of the lists, ordering decides which items survive, not just the
        order they appear in.
        """
        def statements(adapter: str) -> list[str]:
            """Source lines that are not wholly a comment.

            The rationale for each pin is written next to it, so a naive scan
            matches the prose explaining the rule as well as a violation of it.
            """
            return [
                line
                for line in HOOKS[adapter].read_text(encoding="utf-8").splitlines()
                if not line.lstrip().startswith("#")
            ]

        for adapter in ("claude_sh", "codex_sh"):
            with self.subTest(adapter=adapter):
                unpinned = [
                    line
                    for line in statements(adapter)
                    if re.search(r"\|\s*sort\b", line)
                    and not re.search(r"\|\s*LC_ALL=C sort\b", line)
                ]
                self.assertEqual(
                    unpinned,
                    [],
                    f"{adapter} pipes into a `sort` that is not pinned to LC_ALL=C",
                )

        ps1_lines = statements("codex_ps1")
        self.assertEqual(
            [line for line in ps1_lines if re.search(r"\bSort-Object\b", line)],
            [],
            "codex_ps1 uses `Sort-Object`, which compares with the current "
            "culture; the ordinal comparer is what matches the pinned bash sort",
        )
        self.assertTrue(
            any("StringComparer]::Ordinal" in line for line in ps1_lines),
            "codex_ps1 must order through an ordinal comparer",
        )

    def test_ports_agree_on_order_when_the_ambient_locale_is_culture_aware(self) -> None:
        """Same fixture, same order, on all three ports.

        The bash ports are handed a culture-aware locale here. The names differ
        only in a punctuation character, which byte order ranks by code point
        (`-` < `_` < `a`) and a culture-aware collation reorders, and they stay
        distinct on a case-insensitive filesystem — a case-mixed fixture would
        collapse to one file on Windows. Where the locale is not installed the
        run degrades to the C collation and the assertion is merely redundant —
        never wrong — which is why the source-level pin above carries the
        regression guard.
        """
        stems = ("z-a", "z_a", "za")
        for index, stem in enumerate(stems):
            self.ws.write(
                self.ws.shared_memory,
                f"reference_{stem}.md",
                f"---\nname: 観測 {index} {stem}\n---\n\nbody\n",
            )
        self.ws.write(self.ws.shared_memory, "self-evaluation_log.md", "# log\n")

        orders: dict[str, list[str]] = {}
        for adapter in ADAPTERS:
            self.ws.clear_state()
            body = promotion_section(
                self.run_hook(adapter, extra_env=self.CULTURE_AWARE_ENV)
            )
            orders[adapter] = [
                match.group(1)
                for match in (_ENTRY_RE.search(line) for line in (body or "").split("\n"))
                if match
            ]

        expected = sorted(
            (f"reference_{stem}.md" for stem in stems),
            key=lambda name: name.encode("utf-8"),
        )
        for adapter, order in orders.items():
            with self.subTest(adapter=adapter):
                self.assertEqual(
                    order,
                    expected,
                    f"{adapter} did not list the entries in byte order",
                )

    # -- item 4: the format has a spec ---------------------------------------

    def test_the_format_the_detectors_hardcode_is_written_down(self) -> None:
        """The detector's literals must exist in the skill, not only in code.

        Before #1651 `**Axis tags**:` appeared nowhere in Li+ source outside the
        three hooks: the log's format was convention, and a convention that
        drifts takes the detector down silently — which is exactly how #1632 F3
        happened. Pinning the literals here means a format change has to pass
        through the spec.
        """
        spec = (ROOT / "skills" / "evolution-self-eval" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        for literal in (
            "**Axis tags**:",
            "**Axis tags (10-axis)**:",
            "Root cause:",
            "Domain:",
            "。",
            "（",
            "）",
        ):
            with self.subTest(literal=literal):
                self.assertIn(
                    literal,
                    spec,
                    "the detectors branch on this literal; the skill is where it "
                    "is defined",
                )

        for axis in (
            "Assumption surfacing",
            "Contradiction catch",
            "Deepening axis fit",
            "Silence respect",
            "Loop entry",
            "Character drift",
            "Review partition",
            "Gist vs literal",
            "Expansion limit",
            "Request depth",
        ):
            with self.subTest(axis=axis):
                self.assertIn(
                    axis.lower(),
                    spec.lower(),
                    "the normal form expands a shorthand against The 10 axes, so "
                    "the canonical list in the ports must be the skill's list",
                )

        for adapter in ADAPTERS:
            with self.subTest(adapter=adapter):
                self.assertIn(
                    "evolution-self-eval/SKILL.md",
                    HOOKS[adapter].read_text(encoding="utf-8"),
                    "each port must name the spec it implements, so the next "
                    "reader does not take the code for the source",
                )


if __name__ == "__main__":
    unittest.main()
