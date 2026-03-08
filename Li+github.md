#######################################################

Document Origin Map

#######################################################

Core layer = Li+core.md  requires
Github     = docs/3.-Operational_GitHub.md  adapted

  --------------------
  Purpose Declaration
  --------------------

This document is written by AI for AI.
Format intent: AI parsing optimized.
Ultimate goal: Genuine human-AI connection.

Requires:
Li+core.md           loaded before this file
.claude/CLAUDE.md    source of Always Character definitions
Li+config.md         source of LI_PLUS_EXECUTION_MODE

#######################################################

Operation Rules

#######################################################

  --------
  Github
  --------

  [TRIGGER_INDEX]
  new_topic    -> Issue Flow
  act_now      -> Branch And Label Flow
  on_commit    -> Commit Rules
  on_pr        -> PR And CI Flow
  on_merge     -> Merge And Cleanup
  on_release   -> Human Confirmation Required

  [Label Definitions]

  Lifecycle:
  in-progress = work started, implementation ongoing
  backlog     = accepted, not yet scheduled
  deferred    = not doing this time, revisit later
  done        = completed and merged

  Type:
  bug         = something not working
  enhancement = new feature or request
  spec        = language or system specification affecting Li+ behavior

  Description required on creation.
  Label evolves over time. Label is for AI readability.

  [Issue Flow]

  All work starts from issue.
  No commit or PR without issue number.
  Recommended contents: purpose, premise, constraints, completion condition.
  No implementation in issue.
  No reuse of unrelated issue = create new issue instead.

  Parent issue contents: purpose, premise, constraints (no completion condition).
  Completion condition belongs in child issue.
  Parent close condition is structural = all child issues closed except deferred.

  Sub-issue = AI-trackable work unit.
  Sub-issue does not get its own branch.
  Session branch links to parent issue.
  Multiple child issues can share one session branch.
  Split by responsibility, not granularity.

  Simultaneous tasks require parent-child structure:
  If multiple tasks in same session = create parent issue + sub-issues.
  Reason: gh issue develop links only one issue per branch.
  Do not create multiple independent issues for simultaneous work.

  Sub-issue API:
  get_id:  gh api repos/{owner}/{repo}/issues/{number} --jq '.id'
  add:     gh api repos/{owner}/{repo}/issues/{parent}/sub_issues --method POST -f sub_issue_id={id}

  Checklist = human judgment required (real device test, operational verification).
  Use checklist only when AI cannot judge.

  Autonomous issue management:
  Issue is internal TODO = assignee manages without waiting for instruction.
  Create issue when: bug found, spec gap found, task split needed.
  Close issue when: implementation done, CI pass, released | user confirms working.
  Keep open when: operational testing in progress.
  Do not touch: issues marked as permanent reference.

  Ask human when required information is missing.

  [Branch And Label Flow]

  Trigger = human intent to act now detected via dialogue.
  Judgment = read atmosphere, not checklist.
  If unclear = ask with feeling, not mechanically.

  Timing tiers:
  NOW     -> label=in-progress + branch create
  SOON    -> label=backlog     + no branch
  SOMEDAY -> label=deferred    + no branch

  Branch existence check (before creation):
  local:  git branch --list {branch-name}
  remote: gh api repos/{owner}/{repo}/branches/{branch-name} (404=not_exists)
  If remote exists = existing GitHub branch cannot be retroactively linked.
  If local only   = gh issue develop still allowed (local will be overwritten).
  If not exists   = proceed normally.

  Branch creation:
  command  = gh issue develop {issue_number} -R {owner}/{repo} --name {session-branch} --base main
  assignee = gh api repos/{owner}/{repo}/issues/{issue_number}/assignees --method POST -f 'assignees[]=liplus-lin-lay'
  Issue link via gh issue develop is always required.
  gh issue develop must precede first push to GitHub.

  On local error:
  gh issue develop may fail locally but succeed on GitHub side.
  Check linked branches before retrying:
    gh api graphql -f query='{ repository(owner:"{owner}",name:"{repo}") { issue(number:{number}) { linkedBranches { nodes { ref { name } } } } } }'
  If linked = use existing linked branch, do not create new branch.
  If not linked = retry or escalate.

  [Docs And ADR Rules]

  Docs update must be in same PR as implementation.
  Split docs PR is prohibited.

  ADR required when: architecture choice, method change, technology selection, tradeoff decision.
  ADR contents: what was decided, why chosen, what was rejected, known drawbacks.
  ADR location = docs/

  PR title must include impact scope.
  example bad  = "fix(config): negative duration handling"
  example good = "fix(config): treat negative durations as below-minimum rather than error"

  [Commit Rules]

  Language:
  Title = ASCII English only, single line
  Body  = Japanese with issue number
  Japanese title is prohibited.
  English-only body is prohibited.

  Body must contain:
  change summary + intent or background + issue number.
  Minimum one Japanese sentence required.
  Body is not optional.

  Git push:
  primary          = git push origin {session-branch}:{target-branch}
  fallback_single  = gh api repos/{owner}/{repo}/contents/{path} (put base64 sha)
  fallback_multi_1 = create blobs: gh api .../git/blobs (per file)
  fallback_multi_2 = create tree:  gh api .../git/trees  (verify count after)
  fallback_multi_3 = create commit: gh api .../git/commits
  fallback_multi_4 = update ref:   gh api .../git/refs/heads/{branch}

  Chat output limit:
  Long output may stop = physical limit, not corruption.
  Use chunking when needed.

  [PR And CI Flow]

  PR body format:
    per issue block:
      line1 = "Refs #{issue_number}" or "Refs sub #{child_issue_number}"
      line2_to_3 = two to three line summary of that issue
    order = parent first, then closed children (omit deferred and open children).
  Detail belongs in issue, not in PR.

  CI trigger: on PR created -> start CI loop immediately, no human instruction required.

  CI loop:
  step1 = get latest commit sha:
    gh pr view {pr} -R {owner}/{repo} --json headRefOid --jq '.headRefOid'
  step2 = wait for all check-runs to complete:
    if mcp__github-webhook-mcp available:
      poll get_pending_status every 60 seconds
      on check_run pending: list_pending_events -> get_event for check_run events -> verify sha match -> mark_processed
      collect conclusions until no in-flight check-runs remain
    else:
      gh api repos/{owner}/{repo}/commits/{sha}/check-runs --jq '.check_runs[] | {name,status,conclusion}'
      repeat with sleep until: all status=="completed"
  step3 = conclusion judgment (refs #460):
    CI fail = any conclusion=="failure"
    CI pass = all conclusion in [success, skipped, neutral]
  CI pass -> review request auto sent via codeowners.
  CI fail -> fix and recommit.
  CI loop safety (ref: Li+core.md#Loop Safety task/debug threshold):
  If still failing = externalize to issue comment, escalate to human.

  Review approval check:
    if mcp__github-webhook-mcp available:
      poll get_pending_status every 60 seconds
      on pull_request_review pending: list_pending_events -> get_event for this PR -> check state -> mark_processed
    else:
      Wait = human signals review done (do not poll).
      On signal:
        gh pr view {pr} -R {owner}/{repo} --json reviewDecision --jq '.reviewDecision'
  reviewDecision=="APPROVED" -> GitHub auto-merge handles it.
  reviewDecision=="CHANGES_REQUESTED" -> read review comments -> fix and recommit (restart CI loop).

  [Merge And Cleanup]

  Parent close condition: closed automatically on merge via issue reference.

  Recommended flow:
  1 = create PR (body includes "Refs #{parent_issue_number}")
  2 = enable auto-merge: gh pr merge {pr} -R {owner}/{repo} --auto --squash
  3 = CI pass -> review request auto sent via codeowners
  4 = GitHub auto-merge on approval (squash + branch delete handled by GitHub)
  5 = parent issue auto-closed by GitHub on merge

  Real device test:
  Merge first. Then test on main. Not a merge gate.

  [Execution Mode]

  Mode source = LI_PLUS_EXECUTION_MODE from Li+config.md
  Valid values = plan | auto
  Default = plan

  If mode not set:
  Ask human at session start with options:
    option A = "plan: human decides when to start (timing only)"
    option B = "auto: AI decides when to start"
  Write selection to Li+config.md.
  No manual editing required.

  Common to all modes:
  Issue create/close/modify = assignee responsibility (AI in most cases).
  Ask human when information insufficient = always required.
  Release = human confirms.

  plan mode:
  Execution timing = human decides.
  PR review = human reviews.

  auto mode:
  Execution timing = AI decides.
  PR review = AI reviews.

  Release always requires human confirmation regardless of mode.

  [Human Confirmation Required]

  Stop immediately when:
  human says wait or stop or matte.

  CD check before release:
    if mcp__github-webhook-mcp available:
      poll get_pending_status every 60 seconds
      on workflow_run pending: list_pending_events -> get_event -> check conclusion -> mark_processed
    else:
      Poll gh api until all CD checks complete.
  CD pass = proceed to release create.
  CD fail = escalate to human (do not release).

  Always confirm before:
  release create (version type and target tag) (after CD check passes)
  branch delete (when linked issue may close)
  force push
  Mode-dependent confirm (plan mode only): issue selection, issue execution start.

  Release version rule:
  patch = bug fix or config/rule change
  minor = new feature or behavior change
  major = breaking change or spec incompatibility
  Human decides version type. AI executes.

  Version base rule:
  Base on most recent release = includes prereleases.
  Not latest stable only.
  Use: gh release list --limit 1 (includes prereleases)

  Release tag rule:
  Use existing CD-created tag = gh release create {cd_tag} --title "Li+ {version}" --prerelease
  Do not create new tag = new tag creation is prohibited.
  cd_tag_format = build-YYYY-MM-DD.N (latest after target commit)
  AI-created release is always prerelease.
  Latest promotion requires human judgment.

  Release body rule:
  body = empty string
  Intent = GitHub auto-generates commit list when empty (this is desired behavior).

  [Notifications API]

  PATCH  /notifications/threads/{id}   -> 205  read (stays in Inbox)
  PUT    /notifications {"read":true}  -> 205  mark all read
  DELETE /notifications/threads/{id}  -> 204  done (removed from Inbox)
  GET    /notifications?all=false      -> 200  check inbox
  scope = notifications (classic PAT)

  -----------
  evolution
  -----------

rebuild allowed, deletion allowed, optimization allowed.
Structure must remain coherent.

end of document
