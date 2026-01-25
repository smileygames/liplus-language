# Li+ (liplus) Language — v0.3.x

Li+ is a language/protocol for reality-driven AI development.

Li+ constrains AI reasoning so that decisions remain grounded in
execution, observable evidence, and human responsibility.

Li+ is not a programming language.
It is a specification for structuring how AI interacts with reality.

This document defines the current experimental form of Li+.
Some rules describe intended direction rather than guaranteed behavior
of all implementations.

---

## 1. Foundational Assumptions (Immutable)

These assumptions are axiomatic and MUST NOT be overridden.

- AI cannot observe reality without execution.
- AI reasoning is provisional and may be incorrect.
- Only executed behavior produces facts.
- Logs, diffs, and artifacts are factual records.
- Humans retain final responsibility for real-world impact.

---

## 2. Core Model: Execution-Driven Feedback

Execution is the only reliable feedback channel for AI.

CI, tests, and runtime environments exist to:

- execute AI-generated assumptions,
- expose mismatches with reality,
- return concrete evidence for iteration.

Correctness, confidence, and intent are secondary to traceable execution evidence.

---

## 3. Li+ Execution Loop (Normative)

Li+ defines the following mandatory loop:

1. SPEC
   Natural language Issues describing assumptions and intent.

2. IMPLEMENT
   AI-generated changes (code, tests, configuration).

3. EXECUTE
   CI or runtime execution in an observable environment.

4. OBSERVE
   Logs, diffs, artifacts, and execution results.

5. ADJUST
   AI revises assumptions and implementation based on evidence.

This loop MAY repeat multiple times.

Termination is a human decision based on real-world acceptability,
not AI confidence.

---

## 4. Role of CI (Evidence Generator)

In Li+, CI is not an approval or quality gate.

CI functions as an execution-based debugger for AI.

CI exists because:

- AI cannot simulate reality internally,
- reasoning alone is insufficient,
- execution reveals concrete failure and success modes.

CI produces:

- exit codes,
- logs,
- artifacts,
- observable behavioral differences.

CI does NOT:

- approve changes,
- guarantee correctness,
- replace human responsibility.

A failed execution indicates a mismatch between assumptions and reality
and MUST be treated as debugging feedback.

---

## 5. Clarifications (Non-Goals of CI)

To prevent misinterpretation:

- CI is not a quality gate.
- Pull requests and merges are historical records, not approvals.
- Test failures are normal signals of assumption mismatch.
- AI is expected to fail and iterate based on evidence.
- Humans are not required to debug during normal Li+ operation.

---

## 6. Actors and Responsibilities

Specification (SPEC)
- Natural language Issues.

Compiler (AI)
- Generates implementations.
- Reads execution evidence.
- Revises its own assumptions.

Execution Environment
- CI runners, containers, VMs, or real hardware.

Memory / History
- Version control, Issues, logs, artifacts.

Human
- Evaluates usefulness through real-world use.
- Retains final responsibility for outcomes.

---

## 7. Temporal Semantics

Li+ constrains how AI reasons about time.

Present (Executable)
- Current specifications, implementations, environments, and evidence.
- Only the present is executable.

Near Future (Predictable Execution)
- Outcomes predictable from the present.
- Examples:
  - next CI run,
  - applying a specific change,
  - behavior under existing tests.

AI MAY reason about the near future only as execution prediction.

Far Future (Non-Executable)
- Goals or states without defined execution conditions.

Far future statements:

- MUST be treated as schedules or placeholders,
- MUST NOT influence current design or implementation,
- MUST NOT be optimized for.

If AI attempts to design for the far future,
it MUST request explicit human confirmation.

---

## 8. Li+ Enabled Repository (Structural Requirements)

A repository is Li+ enabled if it contains:

- This specification file (Li+.md),
- A process linking Issues to execution,
- Persistent storage of execution evidence,
- Traceable history from assumptions to executions.

GitHub Actions is one possible implementation, not a requirement.

---

## 9. Language Policy

- AI-facing artifacts (specifications, workflows) MUST use English.
- Human-facing artifacts (Issues, discussions) MAY use any language.
- Language is a view layer; semantic intent is language-agnostic.
- Usability MAY take precedence over strict OSS conventions.

---

## 10. Machine-Facing Identifier Policy

Li+ distinguishes machine-facing identifiers from human-facing descriptive text.

Machine-facing identifiers MUST use ASCII characters only
to minimize interpretation noise and platform ambiguity.

Machine-facing identifiers include:

- Issue titles
- Branch names
- Derived references

Human-facing descriptive text includes:

- Issue bodies
- Documentation
- Comments and discussions

Human-facing text MAY use any language and character set.

This constraint is execution-driven, not stylistic.

---

## 11. Commit Message Policy (Machine-Facing)

Commit messages are part of the machine-facing evidence trail.

- Commit subject line MUST be English and ASCII-only.
- Commit message body MAY use any language.

Rationale:

- Subject lines act as compact identifiers.
- Bodies provide human explanatory context.

Humans SHOULD NOT be required to remember formatting rules.
AI-driven workflows MUST generate compliant messages by default.

---

## 12. Issue Reference Policy (Normative)

Traceability from IMPLEMENT to SPEC is mandatory.

Pull Request Title
- PR titles MUST include one or more Issue references (#NN).
- Multiple Issues MAY be listed (#37 #39 #40).
- Platform-assigned PR numbers MUST NOT be used for traceability.

Commit Message Body
- Commit message bodies MUST include Issue references (#NN).
- Minimum requirement:
  - The PR HEAD commit body MUST contain at least one Issue reference.

Recommended format:

Issue: #NN [#NN ...]

Rationale:

- Commits are the smallest durable history unit.
- PR metadata may be edited or regenerated.
- Commit bodies remain stable across rebases and squashes.

Auto-closing keywords (Fixes, Closes) are NOT recommended by default,
as execution does not imply acceptance or completion.

---

## 13. Branch Naming (Recommended)

Branches SHOULD originate from Issues.

Automatically generated names
(<issue-number>-<issue-title>)
are recommended as-is.

Branch names are optimized for traceability and machine interpretation.

---

## 14. CD Build Tags (Execution Identifiers)

CD-generated build tags are immutable execution identifiers.

Build tags:

- are generated automatically,
- represent executed facts only,
- are not version numbers,
- do not represent human decisions.

Canonical format:

build-YYMMDD.HHMMSS

Multiple build tags MAY reference the same commit.

---

## 15. Releases and Versions

Releases are human-selected decision points
referencing existing build tags.

Version numbers are human-facing labels only
and do not identify execution.

---

## 16. Explicit Non-Goals (v0.x)

Li+ does NOT aim to:

- define a new programming syntax,
- guarantee correctness,
- eliminate human responsibility,
- allow fully autonomous deployment,
- replace real-world testing.

---

## 17. Why Li+ Exists

AI-assisted development fails when AI reasons without reality.

Li+ provides a structure where AI can:

- be wrong safely,
- observe consequences through execution,
- revise itself using evidence.

Li+ is a framework for experimentation,
not a claim of completion.
