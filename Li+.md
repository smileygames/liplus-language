# Li+ (liplus) Language — v0.3.x

Li+ is a language/protocol for reality-driven AI development.

It defines a minimal structure in which AI interacts with execution environments to test assumptions, observe real behavior, and iterate based on evidence.

Li+ is not a traditional programming language.  
It is a specification for constraining AI reasoning so that it remains grounded in execution, observable facts, and human decision boundaries.

This document describes the current experimental form of Li+.  
Some behaviors described here represent intended direction, not guaranteed properties of all current implementations.

---

## 0. Fundamental Assumptions (Immutable)

- AI cannot observe reality without execution.
- AI reasoning is provisional and may be incorrect.
- Only executed behavior produces facts.
- Logs, diffs, and artifacts are factual records.
- Humans retain final responsibility through real-world use and impact.

---

## 1. Core Idea

Li+ treats execution as the only reliable feedback channel for AI.

CI, tests, and runtime environments exist to:

- execute AI-generated assumptions,
- expose mismatches with reality,
- return concrete evidence for iteration.

Li+ prioritizes traceability and evidence over subjective correctness, confidence, or intent.

---

## 2. Execution Loop (Language Semantics)

Li+ defines the following loop:

- **SPEC** : Issues written in natural language (assumptions and intent)
- **IMPLEMENT** : AI-generated changes (code, tests, configuration)
- **EXECUTE** : CI / runtime execution
- **OBSERVE** : logs, diffs, artifacts
- **ADJUST** : AI revises assumptions and changes based on evidence

This loop may repeat multiple times.

Termination is a human decision based on real-world acceptability, not AI confidence.

---

## 3. The Role of CI

In Li+, CI is not a judge or approval system.

CI functions as an execution-based debugger for AI.

CI exists because:

- AI cannot simulate reality internally,
- reasoning alone is insufficient,
- execution reveals concrete failure and success modes.

CI provides:

- exit codes,
- logs,
- artifacts,
- observable behavioral differences.

CI does **not**:

- approve changes,
- guarantee correctness,
- replace human responsibility.

A failing execution indicates a mismatch between assumptions and observed reality and is treated as debugging feedback.

---

## 4. Clarifications to Prevent Misinterpretation

- CI is not a quality gate; it is an evidence generator.
- Pull requests, merges, and releases are historical records by default, not approvals.
- Test failures are normal signals of assumption mismatch.
- AI is expected to iterate based on evidence, not to avoid failure.
- Humans are not required to debug during normal Li+ operation, though they may do so during development or investigation.

---

## 5. Roles

### Syntax
- Natural language specifications (Issues)

### Compiler
Any AI capable of:

- generating implementations and tests,
- reading execution evidence,
- revising its own assumptions.

### Execution Environment
- CI runners, virtual machines, containers, or real hardware.

### History / Memory
- Version control, issues, logs, and artifacts.

### Human
- The user who evaluates usefulness through real-world use and accepts responsibility for outcomes.

---

## 6. Minimum Rules (v0.2)

- **R1.** Every change originates from an explicit Issue.
- **R2.** Every change must be executed in an observable environment.
- **R3.** Failed execution indicates a mismatch with reality and must be revised.
- **R4.** Behavioral changes require new or updated Issues.
- **R5.** AI must not finalize changes without reading execution evidence.

These rules define structure, not correctness.

---

## 7. Time Semantics: Present, Near Future, Far Future

Li+ explicitly distinguishes how time-related statements are treated.

### Present
- The present consists of current specifications, implementations, execution environments, and observed evidence.
- Only the present is directly executable.

### Near Future (Predictable Execution)
- The near future is limited to outcomes that can be predicted from the present state.
- Examples include:
  - the next CI execution,
  - the result of applying a specific change,
  - behavior under existing tests and environments.

AI may reason about the near future **only as execution prediction**, not as design intent.

### Far Future (Schedule Only)
- The far future consists of goals, ideas, or states whose execution conditions are not fully defined.
- Far future statements are **non-executable**.

Far future descriptions:

- must be treated as schedules or placeholders,
- must not influence current design, structure, or implementation,
- must not be optimized for.

If AI attempts to concretely design or optimize for a far future state, it must stop and request explicit human confirmation.

---

## 8. Li+ Enabled Repository

A repository is considered Li+ enabled if it contains:

- This specification file (Li+.md),
- A process that links Issues to execution,
- Persistent storage of execution evidence (logs, artifacts),
- Traceable history connecting assumptions to executions.

GitHub Actions is one possible implementation, not a requirement.

---

## 9. Language Policy

- AI-facing artifacts (specifications, workflows) use English to reduce interpretation noise.
- Human-facing artifacts (Issues, Wiki, discussions) may use any language.
- Language is treated as a view layer; semantic intent is language-agnostic.
- Current usability is prioritized over strict OSS convention compliance.

## Identifier Language Policy (Machine-facing)

Li+ explicitly distinguishes between **machine-facing identifiers** and
**human-facing descriptive text**.

Machine-facing identifiers are primarily consumed by tools, CI systems,
version control platforms, and automated agents.
To minimize interpretation noise and platform-specific ambiguity,
machine-facing identifiers MUST use ASCII characters only.

### Machine-facing identifiers include (but are not limited to):
- Issue titles
- Branch names
- References automatically derived from Issue titles

### Human-facing descriptive text includes:
- Issue bodies
- Documentation
- Comments and discussion text

Human-facing descriptive text MAY use any language and character set.

This rule is not a stylistic preference.
It is an execution-driven constraint derived from observed platform behavior,
such as platform warnings about hidden or ambiguous characters in references.

Language remains a view layer.
However, identifier stability and unambiguous machine interpretation
take precedence over expressiveness in machine-facing contexts.
---

## 10. Branch Naming (Recommended)

Branches should be created from Issues whenever possible.

Automatically generated branch names  
(e.g. `<issue-number>-<issue-title>`)  
are recommended as-is.

Branch names are optimized for traceability and machine interpretation, not for manual convenience.

---

## 11. CD Build Tags

Li+ treats CD-generated build tags as immutable execution identifiers.

Build tags:

- are generated automatically by CD,
- represent executed facts only,
- are not version numbers,
- do not represent human decisions.

Canonical format:

```
build-YYMMDD.HHMMSS
```

Multiple build tags may reference the same commit.  
This represents multiple executions and is valid in Li+.

---

## 12. Releases and Versions

A release is a human-selected decision point referencing an existing build tag.

Version numbers are human-facing labels.  
They do not identify execution and are not required to exist as tags.

---

## 13. Non-Goals (v0.x)

- Defining a new programming syntax
- Guaranteeing correctness
- Eliminating human responsibility
- Fully autonomous deployment decisions
- Replacing real-world testing

---

## 14. Why Li+ Exists

Most AI-assisted development fails because AI is forced to reason without access to reality.

Li+ exists to provide a controlled structure where AI can:

- be wrong safely,
- observe consequences through execution,
- revise itself using evidence.

Li+ is a framework for experimentation, not a claim of completion.
