"""
AI Voice Admission Counsellor for Darshan University.

Pipeline per turn:
  Twilio call  ->  <Record> caller's Gujarati speech
               ->  download recording (WAV)
               ->  Bhashini ASR (Gujarati speech -> text)
               ->  GPT-4o-mini counsellor (name / qualification / suggest)
               ->  Bhashini TTS (Gujarati text -> speech)
               ->  Twilio <Play> the reply, then record the next turn.

Run locally, expose with ngrok, and point a Twilio number's Voice webhook at
  POST  https://<your-ngrok>.ngrok-free.app/voice
"""

import json
import os
import threading
import time
import uuid

import requests
from dotenv import load_dotenv
from flask import Flask, redirect, render_template_string, request, send_from_directory, url_for
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse

load_dotenv()  # before local imports so they see env vars

import bhashini  # noqa: E402
import counsellor  # noqa: E402
import storage  # noqa: E402

app = Flask(__name__)


@app.after_request
def _cors(resp):
    """Allow the Next.js frontend (localhost:3000) to call this API."""
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "*"
    return resp


@app.before_request
def _preflight():
    if request.method == "OPTIONS":
        return ("", 204)


AUDIO_DIR = os.path.join(os.path.dirname(__file__), "static", "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_FROM_NUMBER")
DEFAULT_COUNTRY_CODE = os.getenv("DEFAULT_COUNTRY_CODE", "+91")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

_twilio = Client(TWILIO_SID, TWILIO_TOKEN) if TWILIO_SID and TWILIO_TOKEN else None


def _abs(endpoint, **values):
    """Absolute URL for Twilio. Prefer PUBLIC_BASE_URL (ngrok) if configured."""
    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL + url_for(endpoint, **values)
    return url_for(endpoint, _external=True, **values)


def _audio_url(filename):
    """Public URL for a saved audio file -- built WITHOUT url_for so it is safe
    to call from a background thread (no Flask app/request context needed)."""
    if PUBLIC_BASE_URL:
        return f"{PUBLIC_BASE_URL}/static/audio/{filename}"
    return _abs("serve_audio", filename=filename)


def _to_e164(number):
    """Normalize a phone number to E.164 (10-digit -> DEFAULT_COUNTRY_CODE)."""
    n = (number or "").strip().replace(" ", "").replace("-", "")
    if n.startswith("+"):
        return n
    if len(n) == 10:
        return DEFAULT_COUNTRY_CODE + n
    return "+" + n


def place_call(to_number):
    """Dial an outbound call that runs the counsellor flow. Returns the Call."""
    if not _twilio:
        raise RuntimeError("Twilio credentials missing in .env")
    if not TWILIO_FROM:
        raise RuntimeError("TWILIO_FROM_NUMBER missing in .env")
    return _twilio.calls.create(
        to=_to_e164(to_number),
        from_=TWILIO_FROM,
        url=_abs("voice"),
        method="POST",
        status_callback=_abs("call_status"),
        status_callback_event=["completed"],
        status_callback_method="POST",
    )

# In-memory conversation state, keyed by Twilio CallSid (fine for a demo).
CALLS = {}
# Background turn results, keyed by CallSid: {"status","audio_url","end_call"}.
PENDING = {}

# Short filler lines played WHILE a turn is being processed (no dead silence).
# Conversational filler while looking up course details / fees (latency masking).
FILLER_CHECK = "હા, ચોક્કસ. હું હમણાં જ ચેક કરીને જણાવું છું."
FILLER_MAIN = "હું જોઈ રહ્યો છું."   # generic, for quick turns (male form)
FILLER_WAIT = "હું જોઈ રહ્યો છું."   # short, repeated during polling

# Previous-stage values where the next turn looks up info/fees -> use FILLER_CHECK.
_LOOKUP_STAGES = {"list_programs", "program_details"}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _save_tts(text, call_sid):
    """Generate Gujarati speech with Bhashini, save as WAV, return public URL."""
    audio = bhashini.text_to_speech(text)
    fname = f"{call_sid}-{uuid.uuid4().hex[:8]}.wav"
    with open(os.path.join(AUDIO_DIR, fname), "wb") as f:
        f.write(audio)
    # Absolute URL so Twilio can fetch it through ngrok.
    return _audio_url(fname)


