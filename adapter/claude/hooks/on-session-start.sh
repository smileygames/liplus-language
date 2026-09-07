#!/bin/bash
# Source: adapter/claude/hooks/on-session-start.sh ({LI_PLUS_TAG})
# Cold-start Synthesis hook: emits orientation material for the session-opening turn.
# stdout is injected into the initial session context (Claude Code SessionStart contract).
# The hook does NOT synthesize — it only gathers material. AI performs synthesis
# through Character_Instance using the emitted material plus its own loaded layers.
#
# Matchers: startup / resume / clear / compact / fork (see hooks-settings.md).
# Keep total output modest (a few KB). Truncate rather than skip when sources are large.
#
# Diff-only emission (matcher = startup only):
#   Each material section is fingerprinted (sha256 of the raw body) and the
#   fingerprint set is persisted at {workspace_root}/.claude/state/last-cold-start-emit.json.
#   On the next startup the hook compares current fingerprints to the stored set
#   and emits only sections whose body changed. The cold-start rule anchor is
#   always emitted (drift recovery anchor), as are the two date-driven surfaces:
#   the self-evolution observation surface and the promotion tally expiry surface
#   (see their gather blocks). When no section changed and neither of those two
#   has anything due, a single
#   "No new orientation material since last session" marker is emitted so the
#   human can still observe that a session boundary occurred.
#
#   Fail-safe: missing state, unreadable state, malformed JSON, or sha256/node
#   tool absence collapses to "full emit" (every available section) and
#   rewrites the state. A corrupted diff is heavier than a redundant full emit.
#   JSON read/write uses Node.js (`node -e`), not an external `jq` binary —
#   node is the runtime Claude Code itself depends on, so it is a safe
#   assumption and removes a previously-common fail-safe trigger.
#
#   resume / clear / compact / fork matchers do not run diff comparison (the
#   work context is continuous; only the cold-start rule anchor is
#   re-anchored).
export PATH="$HOME/.local/bin:$PATH"
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-.}"
LIPLUS_DIR="$PROJECT_ROOT/liplus-language"
COLDSTART_MD="$LIPLUS_DIR/rules/evolution/cold-start-synthesis.md"
DECISION_STRUCTURE="$LIPLUS_DIR/docs/Decision-Structure.md"
STATE_DIR="$PROJECT_ROOT/.claude/state"
STATE_FILE="$STATE_DIR/last-cold-start-emit.json"
ADAPTER_FILE="$PROJECT_ROOT/.claude/CLAUDE.md"
CONFIG_FILE="$PROJECT_ROOT/Li+config.md"

# ===================================================================
# Prerequisite install: gh CLI
# ===================================================================
# Relocated from Li+update.md Phase 2.1. The hook ensures `gh` is present so
# the update walkthrough does not have to spell out install steps every
# session. Behavior branches on detected host OS (not on adapter identity —
# the Claude adapter runs natively on Linux, macOS, and Windows/Git-Bash
# alike; see Li+update.md Phase 2.1):
#   - Linux: auto-install into `~/.local/bin/gh` when absent (arch-detected
#     tarball, not hardcoded). Presence is a silent skip.
#   - macOS / Windows (incl. Git-Bash/MSYS2): auto-install is NOT attempted.
#     `gh` is treated as a documented prerequisite. When absent from PATH, a
#     platform-appropriate install instruction is surfaced via the
#     GH_INSTALL_STATUS marker and the hook continues without blocking.
# Failure/guidance does NOT abort the hook — it is surfaced as a cold-start
# material entry so the AI can inform (Linux failure) or guide (macOS/Windows
# absence) the user.
GH_INSTALL_STATUS=""
if ! command -v gh >/dev/null 2>&1; then
  HOST_KERNEL=$(uname -s 2>/dev/null || echo "unknown")
  case "$HOST_KERNEL" in
    Linux*)
      GH_INSTALL_LOG=$(mktemp 2>/dev/null || echo "/tmp/liplus-gh-install-$$.log")
      # Subshell, NOT a brace group. A brace group runs in the current shell,
      # so `set -e` inside it applied to the whole hook: a curl/tar failure
      # aborted the process before the `failed:` status below could be built
      # (no gh install banner, no LI_PLUS_UPDATE_STATUS marker, no language
      # contract banner), and on success errexit stayed armed for the remaining
      # ~780 lines, where several bare command substitutions exit non-zero in
      # normal operation (`gh release list` unauthenticated, `gh issue list`,
      # the state-file read whose `$?` fail-safe check would never be reached).
      # The subshell confines errexit to the install steps, which is what the
      # "Failure/guidance does NOT abort the hook" note above already promised.
      # No variable assigned inside is read outside it; the result is observed
      # through the installed binary and the log file.
      (
        set -e
        mkdir -p "$HOME/.local/bin"
        GH_VERSION="2.62.0"
        case "$(uname -m 2>/dev/null)" in
          x86_64|amd64) GH_ARCH="linux_amd64" ;;
          aarch64|arm64) GH_ARCH="linux_arm64" ;;
          armv6l|armv7l) GH_ARCH="linux_armv6" ;;
          386|i686) GH_ARCH="linux_386" ;;
          *) GH_ARCH="linux_amd64" ;;
        esac
        GH_URL="https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_${GH_ARCH}.tar.gz"
        GH_TARBALL="$HOME/.local/bin/gh.tar.gz"
        GH_EXTRACT_DIR="$HOME/.local/bin/_gh_extract"
        mkdir -p "$GH_EXTRACT_DIR"
        curl -fsSL -o "$GH_TARBALL" "$GH_URL"
        tar -xzf "$GH_TARBALL" -C "$GH_EXTRACT_DIR" --strip-components=1
        mv "$GH_EXTRACT_DIR/bin/gh" "$HOME/.local/bin/gh"
        chmod +x "$HOME/.local/bin/gh"
        rm -rf "$GH_EXTRACT_DIR" "$GH_TARBALL"
      ) > "$GH_INSTALL_LOG" 2>&1
      if [ -x "$HOME/.local/bin/gh" ]; then
        GH_INSTALL_STATUS="installed"
      else
        GH_INSTALL_STATUS="failed: $(tail -n 3 "$GH_INSTALL_LOG" 2>/dev/null | tr '\n' ' ')"
      fi
      rm -f "$GH_INSTALL_LOG" 2>/dev/null || true
      ;;
    Darwin*)
      GH_INSTALL_STATUS="missing: macOS host detected, gh not found on PATH. Documented prerequisite — do not auto-install. Ask the user to run: brew install gh"
      ;;
    MINGW*|MSYS*|CYGWIN*)
      GH_INSTALL_STATUS="missing: Windows host detected (Git-Bash/MSYS2), gh not found on PATH. Documented prerequisite — do not auto-install. Ask the user to run in a Windows terminal: winget install --id GitHub.cli"
      ;;
    *)
      GH_INSTALL_STATUS="missing: unrecognized host kernel ($HOST_KERNEL), gh not found on PATH. Documented prerequisite — do not auto-install. Ask the user to install gh via their platform's package manager."
      ;;
  esac
fi

# Guard: if liplus-language source is not resolved yet (e.g. pre-bootstrap), exit silently
# AFTER emitting the gh install failure/guidance marker if applicable.
if [ ! -d "$LIPLUS_DIR" ]; then
  if [ "${GH_INSTALL_STATUS#failed}" != "$GH_INSTALL_STATUS" ] || [ "${GH_INSTALL_STATUS#missing}" != "$GH_INSTALL_STATUS" ]; then
    printf '━━━ gh install ━━━\n%s\n%s\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n' \
      "Prerequisite install failed or gh missing. Master intervention required." \
      "Detail: $GH_INSTALL_STATUS"
  fi
  exit 0
fi

# --- matcher resolution ---
# Claude Code passes the SessionStart payload as JSON on stdin. We read it once
# (non-blocking with a short timeout) and extract the matcher. Empty / unreadable
# stdin falls back to "startup" so the diff-only path is the default.
#
# The payload field is `source`, NOT `matcher`: `matcher` is the settings.json
# filter key and never appears in the payload the host sends. Reading `matcher`
# with a `hook_event_name` fallback (the shape before #1632) resolved every
# production payload to the literal "SessionStart", which matches no branch
# below, so resume / clear / compact / fork all silently ran the startup path.
# `matcher` is kept first for hand-fed payloads, and `session_source` trails it
# for parity with adapter/codex/hooks/on-session-start.sh.
HOOK_INPUT=""
if [ -t 0 ]; then
  HOOK_INPUT=""
