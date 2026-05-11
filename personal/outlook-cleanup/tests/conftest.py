from datetime import datetime, timezone

import pytest

from outlook_cleanup.models import EmailAddress, Message


def make_message(
    *,
    sender: str = "alice@example.com",
    name: str | None = "Alice",
    subject: str = "Hello",
    body: str = "Hi there",
    tab: str = "focused",
    msg_id: str = "msg-1",
) -> Message:
    return Message(
        id=msg_id,
        subject=subject,
        sender=EmailAddress(name=name, address=sender.lower()),
        body_preview=body,
        received_at=datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
        is_read=False,
        inference_classification=tab,
        has_attachments=False,
    )


@pytest.fixture
def message_factory():
    return make_message
