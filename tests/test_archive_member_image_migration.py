from __future__ import annotations

import psycopg
import pytest
import test_postgres as pg

from email_brain.store import Store

database = pg.database


@pytest.mark.postgres
def test_archive_member_image_receipt_schema_is_private_immutable_and_bounded(
    database: tuple[Store, str],
) -> None:
    _, admin = database
    with psycopg.connect(admin) as conn:
        table = conn.execute(
            "SELECT relrowsecurity,relforcerowsecurity "
            "FROM pg_class WHERE oid='brain_archive_member_image_receipts'::regclass"
        ).fetchone()
        assert table == (True, True)

        policies = conn.execute(
            "SELECT policyname FROM pg_policies "
            "WHERE schemaname='public' AND tablename='brain_archive_member_image_receipts'"
        ).fetchall()
        assert policies == [("tenant_isolation",)]

        triggers = conn.execute(
            "SELECT tgname FROM pg_trigger "
            "WHERE tgrelid='brain_archive_member_image_receipts'::regclass "
            "AND NOT tgisinternal"
        ).fetchall()
        assert set(triggers) == {("immutable",), ("protected_no_truncate",)}

        checks = " ".join(
            row[0]
            for row in conn.execute(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conrelid='brain_archive_member_image_receipts'::regclass "
                "AND contype='c' ORDER BY conname"
            ).fetchall()
        )
        for required in (
            "25000000",
            "frame_count = 1",
            "detected_format = image_format",
            "'jpeg'::text",
            "'webp'::text",
            "length(mode)",
            "sandbox-fileos-image-ocr-v1-",
            "request_hash",
        ):
            assert required in checks

        foreign_keys = conn.execute(
            "SELECT count(*) FROM pg_constraint "
            "WHERE conrelid='brain_archive_member_image_receipts'::regclass "
            "AND contype='f'"
        ).fetchone()
        assert foreign_keys == (5,)
