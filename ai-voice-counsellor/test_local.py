"""
Local end-to-end test -- no Twilio, no phone call needed.

Runs three checks:
  1. Counsellor brain (GPT-4o-mini): scripted Gujarati conversation
     (greeting -> name -> qualification -> program suggestions).
  2. Bhashini TTS: synthesize a Gujarati sentence to a WAV file.
  3. Bhashini ASR round-trip: feed that WAV back and print the transcript.

Usage:
    python test_local.py            # run everything
    python test_local.py brain      # only the GPT conversation
    python test_local.py tts        # only TTS
    python test_local.py asr        # only ASR round-trip (does TTS first)
"""

import os
import sys

# Windows consoles default to cp1252 and choke on Gujarati/emoji -> force UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

from dotenv import load_dotenv

# Load .env if present, otherwise fall back to .env.example (handy for demos).
if os.path.exists(".env"):
    load_dotenv(".env")
else:
    load_dotenv(".env.example")

import bhashini  # noqa: E402  (after env load)
import counsellor  # noqa: E402

SAMPLE_TEXT = "નમસ્તે! દર્શન યુનિવર્સિટીમાં આપનું સ્વાગત છે. તમારું નામ જણાવશો?"
TTS_OUT = os.path.join("static", "audio", "test_tts.wav")


def line(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def test_brain():
    line("1. COUNSELLOR BRAIN (GPT-4o-mini)")
    # Simulated student answers, as if transcribed from Gujarati speech.
    student_turns = ["મારું નામ રોનક છે", "મેં બારમું સાયન્સ પાસ કર્યું છે"]

    history = []
    turn = counsellor.next_turn(history)
    print(f"\n🎙️  Agent: {turn['reply_gu']}")
    history.append({"role": "assistant", "content": turn["reply_gu"]})

    for ans in student_turns:
        print(f"🧑  Student: {ans}")
        history.append({"role": "user", "content": ans})
        turn = counsellor.next_turn(history)
        print(f"🎙️  Agent: {turn['reply_gu']}")
        print(f"     [stage={turn['stage']}  name={turn.get('name')!r}  "
              f"qualification={turn.get('qualification')!r}  end={turn['end_call']}]")
        history.append({"role": "assistant", "content": turn["reply_gu"]})

    print("\n✅ Brain test done.")


def test_tts():
    line("2. BHASHINI TTS (Gujarati text -> speech)")
    print(f"Text: {SAMPLE_TEXT}")
    audio = bhashini.text_to_speech(SAMPLE_TEXT)
    os.makedirs(os.path.dirname(TTS_OUT), exist_ok=True)
    with open(TTS_OUT, "wb") as f:
        f.write(audio)
    print(f"✅ Wrote {len(audio):,} bytes -> {TTS_OUT}  (play it to hear the voice)")
    return audio


def test_asr(audio=None):
    line("3. BHASHINI ASR round-trip (speech -> text)")
    if audio is None:
        if os.path.exists(TTS_OUT):
            with open(TTS_OUT, "rb") as f:
                audio = f.read()
        else:
            audio = test_tts()
    text = bhashini.speech_to_text(audio)
    print(f"✅ Recognized: {text}")


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    try:
        if which in ("all", "brain"):
            test_brain()
        if which in ("all", "tts", "asr"):
            audio = test_tts()
        if which in ("all", "asr"):
            test_asr(audio)
        elif which == "asr":
            test_asr()
    except bhashini.BhashiniError as e:
        print(f"\n❌ Bhashini error: {e}")
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        print(f"\n❌ {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
