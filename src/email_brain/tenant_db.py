"""Private, bounded database credential routing for opt-in tenant-isolated service use."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any
from uuid import UUID

from psycopg.conninfo import conninfo_to_dict

from email_brain.processing_controller import private_bytes


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate tenant database configuration key")
        result[key] = value
    return result


def _dsn_details(dsn: object) -> tuple[str, tuple[str, str, str, str]]:
    if not isinstance(dsn, str) or not dsn or len(dsn) > 8192:
        raise ValueError("invalid tenant database DSN")
    try:
        values = conninfo_to_dict(dsn)
    except Exception:
        # A libpq diagnostic may embed the supplied credential. Never echo it.
        raise ValueError("invalid tenant database DSN") from None
    if any(not values.get(key) for key in ("user", "password", "dbname")) or any(
        key in values for key in ("options", "service", "passfile")
    ):
        raise ValueError("tenant database DSNs require explicit credentials and database")
    target = tuple(str(values.get(key) or "") for key in ("host", "hostaddr", "port", "dbname"))
    return str(values["user"]), (target[0], target[1], target[2], target[3])


@dataclass(frozen=True)
class TenantDbRoutes:
    """An immutable server-owned map; its DSNs are deliberately absent from repr/logs."""

    identity_dsn: str = field(repr=False)
    tenant_dsns: Mapping[UUID, str] = field(repr=False)

    @classmethod
    def from_file(cls, path: Path) -> TenantDbRoutes:
        try:
            raw = json.loads(private_bytes(path, 65536), object_pairs_hook=_unique_pairs)
        except (OSError, UnicodeError, json.JSONDecodeError, RecursionError):
            raise ValueError("invalid private tenant database configuration") from None
        if (
            not isinstance(raw, dict)
            or set(raw) != {"version", "identity_dsn", "tenants"}
            or type(raw["version"]) is not int
            or raw["version"] != 1
            or not isinstance(raw["tenants"], dict)
            or not 1 <= len(raw["tenants"]) <= 64
        ):
            raise ValueError("invalid tenant database configuration shape")
        identity_user, target = _dsn_details(raw["identity_dsn"])
        users = {identity_user}
        routes: dict[UUID, str] = {}
        for key, dsn in raw["tenants"].items():
            try:
                tenant_id = UUID(key)
            except (ValueError, TypeError, AttributeError):
                raise ValueError("invalid tenant database route") from None
            if str(tenant_id) != key or tenant_id in routes:
                raise ValueError("invalid tenant database route")
            user, data_target = _dsn_details(dsn)
            if user in users or data_target != target:
                raise ValueError("tenant database routes must use distinct logins on one database")
            users.add(user)
            routes[tenant_id] = dsn
        return cls(raw["identity_dsn"], MappingProxyType(routes))
