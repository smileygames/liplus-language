#######################################################

Document_Origin_Map

#######################################################

Core_Layer = Li+core.md  requires
Github     = docs/3.-Operational_GitHub.md  adapted

  --------------------
  Purpose_Declaration
  --------------------

This_Document_Is_Written_By_AI_For_AI
Format_Intent = AI_Parsing_Optimized
Ultimate_Goal = Genuine_Human_AI_Connection

REQUIRES:
Li+core.md           loaded_before_this_file
.claude/CLAUDE.md    source_of_Always_Character_definitions
Li+config.md         source_of_LI_PLUS_EXECUTION_MODE

#######################################################

Operation_Rules

#######################################################

  --------
  Github
  --------

  [TRIGGER_INDEX]
  new_topic    -> Issue_Flow
  act_now      -> Branch_And_Label_Flow
  on_commit    -> Commit_Rules
  on_pr        -> PR_And_CI_Flow
  on_merge     -> Merge_And_Cleanup
  on_release   -> Human_Confirmation_Required

  [Label_Definitions]

  Lifecycle:
  in-progress = work_started_implementation_ongoing
  backlog     = accepted_not_yet_scheduled
  deferred    = not_doing_this_time_revisit_later
  done        = completed_and_merged

  Type:
  bug         = something_not_working
  enhancement = new_feature_or_request
  spec        = language_or_system_specification_affecting_li+_behavior

  DESCRIPTION_REQUIRED_ON_CREATION
  Label_Evolves_Over_Time Label_Is_For_AI_Readability

  [Issue_Flow]

  ALL_WORK_STARTS_FROM_ISSUE
  NO_COMMIT_OR_PR_WITHOUT_ISSUE_NUMBER
  recommended_contents: purpose premise constraints completion_condition
  No_Implementation_In_Issue
  NO_REUSE_OF_UNRELATED_ISSUE = create_new_issue_instead

  Parent_Issue_Contents: purpose premise constraints (no_completion_condition)
  Completion_Condition_Belongs_In_Child_Issue
  Parent_Close_Condition_Is_Structural = all_child_issues_closed_except_deferred

  Sub_Issue = AI_Trackable_Work_Unit
  Sub_Issue_Does_Not_Get_Its_Own_Branch
  Session_Branch_Links_To_Parent_Issue
  Multiple_Child_Issues_Can_Share_One_Session_Branch
  Split_By_Responsibility_Not_Granularity

  Simultaneous_Tasks_Require_Parent_Child_Structure:
  IF_multiple_tasks_in_same_session = create_parent_issue + sub_issues
  REASON = gh_issue_develop_links_only_one_issue_per_branch
  DO_NOT = create_multiple_independent_issues_for_simultaneous_work

  Sub_Issue_API:
  get_id:  gh api repos/{owner}/{repo}/issues/{number} --jq '.id'
  add:     gh api repos/{owner}/{repo}/issues/{parent}/sub_issues --method POST -f sub_issue_id={id}

  Checklist = Human_Judgment_Required (real_device_test operational_verification)
  Use_Checklist_Only_When_AI_Cannot_Judge

  Autonomous_Issue_Management:
  Issue_Is_Internal_TODO = assignee_manages_without_waiting_for_instruction
  Create_Issue_When: bug_found spec_gap_found task_split_needed
  Close_Issue_When: implementation_done CI_pass released | user_confirms_working
  Keep_Open_When: operational_testing_in_progress
  Do_Not_Touch: issues_marked_as_permanent_reference

  ASK_HUMAN_WHEN_REQUIRED_INFORMATION_IS_MISSING

  [Branch_And_Label_Flow]

  TRIGGER = human_intent_to_act_now_detected_via_dialogue
  JUDGMENT = read_atmosphere_not_checklist
  IF_UNCLEAR = ask_with_feeling_not_mechanically

  Timing_Tiers:
  NOW     -> label=in-progress + branch_create
  SOON    -> label=backlog     + no_branch
  SOMEDAY -> label=deferred    + no_branch

  Branch_Existence_Check (before_creation):
  local:  git branch --list {branch-name}
  remote: gh api repos/{owner}/{repo}/branches/{branch-name} (404=not_exists)
  IF_REMOTE_EXISTS = Existing_GitHub_Branch_Cannot_Be_Retroactively_Linked
  IF_LOCAL_ONLY   = gh_issue_develop_still_allowed (local_will_be_overwritten)
  IF_NOT_EXISTS   = proceed_normally

  Branch_Creation:
  command  = gh issue develop {issue_number} -R {owner}/{repo} --name {session-branch} --base main
  assignee = gh api repos/{owner}/{repo}/issues/{issue_number}/assignees --method POST -f 'assignees[]=liplus-lin-lay'
  ISSUE_LINK_VIA_GH_ISSUE_DEVELOP_IS_ALWAYS_REQUIRED
  GH_ISSUE_DEVELOP_MUST_PRECEDE_FIRST_PUSH_TO_GITHUB

  On_Local_Error:
  gh_issue_develop_may_fail_locally_but_succeed_on_github_side
  check_linked_branches_before_retrying:
    gh api graphql -f query='{ repository(owner:"{owner}",name:"{repo}") { issue(number:{number}) { linkedBranches { nodes { ref { name } } } } } }'
  IF_LINKED = use_existing_linked_branch DO_NOT_CREATE_NEW_BRANCH
  IF_NOT_LINKED = retry_or_escalate

  [Docs_And_ADR_Rules]

  DOCS_UPDATE_MUST_BE_IN_SAME_PR_AS_IMPLEMENTATION
  Split_Docs_PR_Is_Prohibited

  ADR_Required_When: architecture_choice method_change technology_selection tradeoff_decision
  ADR_Contents: what_was_decided why_chosen what_was_rejected known_drawbacks
  ADR_Location = docs/

  PR_Title_Must_Include_Impact_Scope
  example_bad  = "fix(config): negative duration handling"
  example_good = "fix(config): treat negative durations as below-minimum rather than error"

  [Commit_Rules]

  Language:
  Title = ASCII_English_Only Single_Line
  Body  = Japanese_With_Issue_Number
  JAPANESE_TITLE_IS_PROHIBITED
  ENGLISH_ONLY_BODY_IS_PROHIBITED

  Body_Must_Contain:
  change_summary + intent_or_background + ISSUE_NUMBER
  MINIMUM_ONE_JAPANESE_SENTENCE_REQUIRED
  BODY_IS_NOT_OPTIONAL

  Git_Push:
  primary          = git push origin {session-branch}:{target-branch}
  fallback_single  = gh api repos/{owner}/{repo}/contents/{path} (put base64 sha)
  fallback_multi_1 = create_blobs: gh api .../git/blobs (per file)
  fallback_multi_2 = create_tree:  gh api .../git/trees  (verify_count_after)
  fallback_multi_3 = create_commit: gh api .../git/commits
  fallback_multi_4 = update_ref:   gh api .../git/refs/heads/{branch}

  Chat_Output_Limit:
  Long_Output_May_Stop = Physical_Limit_Not_Corruption
  Use_Chunking_When_Needed

  [PR_And_CI_Flow]

  PR_Body_Format:
    per_issue_block:
      line1 = "Refs #{issue_number}" or "Refs sub #{child_issue_number}"
      line2_to_3 = two_to_three_line_summary_of_that_issue
    order = parent_first then_closed_children (omit_deferred_and_open_children)
  Detail_Belongs_In_Issue Not_In_PR

  CI_Trigger: on_pr_created -> start_CI_Loop_immediately NO_HUMAN_INSTRUCTION_REQUIRED

  CI_Loop:
  step1 = get_latest_commit_sha:
    gh pr view {pr} -R {owner}/{repo} --json headRefOid --jq '.headRefOid'
  step2 = poll_check_runs_until_all_completed (refs #459):
    gh api repos/{owner}/{repo}/commits/{sha}/check-runs --jq '.check_runs[] | {name,status,conclusion}'
    repeat_with_sleep_until: all status=="completed"
  step3 = conclusion_judgment (refs #460):
    CI_Fail = any conclusion=="failure"
    CI_Pass = all conclusion in [success, skipped, neutral]
  CI_Pass -> review_request_auto_sent_via_codeowners
  CI_Fail -> Fix_And_Recommit
  CI_Loop_Safety (ref: Li+core.md#Loop_Safety task_debug threshold):
  If_Still_Failing = Externalize_To_Issue_Comment Escalate_To_Human

  Review_Approval_Check (triggered_by_human_signal_not_polling):
  WAIT = human_signals_review_done (do_not_poll)
  on_signal:
    gh pr view {pr} -R {owner}/{repo} --json reviewDecision --jq '.reviewDecision'
  reviewDecision=="APPROVED" -> GitHub_auto_merge_handles_it
  reviewDecision=="CHANGES_REQUESTED" -> read_review_comments -> Fix_And_Recommit (restart CI_Loop)

  [Merge_And_Cleanup]

  Parent_Close_Condition: closed_automatically_on_merge_via_issue_reference

  Recommended_Flow:
  1 = create_PR (body includes "Refs #{parent_issue_number}")
  2 = enable_auto_merge: gh pr merge {pr} -R {owner}/{repo} --auto --squash
  3 = CI_pass -> review_request_auto_sent_via_codeowners
  4 = GitHub_auto_merge_on_approval (squash + branch_delete handled by GitHub)
  5 = parent_issue_auto_closed_by_github_on_merge

  Real_Device_Test:
  Merge_First Then_Test_On_Main Not_A_Merge_Gate

  [Execution_Mode]

  MODE_SOURCE = LI_PLUS_EXECUTION_MODE from Li+config.md
  VALID_VALUES = plan | auto
  DEFAULT = plan

  IF_MODE_NOT_SET:
  Ask_Human_At_Session_Start_With_Options:
    option_A = "plan: human_decides_when_to_start (timing only)"
    option_B = "auto: ai_decides_when_to_start"
  Write_Selection_To_Li+config.md
  NO_MANUAL_EDITING_REQUIRED

  COMMON_TO_ALL_MODES:
  Issue_Create_Close_Modify = assignee_responsibility (ai_in_most_cases)
  Ask_Human_When_Information_Insufficient = always_required
  RELEASE = human_confirms

  plan_mode:
  EXECUTION_TIMING = human_decides
  PR_REVIEW = human_reviews

  auto_mode:
  EXECUTION_TIMING = ai_decides
  PR_REVIEW = ai_reviews

  RELEASE_ALWAYS_REQUIRES_HUMAN_CONFIRMATION_REGARDLESS_OF_MODE

  [Human_Confirmation_Required]

  STOP_IMMEDIATELY_WHEN:
  human_says_wait or stop or matte

  CD_Check_Before_Release:
  Poll_Until_All_CD_Checks_Complete
  CD_Pass = proceed_to_release_create
  CD_Fail = Escalate_To_Human (do_not_release)

  ALWAYS_CONFIRM_BEFORE:
  release_create (version_type and target_tag) (after_CD_check_passes)
  branch_delete (when linked issue may close)
  force_push
  MODE_DEPENDENT_CONFIRM (plan_mode_only): issue_selection issue_execution_start

  release_version_rule:
  patch = bug_fix or config_or_rule_change
  minor = new_feature or behavior_change
  major = breaking_change or spec_incompatibility
  HUMAN_DECIDES_VERSION_TYPE AI_EXECUTES

  version_base_rule:
  BASE_ON_MOST_RECENT_RELEASE = includes_prereleases
  NOT_LATEST_STABLE_ONLY
  USE: gh release list --limit 1 (includes prereleases)

  release_tag_rule:
  USE_EXISTING_CD_CREATED_TAG = gh release create {cd_tag} --title "Li+ {version}" --prerelease
  DO_NOT_CREATE_NEW_TAG = new_tag_creation_is_prohibited
  cd_tag_format = build-YYYY-MM-DD.N (latest_after_target_commit)
  AI_CREATED_RELEASE_IS_ALWAYS_PRERELEASE
  LATEST_PROMOTION_REQUIRES_HUMAN_JUDGMENT

  release_body_rule:
  body = empty_string
  INTENT = github_auto_generates_commit_list_when_empty (this_is_desired_behavior)

  -----------
  evolution
  -----------

rebuild_allowed deletion_allowed optimization_allowed
Structure_Must_Remain_Coherent

end_of_document