else
  HOOK_INPUT=$(cat 2>/dev/null || true)
fi
MATCHER="startup"
if [ -n "$HOOK_INPUT" ]; then
  EXTRACTED=""
  if command -v node >/dev/null 2>&1; then
    EXTRACTED=$(printf '%s' "$HOOK_INPUT" | node -e '
      let raw = "";
      // Without setEncoding each Buffer chunk is decoded on its own, so a
      // multi-byte character straddling a chunk boundary becomes U+FFFD (#1544).
      process.stdin.setEncoding("utf8");
      process.stdin.on("data", (d) => { raw += d; });
      process.stdin.on("end", () => {
        try {
          const payload = JSON.parse(raw);
          const v = payload.matcher || payload.source || payload.session_source || "";
          process.stdout.write(String(v));
        } catch (e) {
          // leave stdout empty; caller falls back to regex extraction
        }
      });
    ' 2>/dev/null)
  fi
  # Fallback: regex-extract "source":"value" (or "matcher":"value") from the
  # JSON payload, used when node is unavailable or JSON parsing above yielded
  # nothing. Both are flat string fields per the Claude Code SessionStart
  # contract.
  if [ -z "$EXTRACTED" ]; then
    EXTRACTED=$(printf '%s' "$HOOK_INPUT" | sed -n 's/.*"\(matcher\|source\)"[[:space:]]*:[[:space:]]*"\([a-z]*\)".*/\2/p' | head -n 1)
  fi
  case "$EXTRACTED" in
    startup|resume|clear|compact|fork)
      MATCHER="$EXTRACTED"
      ;;
  esac
fi

# ===================================================================
# Update sentinel-skip verification
# ===================================================================
# Issue #1309: avoid Li+config + Li+update walkthrough on every session.
# 99% of sessions have no tag change, no schema change, and all config values
# resolved — verification only, no actual changes. The walkthrough costs ~4%
# context (10% with Li+config execution vs 6% without). The hook performs the
# three verifications and emits a single-line update status marker the AI
# parses to decide whether to read Li+config + Li+update at all.
#
# Three axes (ALL must pass for "unnecessary"):
#   1. adapter sentinel tag in .claude/CLAUDE.md == current LI_PLUS_REPO target tag (per LI_PLUS_CHANNEL)
#   2. Li+config.md schema canonical (no legacy keys present)
#   3. LI_PLUS_BASE_LANGUAGE and LI_PLUS_PROJECT_LANGUAGE resolved (non-comment, non-empty)
#
# Marker format (machine/AI-parseable, single line + optional reason):
#   LI_PLUS_UPDATE_STATUS=unnecessary     -> AI skips Li+update walkthrough; Li+config spot read (Read for value lookup, no execute) is permitted
#   LI_PLUS_UPDATE_STATUS=needed reason=<one or more axes>  -> AI runs normal update path
#
# AI-side contract: see adapter/claude/CLAUDE.md "Execute the following at
# startup" block. Master's literal phrase "Li+configを実行" / "Li+config を実行"
# bypasses the marker and forces the full walkthrough; that override is
# AI-side, not hook-side.
UPDATE_STATUS="needed"
UPDATE_REASONS=()

# --- axis 1: adapter sentinel tag vs current target tag ---
ADAPTER_TAG=""
if [ -f "$ADAPTER_FILE" ]; then
  ADAPTER_TAG=$(sed -n 's/^# --- Li+ BEGIN (\([^)]*\)) ---.*/\1/p' "$ADAPTER_FILE" | head -n 1)
fi

# Resolve LI_PLUS_CHANNEL from config (default = release, matches Li+update.md Phase 3.1).
LI_PLUS_CHANNEL_VAL=""
if [ -f "$CONFIG_FILE" ]; then
  LI_PLUS_CHANNEL_VAL=$(sed -n 's/^[[:space:]]*LI_PLUS_CHANNEL[[:space:]]*=[[:space:]]*\(.*\)$/\1/p' "$CONFIG_FILE" | head -n 1 | tr -d '\r')
fi
[ -n "$LI_PLUS_CHANNEL_VAL" ] || LI_PLUS_CHANNEL_VAL="release"

# Resolve target tag by channel (best-effort; failure forces "needed").
TARGET_TAG=""
case "$LI_PLUS_CHANNEL_VAL" in
  latest)
    TARGET_TAG=$(gh release view --repo Liplus-Project/liplus-language --json tagName --jq '.tagName' 2>/dev/null)
    ;;
  release)
    TARGET_TAG=$(gh release list --repo Liplus-Project/liplus-language --limit 1 --json tagName --jq '.[0].tagName' 2>/dev/null)
    ;;
  tag)
    # ls-remote is the only source of truth here: the target is the newest tag on
    # the REMOTE, not whatever this clone happens to hold locally. Do NOT fall back
    # to local `git tag` on ls-remote empty/failure -- a stale clone (remote has a
    # newer tag, local not yet fetched) would resolve its local newest tag to the
    # adapter sentinel tag and emit a false "unnecessary". On failure we leave
    # TARGET_TAG empty so the `[ -z "$TARGET_TAG" ]` check below forces "needed"
    # (confirm-impossible -> safe side; the normal Li+update version check runs).
    # Spec: Li+update.md Phase 3.1 (version check mandatory per startup; stale local
    # clone silent continuation prohibited). See issue #1454.
    TARGET_TAG=$(git -C "$LIPLUS_DIR" ls-remote --tags --sort=-creatordate origin 2>/dev/null \
      | awk -F'refs/tags/' 'NF==2 {print $2}' | sed 's/\^{}$//' | head -n 1)
    ;;
esac

if [ -z "$ADAPTER_TAG" ] || [ -z "$TARGET_TAG" ] || [ "$ADAPTER_TAG" != "$TARGET_TAG" ]; then
  UPDATE_REASONS+=("sentinel-tag(adapter=${ADAPTER_TAG:-unknown},target=${TARGET_TAG:-unknown})")
fi

# --- axis 2: Li+config.md schema canonical (no legacy keys) ---
LEGACY_HIT=""
if [ -f "$CONFIG_FILE" ]; then
  # Match active (non-comment) lines containing any legacy key form.
  LEGACY_HIT=$(grep -E '^[[:space:]]*(LI_PLUS_REPOSITORY|USER_REPOSITORY|USER_REPOSITORY_EXECUTION_MODE)[[:space:]]*=|^[[:space:]]*[^#[:space:]][^=]*_EXECUTION_MODE[[:space:]]*=' "$CONFIG_FILE" 2>/dev/null | head -n 3)
fi
if [ -n "$LEGACY_HIT" ]; then
  UPDATE_REASONS+=("legacy-schema-keys-present")
fi

# --- axis 3: language contract resolved ---
BASE_LANG=""
PROJ_LANG=""
if [ -f "$CONFIG_FILE" ]; then
  BASE_LANG=$(sed -n 's/^[[:space:]]*LI_PLUS_BASE_LANGUAGE[[:space:]]*=[[:space:]]*\(.*\)$/\1/p' "$CONFIG_FILE" | head -n 1 | tr -d '\r' | sed 's/[[:space:]]*$//')
  PROJ_LANG=$(sed -n 's/^[[:space:]]*LI_PLUS_PROJECT_LANGUAGE[[:space:]]*=[[:space:]]*\(.*\)$/\1/p' "$CONFIG_FILE" | head -n 1 | tr -d '\r' | sed 's/[[:space:]]*$//')
fi
if [ -z "$BASE_LANG" ] || [ -z "$PROJ_LANG" ]; then
  UPDATE_REASONS+=("language-contract-unresolved(base=${BASE_LANG:-unset},project=${PROJ_LANG:-unset})")
fi

# --- emit update status marker ---
# Always emit first, before any cold-start material, so AI parses it before
# deciding whether to read Li+config.md and Li+update.md.
if [ "${#UPDATE_REASONS[@]}" -eq 0 ]; then
  UPDATE_STATUS="unnecessary"
  printf '━━━ Li+ update status ━━━\n'
  printf 'LI_PLUS_UPDATE_STATUS=unnecessary tag=%s channel=%s\n' "$TARGET_TAG" "$LI_PLUS_CHANNEL_VAL"
  printf 'Sentinel-skip applies: AI skips Li+update.md re-execution this session. Li+config.md spot read (Read for value lookup, do not execute contents) is permitted.\n'
  printf 'Override: Master input containing "Li+configを実行" / "Li+config を実行" forces the full walkthrough.\n'
  printf '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
