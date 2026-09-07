# Source: adapter/codex/hooks/on-session-start.ps1 ({LI_PLUS_TAG})
# Codex SessionStart hook (Windows native / PowerShell). PRIMARY Windows path.
# Port of adapter/claude/hooks/on-session-start.sh.
#
# Three responsibilities (the first is Codex-specific; Claude gets it from the
# always-loaded .claude/rules/ folder which Codex has no equivalent of):
#   1. RULES INJECTION (Codex-only): read rules/*.md from the LI_PLUS_REPO clone
#      and emit them as additionalContext. This is the Codex substitute for
#      Claude's .claude/rules/ always-on folder (#1502 verified design).
#   2. Update-status verification: sentinel tag / config schema / language
#      contract -> emit LI_PLUS_UPDATE_STATUS marker (parsed by AGENTS.md startup
#      block to decide whether to run the Li+config + Li+update walkthrough).
#   3. Cold-start material gathering (decision structure head, releases, open
#      issues, self-eval head, promotion candidates) with diff-only emission.
#
# Codex contract difference vs Claude: SessionStart context injection on Codex
# requires JSON on stdout (hookSpecificOutput.additionalContext). Claude injects
# raw stdout directly. So the WHOLE emission is accumulated into one buffer and
# wrapped into the JSON envelope at the end.
#
# Matchers: startup / resume / clear / compact (see hooks.json / config.toml).
#   startup            -> full pipeline: rules injection + update status +
#                         diff-only cold-start material.
#   resume/clear/compact -> rules re-injection + cold-start rule anchor
#                         re-anchor only (work context continuous; no diff eval).
#
# NOTE on rules injection + compact: #1502 leaves "does additionalContext survive
# auto-compaction on Codex" UNVERIFIED (Codex App has no manual /compact). We
# re-inject rules on the compact matcher as the safer-side design; if a future
# real-device test shows additionalContext survives compaction, the compact
# re-injection can be trimmed.
$ErrorActionPreference = 'SilentlyContinue'

# ---------- helpers ----------
$script:BUFFER = [System.Text.StringBuilder]::new()
function Emit([string]$text) { [void]$script:BUFFER.AppendLine($text) }
function Emit-Section([string]$banner, [string]$body) {
  if (-not $body) { return }
  Emit "━━━ $banner ━━━"
  Emit $body
  Emit "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  Emit ''
}
function Sha256Of([string]$s) {
  if ($null -eq $s) { $s = '' }
  $sha = [System.Security.Cryptography.SHA256]::Create()
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($s)
  ($sha.ComputeHash($bytes) | ForEach-Object { $_.ToString('x2') }) -join ''
}
function Flush-Json {
  # Wrap the accumulated buffer into the Codex SessionStart JSON envelope.
  $ctx = $script:BUFFER.ToString()
  $out = @{
    hookSpecificOutput = @{
      hookEventName     = 'SessionStart'
      additionalContext = $ctx
    }
  }
  # Write raw UTF-8 bytes so non-ASCII survives Windows PowerShell 5.1
  # (default redirected-output encoding is ANSI).
  $json = $out | ConvertTo-Json -Depth 5 -Compress
  $stdout = [System.Console]::OpenStandardOutput()
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
  $stdout.Write($bytes, 0, $bytes.Length); $stdout.Flush()
}

# ---------- stdin / paths ----------
$raw = [Console]::In.ReadToEnd()
$payload = $null
if ($raw) { try { $payload = $raw | ConvertFrom-Json } catch { $payload = $null } }

$projectRoot = $null
if ($payload -and $payload.cwd) { $projectRoot = $payload.cwd }
if (-not $projectRoot -and $env:CODEX_PROJECT_DIR) { $projectRoot = $env:CODEX_PROJECT_DIR }
if (-not $projectRoot) { $projectRoot = (Get-Location).Path }

$liplusDir       = Join-Path $projectRoot 'liplus-language'
$coldstartMd     = Join-Path $liplusDir 'rules/evolution/cold-start-synthesis.md'
$decisionStruct  = Join-Path $liplusDir 'docs/Decision-Structure.md'
$stateDir        = Join-Path $projectRoot '.codex/state'
$stateFile       = Join-Path $stateDir 'last-cold-start-emit.json'
$adapterFile     = Join-Path $projectRoot 'AGENTS.md'
$configFile      = Join-Path $projectRoot 'Li+config.md'

# ---------- matcher resolution ----------
# Codex stdin uses hook_event_name + an optional source/matcher field. We treat
# the SessionStart "source" (startup|resume|clear|compact) the same as Claude's
# matcher. Default = startup.
$matcher = 'startup'
if ($payload) {
  $m = $null
  foreach ($k in @('matcher','source','session_source')) {
    if ($payload.PSObject.Properties[$k] -and $payload.$k) { $m = $payload.$k; break }
  }
  if ($m -cin @('startup','resume','clear','compact')) { $matcher = $m }
}

# ---------- guard: liplus source not resolved yet (pre-bootstrap) ----------
if (-not (Test-Path -LiteralPath $liplusDir)) {
  Emit '━━━ Li+ update status ━━━'
  Emit 'LI_PLUS_UPDATE_STATUS=needed reason=liplus-source-unresolved'
  Emit 'liplus-language clone not found under workspace root. Run the Li+config / Li+update walkthrough.'
  Emit '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
  Flush-Json
  exit 0
}

