#!/bin/bash
# Source: adapter/codex/hooks/on-session-start.sh ({LI_PLUS_TAG})
# Codex SessionStart hook (portable POSIX fallback). The Windows-native PRIMARY
# path is the sibling on-session-start.ps1 (wired via hooks.json commandWindows).
# Port of adapter/claude/hooks/on-session-start.sh.
#
# Three responsibilities (the first is Codex-specific):
#   1. RULES INJECTION (Codex-only): read rules/*.md from the LI_PLUS_REPO clone
#      and emit them as additionalContext (Codex has no .claude/rules/ always-on
#      folder). #1502 verified design.
#   2. Update-status verification (sentinel tag / config schema / language
#      contract) -> LI_PLUS_UPDATE_STATUS marker.
#   3. Cold-start material gathering with diff-only emission.
#
# Codex contract difference vs Claude: SessionStart context injection requires
# JSON on stdout (hookSpecificOutput.additionalContext). So this port accumulates
# the WHOLE emission into $BUFFER and wraps it once at the end.
#
# Matchers: startup / resume / clear / compact. resume/clear/compact = rules
# re-injection + cold-start anchor only (no diff eval, no update-status re-check).
#
# JSON handling (output wrapping, HOOK_INPUT field extraction, cold-start
# diff-only state read/write) uses Node.js (`node -e`), not an external `jq`
# binary — node is a runtime dependency Codex CLI (like Claude Code) already
# has, so it is a safe assumption. Ported from adapter/claude/hooks/on-session-start.sh
# (#1519); on-session-start.ps1 (Windows-native primary) never depended on jq
# in the first place (PowerShell-native ConvertFrom-Json/ConvertTo-Json). #1526.
export PATH="$HOME/.local/bin:$PATH"

BUFFER=""
emit() { BUFFER="${BUFFER}$1
"; }
emit_section() {
  local banner="$1" body="$2"
  [ -n "$body" ] || return 0
  emit "━━━ $banner ━━━"
  emit "$body"
  emit "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  emit ""
}
flush_json() {
  if command -v node >/dev/null 2>&1; then
    BUFFER="$BUFFER" node -e '
      process.stdout.write(JSON.stringify({
        hookSpecificOutput: { hookEventName: "SessionStart", additionalContext: process.env.BUFFER || "" }
      }) + "\n");
    ' 2>/dev/null && return
  fi
  local esc
  esc=$(printf '%s' "$BUFFER" | sed 's/\\/\\\\/g; s/"/\\"/g' | awk 'BEGIN{ORS=""} {printf "%s\\n", $0}')
  printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' "$esc"
}
sha256_of() {
  local input="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    printf '%s' "$input" | sha256sum | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    printf '%s' "$input" | shasum -a 256 | awk '{print $1}'
  else
    printf ''
  fi
}

# --- stdin / paths ---
HOOK_INPUT=""
if [ ! -t 0 ]; then HOOK_INPUT=$(cat 2>/dev/null || true); fi
PROJECT_ROOT=""
if [ -n "$HOOK_INPUT" ] && command -v node >/dev/null 2>&1; then
  PROJECT_ROOT=$(printf '%s' "$HOOK_INPUT" | node -e '
    let raw = "";
    // Without setEncoding each Buffer chunk is decoded on its own, so a
    // multi-byte character straddling a chunk boundary becomes U+FFFD (#1544).
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (d) => { raw += d; });
    process.stdin.on("end", () => {
      try {
        const payload = JSON.parse(raw);
        process.stdout.write(String(payload.cwd || ""));
      } catch (e) {
        // leave stdout empty; caller falls back to CODEX_PROJECT_DIR/PWD
      }
    });
  ' 2>/dev/null)
fi
[ -n "$PROJECT_ROOT" ] || PROJECT_ROOT="${CODEX_PROJECT_DIR:-$PWD}"

LIPLUS_DIR="$PROJECT_ROOT/liplus-language"
COLDSTART_MD="$LIPLUS_DIR/rules/evolution/cold-start-synthesis.md"
DECISION_STRUCTURE="$LIPLUS_DIR/docs/Decision-Structure.md"
STATE_DIR="$PROJECT_ROOT/.codex/state"
STATE_FILE="$STATE_DIR/last-cold-start-emit.json"
ADAPTER_FILE="$PROJECT_ROOT/AGENTS.md"
CONFIG_FILE="$PROJECT_ROOT/Li+config.md"
RULES_ROOT="$LIPLUS_DIR/rules"

# --- matcher resolution ---
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
  if [ -z "$EXTRACTED" ]; then
    EXTRACTED=$(printf '%s' "$HOOK_INPUT" | sed -n 's/.*"\(matcher\|source\)"[[:space:]]*:[[:space:]]*"\([a-z]*\)".*/\2/p' | head -n 1)
  fi
  case "$EXTRACTED" in
    startup|resume|clear|compact) MATCHER="$EXTRACTED" ;;
  esac