else
  REASON_STR=$(printf '%s,' "${UPDATE_REASONS[@]}")
  REASON_STR="${REASON_STR%,}"
  printf '━━━ Li+ update status ━━━\n'
  printf 'LI_PLUS_UPDATE_STATUS=needed reason=%s\n' "$REASON_STR"
  printf 'AI must read Li+config.md and execute Li+update.md walkthrough this session.\n'
  printf '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
fi

# --- unrecognized config value surfacing (#1804) ---
# A LI_PLUS_CHANNEL value outside the known set matches no branch of the `case`
# above, so TARGET_TAG stays empty and the marker falls to "needed" without ever
# saying why. What is surfaced is the key name and the literal value, not a guess
# at what was meant: normalising `Latest` would pass while `lattest` still fell
# through, so naming the value is what closes the whole silent-fallback class
# rather than its mixed-case part. The fallback behaviour itself is unchanged.
# An empty value is not surfaced -- unset is the documented default
# (docs/B.-Configuration.md), and it was already folded into "release" above.
case "$LI_PLUS_CHANNEL_VAL" in
  latest|release|tag) ;;
  *)
    printf '━━━ Li+config: unrecognized value ━━━\n'
    printf 'LI_PLUS_CHANNEL=%s is not one of: latest / release / tag. Values are case-sensitive. No target tag resolved, so the update status above is "needed".\n' "$LI_PLUS_CHANNEL_VAL"
    printf '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
    ;;
esac

# --- emit language contract values ---
# Issue #1575: the Workspace_Language_Contract is always in context (adapter
# CLAUDE.md), but resolving its VALUES was written as a procedure ("read
# Li+config.md"), and Li+config.md is not auto-loaded into any agent context.
# The contract text was therefore present while its values were not, and the
# emission fell back to the model default (observed: English self-review bodies
# on PR #1531 / #1533 in a base=ja workspace).
# Axis 3 above already extracted both values from the live config this session;
# emitting them removes the read step without baking anything into a generated
# file. Emitted on every path that reaches here, with an unresolved value
# rendered as "unset", so inside a bootstrapped session the block's absence
# never has to be distinguished from an unresolved value. The pre-bootstrap
# guard exits well before this point and emits no Li+ marker at all; the
# adapter Workspace_Language_Contract routes that state to the same ask-human
# branch as "unset".
printf '━━━ Li+ language contract ━━━\n'
printf 'LI_PLUS_BASE_LANGUAGE=%s\n' "${BASE_LANG:-unset}"
printf 'LI_PLUS_PROJECT_LANGUAGE=%s\n' "${PROJ_LANG:-unset}"
printf 'Resolved from Li+config.md at session start. Definitions, scope and precedence: Workspace_Language_Contract (adapter CLAUDE.md).\n'
printf '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'

# Emit gh install status marker after update status (only when install was attempted).
if [ -n "$GH_INSTALL_STATUS" ]; then
  printf '━━━ gh install ━━━\n%s\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n' "GH_INSTALL_STATUS=$GH_INSTALL_STATUS"
fi

# --- sha256 helper (portable: prefers sha256sum, falls back to shasum -a 256) ---
sha256_of() {
  local input="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    printf '%s' "$input" | sha256sum | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    printf '%s' "$input" | shasum -a 256 | awk '{print $1}'
  else
    # No sha256 tool available — return empty so the caller treats diff as
    # unavailable and falls back to full emit.
    printf ''
  fi
}

emit_section() {
  local banner="$1"
  local body="$2"
  [ -n "$body" ] || return 0
  printf '━━━ %s ━━━\n%s\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n' "$banner" "$body"
}

# Section registry (parallel arrays). Keys are stable identifiers used in the
# state JSON; banners are the human-facing section titles; bodies are filled
# below by the gather phase.
SECTION_KEYS=()
SECTION_BANNERS=()
SECTION_BODIES=()

register_section() {
  local key="$1"
  local banner="$2"
  local body="$3"
  SECTION_KEYS+=("$key")
  SECTION_BANNERS+=("$banner")
  SECTION_BODIES+=("$body")
}

