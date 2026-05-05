from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).with_name("sourcer.py")
SPEC = importlib.util.spec_from_file_location("sourcer_script", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
sourcer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sourcer)


def _linkedin_review(**overrides: object) -> dict[str, object]:
    review: dict[str, object] = {
        "read_order_version": sourcer.LINKEDIN_REVIEW_VERSION,
        "years_experience": 9,
        "header_summary": "Engineering Manager at Signal Corp in Los Angeles, CA.",
        "experience_summary": "About 9 years total with infra/platform roles and recent line management.",
        "education_summary": "BS in Computer Science from UCLA.",
        "company_history_summary": "Signal Corp after scaling infra at Stripe and Segment.",
        "location_verdict": "pass",
        "seniority_verdict": "pass",
        "scope_verdict": "pass",
        "school_signal_verdict": "strong",
        "company_signal_verdict": "strong",
    }
    review.update(overrides)
    return review


def _write_candidates(tmp_path: Path) -> Path:
    payload = {
        "candidates": [
            {
                "name": "Alex Example",
                "title": "Engineering Manager",
                "company": "Signal Corp",
                "linkedin": "https://www.linkedin.com/in/alex-example",
                "location": "Los Angeles, CA",
                "notes": "Strong technical manager with defense background.",
                "linkedin_review": _linkedin_review(),
                "scores": {
                    "title_correspondence": 5,
                    "educational_foundation": 4,
                    "professional_trajectory": 4,
                    "talent_density": 5,
                    "timing_window": 3,
                },
            }
        ]
    }
    input_path = tmp_path / "candidates.json"
    input_path.write_text(json.dumps(payload))
    return input_path


def _write_result(payload: dict) -> dict:
    updated_rows = len(payload["rows"]) + 1
    updated_cells = updated_rows * len(payload["headers"])
    return {
        "updated_rows": updated_rows,
        "updated_cells": updated_cells,
        "row_count": len(payload["rows"]),
        "header_count": len(payload["headers"]),
    }


def test_coerce_spreadsheet_reference_accepts_id_and_url():
    assert sourcer._coerce_spreadsheet_reference("sheet-123") == "sheet-123"
    assert (
        sourcer._coerce_spreadsheet_reference(
            "https://docs.google.com/spreadsheets/d/sheet-456/edit#gid=0"
        )
        == "sheet-456"
    )


def test_publish_appends_refined_tab_with_change_log(tmp_path, monkeypatch, capsys):
    input_path = _write_candidates(tmp_path)
    calls: list[tuple[str, str, dict]] = []

    class FakeToolClient:
        def __init__(self, api_url: str, api_key: str | None):
            assert api_url == "http://api:8000"
            assert api_key is None

        def call(self, tool: str, method: str, payload: dict):
            calls.append((tool, method, payload))
            if method == "sheets_create":
                raise AssertionError("refine flow should not create a new spreadsheet")
            if method == "sheets_write_table":
                return _write_result(payload)
            return {"ok": True}

    monkeypatch.setattr(sourcer, "ToolClient", FakeToolClient)

    args = argparse.Namespace(
        input=str(input_path),
        title="Platform Engineer Sourcer Shortlist",
        share_with=None,
        spreadsheet_id="https://docs.google.com/spreadsheets/d/sheet-123/edit#gid=0",
        tab_name="Refined - LA Denver",
        change_log_entry=[
            "Narrowed the company set to defense-adjacent engineering orgs.",
            "Dropped product-heavy candidates and prioritized hands-on leaders.",
        ],
        top_n=None,
        dry_run=False,
        api_url="http://api:8000",
        api_key=None,
    )

    assert sourcer._command_publish(args) == 0

    assert [method for _, method, _ in calls] == [
        "sheets_add_tab",
        "sheets_write_table",
        "sheets_write_table",
    ]
    assert calls[0][2] == {"spreadsheet_id": "sheet-123", "title": "Refined - LA Denver"}
    assert calls[1][2]["headers"] == sourcer.CHANGE_LOG_HEADERS
    assert calls[1][2]["start_cell"] == "A1"
    assert calls[2][2]["headers"] == sourcer.HEADERS
    assert calls[2][2]["start_cell"] == "A5"

    printed = json.loads(capsys.readouterr().out)
    assert printed["spreadsheet_id"] == "sheet-123"
    assert printed["created_new_sheet"] is False
    assert printed["tab_name"] == "Refined - LA Denver"
    assert printed["change_log"] == args.change_log_entry
    assert printed["table_start_cell"] == "A5"
    assert printed["existing_tab_reused"] is False
    assert printed["change_log_write"]["updated_rows"] == 3
    assert printed["candidate_table_write"]["updated_rows"] == 2


