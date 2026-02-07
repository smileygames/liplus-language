[Human_&_AI]

This page defines operational rules for humans and collaborating AIs.
It does not define executable Li+ behavior.

Participating AIs should treat these rules as binding for collaboration,
while recognizing that final judgment and enforcement remain human responsibilities.

---

# GitHub 運用ルール（Li+）

このページは、Li+ プロジェクトにおける  
**GitHub 上での実際の運用規則**を定義する。

ここに書かれている内容は思想や方針ではなく、  
**守られない場合にレビュー・修正・差し戻しの対象となる規則**である。

---

## Issue / Commit / Pull Request 共通ルール

- すべての作業は **Issue から始める**
- Commit / Pull Request は **必ず Issue に紐づける**
- Issue 番号のない Commit / PR は認めない

---

## Issue の記述

- Issue は「要求の置き場」である
- 正解や実装方法を書く必要はない
- 以下を含めることを推奨する
  - 目的
  - 前提
  - 制約
  - 完了条件（曖昧でもよい）

---

## Commit / Pull Request の形式

### Title（必須）

- **英語**
- **ASCII のみ**
- **1行**

例：

Title（英語 / ASCII / 1行）

```
Add placement rules to Li+ index
```

### Body（必須）
```
- **日本語**
- 将来的な多言語化は許容するが、現時点では日本語を基本とする
- 以下を含めること
  - 変更内容の要約
  - 判断理由や背景（あれば）
```
---

### Issue 番号（必須）

- Commit / PR の本文に **必ず Issue 番号を含める**
- 形式は自由だが、Issue との関連が明確であること

例：
```
Refs #159
```

---

## Pull Request 追加ルール

### Pull Request Body の要約（必須）

- **2～3行で要約を書く**
- 変更の要点と影響範囲が分かること
- 詳細説明は不要（Issue を参照する）

---

## 禁止事項

- Issue に紐づかない Commit / PR
- 日本語タイトルの Commit / PR
- Issue 番号の記載がない Commit / PR
- Pull Request の要約が無いもの

---

## 補足

- 詳細な議論や思考過程は Issue に残す
- Wiki は「仕様・定義」を置く場所であり、
  運用上の判断や経緯は GitHub（Issue / PR / Commit）に残す