# --- coldstart anchor block from rules/evolution/cold-start-synthesis.md ---
# This section is ALWAYS emitted (drift recovery anchor). It is not part of the
# diff-only comparison set.
#
# Anchor = the H1 preamble only, cut at the first H2 semantic tag. The rule file
# is always-on loaded, so emitting it whole put the same text in one session's
# context twice; the preamble is the part the AI applies at the step 3 moment,
# and the H2 sections below it (hook emission contract, observation surface) are
# the hook's own behavior spec. A file with no H2 section emits whole: the cut is
# an economy and losing the anchor is the worse failure. Contract source =
# rules/evolution/cold-start-synthesis.md Hook Emission Contract (Anchor cut).
COLDSTART_LITERAL=""
if [ -f "$COLDSTART_MD" ]; then
  # Strip frontmatter (lines between first two `---` markers) and H1 line, then
  # stop at the first H2 opening tag seen after the H1.
  COLDSTART_LITERAL=$(awk '
    /^---$/ { n++; next }
    n < 2   { next }
    seen_h1 && /^<[a-z0-9-]+>$/ { exit }
    /^# /   { seen_h1 = 1 }
            { print }
  ' "$COLDSTART_MD" | sed '1{/^# /d;}' | sed '/./,$!d')
fi

# --- recent decision structure index entries (head of file = index) ---
DECISION_HEAD=""
if [ -f "$DECISION_STRUCTURE" ]; then
  DECISION_HEAD=$(head -n 20 "$DECISION_STRUCTURE")
fi
register_section "decision_structure_head" "Decision structure index (docs/Decision-Structure.md head)" "$DECISION_HEAD"

# --- rules/ tree (fetch address table for cold-start-loaded rules cache) ---
# Issue #1422: cold-start loads the rule literal text into context, but at the
# judgment moment AI's attention does not always reach back to the underlying
# rule. Emitting the path tree of rules/ as an in-context index lets the AI
# resolve "which rule path should I read" without scanning loose headers across
# the prior emission. Filename = semantic identifier (kebab-case slugify of the
# heading topic) per rules/model/liplus-coding-rule.md Source File Format, so
# the path alone carries enough signal; no description extraction needed here.
#
# Generation is dynamic (per session), not a static artifact, to avoid stale
# cache after rule add / rename. Sits inside the diff-only mode via
# register_section, so unchanged trees do not re-emit.
#
# Scope = rules/ only. skills/ is handled by the host auto-invoke router on a
# separate axis; adapter/ is not a judgment-time fetch target.
RULES_TREE=""
if [ -d "$LIPLUS_DIR/rules" ]; then
  RULES_TREE=$(cd "$LIPLUS_DIR" && find rules -type f -name '*.md' 2>/dev/null | LC_ALL=C sort)
fi
register_section "rules_tree" "Rules tree (fetch address table for rules/ cache)" "$RULES_TREE"

# --- most recent release tag (includes prereleases) ---
LATEST_RELEASE=$(gh release list -R Liplus-Project/liplus-language --limit 3 2>/dev/null \
  | head -n 3)
register_section "recent_releases" "Recent releases (includes prereleases)" "$LATEST_RELEASE"

# --- open high-priority issues (in-progress + ready, capped) ---
OPEN_ISSUES=$(gh issue list -R Liplus-Project/liplus-language \
  --state open --label in-progress --limit 5 \
  --json number,title,labels \
  --jq '.[] | "#\(.number) \(.title) [\(.labels | map(.name) | join(","))]"' 2>/dev/null)
register_section "open_in_progress_issues" "Open in-progress issues (max 5)" "$OPEN_ISSUES"

# --- latest self-evaluation entry from host memory (if exists) ---
# Claude Code stores user memory at ~/.claude/projects/<slug>/memory/, where <slug>
# is CLAUDE_PROJECT_DIR with ':', '/', and '\' all replaced by '-'.
# Best-effort read only: silent skip when the file is absent.
CPD="${CLAUDE_PROJECT_DIR:-$PROJECT_ROOT}"
CCD_SLUG=$(printf '%s' "$CPD" | sed 's|[:/\\]|-|g')
# Scope guard for the two glob fallbacks below (#1796).
#
# The two named candidates can both miss while a populated memory directory sits
# under a slug the derivation above did not produce. Rescuing that mismatch is
# what the glob fallbacks are for and it stays. What they must not do is reach a
# *different workspace*: the self-eval head, the promotion candidates and the
# observation surface are this session's observe-stage input, and another
# workspace's memory is not an observation of this one. The populated condition
# below is right inside a slug and does not select between slugs; an empty memory
# directory must read as "no material" and skip silently rather than send the
# search next door.
#
# Accepted = a slug denoting CLAUDE_PROJECT_DIR itself or a directory enclosing
# it, i.e. the candidate slug is CCD_SLUG or a `-`-boundary prefix of it. That
# keeps the rescue whose answer is still this workspace (a session opened below
# the workspace root - a worktree, say - whose material lives at the root) and
# drops every reach sideways. The other direction is not added: no observation
# has needed it, and `rules/model/subtractive-structural-beauty.md` (B) leaves
# an unrequested reach out.
#
# The comparison is on the encoded form because the encoding is lossy and no
# decode exists - a sibling directory whose name is our own with a path-looking
# suffix appended reads as enclosing us. That residual is bounded to siblings
# under our own parent; the boundary the defect crossed is the one this holds.
memory_slug_encloses_project() {
  local parent="${1%/memory}"
  local slug="${parent##*/}"
  # Either side empty would turn the boundary-prefix test into "accept every
  # slug", which is the defect itself. Refuse instead. Not hypothetical on the
  # CCD_SLUG side: PROJECT_ROOT falls back to "." when CLAUDE_PROJECT_DIR is
  # unset, and a slug that names no workspace must select no workspace.
  [ -n "$CCD_SLUG" ] && [ -n "$slug" ] || return 1
  case "$CCD_SLUG" in
    "$slug"|"$slug"-*) return 0 ;;
  esac
  return 1
}

SELFEVAL_FOUND=""
for candidate in \
  "$HOME/.claude/projects/$CCD_SLUG/memory/self-evaluation_log.md" \
  "$PROJECT_ROOT/memory/self-evaluation_log.md"; do
  if [ -f "$candidate" ]; then
    SELFEVAL_FOUND="$candidate"
    break
  fi
done
# Glob fallback: most recently modified self-eval log under a project slug that
# is in scope for this session (memory_slug_encloses_project above, #1796).
if [ -z "$SELFEVAL_FOUND" ]; then
  while IFS= read -r selfevalcandidate; do
    [ -n "$selfevalcandidate" ] || continue
    if memory_slug_encloses_project "${selfevalcandidate%/*}"; then
      SELFEVAL_FOUND="$selfevalcandidate"
      break
    fi
  done < <(ls -1t "$HOME"/.claude/projects/*/memory/self-evaluation_log.md 2>/dev/null)
fi
SELFEVAL_HEAD=""
if [ -n "$SELFEVAL_FOUND" ] && [ -f "$SELFEVAL_FOUND" ]; then
  SELFEVAL_HEAD=$(head -n 15 "$SELFEVAL_FOUND")
fi
register_section "self_eval_head" "Self-evaluation log head (most recent)" "$SELFEVAL_HEAD"

# --- promotion candidates (memory → Li+ source) ---
# Evolution Loop observe stage: surface pattern-detection candidates at cold-start
# so that AI sees promotion candidates without waiting for passive noticing.
# rules/evolution/evolution.md "Pattern Detection Surfacing At Cold-start" fixes
# the three detection targets (self-evaluation log repetition / recent memory
# additions / keyword overlap with Li+ source) and delegates the thresholds and
# the concrete logic to the adapter, which is this block.
# All three detectors are best-effort; silent skip when sources are absent.
# Threshold is adjustable via THRESHOLD_N (initial value = 2, see issue #1080).
# SURFACE_CAP bounds the two list-shaped detectors. This is an orientation
# surface read at session opening, and a list past roughly this length stops
# being scannable; the full count is still printed, so a truncated list never
# hides that more exists.
#
# #1632 F3: every detector below used to read a format nothing writes, so the
# section was empty on every session and an empty surface could not be told
# apart from "nothing crossed the noise floor". Detector 1 matched a
# `root_cause:` / `tags:` line syntax that no spec defines and the log has never
# used; detectors 2 and 3 scanned the flat feedback.md / project.md pair that the
# one-memory-per-file host layout replaced. The formats read below are the ones
# the live artifacts actually carry.
THRESHOLD_N=2
SURFACE_CAP=10

# A candidate qualifies as MEMORY_DIR only when it holds at least one file that
# some MEMORY_DIR consumer reads. Directory existence alone is not the criterion:
# an empty higher-precedence directory would otherwise shadow a populated
# lower-precedence one and silence every consumer at once.
# The marker set is the files MEMORY_DIR consumers read: the observation surface,
# the promotion tally expiry surface,
# the per-topic entry-file prefixes the promotion detectors scan, plus
# self-evaluation_log.md so that both resolution paths agree on what counts as a
# memory directory. That last member never decides a case in practice: the
# self-eval lookup above scans the same candidate directories, so whenever that
# file exists the primary path has already claimed the directory before this
# check runs.
# The prefixes replace the former flat feedback.md / project.md pair (#1632 F3):
# the host auto-memory layout is one memory per file, so a live memory directory
# holds feedback_<topic>.md / project_<topic>.md / reference_<topic>.md /
# user_<topic>.md and neither flat name exists. Matching prefixes rather than any
# *.md is deliberate — an unrelated file must not let a directory claim the slot.
memory_dir_populated() {
  for markerfile in \
    self-evaluation_log.md \
    self-evolution-observation.md \
    promotion_tally.md; do
    if [ -f "$1/$markerfile" ]; then
      return 0
    fi
  done
  for markerglob in "$1"/feedback*.md "$1"/project*.md "$1"/reference*.md "$1"/user*.md; do
    if [ -f "$markerglob" ]; then
      return 0
    fi
  done
  return 1
}

# Memory entry files inside a resolved MEMORY_DIR, under the same one-memory-
# per-file layout. Excluded are the index and the three transient operational
# files, each of which has its own dedicated reader: MEMORY.md is read by the
# index emit, self-evaluation_log.md by the self-eval head, and the two
# date-driven surfaces below read self-evolution-observation.md and
# promotion_tally.md. Flat feedback.md /
# project.md are NOT excluded, so a workspace that has not migrated is still
# scanned. Sorted, because the detector output is sha256-fingerprinted for
# diff-only emission and must not depend on directory order.
memory_entry_files() {
  find "$1" -maxdepth 1 -type f -name '*.md' 2>/dev/null | LC_ALL=C sort | while IFS= read -r entryfile; do
    case "${entryfile##*/}" in
      MEMORY.md|promotion_tally.md|self-evaluation_log.md|self-evolution-observation.md) ;;
      *) printf '%s\n' "$entryfile" ;;
    esac
  done
}

# Title of one memory entry = its frontmatter `name:` (written by the host
# auto-memory) when present, else the filename stem. Under the flat-file layout
# the equivalent unit was a `## ` section header; with one memory per file the
# file itself is the entry, so the title moves to the frontmatter.
memory_entry_title() {
  local title
  title=$(head -n 10 "$1" 2>/dev/null | sed -n 's/^name:[[:space:]]*//p' | head -n 1 \
    | tr -d '\r' | sed 's/[[:space:]]*$//')
  if [ -z "$title" ]; then
    title="${1##*/}"
    title="${title%.md}"
  fi
  printf '%s' "$title"
}

# Resolve memory directory using the same lookup path as self-evaluation_log.md.
# The directory is probed directly when that file is absent: other readers of
# MEMORY_DIR (feedback/project detectors, self-evolution observation surface)
# must not be silenced by the absence of an unrelated file.
MEMORY_DIR=""
if [ -n "$SELFEVAL_FOUND" ]; then
  MEMORY_DIR=$(dirname "$SELFEVAL_FOUND")