def _greeting_audio_url():
    """The greeting text is constant -> synthesize once, reuse for every call.

    Filename encodes the voice settings so it auto-regenerates if they change.
    """
    key = "greeting-{}-{}-{}-{}.wav".format(
        os.getenv("BHASHINI_TTS_GENDER", "female"),
        os.getenv("BHASHINI_TTS_SAMPLING_RATE", "16000"),
        os.getenv("BHASHINI_TTS_VOLUME", "0.7"),
        os.getenv("BHASHINI_TTS_SOFTNESS", "0.0"),
    )
    path = os.path.join(AUDIO_DIR, key)
    if not os.path.exists(path):
        with open(path, "wb") as f:
            f.write(bhashini.text_to_speech(counsellor.GREETING_GU))
    return _audio_url(key)


def _filler_url(text):
    """Synthesize a filler line once and reuse it (cached by text + voice)."""
    key = "filler-{}-{}-{}-{}-{}.wav".format(
        abs(hash(text)) % 10_000_000,
        os.getenv("BHASHINI_TTS_GENDER", "female"),
        os.getenv("BHASHINI_TTS_SAMPLING_RATE", "16000"),
        os.getenv("BHASHINI_TTS_VOLUME", "0.7"),
        os.getenv("BHASHINI_TTS_SOFTNESS", "0.0"),
    )
    path = os.path.join(AUDIO_DIR, key)
    if not os.path.exists(path):
        with open(path, "wb") as f:
            f.write(bhashini.text_to_speech(text))
    return _audio_url(key)


def _process_turn(call_sid, recording_url):
    """Heavy work for one turn (ASR -> GPT -> TTS), run in a background thread.

    Stores the resulting reply audio URL in PENDING[call_sid] so /reply can
    serve it once ready, while the caller hears a filler in the meantime.
    """
    state = CALLS.get(call_sid)
    try:
        transcript = ""
        if recording_url:
            audio = _download_recording(recording_url)
            if audio:
                try:
                    transcript = bhashini.speech_to_text(audio)
                except bhashini.BhashiniError as e:
                    app.logger.error("ASR error: %s", e)

        if not transcript:
            retry = "માફ કરશો, મને બરાબર સંભળાયું નહીં. કૃપા કરી ફરી કહેશો?"
            PENDING[call_sid] = {
                "status": "done",
                "audio_url": _save_tts(retry, call_sid),
                "end_call": False,
            }
            return

        state["history"].append({"role": "user", "content": transcript})
        turn = counsellor.next_turn(state["history"])
        state["history"].append({"role": "assistant", "content": turn["reply_gu"]})
        state["name"] = turn.get("name") or state["name"]
        state["qualification"] = turn.get("qualification") or state["qualification"]
        state["marks"] = turn.get("marks") or state.get("marks", "")
        state["stage"] = turn.get("stage", "")
        if turn.get("suggested_programs"):
            state["suggested_programs"] = turn["suggested_programs"]

        storage.upsert_lead(
            call_sid,
            name=state["name"],
            qualification=state["qualification"],
            marks=state.get("marks", ""),
            suggested_programs=state.get("suggested_programs", []),
            stage=turn.get("stage", ""),
            completed=bool(turn.get("end_call")),
            conversation=state["history"],
        )

        PENDING[call_sid] = {
            "status": "done",
            "audio_url": _save_tts(turn["reply_gu"], call_sid),
            "end_call": bool(turn.get("end_call")),
        }
    except Exception as e:  # noqa: BLE001
        app.logger.error("turn processing failed: %s", e)
        fallback = "માફ કરશો, થોડી તકલીફ આવી. કૃપા કરી ફરી કહેશો?"
        PENDING[call_sid] = {
            "status": "done",
            "audio_url": _save_tts(fallback, call_sid),
            "end_call": False,
        }


