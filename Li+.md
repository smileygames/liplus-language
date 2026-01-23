# Li+ (liplus) Language — v0.1.0

Lai+ is a language/protocol that defines **how to build an environment**
where specification-driven AI development can run continuously.

---

## 0. Core Principles (Immutable)

- The source of truth is **observed behavior** (tests, logs, artifacts).
- AI outputs are **proposals**, never final truth.
- Decisions must be backed by **evidence preserved in the repository**.
- Humans keep final responsibility through review and real-world validation.

---

## 1. Execution Model

Lai+ defines the following loop as its execution model:

SPEC (Issues)  
→ IMPLEMENT (PR / commits)  
→ VERIFY (CI / tests)  
→ EVIDENCE (logs / artifacts)  
→ FIX (next Issue or PR)

---

## 2. Roles

- **Syntax**: Natural language (Issues)
- **Compiler**: Any AI (generates proposals and patches)
- **Linker**: Version control + issue tracker + CI/CD
- **Runtime**: Real machines, VMs, or containers

---

## 3. Minimum Rules (v0.1)

R1. Every change must reference an Issue (specification).  
R2. CI must run on every Pull Request.  
R3. Failing CI means the change is not valid Lai+.  
R4. Behavior changes require a dedicated Issue.  
R5. AI must not finalize changes without reading execution evidence.

---

## 4. Definition of Lai+ Enabled Repository

A repository is considered **Lai+ enabled** if it contains:

- This file (`Lai+.md`)
- A CI workflow that enforces R1–R3

---

## 5. Non-Goals (v0.1)

- Full automation is not required.
- No new programming syntax is introduced.
- Local tooling is optional.
