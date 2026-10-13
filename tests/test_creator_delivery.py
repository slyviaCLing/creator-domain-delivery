import pytest

from creator_mail.creator_delivery import (
    CreatorDispatchRequest,
    DeliveryKind,
    DomainNotReady,
    dispatch_creator_message,
)


class RecordingMail:
    def __init__(self, status: str) -> None:
        self.status = status
        self.sent: list[dict[str, str]] = []

    def get_domain(self, domain: str) -> dict:
        return {"verification": {"status": self.status}}

    def send_email(self, **kwargs: str) -> dict:
        self.sent.append(kwargs)
        return {"message_id": "msg_demo_42"}


def request_for(kind: DeliveryKind = DeliveryKind.ASSET_READY) -> CreatorDispatchRequest:
    return CreatorDispatchRequest(
        event_id="order-42-asset-1",
        kind=kind,
        recipient="reader@example.com",
        creator_name="Mira Studio",
        sending_domain="mail.mirastudio.com",
        title="Lightroom Presets",
        destination_url="https://downloads.example.com/order-42",
    )


def test_verified_domain_sends_asset_delivery_with_stable_event_key() -> None:
    mail = RecordingMail("verified")

    result = dispatch_creator_message(request_for(), mail)

    assert result.message_id == "msg_demo_42"
    assert mail.sent == [
        {
            "to": "reader@example.com",
            "subject": "Your download is ready: Lightroom Presets",
            "text": (
                "Mira Studio has prepared your digital asset. "
                "Download it: https://downloads.example.com/order-42"
            ),
            "sender": "updates@mail.mirastudio.com",
            "idempotency_key": "creator-event:order-42-asset-1",
        }
    ]


def test_unverified_domain_blocks_subscriber_mail() -> None:
    mail = RecordingMail("pending")

    with pytest.raises(DomainNotReady):
        dispatch_creator_message(request_for(DeliveryKind.SUBSCRIBER_UPDATE), mail)

    assert mail.sent == []