def _download_recording(recording_url, attempts=3):
    """Twilio recordings need basic auth and may lag a moment after the call."""
    url = recording_url + ".wav"
    for i in range(attempts):
        resp = requests.get(url, auth=(TWILIO_SID, TWILIO_TOKEN), timeout=15)
        if resp.status_code == 200 and resp.content:
            return resp.content
        time.sleep(0.35 * (i + 1))
    return None


def _student_number(form):
    """The student's number: 'To' for outbound calls we place, else 'From'."""
    if form.get("Direction", "").startswith("outbound"):
        return form.get("To", "")
    return form.get("From", "")


def _add_record(vr):
    """Record the student's answer (tuned for clean telephony ASR)."""
    vr.record(
        action=_abs("process"),
        method="POST",
        max_length=12,
        timeout=3,            # give callers time to start/finish speaking
        play_beep=False,      # no beep between turns
        trim="do-not-trim",   # keep the full clip; don't risk cutting speech
    )
    vr.redirect(_abs("process"))  # fall-through if caller stays silent


def _record_turn(vr, prompt_audio_url):
    """Play the counsellor's reply, then record the student's next answer."""
    vr.play(prompt_audio_url)
    _add_record(vr)
    return vr


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
DASHBOARD_HTML = """
<!doctype html><html><head><meta charset="utf-8">
<title>Darshan University - AI Admission Counsellor</title>
<style>
  body{font-family:system-ui,Arial,sans-serif;max-width:760px;margin:40px auto;padding:0 16px;color:#1a1a1a}
  h1{font-size:22px} .card{border:1px solid #ddd;border-radius:10px;padding:18px;margin:16px 0}
  input,button{font-size:16px;padding:10px;border-radius:8px;border:1px solid #ccc}
  button{background:#0b5cff;color:#fff;border:none;cursor:pointer}
  .msg{padding:10px;border-radius:8px;margin:10px 0}
  .ok{background:#e7f7ec;color:#136c34} .err{background:#fdeaea;color:#a11}
  table{width:100%;border-collapse:collapse;font-size:14px} th,td{border-bottom:1px solid #eee;padding:8px;text-align:left}
  small{color:#666}
</style></head><body>
<h1>📞 AI Admission Counsellor — Darshan University</h1>
<p><small>Outbound calls from {{ from_number }} · agent speaks Gujarati via Bhashini</small></p>
{% if message %}<div class="msg {{ 'ok' if ok else 'err' }}">{{ message }}</div>{% endif %}
<div class="card">
  <form method="POST" action="/call">
    <label>Student phone number<br>
    <input name="to" placeholder="9724556935 or +9197..." style="width:280px" required></label>
    <button type="submit">Call now</button>
  </form>
  <small>10-digit numbers assume {{ country }}. Trial Twilio accounts can only call verified numbers.</small>
</div>
<div class="card">
  <h3>Recent leads ({{ leads|length }})</h3>
  <table><tr><th>Name</th><th>Qualification</th><th>Suggested</th><th>Status</th><th>Updated</th></tr>
  {% for l in leads %}<tr>
    <td>{{ l.name or '—' }}</td><td>{{ l.qualification or '—' }}</td>
    <td>{{ l.suggested_programs|join(', ') or '—' }}</td>
    <td>{{ '✅ done' if l.completed else l.stage }}</td>
    <td><small>{{ l.updated_at }}</small></td>
  </tr>{% endfor %}
  </table>
  <p><a href="/leads">View full JSON →</a></p>
</div>
</body></html>
"""


@app.route("/")
def dashboard():
    return render_template_string(
        DASHBOARD_HTML,
        from_number=TWILIO_FROM or "(not set)",
        country=DEFAULT_COUNTRY_CODE,
        leads=list(reversed(storage.all_leads()))[:20],
        message=request.args.get("msg"),
        ok=request.args.get("ok") == "1",
    )


