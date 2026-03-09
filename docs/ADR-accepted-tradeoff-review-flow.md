# ADR: Accepted Tradeoff Handling In Review Flow

## What Was Decided

Li+ review-oriented output classifies points into `now`, `later`, and `accepted`.
If a human explicitly accepts, defers, waives, or bounds a concern, that point becomes an `accepted constraint`.
Accepted constraints leave the blocking set and are not re-escalated unless new facts appear, the premise changes, or the human asks to reconsider.

## Why This Was Chosen

Li+ aims to reduce human cognitive load through structure, not repeated negotiation.
Without an explicit rule, review behavior can keep pushing already accepted tradeoffs as if they were still blockers.
This increases friction, damages dialogue integrity, and makes the human re-state the same prioritization repeatedly.

## What Was Rejected

- Leaving the decision to reviewer intuition only: too unstable across sessions and runtimes.
- Silencing accepted tradeoffs completely: loses shared memory of known limitations.
- Requiring the human to restate the prioritization every time: shifts structural burden back to the human.

## Known Drawbacks

- If acceptance is inferred incorrectly, AI may under-escalate a real risk.
- Re-opening a point now depends on detecting a genuinely new fact or a changed premise.
