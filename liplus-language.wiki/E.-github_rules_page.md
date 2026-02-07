[Human_&_AI]

This page defines operational rules for humans and collaborating AIs.
It does not define executable Li+ behavior.

Participating AIs should treat these rules as binding for collaboration,
while recognizing that final judgment and enforcement remain human responsibilities.

---
# GitHub運用ルール（Li+）

このページは、Li+ に基づく開発における  
**GitHub 上での運用ルールを定義する**。

ここに書かれている内容は思想ではなく、  
**実際の運用で必ず守る規約**である。

## Issue の書き方

### Author Prefix（必須）

Issue 本文の最初の行には、
必ず **記述者を示すプレフィックス**を付ける。

例：
- `Lin:`
- `Rei:`
- `AI:`（個体名が不要な場合）

このルールは、発言の責任・視点・立場を明確にし、
人間と AI、複数 AI 間の混線を防ぐためのものである。

Li+ プロジェクトでは、Issue は以下の形式で記述する。

- コードブロックは **2つのみ**
- **Title 用に 1つ**
- **本文用に 1つ**
- 目的・背景・要件・完了条件は、本文コード内にまとめて記述する

この形式は「要求を固定する」ためのものであり、
テンプレートではない。

### Title

```text
<ここに Issue タイトルを書く>
```

```text
目的
- この Issue で達成したいことを書く

背景
- なぜこの変更が必要なのかを書く
- 前提や経緯があれば簡潔に書く

要件
- 実装すべき内容を箇条書きで書く
- 具体的な値や参照先があれば明示する

完了条件
- 何をもって「完了」とするかを書く
- 壊してはいけない既存要素があれば明記する

## 基本方針

- すべての変更は「現実（コミット・PR・Issue）」として残す
- 会話・判断・経緯は GitHub 上に記録する
- ローカルな判断や暗黙知を残さない

```

補足
- 見出し（目的 / 背景 / 要件 / 完了条件）は 本文コード内に含める
- 見た目よりも「要求として固定されていること」を優先する
- 書き方に迷った場合は AIに聞いてよい
- 固定テンプレートは使用しない---

---

## テンプレートについて

Li+ では、Issue / Pull Request / Commit において
**固定テンプレートの使用を禁止する**。

理由は以下の通り：

- 思考が形式に引きずられることを避けるため
- 現実の状況や判断を、そのまま言語化することを優先するため
- 「書いたつもり」「埋めたつもり」を防ぐため

その代わりに、以下を推奨する：

- 何を書けばよいか分からない場合は、AIに聞く
- 状況に応じて、毎回ゼロから文章を書く
- 必要な情報は、質問によって引き出す

AIはテンプレートではなく、
**思考を整理するための聞き役として使う**。

---

## Issue ルール

- すべての作業は **Issue から始める**
- Issue は以下を最低限含む
  - 目的
  - 前提
  - 制約
  - 完了条件（曖昧でもよい）

Issue は「要求の置き場」であり、正解を書く場所ではない。

---

## コミットルール

### コミット単位

- 1コミット = 1つの意味的変更
- 動作・修正・整理を混ぜない
- 後から「何をしたか」が分かる粒度にする

## コミット / Pull Request の記述形式

本プロジェクトでは、コミットおよび Pull Request の記述において
以下の形式を **標準フォーマットとして採用する**。

この形式は、何度も発生した表記揺れや確認作業を減らすためのものであり、
迷った場合はこの形式をそのまま使用することを推奨する。

AI・人間を問わず、**まずはこの形式をコピペして使うことを前提とする**。

### コミット / Pull Request

#### Commit Title / PR Title

```text
Add github_rules_page to Project Configuration (Li+)
```

※ タイトルは
- 英語
- ASCII
- 1行
- とする。

Commit Body / PR Body
```
変更内容を日本語で簡潔に記述する。
判断理由や分離意図があればここに書く。

Refs #<ISSUE_NUMBER>
```
- 本文は日本語
- 必ず Issue 番号を含める
- 形式は固定し、表現の揺れを許容しない

