from __future__ import annotations

import pytest
import yaml

from api.proxy_config import (
    PG_LISTEN_PORT_BASE,
    assign_pg_listen_ports,
    render_proxy_yaml,
)
from api.tool_manager import (
    GcpAuthSecret,
    HeaderSecret,
    PgDsnSecret,
    _parse_secret,
    _parse_secrets,
)


# ── parser ──────────────────────────────────────────────────────────────────


def test_parser_accepts_string_for_back_compat() -> None:
    secret = _parse_secret("OPENAI_API_KEY")
    assert isinstance(secret, HeaderSecret)
    assert secret.name == "OPENAI_API_KEY"
    assert secret.secret_ref == "OPENAI_API_KEY"
    assert secret.replacer == "OPENAI_API_KEY"


def test_parser_typed_header_overrides_defaults() -> None:
    secret = _parse_secret(
        {
            "type": "header",
            "name": "CUSTOM_KEY",
            "replacer": "PLACEHOLDER",
            "secret_ref": "OP_REF",
        }
    )
    assert isinstance(secret, HeaderSecret)
    assert secret.replacer == "PLACEHOLDER"
    assert secret.secret_ref == "OP_REF"


def test_parser_typed_header_defaults_replacer_and_ref_to_name() -> None:
    secret = _parse_secret({"type": "header", "name": "API_KEY"})
    assert isinstance(secret, HeaderSecret)
    assert secret.replacer == "API_KEY"
    assert secret.secret_ref == "API_KEY"


def test_parser_typed_gcp_auth() -> None:
    secret = _parse_secret(
        {"type": "gcp_auth", "name": "GCP_GCLOUD_CREDENTIAL"}
    )
    assert isinstance(secret, GcpAuthSecret)
    assert secret.secret_ref == "GCP_GCLOUD_CREDENTIAL"


def test_parser_typed_pg_dsn() -> None:
    secret = _parse_secret(
        {
            "type": "pg_dsn",
            "name": "DATABASE_URL",
            "secret_ref": "INVESTMEMOS_PG",
            "database": "investmemos",
        }
    )
    assert isinstance(secret, PgDsnSecret)
    assert secret.name == "DATABASE_URL"
    assert secret.secret_ref == "INVESTMEMOS_PG"
    assert secret.database == "investmemos"


def test_parser_pg_dsn_requires_database() -> None:
    with pytest.raises(ValueError, match="requires a non-empty 'database'"):
        _parse_secret({"type": "pg_dsn", "name": "DATABASE_URL"})


def test_parser_rejects_unknown_type() -> None:
    with pytest.raises(ValueError, match="unknown secret type"):
        _parse_secret({"type": "bogus", "name": "X"})


def test_parser_rejects_missing_name() -> None:
    with pytest.raises(ValueError, match="missing 'name'"):
        _parse_secret({"type": "header"})


def test_parser_mixed_array() -> None:
    parsed = _parse_secrets(
        [
            "RAW_STRING",
            {"type": "pg_dsn", "name": "DATABASE_URL", "database": "memo_db"},
            {"type": "gcp_auth", "name": "GCP_GCLOUD_CREDENTIAL"},
        ]
    )
    assert [type(s).__name__ for s in parsed] == [
        "HeaderSecret",
        "PgDsnSecret",
        "GcpAuthSecret",
    ]


# ── port allocation ─────────────────────────────────────────────────────────


def test_pg_listen_ports_are_sequential_and_sorted_by_name() -> None:
    secrets = [
        (PgDsnSecret("ZEBRA", "ZEBRA", "z"), ()),
        (PgDsnSecret("ALPHA", "ALPHA", "a"), ()),
        (PgDsnSecret("MIKE", "MIKE", "m"), ()),
    ]
    ports = assign_pg_listen_ports(secrets)
    assert ports == {
        "ALPHA": PG_LISTEN_PORT_BASE,
        "MIKE": PG_LISTEN_PORT_BASE + 1,
        "ZEBRA": PG_LISTEN_PORT_BASE + 2,
    }


def test_pg_listen_ports_deduplicates() -> None:
    secrets = [
        (PgDsnSecret("DB", "DB", "db"), ()),
        (PgDsnSecret("DB", "DB", "db"), ()),  # duplicate (from infra + tool)
    ]
    ports = assign_pg_listen_ports(secrets)
    assert ports == {"DB": PG_LISTEN_PORT_BASE}


# ── renderer ────────────────────────────────────────────────────────────────