# ===================================================================
# RULES INJECTION (Codex-only; substitute for Claude .claude/rules/)
# ===================================================================
# Read every rules/**/*.md from the clone and emit the literal bodies. This is
# the always-on rules surface for Codex. Runs on EVERY matcher (startup and
# resume/clear/compact) because Codex has no folder-level persistence — the
# only always-on substrate is re-injection per session boundary.
# Ordered on the forward-slashed relative path with an ordinal comparer, so the
# emission order matches the bash ports' `find rules ... | LC_ALL=C sort` on both
# axes at once: `Sort-Object` is culture-aware, and `FullName` would order on the
# native separator instead of the `/` the bash ports compare.
$rulesRoot = Join-Path $liplusDir 'rules'
if (Test-Path -LiteralPath $rulesRoot) {
  $ruleFiles = [string[]]@(
    Get-ChildItem -LiteralPath $rulesRoot -Recurse -Filter '*.md' -File -ErrorAction SilentlyContinue |
      ForEach-Object { $_.FullName.Substring($liplusDir.Length).TrimStart('\', '/') -replace '\\', '/' })
  if ($ruleFiles.Count -gt 0) {
    [Array]::Sort($ruleFiles, [System.StringComparer]::Ordinal)
    Emit '━━━ Li+ rules (always-on; injected because Codex has no .claude/rules equivalent) ━━━'
    foreach ($rel in $ruleFiles) {
      $content = Get-Content -LiteralPath (Join-Path $liplusDir $rel) -Raw -ErrorAction SilentlyContinue
      Emit "----- $rel -----"
      Emit $content
      Emit ''
    }
    Emit '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
    Emit ''
  }
}

# ===================================================================
# Language contract values (every matcher)
# ===================================================================
# Issue #1575. Resolved outside the startup-only block below because the values
# must be in context on every session entry point, the same way the always-on
# rules above are re-injected on every matcher. The startup-only axis 3 check
# reuses what this block resolved.
# -CaseSensitive is required for parity with the two bash ports, whose `sed`
# extraction is case-sensitive; without it PowerShell resolves a lowercase key
# spelling that the bash ports leave unset, and one Li+config.md would yield
# two different language contracts depending on the host adapter.
#
# This applies to EVERY Li+config.md / sentinel-tag extraction in this file, not
# only to the language pair below. It was stated here when the language keys were
# pinned (#1581) but left unapplied to the other three (#1632 F5): with
# `li_plus_channel=tag` spelled lowercase, `.ps1` resolved `tag` and queried
# `git ls-remote` while `.sh` left it unset and fell back to the `release`
# default and `gh release list` — so LI_PLUS_UPDATE_STATUS differed by host for
# one and the same workspace. The four sites are: the language pair below, the
# adapter sentinel tag, LI_PLUS_CHANNEL, and the legacy-schema probe.
# Memory-file scans elsewhere in this file match `^## ` and carry no letters, so
# the flag would be inert there.
$baseLang = ''
$projLang = ''
if (Test-Path -LiteralPath $configFile) {
  $bl = Select-String -LiteralPath $configFile -CaseSensitive -Pattern '^\s*LI_PLUS_BASE_LANGUAGE\s*=\s*(.*)$' -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($bl) { $baseLang = $bl.Matches[0].Groups[1].Value.Trim() }
  $pl = Select-String -LiteralPath $configFile -CaseSensitive -Pattern '^\s*LI_PLUS_PROJECT_LANGUAGE\s*=\s*(.*)$' -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($pl) { $projLang = $pl.Matches[0].Groups[1].Value.Trim() }
}

# ===================================================================
# Update sentinel-skip verification (axes 1-3) — startup matcher only.
# On resume/clear/compact the work context is continuous, so we do not re-run
# the update-status verification. Rules were already re-injected above, and the
# language contract block above is emitted on every matcher; the Claude port
# re-emits its update status on every matcher too, so this startup gate is a
# Codex-side choice, not a shared design.
# ===================================================================
if ($matcher -ceq 'startup') {
  $updateReasons = @()

  # --- axis 1: adapter sentinel tag vs current target tag ---
  $adapterTag = ''
  if (Test-Path -LiteralPath $adapterFile) {
    $line = Select-String -LiteralPath $adapterFile -CaseSensitive -Pattern '^# --- Li\+ BEGIN \(([^)]*)\) ---' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($line) { $adapterTag = $line.Matches[0].Groups[1].Value }
  }

  $channel = ''
  if (Test-Path -LiteralPath $configFile) {
    $cl = Select-String -LiteralPath $configFile -CaseSensitive -Pattern '^\s*LI_PLUS_CHANNEL\s*=\s*(.*)$' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cl) { $channel = $cl.Matches[0].Groups[1].Value.Trim() }
  }
  if (-not $channel) { $channel = 'release' }

  # -CaseSensitive: PowerShell `switch` matches case-insensitively by default,
  # while the `case` statements in the two on-session-start.sh ports are
  # case-sensitive. Without the flag, `LI_PLUS_CHANNEL=Latest` resolved a tag
  # here and resolved nothing there, so one workspace produced two different
  # LI_PLUS_UPDATE_STATUS values depending on which host adapter ran (#1804).
  $targetTag = ''
  switch -CaseSensitive ($channel) {
    'latest' { $targetTag = (gh release view --repo Liplus-Project/liplus-language --json tagName --jq '.tagName' 2>$null) }
    'release' { $targetTag = (gh release list --repo Liplus-Project/liplus-language --limit 1 --json tagName --jq '.[0].tagName' 2>$null) }
    'tag' {
      # ls-remote is the only source of truth (stale local clone must not emit a
      # false "unnecessary"). On failure leave empty -> forces "needed".
      $remote = git -C $liplusDir ls-remote --tags --sort=-creatordate origin 2>$null
      if ($remote) {
        $targetTag = ($remote -split "`n" |
          ForEach-Object { if ($_ -match 'refs/tags/(.+?)(\^\{\})?$') { $matches[1] } } |
          Select-Object -First 1)
      }
    }
  }
  if ($targetTag) { $targetTag = $targetTag.Trim() }

  if (-not $adapterTag -or -not $targetTag -or ($adapterTag -ne $targetTag)) {
    $at = if ($adapterTag) { $adapterTag } else { 'unknown' }
    $tt = if ($targetTag) { $targetTag } else { 'unknown' }
    $updateReasons += "sentinel-tag(adapter=$at,target=$tt)"
  }

  # --- axis 2: Li+config.md schema canonical (no legacy keys) ---
  if (Test-Path -LiteralPath $configFile) {
    $legacy = Select-String -LiteralPath $configFile -CaseSensitive -Pattern '^\s*(LI_PLUS_REPOSITORY|USER_REPOSITORY|USER_REPOSITORY_EXECUTION_MODE)\s*=|^\s*[^#\s][^=]*_EXECUTION_MODE\s*=' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($legacy) { $updateReasons += 'legacy-schema-keys-present' }
  }

  # --- axis 3: language contract resolved (values resolved above, every matcher) ---
  if (-not $baseLang -or -not $projLang) {
    $b = if ($baseLang) { $baseLang } else { 'unset' }
    $p = if ($projLang) { $projLang } else { 'unset' }
    $updateReasons += "language-contract-unresolved(base=$b,project=$p)"
  }

  # --- emit update status marker ---
  if ($updateReasons.Count -eq 0) {
    Emit '━━━ Li+ update status ━━━'
    Emit "LI_PLUS_UPDATE_STATUS=unnecessary tag=$targetTag channel=$channel"
    Emit 'Sentinel-skip applies: AI skips Li+update.md re-execution this session. Li+config.md spot read (Read for value lookup, do not execute contents) is permitted.'
    Emit 'Override: Master input containing "Li+configを実行" / "Li+config を実行" forces the full walkthrough.'
    Emit '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
    Emit ''
  } else {
    $reasonStr = ($updateReasons -join ',')
    Emit '━━━ Li+ update status ━━━'
    Emit "LI_PLUS_UPDATE_STATUS=needed reason=$reasonStr"
    Emit 'AI must read Li+config.md and execute Li+update.md walkthrough this session.'
    Emit '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
    Emit ''
  }

  # --- unrecognized config value surfacing (#1804) ---
  # Rationale is in the claude port this one mirrors. -cne, not -ne: see the
  # -CaseSensitive note on the switch above.
  if ($channel -cne 'latest' -and $channel -cne 'release' -and $channel -cne 'tag') {
    Emit '━━━ Li+config: unrecognized value ━━━'
    Emit "LI_PLUS_CHANNEL=$channel is not one of: latest / release / tag. Values are case-sensitive. No target tag resolved, so the update status above is ""needed""."
    Emit '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
    Emit ''
  }
}

# --- emit language contract values (every matcher) ---
# Issue #1575: the contract text is always in context (adapter AGENTS.md) but
# its values were not, because resolving them was written as "read
# Li+config.md" and that file is not auto-loaded. Emitting the values the hook
# already holds removes the read step without baking anything into a generated
# file. Emitted on every path that reaches here, with an unresolved value
# rendered as 'unset', so inside a bootstrapped session the block's absence
# never has to be distinguished from an unresolved value. The unresolved-source
# guard exits well before this point and emits no language marker at all; the
# adapter Workspace_Language_Contract routes that state to the same ask-human
# branch as 'unset'.
$emitBase = if ($baseLang) { $baseLang } else { 'unset' }
$emitProj = if ($projLang) { $projLang } else { 'unset' }
Emit '━━━ Li+ language contract ━━━'
Emit "LI_PLUS_BASE_LANGUAGE=$emitBase"
Emit "LI_PLUS_PROJECT_LANGUAGE=$emitProj"
Emit 'Resolved from Li+config.md at session start. Definitions, scope and precedence: Workspace_Language_Contract (adapter AGENTS.md).'
Emit '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
Emit ''

# ===================================================================
# Cold-start material gathering
# ===================================================================

# --- coldstart anchor block (ALWAYS emitted; drift recovery anchor) ---
# Anchor = the H1 preamble only, cut at the first H2 semantic tag. The rule file
# is always-on loaded, so emitting it whole put the same text in one session's
# context twice. A file with no H2 section emits whole. Contract source =
# rules/evolution/cold-start-synthesis.md Hook Emission Contract (Anchor cut).
$coldstartLiteral = ''
if (Test-Path -LiteralPath $coldstartMd) {
  $lines = Get-Content -LiteralPath $coldstartMd -ErrorAction SilentlyContinue
  # Strip frontmatter (between first two --- markers) and a leading H1 line.
  $dashCount = 0
  $afterFm = @()
  $seenH1 = $false
  foreach ($l in $lines) {
    if ($l -eq '---') { $dashCount++; continue }
    if ($dashCount -lt 2) { continue }
    if ($seenH1 -and $l -match '^<[a-z0-9-]+>$') { break }
    if ($l -match '^# ') { $seenH1 = $true }
    $afterFm += $l
  }
  # Drop a leading H1, then drop leading and trailing blank lines.
  if ($afterFm.Count -gt 0 -and $afterFm[0] -match '^# ') { $afterFm = @($afterFm | Select-Object -Skip 1) }
  while ($afterFm.Count -gt 0 -and $afterFm[0].Trim() -eq '') { $afterFm = @($afterFm | Select-Object -Skip 1) }
  while ($afterFm.Count -gt 0 -and $afterFm[-1].Trim() -eq '') { $afterFm = @($afterFm | Select-Object -First ($afterFm.Count - 1)) }
  $coldstartLiteral = ($afterFm -join "`n")
}
Emit-Section 'Cold-start Synthesis (rules/evolution/cold-start-synthesis.md anchor)' $coldstartLiteral

# Non-startup matchers: rules were re-injected + cold-start anchor emitted; stop.
if ($matcher -cne 'startup') {
  Emit '━━━ Cold-start Synthesis: instruction ━━━'
  Emit "Matcher = $matcher. Session is continuous (resume/clear/compact). Rules were"
  Emit 'reinjected and the cold-start rule anchor re-anchored above. Treat the prior'
  Emit "session's in-context state as authoritative; do not re-orient from scratch."
  Emit '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
  Flush-Json
  exit 0
}

# --- register diff-only sections (startup only) ---
$sectionKeys    = @()
$sectionBanners = @()
$sectionBodies  = @()
function Register-Section([string]$key, [string]$banner, [string]$body) {
  $script:sectionKeys    += $key
  $script:sectionBanners += $banner
  $script:sectionBodies  += $body
}

# decision structure index head
$decisionHead = ''
if (Test-Path -LiteralPath $decisionStruct) {
  $decisionHead = (Get-Content -LiteralPath $decisionStruct -TotalCount 20 -ErrorAction SilentlyContinue) -join "`n"
}
Register-Section 'decision_structure_head' 'Decision structure index (docs/Decision-Structure.md head)' $decisionHead

# rules tree (fetch address table)
$rulesTree = ''
if (Test-Path -LiteralPath $rulesRoot) {
  # Ordinal, to match the bash ports' `LC_ALL=C sort`; `Sort-Object` is
  # culture-aware and would reorder this list under some locales.
  $rel = [string[]]@(
    Get-ChildItem -LiteralPath $rulesRoot -Recurse -Filter '*.md' -File -ErrorAction SilentlyContinue |
      ForEach-Object { 'rules/' + ($_.FullName.Substring($rulesRoot.Length).TrimStart('\','/') -replace '\\','/') })
  if ($rel.Count -gt 0) { [Array]::Sort($rel, [System.StringComparer]::Ordinal) }
  $rulesTree = ($rel -join "`n")
}
Register-Section 'rules_tree' 'Rules tree (fetch address table for rules/ cache)' $rulesTree

# recent releases (includes prereleases)
$recentReleases = ''
$rr = gh release list -R Liplus-Project/liplus-language --limit 3 2>$null
if ($rr) { $recentReleases = (($rr -split "`n") | Select-Object -First 3) -join "`n" }
Register-Section 'recent_releases' 'Recent releases (includes prereleases)' $recentReleases

# open in-progress issues (max 5)
$openIssues = ''
$oi = gh issue list -R Liplus-Project/liplus-language --state open --label in-progress --limit 5 --json number,title,labels --jq '.[] | "#\(.number) \(.title) [\(.labels | map(.name) | join(","))]"' 2>$null
if ($oi) { $openIssues = ($oi -split "`n" | Where-Object { $_ }) -join "`n" }
Register-Section 'open_in_progress_issues' 'Open in-progress issues (max 5)' $openIssues

# self-evaluation log head (workspace-local memory under Codex)
# Codex has no ~/.claude/projects/<slug>/memory; the workspace-local memory/
# directory is the available surface. Best-effort.
$selfEvalFound = ''
foreach ($cand in @(
    (Join-Path $projectRoot 'memory/self-evaluation_log.md'),
    (Join-Path $liplusDir 'memory/self-evaluation_log.md'))) {
  if (Test-Path -LiteralPath $cand) { $selfEvalFound = $cand; break }
}
$selfEvalHead = ''
if ($selfEvalFound) {
  $selfEvalHead = (Get-Content -LiteralPath $selfEvalFound -TotalCount 15 -ErrorAction SilentlyContinue) -join "`n"
}
Register-Section 'self_eval_head' 'Self-evaluation log head (most recent)' $selfEvalHead

# promotion candidates (memory -> Li+ source)
# Evolution Loop observe stage: surface pattern-detection candidates at cold-start
# so that AI sees promotion candidates without waiting for passive noticing.
# rules/evolution/evolution.md "Pattern Detection Surfacing At Cold-start" fixes
# the three detection targets (self-evaluation log repetition / recent memory
# additions / keyword overlap with Li+ source) and delegates the thresholds and
# the concrete logic to the adapter, which is this block.
#
# #1632 F3 / #1636: every detector below used to read a format nothing writes, so
# the section was empty on every session and an empty surface could not be told
# apart from "nothing crossed the noise floor". Detector 1 matched a
# `root_cause:` / `tags:` line syntax that no spec defines and the log has never
# used; detectors 2 and 3 scanned the flat feedback.md / project.md pair that the
# one-memory-per-file host layout replaced. The formats read below are the ones
# the live artifacts actually carry, and they are the same formats the sibling
# ports read — the detection behavior is deliberately identical across
# adapter/claude/hooks/on-session-start.sh, on-session-start.sh and this file.
#
# Case sensitivity: the bash ports match with awk / sed / `case`, which are
# case-sensitive, so every comparison here that stands in for one of those uses
# the case-sensitive operator (`-cmatch` / `-ccontains` / `-cnotcontains`) or an
# ordinal comparer. `ToLowerInvariant` stands in for awk `tolower`, which is
# ASCII-only and culture-independent.
$thresholdN = 2
# $surfaceCap bounds the two list-shaped detectors. This is an orientation
# surface read at session opening, and a list past roughly this length stops
# being scannable; the full count is still printed, so a truncated list never
# hides that more exists.
$surfaceCap = 10

# A candidate qualifies as $memoryDir only when it holds at least one file that
# some $memoryDir consumer reads. Directory existence alone is not the criterion:
# an empty higher-precedence directory would otherwise shadow a populated
# lower-precedence one and silence every consumer at once.
# The marker set is the files $memoryDir consumers read: the observation surface,
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
function Test-MemoryDirPopulated {
  param([string]$Dir)
  foreach ($markerFile in @(
      'self-evaluation_log.md',
      'self-evolution-observation.md',
      'promotion_tally.md')) {
    if (Test-Path -LiteralPath (Join-Path $Dir $markerFile) -PathType Leaf) { return $true }
  }
  foreach ($markerPrefix in @('feedback', 'project', 'reference', 'user')) {
    $hit = Get-ChildItem -LiteralPath $Dir -Filter "$markerPrefix*.md" -File -ErrorAction SilentlyContinue |
      Select-Object -First 1
    if ($hit) { return $true }
  }
  return $false
}

# Memory entry files inside a resolved $memoryDir, under the same one-memory-
# per-file layout. Excluded are the index and the three transient operational
# files, each of which has its own dedicated reader: MEMORY.md is read by the
# index emit, self-evaluation_log.md by the self-eval head, and the two
# date-driven surfaces below read self-evolution-observation.md and
# promotion_tally.md. The last of those four carried no reader until #1894, so
# the stated reason held for three members and not for the fourth; the exclusion
# was right either way (a tally cluster is not a memory entry), but what the
# exclusion stands in for is the dedicated reader. Flat feedback.md /
# project.md are NOT excluded, so a workspace that has not migrated is still
# scanned. Ordinal sort, because the detector output is sha256-fingerprinted for
# diff-only emission and must not depend on directory order — and to match the
# bash ports, which pin `LC_ALL=C sort` (#1651) so that their order is bytewise
# by enforcement rather than by whatever locale the session happens to carry.
# Byte order over UTF-8 and ordinal order over UTF-16 agree on the BMP, which is
# the range these names live in.
function Get-MemoryEntryFiles {
  param([string]$Dir)
  $skip = @('MEMORY.md', 'promotion_tally.md', 'self-evaluation_log.md', 'self-evolution-observation.md')
  $names = [string[]]@(
    Get-ChildItem -LiteralPath $Dir -Filter '*.md' -File -ErrorAction SilentlyContinue |
      Where-Object { $skip -cnotcontains $_.Name } |
      ForEach-Object { $_.Name })
  if ($names.Count -eq 0) { return @() }
  [Array]::Sort($names, [System.StringComparer]::Ordinal)
  return @($names | ForEach-Object { Join-Path $Dir $_ })
}

# Title of one memory entry = its frontmatter `name:` (written by the host
# auto-memory) when present, else the filename stem. Under the flat-file layout
# the equivalent unit was a `## ` section header; with one memory per file the
# file itself is the entry, so the title moves to the frontmatter.
function Get-MemoryEntryTitle {
  param([string]$Path)
  $title = ''
  foreach ($line in @(Get-Content -LiteralPath $Path -TotalCount 10 -ErrorAction SilentlyContinue)) {
    if ($line -cmatch '^name:[ \t]*(.*)$') { $title = $matches[1]; break }
  }
  $title = ($title -replace "`r", '') -replace '\s+$', ''
  if (-not $title) { return [System.IO.Path]::GetFileNameWithoutExtension($Path) }
  return $title
}

# The 10 axes of `skills/evolution-self-eval/SKILL.md`, verbatim and lowercased.
# Canonical vocabulary for the axis-name normal form: a shorthand that is a
# word-boundary prefix of exactly one of these expands to it, which is why no
# alias table exists beside the list.
$axisCanon = @(
  'assumption surfacing', 'contradiction catch', 'deepening axis fit',
  'silence respect', 'loop entry', 'character drift', 'review partition',
  'gist vs literal', 'expansion limit', 'request depth')

# Inline pair-list terminators, in the order the skill lists them.
$axisTerminators = @('。', 'Root cause:', 'Domain:')

# Bracket tokens the scans below track. ASCII and full-width are one class: an
# opener of either kind is closed by a closer of either kind. Tracking a further
# pair is one more entry in these tables, not another character test wired into
# the walk — comparing characters inline is what left the full-width pair
# untracked while the ASCII pair worked.
$axisBracketOpen = @('(', '（')
$axisBracketClose = @(')', '）')

# First index of a bracket opener in $Text, or -1. Matching is not required
# here: the normal form drops the qualifier and everything after it.
function Get-OpenIndex {
  param([string]$Text)
  $best = -1
  foreach ($t in $axisBracketOpen) {
    $p = $Text.IndexOf($t, [System.StringComparison]::Ordinal)
    if ($p -ge 0 -and ($best -lt 0 -or $p -lt $best)) { $best = $p }
  }
  return $best
}

# Bracket occurrences in $Text, positions ascending, with the ones that have no
# partner dropped. Both ends must be present before the span between them counts
# as bracketed: a stray `)` was always ignored, while a stray `(` used to hold
# the rest of the line inside brackets, so every pair written after it went
# uncounted.
function Get-BracketMap {
  param([string]$Text)
  $occ = New-Object System.Collections.Generic.List[psobject]
  $cursor = 0
  while ($cursor -lt $Text.Length) {
    $best = -1
    $bestLen = 0
    $bestOpen = $false
    foreach ($t in $axisBracketOpen) {
      $p = $Text.IndexOf($t, $cursor, [System.StringComparison]::Ordinal)
      if ($p -ge 0 -and ($best -lt 0 -or $p -lt $best)) { $best = $p; $bestLen = $t.Length; $bestOpen = $true }
    }
    foreach ($t in $axisBracketClose) {
      $p = $Text.IndexOf($t, $cursor, [System.StringComparison]::Ordinal)
      if ($p -ge 0 -and ($best -lt 0 -or $p -lt $best)) { $best = $p; $bestLen = $t.Length; $bestOpen = $false }
    }
    if ($best -lt 0) { break }
    $occ.Add([pscustomobject]@{ Pos = $best; IsOpen = $bestOpen; Live = $false })
    $cursor = $best + $bestLen
  }
  $stack = New-Object System.Collections.Generic.Stack[int]
  for ($i = 0; $i -lt $occ.Count; $i++) {
    if ($occ[$i].IsOpen) {
      $stack.Push($i)
    } elseif ($stack.Count -gt 0) {
      $occ[$stack.Pop()].Live = $true
      $occ[$i].Live = $true
    }
  }
  return ,$occ
}

# First index of $Needle in $Hay that sits outside brackets, or -1.
# Ordinal throughout: the `IndexOf(string)` overload without a comparison
# argument is culture-aware and would not agree with the awk ports.
function Get-OuterIndex {
  param([string]$Hay, [string]$Needle)
  $occ = Get-BracketMap $Hay
  $base = 0
  while ($true) {
    if ($base -gt $Hay.Length) { return -1 }
    $pos = $Hay.IndexOf($Needle, $base, [System.StringComparison]::Ordinal)
    if ($pos -lt 0) { return -1 }
    $depth = 0
    foreach ($t in $occ) {
      if ($t.Pos -ge $pos) { break }
      if (-not $t.Live) { continue }
      if ($t.IsOpen) { $depth++ } else { $depth-- }
    }
    if ($depth -eq 0) { return $pos }
    $base = $pos + 1
  }
}

# Inline pair list of one `**Axis tags**:` line, per the skill's "Inline list
# end": the list stops at the first outside-brackets terminator, then splits
# on outside-brackets ' / '. Without the stop the last segment ran to end of
# line and swallowed the free-form trailer, which both fed that prose to the
# miss scan and split a parenthetical ' / ' inside it into a phantom axis.
function Split-AxisPairs {
  param([string]$Rest)
  $best = -1
  foreach ($mark in $axisTerminators) {
    $p = Get-OuterIndex $Rest $mark
    if ($p -ge 0 -and ($best -lt 0 -or $p -lt $best)) { $best = $p }
  }
  if ($best -ge 0) { $Rest = $Rest.Substring(0, $best) }
  $pairs = New-Object System.Collections.Generic.List[string]
  while ($true) {
    $p = Get-OuterIndex $Rest ' / '
    if ($p -lt 0) { break }
    $pairs.Add($Rest.Substring(0, $p))
    $Rest = $Rest.Substring($p + 3)
  }
  $pairs.Add($Rest)
  return $pairs
}

# Axis name normal form, step for step as the skill lists it.
function Get-AxisNormalForm {
  param([string]$Axis)
  $name = $Axis -replace '\*', ''
  $p = Get-OpenIndex $name
  if ($p -ge 0) { $name = $name.Substring(0, $p) }
  $name = (($name -replace '[-_]', ' ') -replace '\s+', ' ').Trim().ToLowerInvariant()
  if (-not $name) { return '' }
  $hits = 0
  $expanded = ''
  foreach ($c in $axisCanon) {
    if ($c -ceq $name) { return $name }
    if ($c.Length -gt $name.Length -and ($c.Substring(0, $name.Length + 1) -ceq ($name + ' '))) {
      $hits++
      $expanded = $c
    }
  }
  # Ambiguous shorthand stays as written; guessing would merge two axes.
  if ($hits -eq 1) { return $expanded }
  return $name
}

# One (axis, verdict) pair out of a self-evaluation entry's axis-tag list.
# Counted only when the verdict carries the word `miss`.
function Add-AxisMiss {
  param([hashtable]$Tally, [string]$Pair)
  $sep = $Pair.IndexOf([char]':')
  if ($sep -lt 0) { return }
  $axis = Get-AxisNormalForm $Pair.Substring(0, $sep)
  $verdict = $Pair.Substring($sep + 1)
  if (-not $axis) { return }
  if ($verdict.ToLowerInvariant().IndexOf('miss', [System.StringComparison]::Ordinal) -lt 0) { return }
  if ($Tally.ContainsKey($axis)) { $Tally[$axis]++ } else { $Tally[$axis] = 1 }
}

# Probe the directory directly when self-evaluation_log.md is absent: the other
# $memoryDir readers (promotion detectors, self-evolution observation surface)
# must not be silenced by the absence of an unrelated file.
$memoryDir = ''
if ($selfEvalFound) {
  $memoryDir = Split-Path -Parent $selfEvalFound
} else {
  foreach ($memCand in @((Join-Path $projectRoot 'memory'), (Join-Path $liplusDir 'memory'))) {
    if (Test-MemoryDirPopulated $memCand) { $memoryDir = $memCand; break }
  }
}
$promotionBody = ''

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
if ($selfEvalFound -and (Test-Path -LiteralPath $selfEvalFound)) {
  # Ordinal comparer to match the awk arrays of the bash ports, which key
  # case-sensitively while a `@{}` literal does not. Unlike the overlap detector
  # below, no input reaches this table still carrying case: Get-AxisNormalForm
  # lowercases on every return path, so the comparer cannot change a tally today.
  # It is set anyway because the parity it holds is with awk's semantics, not
  # with the current normalizer — a normalizer that stopped lowercasing would
  # otherwise split this port's tally away from the bash ports silently.
  $axisCount = New-Object System.Collections.Hashtable ([System.StringComparer]::Ordinal)
  $inAxisBlock = $false
  foreach ($l in @(Get-Content -LiteralPath $selfEvalFound -ErrorAction SilentlyContinue)) {
    if ($l -cmatch '^\s*\*\*Axis tags') {
      # Everything past the closing "**:" of the label is the inline pair list;
      # an empty remainder means the bullet layout follows.
      $labelEnd = $l.IndexOf('**:', [System.StringComparison]::Ordinal)
      $rest = if ($labelEnd -ge 0) { $l.Substring($labelEnd + 3) } else { '' }
      if ($rest -match '\S') {
        foreach ($part in (Split-AxisPairs $rest)) { Add-AxisMiss $axisCount $part }
        $inAxisBlock = $false
      } else {
        $inAxisBlock = $true
      }
      continue
    }
    if ($inAxisBlock -and ($l -match '^\s*-\s')) {
      # One bullet is one pair: the line break already ends the verdict, so the
      # inline terminator does not apply here.
      Add-AxisMiss $axisCount ($l -replace '^\s*-\s*', '')
      continue
    }
    if ($inAxisBlock) { $inAxisBlock = $false }
  }
  $axisLines = [string[]]@(
    $axisCount.Keys |
      Where-Object { $axisCount[$_] -ge $thresholdN } |
      ForEach-Object { '  - axis "{0}" tagged miss x{1}' -f $_, $axisCount[$_] })
  if ($axisLines.Count -gt 0) {
    [Array]::Sort($axisLines, [System.StringComparer]::Ordinal)
    $promotionBody += "repeated self-evaluation axis misses:`n" + ($axisLines -join "`n") + "`n"
  }
}

# Detector 2: memory entries written or rewritten within the last 7 days.
# One memory is one file, so the entry is the unit of recency and file mtime is
# the signal; the flat-file era counted '## ' sections inside two files instead.
# Flagged when the count reaches $thresholdN.
#
# Note: this 7d window is the memory-scan recency window (Cold-start observe
# stage surface), independent from the 3d cluster window in
# rules/evolution/promotion-judgment.md. The two timers serve different axes:
#   - 7d here = "did anything new land in memory recently? show it for AI review"
#   - 3d there = "has the same cluster crossed the noise floor for promotion?"
# Do not unify the two values; they intentionally sit on different axes.
if ($memoryDir -and (Test-Path -LiteralPath $memoryDir)) {
  $recentEntries = ''
  $recentCount = 0
  $recentCutoff = (Get-Date).AddDays(-7)
  foreach ($mf in (Get-MemoryEntryFiles $memoryDir)) {
    $mtime = (Get-Item -LiteralPath $mf -ErrorAction SilentlyContinue).LastWriteTime
    if ($mtime -and $mtime -ge $recentCutoff) {
      $recentCount++
      if ($recentCount -le $surfaceCap) {
        $recentEntries += "  - $(Split-Path -Leaf $mf) [$(Get-MemoryEntryTitle $mf)]`n"
      }
    }
  }
  if ($recentCount -ge $thresholdN) {
    # A consolidate pass rewrites every entry at once, so the cap is a normal
    # occurrence rather than an edge case.
    if ($recentCount -gt $surfaceCap) {
      $recentEntries += "  - ... and $($recentCount - $surfaceCap) more`n"
    }
    $promotionBody += "recent memory additions (<= 7d, $recentCount entries):`n$recentEntries"
  }
}

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
# A pair is reported only once at least $thresholdN distinct title tokens land in
# the same source file. One shared common word ("identity", "answer") is
# coincidence at this corpus size and produced hundreds of lines when measured
# against the live memory set; two independent words of one title meeting in one
# file is topical adjacency, which is what this detector is looking for.
#
# The source is named by its path relative to the clone, not by basename: every
# skill file is called SKILL.md, so a basename label identifies nothing.
#
# Matching is on whole words, not substrings: each source file is split on
# non-alphanumeric runs exactly as the titles are, so `user` no longer hits
# inside `users` and the two bash ports and this one agree on what a hit is.
# The rank prefix (inverted token count, zero padded) makes a plain ordinal sort
# order strongest adjacency first, and the cap is applied after the sort —
# capping an unordered set would pick a different subset per run and churn the
# sha256 the diff-only emission compares against.
if ($memoryDir -and (Test-Path -LiteralPath $memoryDir)) {
  # Parallel arrays, deliberately not de-duplicated: a token repeated inside one
  # title counts twice, matching the bash ports.
  $tokenLabels = @()
  $tokenNames = @()
  foreach ($mf in (Get-MemoryEntryFiles $memoryDir)) {
    $entryTitle = Get-MemoryEntryTitle $mf
    $entryLabel = "$(Split-Path -Leaf $mf) [$entryTitle]"
    foreach ($tok in ($entryTitle.ToLowerInvariant() -split '[^a-z0-9]+')) {
      if ($tok.Length -lt 4) { continue }
      if (@('feedback', 'project', 'reference', 'user') -ccontains $tok) { continue }
      $tokenLabels += $entryLabel
      $tokenNames += $tok
    }
  }
  $srcFiles = @()
  if (Test-Path -LiteralPath $rulesRoot) {
    $srcFiles += @(Get-ChildItem -LiteralPath $rulesRoot -Recurse -Filter '*.md' -File -ErrorAction SilentlyContinue)
  }
  $skillsRoot = Join-Path $liplusDir 'skills'
  if (Test-Path -LiteralPath $skillsRoot) {
    $srcFiles += @(Get-ChildItem -LiteralPath $skillsRoot -Recurse -Depth 1 -Filter 'SKILL.md' -File -ErrorAction SilentlyContinue)
  }
  if ($tokenNames.Count -gt 0 -and $srcFiles.Count -gt 0) {
    $wanted = @{}
    foreach ($tok in $tokenNames) { $wanted[$tok] = $true }
    $srcHits = @{}
    $rootPrefix = ($liplusDir -replace '\\', '/').TrimEnd('/') + '/'
    foreach ($sf in $srcFiles) {
      $rel = $sf.FullName -replace '\\', '/'
      if ($rel.StartsWith($rootPrefix)) { $rel = $rel.Substring($rootPrefix.Length) }
      $content = Get-Content -LiteralPath $sf.FullName -Raw -ErrorAction SilentlyContinue
      if (-not $content) { continue }
      $seen = @{}
      foreach ($word in ($content.ToLowerInvariant() -split '[^a-z0-9]+')) {
        if (-not $wanted.ContainsKey($word)) { continue }
        if ($seen.ContainsKey($word)) { continue }
        $seen[$word] = $true
        if (-not $srcHits.ContainsKey($word)) { $srcHits[$word] = @() }
        $srcHits[$word] += $rel
      }
    }
    # Ordinal comparer, not the `@{}` literal: a PowerShell hashtable literal
    # keys case-insensitively, while the awk arrays the bash ports use are
    # case-sensitive. This key carries the entry title and the source path at
    # their original case, so the literal would merge two pairs the bash ports
    # keep apart. ($wanted / $seen / $srcHits key on already-lowercased tokens,
    # so the default comparer is equivalent there.)
    $pairs = New-Object System.Collections.Hashtable ([System.StringComparer]::Ordinal)
    for ($j = 0; $j -lt $tokenNames.Count; $j++) {
      $tok = $tokenNames[$j]
      if (-not $srcHits.ContainsKey($tok)) { continue }
      foreach ($rel in $srcHits[$tok]) {
        $key = $tokenLabels[$j] + [char]28 + $rel
        if ($pairs.ContainsKey($key)) {
          $pairs[$key].Tokens += " $tok"
          $pairs[$key].Depth++
        } else {
          $pairs[$key] = [pscustomobject]@{
            Label  = $tokenLabels[$j]
            Rel    = $rel
            Tokens = " $tok"
            Depth  = 1
          }
        }
      }
    }
    $overlapRanked = [string[]]@(
      $pairs.Values |
        Where-Object { $_.Depth -ge $thresholdN } |
        ForEach-Object { ('{0:d3}' -f (999 - $_.Depth)) + "`t" + "  - $($_.Label) ~ $($_.Rel) (tokens:$($_.Tokens))" })
    if ($overlapRanked.Count -gt 0) {
      [Array]::Sort($overlapRanked, [System.StringComparer]::Ordinal)
      $overlapCount = $overlapRanked.Count
      $overlapText = (@($overlapRanked |
        Select-Object -First $surfaceCap |
        ForEach-Object { $_.Substring($_.IndexOf("`t") + 1) }) -join "`n")
      if ($overlapCount -gt $surfaceCap) {
        $overlapText += "`n  - ... and $($overlapCount - $surfaceCap) more"
      }
      $promotionBody += "possible keyword overlap with Li+ source ($overlapCount pairs):`n$overlapText`n"
    }
  }
}
Register-Section 'promotion_candidates' 'Promotion candidates (memory → Li+ source)' $promotionBody

# --- self-evolution observation surface (due / overdue) ---
# Implements rules/evolution/cold-start-synthesis.md "Self-Evolution Observation
# Surface" (#1537). Port of the same block in adapter/claude/hooks/on-session-start.sh:
#   next_check <= today AND verdict_state == pending -> "observation due"
#   expires    <  today AND verdict_state == pending -> "observation overdue,
#                                                       human judgment needed"
#
# Deliberately NOT passed through Register-Section: the trigger is date-driven
# while the body is content-driven, so an unresolved entry keeps a byte-identical
# body and a fingerprint comparison would surface it once and then suppress it
# for the whole period it still needs attention. Empty body = silent skip.
# An entry past expires is reported as OVERDUE only (overdue carries the
# escalation; reporting it on both axes is noise). CompareOrdinal on ISO
# YYYY-MM-DD is order-preserving and culture-independent.
$observationBody = ''
$observationFile = ''
if ($memoryDir) {
  $obsCand = Join-Path $memoryDir 'self-evolution-observation.md'
  if (Test-Path -LiteralPath $obsCand) { $observationFile = $obsCand }
}
if ($observationFile) {
  $today = (Get-Date).ToString('yyyy-MM-dd')
  $entries = @()
  $cur = $null
  # -cmatch / -cne (not -match / -ne): PowerShell comparison is case-insensitive
  # by default, while the awk ports in the two on-session-start.sh hooks are
  # case-sensitive. Without the c-prefix, `PR:` / `Verdict_State:` / `Pending`
  # would be accepted here and rejected there — same input, different output.
  foreach ($l in (Get-Content -LiteralPath $observationFile -ErrorAction SilentlyContinue)) {
    if ($l -cmatch '^##\s+observation:\s*(.*)$') {
      if ($cur) { $entries += $cur }
      $cur = @{ name = $matches[1].Trim(); pr = ''; expires = ''; next = ''; state = '' }
      continue
    }
    if ($l -cmatch '^##\s') { if ($cur) { $entries += $cur; $cur = $null }; continue }
    if (-not $cur) { continue }
    if ($l -cmatch '^\s*pr:\s*(.*)$')            { $cur.pr      = $matches[1].Trim(); continue }
    if ($l -cmatch '^\s*expires:\s*(.*)$')       { $cur.expires = $matches[1].Trim(); continue }
    if ($l -cmatch '^\s*next_check:\s*(.*)$')    { $cur.next    = $matches[1].Trim(); continue }
    if ($l -cmatch '^\s*verdict_state:\s*(.*)$') { $cur.state   = $matches[1].Trim(); continue }
  }
  if ($cur) { $entries += $cur }

  $observationList = ''
  foreach ($e in $entries) {
    # Empty descriptor = malformed header; the awk ports drop it in flush().
    if (-not $e.name) { continue }
    if ($e.state -cne 'pending') { continue }
    $label = ''
    if ($e.expires -and ([string]::CompareOrdinal($e.expires, $today) -lt 0)) {
      $label = "OVERDUE (expires $($e.expires), human judgment needed)"
    } elseif ($e.next -and ([string]::CompareOrdinal($e.next, $today) -le 0)) {
      $label = "DUE (next_check $($e.next))"
    }
    if ($label) {
      $suffix = if ($e.pr) { " [PR #$($e.pr)]" } else { '' }
      $observationList += "  - $($label): $($e.name)$suffix`n"
    }
  }
  if ($observationList) {
    $observationBody = "memory/self-evolution-observation.md - entries whose check window has opened:`n" +
      $observationList +
      "Surfacing is observation, not auto-action. Verdict transition (settle / revert /`n" +
      "supersede) follows rules/evolution/memory-entry-format.md Self-Evolution`n" +
      "Observation Format."
  }
}

# Emitted before the diff sections so a due/overdue entry is not buried under
# whatever else changed.
$observationEmitted = $false
if ($observationBody) {
  Emit-Section 'Self-evolution observation (due / overdue)' $observationBody
  $observationEmitted = $true
}

# --- promotion tally expiry surface (due / overdue) ---
# Implements rules/evolution/cold-start-synthesis.md "Promotion Tally Expiry
# Surface" (#1894). Port of the same block in adapter/claude/hooks/on-session-start.sh:
#   expires <= today -> "tally expiry reached"
#   expires <  today -> "tally expiry overdue, threshold judgment not taken"
#
# Same treatment as the observation surface above and for the same reasons: not
# passed through Register-Section (date-driven trigger over a content-driven
# body), overdue reported alone, empty body = silent skip, CompareOrdinal on
# ISO YYYY-MM-DD.
#
# No verdict field is read because the tally format carries none: every outcome
# the Threshold Rules name removes the cluster, so a cluster still written down
# is a judgment not yet taken. The occurrence count is carried on the line
# because it selects the Threshold Rules row that applies.
$tallyBody = ''
$tallyFile = ''
if ($memoryDir) {
  $tallyCand = Join-Path $memoryDir 'promotion_tally.md'
  if (Test-Path -LiteralPath $tallyCand) { $tallyFile = $tallyCand }
}
if ($tallyFile) {
  $today = (Get-Date).ToString('yyyy-MM-dd')
  $clusters = @()
  $curC = $null
  # -cmatch (not -match): same case-sensitivity parity with the awk ports as the
  # observation block above.
  foreach ($l in (Get-Content -LiteralPath $tallyFile -ErrorAction SilentlyContinue)) {
    if ($l -cmatch '^##\s+cluster:\s*(.*)$') {
      if ($curC) { $clusters += $curC }
      $curC = @{ name = $matches[1].Trim(); expires = ''; occ = 0 }
      continue
    }
    if ($l -cmatch '^##\s') { if ($curC) { $clusters += $curC; $curC = $null }; continue }
    if (-not $curC) { continue }
    if ($l -cmatch '^\s*expires:\s*(.*)$') { $curC.expires = $matches[1].Trim(); continue }
    if ($l -cmatch '^\s*-\s')              { $curC.occ++; continue }
  }
  if ($curC) { $clusters += $curC }

  $tallyList = ''
  foreach ($c in $clusters) {
    # Empty descriptor = malformed header; the awk ports drop it in flush().
    if (-not $c.name) { continue }
    $label = ''
    if ($c.expires -and ([string]::CompareOrdinal($c.expires, $today) -lt 0)) {
      $label = "OVERDUE (expires $($c.expires), threshold judgment not taken)"
    } elseif ($c.expires -and ([string]::CompareOrdinal($c.expires, $today) -le 0)) {
      $label = "DUE (expires $($c.expires))"
    }
    if ($label) {
      $tallyList += "  - $($label): $($c.name) [occurrences: $($c.occ)]`n"
    }
  }
  if ($tallyList) {
    $tallyBody = "memory/promotion_tally.md - clusters whose 3d window has closed:`n" +
      $tallyList +
      "Surfacing is observation, not auto-action. The threshold judgment (issue`n" +
      "creation / merge into an existing promotion-marker issue / deletion) follows`n" +
      "rules/evolution/promotion-judgment.md Threshold Rules."
  }
}

# Emitted next to the observation surface, before the diff sections, for the
# same reason: a closed window must not be buried under whatever else changed.
$tallyEmitted = $false
if ($tallyBody) {
  Emit-Section 'Tally expiry (due / overdue)' $tallyBody
  $tallyEmitted = $true
}

# ===================================================================
# Diff-only emission (startup matcher)
# ===================================================================
$failSafeFull = $false
$failSafeReason = ''

# Read prior state.
$priorFp = @{}
if (Test-Path -LiteralPath $stateFile) {
  try {
    $prior = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
    if ($prior -and $prior.sections) {
      foreach ($prop in $prior.sections.PSObject.Properties) { $priorFp[$prop.Name] = $prop.Value }
    }
  } catch {
    $failSafeFull = $true; $failSafeReason = 'state file malformed JSON'
  }
} else {
  $failSafeFull = $true; $failSafeReason = 'state file absent (first run or post-cleanup)'
}

$emittedAny = $false
$newSections = @{}
for ($i = 0; $i -lt $sectionKeys.Count; $i++) {
  $key = $sectionKeys[$i]; $banner = $sectionBanners[$i]; $body = $sectionBodies[$i]
  if (-not $body) { continue }
  $curFp = Sha256Of $body
  $newSections[$key] = $curFp
  $pf = if ($priorFp.ContainsKey($key)) { $priorFp[$key] } else { '' }
  if ($failSafeFull -or ($curFp -ne $pf)) {
    Emit-Section $banner $body
    $emittedAny = $true
  }
}

# The two date-driven surfaces count as material: pairing a just-emitted overdue
# entry or an expired tally cluster with "No new orientation material" would be
# self-contradictory output.
if (-not $emittedAny -and -not $observationEmitted -and -not $tallyEmitted -and -not $failSafeFull) {
  Emit-Section 'Orientation diff' 'No new orientation material since last session. Prior in-context state remains authoritative.'
}

# Persist new state (best-effort).
try {
  if (-not (Test-Path -LiteralPath $stateDir)) { New-Item -ItemType Directory -Path $stateDir -Force | Out-Null }
  $ts = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
  $stateObj = @{ sections = $newSections; last_emit_at = $ts }
  $stateObj | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $stateFile -Encoding UTF8
} catch { }

# --- instruction to the AI ---
if ($failSafeFull) {
  Emit '━━━ Cold-start Synthesis: instruction ━━━'
  Emit "Fail-safe full emit (reason: $failSafeReason). All available material is shown"
  Emit 'above. Using it, perform Cold-start Synthesis through Character_Instance:'
  Emit '1. Summarize the current Li+ state (active tag, recent structural shifts, unresolved threads).'
  Emit '2. Report synthesis to the human as the opening orientation.'
  Emit 'The hook only gathers material. Judgment and expression belong to the AI.'
  Emit '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
} else {
  Emit '━━━ Cold-start Synthesis: instruction ━━━'
  Emit 'Diff-only emission: only sections changed since the prior session are shown'
  Emit 'above (rules + cold-start rule anchor are always re-anchored). Using the diff'
  Emit 'plus your loaded layers, perform Cold-start Synthesis through Character_Instance:'
  Emit '1. Summarize the current Li+ state delta (what changed; unresolved threads).'
  Emit '2. Report synthesis to the human as the opening orientation — apply the'
  Emit '   non-redundancy gate in rules/evolution/cold-start-synthesis.md (silent'
  Emit '   skip when no unique insight remains after synthesis).'
  Emit 'The hook only gathers material. Judgment and expression belong to the AI.'
  Emit '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
}

Flush-Json
exit 0
