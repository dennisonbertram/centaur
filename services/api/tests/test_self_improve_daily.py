"""Unit tests for the pure helpers in workflows.self_improve_daily.

These target the pieces of the nightly self-improvement workflow that do
not require a WorkflowContext: scorecard rendering, Slack link
formatting, user-name extraction, child-result annotation, and the
slack_narrative privacy strip that runs before the implementing child
workflow ever sees the fix packet.
"""

from __future__ import annotations

from workflows.self_improve_daily import (
    SLACK_ONLY_FIX_FIELDS,
    _annotate_child_results_with_narratives,
    _build_scorecard_markdown,
    _message_user_display,
    _slack_pr_link,
    _strip_slack_only_fields,
)


def test_slack_pr_link_uses_angle_bracket_format() -> None:
    # Slack renders `<url|text>` as a link; GitHub-style `[text](url)` is
    # surfaced as literal characters, which is the bug we saw in the
    # first rendered nightly scorecard post.
    link = _slack_pr_link(322, "https://github.com/paradigmxyz/centaur/pull/322")
    assert link == "<https://github.com/paradigmxyz/centaur/pull/322|#322>"


def test_slack_pr_link_handles_missing_pieces() -> None:
    assert _slack_pr_link("", "") == ""
    assert _slack_pr_link(322, "") == "#322"
    assert _slack_pr_link("", "https://example.test/pr") == "<https://example.test/pr>"


def test_message_user_display_prefers_user_name_then_name_then_username() -> None:
    assert (
        _message_user_display(
            {"metadata": {"user_name": "Josie", "name": "ignored", "username": "j"}}
        )
        == "Josie"
    )
    assert (
        _message_user_display(
            {"metadata": {"name": "Josie Kim", "username": "j"}}
        )
        == "Josie Kim"
    )
    assert _message_user_display({"metadata": {"username": "josie"}}) == "josie"
    assert _message_user_display({"metadata": {}}) == ""
    assert _message_user_display({}) == ""


def test_strip_slack_only_fields_removes_narrative_but_keeps_rest() -> None:
    packet = {
        "title": "Tighten verification reminder",
        "fix_type": "prompt_tweak",
        "target_surface": "tools/personas/eng/PROMPT.md",
        "what_to_change": "Add lint check reminder.",
        "slack_narrative": "Josie hit this on Tuesday.",
    }

    stripped = _strip_slack_only_fields(packet)

    assert "slack_narrative" not in stripped
    for field in SLACK_ONLY_FIX_FIELDS:
        assert field not in stripped
    assert stripped["title"] == "Tighten verification reminder"
    # Input must not be mutated — callers still need the narrative for Slack.
    assert packet["slack_narrative"] == "Josie hit this on Tuesday."


def test_annotate_child_results_with_narratives_pairs_by_position() -> None:
    selected_fixes = [
        {
            "title": "Tighten verification reminder",
            "fix_type": "prompt_tweak",
            "dominant_failure_mode": "verification_miss",
            "slack_narrative": "Josie hit the lint gap Tuesday; Matt Thursday.",
        },
        {
            "title": "Add triage-first guidance",
            "fix_type": "workflow_fix",
            "dominant_failure_mode": "intent_miss",
            "slack_narrative": "Asher asked why morning-brief never posted.",
        },
    ]
    child_results = [
        {"pr_number": 42, "pr_url": "https://example.test/pr/42", "title": "Add lint check"},
        {"error": "child workflow timed out", "child_run_id": "wfr_abc"},
    ]

    annotated = _annotate_child_results_with_narratives(
        child_results=child_results,
        selected_fixes=selected_fixes,
    )

    assert annotated[0]["slack_narrative"].startswith("Josie hit the lint")
    assert annotated[0]["fix_type"] == "prompt_tweak"
    assert annotated[0]["dominant_failure_mode"] == "verification_miss"
    # Title that already exists on the child result must win over the
    # upstream fix title (the child's PR title is what shipped).
    assert annotated[0]["title"] == "Add lint check"
    assert annotated[1]["slack_narrative"].startswith("Asher asked")
    # Missing PR data still gets paired with its narrative so the
    # failure line in the scorecard can explain what we were trying.
    assert annotated[1]["error"] == "child workflow timed out"


def test_annotate_child_results_tolerates_length_mismatch() -> None:
    # Reality: one of the kids failed to start and never produced an
    # output_json. The annotator must not crash and must leave the
    # fixes-we-actually-have alone.
    annotated = _annotate_child_results_with_narratives(
        child_results=[
            {"pr_number": 1, "pr_url": "https://x.test/1"},
            {"pr_number": 2, "pr_url": "https://x.test/2"},
            {"error": "bad"},
        ],
        selected_fixes=[
            {"title": "Fix A", "slack_narrative": "A narrative."},
        ],
    )

    assert annotated[0]["slack_narrative"] == "A narrative."
    assert "slack_narrative" not in annotated[1]
    assert "slack_narrative" not in annotated[2]


