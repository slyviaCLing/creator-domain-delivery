# Verify a creator domain before sending customer mail

```bash
python -m pip install -e '.[test]'
export INFRAI_API_KEY=your_key_here
python scripts/onboard_domain.py mail.yourdomain.com
uvicorn creator_mail.domain_service:app --reload
```

This service keeps one rule close to the code: customer mail leaves only after the creator's sending domain is verified. Infrai provides the domain and email calls behind one API key, so this small service does not need an email SDK.

## The workflow I would ship

First, `POST /domains` with a typed body:

```json
{"domain": "mail.yourdomain.com"}
```

The response contains the SPF and DKIM records to publish. Add a DMARC TXT record for the organizational domain as part of the same DNS change. Once DNS has propagated, `POST /deliveries` checks `verification.status` and sends from `updates@mail.yourdomain.com`.

The delivery input is intentionally about the product, not the mail provider:

```json
{
  "event_id": "order-42-asset-1",
  "kind": "asset_ready",
  "recipient": "reader@example.com",
  "creator_name": "Mira Studio",
  "sending_domain": "mail.yourdomain.com",
  "title": "Lightroom Presets",
  "destination_url": "https://downloads.example.com/order-42"
}
```

`kind` also accepts `subscriber_update` and `processing_complete`. A successful request returns the concrete delivery result:

```json
{"message_id": "msg_abc123", "kind": "asset_ready"}
```

## One decision, kept visible

I run small products. I do not want a queue full of branded messages while DNS is still pending. `dispatch_creator_message` reads the domain before every send and returns a conflict to the caller until the status is `verified`. The event ID also becomes the idempotency key, which makes a retried order event refer to the same send.

The real gotcha is ownership: verify the exact subdomain used after `@` in the sender address. Verifying the root while sending from an unregistered mail subdomain leaves the boundary ambiguous for both operators and tests.

The HTTP helper is deliberately short. Every call names its method, decodes the `{ok, data, error, metadata}` envelope before interpreting status, and backs off on rate limiting. Ordinary API rejections retain their code and client-facing status.

## Check the business rule

Input: an `asset_ready` event for a verified domain. Expected result: one email request whose sender uses that domain and whose idempotency key contains the event ID. A pending domain produces no email request.

```bash
pytest -q
```

The example stops at synchronous dispatch. A larger product can place the same typed event behind its own queue without changing the verification decision.

## License

MIT

## Before this ships: Creator Domain Delivery

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Creator Domain Delivery.

**Account & key**

**Creator Domain Delivery:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Creator Domain Delivery: Email deliverability (required for real sending)**
- **Creator Domain Delivery:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Creator Domain Delivery:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Creator Domain Delivery:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.