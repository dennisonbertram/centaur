from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

import structlog

from shared.engineer.agent_loop import AgentLoopError, run_agent_loop
from shared.engineer.git_ops import (
    GitOperationError,
    cleanup_worktree,
    commit_all,
    create_worktree,
    get_diff,
    has_changes,
    push_branch,
    slugify,
)
from shared.engineer.github_pr import GitHubPRError, create_pull_request
from shared.engineer.loop_guards import LoopGuardState
from shared.engineer.models import EngineerResult, Phase
from shared.engineer.prompts import (
    clarifier_prompt,
    engineer_prompt,
    load_repo_guidance,
    planner_prompt,
    researcher_prompt,
    reviewer_prompt,
)
from shared.engineer.session import EngineerSession
from shared.engineer.settings import EngineerSettings, engineer_settings
from shared.engineer.tools import ENGINEER_TOOLS, RESEARCH_TOOLS, ToolExecutor
from shared.engineer.validation_gate import run_validation

log = structlog.get_logger()

MessageCallback = Callable[[str], Awaitable[None]]


async def _noop(_: str) -> None:
    return


class EngineerOrchestrator:
    def __init__(
        self,
        *,
        settings: EngineerSettings | None = None,
        dry_run: bool = False,
        skip_clarify: bool = False,
        model_preference: str | None = None,
    ) -> None:
        self.settings = settings or engineer_settings
        self.repo_root = Path(__file__).resolve().parents[3]
        self.dry_run = dry_run
        self.skip_clarify = skip_clarify
        self.model_preference = model_preference

    def _effective_model(self, session: EngineerSession) -> str:
        preference = (session.model_preference or self.model_preference or "").strip().lower()
        if preference in {"claude", "claude-code"}:
            return self.settings.anthropic_model
        if preference in {"amp", "codex", "pi-mono"}:
            return self.settings.anthropic_model_fallback
        if preference.startswith("claude-"):
            return preference
        return self.settings.anthropic_model

    def _preference_hint(self, session: EngineerSession) -> str:
        preference = (session.model_preference or self.model_preference or "").strip()
        if not preference:
            return ""
        return f"\nOperator model preference: {preference}"

    def _phase_guard(self, *, max_turns: int | None = None) -> LoopGuardState:
        return LoopGuardState(
            max_turns=max_turns or self.settings.max_turns_per_phase,
            max_tool_calls_total=self.settings.max_tool_calls_total,
            max_wall_time_seconds=self.settings.max_wall_time_seconds,
            max_consecutive_tool_failures=self.settings.max_consecutive_tool_failures,
        )

    async def run(
        self,
        session: EngineerSession,
        *,
        post_message: MessageCallback | None = None,
    ) -> EngineerResult:
        """Drive the full engineer workflow."""
        send = post_message or _noop
        repo_guidance = load_repo_guidance(self.repo_root)
        effort = self.settings.anthropic_effort

        try:
            model = self._effective_model(session)
            if session.model_preference or self.model_preference:
                await send(
                    f"Using model: `{model}` (effort: {effort})"
                )

            branch = (
                f"{self.settings.branch_prefix}/{session.run_id[:8]}"
                f"/{slugify(session.task, max_len=32)}"
            )
            session.branch_name = branch
            session.worktree = await create_worktree(
                self.repo_root, branch, self.settings.github_base_branch
            )
            executor = ToolExecutor(
                session.worktree,
                command_allowlist=self.settings.command_allowlist_set,
                protected_paths=self.settings.protected_write_path_list,
            )

            session.phase = Phase.RESEARCH
            await send("Researching the codebase...")

            research = await run_agent_loop(
                api_key=self.settings.anthropic_api_key,
                model=model,
                max_tokens=self.settings.anthropic_max_tokens,
                system_prompt=researcher_prompt(repo_guidance),
                user_prompt=f"Task: {session.task}{self._preference_hint(session)}",
                tools=RESEARCH_TOOLS,
                execute_tool=executor.execute,
                guard_state=self._phase_guard(),
                effort=effort,
            )
            session.research_brief = research.text or f"Implement task: {session.task}"
            await send(
                f"Research complete ({research.turns} turns, {research.tool_calls} tool calls)"
            )

            session.phase = Phase.PLAN
            await send("Planning implementation...")

            plan_result = await run_agent_loop(
                api_key=self.settings.anthropic_api_key,
                model=model,
                max_tokens=self.settings.anthropic_max_tokens,
                system_prompt=planner_prompt(repo_guidance),
                user_prompt=(
                    f"Task: {session.task}\n\n"
                    f"Research findings:\n{session.research_brief}"
                ),
                tools=[],
                execute_tool=None,
                guard_state=self._phase_guard(max_turns=4),
                effort=effort,
            )
            session.plan = plan_result.text or ""
            await send("Plan ready.")

            if self.skip_clarify:
                session.spec = (
                    f"Task: {session.task}\n\n"
                    f"Research brief:\n{session.research_brief}\n\n"
                    f"Plan:\n{session.plan}"
                )
                await send("Skipping clarification, using research + plan as spec.")
            else:
                session.phase = Phase.CLARIFY
                session.spec = await self._clarify_loop(session, repo_guidance, send)

            session.phase = Phase.IMPLEMENT
            feedback = ""

            for iteration in range(self.settings.max_iterations):
                session.iteration = iteration + 1
                await send(
                    f"Implementing (iteration {session.iteration}/{self.settings.max_iterations})..."
                )

                _ = await run_agent_loop(
                    api_key=self.settings.anthropic_api_key,
                    model=model,
                    max_tokens=self.settings.anthropic_max_tokens,
                    system_prompt=engineer_prompt(
                        repo_guidance, session.spec, session.plan, feedback
                    ),
                    user_prompt=f"Implement: {session.task}{self._preference_hint(session)}",
                    tools=ENGINEER_TOOLS,
                    execute_tool=executor.execute,
                    guard_state=self._phase_guard(),
                    effort=effort,
                )

                await send("Running validation...")
                report = await run_validation(session.worktree)
                validation_feedback = (
                    "All checks passed." if report.success else report.to_feedback()
                )
                if not report.success:
                    feedback = validation_feedback
                    await send(
                        f"Validation failed, iterating...\n```\n{validation_feedback[:1000]}\n```"
                    )
                    continue

                diff_text = await get_diff(session.worktree)
                if not diff_text.strip():
                    feedback = "No code diff found. Apply concrete code changes."
                    await send("No diff produced, iterating...")
                    continue

                await send(f"Diff: {diff_text.count(chr(10))} lines changed")

                session.phase = Phase.REVIEW
                await send("Reviewing changes...")
                review = await run_agent_loop(
                    api_key=self.settings.anthropic_api_key,
                    model=model,
                    max_tokens=self.settings.anthropic_max_tokens,
                    system_prompt=reviewer_prompt(
                        repo_guidance, session.spec, session.plan
                    ),
                    user_prompt=(
                        f"Review the changes on this branch.\n\n"
                        f"Validation results: {validation_feedback}\n\n"
                        f"Diff:\n```\n{diff_text}\n```"
                    ),
                    tools=RESEARCH_TOOLS,
                    execute_tool=executor.execute,
                    guard_state=self._phase_guard(max_turns=12),
                    effort=effort,
                )

                review_text = review.text.strip()
                if review_text.upper().startswith("APPROVED"):
                    await send("Review: APPROVED")
                    break
                feedback = f"Reviewer feedback:\n{review_text}"
                session.phase = Phase.IMPLEMENT
                await send(f"Review: CHANGES_REQUESTED\n{review_text[:500]}")
            else:
                session.phase = Phase.FAILED
                session.error = "Review loop did not reach approval"
                return EngineerResult(
                    run_id=session.run_id,
                    success=False,
                    status="failed",
                    branch_name=session.branch_name,
                    error=session.error,
                )

            if not await has_changes(session.worktree):
                session.phase = Phase.FAILED
                session.error = "No changes to commit"
                return EngineerResult(
                    run_id=session.run_id,
                    success=False,
                    status="failed",
                    branch_name=session.branch_name,
                    error=session.error,
                )

            session.phase = Phase.PUBLISH
            commit_msg = f"feat: {slugify(session.task, max_len=60)}"
            await commit_all(session.worktree, commit_msg)
            await send(f"Committed: {commit_msg}")

            if self.dry_run:
                await send(
                    f"DRY RUN — skipping push/PR.\n"
                    f"Worktree preserved at: {session.worktree}\n"
                    f"Branch: {session.branch_name}\n"
                    f"Inspect with: cd {session.worktree} && git log --oneline -3 && git diff HEAD~1"
                )
                session.phase = Phase.DONE
                return EngineerResult(
                    run_id=session.run_id,
                    success=True,
                    status="completed",
                    branch_name=session.branch_name,
                    summary="Dry run completed — changes committed locally, PR skipped.",
                )

            await send("Pushing branch and opening PR...")
            await push_branch(session.worktree, session.branch_name)
            pr_url = await create_pull_request(
                token=self.settings.github_token,
                owner=self.settings.github_repo_owner,
                repo=self.settings.github_repo_name,
                base_branch=self.settings.github_base_branch,
                head_branch=session.branch_name,
                title=f"feat: {session.task[:72]}",
                body=(
                    f"## Task\n{session.task}\n\n"
                    f"## Plan\n{session.plan[:2000]}\n\n"
                    f"## Specification\n{session.spec[:2000]}\n\n"
                    f"Run ID: `{session.run_id}`\n"
                    f"Iterations: {session.iteration}\n"
                ),
            )

            session.pr_url = pr_url
            session.phase = Phase.DONE
            return EngineerResult(
                run_id=session.run_id,
                success=True,
                status="completed",
                branch_name=session.branch_name,
                pr_url=pr_url,
                summary="Engineer workflow completed successfully",
            )

        except (AgentLoopError, GitOperationError, GitHubPRError, RuntimeError) as exc:
            log.exception("engineer_run_failed", run_id=session.run_id, error=str(exc))
            session.phase = Phase.FAILED
            session.error = str(exc)
            return EngineerResult(
                run_id=session.run_id,
                success=False,
                status="failed",
                branch_name=session.branch_name,
                error=str(exc),
            )
        finally:
            should_cleanup = (
                session.worktree is not None
                and self.settings.cleanup_worktree
                and not self.dry_run
            )
            if should_cleanup:
                assert session.worktree is not None
                await cleanup_worktree(self.repo_root, session.worktree)

    async def _clarify_loop(
        self,
        session: EngineerSession,
        repo_guidance: str,
        send: MessageCallback,
    ) -> str:
        """Run the clarification interview loop. Returns the final spec."""
        from anthropic import AsyncAnthropic

        messages: list[dict[str, str]] = [
            {
                "role": "user",
                "content": (
                    f"Task: {session.task}{self._preference_hint(session)}\n\n"
                    f"Research brief:\n{session.research_brief}\n\n"
                    f"Plan:\n{session.plan}"
                ),
            }
        ]

        system = clarifier_prompt(repo_guidance, session.research_brief)
        client = AsyncAnthropic(api_key=self.settings.anthropic_api_key)

        for _ in range(10):
            response = await client.messages.create(
                model=self._effective_model(session),
                max_tokens=self.settings.anthropic_max_tokens,
                system=system,
                messages=messages,  # type: ignore[arg-type]
            )

            assistant_text = ""
            for block in response.content:
                if getattr(block, "type", "") == "text":
                    assistant_text += getattr(block, "text", "")
            assistant_text = assistant_text.strip()

            if assistant_text.startswith("SPEC_COMPLETE"):
                spec = assistant_text[len("SPEC_COMPLETE"):].strip()
                await send(f"Specification finalized:\n```\n{spec[:2000]}\n```")
                return spec

            await send(assistant_text)
            messages.append({"role": "assistant", "content": assistant_text})

            user_reply = await session.wait_for_user_reply(
                timeout=float(self.settings.max_wall_time_seconds)
            )
            if user_reply is None:
                await send("Timed out waiting for reply. Proceeding with current information.")
                return self._fallback_spec(session, messages)

            session.clarify_history.append({"role": "user", "content": user_reply})
            messages.append({"role": "user", "content": user_reply})

        return self._fallback_spec(session, messages)

    @staticmethod
    def _fallback_spec(session: EngineerSession, messages: list[dict[str, str]]) -> str:
        return (
            f"Task: {session.task}\n\n"
            f"Research brief:\n{session.research_brief}\n\n"
            f"Plan:\n{session.plan}\n\n"
            "Conversation:\n"
            + "\n".join(f"{m['role']}: {m['content'][:500]}" for m in messages)
        )
