"""
Tiny JSON "database" for captured admission leads.

Each call is one record in data/leads.json, upserted by CallSid so the file is
updated live as the conversation progresses (incomplete calls are kept too).

Record shape:
{
  "call_sid": "...",
  "name": "રોનક",
  "qualification": "12મું સાયન્સ",
  "suggested_programs": ["B.Tech. Computer Science and Engineering", ...],
  "stage": "done",
  "completed": true,
  "conversation": [{"role": "assistant"|"user", "content": "..."}, ...],
  "created_at": "2026-06-05T17:55:01",
  "updated_at": "2026-06-05T17:56:10"
}
"""

import os
import json
import threading
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
LEADS_FILE = os.path.join(DATA_DIR, "leads.json")

_lock = threading.Lock()


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _load():
    if not os.path.exists(LEADS_FILE):
        return []
    try:
        with open(LEADS_FILE, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_all(records):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = LEADS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    os.replace(tmp, LEADS_FILE)  # atomic on Windows + POSIX


def upsert_lead(call_sid, **fields):
    """Create or update the record for this call. Returns the saved record."""
    with _lock:
        records = _load()
        for rec in records:
            if rec.get("call_sid") == call_sid:
                rec.update(fields)
                rec["updated_at"] = _now()
                _save_all(records)
                return rec
        rec = {"call_sid": call_sid, "created_at": _now(), "updated_at": _now()}
        rec.update(fields)
        records.append(rec)
        _save_all(records)
        return rec


def all_leads():
    with _lock:
        return _load()
