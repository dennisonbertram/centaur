"""Airtable API client for bases, schemas, views, and records."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlparse

import httpx

from centaur_sdk import secret

BASE_URL = "https://api.airtable.com/v0"
META_URL = f"{BASE_URL}/meta"


def _clean_secret(value: str | None) -> str:
    if not value:
        return ""
    return value.strip().splitlines()[0].strip()


def _simplify_cell(value: Any) -> Any:
    """Keep Airtable cell values readable without losing nested data."""
    if isinstance(value, list):
        return [_simplify_cell(item) for item in value]
    if isinstance(value, dict):
        if "url" in value and "filename" in value:
            return {
                "filename": value.get("filename"),
                "url": value.get("url"),
                "type": value.get("type"),
                "size": value.get("size"),
            }
        if "email" in value and "name" in value:
            return {"name": value.get("name"), "email": value.get("email")}
        return {key: _simplify_cell(nested) for key, nested in value.items()}
    return value


def _compact_record(record: dict[str, Any], fields: list[str] | None = None) -> dict[str, Any]:
    raw_fields = record.get("fields") if isinstance(record.get("fields"), dict) else {}
    selected = raw_fields
    if fields:
        selected = {field: raw_fields[field] for field in fields if field in raw_fields}
    return {
        "id": record.get("id"),
        "createdTime": record.get("createdTime"),
        "fields": {key: _simplify_cell(value) for key, value in selected.items()},
    }


def _match_text(value: Any, query: str) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, int, float, bool)):
        return query in str(value).lower()
    if isinstance(value, list):
        return any(_match_text(item, query) for item in value)
    if isinstance(value, dict):
        return any(_match_text(item, query) for item in value.values())
    return query in str(value).lower()


def _path_part(value: str) -> str:
    return quote(value, safe="")


class AirtableClient:
    """Client for Airtable's REST API."""

    def __init__(self, api_key: str | None = None, timeout: float = 30.0):
        self.api_key = _clean_secret(api_key or secret("AIRTABLE_API_KEY", ""))
        if not self.api_key:
            raise RuntimeError(
                "AIRTABLE_API_KEY not set. Add the 1Password item 'Airtable API Key' "
                "or export AIRTABLE_API_KEY for local use."
            )
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | list[tuple[str, Any]] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = self._client.request(method, url, params=params, json=json)
        if response.status_code == 401:
            raise RuntimeError("Airtable API error: AIRTABLE_API_KEY is missing or invalid")
        if response.status_code == 403:
            raise RuntimeError(
                "Airtable API error: AIRTABLE_API_KEY lacks access to this base, table, or scope"
            )
        if response.status_code == 404:
            raise RuntimeError("Airtable API error: base, table, view, or record not found")
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Airtable API error: {exc.response.status_code} - {exc.response.text}"
            ) from exc
        return response.json()

    def parse_url(self, url: str) -> dict[str, str | None]:
        """Parse an Airtable URL into app/base, table, view, page, and record IDs."""
        parsed = urlparse(url)
        parts = [part for part in parsed.path.split("/") if part]
        ids: dict[str, str | None] = {
            "base_id": None,
            "table_id": None,
            "view_id": None,
            "page_id": None,
            "record_id": None,
        }
        for part in parts:
            if part.startswith("app"):
                ids["base_id"] = part
            elif part.startswith("tbl"):
                ids["table_id"] = part
            elif part.startswith("viw"):
                ids["view_id"] = part
            elif part.startswith("pag"):
                ids["page_id"] = part
            elif part.startswith("rec"):
                ids["record_id"] = part
        return {
            "url": url,
            "host": parsed.netloc,
            **ids,
        }

    def whoami(self) -> dict[str, Any]:
        """Return the Airtable user/workspace identity for this API key."""
        return self._request("GET", f"{META_URL}/whoami")

    def list_bases(self, limit: int = 100) -> list[dict[str, Any]]:
        """List bases visible to AIRTABLE_API_KEY."""
        data = self._request("GET", f"{META_URL}/bases")
        bases = data.get("bases", [])
        return bases[: max(1, min(limit, 1000))]

    def find_bases(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Find visible bases by name or base ID."""
        needle = query.lower()
        matches = [
            base
            for base in self.list_bases(limit=1000)
            if needle in str(base.get("name", "")).lower()
            or needle in str(base.get("id", "")).lower()
        ]
        return matches[: max(1, min(limit, 100))]

    def schema(self, base_id: str) -> dict[str, Any]:
        """Get tables, fields, and views for a base."""
        return self._request("GET", f"{META_URL}/bases/{base_id}/tables")

    def list_tables(self, base_id: str) -> list[dict[str, Any]]:
        """List tables, fields, and views in a base."""
        tables = self.schema(base_id).get("tables", [])
        return [
            {
                "id": table.get("id"),
                "name": table.get("name"),
                "description": table.get("description"),
                "fields": table.get("fields", []),
                "views": table.get("views", []),
            }
            for table in tables
        ]

    def find_tables(self, base_id: str, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Find tables or views in a base by name or ID."""
        needle = query.lower()
        matches: list[dict[str, Any]] = []
        for table in self.list_tables(base_id):
            table_hit = needle in str(table.get("name", "")).lower() or needle in str(
                table.get("id", "")
            ).lower()
            view_hits = [
                view
                for view in table.get("views", [])
                if needle in str(view.get("name", "")).lower()
                or needle in str(view.get("id", "")).lower()
            ]
            if table_hit or view_hits:
                matches.append({**table, "matching_views": view_hits})
        return matches[: max(1, min(limit, 100))]

    def list_records(
        self,
        base_id: str,
        table: str,
        view: str | None = None,
        max_records: int = 100,
        fields: list[str] | None = None,
        filter_by_formula: str | None = None,
    ) -> dict[str, Any]:
        """List records from a table or view.

        `table` may be a table ID or table name. `view` may be a view ID or view name.
        """
        max_records = max(1, min(max_records, 1000))
        page_size = min(max_records, 100)
        params: list[tuple[str, Any]] = [("pageSize", page_size)]
        if view:
            params.append(("view", view))
        if filter_by_formula:
            params.append(("filterByFormula", filter_by_formula))
        for field in fields or []:
            params.append(("fields[]", field))

        records: list[dict[str, Any]] = []
        offset: str | None = None
        while len(records) < max_records:
            request_params = list(params)
            if offset:
                request_params.append(("offset", offset))
            data = self._request(
                "GET",
                f"{BASE_URL}/{_path_part(base_id)}/{_path_part(table)}",
                params=request_params,
            )
            records.extend(data.get("records", []))
            offset = data.get("offset")
            if not offset:
                break

        return {
            "base_id": base_id,
            "table": table,
            "view": view,
            "count": min(len(records), max_records),
            "records": [_compact_record(record, fields) for record in records[:max_records]],
            "has_more": bool(offset),
        }

    def get_record(self, base_id: str, table: str, record_id: str) -> dict[str, Any]:
        """Get one Airtable record by ID."""
        record = self._request(
            "GET",
            f"{BASE_URL}/{_path_part(base_id)}/{_path_part(table)}/{_path_part(record_id)}",
        )
        return _compact_record(record)

    def records_from_url(
        self,
        url: str,
        max_records: int = 100,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Read records from an Airtable table/view URL."""
        parsed = self.parse_url(url)
        base_id = parsed.get("base_id")
        table_id = parsed.get("table_id")
        view_id = parsed.get("view_id")
        if not base_id or not table_id:
            raise RuntimeError(
                "Airtable URL must include an app/base ID and table ID, e.g. "
                "https://airtable.com/app.../tbl.../viw..."
            )
        result = self.list_records(
            base_id=base_id,
            table=table_id,
            view=view_id,
            max_records=max_records,
            fields=fields,
        )
        return {"parsed": parsed, **result}

    def search_records(
        self,
        base_id: str,
        table: str,
        query: str,
        view: str | None = None,
        max_records: int = 200,
    ) -> dict[str, Any]:
        """Search visible record fields by text after fetching records."""
        data = self.list_records(base_id, table, view=view, max_records=max_records)
        needle = query.lower()
        matches = [
            record
            for record in data["records"]
            if any(_match_text(value, needle) for value in record.get("fields", {}).values())
        ]
        return {
            "base_id": base_id,
            "table": table,
            "view": view,
            "query": query,
            "searched": data["count"],
            "count": len(matches),
            "records": matches,
        }

    def snapshot_from_url(self, url: str, max_records: int = 50) -> dict[str, Any]:
        """Return a compact table-shaped snapshot for an Airtable table/view URL."""
        data = self.records_from_url(url, max_records=max_records)
        records = data["records"]
        field_order: list[str] = []
        for record in records:
            for field in record.get("fields", {}):
                if field not in field_order:
                    field_order.append(field)
        rows = [
            {
                "id": record.get("id"),
                **{field: record.get("fields", {}).get(field) for field in field_order},
            }
            for record in records
        ]
        return {
            "parsed": data["parsed"],
            "base_id": data["base_id"],
            "table": data["table"],
            "view": data["view"],
            "columns": field_order,
            "count": data["count"],
            "rows": rows,
            "has_more": data["has_more"],
        }

    def close(self) -> None:
        self._client.close()


def _client() -> AirtableClient:
    return AirtableClient()