fi

# --- guard: liplus source not resolved yet ---
if [ ! -d "$LIPLUS_DIR" ]; then
  emit "━━━ Li+ update status ━━━"
  emit "LI_PLUS_UPDATE_STATUS=needed reason=liplus-source-unresolved"
  emit "liplus-language clone not found under workspace root. Run the Li+config / Li+update walkthrough."
  emit "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  flush_json
  exit 0
fi

# ===================================================================
# RULES INJECTION (Codex-only; substitute for Claude .claude/rules/)
# Runs on EVERY matcher (Codex has no folder-level persistence).
# ===================================================================
if [ -d "$RULES_ROOT" ]; then
  RULE_FILES=$(cd "$LIPLUS_DIR" && find rules -type f -name '*.md' 2>/dev/null | LC_ALL=C sort)
  if [ -n "$RULE_FILES" ]; then
    emit "━━━ Li+ rules (always-on; injected because Codex has no .claude/rules equivalent) ━━━"
    while IFS= read -r rel; do
      [ -n "$rel" ] || continue
      emit "----- $rel -----"
      emit "$(cat "$LIPLUS_DIR/$rel" 2>/dev/null)"
      emit ""
    done <<< "$RULE_FILES"
    emit "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    emit ""
  fi
fi

# ===================================================================
# Language contract values (every matcher)
# ===================================================================
# Issue #1575. Extracted here rather than inside the startup-only block below
# because the values must be in context on every session entry point, the same
# way the always-on rules above are re-injected on every matcher. The
# startup-only axis 3 check reuses what this block resolved.
BASE_LANG=""; PROJ_LANG=""
if [ -f "$CONFIG_FILE" ]; then
  BASE_LANG=$(sed -n 's/^[[:space:]]*LI_PLUS_BASE_LANGUAGE[[:space:]]*=[[:space:]]*\(.*\)$/\1/p' "$CONFIG_FILE" | head -n 1 | tr -d '\r' | sed 's/[[:space:]]*$//')
  PROJ_LANG=$(sed -n 's/^[[:space:]]*LI_PLUS_PROJECT_LANGUAGE[[:space:]]*=[[:space:]]*\(.*\)$/\1/p' "$CONFIG_FILE" | head -n 1 | tr -d '\r' | sed 's/[[:space:]]*$//')
fi