else
  for memcandidate in \
    "$HOME/.claude/projects/$CCD_SLUG/memory" \
    "$PROJECT_ROOT/memory"; do
    if memory_dir_populated "$memcandidate"; then
      MEMORY_DIR="$memcandidate"
      break
    fi
  done
  # Glob fallback mirrors the self-eval log fallback: most recently modified
  # memory dir under a project slug in scope for this session, populated ones
  # only. The scope guard is what keeps the populated condition from reaching
  # across a workspace boundary (memory_slug_encloses_project, #1796); the two
  # conditions are separate and both must hold.
  if [ -z "$MEMORY_DIR" ]; then
    while IFS= read -r memcandidate; do
      [ -n "$memcandidate" ] || continue
      memory_slug_encloses_project "$memcandidate" || continue
      if memory_dir_populated "$memcandidate"; then
        MEMORY_DIR="$memcandidate"
        break
      fi
    done < <(ls -1td "$HOME"/.claude/projects/*/memory 2>/dev/null)
  fi
fi

PROMOTION_BODY=""

# Detector 1: the same observational axis tagged `miss` across several
# self-evaluation entries. That repetition is the one the spec names:
# `skills/evolution-self-eval/SKILL.md` Recording — "Repeated miss on the same
# axis across entries = weakness region = distill candidate for evolution loop".
#
# The line format this reads is specified, not inferred: `skills/evolution-self-eval/SKILL.md`
# "Axis tag line format" fixes the two layouts, the axis-name normal form and the
# inline list terminator. Everything below implements that section and nothing
# beyond it; when the two disagree, the skill is the source. Before #1651 no spec
# held the format at all, so the log drifted and the detector went quiet.
#
#   **Axis tags**: <axis>: <verdict> / <axis>: <verdict> / ...   (one line)
#   **Axis tags (10-axis)**:                                     (header, then)
#   - <axis>: <verdict>                                          (bullets)
if [ -n "$SELFEVAL_FOUND" ] && [ -f "$SELFEVAL_FOUND" ]; then
  AXIS_MISSES=$(awk -v n="$THRESHOLD_N" '
    BEGIN {
      # The 10 axes, verbatim and lowercased. Canonical vocabulary for the
      # normal form: a shorthand that is a word-boundary prefix of exactly one
      # of these expands to it, which is why no alias table exists.
      canon_n = split("assumption surfacing,contradiction catch,deepening axis fit," \
                      "silence respect,loop entry,character drift,review partition," \
                      "gist vs literal,expansion limit,request depth", canon, ",")
      # Bracket tokens the scans below track. ASCII and full-width are one
      # class: an opener of either kind is closed by a closer of either kind.
      # Tracking a further pair is one more entry in this table, not another
      # character test wired into the walk — comparing characters inline is
      # what left the full-width pair untracked while the ASCII pair worked.
      tok_n = 0
      tok_k = split("(,（", tok_src, ",")
      for (tok_i = 1; tok_i <= tok_k; tok_i++) {
        tok_n++; brk_tok[tok_n] = tok_src[tok_i]; brk_tok_open[tok_n] = 1
      }
      tok_k = split("),）", tok_src, ",")
      for (tok_i = 1; tok_i <= tok_k; tok_i++) {
        tok_n++; brk_tok[tok_n] = tok_src[tok_i]; brk_tok_open[tok_n] = 0
      }
    }
    # Bracket occurrences in hay, positions ascending, with the ones that have
    # no partner dropped. Both ends must be present before the span between them
    # counts as bracketed: a stray `)` was always ignored, while a stray `(`
    # used to hold the rest of the line inside brackets, so every pair written
    # after it went uncounted. Results land in occ_*; the return is the count.
    function bracket_map(hay,   n, cursor, k, p, best, bestk, seg, i, top, stack) {
      split("", occ_pos, ","); split("", occ_open, ","); split("", occ_live, ",")
      n = 0; cursor = 1
      while (1) {
        seg = substr(hay, cursor)
        best = 0; bestk = 0
        for (k = 1; k <= tok_n; k++) {
          p = index(seg, brk_tok[k])
          if (p > 0 && (best == 0 || p < best)) { best = p; bestk = k }
        }
        if (best == 0) break
        n++
        occ_pos[n] = cursor + best - 1
        occ_open[n] = brk_tok_open[bestk]
        occ_live[n] = 0
        cursor = occ_pos[n] + length(brk_tok[bestk])
      }
      top = 0
      for (i = 1; i <= n; i++) {
        if (occ_open[i]) { top++; stack[top] = i }
        else if (top > 0) { occ_live[stack[top]] = 1; occ_live[i] = 1; top-- }
      }
      return n
    }
    # First position of needle in hay that sits outside brackets, or 0.
    # Every offset comes from index(), substr() and length() over one string, so
    # the scan reads the same whether this awk counts in bytes or in characters.
    function outer_index(hay, needle,   n, base, rel, pos, i, depth) {
      n = bracket_map(hay)
      base = 0
      while (1) {
        rel = index(substr(hay, base + 1), needle)
        if (rel == 0) return 0
        pos = base + rel
        depth = 0
        for (i = 1; i <= n; i++) {
          if (occ_pos[i] >= pos) break
          if (occ_live[i] == 0) continue
          if (occ_open[i]) depth++
          else depth--
        }
        if (depth == 0) return pos
        base = pos
      }
    }
    # First position of a bracket opener in s, or 0. Matching is not required
    # here: the normal form drops the qualifier and everything after it.
    function open_index(s,   k, p, best) {
      best = 0
      for (k = 1; k <= tok_n; k++) {
        if (brk_tok_open[k] == 0) continue
        p = index(s, brk_tok[k])
        if (p > 0 && (best == 0 || p < best)) best = p
      }
      return best
    }
    # Inline list end: the pair list stops at the first outside-brackets
    # sentence terminator or `Root cause:` / `Domain:` label. Without this the
    # last segment ran to end of line and swallowed the free-form trailer, which
    # both fed that prose to the miss scan and split a parenthetical " / " inside
    # it into a phantom axis.
    function cut_trailer(rest,   best, p, k, marks) {
      split("。,Root cause:,Domain:", marks, ",")
      best = 0
      for (k = 1; k <= 3; k++) {
        p = outer_index(rest, marks[k])
        if (p > 0 && (best == 0 || p < best)) best = p
      }
      return (best > 0) ? substr(rest, 1, best - 1) : rest
    }
    # Axis name normal form, step for step as the skill lists it.
    function normalize_axis(axis,   p, k, hits, expanded) {
      gsub(/\*/, "", axis)
      p = open_index(axis)
      if (p > 0) axis = substr(axis, 1, p - 1)
      gsub(/[-_]/, " ", axis)
      gsub(/[[:space:]]+/, " ", axis)
      sub(/^ /, "", axis)
      sub(/ $/, "", axis)
      axis = tolower(axis)
      if (axis == "") return ""
      hits = 0
      for (k = 1; k <= canon_n; k++) {
        if (canon[k] == axis) return axis
        if (substr(canon[k], 1, length(axis) + 1) == axis " ") {
          hits++
          expanded = canon[k]
        }
      }
      # Ambiguous shorthand stays as written; guessing would merge two axes.
      return (hits == 1) ? expanded : axis
    }
    function record(pair,   sep, axis, verdict) {
      sep = index(pair, ":")
      if (sep == 0) return
      axis = normalize_axis(substr(pair, 1, sep - 1))
      verdict = substr(pair, sep + 1)
      if (axis == "") return
      # A verdict counts as a miss when the word appears anywhere in it, so
      # `**miss (primary)**` and `miss→hit` both register.
      if (index(tolower(verdict), "miss") == 0) return
      count[axis]++
    }
    /^[[:space:]]*\*\*Axis tags/ {
      # Everything past the closing "**:" of the label is the inline pair list;
      # an empty remainder means the bullet layout follows.
      label_end = index($0, "**:")
      rest = (label_end > 0) ? substr($0, label_end + 3) : ""
      if (rest ~ /[^[:space:]]/) {
        rest = cut_trailer(rest)
        while ((sep_pos = outer_index(rest, " / ")) > 0) {
          record(substr(rest, 1, sep_pos - 1))
          rest = substr(rest, sep_pos + 3)
        }
        record(rest)
        in_axis_block = 0
      } else {
        in_axis_block = 1
      }
      next
    }
    in_axis_block && /^[[:space:]]*-[[:space:]]/ {
      # One bullet is one pair: the line break already ends the verdict, so the
      # inline terminator does not apply here.
      bullet = $0
      sub(/^[[:space:]]*-[[:space:]]*/, "", bullet)
      record(bullet)
      next
    }
    in_axis_block { in_axis_block = 0 }
    END {
      for (axis in count) {
        if (count[axis] >= n) {
          printf "  - axis \"%s\" tagged miss x%d\n", axis, count[axis]
        }
      }
    }
  ' "$SELFEVAL_FOUND" | LC_ALL=C sort)
  if [ -n "$AXIS_MISSES" ]; then
    PROMOTION_BODY="${PROMOTION_BODY}repeated self-evaluation axis misses:
${AXIS_MISSES}
"
  fi
fi

