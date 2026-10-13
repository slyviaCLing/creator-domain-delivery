import argparse

from creator_mail.infrai_email import InfraiClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Register a creator sending domain")
    parser.add_argument("domain", help="sending domain, for example mail.creator.example")
    args = parser.parse_args()

    client = InfraiClient()
    try:
        result = client.verify_domain(args.domain)
    finally:
        client.close()

    print(f"DNS records for {args.domain}:")
    for record in result.get("dns_records", []):
        print(f"{record.get('type')} {record.get('name')} {record.get('value')}")


if __name__ == "__main__":
    main()

