#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_JSON_FILE="$(mktemp)"
TOOLS_JSON_FILE="$(mktemp)"
cleanup() {
  rm -f "$RUNTIME_JSON_FILE" "$TOOLS_JSON_FILE"
}
trap cleanup EXIT

"$SCRIPT_DIR/qa-agent-runtime-flow.sh" --with-agent-tool-smoke "$@" > "$RUNTIME_JSON_FILE"
python3 "$SCRIPT_DIR/qa-full-tools.py" > "$TOOLS_JSON_FILE"

python3 - "$RUNTIME_JSON_FILE" "$TOOLS_JSON_FILE" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

runtime = json.loads(Path(sys.argv[1]).read_text())
full_tools = json.loads(Path(sys.argv[2]).read_text())
combined = {
    "ok": bool(runtime.get("ok")) and not full_tools.get("mismatches"),
    "runtime_flow": runtime,
    "full_tools": full_tools,
}
print(json.dumps(combined, indent=2))
PY