# Detector 2: memory entries written or rewritten within the last 7 days.
# One memory is one file, so the entry is the unit of recency and file mtime is
# the signal; the flat-file era counted '## ' sections inside two files instead.
# Flagged when the count reaches THRESHOLD_N.
#
# Note: this 7d window is the memory-scan recency window (Cold-start observe
# stage surface), independent from the 3d cluster window in
# rules/evolution/promotion-judgment.md. The two timers serve different axes:
#   - 7d here = "did anything new land in memory recently? show it for AI review"
#   - 3d there = "has the same cluster crossed the noise floor for promotion?"
# Do not unify the two values; they intentionally sit on different axes.
if [ -n "$MEMORY_DIR" ] && [ -d "$MEMORY_DIR" ]; then
  RECENT_ENTRIES=""
  RECENT_COUNT=0
  while IFS= read -r memfile; do
    [ -n "$memfile" ] || continue
    # entry modified within last 7 days?
    if find "$memfile" -mtime -7 -print 2>/dev/null | grep -q .; then
      RECENT_COUNT=$((RECENT_COUNT + 1))
      if [ "$RECENT_COUNT" -le "$SURFACE_CAP" ]; then
        RECENT_ENTRIES="${RECENT_ENTRIES}  - ${memfile##*/} [$(memory_entry_title "$memfile")]
"
      fi
    fi
  done < <(memory_entry_files "$MEMORY_DIR")
  if [ "$RECENT_COUNT" -ge "$THRESHOLD_N" ]; then
    # A consolidate pass rewrites every entry at once, so the cap is a normal
    # occurrence rather than an edge case.
    if [ "$RECENT_COUNT" -gt "$SURFACE_CAP" ]; then
      RECENT_ENTRIES="${RECENT_ENTRIES}  - ... and $((RECENT_COUNT - SURFACE_CAP)) more
"
    fi
    PROMOTION_BODY="${PROMOTION_BODY}recent memory additions (<= 7d, ${RECENT_COUNT} entries):
${RECENT_ENTRIES}"
  fi
fi

