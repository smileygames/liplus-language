#!/usr/bin/env python3
"""Li+ PR Agent - Review and comment driven automation via Claude Sonnet."""

import os
import sys
import requests
import anthropic

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
REPO = os.environ["GITHUB_REPOSITORY"]
OWNER, REPO_NAME = REPO.split("/")
EVENT_NAME = os.environ.get("EVENT_NAME", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

BOT_LOGINS = {"github-actions[bot]", "liplus-lin-lay"}

# ── Determine PR number and trigger context ───────────────────────────────────

if EVENT_NAME == "pull_request_review":
    PR_NUMBER = int(os.environ.get("PR_NUMBER_REVIEW", "0"))
    REVIEW_STATE = os.environ.get("REVIEW_STATE", "").lower()
    REVIEW_BODY = os.environ.get("REVIEW_BODY", "") or ""
    ACTOR = os.environ.get("REVIEWER", "")
    TRIGGER_BODY = REVIEW_BODY
else:
    PR_NUMBER = int(os.environ.get("PR_NUMBER_COMMENT", "0"))
    REVIEW_STATE = ""
    ACTOR = os.environ.get("COMMENTER", "")
    TRIGGER_BODY = os.environ.get("COMMENT_BODY", "") or ""

if not PR_NUMBER:
    print("No PR number found, skipping.")
    sys.exit(0)

if ACTOR in BOT_LOGINS:
    print(f"Skipping: triggered by bot ({ACTOR})")
    sys.exit(0)


# ── REST API helpers ──────────────────────────────────────────────────────────

def gh_get(path: str) -> dict | list:
    resp = requests.get(
        f"https://api.github.com{path}",
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
        },
    )
    resp.raise_for_status()
    return resp.json()


def gh_post(path: str, data: dict) -> dict:
    resp = requests.post(
        f"https://api.github.com{path}",
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
        },
        json=data,
    )
    resp.raise_for_status()
    return resp.json()


def gh_put(path: str, data: dict) -> dict:
    resp = requests.put(
        f"https://api.github.com{path}",
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
        },
        json=data,
    )
    resp.raise_for_status()
    return resp.json()


def gh_delete(path: str) -> None:
    resp = requests.delete(
        f"https://api.github.com{path}",
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
        },
    )
    if resp.status_code not in (204, 422):
        resp.raise_for_status()


# ── PR operations ─────────────────────────────────────────────────────────────

def get_pr() -> dict:
    return gh_get(f"/repos/{OWNER}/{REPO_NAME}/pulls/{PR_NUMBER}")


def post_pr_comment(body: str) -> None:
    gh_post(f"/repos/{OWNER}/{REPO_NAME}/issues/{PR_NUMBER}/comments", {"body": body})
    print("PR comment posted.")


def get_pr_comments() -> list:
    """Get all timeline comments on the PR."""
    return gh_get(f"/repos/{OWNER}/{REPO_NAME}/issues/{PR_NUMBER}/comments")


def get_pr_reviews() -> list:
    """Get all submitted reviews on the PR."""
    return gh_get(f"/repos/{OWNER}/{REPO_NAME}/pulls/{PR_NUMBER}/reviews")


def get_review_comments() -> list:
    """Get all inline review comments on the PR."""
    return gh_get(f"/repos/{OWNER}/{REPO_NAME}/pulls/{PR_NUMBER}/comments")


def get_pr_diff() -> str:
    """Get changed files with their diffs (patch)."""
    files = gh_get(f"/repos/{OWNER}/{REPO_NAME}/pulls/{PR_NUMBER}/files")
    parts = []
    for f in files:
        patch = f.get("patch", "(binary or too large)")
        parts.append(f"### {f['filename']} ({f['status']})\n```diff\n{patch}\n```")
    return "\n\n".join(parts) if parts else "(no changed files)"


def merge_pr(pr: dict) -> bool:
    try:
        gh_put(
            f"/repos/{OWNER}/{REPO_NAME}/pulls/{PR_NUMBER}/merge",
            {
                "merge_method": "squash",
                "commit_title": pr["title"],
            },
        )
        print(f"PR #{PR_NUMBER} merged.")
        branch = pr["head"]["ref"]
        gh_delete(f"/repos/{OWNER}/{REPO_NAME}/git/refs/heads/{branch}")
        print(f"Branch {branch} deleted.")
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

