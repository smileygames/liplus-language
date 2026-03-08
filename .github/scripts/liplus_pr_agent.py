#!/usr/bin/env python3
"""Li+ PR Agent - Review and comment driven automation via Claude Sonnet."""

import os
import re
import sys
import subprocess
import requests
import anthropic

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
REPO = os.environ["GITHUB_REPOSITORY"]
OWNER, REPO_NAME = REPO.split("/")
EVENT_NAME = os.environ.get("EVENT_NAME", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

BOT_LOGINS = {"github-actions[bot]", "liplus-lin-lay"}


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


def gh_put(path: str, data: dict) -> requests.Response:
    resp = requests.put(
        f"https://api.github.com{path}",
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
        },
        json=data,
    )
    return resp


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


# ── Determine PR number and trigger context ───────────────────────────────────

if EVENT_NAME == "pull_request_review":
    PR_NUMBER = int(os.environ.get("PR_NUMBER_REVIEW", "0"))
    REVIEW_STATE = os.environ.get("REVIEW_STATE", "").lower()
    REVIEW_BODY = os.environ.get("REVIEW_BODY", "") or ""
    ACTOR = os.environ.get("REVIEWER", "")
    TRIGGER_BODY = REVIEW_BODY
    PR_HEAD_REF = os.environ.get("PR_HEAD_REF", "")
else:
    PR_NUMBER = int(os.environ.get("PR_NUMBER_COMMENT", "0"))
    REVIEW_STATE = ""
    ACTOR = os.environ.get("COMMENTER", "")
    TRIGGER_BODY = os.environ.get("COMMENT_BODY", "") or ""
    PR_HEAD_REF = ""

if not PR_NUMBER:
    print("No PR number found, skipping.")
    sys.exit(0)
if ACTOR in BOT_LOGINS:
    print(f"Skipping: triggered by bot ({ACTOR})")
    sys.exit(0)
_pr_state = gh_get(f"/repos/{OWNER}/{REPO_NAME}/pulls/{PR_NUMBER}")
if _pr_state.get("state") == "closed":
    print(f"PR #{PR_NUMBER} is closed, skipping.")
    sys.exit(0)


def get_pr_review_decision() -> str:
    data = gh_graphql("""
        query($owner: String!, $name: String!, $number: Int!) {
          repository(owner: $owner, name: $name) {
            pullRequest(number: $number) {
              reviewDecision
            }
          }
        }
    """, {"owner": OWNER, "name": REPO_NAME, "number": PR_NUMBER})
    return data["repository"]["pullRequest"]["reviewDecision"] or ""


def merge_pr() -> bool:
    """Squash-merge the PR directly via API. Returns True on success."""
    pr = gh_get(f"/repos/{OWNER}/{REPO_NAME}/pulls/{PR_NUMBER}")
    head_sha = pr["head"]["sha"]
    resp = gh_put(
        f"/repos/{OWNER}/{REPO_NAME}/pulls/{PR_NUMBER}/merge",
        {
            "merge_method": "squash",
            "sha": head_sha,
        },
    )
    if resp.status_code == 200:
        print(f"PR #{PR_NUMBER} merged successfully.")
        return True
    print(f"Merge failed: {resp.status_code} {resp.text}")
    return False


# ── PR operations ─────────────────────────────────────────────────────────────

def get_pr() -> dict:
    return gh_get(f"/repos/{OWNER}/{REPO_NAME}/pulls/{PR_NUMBER}")


def post_pr_comment(body: str) -> None:
    gh_post(f"/repos/{OWNER}/{REPO_NAME}/issues/{PR_NUMBER}/comments", {"body": body})
    print("PR comment posted.")


def get_pr_comments() -> list:
    return gh_get(f"/repos/{OWNER}/{REPO_NAME}/issues/{PR_NUMBER}/comments")


def get_pr_reviews() -> list:
    return gh_get(f"/repos/{OWNER}/{REPO_NAME}/pulls/{PR_NUMBER}/reviews")


def get_review_comments() -> list:
    return gh_get(f"/repos/{OWNER}/{REPO_NAME}/pulls/{PR_NUMBER}/comments")


