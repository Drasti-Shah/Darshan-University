"""Check the status of a Twilio call. Usage: python call_status.py <CallSid>"""
import os
import sys
from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv(".env" if os.path.exists(".env") else ".env.example")

sid = sys.argv[1] if len(sys.argv) > 1 else None
if not sid:
    print("Usage: python call_status.py <CallSid>")
    sys.exit(1)

c = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
call = c.calls(sid).fetch()
print("status      :", call.status)
print("to          :", call.to)
print("from        :", call._from)
print("duration(s) :", call.duration)
print("price       :", call.price, call.price_unit)
