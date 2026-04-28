"""Verify synthetic memos written by write_test_investmemos.py round-trip cleanly.

Uses the real InvestmemosClient read path (list_memos + read_memo), filters to
the synthetic relative_path prefix so it is safe against a populated DB, and
checks that every paragraph of the deterministic source content survives the
chunk-reassemble round trip. Chunk overlap means strict equality is not
expected; "no paragraph lost" is the meaningful invariant.

Exit 0 on clean pass. Nonzero on any mismatch.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools" / "research" / "investmemos"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from client import InvestmemosClient  # noqa: E402
from write_test_investmemos import _build_test_decks  # noqa: E402


SYNTHETIC_PREFIX = "synthetic/investmemos/"
EXPECTED_COUNT = 10


def _fail(msg: str) -> int:
    print(f"FAIL: {msg}", file=sys.stderr)
    return 1


def main() -> int:
    if not os.environ.get("DATABASE_URL"):
        return _fail("DATABASE_URL not set")

    client = InvestmemosClient()

    listing = client.list_memos(limit=200)
    if listing.get("status") != "ok":
        return _fail(f"list_memos error: {listing}")

    synthetic = [
        m for m in listing.get("memos", [])
        if (m.get("relative_path") or "").startswith(SYNTHETIC_PREFIX)
    ]
    if len(synthetic) != EXPECTED_COUNT:
        return _fail(
            f"expected {EXPECTED_COUNT} synthetic memos via list_memos, got {len(synthetic)}"
        )
    print(f"OK list_memos: {len(synthetic)} synthetic memos visible")

    expected_decks = {d.document_id: d for d in _build_test_decks(EXPECTED_COUNT)}
    listed_ids = {m["document_id"] for m in synthetic}
    if listed_ids != set(expected_decks):
        missing = set(expected_decks) - listed_ids
        extra = listed_ids - set(expected_decks)
        return _fail(
            f"list_memos returned a different set of document_ids than the writer would produce. "
            f"missing={sorted(missing)} extra={sorted(extra)}"
        )

    target = synthetic[0]
    document_id = target["document_id"]
    expected_deck = expected_decks[document_id]

    read = client.read_memo(memo=document_id, max_chars=120000)
    if read.get("status") != "ok":
        return _fail(f"read_memo error: {read}")

    got = read.get("content") or ""
    expected_paragraphs = [p.strip() for p in expected_deck.content.split("\n\n") if p.strip()]
    missing = [p for p in expected_paragraphs if p not in got]
    if missing:
        sample = missing[0][:120]
        return _fail(
            f"read_memo lost {len(missing)}/{len(expected_paragraphs)} paragraph(s). "
            f"first missing: {sample!r}"
        )

    print(
        f"OK read_memo: {document_id} ({read.get('memo_name')}) round-tripped "
        f"({len(expected_paragraphs)} paragraphs, {read.get('chars')} chars)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