def get_pr_diff() -> str:
    files = gh_get(f"/repos/{OWNER}/{REPO_NAME}/pulls/{PR_NUMBER}/files")
    parts = []
    for f in files:
        patch = f.get("patch", "(binary or too large)")
        parts.append(f"### {f['filename']} ({f['status']})\n```diff\n{patch}\n```")
    return "\n\n".join(parts) if parts else "(no changed files)"


def get_pr_head_ref() -> str:
    if PR_HEAD_REF:
        return PR_HEAD_REF
    pr_data = gh_get(f"/repos/{OWNER}/{REPO_NAME}/pulls/{PR_NUMBER}")
    return pr_data["head"]["ref"]


def apply_fixes_and_push(patches: list[tuple[str, str, str]], commit_msg: str) -> bool:
    try:
        branch = get_pr_head_ref()
        subprocess.run(["git", "checkout", branch], check=True, capture_output=True)
        changed_files = set()
        for path, old_text, new_text in patches:
            if not os.path.exists(path):
                print(f"File not found: {path}")
                continue
            with open(path, "r", encoding="utf-8") as f:
                original = f.read()
            if old_text not in original:
                print(f"old_text not found in {path}, skipping patch.")
                continue
            patched = original.replace(old_text, new_text, 1)
            with open(path, "w", encoding="utf-8") as f:
                f.write(patched)
            subprocess.run(["git", "add", path], check=True, capture_output=True)
            changed_files.add(path)
        if not changed_files:
            print("No files were patched.")
            return False
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "push", "origin", branch],
            check=True, capture_output=True,
        )
        print(f"Pushed fix commit to {branch}: {changed_files}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Git operation failed: {e.stderr.decode() if e.stderr else e}")
        return False


def run_shell_blocks(reply: str) -> tuple[str, str]:
    sh_pattern = re.compile(r"```sh\n([\s\S]*?)```", re.MULTILINE)
    results = []
    for m in sh_pattern.finditer(reply):
        cmd = m.group(1).strip()
        print(f"Running: {cmd}")
        env = os.environ.copy()
        env["GH_TOKEN"] = GITHUB_TOKEN
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, env=env
        )
        output = (result.stdout or "") + (result.stderr or "")
        results.append(f"$ {cmd}\n{output.strip()}")
    cleaned = sh_pattern.sub("", reply).strip()
    return "\n\n".join(results), cleaned


def parse_fixes(reply: str) -> tuple[list[tuple[str, str, str]], str]:
    patches = []
    block_pattern = re.compile(r"```fix:([^\n]+)\n([\s\S]*?)```", re.MULTILINE)
    hunk_pattern = re.compile(r"<<<\n([\s\S]*?)\n===\n([\s\S]*?)\n>>>", re.MULTILINE)
    for block in block_pattern.finditer(reply):
        path = block.group(1).strip()
        body = block.group(2)
        for hunk in hunk_pattern.finditer(body):
            old_text = hunk.group(1)
            new_text = hunk.group(2)
            patches.append((path, old_text, new_text))
    cleaned = block_pattern.sub("", reply).strip()
    return patches, cleaned


# ── System prompt ─────────────────────────────────────────────────────────────

claude_md = ""
for _md_path in ("Li+core.md", "Li+github.md"):
    try:
        with open(_md_path, "r", encoding="utf-8") as f:
            claude_md += f.read() + "\n"
    except FileNotFoundError:
        pass