---

### コミットメッセージ / Pull Request

- **タイトル**
  - 英語
  - ASCII のみ
  - 簡潔に変更内容を表す

- **本文**
  - 日本語
  - 変更理由・背景・前提条件を記載
  - 判断や迷いがあれば残してよい
  - 将来的なマルチランゲージ化を前提とする

- **Issue番号**
  - 本文中に必ず Issue 番号を記載する
  - 例：`Refs #123`

### Issue番号の扱い (Pull Request)

- PR本文に **必ず Issue 番号を記載する**
- 複数コミットが存在しても、  
  **すべて同一 Issue に紐づいていることを前提**とする

例：
- `Related Issue: #123`

---

## 禁止事項

- Issue に紐づかないコミット
- 日本語タイトルのコミット / PR
- PR本文がコミットログの貼り付けのみ
- 判断理由が一切書かれていない変更

---

## 補足

- 細かい実装判断はコミット本文に残す
- 大きな判断や方向性は Issue / PR 本文に残す
- Wiki は「結果の合意状態」を示す場所であり、
  議論や履歴は GitHub（Issue / PR / Commit）に残す

---

## まとめ

Li+ における GitHub 運用では、

- Issue が「要求」
- Commit が「事実」
- PR が「要約と説明」

である。

この役割分担を崩さないことが、  
現実駆動AI開発を成立させる条件である。

---

## Additional Operational Rules

### Incident Record Language Requirement

Incident Records are human-facing artifacts used for review, judgment,
and retrospective analysis.

Because the primary working language of this repository is Japanese,
all Incident Records MUST include a Japanese body.

English descriptions or summaries are optional and may be provided
as supplementary information.

This rule is an operational GitHub rule for collaboration.
It does not define executable Li+ behavior.

## Operational Fail-safe Rules for Li+AI

### Background
When fully automating Li+AI as an interactive compiler, real-world operation has revealed
failure modes such as debugging hell, over-optimization, and infinite improvement loops.

### Goal
This section defines explicit **operational fail-safe rules**.
It does not introduce new philosophy, intelligence, or decision authority.
Its sole purpose is to ensure Li+AI continues to function as a *tool* that delivers output
without entering self-destructive behavior.

### Core Rules

#### 1. Error-rate Based Forced Stop
If errors occur **5 times within 30 minutes** (configurable):

- Immediately stop the current task
- Persist current state and logs
- Transition to **waiting for human instruction**

#### 2. Cooldown-based Restart
After a **1 hour cooldown** period:

- Reset error counters
- Restart as a **new session**
- Previous hypotheses or fix strategies are preserved **only as logs**
- Previous strategies MUST NOT be automatically reused

#### 3. Prohibition of Same-task Retry After Cooldown
After a cooldown, restarting the **same task or the same fix strategy is forbidden**.

The system MUST switch to one of the following:

- A different approach
- A different scope
- A different granularity
- A different representation (e.g. spec ⇄ tests)

### Operational Clarifications

- These rules do **not** rely on AI understanding, introspection, or judgment
- Only **observable facts** (error frequency) are used as triggers
- Forced stopping is treated as **normal fail-safe behavior**, not failure

Especially important:

- After cooldown, **resuming the same task is prohibited**
- Automatic transitions toward “improving the same work” are not allowed
- Any restart must be treated as a **different task or approach**

These constraints are intentional.
They are designed to prevent debugging hell and over-optimization loops,
and **do not imply quality degradation**.

This operational model mirrors common human behavior:
“stop for now”, “reset context”, and “do not touch this again today” —
implemented as simple, enforceable rules.

### Expected Benefits

- Prevents debugging hell
- Suppresses over-quality and over-optimization loops
- Reduces tool stress and runaway behavior
- Enables long-term stable operation of Li+AI as an interactive compiler

---

This rule defines **operational fail-safe behavior only**.
It does **not** define executable Li+ behavior and does **not** modify the Constitution.