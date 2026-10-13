from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

try:
    from pydantic import BaseModel, Field
except ModuleNotFoundError:
    BaseModel = None  # type: ignore[assignment,misc]


class DeliveryKind(StrEnum):
    ASSET_READY = "asset_ready"
    SUBSCRIBER_UPDATE = "subscriber_update"
    PROCESSING_COMPLETE = "processing_complete"


if BaseModel is not None:
    class DomainOnboardingRequest(BaseModel):
        domain: str = Field(pattern=r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


    class CreatorDispatchRequest(BaseModel):
        event_id: str = Field(min_length=1, max_length=120)
        kind: DeliveryKind
        recipient: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
        creator_name: str = Field(min_length=1, max_length=100)
        sending_domain: str = Field(pattern=r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
        title: str = Field(min_length=1, max_length=160)
        destination_url: str = Field(pattern=r"^https://")


    class DispatchResult(BaseModel):
        message_id: str
        kind: DeliveryKind
else:
    _DOMAIN_PATTERN = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
    _EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    @dataclass
    class DomainOnboardingRequest:
        domain: str

        def __post_init__(self) -> None:
            if not _DOMAIN_PATTERN.fullmatch(self.domain):
                raise ValueError("domain must be a valid domain name")


    @dataclass
    class CreatorDispatchRequest:
        event_id: str
        kind: DeliveryKind
        recipient: str
        creator_name: str
        sending_domain: str
        title: str
        destination_url: str

        def __post_init__(self) -> None:
            self.kind = DeliveryKind(self.kind)
            if not 1 <= len(self.event_id) <= 120:
                raise ValueError("event_id must contain between 1 and 120 characters")
            if not _EMAIL_PATTERN.fullmatch(self.recipient):
                raise ValueError("recipient must be a valid email address")
            if not 1 <= len(self.creator_name) <= 100:
                raise ValueError("creator_name must contain between 1 and 100 characters")
            if not _DOMAIN_PATTERN.fullmatch(self.sending_domain):
                raise ValueError("sending_domain must be a valid domain name")
            if not 1 <= len(self.title) <= 160:
                raise ValueError("title must contain between 1 and 160 characters")
            if not self.destination_url.startswith("https://"):
                raise ValueError("destination_url must use HTTPS")


    @dataclass
    class DispatchResult:
        message_id: str
        kind: DeliveryKind


class DomainNotReady(Exception):
    pass


def dispatch_creator_message(request: CreatorDispatchRequest, mail: Any) -> DispatchResult:
    domain = mail.get_domain(request.sending_domain)
    status = domain.get("verification", {}).get("status")
    if status != "verified":
        raise DomainNotReady("Publish the returned DNS records and verify the sending domain first")

    subject, text = _render_message(request)
    result = mail.send_email(
        to=str(request.recipient),
        subject=subject,
        text=text,
        sender=f"updates@{request.sending_domain}",
        idempotency_key=f"creator-event:{request.event_id}",
    )
    return DispatchResult(message_id=str(result["message_id"]), kind=request.kind)


def _render_message(request: CreatorDispatchRequest) -> tuple[str, str]:
    messages = {
        DeliveryKind.ASSET_READY: (
            f"Your download is ready: {request.title}",
            f"{request.creator_name} has prepared your digital asset. Download it: {request.destination_url}",
        ),
        DeliveryKind.SUBSCRIBER_UPDATE: (
            f"New from {request.creator_name}: {request.title}",
            f"A new subscriber update is live. Read it: {request.destination_url}",
        ),
        DeliveryKind.PROCESSING_COMPLETE: (
            f"Content processing finished: {request.title}",
            f"Your content is processed and ready to review: {request.destination_url}",
        ),
    }
    return messages[request.kind]