def test_score_requires_linkedin_review_for_linkedin_candidates(tmp_path):
    payload = {
        "candidates": [
            {
                "name": "Alex Example",
                "title": "Engineering Manager",
                "company": "Signal Corp",
                "linkedin": "https://www.linkedin.com/in/alex-example",
                "location": "Los Angeles, CA",
                "scores": {
                    "title_correspondence": 5,
                    "educational_foundation": 4,
                    "professional_trajectory": 4,
                    "talent_density": 5,
                    "timing_window": 3,
                },
            }
        ]
    }
    input_path = tmp_path / "missing-review.json"
    input_path.write_text(json.dumps(payload))

    args = argparse.Namespace(input=str(input_path), output=None, top_n=None)

    with pytest.raises(SystemExit):
        sourcer._command_score(args)


def test_score_rejects_weak_company_signal_for_linkedin_candidates(tmp_path):
    payload = {
        "candidates": [
            {
                "name": "Alex Example",
                "title": "Engineering Manager",
                "company": "Signal Corp",
                "linkedin": "https://www.linkedin.com/in/alex-example",
                "location": "Los Angeles, CA",
                "linkedin_review": _linkedin_review(company_signal_verdict="weak"),
                "scores": {
                    "title_correspondence": 5,
                    "educational_foundation": 4,
                    "professional_trajectory": 4,
                    "talent_density": 5,
                    "timing_window": 3,
                },
            }
        ]
    }
    input_path = tmp_path / "weak-company-signal.json"
    input_path.write_text(json.dumps(payload))

    args = argparse.Namespace(input=str(input_path), output=None, top_n=None)

    with pytest.raises(SystemExit):
        sourcer._command_score(args)


def test_score_allows_zero_years_experience_for_entry_level_candidates(tmp_path, capsys):
    payload = {
        "candidates": [
            {
                "name": "Alex Example",
                "title": "Software Engineer",
                "company": "Signal Corp",
                "linkedin": "https://www.linkedin.com/in/alex-example",
                "location": "Los Angeles, CA",
                "linkedin_review": _linkedin_review(
                    years_experience=0,
                    experience_summary="New graduate with internship experience and hands-on projects.",
                ),
                "scores": {
                    "title_correspondence": 5,
                    "educational_foundation": 4,
                    "professional_trajectory": 3,
                    "talent_density": 4,
                    "timing_window": 4,
                },
            }
        ]
    }
    input_path = tmp_path / "zero-years.json"
    input_path.write_text(json.dumps(payload))

    args = argparse.Namespace(input=str(input_path), output=None, top_n=None)

    assert sourcer._command_score(args) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["candidates"][0]["linkedin_review"]["years_experience"] == 0.0


def test_score_top_n_ignores_invalid_low_ranked_linkedin_candidate(tmp_path, capsys):
    payload = {
        "candidates": [
            {
                "name": "Top Candidate",
                "title": "Engineering Manager",
                "company": "Signal Corp",
                "linkedin": "https://www.linkedin.com/in/top-candidate",
                "location": "Los Angeles, CA",
                "linkedin_review": _linkedin_review(),
                "scores": {
                    "title_correspondence": 5,
                    "educational_foundation": 5,
                    "professional_trajectory": 5,
                    "talent_density": 5,
                    "timing_window": 5,
                },
            },
            {
                "name": "Low Ranked Invalid",
                "title": "Engineering Manager",
                "company": "Signal Corp",
                "linkedin": "https://www.linkedin.com/in/low-ranked-invalid",
                "location": "Los Angeles, CA",
                "scores": {
                    "title_correspondence": 1,
                    "educational_foundation": 1,
                    "professional_trajectory": 1,
                    "talent_density": 1,
                    "timing_window": 1,
                },
            },
        ]
    }
    input_path = tmp_path / "top-n-valid-only.json"
    input_path.write_text(json.dumps(payload))

    args = argparse.Namespace(input=str(input_path), output=None, top_n=1)

    assert sourcer._command_score(args) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["count"] == 1
    assert printed["candidates"][0]["name"] == "Top Candidate"


