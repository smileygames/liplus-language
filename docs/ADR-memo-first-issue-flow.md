# ADR: Memo-First Issue Flow

## What Was Decided

Li+ issue flow now treats the issue body as the current requirements snapshot.
An issue may start as a memo with only the headings needed at that moment.
AI creates the issue once a dialogue topic becomes a durable work unit, without requiring an explicit human phrase such as "make issue".
As dialogue progresses, AI rewrites the body so the latest accepted understanding is readable without replaying comment history.
When an issue becomes implementable, its body converges to `purpose`, `premise`, `constraints`, and `completion condition`.
Even after convergence, the issue remains editable as a living requirements document.
Requirement maturity is tracked separately from timing through the labels `memo`, `forming`, and `ready`.

## Why This Was Chosen

Li+ aims to behave as a dialogue compiler, not as a form-filling agent.
Requiring the canonical four-part structure at issue creation makes early dialogue too heavy and breaks the path from casual conversation to structured work.
Requiring the human to explicitly request issue creation would move activation burden back to the human and reduce the system to a manual agent workflow.
Using comments as the main memory source also increases read cost because AI must replay history to recover the current state.
Rewriting the issue body keeps the working context small while preserving a clear convergence target.

## What Was Rejected

- Requiring every issue to fully match the canonical four-part structure at creation: too rigid for early-stage dialogue.
- Using comment threads as the primary requirements record: too expensive to reload and too easy to drift.
- Reusing lifecycle labels (`in-progress`, `backlog`, `deferred`) to express requirement maturity: mixes timing with convergence and makes state unclear.

## Known Drawbacks

- Rewriting the body can discard nuance if unresolved points are not preserved explicitly.
- History becomes less visible inside the issue itself, so commit messages and docs remain important as external memory.
- `ready` still depends on AI judgment, so premature convergence remains possible when the dialogue signal is weak.
