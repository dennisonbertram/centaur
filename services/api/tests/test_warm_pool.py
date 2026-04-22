from __future__ import annotations

import pytest

import api.warm_pool as warm_pool


@pytest.fixture(autouse=True)
def clear_warm_pool_state():
    warm_pool._pool.clear()
    yield
    warm_pool._pool.clear()
    if warm_pool._replenish_task is not None:
        warm_pool._replenish_task.cancel()
        warm_pool._replenish_task = None


@pytest.mark.asyncio
async def test_start_replenish_loop_skips_unsupported_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeBackend:
        name = "fake"
        supports_warm_pool = False

    monkeypatch.setattr("api.warm_pool.get_backend", lambda: FakeBackend())

    async def unexpected_get_assigned_sandbox_ids() -> set[str]:
        raise AssertionError("unsupported backends should not start the warm pool loop")

    monkeypatch.setattr(
        "api.warm_pool._get_assigned_sandbox_ids",
        unexpected_get_assigned_sandbox_ids,
    )

    task = await warm_pool.start_replenish_loop()

    assert task is None


@pytest.mark.asyncio
async def test_claim_container_skips_kubernetes_persona_or_repo_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeBackend:
        name = "kubernetes"
        supports_warm_pool = True

    monkeypatch.setattr("api.warm_pool.get_backend", lambda: FakeBackend())
    warm_pool._pool.append(warm_pool.WarmContainer(sandbox_id="sandbox-1", harness="amp", engine="amp"))

    claimed = await warm_pool.claim_container("thread-1", "amp", persona="eng")

    assert claimed is None
    assert len(warm_pool._pool) == 1