@app.route("/call", methods=["POST"])
def call():
    """Trigger an outbound call to a student's number."""
    to = request.form.get("to") or (request.get_json(silent=True) or {}).get("to")
    if not to:
        return {"error": "missing 'to' number"}, 400
    try:
        c = place_call(to)
    except Exception as e:  # noqa: BLE001
        app.logger.error("place_call failed: %s", e)
        if request.form.get("to"):  # browser form -> redirect with message
            return redirect(url_for("dashboard", msg=f"Call failed: {e}", ok=0))
        return {"error": str(e)}, 500
    if request.form.get("to"):
        return redirect(url_for("dashboard",
                                msg=f"Calling {_to_e164(to)} … (SID {c.sid})", ok=1))
    return {"sid": c.sid, "to": c.to, "status": c.status}


@app.route("/campaign", methods=["POST"])
def campaign():
    """Place outbound calls to a list of numbers (a calling campaign)."""
    body = request.get_json(silent=True) or {}
    numbers = body.get("numbers") or []
    if isinstance(numbers, str):
        numbers = [n for n in numbers.replace(",", "\n").splitlines() if n.strip()]
    if not numbers:
        return {"error": "no numbers provided"}, 400

    results = []
    for raw in numbers:
        raw = raw.strip()
        if not raw:
            continue
        try:
            c = place_call(raw)
            results.append({"to": _to_e164(raw), "sid": c.sid, "status": c.status})
        except Exception as e:  # noqa: BLE001
            results.append({"to": raw, "error": str(e)})
    ok = sum(1 for r in results if r.get("sid"))
    saved = storage.save_campaign({"queued": ok, "total": len(results), "results": results})
    return {"id": saved["id"], "queued": ok, "total": len(results), "results": results}


@app.route("/api/campaigns")
def api_campaigns():
    """List launched campaigns, enriched with live call completion counts."""
    leads_ = {r.get("call_sid"): r for r in storage.all_leads()}
    out = []
    for camp in reversed(storage.all_campaigns()):
        completed = 0
        for r in camp.get("results", []):
            lead = leads_.get(r.get("sid"))
            if lead and lead.get("completed"):
                completed += 1
        out.append({
            "id": camp.get("id"),
            "created_at": camp.get("created_at"),
            "total": camp.get("total", 0),
            "queued": camp.get("queued", 0),
            "completed": completed,
            "results": camp.get("results", []),
        })
    return {"count": len(out), "campaigns": out}


@app.route("/api/stats")
def api_stats():
    """Aggregate stats for the dashboard / analytics pages."""
    leads_ = storage.all_leads()
    total = len(leads_)
    completed = sum(1 for r in leads_ if r.get("completed"))
    by_qual, by_program = {}, {}
    total_dur = 0
    for r in leads_:
        q = (r.get("qualification") or "Unknown").strip() or "Unknown"
        by_qual[q] = by_qual.get(q, 0) + 1
        for p in r.get("suggested_programs", []):
            by_program[p] = by_program.get(p, 0) + 1
        try:
            total_dur += int(r.get("call_duration") or 0)
        except (TypeError, ValueError):
            pass
    named = sum(1 for r in leads_ if (r.get("name") or "").strip())
    return {
        "total_calls": total,
        "completed_calls": completed,
        "leads_captured": named,
        "conversion_pct": round(100 * named / total) if total else 0,
        "avg_duration_sec": round(total_dur / total) if total else 0,
        "by_qualification": by_qual,
        "by_program": by_program,
    }


@app.route("/call-status", methods=["POST"])
def call_status():
    """Twilio status callback -> record final call outcome on the lead."""
    call_sid = request.form.get("CallSid", "")
    if call_sid:
        storage.upsert_lead(
            call_sid,
            call_status=request.form.get("CallStatus", ""),
            call_duration=request.form.get("CallDuration", ""),
        )
    return ("", 204)


@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/leads")
def leads():
    """View all captured admission leads as JSON."""
    records = storage.all_leads()
    return app.response_class(
        json.dumps({"count": len(records), "leads": records},
                   ensure_ascii=False, indent=2),
        mimetype="application/json",
    )


@app.route("/static/audio/<path:filename>")
def serve_audio(filename):
    return send_from_directory(AUDIO_DIR, filename)


