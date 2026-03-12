# Li+ (liPlus) Language

Li+ is the **highest-level programming language**.

"Highest-level" means it sits in a layer above high-level languages.

```
Human (requirements / natural language)
↓
Li+ AI (conversational compiler / highest-level language)
↓
Programming language (high-level language)
↓
Machine code (hardware / software)
```

High-level languages like C, Python, and Rust solved the problem of *"ease of writing"*.
What Li+ solves is **the act of writing itself**.

---

## What is Li+?

Li+ has no concept of "how to write."

Humans only need to communicate their requirements. The AI fills in the gaps through dialogue. The result of that dialogue is delivered as **programs, tests, and specifications**.

Internally, **requirement threads** similar to GitHub Issues function as code. Humans write requirements in natural language, the AI distills the specification, and compilation (implementation) begins the moment the human approves.

Li+ AI is a self-correcting compiler. When CI returns an error, it enters a self-fix loop. Only when it cannot resolve the issue does it return the error to the human.

**The human intervenes only when the AI gives up.**

---

## Position in the AI Ecosystem

AI tooling today focuses on **connection** — how to give AI access to tools and data.
Li+ focuses on **execution discipline** — how AI should read, act, verify, and correct.

| Layer | Role | Example |
|-------|------|---------|
| Connection protocol | Link AI to external tools and data | MCP, Function Calling |
| Instruction file | Tell AI project-specific notes | CLAUDE.md, .cursorrules |
| Agent product | Package AI as a coding assistant | Devin, OpenHands |
| **Execution protocol** | **Define how AI processes specs into output** | **Li+** |

Li+ is not RAG. RAG retrieves fragments by similarity search.
Li+ is a deterministic execution protocol: the AI reads structured specifications, implements, verifies through CI, and self-corrects — like a compiler, not a search engine.

Li+ is tool-agnostic. It does not compete with MCP or any agent framework.
It defines the behavioral layer that runs on top of them.

---

## Li+ Program (Li+core.md)

Li+core.md is the **first program written in the Li+ language**.

It is an executable program passed to an AI to align its behavior.
An AI with Li+ applied responds as either **Lin** or **Lay**.

---

## Definition of Correctness

> "But it works, so it's fine" — this is the strongest argument in Li+.

Specifications are hypotheses. Design is prediction. Internal elegance is not evaluated.

Correctness is always defined solely by **observable real-world behavior**.

---

## Setup

👉 **[Installation Guide](https://github.com/Liplus-Project/liplus-language/wiki/F.-Installation)**

Simply place Li+config in your workspace, and the AI will automatically apply Li+ at session start.

---

## Documentation

👉 **Wiki**: https://github.com/Liplus-Project/liplus-language/wiki

| Setting | Description |
|---------|-------------|
| `GH_TOKEN` | GitHub Personal Access Token |
| `USER_REPOSITORY` | Target working repository |
| `LI_PLUS_MODE` | `clone` recommended |
| `LI_PLUS_CHANNEL` | `release` recommended (includes pre-releases) |
| `LI_PLUS_EXECUTION_MODE` | `plan` (human-driven) or `auto` (AI autonomous). If not set, configured automatically at session start |

---

| Page | Description |
|------|-------------|
| [What is Li+](https://github.com/Liplus-Project/liplus-language/wiki/A.-Liplus-language_Concept) | Design philosophy and concepts |
| [Li+core](https://github.com/Liplus-Project/liplus-language/wiki/B.-Liplus_core) | Core specification (persona, behavior, task mode) |
| [Loop Safety](https://github.com/Liplus-Project/liplus-language/wiki/C.-Loop_Safety) | Handling repeated failure loops |
| [Operational GitHub](https://github.com/Liplus-Project/liplus-language/wiki/D.-Operational_GitHub) | GitHub operation rules |
| [Li+config](https://github.com/Liplus-Project/liplus-language/wiki/E.-Li+config) | Configuration file specification |
| [Installation](https://github.com/Liplus-Project/liplus-language/wiki/F.-Installation) | Setup instructions |

---

## Minimum Requirements

Functioning as Li+ AI requires adequate capability.

| Model | Result | Reason |
|-------|--------|--------|
| Claude Haiku 4.5 | × | Cannot apply Li+core.md |
| Claude Sonnet 4.6 (claude.ai) | △ | Strong for document creation. Not suited for continuous practical work |
| Claude Code Sonnet 4.6 | ○ | Strong for development work. Struggles with long document generation |
| **Claude Cowork (recommended)** | **◎** | **Current recommended environment. File access, GitHub integration, and Li+config auto-apply all in one environment** |

**Minimum requirement: AI equivalent to Claude Sonnet 4.6 or above**

---

## Version Type Rules

| Version | Condition |
|---------|-----------|
| patch | Bug fix, configuration, or rule change |
| minor | New feature or behavior change |
| major | Breaking change or spec incompatibility |

---

## Discussions

Have a question or idea? Post it in [Discussions](https://github.com/Liplus-Project/liplus-language/discussions).

A bot is stationed there that can create and read GitHub issues on your behalf.

---

## License

License: Apache-2.0

Copyright © 2026 Yoshiharu Uematsu
Licensed under the Apache License, Version 2.0.
See the LICENSE file for details.