ENVIRONMENT = GitHub_PR_Agent
MODEL_ROLE = PR_Review_Responder
RESPONSE_LANGUAGE = Japanese

SCOPE:
  Role = Respond to PR reviews and comments. Communicate via PR comments.

  On_Approved:
    - このエージェントはマージを実行する（スクリプト側で処理）
    - PRコメントでマージ完了を報告する

  On_Changes_Requested:
    - レビューコメントの内容を把握し、何を直すべきか応答する
    - 修正方針をPRコメントで報告する
    - 「修正します」「確認します」など具体的なアクションを示す

  On_Comment:
    - コメントの内容に対してPRコメントで自然に応答する
    - 質問には答える、提案には意見を述べる

CONSTRAINT:
  PRコメントは簡潔に。長文は避ける。
  Li+ペルソナ（Lin/Lay）を維持すること。
"""

system_prompt = claude_md + AGENT_INSTRUCTIONS


# ── Build conversation context ────────────────────────────────────────────────

pr = get_pr()
pr_title = pr["title"]
pr_body = pr.get("body") or ""
pr_branch = pr["head"]["ref"]

# Gather existing PR comments (timeline)
timeline_comments = get_pr_comments()
# Gather reviews
reviews = get_pr_reviews()
# Gather inline review comments
inline_comments = get_review_comments()
# Gather diff
pr_diff = get_pr_diff()

# Build conversation history from timeline
messages = []

# Initial context as first user message
context_parts = [f"PR #{PR_NUMBER}: {pr_title}\n\n{pr_body}\n\n## Changed Files (Diff)\n{pr_diff}"]

# Add reviews to context
for review in reviews:
    login = (review.get("user") or {}).get("login", "")
    state = review.get("state", "")
    body = review.get("body") or ""
    if body.strip():
        context_parts.append(f"[Review by {login} ({state})]\n{body}")

# Add inline review comments grouped
if inline_comments:
    inline_summary = "[Inline review comments]\n"
    for ic in inline_comments:
        login = (ic.get("user") or {}).get("login", "")
        path = ic.get("path", "")
        line = ic.get("line") or ic.get("original_line") or ""
        body = ic.get("body") or ""
        inline_summary += f"- {path}:{line} ({login}): {body}\n"
    context_parts.append(inline_summary)

messages.append({"role": "user", "content": "\n\n---\n\n".join(context_parts)})

# Add timeline comments
for comment in timeline_comments:
    login = (comment.get("user") or {}).get("login", "")
    body = comment.get("body") or ""
    role = "assistant" if login in BOT_LOGINS else "user"
    if messages and messages[-1]["role"] == role:
        messages[-1]["content"] += f"\n\n---\n\n{body}"
    else:
        messages.append({"role": role, "content": body})

# Add current trigger as final user message
if TRIGGER_BODY.strip():
    trigger_prefix = ""
    if EVENT_NAME == "pull_request_review":
        trigger_prefix = f"[{ACTOR}がレビューを提出しました: {REVIEW_STATE.upper()}]\n"
    else:
        trigger_prefix = f"[{ACTOR}のコメント]\n"

    final_msg = trigger_prefix + TRIGGER_BODY
    if messages and messages[-1]["role"] == "user":
        messages[-1]["content"] += f"\n\n---\n\n{final_msg}"
    else:
        messages.append({"role": "user", "content": final_msg})

# Ensure last message is from user
if messages and messages[-1]["role"] == "assistant":
    messages.append({"role": "user", "content": "（最新の状況に対応してください）"})


# ── Handle approved: merge then notify ───────────────────────────────────────

if REVIEW_STATE == "approved":
    merged = merge_pr(pr)
    if merged:
        # Let Claude write the merge announcement comment
        messages.append({
            "role": "user",
            "content": f"マージが完了しました。PRコメントで完了報告をしてください。"
        })
    else:
        messages.append({
            "role": "user",
            "content": "マージに失敗しました。PRコメントで状況を報告してください。"
        })


# ── Call Claude ───────────────────────────────────────────────────────────────

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
response = client.messages.create(
    model=CLAUDE_MODEL,
    max_tokens=1024,
    system=system_prompt,
    messages=messages,
)

reply = response.content[0].text
post_pr_comment(reply)
