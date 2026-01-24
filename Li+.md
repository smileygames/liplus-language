# Li+ (liplus) Language — v0.2.x

Li+ is a language/protocol for **reality-driven AI development**.
It defines how AI interacts with execution environments to continuously
align its assumptions with observed behavior.

Li+ is not a traditional programming language.
It is a specification for building a loop where AI can be wrong safely,
observe the consequences, and correct itself using evidence.

---

## 0. Fundamental Assumptions (Immutable)

- AI cannot observe reality without execution.
- AI reasoning is provisional and must be validated by evidence.
- Only executed behavior produces facts.
- Logs, diffs, and artifacts are facts.
- Humans keep final responsibility through real-world use and validation.

---

## 1. Core Idea

Li+ treats execution as the only reliable feedback channel for AI.

CI, tests, and runtime environments exist to:
- execute AI-generated assumptions,
- observe mismatches with reality,
- return evidence to AI for iteration.

Li+ is designed to maximize **traceability** and **evidence**, not to
maximize subjective confidence.

---

## 2. Execution Loop (Language Semantics)

Li+ defines the following loop:

```
SPEC : Issues written in natural language (assumptions and intent)
IMPLEMENT: AI-generated changes (code, tests, config)
EXECUTE : CI / runtime execution
OBSERVE : logs, diffs, artifacts
ADJUST : AI revises assumptions and changes based on evidence
```

This loop repeats until observed behavior is acceptable in real usage.

---

## 3. The Role of CI (Critical)

In Li+, CI is **not** a judge.

CI is an **execution-based debugger for AI**.

Why CI exists:
- AI cannot simulate reality internally.
- AI needs concrete failure modes and concrete success signals.
- Silent success and silent failure are both meaningful signals.

What CI provides:
- exit codes,
- logs,
- artifacts,
- behavioral diffs.

What CI does NOT do:
- approve changes,
- judge correctness,
- replace human responsibility.

A failing CI run indicates a mismatch between AI assumptions and observed reality,
and must be treated as debugging feedback.

## 3.1 Common Misconceptions

- CI is not a judge or approval system.
  It exists solely to execute assumptions and return observable evidence to AI.

- Humans are not expected to debug.
  Humans validate usefulness through real-world use and bear final responsibility.

- Pull requests, merges, and releases are not approvals by default.
  They are historical records of executed states.

- Test failures are not errors to be avoided.
  They are normal signals indicating a mismatch between assumptions and reality.

---

## 4. Roles

- **Syntax**  
  Natural language specifications (Issues)

- **Compiler**  
  Any AI capable of:
  - generating implementations and tests,
  - interpreting execution evidence,
  - revising its own assumptions.

- **Execution Environment**  
  CI runners, VMs, containers, real machines

- **History / Memory**  
  Version control, issues, logs, artifacts

- **Human**  
  The final user of the result (decides usefulness through real-world use)

---

## 5. Minimum Rules (v0.2)

R1. Every change must originate from an Issue (explicit assumption).  
R2. Every change must be executed in an environment observable by AI.  
R3. Failed execution indicates a mismatch with reality and must be revised.  
R4. Behavioral changes must be expressed as new or updated Issues.  
R5. AI must not finalize changes without reading execution evidence.  

---

## 6. Li+ Enabled Repository

A repository is considered Li+ enabled if it contains:

- This specification file (`Li+.md`)
- A workflow or process that enforces Issue linkage and execution evidence
- Persistent storage of execution evidence (logs, artifacts)
- A traceable history linking assumptions to executions

GitHub Actions is one implementation option — not a requirement.

---

## 7. Language Policy

- AI-facing artifacts (e.g., this specification, workflows) use English to minimize interpretation noise.
- Human-facing artifacts (e.g., Issues, Wiki) may be written in Japanese or any language.
- Language is treated as a view layer; semantic intent is language-agnostic.
- Usability is prioritized at the current stage; OSS conventions and third-party perspectives are secondary for now.

---

## 8. Branch Naming (Recommended)

Branches should be created from Issues whenever possible.

When using GitHub's issue-to-branch feature, the automatically generated
branch name (e.g. `<issue-number>-<issue-title>`) is recommended as-is.

Branch names represent implementation scope and are optimized for traceability
and machine interpretation rather than manual typing.

---

## 9. Non-Goals (v0.x)

- Defining a new programming syntax
- Guaranteeing correctness
- Eliminating human responsibility
- Full automation of deployment decisions
- Replacing real-world testing

---

## 10. CD Build Tags

Li+ treats CD-generated build tags as **immutable execution identifiers**.

Build tags:
- are generated automatically by CD,
- represent executed facts only,
- are not version numbers,
- do not represent human decisions.

The canonical build tag format is:

```
build-YYMMDD.HHMMSS
```

This format is time-ordered, collision-resistant in distributed environments,
and suitable as a stable reference to executed behavior.

Multiple build tags may point to the same commit.
This represents multiple executions of the same state and is valid in Li+.

---

## 11. Releases and Versions

A release in Li+ is created by a human by selecting an existing build tag.
It represents a **decision point**, not correctness or completeness.

Version numbers are treated as **view-level labels for humans**.
They are not execution identifiers and are not required to exist as tags.

---

## 12. Why Li+ Exists

Most AI-assisted development fails because AI is forced to reason without reality.

Li+ exists to give AI a controlled way to be wrong,
observe the consequences through execution,
and correct itself using evidence.
