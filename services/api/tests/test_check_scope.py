"""Unit tests for api.api_keys.check_scope."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from api.api_keys import APIKeyInfo, check_scope


def _key(scopes: list[str]) -> APIKeyInfo:
    return APIKeyInfo(id="k1", name="test", key_prefix="tst", scopes=scopes, created_by="test")


class TestWildcard:
    def test_star_grants_everything(self):
        key = _key(["*"])
        assert check_scope(key, "admin") is True
        assert check_scope(key, "agent:execute") is True
        assert check_scope(key, "tools", resource="slack") is True


class TestToolScopes:
    def test_tools_star_grants_all_tools(self):
        key = _key(["tools:*"])
        assert check_scope(key, "tools", resource="slack") is True
        assert check_scope(key, "tools", resource="linear") is True

    def test_tools_slack_grants_only_slack(self):
        key = _key(["tools:slack"])
        assert check_scope(key, "tools", resource="slack") is True

    def test_tools_slack_does_not_grant_linear(self):
        key = _key(["tools:slack"])
        assert check_scope(key, "tools", resource="linear") is False


class TestCategoryScopes:
    def test_bare_agent_grants_agent_execute(self):
        key = _key(["agent"])
        assert check_scope(key, "agent:execute") is True

    def test_agent_execute_grants_agent_execute(self):
        key = _key(["agent:execute"])
        assert check_scope(key, "agent:execute") is True

    def test_agent_execute_does_not_grant_agent_stop(self):
        key = _key(["agent:execute"])
        assert check_scope(key, "agent:stop") is False

    def test_admin_scope_grants_admin(self):
        key = _key(["admin"])
        assert check_scope(key, "admin") is True


class TestSandboxScopes:
    def test_sandbox_scopes_grant_tools(self):
        key = _key(["agent", "tools:*"])
        assert check_scope(key, "tools", resource="slack") is True
        assert check_scope(key, "tools", resource="linear") is True

    def test_sandbox_scopes_grant_agent(self):
        key = _key(["agent", "tools:*"])
        assert check_scope(key, "agent:execute") is True

    def test_sandbox_scopes_do_not_grant_admin(self):
        key = _key(["agent", "tools:*"])
        assert check_scope(key, "admin") is False


class TestEmptyScopes:
    def test_empty_scopes_grant_nothing(self):
        key = _key([])
        assert check_scope(key, "admin") is False
        assert check_scope(key, "agent") is False
        assert check_scope(key, "agent:execute") is False
        assert check_scope(key, "tools", resource="slack") is False
