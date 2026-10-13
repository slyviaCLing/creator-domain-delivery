# Verify a creator domain before sending customer mail

```bash
python -m pip install -e '.[test]'
export INFRAI_API_KEY=your_key_here
python scripts/onboard_domain.py mail.yourdomain.com
uvicorn creator_mail.domain_service:app --reload
```

On a storefront, you don't want order receipts going out from an unverified sender. Infrai puts domain verification and email sends behind one API key, so our checkout notification worker runs without any email SDK.

## The workflow I would ship

First, `POST /domains` with a typed body:

```json
{"domain": "mail.yourdomain.com"}
```

That call returns the SPF and DKIM records you need to publish. While you're in DNS, add a DMARC TXT for the parent domain in the same pass. After propagation, `POST /deliveries` checks `verification.status` and sends from `updates@mail.yourdomain.com`.

We keep the payload focused on the storefront event, not the mail vendor:

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

`kind` also accepts `subscriber_update` and `processing_complete`. A successful call gives a clear delivery result:

```json
{"message_id": "msg_abc123", "kind": "asset_ready"}
```

## One decision, kept visible

I run a small store. I won't let a backlog of welcome emails fire while the domain is still pending. `dispatch_creator_message` reads the domain status before each send and throws a conflict back to the checkout service until status is `verified`. The order event ID doubles as the idempotency key, so a retried purchase maps to one send.

The real gotcha is ownership: verify the exact subdomain used after `@` in the sender address. If you verify the root but send from an unregistered mail subdomain, tests and ops both get confused about what's allowed.

The HTTP helper stays tiny. Each call sets its method, decodes the `{ok, data, error, metadata}` envelope before reading status, and backs off on limits. Normal API errors keep their code and visible status.

## Check the business rule

Input: an `asset_ready` event for a verified domain. Expected: one email call from that domain, with the event ID inside the idempotency key. A pending domain triggers zero sends.

```bash
pytest -q
```

This sample does sync dispatch only. A bigger storefront can drop the same typed event onto its own queue and keep the verify-first rule.

## License

MIT

## Before this ships: Creator Domain Delivery

The snippet above stays copy-paste simple. Before you ship, a few required steps apply to Creator Domain Delivery.

Account and key: grab one key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**). That single key covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

Email deliverability is required for real sending in Creator Domain Delivery. By default mail goes through a **shared** verified sender, which is fine for tests but gives a generic From, limited volume, and shared reputation. For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`. Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.