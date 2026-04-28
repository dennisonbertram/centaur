from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncpg


DEFAULT_SOURCE = "invest_memo_corpus"
DEFAULT_KIND = "invest_memo_chunk"
DEFAULT_CHUNK_CHARS = 1600
DEFAULT_OVERLAP_CHARS = 220

SEED_DECKS: tuple[dict[str, str], ...] = (
    {
        "company": "Aster Network",
        "stage": "series_a",
        "type_hint": "crypto_protocol",
        "theme": "consumer rollup for creator payments",
        "wedge": "wallet-native subscriptions and low-friction recurring commerce",
        "market": "onchain media monetization",
        "risk": "retention depends on creator distribution concentration",
    },
    {
        "company": "Beacon Ledger",
        "stage": "seed",
        "type_hint": "software_business",
        "theme": "finance workflow tooling for token issuers",
        "wedge": "cap table, vesting, and disclosure ops in one system of record",
        "market": "issuer back-office software",
        "risk": "procurement cycles could stretch without audit integrations",
    },
    {
        "company": "Cinder AI",
        "stage": "series_b",
        "type_hint": "ai_startup",
        "theme": "inference stack for retrieval-heavy enterprise agents",
        "wedge": "cost-aware routing between small and frontier models",
        "market": "enterprise agent infrastructure",
        "risk": "model platform incumbents may compress margins over time",
    },
    {
        "company": "Drift Atlas",
        "stage": "pre-seed",
        "type_hint": "crypto_protocol",
        "theme": "risk engine for onchain structured products",
        "wedge": "shared margin and programmable guardrails across vault strategies",
        "market": "defi risk middleware",
        "risk": "early protocol complexity may slow external integrator adoption",
    },
    {
        "company": "Ember Public Markets",
        "stage": "update",
        "type_hint": "public_equities",
        "theme": "public equities lens on listed crypto proxy companies",
        "wedge": "cross-comparing treasury beta, mining leverage, and software multiples",
        "market": "crypto-adjacent public equities",
        "risk": "equity narratives can drift faster than underlying fundamentals",
    },
    {
        "company": "Fjord Security",
        "stage": "series_a",
        "type_hint": "software_business",
        "theme": "transaction policy engine for institutional wallets",
        "wedge": "human-readable risk policies attached directly to signing flows",
        "market": "institutional wallet security",
        "risk": "long sales cycles with custody buyers may reduce velocity",
    },
    {
        "company": "Glyph Labs",
        "stage": "seed",
        "type_hint": "ai_startup",
        "theme": "document intelligence for diligence workflows",
        "wedge": "turning fragmented PDFs and notes into reusable investment memory",
        "market": "investment workflow automation",
        "risk": "quality bar is high because analysts compare against bespoke manual work",
    },
    {
        "company": "Harbor Credit",
        "stage": "series_c",
        "type_hint": "software_business",
        "theme": "credit underwriting stack for internet-native lenders",
        "wedge": "blending transaction telemetry with operator-entered underwriting notes",
        "market": "modern credit infrastructure",
        "risk": "cyclical credit losses could mask product quality improvements",
    },
    {
        "company": "Ion Settlement",
        "stage": "series_b",
        "type_hint": "crypto_protocol",
        "theme": "cross-border stablecoin settlement rails",
        "wedge": "programmable treasury controls for high-volume B2B payouts",
        "market": "global stablecoin payments",
        "risk": "regulatory fragmentation could slow corridor-by-corridor rollout",
    },
    {
        "company": "Juniper Health AI",
        "stage": "series_a",
        "type_hint": "ai_startup",
        "theme": "clinical staffing copilot with voice and workflow automation",
        "wedge": "shrinking charting time while preserving auditable care notes",
        "market": "healthcare workflow AI",
        "risk": "buyer urgency is strong, but integration depth is expensive",
    },
)


@dataclass(frozen=True)
class TestDeck:
    document_id: str
    memo_name: str
    relative_path: str
    content_hash: str
    content: str
    stage_hint: str
    type_hint: str