def _scorecard_review_fixture() -> dict:
    return {
        "tasks_reviewed": 8,
        "below_bar_count": 3,
        "below_bar_rate": 0.375,
        "task_reviews": [
            {"composite_score": 82},
            {"composite_score": 60},
            {"composite_score": 55},
        ],
        "top_failure_modes": [
            {"failure_mode": "verification_miss", "count": 3},
            {"failure_mode": "intent_miss", "count": 2},
        ],
        "selected_fixes": [
            {
                "title": "Tighten verification reminder",
                "fix_type": "prompt_tweak",
                "slack_narrative": (
                    "Josie's pulumi change shipped without lint on Tuesday and Matt "
                    "hit the same gap Thursday, so code-change tasks keep bypassing "
                    "ruff."
                ),
            },
            {
                "title": "Add triage-first workflow guidance",
                "fix_type": "workflow_fix",
                "slack_narrative": (
                    "Asher asked why the morning-brief workflow never posted and the "
                    "agent proposed a redesign instead of checking logs."
                ),
            },
        ],
    }


def _scorecard_synthesis_fixture() -> dict:
    return {
        "opportunities_found": 2,
        "opportunities": [
            {
                "opportunity_type": "new_persona",
                "title": "Editorial persona for decision memos",
            },
            {
                "opportunity_type": "new_workflow_idea",
                "title": "Guided bootstrap for policy-news monitors",
            },
        ],
        "selected_builds": [
            {
                "opportunity_type": "new_persona",
                "title": "Editorial persona for decision memos",
                "slack_narrative": (
                    "Matt and Dan both asked for crisper decision memos three times "
                    "last week; no existing persona covers that stance."
                ),
            },
        ],
    }


def test_build_scorecard_markdown_has_clean_indentation() -> None:
    # This is the regression bug from the first rendered nightly post:
    # textwrap.dedent with multi-line f-string substitutions lost its
    # common prefix on continuation lines, leaving an 8-space indent on
    # the top-level lines. Every line the renderer produces must start
    # at column 0 (top-level) or column 2 (sub-bullet).
    child_results = [
        {
            "pr_number": 322,
            "pr_url": "https://github.com/paradigmxyz/centaur/pull/322",
            "title": "Tighten verification",
            "slack_narrative": (
                "Josie's pulumi change shipped without lint on Tuesday and Matt "
                "hit the same gap Thursday, so code-change tasks keep bypassing "
                "ruff."
            ),
            "fix_type": "prompt_tweak",
        },
    ]

    md = _build_scorecard_markdown(
        review=_scorecard_review_fixture(),
        synthesis=_scorecard_synthesis_fixture(),
        child_results=child_results,
        notifier_stats={"merged_prs": 1, "deployed_prs": 1, "source_threads_notified": 2},
    )

    for line in md.splitlines():
        if not line.strip():
            continue
        leading_spaces = len(line) - len(line.lstrip(" "))
        assert leading_spaces in {0, 2, 4}, (
            f"unexpected leading whitespace ({leading_spaces} spaces) on line: {line!r}"
        )


def test_build_scorecard_markdown_uses_slack_link_format_not_markdown_link() -> None:
    md = _build_scorecard_markdown(
        review={"tasks_reviewed": 0, "selected_fixes": []},
        synthesis={"opportunities": [], "selected_builds": []},
        child_results=[
            {
                "pr_number": 322,
                "pr_url": "https://github.com/paradigmxyz/centaur/pull/322",
                "title": "Tighten verification",
            }
        ],
        notifier_stats={"merged_prs": 0, "deployed_prs": 0, "source_threads_notified": 0},
    )

    assert "<https://github.com/paradigmxyz/centaur/pull/322|#322>" in md
    # GitHub-style markdown would be the bug. Make sure it is truly gone.
    assert "[#322]" not in md
    assert "](https://github.com" not in md


def test_build_scorecard_markdown_renders_per_fix_narratives() -> None:
    md = _build_scorecard_markdown(
        review=_scorecard_review_fixture(),
        synthesis=_scorecard_synthesis_fixture(),
        child_results=[
            {
                "pr_number": 42,
                "pr_url": "https://example.test/pr/42",
                "title": "Add lint check",
                "slack_narrative": "Josie's Tuesday pulumi change failed CI because ruff didn't run.",
            }
        ],
        notifier_stats={"merged_prs": 0, "deployed_prs": 0, "source_threads_notified": 0},
    )

    # Narratives should land under the Gap Analysis fixes.
    assert "Josie's pulumi change shipped without lint" in md
    assert "Asher asked why the morning-brief" in md
    # ...and under the Learning Synthesis builds.
    assert "Matt and Dan both asked for crisper decision memos" in md
    # ...and next to the opened PR.
    assert "Josie's Tuesday pulumi change failed CI because ruff" in md
    # The _Why:_ prefix signals the sub-bullet type and renders as italic
    # in Slack mrkdwn. Make sure it is wired up.
    assert "_Why:_" in md


def test_build_scorecard_markdown_handles_empty_state() -> None:
    md = _build_scorecard_markdown(
        review={"tasks_reviewed": 0, "selected_fixes": []},
        synthesis={"opportunities": [], "selected_builds": []},
        child_results=[],
        notifier_stats={"merged_prs": 0, "deployed_prs": 0, "source_threads_notified": 0},
    )

    assert "*Self Improve Nightly*" in md
    assert "- none selected" in md
    assert "- none found" in md
    assert "- none opened" in md
    assert "- none" in md
    # No tracebacks, no crashes — the message remains postable.
    assert md.startswith("*Self Improve Nightly*")
