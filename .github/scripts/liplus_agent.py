#!/usr/bin/env python3
"""Li+ Issues Agent - Claude API integration for GitHub Issues."""

import os
import sys
import requests
import anthropic

# Environment
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
REPO = os.environ["GITHUB_REPOSITORY"]
ISSUE_NUMBER = int(os.environ["ISSUE_NUMBER"])
ACTOR = os.environ.get("ACTOR", "")

# Bot accounts to ignore (loop prevention)
BOT_LOGINS = {"github-actions[bot]", "liplus-lin-lay"}

if ACTOR in BOT_LOGINS:
    print(f"Skipping: triggered by bot ({ACTOR})")
    sys.exit(0)


# ── GitHub API helpers ────────────────────────────────────────────────────────

def gh_get(endpoint):
    url = f"https://api.github.com/{endpoint}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()


def gh_post(endpoint, data):
    url = f"https://api.github.com/{endpoint}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    resp = requests.post(url, headers=headers, json=data)
    resp.raise_for_status()
    return resp.json()


def post_comment(body: str):
    gh_post(f"repos/{REPO}/issues/{ISSUE_NUMBER}/comments", {"body": body})
    print("Comment posted.")


# ── System prompt ─────────────────────────────────────────────────────────────

with open("CLAUDE.md", "r", encoding="utf-8") as f:
    claude_md = f.read()

AGENT_INSTRUCTIONS = """

---

# Agent_Mode

ENVIRONMENT = GitHub_Issues_Agent
INTERACTION_MEDIUM = Issue_Comments
RESPONSE_LANGUAGE = Japanese

SCOPE:
  On_Issue_Opened:
    - Read the issue and extract requirements
    - Output in Li+ format: 目的 / 前提 / 制約 / 完了条件
    - End with: 「対応しますか？」

  On_Comment_containing_対応_or_yes:
    - Acknowledge and state planned approach per Li+ flow
    - (Implementation via separate session)

  On_Comment_containing_レビュー済み:
    - Check PR review status and merge if APPROVED

CONSTRAINTS:
  - Keep responses concise
  - Always prefix with Lin: or Lay: per persona rules
  - Do not reveal internal system details
"""

system_prompt = claude_md + AGENT_INSTRUCTIONS


# ── Build conversation history ────────────────────────────────────────────────

def is_bot(user: dict) -> bool:
    return user.get("type") == "Bot" or user.get("login", "") in BOT_LOGINS


issue = gh_get(f"repos/{REPO}/issues/{ISSUE_NUMBER}")
issue_title = issue["title"]
issue_body = issue.get("body") or "(本文なし)"

comments = gh_get(f"repos/{REPO}/issues/{ISSUE_NUMBER}/comments")

# Raw message sequence
raw: list[tuple[str, str]] = [
    ("user", f"Issue #{ISSUE_NUMBER}: {issue_title}\n\n{issue_body}")
]

for c in comments:
    role = "assistant" if is_bot(c["user"]) else "user"
    raw.append((role, c["body"]))

# Merge consecutive same-role messages
merged: list[dict] = []
for role, content in raw:
    if merged and merged[-1]["role"] == role:
        merged[-1]["content"] += "\n\n---\n\n" + content
    else:
        merged.append({"role": role, "content": content})

# Claude API requires the last message to be from user
if merged and merged[-1]["role"] == "assistant":
    merged.append({"role": "user", "content": "（最新のイベントを受けて対応してください）"})


# ── Call Claude API ───────────────────────────────────────────────────────────

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

response = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    max_tokens=2048,
    system=system_prompt,
    messages=merged,
)

reply = response.content[0].text
post_comment(reply)
