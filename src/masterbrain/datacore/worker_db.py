"""One authenticated worker tenant to one optional PostgreSQL login binding."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from email_brain.store import Store


def worker_store(
    store_factory: Callable[..., Store],
    dsn: str,
    tenant_id: UUID,
    tenant_bound_db: bool,
    **store_options: object,
) -> Store:
    """Build a worker Store without letting source data choose a tenant route."""
    if type(tenant_bound_db) is not bool:
        raise ValueError("tenant-bound database mode must be boolean")
    if tenant_bound_db:
        return store_factory(dsn, tenant_dsns={tenant_id: dsn}, **store_options)
    return store_factory(dsn, **store_options)
