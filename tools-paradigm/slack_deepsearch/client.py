"""Parallel Slack deep-search helper."""

from __future__ import annotations

import importlib.util
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


class SlackDeepSearchClient:
    """Generate many query variants and rank Slack hits."""

    _MAX_PARALLEL = 8
    _MAX_QUERIES = 60

    def _load_slack_client(self):
        import sys

        candidate_roots = [
            Path("/app/tools-paradigm/slack"),
            Path(__file__).resolve().parent.parent / "slack",
        ]
        slack_dir = next((p for p in candidate_roots if (p / "client.py").exists()), None)
        if slack_dir is None:
            raise RuntimeError("slack package not found")

        parent = str(slack_dir.parent)
        if parent not in sys.path:
            sys.path.insert(0, parent)

        module_name = slack_dir.name
        module = importlib.import_module(f"{module_name}.client")
        return module.SlackClient()

    @staticmethod
    def _clean(values: list[str] | None) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for raw in values or []:
            value = (raw or "").strip()
            if not value:
                continue
            norm = value.lower()
            if norm in seen:
                continue
            seen.add(norm)
            out.append(value)
        return out

    @staticmethod
    def _date_clause(days: int | None) -> str:
        if days is None:
            return ""
        cutoff = (datetime.now(UTC) - timedelta(days=days)).date().isoformat()
        return f" after:{cutoff}"

    def _build_queries(
        self,
        *,
        seed: str,
        aliases: list[str],
        founders: list[str],
        competitors: list[str],
        sector_terms: list[str],
        channels: list[str],
        time_windows_days: list[int | None],
    ) -> list[str]:
        channel_tokens = [f"in:#{c.lstrip('#')}" for c in channels] or ["in:#investing"]
        date_clauses = [self._date_clause(d) for d in time_windows_days] or [""]

        base_terms = [seed, *aliases]
        competitor_clause = (
            f"({' OR '.join(competitors[:4])})" if competitors else ""
        )
        sector_clause = f"({' OR '.join(sector_terms[:4])})" if sector_terms else ""

        templates = [
            "{term}",
            "{term} thesis",
            "{term} thoughts",
            "{term} take",
            "{term} round",
            "{term} raising",
            "{term} valuation",
            "{term} revenue",
            "{term} traction",
            "{term} metrics",
            "{term} founder",
            "{term} team",
            "{term} strategy",
            "{term} moat",
            "{term} distribution",
            "{term} risks",
            "{term} pass",
        ]
        if competitor_clause:
            templates.extend(
                [
                    "{term} " + competitor_clause,
                    "{term} competition " + competitor_clause,
                ]
            )
        if sector_clause:
            templates.extend(
                [
                    "{term} " + sector_clause,
                    sector_clause + " " + "{term}",
                ]
            )

        queries: list[str] = []
        for term in base_terms:
            for template in templates:
                base = template.format(term=term).strip()
                for channel in channel_tokens:
                    for date_clause in date_clauses:
                        queries.append(f"{base} {channel}{date_clause}".strip())

        for founder in founders:
            for channel in channel_tokens:
                for date_clause in date_clauses:
                    queries.append(f"{founder} {channel}{date_clause}".strip())

        # Deduplicate while preserving order
        seen: set[str] = set()
        deduped: list[str] = []
        for query in queries:
            key = re.sub(r"\s+", " ", query.lower()).strip()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(query)
        return deduped

    @staticmethod
    def _ts_to_datetime(ts: str) -> datetime | None:
        try:
            return datetime.fromtimestamp(float(ts), tz=UTC)
        except Exception:
            return None

    def _query_once(self, slack_client: Any, query: str, max_results_per_query: int) -> dict[str, Any]:
        try:
            results = slack_client.search_messages(query=query, max_results=max_results_per_query)
            return {"query": query, "status": "ok", "results": results}
        except Exception as exc:
            return {"query": query, "status": "error", "error": str(exc), "results": []}

    def run(
        self,
        seed: str,
        aliases: list[str] | None = None,
        founders: list[str] | None = None,
        competitors: list[str] | None = None,
        sector_terms: list[str] | None = None,
        channels: list[str] | None = None,
        time_windows_days: list[int | None] | None = None,
        max_queries: int = 40,
        max_results_per_query: int = 10,
        top_n: int = 15,
        parallelism: int = 6,
    ) -> dict[str, Any]:
        """Run heavy Slack fan-out and return ranked deduped permalinks."""
        seed = (seed or "").strip()
        if not seed:
            return {"status": "error", "error": "seed cannot be empty"}

        aliases_clean = self._clean(aliases)
        founders_clean = self._clean(founders)
        competitors_clean = self._clean(competitors)
        sector_clean = self._clean(sector_terms)
        channels_clean = self._clean(channels) or [
            "investing",
            "investment-sourcing",
            "investing-publics",
            "investment-talent",
            "miq-investing-and-research",
        ]
        windows = time_windows_days or [90, 365, None]

        queries = self._build_queries(
            seed=seed,
            aliases=aliases_clean,
            founders=founders_clean,
            competitors=competitors_clean,
            sector_terms=sector_clean,
            channels=channels_clean,
            time_windows_days=windows,
        )
        max_q = max(1, min(max_queries, self._MAX_QUERIES))
        selected_queries = queries[:max_q]
        parallel = max(1, min(parallelism, self._MAX_PARALLEL))

        slack_client = self._load_slack_client()

        query_runs: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=parallel) as executor:
            futures = [
                executor.submit(
                    self._query_once,
                    slack_client,
                    query,
                    max_results_per_query,
                )
                for query in selected_queries
            ]
            for future in as_completed(futures):
                query_runs.append(future.result())

        by_permalink: dict[str, dict[str, Any]] = {}
        for run in query_runs:
            if run.get("status") != "ok":
                continue
            query = run.get("query", "")
            for item in run.get("results", []):
                permalink = item.get("permalink") or ""
                if not permalink:
                    continue
                ts = item.get("timestamp") or ""
                record = by_permalink.get(permalink)
                if record is None:
                    by_permalink[permalink] = {
                        "permalink": permalink,
                        "channel": item.get("channel", ""),
                        "channel_id": item.get("channel_id", ""),
                        "user": item.get("user", ""),
                        "text": item.get("text", ""),
                        "timestamp": ts,
                        "thread_ts": item.get("thread_ts"),
                        "reply_count": item.get("reply_count", 0),
                        "hit_count": 1,
                        "queries": [query],
                    }
                else:
                    record["hit_count"] += 1
                    if query not in record["queries"]:
                        record["queries"].append(query)

        now = datetime.now(UTC)
        ranked: list[dict[str, Any]] = []
        for value in by_permalink.values():
            dt = self._ts_to_datetime(value.get("timestamp", ""))
            age_days = ((now - dt).total_seconds() / 86400.0) if dt else 9999.0
            recency = 1.0 / (1.0 + max(age_days, 0.0))
            score = float(value.get("hit_count", 1)) + recency
            value["score"] = round(score, 4)
            value["age_days"] = round(age_days, 2) if age_days != 9999.0 else None
            ranked.append(value)

        ranked.sort(key=lambda x: (x.get("score", 0.0), x.get("hit_count", 0)), reverse=True)
        top = ranked[: max(1, top_n)]

        failures = [run for run in query_runs if run.get("status") != "ok"]
        return {
            "status": "ok" if top else ("partial" if by_permalink else "error"),
            "summary": {
                "queries_generated": len(queries),
                "queries_executed": len(selected_queries),
                "queries_failed": len(failures),
                "unique_hits": len(by_permalink),
                "returned": len(top),
            },
            "top_results": top,
            "failures": failures[:10],
            "executed_queries": selected_queries,
        }


def _client() -> SlackDeepSearchClient:
    return SlackDeepSearchClient()