# ===================================================================
# Update sentinel-skip verification (startup only)
# ===================================================================
if [ "$MATCHER" = "startup" ]; then
  UPDATE_REASONS=()

  # axis 1: adapter sentinel tag vs target tag
  ADAPTER_TAG=""
  if [ -f "$ADAPTER_FILE" ]; then
    ADAPTER_TAG=$(sed -n 's/^# --- Li+ BEGIN (\([^)]*\)) ---.*/\1/p' "$ADAPTER_FILE" | head -n 1)
  fi
  LI_PLUS_CHANNEL_VAL=""
  if [ -f "$CONFIG_FILE" ]; then
    LI_PLUS_CHANNEL_VAL=$(sed -n 's/^[[:space:]]*LI_PLUS_CHANNEL[[:space:]]*=[[:space:]]*\(.*\)$/\1/p' "$CONFIG_FILE" | head -n 1 | tr -d '\r')
  fi
  [ -n "$LI_PLUS_CHANNEL_VAL" ] || LI_PLUS_CHANNEL_VAL="release"
  TARGET_TAG=""
  case "$LI_PLUS_CHANNEL_VAL" in
    latest)  TARGET_TAG=$(gh release view --repo Liplus-Project/liplus-language --json tagName --jq '.tagName' 2>/dev/null) ;;
    release) TARGET_TAG=$(gh release list --repo Liplus-Project/liplus-language --limit 1 --json tagName --jq '.[0].tagName' 2>/dev/null) ;;
    tag)
      TARGET_TAG=$(git -C "$LIPLUS_DIR" ls-remote --tags --sort=-creatordate origin 2>/dev/null \
        | awk -F'refs/tags/' 'NF==2 {print $2}' | sed 's/\^{}$//' | head -n 1) ;;
  esac
  if [ -z "$ADAPTER_TAG" ] || [ -z "$TARGET_TAG" ] || [ "$ADAPTER_TAG" != "$TARGET_TAG" ]; then
    UPDATE_REASONS+=("sentinel-tag(adapter=${ADAPTER_TAG:-unknown},target=${TARGET_TAG:-unknown})")
  fi

  # axis 2: config schema canonical
  LEGACY_HIT=""
  if [ -f "$CONFIG_FILE" ]; then
    LEGACY_HIT=$(grep -E '^[[:space:]]*(LI_PLUS_REPOSITORY|USER_REPOSITORY|USER_REPOSITORY_EXECUTION_MODE)[[:space:]]*=|^[[:space:]]*[^#[:space:]][^=]*_EXECUTION_MODE[[:space:]]*=' "$CONFIG_FILE" 2>/dev/null | head -n 3)
  fi
  [ -n "$LEGACY_HIT" ] && UPDATE_REASONS+=("legacy-schema-keys-present")

  # axis 3: language contract resolved (values extracted above, every matcher)
  if [ -z "$BASE_LANG" ] || [ -z "$PROJ_LANG" ]; then
    UPDATE_REASONS+=("language-contract-unresolved(base=${BASE_LANG:-unset},project=${PROJ_LANG:-unset})")
  fi

  if [ "${#UPDATE_REASONS[@]}" -eq 0 ]; then
    emit "━━━ Li+ update status ━━━"
    emit "LI_PLUS_UPDATE_STATUS=unnecessary tag=$TARGET_TAG channel=$LI_PLUS_CHANNEL_VAL"
    emit "Sentinel-skip applies: AI skips Li+update.md re-execution this session. Li+config.md spot read (Read for value lookup, do not execute contents) is permitted."
    emit "Override: Master input containing \"Li+configを実行\" / \"Li+config を実行\" forces the full walkthrough."
    emit "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    emit ""
  else
    REASON_STR=$(printf '%s,' "${UPDATE_REASONS[@]}"); REASON_STR="${REASON_STR%,}"
    emit "━━━ Li+ update status ━━━"
    emit "LI_PLUS_UPDATE_STATUS=needed reason=$REASON_STR"
    emit "AI must read Li+config.md and execute Li+update.md walkthrough this session."
    emit "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    emit ""
  fi

  # --- unrecognized config value surfacing (#1804) ---
  # Rationale is in the claude port this one mirrors.
  case "$LI_PLUS_CHANNEL_VAL" in
    latest|release|tag) ;;
    *)
      emit "━━━ Li+config: unrecognized value ━━━"
      emit "LI_PLUS_CHANNEL=$LI_PLUS_CHANNEL_VAL is not one of: latest / release / tag. Values are case-sensitive. No target tag resolved, so the update status above is \"needed\"."
      emit "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
      emit ""
      ;;
  esac
