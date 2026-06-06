# AI Voice Admission Counsellor — Darshan University (Demo)

A phone-based AI admission counsellor. A student calls a Twilio number, the
agent greets them **in Gujarati**, asks for their **name** and **latest
qualification**, and then suggests matching **Darshan University** degree
programs.

```
Caller ─► Twilio (Record) ─► Bhashini ASR (Gujarati→text)
       ─► GPT-4o-mini (counsellor logic) ─► Bhashini TTS (text→Gujarati)
       ─► Twilio (Play) ─► next turn …
```

- **Telephony:** Twilio Programmable Voice
- **Speech (Gujarati STT + TTS):** Bhashini (MeitY / ULCA), low sampling rate (8 kHz) for low latency
- **Brain:** OpenAI `gpt-4o-mini`
- **Tunnel:** ngrok
- **Knowledge base:** `programs.json` — 10 real programs scraped from <https://darshan.ac.in/programs>

---

## 1. Setup

```powershell
cd "e:\Darshan University\ai-voice-counsellor"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and fill in:

| Variable | What it is |
|---|---|
| `OPENAI_API_KEY` | OpenAI key |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` | from Twilio console (used to download recordings) |
| `TWILIO_FROM_NUMBER` | your Twilio phone number |
| `BHASHINI_INFERENCE_KEY` | your **inference** key — this alone is enough (direct mode) |
| `BHASHINI_UDYAT_KEY` | your **Udyat / ULCA** key (only needed for config mode) |
| `PUBLIC_BASE_URL` | your ngrok HTTPS URL, e.g. `https://xxxx.ngrok-free.dev` |

> **About your keys (Bhashini has two modes):**
> - **Direct mode (default, what this demo uses):** the inference call goes
>   straight to the Dhruva endpoint with `Authorization: <BHASHINI_INFERENCE_KEY>`
>   and fixed Gujarati service ids. **No userID needed.** This is verified working.
> - **Config mode (optional):** if you also set `BHASHINI_USER_ID` +
>   `BHASHINI_UDYAT_KEY`, the client first calls `getModelsPipeline` to resolve
>   service ids dynamically.

> ⚠️ **Security:** keep your real keys in `.env` (gitignored), **not** in
> `.env.example`. Rotate any keys you've already committed.

## 2. Test locally first (no phone call)

Verify the brain + Bhashini speech work before touching Twilio:

```powershell
python test_local.py          # brain + TTS + ASR round-trip
python test_local.py brain    # only the GPT Gujarati conversation
python test_local.py tts      # only TTS -> static/audio/test_tts.wav
python test_local.py asr      # only ASR round-trip
```

Expected: a Gujarati conversation (name → qualification → 2-3 B.Tech/BCA/MBA
suggestions), a generated `test_tts.wav` you can play, and an ASR transcript.

## 3. Run the app

```powershell
python app.py
```

The server starts on `http://localhost:5000`.

## 4. Expose with ngrok

In a second terminal:

```powershell
ngrok http 5000
```

Copy the HTTPS forwarding URL, e.g. `https://abc123.ngrok-free.app`.

## 5. Make OUTBOUND calls (primary mode)

The system dials students from your Twilio number and runs the counsellor. Three ways:

**A. Browser dashboard** — open the public URL root:
```
https://saloon-untried-maturely.ngrok-free.dev/
```
Enter a number, click **Call now**. The page also lists captured leads.

**B. CLI** (single, multiple, or a file):
```powershell
python make_call.py 9724556935                 # one (10-digit -> +91)
python make_call.py 9724556935 9913000000      # several
python make_call.py --file numbers.txt          # one per line
```

**C. HTTP API:**
```powershell
Invoke-RestMethod -Uri "https://saloon-untried-maturely.ngrok-free.dev/call" `
  -Method POST -ContentType "application/json" -Body '{"to":"9724556935"}'
```

> Outbound endpoints: `GET /` dashboard · `POST /call` trigger · `POST /call-status`
> Twilio status callback (records call outcome on the lead).
>
> ⚠️ **Trial Twilio accounts** can only call **verified** numbers, and India (+91)
> needs international permissions + balance. Verify the destination number in the
> Twilio console first if calls fail.

## 6. (Optional) Inbound calls — point Twilio at it

In the Twilio Console → your phone number → **Voice → A call comes in**:

- Set to **Webhook**, `POST`
- URL: `https://abc123.ngrok-free.app/voice`

Save.

## 7. Inbound test call 📞

Speak in Gujarati. The flow:

1. *"નમસ્તે! દર્શન યુનિવર્સિટીમાં આપનું સ્વાગત છે. તમારું નામ જણાવશો?"*
2. Student says their name.
3. *"તમારી છેલ્લી લાયકાત શું છે?"* (latest qualification)
4. Student answers (e.g. *"બારમું સાયન્સ"*).
5. Agent suggests 2–3 matching programs and closes the call.

---

## Files

| File | Role |
|---|---|
| `app.py` | Flask + Twilio webhooks, per-turn pipeline, call state |
| `bhashini.py` | Bhashini ASR + TTS client (ULCA config cached) |
| `counsellor.py` | GPT-4o-mini turn logic (returns structured JSON) |
| `programs.json` | 10 Darshan University programs + eligibility |
| `storage.py` | JSON "database" — upserts each call's lead into `data/leads.json` |
| `make_call.py` | CLI to place outbound calls (single / multiple / `--file`) |
| `smoke_test.py` | End-to-end test (no phone): app + Bhashini + GPT + DB |
| `call_status.py` | Check a Twilio call's status by SID |

## Captured data (JSON database)

Every call is saved live to **`data/leads.json`** (upserted by CallSid, so even
incomplete calls are kept). Each record holds the student's name, latest
qualification, the programs suggested, the full Gujarati conversation, the
caller's number, and timestamps:

```json
{
  "call_sid": "CA...",
  "name": "રોનક",
  "qualification": "12મું સાયન્સ",
  "suggested_programs": ["B.Tech. Computer Science and Engineering"],
  "stage": "done",
  "completed": true,
  "from_number": "+91...",
  "conversation": [{"role": "assistant", "content": "..."}],
  "created_at": "2026-06-05T18:12:05",
  "updated_at": "2026-06-05T18:13:40"
}
```

View all leads in the browser: **`<PUBLIC_BASE_URL>/leads`** (or `http://localhost:5000/leads`).

## Change the agent's voice

The voice is a **soft female** by default. Tune it in `.env` (no code changes):

| Variable | Default | Effect |
|---|---|---|
| `BHASHINI_TTS_GENDER` | `female` | `female` or `male` |
| `BHASHINI_TTS_SAMPLING_RATE` | `16000` | higher = warmer/clearer (e.g. `22050`); `8000` = telephony |
| `BHASHINI_TTS_VOLUME` | `0.7` | `0.0`–`1.0`; lower = softer/gentler |

To compare options, run `python voice_samples.py` — it writes sample clips to
`static/audio/` so you can listen before choosing.

## Latency notes

- 8 kHz sampling for both ASR and TTS (telephony quality, smaller payloads).
- Bhashini pipeline config is fetched once and cached.
- Short LLM replies (1–2 sentences, `max_tokens=300`).
- `<Record timeout="3">` ends a turn quickly after the student stops speaking.

## Demo limitations

- Call state is in-memory (`CALLS` dict) — fine for a single-instance demo, not for production scale.
- No webhook signature validation (add `twilio.request_validator` for production).
- Generated audio accumulates in `static/audio/` — clear it periodically.
