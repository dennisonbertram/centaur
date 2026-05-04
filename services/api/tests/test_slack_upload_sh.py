"""Regression tests for the sandbox `slack-upload` helper."""

from __future__ import annotations

import json
import stat
import subprocess
from pathlib import Path


SLACK_UPLOAD_SH = Path(__file__).resolve().parents[2] / "sandbox" / "slack-upload.sh"


def _write_fake_call(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _run_helper(tmp_path: Path, file_path: Path) -> subprocess.CompletedProcess[str]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()

    script = f"""#!/bin/bash
set -euo pipefail
count_file={json.dumps(str(tmp_path / 'call-count'))}
count=0
if [ -f \"$count_file\" ]; then
  count=$(cat \"$count_file\")
fi
count=$((count + 1))
printf '%s' \"$count\" > \"$count_file\"

case \"$count\" in
  1)
    printf '%s\\n' '{{"error":"http_error","status":500}}'
    exit 1
    ;;
  2)
    printf '%s' "$3" > {json.dumps(str(tmp_path / 'fallback-body.json'))}
    jq -e '.filename == "artifact.mp4" and (.content_base64 | length > 0)' {json.dumps(str(tmp_path / 'fallback-body.json'))} >/dev/null
    printf '%s\\n' '{{"permalink":"https://slack.com/archives/C123/p456"}}'
    ;;
esac
"""
    _write_fake_call(fake_bin / "call", script)

    env = {
        "PATH": f"{fake_bin}:/usr/bin:/bin",
        "SLACK_CHANNEL": "C123",
        "SLACK_THREAD_TS": "123.456",
    }

    return subprocess.run(
        ["bash", str(SLACK_UPLOAD_SH), str(file_path)],
        check=False,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )


def test_slack_upload_retries_with_inline_content_when_file_upload_fails(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    artifact = artifact_dir / "artifact.mp4"
    artifact.write_bytes(b"video-bytes")

    result = _run_helper(tmp_path, Path("artifacts/artifact.mp4"))

    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout.strip() == "https://slack.com/archives/C123/p456"

    fallback_payload = json.loads((tmp_path / "fallback-body.json").read_text())
    assert fallback_payload["channel"] == "C123"
    assert fallback_payload["thread_ts"] == "123.456"
    assert fallback_payload["filename"] == "artifact.mp4"
    assert "file_path" not in fallback_payload


def test_slack_upload_uses_absolute_file_path_for_primary_upload(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "nested"
    artifact_dir.mkdir()
    artifact = artifact_dir / "artifact.mp4"
    artifact.write_bytes(b"video-bytes")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()

    script = f"""#!/bin/bash
set -euo pipefail
printf '%s' "$3" > {json.dumps(str(tmp_path / 'primary-body.json'))}
jq -e '.file_path | startswith("/")' {json.dumps(str(tmp_path / 'primary-body.json'))} >/dev/null
jq -e '.file_path | endswith("/artifact.mp4")' {json.dumps(str(tmp_path / 'primary-body.json'))} >/dev/null
printf '%s\\n' '{{"permalink":"https://slack.com/archives/C123/p123"}}'
"""
    _write_fake_call(fake_bin / "call", script)

    result = subprocess.run(
        ["bash", str(SLACK_UPLOAD_SH), str(Path("nested") / "artifact.mp4"), "done"],
        check=False,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={
            "PATH": f"{fake_bin}:/usr/bin:/bin",
            "SLACK_CHANNEL": "C123",
            "SLACK_THREAD_TS": "123.456",
        },
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout.strip() == "https://slack.com/archives/C123/p123"

    primary_payload = json.loads((tmp_path / "primary-body.json").read_text())
    assert primary_payload["comment"] == "done"
    assert primary_payload["thread_ts"] == "123.456"