@app.route("/voice", methods=["POST"])
def voice():
    """Twilio hits this when the call connects: greet + ask for name."""
    call_sid = request.form.get("CallSid", uuid.uuid4().hex)

    turn = counsellor.next_turn([])
    CALLS[call_sid] = {
        "history": [{"role": "assistant", "content": turn["reply_gu"]}],
        "name": turn.get("name", ""),
        "qualification": turn.get("qualification", ""),
        "marks": turn.get("marks", ""),
        "suggested_programs": turn.get("suggested_programs", []),
        "stage": turn.get("stage", "ask_name"),
    }
    storage.upsert_lead(
        call_sid,
        name=turn.get("name", ""),
        qualification=turn.get("qualification", ""),
        marks=turn.get("marks", ""),
        suggested_programs=turn.get("suggested_programs", []),
        stage=turn.get("stage", "ask_name"),
        completed=False,
        student_number=_student_number(request.form),
        conversation=CALLS[call_sid]["history"],
    )

    vr = VoiceResponse()
    audio_url = _greeting_audio_url()  # cached -> faster pickup
    _record_turn(vr, audio_url)
    return str(vr), 200, {"Content-Type": "text/xml"}


@app.route("/process", methods=["POST"])
def process():
    """Twilio posts the recording here. Kick off processing + play a filler."""
    call_sid = request.form.get("CallSid", "")
    state = CALLS.get(call_sid)
    vr = VoiceResponse()

    if state is None:
        # Unknown call (e.g. server restarted mid-call) -> restart.
        vr.redirect(_abs("voice"))
        return str(vr), 200, {"Content-Type": "text/xml"}

    recording_url = request.form.get("RecordingUrl")
    # Process this turn in the background; meanwhile the caller hears a filler.
    PENDING[call_sid] = {"status": "working"}
    threading.Thread(
        target=_process_turn, args=(call_sid, recording_url), daemon=True
    ).start()

    # Use the conversational "checking…" filler when the next turn looks up
    # course details/fees; a short generic one otherwise.
    filler = FILLER_CHECK if state.get("stage") in _LOOKUP_STAGES else FILLER_MAIN
    vr.play(_filler_url(filler))
    vr.redirect(_abs("reply"))
    return str(vr), 200, {"Content-Type": "text/xml"}


@app.route("/reply", methods=["GET", "POST"])
def reply():
    """Serve the reply once the background turn is ready; else play a short filler."""
    call_sid = request.form.get("CallSid") or request.args.get("CallSid", "")
    polls = int(request.args.get("n", "0"))
    state = CALLS.get(call_sid)
    pend = PENDING.get(call_sid)
    vr = VoiceResponse()

    if state is None or pend is None:
        vr.redirect(_abs("voice"))
        return str(vr), 200, {"Content-Type": "text/xml"}

    if pend.get("status") != "done":
        # Still working. The main filler already played once in /process, so here
        # we mostly hold quietly and only reassure occasionally -- otherwise slow
        # turns (e.g. on a small cloud instance) would repeat the filler many times.
        if polls < 30:
            if polls > 0 and polls % 3 == 0:
                vr.play(_filler_url(FILLER_WAIT))   # gentle reassurance ~every 6s
            vr.pause(length=2)
            vr.redirect(_abs("reply") + f"?CallSid={call_sid}&n={polls + 1}")
        else:
            vr.redirect(_abs("reply") + f"?CallSid={call_sid}&n=0")
        return str(vr), 200, {"Content-Type": "text/xml"}

    # Done.
    PENDING.pop(call_sid, None)
    vr.play(pend["audio_url"])
    if pend.get("end_call"):
        vr.hangup()
        CALLS.pop(call_sid, None)
    else:
        # Reply already played above; now record the student's next answer.
        _add_record(vr)
    return str(vr), 200, {"Content-Type": "text/xml"}


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    # Auto-reloader is OFF by default for stability (a call landing mid-reload
    # would fail). Set FLASK_DEBUG=1 to enable reload during development.
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug,
            threaded=True, use_reloader=debug)
