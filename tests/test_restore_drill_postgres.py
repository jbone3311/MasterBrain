"""Populated restore-seed checks that need the disposable PostgreSQL gate.

The offline drill-safety tests stay in test_restore_drill.py, which the restore
workflow runs without a database; these run in the main CI gate.
"""

from uuid import uuid4

import pytest
import test_postgres as pg
from test_restore_drill import drill

from email_brain.store import NotFound
from masterbrain.artifact_proposals import ArtifactProposalBatches
from masterbrain.fact_proposals import FactProposalBatches

database = pg.database
pytestmark = pytest.mark.postgres


def test_populated_restore_seed_covers_pending_and_approved_fact_batches(database):
    store, admin = database
    tenants = drill.seed(admin, store, keyword_suffix=uuid4().hex[:8])
    assert [item.fact_proposal_fact_id is not None for item in tenants] == [False, True]
    assert [item.artifact_proposal_link_id is not None for item in tenants] == [False, True]
    for current, foreign in ((tenants[0], tenants[1]), (tenants[1], tenants[0])):
        batches = FactProposalBatches(store)
        preview = batches.preview(current.context, current.fact_proposal_batch_id)
        assert preview["row_count"] == 1


        assert preview["proposals"][0]["proposal_id"] == current.fact_proposal_id
        assert preview["proposals"][0]["status"] == (
            "approved" if current.fact_proposal_fact_id else "proposed"
        )
        assert preview["proposals"][0]["object_id"] == current.fact_proposal_fact_id
        with pytest.raises(NotFound):
            batches.preview(current.context, foreign.fact_proposal_batch_id)
        artifact_batches = ArtifactProposalBatches(store)
        artifact_preview = artifact_batches.preview(
            current.context, current.artifact_proposal_batch_id,
        )
        assert artifact_preview["row_count"] == 1
        assert artifact_preview["proposals"][0]["proposal_id"] == current.artifact_proposal_id
        assert artifact_preview["proposals"][0]["status"] == (
            "approved" if current.artifact_proposal_link_id else "proposed"
        )
        assert artifact_preview["proposals"][0]["object_id"] == (
            current.artifact_proposal_link_id
        )
        with pytest.raises(NotFound):
            artifact_batches.preview(current.context, foreign.artifact_proposal_batch_id)


def test_restore_seed_includes_reviewed_retrievable_xlsx(database):
    store, admin = database
    tenants = drill.seed(admin, store, keyword_suffix=uuid4().hex[:8])
    tenant = tenants[0]
    seeded = drill.seed_email_xlsx_publication(store, tenant)
    drill.verify_restored_xlsx(store, seeded, tenants[1].context)
    with store.transaction(tenant.context) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM brain_email_xlsx_extraction_results "
            "WHERE approval_id=%s", (seeded.approval_id,),
        ).fetchone()["n"] == 1
