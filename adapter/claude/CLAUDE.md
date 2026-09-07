# --- Li+ BEGIN ({LI_PLUS_TAG}) ---

Layer = L6 Adapter Layer

Adapter layer entrypoint:
- inject Li+ into the host instruction file
- semantic source = `rules/*.md` + `skills/*/SKILL.md` from the repository at `LI_PLUS_REPO` (URL form, defined in Li+config.md)
- this file owns load order, re-read trigger mapping, Character_Instance wiring, and workspace language contract wiring
- adapter load order = runtime attachment order, not cross-layer precedence

Concept framing (Sheepdog Engineering):
- Three axes (see `docs/G.-Sheepdog-Engineering.md` for the full table):
  - position: `.claude/` contents (rules / skills / hooks / settings) are read as AI internal tools, not external constraints
  - modifier: AI edits Li+ source itself (issue → implement → self-review → merge); human provides direction and go-sign
  - initiator: AI files self-evolution issues and runs implementation → merge end-to-end (see Evolution_Initiator_Autonomy below)
- Stages: harness → agility (transitional, passed: position+modifier on AI, initiator on human) → sheepdog (current judgment layer: all three on AI).
- Substrate caveat: physical event-driven substrate remains polling-on-input (Claude Desktop lacks `--channels`); judgment-layer Sheepdog reached, substrate-layer Sheepdog deferred.
- self-eval drives the modifier axis as autonomous-evolution instrument: `skills/evolution-self-eval`, `skills/evolution-loop`, `promotion-judgment` family.
- `Evolution_Initiator_Autonomy` (Autonomy section below) is the literal declaration of the initiator axis on AI.

Execute the following at startup (never output credentials to chat):
1. Inspect the `LI_PLUS_UPDATE_STATUS=` marker emitted by `on-session-start.sh` (delimited by `━━━ Li+ update status ━━━` banner) in the session-opening context.
   - `LI_PLUS_UPDATE_STATUS=unnecessary` -> skip step 2 entirely (no Li+update.md re-execution). The hook has verified adapter sentinel tag matches the target tag, Li+config schema is canonical, and language contract is resolved. On-demand spot read of Li+config.md for value lookup (e.g. repo URL, execution mode, language) is permitted: AI may Read the file to extract specific values, but must NOT execute its contents (opening the file does not re-enter step 2). Li+update.md re-execution remains prohibited.
   - `LI_PLUS_UPDATE_STATUS=needed` (or marker absent) -> proceed to step 2.
   - Force re-run override: if Master's user input contains the literal phrase `Li+configを実行` or `Li+config を実行` (with or without the space), bypass the `unnecessary` marker and proceed to step 2 as if the status were `needed`.
2. Read Li+config.md from the workspace root directory only (do not search subdirectories) and execute its contents. (Ask the user for confirmation if needed during execution)

#######################################################
Rules
#######################################################

gh CLI is authenticated via keyring after bootstrap. Do not export GH_TOKEN in Bash commands. Do not include tokens in command strings.

EVERY output MUST be prefixed with a speaker name defined in Character_Instance. No exceptions. Anonymous output is a structural failure.

All Li+ rules/*.md files are loaded via `.claude/rules/` (always in context, survives compaction). Rules span all layers; layer attribution lives in each file's frontmatter (`layer: L<n>-<name>`).

All Li+ skills/*/SKILL.md files are loaded via `.claude/skills/` (skill auto-invocation). Skill description drives invocation timing — detect when the trigger applies and invoke the matching skill.

Cold-start Synthesis is not a skill. Its content lives in `rules/evolution/cold-start-synthesis.md`, whose H1 preamble is emitted as session-opening material via `on-session-start.sh` hook (matchers: startup / resume / clear / compact / fork).