@dataclass(frozen=True)
class ChunkRecord:
    source: str
    kind: str
    source_id: str
    content: str
    metadata: dict[str, str | int | bool]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "memo"


def _document_id(relative_path: str) -> str:
    return hashlib.sha256(relative_path.encode("utf-8")).hexdigest()[:24]


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _chunk_text(content: str, chunk_chars: int, overlap_chars: int) -> list[str]:
    normalized = re.sub(r"\n{3,}", "\n\n", content).strip()
    if not normalized:
        return []
    if len(normalized) <= chunk_chars:
        return [normalized]

    paragraphs = [paragraph.strip() for paragraph in normalized.split("\n\n") if paragraph.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= chunk_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
            tail = current[-overlap_chars:] if overlap_chars > 0 else ""
            current = f"{tail}\n\n{paragraph}".strip()
        else:
            chunks.append(paragraph[:chunk_chars])
            current = paragraph[max(chunk_chars - overlap_chars, 0) :]
    if current:
        chunks.append(current)
    return chunks


def _build_test_decks(count: int) -> list[TestDeck]:
    decks: list[TestDeck] = []
    for index in range(count):
        seed = SEED_DECKS[index % len(SEED_DECKS)]
        copy_number = index // len(SEED_DECKS) + 1
        company = seed["company"]
        suffix = f" {copy_number}" if copy_number > 1 else ""
        memo_name = f"{company}{suffix} {seed['stage'].replace('_', ' ').title()} Memo.md"
        relative_path = f"synthetic/investmemos/{_slugify(company)}-{index + 1:02d}.md"

        sections = [
            f"# {company}{suffix}",
            "## Investment Snapshot",
            (
                f"{company}{suffix} is positioned around {seed['theme']}. The current deck frames its wedge as "
                f"{seed['wedge']}. The memo is intentionally synthetic, but it is structured like a real internal "
                "investment note so `list_memos` and `read_memo` have realistic-looking metadata and chunk content "
                "to retrieve."
            ),
            "## Why Now",
            (
                f"The timing argument centers on {seed['market']}. Recent market structure changes create a window "
                "for a narrowly focused product to land with sophisticated early adopters before broader platform "
                "vendors re-bundle the workflow. The team believes speed of execution and opinionated workflow design "
                "matter more than broad configurability at this stage."
            ),
            "## Product",
            (
                f"The product story emphasizes {seed['wedge']}. In this synthetic deck, customers adopt the first "
                "module because it removes an expensive manual step, then expand into adjacent workflows once the "
                "system of record is established. That expansion path is what supports eventual platform economics."
            ),
            "## Market",
            (
                f"Management sizes the opportunity around {seed['market']}. The market section assumes an initial "
                "beachhead with power users who already feel acute workflow pain, followed by expansion into teams "
                "that need compliance, auditability, or automation. The deck repeatedly argues that the category is "
                "under-served by existing generic tools."
            ),
            "## Traction",
            (
                f"Synthetic traction for {company}{suffix} includes twelve design partners, seven weekly active "
                "production accounts, and clear evidence that the product replaces spreadsheets, ad hoc docs, or "
                "manual review loops. Revenue and usage figures are fabricated for testing only, but the prose is long "
                "enough to yield multiple chunks and mimic a real memo body."
            ),
            "## Risks",
            (
                f"The primary risk flagged in this memo is that {seed['risk']}. Secondary concerns include execution "
                "concentration, integration drag, and whether the product can maintain pricing power once incumbents "
                "copy the obvious features. The memo also notes that diligence should separate authentic customer love "
                "from one-off pilot enthusiasm."
            ),
            "## Diligence Questions",
            (
                f"Open questions focus on implementation depth, buyer urgency, and the durability of the initial wedge "
                f"around {seed['wedge']}. The deal team wants reference calls on deployment speed, net retention, and "
                "whether the product becomes more valuable as more workflows move into the system."
            ),
        ]

        content = "\n\n".join(sections).strip()
        decks.append(
            TestDeck(
                document_id=_document_id(relative_path),
                memo_name=memo_name,
                relative_path=relative_path,
                content_hash=_content_hash(content),
                content=content,
                stage_hint=seed["stage"],
                type_hint=seed["type_hint"],
            )
        )
    return decks


def _build_chunk_records(
    decks: list[TestDeck],
    source: str,
    kind: str,
    chunk_chars: int,
    overlap_chars: int,
) -> list[ChunkRecord]:
    records: list[ChunkRecord] = []
    for deck in decks:
        chunks = _chunk_text(deck.content, chunk_chars=chunk_chars, overlap_chars=overlap_chars)
        for index, chunk in enumerate(chunks):
            records.append(
                ChunkRecord(
                    source=source,
                    kind=kind,
                    source_id=f"{deck.document_id}:{deck.content_hash[:12]}:{index}",
                    content=chunk[:8000],
                    metadata={
                        "document_id": deck.document_id,
                        "memo_name": deck.memo_name,
                        "relative_path": deck.relative_path,
                        "content_hash": deck.content_hash,
                        "stage_hint": deck.stage_hint,
                        "type_hint": deck.type_hint,
                        "chunk_index": index,
                    },
                )
            )
    return records


async def _infer_embedding_dimensions(conn: asyncpg.Connection) -> int | None:
    row = await conn.fetchrow(
        """
        SELECT vector_dims(embedding) AS dims
        FROM embeddings
        WHERE embedding IS NOT NULL
        LIMIT 1
        """
    )
    if not row:
        return None
    dims = row["dims"]
    return int(dims) if dims is not None else None


def _zero_vector(dimensions: int) -> str:
    return "[" + ",".join("0" for _ in range(dimensions)) + "]"


async def _write_records(
    *,
    database_url: str,
    source: str,
    kind: str,
    decks: list[TestDeck],
    chunk_records: list[ChunkRecord],
    null_embedding: bool,
    embedding_dimensions: int | None,
) -> dict[str, object]:
    try:
        import asyncpg
    except ImportError as exc:
        raise RuntimeError(
            "asyncpg is required for DB writes. Run with `uv run --with asyncpg python scripts/write_test_investmemos.py ...`."
        ) from exc

    conn = await asyncpg.connect(database_url, command_timeout=60)
    warning: str | None = None
    try:
        resolved_dimensions = embedding_dimensions
        if not null_embedding and resolved_dimensions is None:
            resolved_dimensions = await _infer_embedding_dimensions(conn)
            if resolved_dimensions is None:
                raise RuntimeError(
                    "Could not infer embedding dimensions from existing rows. Re-run with --null-embedding "
                    "or --embedding-dimensions <N>."
                )

        document_rows = [
            (
                source,
                "document",
                deck.document_id,
                deck.content_hash,
                json.dumps(
                    {
                        "memo_name": deck.memo_name,
                        "relative_path": deck.relative_path,
                        "stage_hint": deck.stage_hint,
                        "type_hint": deck.type_hint,
                        "content_hash": deck.content_hash,
                        "char_count": len(deck.content),
                        "chunk_count": sum(
                            1
                            for record in chunk_records
                            if record.metadata["document_id"] == deck.document_id
                        ),
                    }
                ),
            )
            for deck in decks
        ]

        vector_value = None if null_embedding else _zero_vector(resolved_dimensions)
        chunk_rows = [
            (
                record.source,
                record.kind,
                record.source_id,
                record.content,
                json.dumps(record.metadata),
            )
            for record in chunk_records
        ]

        async with conn.transaction():
            await conn.executemany(
                """
                INSERT INTO raw_records (source, kind, external_id, content_hash, data)
                VALUES ($1, $2, $3, $4, $5::jsonb)
                ON CONFLICT (source, kind, external_id, content_hash)
                DO UPDATE SET
                    fetched_at = now(),
                    data = EXCLUDED.data
                """,
                document_rows,
            )

            if null_embedding:
                await conn.executemany(
                    """
                    INSERT INTO embeddings (source, kind, source_id, content, embedding, metadata)
                    VALUES ($1, $2, $3, $4, NULL::vector, $5::jsonb)
                    ON CONFLICT (source, kind, source_id) DO UPDATE SET
                        content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata,
                        created_at = now()
                    """,
                    chunk_rows,
                )
            else:
                await conn.executemany(
                    """
                    INSERT INTO embeddings (source, kind, source_id, content, embedding, metadata)
                    VALUES ($1, $2, $3, $4, $5::vector, $6::jsonb)
                    ON CONFLICT (source, kind, source_id) DO UPDATE SET
                        content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata,
                        created_at = now()
                    """,
                    [
                        (
                            record.source,
                            record.kind,
                            record.source_id,
                            record.content,
                            vector_value,
                            json.dumps(record.metadata),
                        )
                        for record in chunk_records
                    ],
                )

        has_content_tsv = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'embeddings'
                  AND column_name = 'content_tsv'
                  AND table_schema = ANY (current_schemas(false))
            )
            """
        )
        if not has_content_tsv:
            warning = (
                "embeddings.content_tsv is missing in this database; list_memos and read_memo can work, "
                "but search_memos will still fail until that column exists."
            )

        return {
            "documents": len(decks),
            "chunks": len(chunk_records),
            "embedding_mode": "null" if null_embedding else f"zero-vector:{resolved_dimensions}",
            "warning": warning,
        }
    finally:
        await conn.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write deterministic test investmemos records into raw_records and embeddings."
    )
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    parser.add_argument("--source", default=os.getenv("INVEST_MEMO_SOURCE", DEFAULT_SOURCE))
    parser.add_argument("--kind", default=os.getenv("INVEST_MEMO_KIND", DEFAULT_KIND))
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--chunk-chars", type=int, default=DEFAULT_CHUNK_CHARS)
    parser.add_argument("--overlap-chars", type=int, default=DEFAULT_OVERLAP_CHARS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--null-embedding",
        action="store_true",
        help="Insert NULL embeddings instead of zero-vectors. Use this when the table is empty and dimensions cannot be inferred.",
    )
    parser.add_argument(
        "--embedding-dimensions",
        type=int,
        default=None,
        help="Explicit vector size for zero-vector inserts when dims cannot be inferred from existing rows.",
    )
    return parser.parse_args()


async def _main_async(args: argparse.Namespace) -> int:
    decks = _build_test_decks(max(1, args.count))
    chunk_records = _build_chunk_records(
        decks,
        source=args.source,
        kind=args.kind,
        chunk_chars=max(600, min(args.chunk_chars, 6000)),
        overlap_chars=max(0, min(args.overlap_chars, 1200)),
    )

    print(
        f"Prepared {len(decks)} synthetic test memos and {len(chunk_records)} chunk rows "
        f"for source={args.source!r} kind={args.kind!r}."
    )
    for deck in decks[:3]:
        print(f"  - {deck.memo_name} [{deck.document_id}] -> {deck.relative_path}")
    if len(decks) > 3:
        print(f"  ... {len(decks) - 3} more memo(s)")

    if args.dry_run:
        print("Dry run only. No DB writes performed.")
        print(
            "Reminder: this script does not fix the live search schema issue; if embeddings.content_tsv is missing, "
            "search_memos will still fail after the write."
        )
        return 0

    if not args.database_url.strip():
        raise RuntimeError("DATABASE_URL is required unless --dry-run is set.")

    result = await _write_records(
        database_url=args.database_url.strip(),
        source=args.source,
        kind=args.kind,
        decks=decks,
        chunk_records=chunk_records,
        null_embedding=bool(args.null_embedding),
        embedding_dimensions=args.embedding_dimensions,
    )
    print(
        f"Wrote {result['documents']} document row(s) and {result['chunks']} chunk row(s) "
        f"using {result['embedding_mode']} embeddings."
    )
    if result["warning"]:
        print(f"Warning: {result['warning']}")
    return 0


def main() -> int:
    args = _parse_args()
    try:
        return asyncio.run(_main_async(args))
    except Exception as exc:
        print(f"Error: {exc}")
        print(
            "Reminder: this writer does not repair embeddings.content_tsv; it only seeds raw_records and embeddings "
            "for list_memos/read_memo style testing."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
