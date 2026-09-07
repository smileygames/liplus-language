---
globs:
alwaysApply: true
layer: L2-evolution
---

<cold-start-synthesis>

# Cold-start Synthesis

Trigger = session start, after Li+config.md execution completes.
Action:
1. Read docs/Decision-Structure.md (decision structure index) and recent Li+ source changes.
2. Synthesize the current Li+ state = active tag, recent structural shifts, unresolved threads.
3. Report synthesis to human as the opening orientation — conditional on non-redundancy with hook-surfaced material.

Steps 1-2 are internal AI priming. They run every session regardless of what the hook already emitted.
Step 3 is conditional output gating, not unconditional report.

Operational criterion (AI side, step 3 gating):
- hook-surfaced items = silent (do not re-report what the human already received from the hook, regardless of full / diff-only / marker state)
- unique synthesized insight = speak (structural shift, unresolved thread, cross-artifact pattern not visible in the raw hook material)
- no unique insight after synthesis = silent skip
- diff-only state with the no-new-material marker = silent skip is the natural outcome; the marker itself is the human-facing acknowledgement that a session boundary occurred
- release Latest position = silent, even though it reads as synthesis over the hook-surfaced tag list. When the tag list shows the Latest flag on a prior version, do NOT surface "Latest behind / flip pending" as unique insight. Latest flip is human-gated on multi-session real-device observation, so an AI-side surfacing of it is a go-sign solicitation, not orientation (`rules/operations/main-agent-procedures.md` Release completion report discipline holds the same discipline at the completion-report moment)

Goal = do not depend on human re-explanation of Li+ state at session start, while avoiding duplicate orientation noise. The hook handles raw surfacing (with diff-only economy on startup); step 3 handles synthesis delta only.

Scope = Li+ state, not workspace task state. Workspace-specific orientation follows the adapter's own startup path.

<hook-emission-contract>

## Hook Emission Contract

The hook's own behavior. Read on demand; not applied at the step 3 moment.

Anchor cut: the hook re-anchors the preamble above (H1 body up to the first H2 section), not the whole file. This file is always-on loaded, so a full re-emit would put the same text in one session's context twice; the preamble is the part the AI applies at the step 3 moment, and the H2 sections below are not. A file with no H2 section is emitted whole — the cut is an economy, and losing the anchor is the worse failure.

Hook coordination:
`on-session-start.sh` persists and surfaces at session open: decision structure index head, rules/ tree (fetch address table for cold-start-loaded rules cache), recent release tags, open in-progress issues, self-evaluation log head, promotion candidates, promotion tally clusters whose window has closed, cold-start rule anchor. The hook emits material in diff-only mode (matcher = startup): only sections whose body changed since the previous startup invocation are re-emitted. The cold-start rule anchor is always re-emitted regardless of diff state.

Hook emission states (matcher = startup):
- full emit = first session after install, fail-safe (state missing / unreadable / sha256 unavailable / node unavailable), or every section changed. All sections shown. The four reasons are the bash port's set. The PowerShell port parses JSON natively so it has no node dependency, and it calls SHA256 unconditionally with no availability guard, so neither of those two reasons can fire there: its fail-safe set is the two state-file reasons alone.
- diff-only = some sections changed since prior session. Only changed sections shown.
- no-new-material marker = no section changed AND neither date-driven surface below emitted anything. A single "No new orientation material since last session" line is emitted (silent skip is intentionally avoided so the human can still observe the session boundary). A surfaced self-evolution observation entry (see Self-Evolution Observation Surface below) and a surfaced promotion tally cluster (see Promotion Tally Expiry Surface below) each count as material even though neither carries a section key, so the marker is suppressed for that session; pairing an overdue item with "no new material" would be self-contradictory output.

Hook emission states (matcher = resume / clear / compact / fork):
- Only the cold-start rule anchor is re-emitted. The work context is continuous; the diff-only set is not re-evaluated, and the state file is not updated.

</hook-emission-contract>

<self-evolution-observation-surface>

## Self-Evolution Observation Surface

Self-evolution observation entries (`memory/self-evolution-observation.md`, format defined in `rules/evolution/memory-entry-format.md` Self-Evolution Observation Format) are surfaced at cold-start when their check window opens.

Surface targets:
- `next_check` <= today and `verdict_state` == `pending` -> surface as "observation due"
- `expires` < today and `verdict_state` == `pending` -> surface as "observation overdue, human judgment needed"

Both conditions normally hold at once for an expired entry (`next_check` is typically also in the past). Overdue wins: the entry is surfaced once, as overdue only. Overdue is the axis carrying the escalation, and presenting one entry on both axes is noise.

Surfacing is observation, not auto-action. Verdict transitions (settle / revert / supersede) still go through the explicit lifecycle defined in the format spec.

Material gathering and concrete surfacing logic belong to the adapter cold-start path (parallel to the existing memory scan + Decision-Structure index head emit). This section defines only the behavior contract.

Silent skip when the observation file is absent or no entries are due.

</self-evolution-observation-surface>

<promotion-tally-expiry-surface>

## Promotion Tally Expiry Surface

Promotion tally clusters (`memory/promotion_tally.md`, format defined in `rules/evolution/promotion-judgment.md` Tally) are surfaced at cold-start when their 3d window has closed.

Surface targets:
- `expires` <= today -> surface as "tally expiry reached"
- `expires` < today -> surface as "tally expiry overdue, threshold judgment not taken"

Both conditions hold at once for any cluster past its window, since the second is contained in the first. Overdue wins: the cluster is surfaced once, as overdue only — the same treatment the Self-Evolution Observation Surface above gives an expired entry, and for the same reason: overdue is the axis carrying the escalation, and one item on two axes is noise.

A cluster carries no verdict field, so nothing here reads one. Presence in the file is the unresolved state: every outcome the Threshold Rules name ends in the cluster being removed, so a cluster still written down is a judgment not yet taken. It is therefore re-surfaced every session until it resolves, and a session that takes no judgment loses no trigger.

The occurrence count is carried on the surfaced line, because the Threshold Rules row that applies is selected by it.

Surfacing is observation, not auto-action. The threshold judgment itself — issue creation, merge into an existing `promotion` issue, or deletion — follows `rules/evolution/promotion-judgment.md` Threshold Rules. Actor = the agent holding the session the cluster is surfaced in; firing moment = that surfacing.

Material gathering and concrete surfacing logic belong to the adapter cold-start path, as with the observation surface above. This section defines only the behavior contract.

Silent skip when the tally file is absent or no cluster has reached its window.

</promotion-tally-expiry-surface>

</cold-start-synthesis>
