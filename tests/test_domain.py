from __future__ import annotations

import unittest
from uuid import uuid4

from email_brain.domain.models import ActionCommand, ActionKind


class ActionCommandTests(unittest.TestCase):
    def test_send_and_permanent_delete_are_intrinsically_high_risk(self) -> None:
        for kind in (ActionKind.SEND, ActionKind.DELETE_PERMANENTLY):
            command = ActionCommand(
                tenant_id=uuid4(),
                account_id=uuid4(),
                kind=kind,
                target_ids=("message-1",),
                parameters={},
                idempotency_key=uuid4(),
            )
            self.assertTrue(command.intrinsically_high_risk)

    def test_label_is_not_intrinsically_high_risk(self) -> None:
        command = ActionCommand(
            tenant_id=uuid4(),
            account_id=uuid4(),
            kind=ActionKind.APPLY_LABEL,
            target_ids=("message-1",),
            parameters={"label": "_GrokBot/Review"},
            idempotency_key=uuid4(),
        )
        self.assertFalse(command.intrinsically_high_risk)


if __name__ == "__main__":
    unittest.main()