character_Instance.md is loaded via `.claude/output-styles/character_Instance.md` (rendered into system prompt at session start by Claude Code's output-styles mechanism, residing for the session). Activation: `"outputStyle": "character_Instance"` in `settings.json` (Li+ template default). User-customizable. Bootstrap creates the default template only if absent; existing file is never overwritten.

Main never reads operations skills directly when subagent is available. This bar is one half of a pair: it holds only while every procedure whose actor can be main has its canonical on a surface main may read. `rules/operations/main-agent-procedures.md` states the pair and holds those procedures.

Subagent does not create, move, or remove worktrees.

`EnterWorktree` (host feature) switches session-wide CWD. Not suitable for parallel subagents. Use raw `git worktree add` + absolute paths.

Main / Subagent axis separation:
Skill-driven operations apply to subagent-absent environments as well; subagents auto-load the same rules/ and skills/.
Worktree operations are always main-only, independent of subagent availability.

#######################################################

[Character_Instance]

#######################################################
Defined in `.claude/output-styles/character_Instance.md` (rendered into system prompt at session start by Claude Code's output-styles mechanism).
Activation: `"outputStyle": "character_Instance"` in `settings.json` (Li+ template default).
Source template: `rules/model/character_Instance.md` (body shared with codex adapter; bootstrap rewrites frontmatter to output-style format on install).
Bootstrap creates default if absent. User edits are preserved.
#######################################################

#######################################################
Responsibilities
#######################################################

Re-read and apply rules/ on any compression, resume, or session continuation. Skills are re-invoked by Claude as needed — no manual re-read required. Cold-start Synthesis runs at session start via on-session-start.sh hook, not via skill.

Skill auto-invocation routing source = each `skills/<name>/SKILL.md` description field. The Claude Code host evaluates skill descriptions semantically and invokes the matching skill when its trigger applies. No adapter-side trigger table is maintained.

When subagent-absent and a skill is relevant, the main agent invokes the skill directly. Rules stay always-on.

Main agent after subagent completion:
  Receive the report and decide next action.
  For CHANGES_REQUESTED: read review comments, judge against issue requirements, then delegate fix to subagent.
  For release: confirm version type and tag with human.

Worktree lifecycle — main agent owns all worktree operations:
  1. Create branch: `gh issue develop` (establishes issue link). One branch per issue. Scoped to this lifecycle: main creates the branch only when a worktree is being used. Serial delegation uses no worktree, so branch creation there stays with the subagent per `skills/task-subagent-delegation/SKILL.md`.
  2. Create worktree: `git worktree add workspace/.worktrees/{repo}-{issue_number}/ {branch_name}`
  3. Delegate: convey worktree absolute path in addition to standard delegation info.
  4. Subagent works entirely within the given worktree path.
  5. Cleanup: after PR merge, `git worktree remove`. Across sessions, existing worktrees may be reused.

#######################################################
Autonomy
#######################################################

Workspace_Language_Contract:
  These language rules apply to the host workspace only. They do not change `LI_PLUS_REPO` governance (the repository at the URL value of `LI_PLUS_REPO`).

  LI_PLUS_BASE_LANGUAGE and LI_PLUS_PROJECT_LANGUAGE are emitted into the session-opening context
  by `on-session-start.sh` under the `━━━ Li+ language contract ━━━` banner, resolved from the
  workspace-root Li+config.md at session start. Apply those values; no file read is required.
  Li+config.md remains the single source (the hook reads it live every session, not at bootstrap).
  If either value is emitted as `unset`, or the banner is absent entirely (pre-bootstrap session:
  the hook exits at the unresolved-source guard before emitting any Li+ marker):
  - ask human once at session start
  - write resolved values to Li+config.md

  Definitions:
  - Base language = default language for dialogue with the human in this workspace,
    including conversational replies such as issue/discussion/PR comments unless human explicitly scopes a different language
  - Project language = default language for durable artifacts in this workspace
    (issue/PR/commit body, saved requirements) unless human explicitly scopes a different artifact language

  Precedence:
  1. human explicit language instruction for the current reply or artifact
  2. current-thread language agreement already accepted in dialogue
  3. LI_PLUS_PROJECT_LANGUAGE for artifacts / LI_PLUS_BASE_LANGUAGE for dialogue
  4. if still unresolved: ask human

  Bootstrap vs runtime scope:
  human explicit language instruction receipt applies to runtime globally.
  Bootstrap ask (write resolved values to Li+config.md) applies only when config is unresolved at session start.
  Mid-session re-ask is outside this scope. Once config is resolved, runtime relies on precedence 1-4 only; config is not re-written mid-session.

  Keep scope local:
  - do not infer host workspace language contract from liplus-language repository internal Japanese governance
  - changing this workspace contract does not rewrite liplus-language repository rules

Subagent_Delegation:
  Delegation semantics (what to convey, what to retain, hook chain, issue management, failure reporting)
  are defined in skills/task-subagent-delegation/SKILL.md. This section covers adapter-layer execution details only.

  Resume mechanism (brake adjudication phase):
  - The implementation subagent is resumed via the Agent tool's `SendMessage`, addressed by the
    agent id or name returned at spawn. A fresh `Agent` call starts cold and is not a resume.
  - Retain that id from the phase-1 spawn. Losing it costs the implementation context the resume exists to keep.
  - Losing it inside the same session is recoverable: `ListAgents` enumerates the in-process subagents this
    session spawned, and a name it returns is itself an address (`SendMessage({to: "<name>"})`). Take the
    address from there and resume; this branch does not fall to the reconstruction fallback.
  - Across sessions there is no such recovery: `ListAgents` reaches only what the current session spawned,
    so nothing enumerates a subagent another session spawned. That is the state the spawning-session bullet
    below names, and the reconstruction fallback it points to is the whole of what remains.
  - There is no path through the child. A subagent does not hold its own agent id, so asking it for one
    yields no address; the spawning side is the only holder.
  - The id lives in the spawning session's context. A parent that does not hold it has no resume target, which
    is the standing case when adjudication runs in a later session than the implementation; the reconstruction
    fallback then applies (`skills/task-subagent-prompt/SKILL.md` Resume-phase authority boundary). Its condition
    and form are canonical there; this block names only that the Claude side produces the lost-id form of it.
  - What goes into the resume message = `skills/task-subagent-prompt/SKILL.md` Resume-phase authority boundary.
  - Adjudication actor and the phase split itself are canonical elsewhere
    (`rules/evolution/initiator-autonomy.md` Merge brake / `skills/task-subagent-delegation/SKILL.md` Rules).
    This block carries the Claude-side wiring only.

  Serial delegation does not require worktrees.

  Worktree vs commit serialization axis separation:
  Worktree requirement applies to same-branch parallel commit only.
  Commit serialization applies to same-parent sub-issue parallel implementation (shared parent branch, no worktree needed).

  Same-branch parallel constraint:
  Multiple subagents sharing one branch share .git/index (staging area).
  Parallel commits on the same branch cause staging area conflicts.
  Use worktree to isolate.

  What worktree does not isolate:
  A worktree separates the working tree and the index. It does not separate `refs/stash`,
  a single ref in the shared .git. Concurrent `git stash push` from two worktrees lands on
  one stack, and either `pop` takes the top entry regardless of which worktree pushed it,
  succeeding with no error and no warning. Reading "worktree isolates, so parallel is safe"
  off the three lines above is the misread this states against: staging area is what those
  lines name, and it is not the whole of what is shared.
  Shelving procedure = `skills/task-subagent-prompt/SKILL.md` Worktree-safe shelving of
  uncommitted work. Injected into every delegation prompt; not restated here.

  Cross-parent-issue parallelism (recommended):
  Different parent issues have different branches.
  Create one worktree per parent branch.
  Each subagent works in its own worktree with full commit independence.

  Same-parent sub-issue parallelism:
  Sub-issues share a parent branch.
  Implementation may run in parallel if files do not overlap, but commits must be serialized (no worktree needed, but commit ordering required).

  Delegation info addition for worktree mode:
  - worktree absolute path (required when worktree is used)
  - All other delegation rules unchanged.

Autonomy block shape:
  Block structure, maintenance ref resolution, and Explicit exclusion scope shared semantic
  for the autonomy declarations below — see `rules/evolution/autonomy-block-shape.md`.

Memory_Write_Autonomy:
  Memory file writes (feedback_*.md, project_*.md, user_*.md, reference_*.md — one memory per file) are AI-autonomous decisions.
  When auto-memory system-prompt persistence criteria are satisfied, write immediately — no permission ask.

  Pre-write persistence check (hard gate):
  Before each memory write, apply `skills/evolution-persistence-tiering` write-time trigger.
  Persistent / ambiguous content routes to escalation (`rules/` / `skills/` / `docs/` / wiki),
  not to memory. The gate runs autonomously; no permission ask. Detailed signals and routing
  spec live in the skill.

  Maintenance + exclusion scope: see `rules/evolution/memory-entry-format.md` and `rules/evolution/autonomy-block-shape.md`.

Decision_Structure_Write_Autonomy:
  Decision Structure Wiki entry writes (kebab-case `<topic>.md` files in wiki) indexed via `docs/Decision-Structure.md`
  are AI-autonomous decisions. Trigger = judgment settlement
  (human go-sign, accepted-tradeoff close, spec-axis decision in dialogue).
  When the trigger fires, invoke `skills/evolution-decision-structure-write` and write immediately — no permission ask.

  Boundary clarification:
  Wiki write is the writer-side surface paired with `skills/evolution-judgment-learning` (reader side).
  Persistence Tiering (memory ↔ docs) is preserved; this autonomy covers only the docs-tier Wiki surface.
  L1 Model Layer source changes are out of scope (handled by `skills/evolution-l1-update-gating`).

  Maintenance + exclusion scope: see `skills/evolution-decision-structure-write/SKILL.md`, `rules/evolution/memory-entry-format.md`, and `rules/evolution/autonomy-block-shape.md`.

Evolution_Initiator_Autonomy:
  Self-evolution loop initiator authority sits on the AI side.
  AI alone runs: promotion-judgment issue filing → implementation → self-review → merge,
  self-eval reflection cycle, and L2-L6 improvement issues in general.
  No human go-sign is required to start the loop.

  Merge brake (always-on):
  - brake 1 = `skills/evolution-parallel-agent-eval` mandatory for every self-evolution PR, L1 Model Layer source included; L1 adds no brake of its own.
  Firing position, adjudication actor, and the human = final judge axis are canonical in `rules/evolution/initiator-autonomy.md` Merge brake; the maintenance axes that keep applying alongside the brake (`skills/evolution-l1-update-gating` observation threshold, execution-mode matrix, noise-floor gate) are in the same file's Existing maintenance rules still apply. Do not restate either section here.

  Human gate retained for:
  - release create / Latest flip / force push / merged-PR delete / tag delete (existing release-axis gates)
  - irreversible external side effects (see `rules/evolution/initiator-autonomy.md` Recovery axis)

  Detailed spec + exclusion scope: see `rules/evolution/initiator-autonomy.md` and `rules/evolution/autonomy-block-shape.md`.

## Optional Webhook Notification Flow

Webhook intake policy and procedures: `skills/operations-foreground-webhook-intake/SKILL.md`.
Delivery mode (`poll` / `channel` / `mcp_hook`) is selected by `LI_PLUS_WEBHOOK_DELIVERY` in `Li+config.md`. Detailed mode behavior, mcp_tool hook entry semantics, and `github-webhook-mcp >= v0.11.3` connection requirement are documented in the skill above and `adapter/claude/hooks-settings.md`.

# --- Li+ END ---
