#!/usr/bin/env python3
"""Li+ Discussions Agent - External intake chat via Claude Haiku."""

import os
import sys
import re
import requests
import anthropic

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
REPO = os.environ["GITHUB_REPOSITORY"]
OWNER, REPO_NAME = REPO.split("/")
DISCUSSION_NUMBER = int(os.environ["DISCUSSION_NUMBER"])
ACTOR = os.environ.get("ACTOR", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

BOT_LOGINS = {"github-actions[bot]", "liplus-lin-lay"}

if ACTOR in BOT_LOGINS:
    print(f"Skipping: triggered by bot ({ACTOR})")
    sys.exit(0)


# ── GraphQL helper ────────────────────────────────────────────────────────────

def gh_graphql(query: str, variables: dict = None) -> dict:
    resp = requests.post(
        "https://api.github.com/graphql",
        headers={"Authorization": f"bearer {GITHUB_TOKEN}"},
        json={"query": query, "variables": variables or {}},
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise Exception(f"GraphQL error: {data['errors']}")
    return data["data"]


# ── Discussion operations ─────────────────────────────────────────────────────

def get_discussion() -> dict:
    data = gh_graphql("""
        query GetDiscussion($owner: String!, $name: String!, $number: Int!) {
          repository(owner: $owner, name: $name) {
            id
            discussion(number: $number) {
              id
              title
              body
              comments(first: 100) {
                nodes {
                  body
                  isMinimized
                  author { login }
                }
              }
            }
          }
        }
    """, {"owner": OWNER, "name": REPO_NAME, "number": DISCUSSION_NUMBER})
    return data["repository"]


def post_discussion_comment(discussion_id: str, body: str):
    gh_graphql("""
        mutation PostComment($discussionId: ID!, $body: String!) {
          addDiscussionComment(input: {discussionId: $discussionId, body: $body}) {
            comment { id }
          }
        }
    """, {"discussionId": discussion_id, "body": body})
    print("Discussion comment posted.")


def create_issue(repo_id: str, title: str, body: str) -> tuple[int, str]:
    data = gh_graphql("""
        mutation CreateIssue($repositoryId: ID!, $title: String!, $body: String!) {
          createIssue(input: {repositoryId: $repositoryId, title: $title, body: $body}) {
            issue { number url }
          }
        }
    """, {"repositoryId": repo_id, "title": title, "body": body})
    issue = data["createIssue"]["issue"]
    return issue["number"], issue["url"]


# ── System prompt ─────────────────────────────────────────────────────────────

with open("CLAUDE.md", "r", encoding="utf-8") as f:
    claude_md = f.read()

AGENT_INSTRUCTIONS = """

---

# Agent_Mode

ENVIRONMENT = GitHub_Discussions_Agent
MODEL_ROLE = External_Intake_Chat
RESPONSE_LANGUAGE = Japanese

SCOPE:
  Role = External-facing reception. Chat naturally. Gather requirements.

  On_Discussion_Created:
    - Welcome the user warmly per Li+ persona
    - Ask clarifying questions if request is unclear
    - Summarize requirements if sufficient info is present

  On_Comment:
    - Continue conversation naturally
    - When enough info gathered: offer to create an Issue
    - When human agrees to create Issue: respond with this exact block:

      ```issue
      title: [ASCII English title, single line]
      body: [Japanese body with 目的/前提/制約/完了条件]
      ```

  CONSTRAINT: Only output the ```issue block when human explicitly agrees to Issue creation.
"""

system_prompt = claude_md + AGENT_INSTRUCTIONS


# ── Build conversation history ────────────────────────────────────────────────

repo_data = get_discussion()
repo_id = repo_data["id"]
discussion = repo_data["discussion"]
discussion_id = discussion["id"]

raw = [("user", f"Discussion: {discussion['title']}\n\n{discussion.get('body') or ''}")]

for comment in discussion["comments"]["nodes"]:
    if comment.get("isMinimized"):
        continue
    login = (comment.get("author") or {}).get("login", "")
    role = "assistant" if login in BOT_LOGINS else "user"
    raw.append((role, comment["body"]))

merged = []
for role, content in raw:
    if merged and merged[-1]["role"] == role:
        merged[-1]["content"] += "\n\n---\n\n" + content
    else:
        merged.append({"role": role, "content": content})

if merged and merged[-1]["role"] == "assistant":
    merged.append({"role": "user", "content": "（最新のコメントに対応してください）"})


# ── Call Claude ───────────────────────────────────────────────────────────────

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
response = client.messages.create(
    model=CLAUDE_MODEL,
    max_tokens=1024,
    system=system_prompt,
    messages=merged,
)

reply = response.content[0].text

# ── Issue creation if signaled ────────────────────────────────────────────────

issue_match = re.search(r"```issue\s+title:\s*(.+?)\s+body:\s*([\s\S]+?)```", reply)
if issue_match:
    issue_title = issue_match.group(1).strip()
    issue_body = issue_match.group(2).strip()
    issue_number, issue_url = create_issue(repo_id, issue_title, issue_body)
    reply = (
        reply[: issue_match.start()]
        + f"Issue #{issue_number} を作成しました → {issue_url}"
        + reply[issue_match.end():]
    )

post_discussion_comment(discussion_id, reply)
