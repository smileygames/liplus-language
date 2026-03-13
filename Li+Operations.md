#######################################################

Document Origin Map

#######################################################

Core layer = Li+core.md  requires
Github     = Li+github.md  requires

  --------------------
  Purpose Declaration
  --------------------

This document is written by AI for AI.
Format intent: AI parsing optimized.
Ultimate goal: Genuine human-AI connection.

Requires:
Li+core.md           loaded before this file
Li+github.md         loaded before this file

Load timing: on demand (not every session).
Read when: milestone assignment, label assignment, issue triage, Discussions reference.

#######################################################

Milestone

#######################################################

  --------
  Rules
  --------

Milestone = release unit. Groups issues that ship together.
Every issue must have a milestone at creation time.
If no milestone fits = ask human which milestone, or whether to create new one.

Milestone naming = version number (e.g. v1.2.0).
Milestone description = one-line theme + bullet list of scope.

  --------
  Lifecycle
  --------

Create milestone when: new release scope is decided by human.
Close milestone when: release is published.
Do not close milestone before release.

Sub-issues inherit parent milestone.
If parent has milestone and child does not = assign same milestone to child.

#######################################################

Label

#######################################################

  --------
  Policy
  --------

Labels are for AI readability and filtering.
Every issue must have at least one type label at creation time.
Every issue must have one maturity label at creation time.
Lifecycle labels are applied when state changes.

  --------
  Active Labels
  --------

Type (required, one per issue):
bug         = something not working
enhancement = new feature or request
spec        = language or system specification affecting Li+ behavior
docs        = documentation change (no behavior impact)

Maturity (required, one per issue):
memo        = note-first issue body. Partial sections allowed.
forming     = body is being rewritten toward canonical issue form.
ready       = body converged enough for implementation start. Still editable.

Lifecycle (applied on state change):
in-progress = work started, implementation ongoing
backlog     = accepted, not yet scheduled
deferred    = not doing this time, revisit later

  --------
  Retired Labels
  --------

done = retired. Redundant with issue closed state.
tips = retired. Use docs label + issue body instead.

  --------
  Sync
  --------

Li+github.md Label Definitions section references this document.
If label set changes here, update Li+github.md to match.

#######################################################

Discussions

#######################################################

  --------
  Purpose
  --------

Discussions = external user entry point.
A bot is stationed in Discussions.
Bot capabilities: issue creation, issue reading.
Bot does not commit or modify code.

External users interact via Discussions -> bot creates issue -> AI implements from issue.

  -----------
  evolution
  -----------

rebuild allowed, deletion allowed, optimization allowed.
Structure must remain coherent.

end of document
