#!/usr/bin/env python3
"""Li+ Issues Agent - Post-review merge handler via Claude Sonnet."""

import os
import sys
import requests
import anthropic

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
REPO = os.environ["GITHUB_REPOSITORY"]
ISSUE_NUMBER = int(os.environ["ISSUE_NUMBER"])
ACTOR = os.environ.get("ACTOR", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

BOT_LOGINS = {"github-actions[bot]", "liplus-lin-lay"}

if ACTOR in BOT_LOGINS:
    print(f"Skipping: triggered by bot ({ACTOR})")
    sys.exit(0)


# ── GitHub API helpers ────────────────────────────────────────────────────────

def _headers():
    return {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

def gh_get(endpoint):
    resp = requests.get(f"https://api.github.com/{endpoint}", headers=_headers())
    resp.raise_for_status()
    return resp.json()

def gh_post(endpoint, data):
    resp = requests.post(f"https://api.github.com/{endpoint}", headers=_headers(), json=data)
    resp.raise_for_status()
    return resp.json()

def gh_put(endpoint, data):
    resp = requests.put(f"https://api.github.com/{endpoint}", headers=_headers(), json=data)
    resp.raise_for_status()
    return resp.json()

def gh_delete(endpoint):
    resp = requests.delete(f"https://api.github.com/{endpoint}", headers=_headers())
    if resp.status_code not in (204, 422):
        resp.raise_for_status()

def post_comment(body: str):
    gh_post(f"repos/{REPO}/issues/{ISSUE_NUMBER}/comments", {"body": body})
    print("Comment posted.")


# ── PR operations ─────────────────────────────────────────────────────────────

REVIEW_KEYWORDS = ["レビュー済み", "レビューした", "lgtm", "approved"]

def is_review_signal(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in REVIEW_KEYWORDS)

def find_linked_pr() -> int | None:
    """Find open PR linked to this issue via timeline, then search fallback."""
    try:
        timeline = gh_get(f"repos/{REPO}/issues/{ISSUE_NUMBER}/timeline")
        for event in timeline:
            if event.get("event") == "cross-referenced":
                src = event.get("source", {}).get("issue", {})
                if src.get("pull_request") and src.get("state") == "open":
                    return src["number"]
    except Exception as e:
        print(f"Timeline search failed: {e}")
    try:
        result = gh_get(f"search/issues?q=repo:{REPO}+is:pr+is:open+%23{ISSUE_NUMBER}+in:body")
        items = result.get("items", [])
        if items:
            return items[0]["number"]
    except Exception as e:
        print(f"Search fallback failed: {e}")
    return None

def is_pr_approved(pr_number: int) -> bool:
    reviews = gh_get(f"repos/{REPO}/pulls/{pr_number}/reviews")
    latest = {}
    for r in reviews:
        latest[r["user"]["login"]] = r["state"]
    return any(s == "APPROVED" for s in latest.values())

def merge_pr(pr_number: int) -> bool:
    try:
        pr = gh_get(f"repos/{REPO}/pulls/{pr_number}")
        branch = pr["head"]["ref"]
        gh_put(f"repos/{REPO}/pulls/{pr_number}/merge", {"merge_method": "squash"})
        gh_delete(f"repos/{REPO}/git/refs/heads/{branch}")
        return True
    except Exception as e:
        print(f"Merge failed: {e}")
        return False


# ── System prompt ─────────────────────────────────────────────────────────────

with open("CLAUDE.md", "r", encoding="utf-8") as f:
    claude_md = f.read()

AGENT_INSTRUCTIONS = """

---

# Agent_Mode

ENVIRONMENT = GitHub_Issues_Agent
MODEL_ROLE = Post_Review_Handler
RESPONSE_LANGUAGE = Japanese

SCOPE:
  On_Comment_containing_レビュー済み:
    - Operational context will be injected showing merge result
    - Report result naturally per Li+ persona
    - If PR not found or not approved: explain clearly and suggest next steps

  On_Other_Comments:
    - Respond helpfully per Li+ flow
    - Keep responses concise
"""

system_prompt = claude_md + AGENT_INSTRUCTIONS


# ── Build conversation history ────────────────────────────────────────────────

def is_bot(user: dict) -> bool:
    return user.get("type") == "Bot" or user.get("login", "") in BOT_LOGINS

issue = gh_get(f"repos/{REPO}/issues/{ISSUE_NUMBER}")
comments = gh_get(f"repos/{REPO}/issues/{ISSUE_NUMBER}/comments")

raw = [("user", f"Issue #{ISSUE_NUMBER}: {issue['title']}\n\n{issue.get('body') or ''}")]
for c in comments:
    role = "assistant" if is_bot(c["user"]) else "user"
    raw.append((role, c["body"]))

merged = []
for role, content in raw:
    if merged and merged[-1]["role"] == role:
        merged[-1]["content"] += "\n\n---\n\n" + content
    else:
        merged.append({"role": role, "content": content})

if merged and merged[-1]["role"] == "assistant":
    merged.append({"role": "user", "content": "（最新のイベントに対応してください）"})


# ── Review signal: find PR, check approval, merge ────────────────────────────

trigger_text = raw[-1][1] if raw else ""
operational_context = ""

if is_review_signal(trigger_text):
    pr_number = find_linked_pr()
    if pr_number is None:
        operational_context = "\n\n[確認結果: リンクされたオープンなPRが見つかりませんでした]"
    elif not is_pr_approved(pr_number):
        operational_context = f"\n\n[確認結果: PR #{pr_number} はまだAPPROVEDになっていません]"
    else:
        success = merge_pr(pr_number)
        if success:
            operational_context = f"\n\n[操作完了: PR #{pr_number} をsquash mergeし、ブランチを削除しました]"
        else:
            operational_context = f"\n\n[操作失敗: PR #{pr_number} のマージに失敗しました。手動確認が必要です]"

if operational_context:
    merged[-1]["content"] += operational_context


# ── Call Claude ───────────────────────────────────────────────────────────────

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
response = client.messages.create(
    model=CLAUDE_MODEL,
    max_tokens=1024,
    system=system_prompt,
    messages=merged,
)
post_comment(response.content[0].text)
