"""
Place OUTBOUND counsellor calls from the Twilio number.

Usage:
    python make_call.py 9724556935                 # one number (10-digit -> +91)
    python make_call.py 9724556935 9913000000      # several numbers
    python make_call.py +9197...                    # full E.164
    python make_call.py --file numbers.txt          # one number per line

Each call is dialed from TWILIO_FROM_NUMBER and connected to the /voice webhook
(via PUBLIC_BASE_URL), so the Gujarati admission counsellor runs the conversation.
"""

import os
import sys

from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv(".env" if os.path.exists(".env") else ".env.example")

DEFAULT_CC = os.getenv("DEFAULT_COUNTRY_CODE", "+91")


def normalize(num):
    n = num.strip().replace(" ", "").replace("-", "")
    if n.startswith("+"):
        return n
    if len(n) == 10:
        return DEFAULT_CC + n
    return "+" + n


def collect_numbers(argv):
    if not argv:
        return []
    if argv[0] == "--file":
        with open(argv[1], encoding="utf-8") as f:
            return [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    return argv


def main():
    numbers = collect_numbers(sys.argv[1:])
    if not numbers:
        print("Usage: python make_call.py <number> [more numbers] | --file numbers.txt")
        sys.exit(1)

    from_ = os.getenv("TWILIO_FROM_NUMBER")
    base = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    if not all([from_, base, sid, token]):
        print("Missing TWILIO_FROM_NUMBER / PUBLIC_BASE_URL / TWILIO creds in .env")
        sys.exit(1)

    client = Client(sid, token)
    voice_url = base + "/voice"
    status_url = base + "/call-status"

    for raw in numbers:
        to = normalize(raw)
        try:
            call = client.calls.create(
                to=to, from_=from_, url=voice_url, method="POST",
                status_callback=status_url, status_callback_event=["completed"],
                status_callback_method="POST",
            )
            print(f"✅ {to}  queued  SID={call.sid}")
        except Exception as e:  # noqa: BLE001
            print(f"❌ {to}  failed: {e}")

    print("\nWatch live requests at http://127.0.0.1:4040  |  leads at "
          f"{base}/leads")


if __name__ == "__main__":
    main()
