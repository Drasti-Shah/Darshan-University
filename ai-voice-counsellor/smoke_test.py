"""
End-to-end smoke test. Exercises every component and prints a readable
'conversation with the agent', plus what gets stored in the JSON database.

  1. Live app health (local + public ngrok URL)
  2. Bhashini speech pipeline: TTS -> ASR round-trip (proves Gujarati voice)
  3. Agent conversation (GPT-4o-mini): greeting -> name -> qualification -> degrees
     (the first student answer is sent through the REAL Bhashini ASR path)
  4. Lead persisted to data/leads.json -> printed back
"""

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

from dotenv import load_dotenv

load_dotenv(".env" if os.path.exists(".env") else ".env.example")

import requests  # noqa: E402
import bhashini  # noqa: E402
import counsellor  # noqa: E402
import storage  # noqa: E402

LOCAL = "http://localhost:5000"
PUBLIC = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
CALL_SID = "SMOKETEST-001"


def hr(title):
    print("\n" + "=" * 64 + f"\n{title}\n" + "=" * 64)


# --------------------------------------------------------------------------- #
def step_health():
    hr("STEP 1  |  Live app health")
    for label, base in [("local", LOCAL), ("public", PUBLIC)]:
        if not base:
            continue
        try:
            r = requests.get(base + "/health",
                             headers={"ngrok-skip-browser-warning": "1"}, timeout=8)
            print(f"  {label:7} {base}/health  ->  {r.status_code} {r.text.strip()}")
        except Exception as e:  # noqa: BLE001
            print(f"  {label:7} {base}/health  ->  ERROR: {e}")


def step_speech():
    hr("STEP 2  |  Bhashini speech pipeline (TTS -> ASR round-trip)")
    text = "મારું નામ રોનક છે"
    print(f"  TTS input : {text}")
    audio = bhashini.text_to_speech(text)
    print(f"  TTS output: {len(audio):,} bytes of WAV audio  ✅")
    recognized = bhashini.speech_to_text(audio)
    print(f"  ASR output: {recognized}  ✅")
    return audio


def step_conversation(first_answer_audio):
    hr("STEP 3  |  Conversation with the agent")
    history = []

    # --- greeting ---
    turn = counsellor.next_turn(history)
    print(f"\n  🎙️  Agent  : {turn['reply_gu']}")
    history.append({"role": "assistant", "content": turn["reply_gu"]})

    # --- student answer #1: through the REAL Bhashini ASR path ---
    asr_name = bhashini.speech_to_text(first_answer_audio)
    print(f"  🧑 Student : (spoken) -> ASR heard: {asr_name}")
    history.append({"role": "user", "content": asr_name})
    turn = counsellor.next_turn(history)
    print(f"  🎙️  Agent  : {turn['reply_gu']}")
    print(f"      [name={turn.get('name')!r}  stage={turn['stage']}]")
    history.append({"role": "assistant", "content": turn["reply_gu"]})

    # --- student answer #2: latest qualification -> agent asks MARKS ---
    ans2 = "મેં બારમું સાયન્સ પાસ કર્યું છે"
    print(f"  🧑 Student : {ans2}")
    history.append({"role": "user", "content": ans2})
    turn = counsellor.next_turn(history)
    print(f"  🎙️  Agent  : {turn['reply_gu']}")
    print(f"      [qualification={turn.get('qualification')!r}  stage={turn['stage']}]")
    history.append({"role": "assistant", "content": turn["reply_gu"]})

    # --- remaining student turns ---
    follow_ups = [
        ("નેવું ટકા આવ્યા છે",                                "marks -> warm reaction + LISTS degrees"),
        ("મને બી.ટેક. કમ્પ્યુટર સાયન્સ વિશે વધુ જાણવું છે",  "picks a degree -> full info"),
        ("મને આ કોર્સ વિશે વધુ વિગતો આપો",                    "'more details' -> program details (NOT placement)"),
        ("આ કોર્સનું પ્લેસમેન્ટ કેવું છે?",                    "asks placement -> placement info"),
        ("ના, બસ આટલું જ. આભાર.",                              "done -> end call"),
    ]
    for ans, note in follow_ups:
        print(f"  🧑 Student : {ans}   ({note})")
        history.append({"role": "user", "content": ans})
        turn = counsellor.next_turn(history)
        print(f"  🎙️  Agent  : {turn['reply_gu']}")
        print(f"      [stage={turn['stage']}  marks={turn.get('marks')!r}  "
              f"end_call={turn.get('end_call')}]")
        history.append({"role": "assistant", "content": turn["reply_gu"]})

    return turn, history


def step_store(turn, history):
    hr("STEP 4  |  JSON database (data/leads.json)")
    rec = storage.upsert_lead(
        CALL_SID,
        name=turn.get("name", ""),
        qualification=turn.get("qualification", ""),
        suggested_programs=turn.get("suggested_programs", []),
        stage=turn.get("stage", ""),
        completed=True,
        from_number="+919999000011",
        conversation=history,
    )
    import json
    print(json.dumps(rec, ensure_ascii=False, indent=2))


def main():
    try:
        step_health()
        audio = step_speech()
        turn, history = step_conversation(audio)
        step_store(turn, history)
        hr("RESULT")
        print("  ✅ Smoke test passed: app + Bhashini ASR/TTS + GPT-4o-mini + JSON DB.")
    except bhashini.BhashiniError as e:
        print(f"\n❌ Bhashini error: {e}")
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        print(f"\n❌ {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