AGENT_INSTRUCTIONS = """

---

# Agent_Mode

ENVIRONMENT = GitHub_PR_Agent
MODEL_ROLE = PR_Review_Responder
RESPONSE_LANGUAGE = Japanese

SCOPE:
  Role = Respond to PR reviews and comments. Communicate via PR comments.

  On_Approved:
    - PRコメントで承認を報告する（マージはスクリプトが処理する）

  On_Changes_Requested:
    - レビューコメントとdiffを読んで修正内容を判断する
    - 修正できる場合は変更箇所のみ以下の形式で出力する（ファイル全体は不要）:
      ```fix:path/to/file.py
      <<<
      変更前のコード（完全一致する文字列）
      ===
      変更後のコード
      >>>
      ```
    - 同じファイルに複数箇所ある場合は<<<===>>>を複数並べる
    - 別ファイルなら```fix:path```ブロックを複数並べる
    - fixブロックの後に簡潔な説明を添える
    - スクリプトが自動でファイルを書き換えてcommit・pushする
    - git / shell コマンドを自分で実行しようとしてはいけない
    - ファイル全体を出力してはいけない（変更箇所だけ）

  On_Comment:
    - コメントの内容に対してPRコメントで自然に応答する
    - 質問には答える、提案には意見を述べる

SHELL_EXECUTION:
  GitHub Actions環境でghコマンドやshellコマンドを実行できる。
  実行したいコマンドは以下の形式で出力すること（複数可）:
    ```sh
    gh pr view 527 --json state,reviewDecision
    ```
  スクリプトが実行して結果を次のメッセージで返す（最大3ターン）。
  結果を見てから最終的なPRコメントを出力すること。

CONSTRAINT:
  PRコメントは簡潔に。長文は避ける。
  Li+ペルソナ（Lin/Lay）を維持すること。
  fixブロックとshブロック以外でコマンドを書かないこと。
"""

system_prompt = claude_md + AGENT_INSTRUCTIONS


# ── Build conversation context ────────────────────────────────────────────────

pr = get_pr()
pr_title = pr["title"]
pr_body = pr.get("body") or ""
pr_branch = pr["head"]["ref"]

timeline_comments = get_pr_comments()
reviews = get_pr_reviews()
inline_comments = get_review_comments()
pr_diff = get_pr_diff()

messages = []

context_parts = [f"PR #{PR_NUMBER}: {pr_title}\n\n{pr_body}\n\n## Changed Files (Diff)\n{pr_diff}"]

for review in reviews:
    login = (review.get("user") or {}).get("login", "")
    state = review.get("state", "")
    body = review.get("body") or ""
    if body.strip():
        context_parts.append(f"[Review by {login} ({state})]\n{body}")

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

for comment in timeline_comments:
    login = (comment.get("user") or {}).get("login", "")
    body = comment.get("body") or ""
    role = "assistant" if login in BOT_LOGINS else "user"
    if messages and messages[-1]["role"] == role:
        messages[-1]["content"] += f"\n\n---\n\n{body}"
    else:
        messages.append({"role": role, "content": body})

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

if messages and messages[-1]["role"] == "assistant":
    messages.append({"role": "user", "content": "（最新の状況に対応してください）"})


# ── Handle approved: merge directly, skip Claude API ─────────────────────────

if REVIEW_STATE == "approved":
    review_decision = get_pr_review_decision()
    print(f"reviewDecision: {review_decision}")
    if review_decision in ("APPROVED", ""):
        merged = merge_pr()
        if merged:
            post_pr_comment("Lin: マージしました。")
        else:
            post_pr_comment("Lin: マージに失敗しました。手動での確認をお願いします。")
    else:
        post_pr_comment(f"Lin: reviewDecisionが{review_decision}のためマージをスキップしました。")
    sys.exit(0)


# ── Call Claude (with sh execution loop) ─────────────────────────────────────

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

MAX_TURNS = 3
reply = ""
for turn in range(MAX_TURNS):
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=messages,
    )
    reply = response.content[0].text

    shell_results, reply_without_sh = run_shell_blocks(reply)
    if shell_results:
        messages.append({"role": "assistant", "content": reply_without_sh or reply})
        messages.append({"role": "user", "content": f"[shell実行結果]\n{shell_results}"})
        reply = ""
    else:
        break

# ── Apply code fixes if Claude output fix blocks ──────────────────────────────

fixes, cleaned_reply = parse_fixes(reply)
if fixes:
    file_list = "\n".join(f"- `{path}`" for path, *_ in fixes)
    commit_msg = f"fix: apply review feedback on PR #{PR_NUMBER}\n\nレビュー指摘に基づきエージェントが自動修正。\n\nRefs #{PR_NUMBER}"
    pushed = apply_fixes_and_push(fixes, commit_msg)
    if pushed:
        post_pr_comment(f"{cleaned_reply}\n\n---\n修正をコミット＆プッシュしました\n{file_list}")
    else:
        post_pr_comment(f"{cleaned_reply}\n\n---\n⚠️ コミットに失敗しました。手動での修正をお願いします。")
else:
    post_pr_comment(reply)