def test_render_emits_header_and_gcp_auth_transforms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FIREWALL_MANAGER_SECRET_SOURCE", "env")
    secrets = [
        (
            HeaderSecret("OPENAI_API_KEY", "OPENAI_API_KEY", "OPENAI_API_KEY"),
            ("api.openai.com",),
        ),
        (
            GcpAuthSecret("GCP_GCLOUD_CREDENTIAL", "GCP_GCLOUD_CREDENTIAL"),
            ("storage.googleapis.com",),
        ),
    ]
    cfg = yaml.safe_load(render_proxy_yaml(secrets))
    names = [t["name"] for t in cfg["transforms"]]
    assert names == ["allowlist", "secrets", "gcp_auth", "header_allowlist"]
    secrets_block = next(t for t in cfg["transforms"] if t["name"] == "secrets")
    assert secrets_block["config"]["secrets"][0]["proxy_value"] == "OPENAI_API_KEY"
    assert secrets_block["config"]["secrets"][0]["rules"] == [
        {"host": "api.openai.com"}
    ]


def test_render_omits_managed_transforms_when_no_matching_secrets() -> None:
    cfg = yaml.safe_load(render_proxy_yaml([]))
    assert [t["name"] for t in cfg["transforms"]] == [
        "allowlist",
        "header_allowlist",
    ]
    assert "postgres" not in cfg


def test_render_emits_postgres_listeners_with_env_refs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FIREWALL_MANAGER_SECRET_SOURCE", "env")
    secrets = [
        (PgDsnSecret("DATABASE_URL", "DB_REF", "memo_db"), ()),
        (PgDsnSecret("ANALYTICS_PG", "AN_REF", "analytics"), ()),
    ]
    cfg = yaml.safe_load(render_proxy_yaml(secrets))
    listeners = cfg["postgres"]
    assert [l["name"] for l in listeners] == ["analytics_pg", "database_url"]
    assert listeners[0]["listen"] == "0.0.0.0:5432"
    assert listeners[1]["listen"] == "0.0.0.0:5433"
    # upstream.dsn uses the secret_ref directly so iron-proxy can resolve it
    # from env (or 1Password, depending on FIREWALL_MANAGER_SECRET_SOURCE).
    assert listeners[0]["upstream"] == {"dsn": {"type": "env", "var": "AN_REF"}}
    assert listeners[1]["upstream"] == {"dsn": {"type": "env", "var": "DB_REF"}}
    assert listeners[0]["client"] == {
        "user": "app_user",
        "password_env": "PG_PROXY_PASSWORD_ANALYTICS_PG",
    }


def test_render_postgres_upstream_dsn_uses_onepassword_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FIREWALL_MANAGER_SECRET_SOURCE", "onepassword")
    monkeypatch.setenv("OP_VAULT", "ai-agents")
    secrets = [(PgDsnSecret("DATABASE_URL", "INVESTMEMOS_PG_DSN", "memo_db"), ())]
    cfg = yaml.safe_load(render_proxy_yaml(secrets))
    upstream = cfg["postgres"][0]["upstream"]["dsn"]
    assert upstream["type"] == "1password"
    assert upstream["secret_ref"] == "op://ai-agents/INVESTMEMOS_PG_DSN/credential"


def test_render_with_onepassword_source_emits_op_ref(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FIREWALL_MANAGER_SECRET_SOURCE", "onepassword-connect")
    monkeypatch.setenv("OP_VAULT", "engineering")
    secrets = [
        (
            GcpAuthSecret("GCP_GCLOUD_CREDENTIAL", "GCP_GCLOUD_CREDENTIAL"),
            ("storage.googleapis.com",),
        )
    ]
    cfg = yaml.safe_load(render_proxy_yaml(secrets))
    gcp = next(t for t in cfg["transforms"] if t["name"] == "gcp_auth")
    assert gcp["config"]["keyfile"]["type"] == "1password_connect"
    assert (
        gcp["config"]["keyfile"]["secret_ref"]
        == "op://engineering/GCP_GCLOUD_CREDENTIAL/credential"
    )


def test_render_groups_header_secret_hosts_when_repeated() -> None:
    secrets = [
        (
            HeaderSecret("GITHUB_TOKEN", "GITHUB_TOKEN", "GITHUB_TOKEN"),
            ("github.com", "api.github.com"),
        ),
        (
            HeaderSecret("GITHUB_TOKEN", "GITHUB_TOKEN", "GITHUB_TOKEN"),
            ("uploads.github.com",),
        ),
    ]
    cfg = yaml.safe_load(render_proxy_yaml(secrets))
    secrets_block = next(t for t in cfg["transforms"] if t["name"] == "secrets")
    entries = secrets_block["config"]["secrets"]
    assert len(entries) == 1
    assert {r["host"] for r in entries[0]["rules"]} == {
        "github.com",
        "api.github.com",
        "uploads.github.com",
    }