# Detector 3: keyword overlap between memory entry titles and Li+ source files.
# Tokens are the >= 4-char ASCII alphanumeric words of an entry title; a hit
# means the entry's topic already has a surface in rules/ or skills/. Surfaced
# as a "possible overlap" hint — not a promotion decision.
#
# The four entry-type prefixes are dropped: under the per-topic naming scheme
# they classify the entry rather than name its topic, so they would match nearly
# every source file and drown the real signal. A non-ASCII title yields no
# tokens and is simply skipped, as before.
#
# A pair is reported only once at least THRESHOLD_N distinct title tokens land in
# the same source file. One shared common word ("identity", "answer") is
# coincidence at this corpus size and produced hundreds of lines when measured
# against the live memory set; two independent words of one title meeting in one
# file is topical adjacency, which is what this detector is looking for.
#
# The source is named by its path relative to the clone, not by basename: every
# skill file is called SKILL.md, so a basename label identifies nothing.
#
# One awk pass over the whole source set replaces the previous nested loop,
# which re-read every source file once per title (title count x source count
# whole-file reads, plus one grep per token). Source paths are handed over as a
# list file and read with getline, so a workspace path containing spaces stays
# intact. awk emits every qualifying pair; the sort and the cap are applied
# after it, in that order. Sorting first is what makes the truncation stable —
# awk's `for (k in array)` order is unspecified, so capping inside awk would
# pick a different subset per run and churn the sha256 the diff-only emission
# compares against.
if [ -n "$MEMORY_DIR" ] && [ -d "$MEMORY_DIR" ]; then
  OVERLAP=""
  OVERLAP_ALL=""
  TMP_TOKENS=$(mktemp 2>/dev/null || echo "/tmp/liplus-tokens-$$")
  TMP_SRCLIST=$(mktemp 2>/dev/null || echo "/tmp/liplus-srclist-$$")
  : > "$TMP_TOKENS"
  while IFS= read -r memfile; do
    [ -n "$memfile" ] || continue
    entry_title=$(memory_entry_title "$memfile")
    entry_label="${memfile##*/} [${entry_title}]"
    printf '%s' "$entry_title" | tr 'A-Z' 'a-z' | tr -cs 'a-z0-9' '\n' \
      | awk -v lbl="$entry_label" '
          length($0) >= 4 &&
          $0 != "feedback" && $0 != "project" && $0 != "reference" && $0 != "user" {
            print lbl "\t" $0
          }' >> "$TMP_TOKENS"
  done < <(memory_entry_files "$MEMORY_DIR")
  find "$LIPLUS_DIR/rules" -type f -name '*.md' 2>/dev/null > "$TMP_SRCLIST"
  find "$LIPLUS_DIR/skills" -maxdepth 2 -type f -name 'SKILL.md' 2>/dev/null >> "$TMP_SRCLIST"
  if [ -s "$TMP_TOKENS" ] && [ -s "$TMP_SRCLIST" ]; then
    OVERLAP_ALL=$(awk -v n="$THRESHOLD_N" -v root="$LIPLUS_DIR/" '
      # pass 1: "<entry label>\t<token>" lines
      NR == FNR {
        sep = index($0, "\t")
        if (sep == 0) next
        tn++
        tlabel[tn] = substr($0, 1, sep - 1)
        ttok[tn] = substr($0, sep + 1)
        wanted[ttok[tn]] = 1
        next
      }
      # pass 2: one Li+ source path per line
      {
        path = $0
        if (path == "") next
        src = path
        if (substr(src, 1, length(root)) == root) src = substr(src, length(root) + 1)
        gsub(/\\/, "/", src)
        while ((getline srcline < path) > 0) {
          words = tolower(srcline)
          gsub(/[^a-z0-9]+/, " ", words)
          wc = split(words, w, " ")
          for (i = 1; i <= wc; i++) {
            if (!(w[i] in wanted)) continue
            if ((src SUBSEP w[i]) in seen) continue
            seen[src SUBSEP w[i]] = 1
            srcs[w[i]] = srcs[w[i]] " " src
          }
        }
        close(path)
      }
      END {
        for (j = 1; j <= tn; j++) {
          if (!(ttok[j] in srcs)) continue
          fc = split(srcs[ttok[j]], f, " ")
          for (i = 1; i <= fc; i++) {
            if (f[i] == "") continue
            key = tlabel[j] SUBSEP f[i]
            hit[key] = hit[key] " " ttok[j]
            depth[key]++
          }
        }
        for (key in hit) {
          if (depth[key] < n) continue
          split(key, part, SUBSEP)
          # Rank prefix = inverted token count, zero padded, so a plain
          # lexicographic sort orders strongest adjacency first and falls back
          # to the line text for ties. Keeping the ordering inside plain `sort`
          # avoids depending on a field-separator flag; `cut` strips the prefix.
          printf "%03d\t  - %s ~ %s (tokens:%s)\n", 999 - depth[key], part[1], part[2], hit[key]
        }
      }
    ' "$TMP_TOKENS" "$TMP_SRCLIST" | LC_ALL=C sort | cut -f2-)
  fi
  rm -f "$TMP_TOKENS" "$TMP_SRCLIST"
  if [ -n "$OVERLAP_ALL" ]; then
    OVERLAP_COUNT=$(printf '%s\n' "$OVERLAP_ALL" | grep -c '^  - ')
    OVERLAP=$(printf '%s\n' "$OVERLAP_ALL" | head -n "$SURFACE_CAP")
    if [ "${OVERLAP_COUNT:-0}" -gt "$SURFACE_CAP" ]; then
      OVERLAP="${OVERLAP}
  - ... and $((OVERLAP_COUNT - SURFACE_CAP)) more"
    fi
    PROMOTION_BODY="${PROMOTION_BODY}possible keyword overlap with Li+ source (${OVERLAP_COUNT} pairs):
${OVERLAP}
"
  fi
fi
register_section "promotion_candidates" "Promotion candidates (memory → Li+ source)" "$PROMOTION_BODY"

# --- self-evolution observation surface (due / overdue) ---
# Implements rules/evolution/cold-start-synthesis.md "Self-Evolution Observation
# Surface" (issue #1537 — the contract existed, the adapter side did not):
#   next_check <= today AND verdict_state == pending -> "observation due"
#   expires    <  today AND verdict_state == pending -> "observation overdue,
#                                                       human judgment needed"
#
# NOT registered via register_section — this section is deliberately outside the
# diff-only comparison set (same treatment as the cold-start rule anchor, for a
# different reason). The trigger is date-driven while the body is content-driven:
# an unresolved entry produces a byte-identical body day after day, so a
# fingerprint comparison would surface it exactly once and then suppress it for
# the whole period during which it still needs attention. An empty body is a
# silent skip (nothing due), so always-emit costs nothing in the common case.
#
# Source file = memory/self-evolution-observation.md, resolved through the same
# MEMORY_DIR lookup the promotion detectors above already use. Silent skip when
# the file is absent (workspace-local + gitignored; absence is normal).
#
# An entry past expires is reported as OVERDUE only. Its next_check is normally
# also in the past, but reporting the same entry on both axes is noise, and
# overdue is the axis that carries the escalation.
#
# Date comparison is lexicographic on ISO YYYY-MM-DD, which is order-preserving.
OBSERVATION_BODY=""
OBSERVATION_FILE=""
if [ -n "$MEMORY_DIR" ] && [ -f "$MEMORY_DIR/self-evolution-observation.md" ]; then
  OBSERVATION_FILE="$MEMORY_DIR/self-evolution-observation.md"
fi
if [ -n "$OBSERVATION_FILE" ]; then
  TODAY=$(date +%Y-%m-%d 2>/dev/null || echo "")
  if [ -n "$TODAY" ]; then
    OBSERVATION_LIST=$(awk -v today="$TODAY" '
      function flush(   label) {
        if (name == "") return
        if (state == "pending") {
          label = ""
          if (expires != "" && expires < today) {
            label = "OVERDUE (expires " expires ", human judgment needed)"
          } else if (nextcheck != "" && nextcheck <= today) {
            label = "DUE (next_check " nextcheck ")"
          }
          if (label != "") {
            printf "  - %s: %s%s\n", label, name, (pr == "" ? "" : " [PR #" pr "]")
          }
        }
        name = ""; pr = ""; expires = ""; nextcheck = ""; state = ""
      }
      /^##[[:space:]]+observation:/ {
        flush()
        v = $0
        sub(/^##[[:space:]]+observation:[[:space:]]*/, "", v)
        gsub(/[[:space:]]+$/, "", v)
        name = v
        next
      }
      name != "" && /^[[:space:]]*pr:[[:space:]]*/ {
        v = $0; sub(/^[[:space:]]*pr:[[:space:]]*/, "", v); gsub(/[[:space:]]+$/, "", v); pr = v; next
      }
      name != "" && /^[[:space:]]*expires:[[:space:]]*/ {
        v = $0; sub(/^[[:space:]]*expires:[[:space:]]*/, "", v); gsub(/[[:space:]]+$/, "", v); expires = v; next
      }
      name != "" && /^[[:space:]]*next_check:[[:space:]]*/ {
        v = $0; sub(/^[[:space:]]*next_check:[[:space:]]*/, "", v); gsub(/[[:space:]]+$/, "", v); nextcheck = v; next
      }
      name != "" && /^[[:space:]]*verdict_state:[[:space:]]*/ {
        v = $0; sub(/^[[:space:]]*verdict_state:[[:space:]]*/, "", v); gsub(/[[:space:]]+$/, "", v); state = v; next
      }
      /^##[[:space:]]/ { flush() }
      END { flush() }
    ' "$OBSERVATION_FILE")
    if [ -n "$OBSERVATION_LIST" ]; then
      OBSERVATION_BODY="memory/self-evolution-observation.md - entries whose check window has opened:
${OBSERVATION_LIST}
Surfacing is observation, not auto-action. Verdict transition (settle / revert /
supersede) follows rules/evolution/memory-entry-format.md Self-Evolution
Observation Format."
    fi
  fi
fi

# --- promotion tally expiry surface (due / overdue) ---
# Implements rules/evolution/cold-start-synthesis.md "Promotion Tally Expiry
# Surface" (issue #1894):
#   expires <= today -> "tally expiry reached"
#   expires <  today -> "tally expiry overdue, threshold judgment not taken"
#
# Same treatment as the observation surface above and for the same reasons: NOT
# registered via register_section (date-driven trigger over a content-driven
# body, so a fingerprint would surface a cluster once and then suppress it for
# the whole period it still needs a judgment), overdue reported alone (one item
# on two axes is noise), empty body = silent skip, lexicographic ISO date
# comparison.
#
# No verdict field is read because the tally format carries none: every outcome
# the Threshold Rules name removes the cluster, so a cluster still written down
# is a judgment not yet taken. The occurrence count is carried on the line
# because it selects the Threshold Rules row that applies.
TALLY_BODY=""
TALLY_FILE=""
if [ -n "$MEMORY_DIR" ] && [ -f "$MEMORY_DIR/promotion_tally.md" ]; then
  TALLY_FILE="$MEMORY_DIR/promotion_tally.md"
fi
if [ -n "$TALLY_FILE" ]; then
  TODAY=$(date +%Y-%m-%d 2>/dev/null || echo "")
  if [ -n "$TODAY" ]; then
    TALLY_LIST=$(awk -v today="$TODAY" '
      function flush(   label) {
        if (name == "") return
        label = ""
        if (expires != "" && expires < today) {
          label = "OVERDUE (expires " expires ", threshold judgment not taken)"
        } else if (expires != "" && expires <= today) {
          label = "DUE (expires " expires ")"
        }
        if (label != "") {
          printf "  - %s: %s [occurrences: %d]\n", label, name, occ
        }
        name = ""; expires = ""; occ = 0
      }
      /^##[[:space:]]+cluster:/ {
        flush()
        v = $0
        sub(/^##[[:space:]]+cluster:[[:space:]]*/, "", v)
        gsub(/[[:space:]]+$/, "", v)
        name = v
        next
      }
      name != "" && /^[[:space:]]*expires:[[:space:]]*/ {
        v = $0; sub(/^[[:space:]]*expires:[[:space:]]*/, "", v); gsub(/[[:space:]]+$/, "", v); expires = v; next
      }
      name != "" && /^[[:space:]]*-[[:space:]]/ { occ++; next }
      /^##[[:space:]]/ { flush() }
      END { flush() }
    ' "$TALLY_FILE")
    if [ -n "$TALLY_LIST" ]; then
      TALLY_BODY="memory/promotion_tally.md - clusters whose 3d window has closed:
${TALLY_LIST}
Surfacing is observation, not auto-action. The threshold judgment (issue
creation / merge into an existing promotion-marker issue / deletion) follows
rules/evolution/promotion-judgment.md Threshold Rules."
    fi
  fi
fi

# ===================================================================
# Emission phase
# ===================================================================
#
# Always emit cold-start rule anchor first (drift recovery anchor).
emit_section "Cold-start Synthesis (rules/evolution/cold-start-synthesis.md anchor)" "$COLDSTART_LITERAL"

# Non-startup matchers (resume / clear / compact / fork): only the cold-start
# anchor is emitted. The work context is continuous; re-emitting the full
# material set would be the redundant noise this diff-only design exists to
# eliminate.
if [ "$MATCHER" != "startup" ]; then
  cat <<EOF
━━━ Cold-start Synthesis: instruction ━━━
Matcher = ${MATCHER}. Session is continuous (resume/clear/compact/fork). Only
the cold-start rule anchor is re-anchored above. Treat the prior session's
in-context state as authoritative; do not re-orient from scratch.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EOF
  exit 0
fi

# --- self-evolution observation surface (outside the diff-only set) ---
# Emitted before the diff sections so a due/overdue entry is not buried under
# whatever else changed. Empty body = silent skip (see gather phase above).
OBSERVATION_EMITTED=0
if [ -n "$OBSERVATION_BODY" ]; then
  emit_section "Self-evolution observation (due / overdue)" "$OBSERVATION_BODY"
  OBSERVATION_EMITTED=1
fi

# --- promotion tally expiry surface (outside the diff-only set) ---
# Emitted next to the observation surface, before the diff sections, for the
# same reason: a closed window must not be buried under whatever else changed.
TALLY_EMITTED=0
if [ -n "$TALLY_BODY" ]; then
  emit_section "Tally expiry (due / overdue)" "$TALLY_BODY"
  TALLY_EMITTED=1
fi

# --- diff-only logic (startup matcher only) ---
#
# Compute current fingerprint per section. Load prior fingerprint set from
# state. Emit a section iff its fingerprint differs from the stored value or
# fail-safe (no state / unreadable / sha256 unavailable / node unavailable)
# forces full emit.
#
# JSON handling uses Node.js (`node -e`) instead of an external `jq` binary.
# Node is a safe assumption: it is the runtime Claude Code itself depends on.
# This mirrors adapter/codex/hooks/on-session-start.ps1, which solves the same
# problem with PowerShell-native ConvertFrom-Json/ConvertTo-Json.
FAIL_SAFE_FULL_EMIT=0
FAIL_SAFE_REASON=""

# node availability check (used for state read/parse and state write).
NODE_BIN=""
if command -v node >/dev/null 2>&1; then
  NODE_BIN="node"
fi

# sha256 availability check (used for both current fingerprints and state read).
if [ -z "$(sha256_of probe)" ]; then
  FAIL_SAFE_FULL_EMIT=1
  FAIL_SAFE_REASON="sha256 tool unavailable"
fi

# node availability check: state read and write both require it. Without
# node, diff comparison and state rewrite cannot proceed reliably.
if [ "$FAIL_SAFE_FULL_EMIT" -eq 0 ] && [ -z "$NODE_BIN" ]; then
  FAIL_SAFE_FULL_EMIT=1
  FAIL_SAFE_REASON="node unavailable"
fi

# Read prior state, if present and parseable. On success, PRIOR_FP_DUMP holds
# one "key<TAB>fingerprint" line per recorded section (flat text, easy to
# grep from bash without needing associative arrays).
PRIOR_FP_DUMP=""
# The one field the state file has carried with no reader (#1910). Left empty
# when the state holds no well-formed stamp; that only drops the read-back line
# below, and is never a reason to fall through to full emit.
PRIOR_EMIT_AT=""
if [ "$FAIL_SAFE_FULL_EMIT" -eq 0 ]; then
  if [ -f "$STATE_FILE" ]; then
    PRIOR_STATE_DUMP=$("$NODE_BIN" -e '
      const fs = require("fs");
      try {
        const raw = fs.readFileSync(process.argv[1], "utf8");
        const data = JSON.parse(raw);
        const obj = (data && typeof data === "object") ? data : {};
        const stamp = obj.last_emit_at;
        const shaped = typeof stamp === "string" &&
          /^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$/.test(stamp);
        process.stdout.write((shaped ? stamp : "") + "\n");
        const sections = obj.sections || {};
        for (const k of Object.keys(sections)) {
          process.stdout.write(k + "\t" + String(sections[k]) + "\n");
        }
      } catch (e) {
        process.exit(1);
      }
    ' "$STATE_FILE" 2>/dev/null)
    if [ "$?" -ne 0 ]; then
      FAIL_SAFE_FULL_EMIT=1
      FAIL_SAFE_REASON="state file malformed JSON"
    else
      PRIOR_EMIT_AT=$(printf '%s\n' "$PRIOR_STATE_DUMP" | sed -n '1p')
      PRIOR_FP_DUMP=$(printf '%s\n' "$PRIOR_STATE_DUMP" | tail -n +2)
    fi
  else
    FAIL_SAFE_FULL_EMIT=1
    FAIL_SAFE_REASON="state file absent (first run or post-cleanup)"
  fi
fi

# Helper: look up a key's prior fingerprint from the flat PRIOR_FP_DUMP dump.
prior_fp_of() {
  local key="$1"
  [ -n "$PRIOR_FP_DUMP" ] || return 0
  printf '%s\n' "$PRIOR_FP_DUMP" | awk -F'\t' -v k="$key" '$1 == k { print $2; exit }'
}

# Build current fingerprints and emit per section. NEW_FP_KEYS / NEW_FP_VALS
# are parallel arrays accumulating "last gathered" fingerprints, written out
# as a single JSON object at the end (one node invocation, not one per key).
EMITTED_ANY=0
MARKER_EMITTED=0
NEW_FP_KEYS=()
NEW_FP_VALS=()

i=0
while [ "$i" -lt "${#SECTION_KEYS[@]}" ]; do
  key="${SECTION_KEYS[$i]}"
  banner="${SECTION_BANNERS[$i]}"
  body="${SECTION_BODIES[$i]}"
  i=$((i + 1))

  # Empty body → no section to emit and no fingerprint to record.
  if [ -z "$body" ]; then
    continue
  fi

  current_fp=$(sha256_of "$body")

  prior_fp=""
  if [ "$FAIL_SAFE_FULL_EMIT" -eq 0 ]; then
    prior_fp=$(prior_fp_of "$key")
  fi

  # Record current fingerprint (even if not emitted, so the state always
  # reflects "last gathered" not "last emitted"; this prevents an unchanged
  # section from being re-emitted forever after one stale state read).
  if [ -n "$current_fp" ]; then
    NEW_FP_KEYS+=("$key")
    NEW_FP_VALS+=("$current_fp")
  fi

  if [ "$FAIL_SAFE_FULL_EMIT" -eq 1 ] || [ "$current_fp" != "$prior_fp" ] || [ -z "$current_fp" ]; then
    emit_section "$banner" "$body"
    EMITTED_ANY=1
  fi
done

# If no section emitted under diff-only mode, emit the no-new-material marker
# so the human can still observe that a session boundary occurred (silent
# skip is intentionally avoided — it would hide the session transition).
# The two date-driven surfaces count as material: pairing a just-emitted overdue
# entry or an expired tally cluster with "No new orientation material" would be
# self-contradictory output.
if [ "$EMITTED_ANY" -eq 0 ] && [ "$OBSERVATION_EMITTED" -eq 0 ] && [ "$TALLY_EMITTED" -eq 0 ] && [ "$FAIL_SAFE_FULL_EMIT" -eq 0 ]; then
  emit_section "Orientation diff" "No new orientation material since last session. Prior in-context state remains authoritative."
  MARKER_EMITTED=1
fi

# Prior-baseline read-back. Emitted in the diff-only state only: under full emit
# nothing was suppressed, so the prior time is not judgment material, and under
# the no-new-material marker the session boundary is already stated in one line.
#
# Signal, not detector. The state file carries no identifier, so "another session
# in this shared workspace consumed the baseline" and "this session was reopened"
# read identically here.
if [ "$FAIL_SAFE_FULL_EMIT" -eq 0 ] && [ "$MARKER_EMITTED" -eq 0 ] && [ -n "$PRIOR_EMIT_AT" ]; then
  emit_section "Prior baseline" "Diff baseline last consumed at ${PRIOR_EMIT_AT} (UTC).
No identifier is recorded, so this does not say who consumed it."
fi

# Persist new state (best-effort; failure is non-fatal — next session will
# fall through to fail-safe full emit).
if [ -n "$NODE_BIN" ]; then
  mkdir -p "$STATE_DIR" 2>/dev/null || true
  # Add a top-level timestamp for human-readable forensics.
  TS=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "")
  # Pass keys/values/timestamp as argv to node; it assembles and writes the
  # JSON object directly (single invocation, no shell-side JSON string building).
  # Build the interleaved key/value argv list as a real array (avoids fragile
  # word-splitting via command substitution).
  NEW_FP_ARGV=()
  j=0
  while [ "$j" -lt "${#NEW_FP_KEYS[@]}" ]; do
    NEW_FP_ARGV+=("${NEW_FP_KEYS[$j]}" "${NEW_FP_VALS[$j]}")
    j=$((j + 1))
  done
  "$NODE_BIN" -e '
    const fs = require("fs");
    const outPath = process.argv[1];
    const ts = process.argv[2];
    const rest = process.argv.slice(3);
    const sections = {};
    for (let i = 0; i < rest.length; i += 2) {
      sections[rest[i]] = rest[i + 1];
    }
    const state = { sections: sections };
    if (ts) { state.last_emit_at = ts; }
    try {
      fs.writeFileSync(outPath, JSON.stringify(state) + "\n");
    } catch (e) {
      process.exit(1);
    }
  ' "$STATE_FILE" "$TS" "${NEW_FP_ARGV[@]}" 2>/dev/null || true
fi

# --- instruction to the AI: synthesize through Character_Instance ---
if [ "$FAIL_SAFE_FULL_EMIT" -eq 1 ]; then
  cat <<EOF
━━━ Cold-start Synthesis: instruction ━━━
Fail-safe full emit (reason: ${FAIL_SAFE_REASON:-unknown}). All available
material is shown above. Using it, perform Cold-start Synthesis through
Character_Instance:
1. Summarize the current Li+ state (active tag, recent structural shifts, unresolved threads).
2. Report synthesis to the human as the opening orientation.
The hook only gathers material. Judgment and expression belong to the AI.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EOF
else
  cat <<'EOF'
━━━ Cold-start Synthesis: instruction ━━━
Diff-only emission: only sections changed since the prior session are shown
above (cold-start rule anchor is always re-anchored). Using the diff plus
your loaded layers, perform Cold-start Synthesis through Character_Instance:
1. Summarize the current Li+ state delta (what changed; unresolved threads).
2. Report synthesis to the human as the opening orientation — apply the
   non-redundancy gate in rules/evolution/cold-start-synthesis.md (silent
   skip when no unique insight remains after synthesis).
The hook only gathers material. Judgment and expression belong to the AI.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EOF
fi

exit 0