fi

# --- emit language contract values (every matcher) ---
# Issue #1575: the contract text is always in context (adapter AGENTS.md) but
# its values were not, because resolving them was written as "read
# Li+config.md" and that file is not auto-loaded. Emitting the values the hook
# already holds removes the read step without baking anything into a generated
# file. Emitted on every path that reaches here, with an unresolved value
# rendered as "unset", so inside a bootstrapped session the block's absence
# never has to be distinguished from an unresolved value. The unresolved-source
# guard exits well before this point and emits no language marker at all; the
# adapter Workspace_Language_Contract routes that state to the same ask-human
# branch as "unset".
emit "━━━ Li+ language contract ━━━"
emit "LI_PLUS_BASE_LANGUAGE=${BASE_LANG:-unset}"
emit "LI_PLUS_PROJECT_LANGUAGE=${PROJ_LANG:-unset}"
emit "Resolved from Li+config.md at session start. Definitions, scope and precedence: Workspace_Language_Contract (adapter AGENTS.md)."
emit "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
emit ""

# ===================================================================
# Cold-start material gathering
# ===================================================================
# Anchor = the H1 preamble only, cut at the first H2 semantic tag. The rule file
# is always-on loaded, so emitting it whole put the same text in one session's
# context twice. A file with no H2 section emits whole. Contract source =
# rules/evolution/cold-start-synthesis.md Hook Emission Contract (Anchor cut).
COLDSTART_LITERAL=""
if [ -f "$COLDSTART_MD" ]; then
  COLDSTART_LITERAL=$(awk '
    /^---$/ { n++; next }
    n < 2   { next }
    seen_h1 && /^<[a-z0-9-]+>$/ { exit }
    /^# /   { seen_h1 = 1 }
            { print }
  ' "$COLDSTART_MD" | sed '1{/^# /d;}' | sed '/./,$!d')
fi
emit_section "Cold-start Synthesis (rules/evolution/cold-start-synthesis.md anchor)" "$COLDSTART_LITERAL"

if [ "$MATCHER" != "startup" ]; then
  emit "━━━ Cold-start Synthesis: instruction ━━━"
  emit "Matcher = ${MATCHER}. Session is continuous (resume/clear/compact). Rules were"
  emit "reinjected and the cold-start rule anchor re-anchored above. Treat the prior"
  emit "session's in-context state as authoritative; do not re-orient from scratch."
  emit "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  flush_json
  exit 0
fi

# --- register diff-only sections ---
SECTION_KEYS=(); SECTION_BANNERS=(); SECTION_BODIES=()
register_section() { SECTION_KEYS+=("$1"); SECTION_BANNERS+=("$2"); SECTION_BODIES+=("$3"); }

DECISION_HEAD=""
[ -f "$DECISION_STRUCTURE" ] && DECISION_HEAD=$(head -n 20 "$DECISION_STRUCTURE")
register_section "decision_structure_head" "Decision structure index (docs/Decision-Structure.md head)" "$DECISION_HEAD"

RULES_TREE=""
[ -d "$RULES_ROOT" ] && RULES_TREE=$(cd "$LIPLUS_DIR" && find rules -type f -name '*.md' 2>/dev/null | LC_ALL=C sort)
register_section "rules_tree" "Rules tree (fetch address table for rules/ cache)" "$RULES_TREE"

LATEST_RELEASE=$(gh release list -R Liplus-Project/liplus-language --limit 3 2>/dev/null | head -n 3)
register_section "recent_releases" "Recent releases (includes prereleases)" "$LATEST_RELEASE"

OPEN_ISSUES=$(gh issue list -R Liplus-Project/liplus-language --state open --label in-progress --limit 5 \
  --json number,title,labels \
  --jq '.[] | "#\(.number) \(.title) [\(.labels | map(.name) | join(","))]"' 2>/dev/null)
register_section "open_in_progress_issues" "Open in-progress issues (max 5)" "$OPEN_ISSUES"

# Self-eval head: Codex has no ~/.claude/projects memory; use workspace-local memory/.
SELFEVAL_FOUND=""
for candidate in "$PROJECT_ROOT/memory/self-evaluation_log.md" "$LIPLUS_DIR/memory/self-evaluation_log.md"; do
  [ -f "$candidate" ] && { SELFEVAL_FOUND="$candidate"; break; }
done
SELFEVAL_HEAD=""
[ -n "$SELFEVAL_FOUND" ] && [ -f "$SELFEVAL_FOUND" ] && SELFEVAL_HEAD=$(head -n 15 "$SELFEVAL_FOUND")
register_section "self_eval_head" "Self-evaluation log head (most recent)" "$SELFEVAL_HEAD"

# promotion candidates
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
# #1632 F3 / #1636: every detector below used to read a format nothing writes, so
# the section was empty on every session and an empty surface could not be told
# apart from "nothing crossed the noise floor". Detector 1 matched a
# `root_cause:` / `tags:` line syntax that no spec defines and the log has never
# used; detectors 2 and 3 scanned the flat feedback.md / project.md pair that the
# one-memory-per-file host layout replaced. The formats read below are the ones
# the live artifacts actually carry, and they are the same formats the sibling
# ports read — the detection behavior is deliberately identical across
# adapter/claude/hooks/on-session-start.sh, this file and on-session-start.ps1.
THRESHOLD_N=2
SURFACE_CAP=10

# A candidate qualifies as MEMORY_DIR only when it holds at least one file that
# some MEMORY_DIR consumer reads. Directory existence alone is not the criterion:
# an empty higher-precedence directory would otherwise shadow a populated
# lower-precedence one and silence every consumer at once.
# The marker set is the files MEMORY_DIR consumers read: the observation surface,
# the promotion tally expiry surface (#1894 — it became a consumer when it got
# its reader, and the criterion is consumer-read, not file identity),
# the per-topic entry-file prefixes the promotion detectors scan, plus
# self-evaluation_log.md so that both resolution paths agree on what counts as a
# memory directory. That last member never decides a case in practice: the
# self-eval lookup above scans the same candidate directories, so whenever that
# file exists the primary path has already claimed the directory before this
# check runs.
# The prefixes replace the former flat feedback.md / project.md pair: the host
# auto-memory layout is one memory per file, so a live memory directory holds
# feedback_<topic>.md / project_<topic>.md / reference_<topic>.md /
# user_<topic>.md and neither flat name exists. Matching prefixes rather than any
# *.md is deliberate — an unrelated file must not let a directory claim the slot.
memory_dir_populated() {
  for markerfile in \
    self-evaluation_log.md \
    self-evolution-observation.md \
    promotion_tally.md; do
    [ -f "$1/$markerfile" ] && return 0
  done
  for markerglob in "$1"/feedback*.md "$1"/project*.md "$1"/reference*.md "$1"/user*.md; do
    [ -f "$markerglob" ] && return 0
  done
  return 1
}

# Memory entry files inside a resolved MEMORY_DIR, under the same one-memory-
# per-file layout. Excluded are the index and the three transient operational
# files, each of which has its own dedicated reader: MEMORY.md is read by the
# index emit, self-evaluation_log.md by the self-eval head, and the two
# date-driven surfaces below read self-evolution-observation.md and
# promotion_tally.md. The last of those four carried no reader until #1894, so
# the stated reason held for three members and not for the fourth; the exclusion
# was right either way (a tally cluster is not a memory entry), but what the
# exclusion stands in for is the dedicated reader. Flat feedback.md /
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

# Probe the directory directly when self-evaluation_log.md is absent: the other
# MEMORY_DIR readers (promotion detectors, self-evolution observation surface)
# must not be silenced by the absence of an unrelated file.
MEMORY_DIR=""
if [ -n "$SELFEVAL_FOUND" ]; then
  MEMORY_DIR=$(dirname "$SELFEVAL_FOUND")
else
  for memcandidate in "$PROJECT_ROOT/memory" "$LIPLUS_DIR/memory"; do
    memory_dir_populated "$memcandidate" && { MEMORY_DIR="$memcandidate"; break; }
  done
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
  [ -n "$AXIS_MISSES" ] && PROMOTION_BODY="${PROMOTION_BODY}repeated self-evaluation axis misses:
${AXIS_MISSES}
"
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
# which re-read every source file once per title. Source paths are handed over
# as a list file and read with getline, so a workspace path containing spaces
# stays intact. awk emits every qualifying pair; the sort and the cap are
# applied after it, in that order. Sorting first is what makes the truncation
# stable — awk's `for (k in array)` order is unspecified, so capping inside awk
# would pick a different subset per run and churn the sha256 the diff-only
# emission compares against.
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
# Surface" (#1537). Port of the same block in adapter/claude/hooks/on-session-start.sh:
#   next_check <= today AND verdict_state == pending -> "observation due"
#   expires    <  today AND verdict_state == pending -> "observation overdue,
#                                                       human judgment needed"
#
# Deliberately NOT registered via register_section: the trigger is date-driven
# while the body is content-driven, so an unresolved entry keeps a byte-identical
# body and a fingerprint comparison would surface it once and then suppress it
# for the whole period it still needs attention. Empty body = silent skip.
# An entry past expires is reported as OVERDUE only (overdue carries the
# escalation; reporting it on both axes is noise). Date comparison is
# lexicographic on ISO YYYY-MM-DD, which is order-preserving.
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
# Surface" (#1894). Port of the same block in adapter/claude/hooks/on-session-start.sh:
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

# Emitted before the diff sections so a due/overdue entry is not buried under
# whatever else changed.
OBSERVATION_EMITTED=0
if [ -n "$OBSERVATION_BODY" ]; then
  emit_section "Self-evolution observation (due / overdue)" "$OBSERVATION_BODY"
  OBSERVATION_EMITTED=1
fi

# Emitted next to the observation surface, before the diff sections, for the
# same reason: a closed window must not be buried under whatever else changed.
TALLY_EMITTED=0
if [ -n "$TALLY_BODY" ]; then
  emit_section "Tally expiry (due / overdue)" "$TALLY_BODY"
  TALLY_EMITTED=1
fi

# ===================================================================
# Diff-only emission (startup)
# ===================================================================
# JSON handling uses Node.js (`node -e`) instead of an external `jq` binary.
# Node is a safe assumption: it is the runtime Codex CLI itself depends on
# (mirrors the fix applied to adapter/claude/hooks/on-session-start.sh in #1519;
# on-session-start.ps1, the Windows-native primary, already avoided jq via
# PowerShell-native ConvertFrom-Json/ConvertTo-Json).
FAIL_SAFE_FULL_EMIT=0
FAIL_SAFE_REASON=""

NODE_BIN=""
if command -v node >/dev/null 2>&1; then
  NODE_BIN="node"
fi

if [ -z "$(sha256_of probe)" ]; then FAIL_SAFE_FULL_EMIT=1; FAIL_SAFE_REASON="sha256 tool unavailable"; fi
if [ "$FAIL_SAFE_FULL_EMIT" -eq 0 ] && [ -z "$NODE_BIN" ]; then FAIL_SAFE_FULL_EMIT=1; FAIL_SAFE_REASON="node unavailable"; fi

# Read prior state, if present and parseable. On success, PRIOR_FP_DUMP holds
# one "key<TAB>fingerprint" line per recorded section (flat text, easy to
# grep from bash without needing associative arrays).
PRIOR_FP_DUMP=""
if [ "$FAIL_SAFE_FULL_EMIT" -eq 0 ]; then
  if [ -f "$STATE_FILE" ]; then
    PRIOR_FP_DUMP=$("$NODE_BIN" -e '
      const fs = require("fs");
      try {
        const raw = fs.readFileSync(process.argv[1], "utf8");
        const data = JSON.parse(raw);
        const sections = (data && typeof data === "object" && data.sections) || {};
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

EMITTED_ANY=0
NEW_FP_KEYS=(); NEW_FP_VALS=()
i=0
while [ "$i" -lt "${#SECTION_KEYS[@]}" ]; do
  key="${SECTION_KEYS[$i]}"; banner="${SECTION_BANNERS[$i]}"; body="${SECTION_BODIES[$i]}"
  i=$((i + 1))
  [ -z "$body" ] && continue
  current_fp=$(sha256_of "$body")
  prior_fp=""
  if [ "$FAIL_SAFE_FULL_EMIT" -eq 0 ]; then
    prior_fp=$(prior_fp_of "$key")
  fi
  if [ -n "$current_fp" ]; then
    NEW_FP_KEYS+=("$key")
    NEW_FP_VALS+=("$current_fp")
  fi
  if [ "$FAIL_SAFE_FULL_EMIT" -eq 1 ] || [ "$current_fp" != "$prior_fp" ] || [ -z "$current_fp" ]; then
    emit_section "$banner" "$body"; EMITTED_ANY=1
  fi
done

# The two date-driven surfaces count as material: pairing a just-emitted overdue
# entry or an expired tally cluster with "No new orientation material" would be
# self-contradictory output.
if [ "$EMITTED_ANY" -eq 0 ] && [ "$OBSERVATION_EMITTED" -eq 0 ] && [ "$TALLY_EMITTED" -eq 0 ] && [ "$FAIL_SAFE_FULL_EMIT" -eq 0 ]; then
  emit_section "Orientation diff" "No new orientation material since last session. Prior in-context state remains authoritative."
fi

# Persist new state (best-effort; failure is non-fatal — next session will
# fall through to fail-safe full emit). Keys/values/timestamp are passed as
# argv to a single node invocation (no shell-side JSON string building).
if [ -n "$NODE_BIN" ]; then
  mkdir -p "$STATE_DIR" 2>/dev/null || true
  TS=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "")
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

if [ "$FAIL_SAFE_FULL_EMIT" -eq 1 ]; then
  emit "━━━ Cold-start Synthesis: instruction ━━━"
  emit "Fail-safe full emit (reason: ${FAIL_SAFE_REASON:-unknown}). All available"
  emit "material is shown above. Using it, perform Cold-start Synthesis through"
  emit "Character_Instance:"
  emit "1. Summarize the current Li+ state (active tag, recent structural shifts, unresolved threads)."
  emit "2. Report synthesis to the human as the opening orientation."
  emit "The hook only gathers material. Judgment and expression belong to the AI."
  emit "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
else
  emit "━━━ Cold-start Synthesis: instruction ━━━"
  emit "Diff-only emission: only sections changed since the prior session are shown"
  emit "above (rules + cold-start rule anchor are always re-anchored). Using the diff"
  emit "plus your loaded layers, perform Cold-start Synthesis through Character_Instance:"
  emit "1. Summarize the current Li+ state delta (what changed; unresolved threads)."
  emit "2. Report synthesis to the human as the opening orientation — apply the"
  emit "   non-redundancy gate in rules/evolution/cold-start-synthesis.md (silent"
  emit "   skip when no unique insight remains after synthesis)."
  emit "The hook only gathers material. Judgment and expression belong to the AI."
  emit "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
fi

flush_json
exit 0