def test_publish_rejects_invalid_linkedin_review_before_gsuite_calls(tmp_path, monkeypatch):
    payload = {
        "candidates": [
            {
                "name": "Alex Example",
                "title": "Engineering Manager",
                "company": "Signal Corp",
                "linkedin": "https://www.linkedin.com/in/alex-example",
                "location": "Los Angeles, CA",
                "linkedin_review": _linkedin_review(company_signal_verdict="weak"),
                "scores": {
                    "title_correspondence": 5,
                    "educational_foundation": 4,
                    "professional_trajectory": 4,
                    "talent_density": 5,
                    "timing_window": 3,
                },
            }
        ]
    }
    input_path = tmp_path / "invalid-publish.json"
    input_path.write_text(json.dumps(payload))
    calls: list[tuple[str, str, dict]] = []

    class FakeToolClient:
        def __init__(self, api_url: str, api_key: str | None):
            calls.append(("init", api_url, {"api_key": api_key}))

        def call(self, tool: str, method: str, payload: dict):
            calls.append((tool, method, payload))
            return {"ok": True}

    monkeypatch.setattr(sourcer, "ToolClient", FakeToolClient)

    args = argparse.Namespace(
        input=str(input_path),
        title="Platform Engineer Sourcer Shortlist",
        share_with="owner@example.com",
        spreadsheet_id=None,
        tab_name=None,
        change_log_entry=[],
        top_n=None,
        dry_run=False,
        api_url="http://api:8000",
        api_key=None,
    )

    with pytest.raises(SystemExit):
        sourcer._command_publish(args)

    assert calls == []


def test_publish_allows_non_linkedin_candidate_without_review(tmp_path, monkeypatch, capsys):
    payload = {
        "candidates": [
            {
                "name": "GitHub Only",
                "title": "Engineering Manager",
                "company": "Signal Corp",
                "location": "Los Angeles, CA",
                "notes": "Strong open-source footprint.",
                "scores": {
                    "title_correspondence": 4,
                    "educational_foundation": 3,
                    "professional_trajectory": 4,
                    "talent_density": 4,
                    "timing_window": 3,
                },
            }
        ]
    }
    input_path = tmp_path / "non-linkedin-publish.json"
    input_path.write_text(json.dumps(payload))
    calls: list[tuple[str, str, dict]] = []

    class FakeToolClient:
        def __init__(self, api_url: str, api_key: str | None):
            assert api_url == "http://api:8000"
            assert api_key is None

        def call(self, tool: str, method: str, payload: dict):
            calls.append((tool, method, payload))
            if method == "sheets_create":
                return {"spreadsheet_id": "sheet-123", "url": "https://docs.google.com/spreadsheets/d/sheet-123"}
            if method == "sheets_add_tab":
                return {"ok": True}
            if method == "sheets_write_table":
                return _write_result(payload)
            if method == "drive_share":
                return {"ok": True}
            raise AssertionError(f"Unexpected method: {method}")

    monkeypatch.setattr(sourcer, "ToolClient", FakeToolClient)

    args = argparse.Namespace(
        input=str(input_path),
        title="Platform Engineer Sourcer Shortlist",
        share_with="owner@example.com",
        spreadsheet_id=None,
        tab_name=None,
        change_log_entry=[],
        top_n=None,
        dry_run=False,
        api_url="http://api:8000",
        api_key=None,
    )

    assert sourcer._command_publish(args) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["count"] == 1
    assert printed["rows"][0]["Name"] == "GitHub Only"
    assert [method for _, method, _ in calls] == ["sheets_create", "sheets_add_tab", "sheets_write_table", "drive_share"]


def test_score_accepts_acceptable_verdicts(tmp_path, capsys):
    payload = {
        "candidates": [
            {
                "name": "Alex Example",
                "title": "Engineering Manager",
                "company": "Signal Corp",
                "linkedin": "https://www.linkedin.com/in/alex-example",
                "location": "Los Angeles, CA",
                "linkedin_review": _linkedin_review(
                    school_signal_verdict="acceptable",
                    company_signal_verdict="acceptable",
                ),
                "scores": {
                    "title_correspondence": 5,
                    "educational_foundation": 4,
                    "professional_trajectory": 4,
                    "talent_density": 5,
                    "timing_window": 3,
                },
            }
        ]
    }
    input_path = tmp_path / "acceptable-verdicts.json"
    input_path.write_text(json.dumps(payload))

    args = argparse.Namespace(input=str(input_path), output=None, top_n=None)

    assert sourcer._command_score(args) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["candidates"][0]["linkedin_review"]["school_signal_verdict"] == "acceptable"
    assert printed["candidates"][0]["linkedin_review"]["company_signal_verdict"] == "acceptable"


