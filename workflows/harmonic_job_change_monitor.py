from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from api.workflow_engine import WorkflowContext

WORKFLOW_NAME = "harmonic_job_change_monitor"
DEFAULT_MONITORS_FILE = "/app/workflows/harmonic_job_change_monitors.json"
DEFAULT_POLL_INTERVAL_SECONDS = 3600

SCHEDULE = {
    "interval_seconds": DEFAULT_POLL_INTERVAL_SECONDS,
    # The workflow posts directly to each configured monitor channel; this
    # bootstrap destination just keeps the scheduler row active.
    "slack_channel": "C0AEAL252BD",
    "input": {"config_path": DEFAULT_MONITORS_FILE},
}


@dataclass(frozen=True)
class Monitor:
    name: str
    linkedin_url: str
    slack_channel: str
    enabled: bool = True

    @property
    def key(self) -> str:
        return self.linkedin_url


@dataclass(frozen=True)
class Snapshot:
    company: str
    title: str
    visibility: str
    comparable: bool

    @property
    def signature(self) -> str:
        return f"{self.company}|{self.title}"

    @property
    def display(self) -> str:
        left = self.company or "unknown company"
        right = self.title or "unknown title"
        if not self.company and not self.title:
            return "no current company/title"
        return f"{left} / {right}"


@dataclass
class Input:
    config_path: str = DEFAULT_MONITORS_FILE


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_linkedin_url(value: str) -> str:
    url = _clean_text(value)
    if not url:
        return ""
    url = url.replace("http://", "https://")
    url = url.rstrip("/")
    if "linkedin.com/" in url and not url.startswith("https://"):
        url = f"https://{url}"
    return url


def _monitor_sort_key(monitor: Monitor) -> tuple[str, str, str]:
    return (monitor.slack_channel, monitor.linkedin_url, monitor.name)


def _load_monitors(path: str) -> list[Monitor]:
    payload = json.loads(Path(path).read_text())
    raw_monitors = payload.get("monitors") if isinstance(payload, dict) else None
    if not isinstance(raw_monitors, list):
        return []

    monitors: list[Monitor] = []
    for item in raw_monitors:
        if not isinstance(item, dict):
            continue
        linkedin_url = _normalize_linkedin_url(item.get("linkedin_url"))
        slack_channel = _clean_text(item.get("slack_channel")).lstrip("#")
        if not linkedin_url or not slack_channel:
            continue
        name = _clean_text(item.get("name")) or linkedin_url.rsplit("/", 1)[-1]
        enabled = bool(item.get("enabled", True))
        monitors.append(
            Monitor(
                name=name,
                linkedin_url=linkedin_url,
                slack_channel=slack_channel,
                enabled=enabled,
            )
        )

    return sorted((monitor for monitor in monitors if monitor.enabled), key=_monitor_sort_key)


def _pick_current_experience(person: dict[str, Any]) -> dict[str, Any] | None:
    experiences = person.get("experience") or []
    if not isinstance(experiences, list):
        return None

    current_candidates: list[dict[str, Any]] = []
    fallback_candidates: list[dict[str, Any]] = []
    for item in experiences:
        if not isinstance(item, dict):
            continue
        fallback_candidates.append(item)

        is_current = item.get("is_current")
        end_date = item.get("end_date") or item.get("endDate")
        if is_current is True or (is_current is None and not end_date):
            current_candidates.append(item)

    if current_candidates:
        return current_candidates[0]
    if fallback_candidates:
        return fallback_candidates[0]
    return None


def _company_name(experience: dict[str, Any]) -> str:
    company = experience.get("company")
    if isinstance(company, dict):
        for key in ("name", "display_name", "displayName"):
            value = _clean_text(company.get(key))
            if value:
                return value
    for key in ("company_name", "companyName", "organization_name", "organizationName"):
        value = _clean_text(experience.get(key))
        if value:
            return value
    return ""


def _extract_snapshot(person: dict[str, Any]) -> Snapshot:
    visibility = _clean_text(person.get("linkedin_profile_visibility_type"))
    current_experience = _pick_current_experience(person)
    if current_experience is not None:
        company = _company_name(current_experience)
        title = _clean_text(current_experience.get("title") or current_experience.get("role"))
        return Snapshot(
            company=company,
            title=title,
            visibility=visibility,
            comparable=bool(company or title),
        )

    if visibility == "PRIVATE_OR_NONEXISTENT":
        return Snapshot(company="", title="", visibility=visibility, comparable=False)

    return Snapshot(company="", title="", visibility=visibility, comparable=True)


def _job_change_message(
    name: str,
    linkedin_url: str,
    previous: Snapshot,
    current: Snapshot,
) -> str | None:
    if not previous.comparable or not current.comparable:
        return None
    if previous.signature == current.signature:
        return None
    return f"{name}: {previous.display} -> {current.display}\n{linkedin_url}"


async def handler(inp: Input, ctx: WorkflowContext) -> dict[str, Any]:
    iteration = 0
    last_seen: dict[str, Snapshot] = {}

    while True:
        monitors = await ctx.step(
            f"load_config_{iteration}",
            lambda: _load_monitors(inp.config_path or DEFAULT_MONITORS_FILE),
            step_kind="gather",
        )

        for monitor in monitors:
            try:
                person = await ctx.tools.harmonic.enrich_person(
                    linkedin_url=monitor.linkedin_url,
                )
            except Exception as exc:
                ctx.log(
                    "harmonic_job_change_monitor_fetch_failed",
                    linkedin_url=monitor.linkedin_url,
                    error=str(exc),
                )
                continue

            if not isinstance(person, dict):
                ctx.log(
                    "harmonic_job_change_monitor_invalid_response",
                    linkedin_url=monitor.linkedin_url,
                    response_type=type(person).__name__,
                )
                continue

            current = _extract_snapshot(person)
            previous = last_seen.get(monitor.key)
            if previous is not None:
                message = _job_change_message(
                    monitor.name,
                    monitor.linkedin_url,
                    previous,
                    current,
                )
                if message:
                    await ctx.post_to_slack(monitor.slack_channel, message)
                    ctx.log(
                        "harmonic_job_change_detected",
                        linkedin_url=monitor.linkedin_url,
                        previous=previous.display,
                        current=current.display,
                        slack_channel=monitor.slack_channel,
                    )

            last_seen[monitor.key] = current

        await ctx.sleep(
            f"wait_{iteration}",
            dt.timedelta(seconds=DEFAULT_POLL_INTERVAL_SECONDS),
        )
        iteration += 1