def test_publish_requires_share_recipient_for_new_sheet(tmp_path):
    input_path = _write_candidates(tmp_path)
    args = argparse.Namespace(
        input=str(input_path),
        title="Platform Engineer Sourcer Shortlist",
        share_with=None,
        spreadsheet_id=None,
        tab_name=None,
        change_log_entry=[],
        top_n=None,
        dry_run=True,
        api_url="http://api:8000",
        api_key=None,
    )

    with pytest.raises(SystemExit):
        sourcer._command_publish(args)


def test_publish_requires_change_log_for_existing_sheet(tmp_path):
    input_path = _write_candidates(tmp_path)
    args = argparse.Namespace(
        input=str(input_path),
        title="Platform Engineer Sourcer Shortlist",
        share_with=None,
        spreadsheet_id="sheet-123",
        tab_name="Refined Replay",
        change_log_entry=[],
        top_n=None,
        dry_run=True,
        api_url="http://api:8000",
        api_key=None,
    )

    with pytest.raises(SystemExit):
        sourcer._command_publish(args)


def test_publish_replays_duplicate_existing_tab(tmp_path, monkeypatch, capsys):
    input_path = _write_candidates(tmp_path)
    calls: list[tuple[str, str, dict]] = []

    class FakeToolClient:
        def __init__(self, api_url: str, api_key: str | None):
            pass

        def call(self, tool: str, method: str, payload: dict):
            calls.append((tool, method, payload))
            if method == "sheets_add_tab":
                raise RuntimeError(
                    "gsuite.sheets_add_tab failed: A sheet with the name "
                    "'Refined Replay' already exists."
                )
            if method == "sheets_write_table":
                return _write_result(payload)
            raise AssertionError(f"Unexpected method: {method}")

    monkeypatch.setattr(sourcer, "ToolClient", FakeToolClient)

    args = argparse.Namespace(
        input=str(input_path),
        title="Platform Engineer Sourcer Shortlist",
        share_with=None,
        spreadsheet_id="sheet-123",
        tab_name="Refined Replay",
        change_log_entry=["Replay of the same refined slate after a failed publish."],
        top_n=None,
        dry_run=False,
        api_url="http://api:8000",
        api_key=None,
    )

    assert sourcer._command_publish(args) == 0

    assert [method for _, method, _ in calls] == [
        "sheets_add_tab",
        "sheets_write_table",
        "sheets_write_table",
    ]
    printed = json.loads(capsys.readouterr().out)
    assert printed["existing_tab_reused"] is True
    assert printed["spreadsheet_id"] == "sheet-123"
    assert printed["change_log_write"]["updated_rows"] == 2
    assert printed["candidate_table_write"]["updated_rows"] == 2


def test_publish_checks_change_log_write_counts(tmp_path, monkeypatch):
    input_path = _write_candidates(tmp_path)

    class FakeToolClient:
        def __init__(self, api_url: str, api_key: str | None):
            pass

        def call(self, tool: str, method: str, payload: dict):
            if method == "sheets_write_table" and payload["headers"] == sourcer.CHANGE_LOG_HEADERS:
                return {"updated_rows": 1, "updated_cells": 2}
            if method == "sheets_write_table":
                return _write_result(payload)
            return {"ok": True}

    monkeypatch.setattr(sourcer, "ToolClient", FakeToolClient)

    args = argparse.Namespace(
        input=str(input_path),
        title="Platform Engineer Sourcer Shortlist",
        share_with=None,
        spreadsheet_id="sheet-123",
        tab_name="Refined Counts",
        change_log_entry=["One refinement note."],
        top_n=None,
        dry_run=False,
        api_url="http://api:8000",
        api_key=None,
    )

    with pytest.raises(SystemExit):
        sourcer._command_publish(args)


def test_publish_checks_candidate_table_write_counts(tmp_path, monkeypatch):
    input_path = _write_candidates(tmp_path)

    class FakeToolClient:
        def __init__(self, api_url: str, api_key: str | None):
            pass

        def call(self, tool: str, method: str, payload: dict):
            if method != "sheets_write_table":
                return {"ok": True}
            if payload["headers"] == sourcer.HEADERS:
                return {"updated_rows": 1, "updated_cells": len(sourcer.HEADERS)}
            return _write_result(payload)

    monkeypatch.setattr(sourcer, "ToolClient", FakeToolClient)

    args = argparse.Namespace(
        input=str(input_path),
        title="Platform Engineer Sourcer Shortlist",
        share_with=None,
        spreadsheet_id="sheet-123",
        tab_name="Refined Counts",
        change_log_entry=["One refinement note."],
        top_n=None,
        dry_run=False,
        api_url="http://api:8000",
        api_key=None,
    )

    with pytest.raises(SystemExit):
        sourcer._command_publish(args)
