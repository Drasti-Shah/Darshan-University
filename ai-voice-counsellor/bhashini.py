"""
Bhashini client: Gujarati ASR (speech -> text) and TTS (text -> speech).

Two modes:

  DIRECT MODE (default, used here)
    You already have an inference key, so we POST straight to the Dhruva
    inference endpoint with `Authorization: <inference key>` and fixed
    Gujarati service ids. No userID needed.
      env: BHASHINI_INFERENCE_KEY   (your "inference variable key")

  CONFIG MODE (optional fallback)
    If you also have a ULCA userID + key, we first call getModelsPipeline to
    resolve service ids + endpoint + key dynamically.
      env: BHASHINI_USER_ID + BHASHINI_UDYAT_KEY (a.k.a. ulcaApiKey)
"""

import os
import re
import math
import base64
import struct
import array
import requests

ULCA_PIPELINE_CONFIG_URL = (
    "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline"
)
DHRUVA_INFERENCE_URL = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
DEFAULT_PIPELINE_ID = "64392f96daac500b55c543cd"

# Public Gujarati (indo-aryan) service ids on the default MeitY pipeline.
DEFAULT_ASR_SERVICE_ID = "ai4bharat/conformer-multilingual-indo_aryan-gpu--t4"
DEFAULT_TTS_SERVICE_ID = "ai4bharat/indic-tts-coqui-indo_aryan-gpu--t4"

LANG = "gu"  # Gujarati

_config_cache = None


class BhashiniError(RuntimeError):
    pass


def _inference_key():
    return os.getenv("BHASHINI_INFERENCE_KEY") or os.getenv("BHASHINI_INFERENCE_API_KEY")


def _ulca_key():
    return os.getenv("BHASHINI_UDYAT_KEY") or os.getenv("BHASHINI_ULCA_API_KEY")


def _resolve_config():
    """
    Return dict: callback_url, auth_name, auth_value, asr_service_id, tts_service_id.

    Uses CONFIG MODE when a userID is available, otherwise DIRECT MODE.
    """
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    user_id = os.getenv("BHASHINI_USER_ID")
    inf_key = _inference_key()

    if user_id and _ulca_key():
        _config_cache = _resolve_via_ulca(user_id)
    elif inf_key:
        _config_cache = {
            "callback_url": os.getenv("BHASHINI_INFERENCE_URL", DHRUVA_INFERENCE_URL),
            "auth_name": "Authorization",
            "auth_value": inf_key,
            "asr_service_id": os.getenv("BHASHINI_ASR_SERVICE_ID", DEFAULT_ASR_SERVICE_ID),
            "tts_service_id": os.getenv("BHASHINI_TTS_SERVICE_ID", DEFAULT_TTS_SERVICE_ID),
        }
    else:
        raise BhashiniError(
            "No Bhashini credentials. Set BHASHINI_INFERENCE_KEY (direct mode) "
            "or BHASHINI_USER_ID + BHASHINI_UDYAT_KEY (config mode)."
        )
    return _config_cache


def _resolve_via_ulca(user_id):
    payload = {
        "pipelineTasks": [
            {"taskType": "asr", "config": {"language": {"sourceLanguage": LANG}}},
            {"taskType": "tts", "config": {"language": {"sourceLanguage": LANG}}},
        ],
        "pipelineRequestConfig": {
            "pipelineId": os.getenv("BHASHINI_PIPELINE_ID", DEFAULT_PIPELINE_ID)
        },
    }
    headers = {
        "userID": user_id,
        "ulcaApiKey": _ulca_key(),
        "Content-Type": "application/json",
    }
    resp = requests.post(ULCA_PIPELINE_CONFIG_URL, json=payload, headers=headers, timeout=30)
    if resp.status_code != 200:
        raise BhashiniError(f"ULCA config failed [{resp.status_code}]: {resp.text[:300]}")
    data = resp.json()

    asr_sid = tts_sid = None
    for task in data.get("pipelineResponseConfig", []):
        cfgs = task.get("config", [])
        if not cfgs:
            continue
        if task.get("taskType") == "asr":
            asr_sid = cfgs[0].get("serviceId")
        elif task.get("taskType") == "tts":
            tts_sid = cfgs[0].get("serviceId")

    ep = data.get("pipelineInferenceAPIEndPoint", {})
    key = ep.get("inferenceApiKey", {})
    auth_value = _inference_key() or key.get("value")
    return {
        "callback_url": ep.get("callbackUrl", DHRUVA_INFERENCE_URL),
        "auth_name": key.get("name", "Authorization"),
        "auth_value": auth_value,
        "asr_service_id": asr_sid or DEFAULT_ASR_SERVICE_ID,
        "tts_service_id": tts_sid or DEFAULT_TTS_SERVICE_ID,
    }


def _inference(payload):
    cfg = _resolve_config()
    headers = {cfg["auth_name"]: cfg["auth_value"], "Content-Type": "application/json"}
    resp = requests.post(cfg["callback_url"], json=payload, headers=headers, timeout=60)
    if resp.status_code != 200:
        raise BhashiniError(f"Inference failed [{resp.status_code}]: {resp.text[:300]}")
    return resp.json()


def _preprocess_asr(wav_bytes, target_rate=16000):
    """
    Clean up Twilio's 8 kHz telephony recording for better Bhashini ASR:
      - take mono, convert to float
      - peak-normalize (telephony audio is often quiet)  -> louder, clearer
      - upsample to 16 kHz (Bhashini Gujarati models expect 16 kHz)
    Returns (wav_bytes_16k_pcm, sample_rate). Falls back to the original on any
    unexpected format.
    """
    tag, nch, rate, bits, data = _parse_wav(wav_bytes)
    if tag == 1 and bits == 16:
        src = array.array("h"); src.frombytes(data); norm = 1.0 / 32768.0
    elif tag == 3 and bits == 32:
        src = array.array("f"); src.frombytes(data); norm = 1.0
    else:
        return wav_bytes, rate

    if nch > 1:                       # keep first channel only
        src = src[0::nch]
    floats = [s * norm for s in src]
    n = len(floats)
    if n == 0:
        return wav_bytes, rate

    # Peak-normalize with a capped gain (don't blow up pure silence/noise).
    peak = max(abs(x) for x in floats)
    if peak > 0:
        gain = min(8.0, 0.95 / peak)
        floats = [x * gain for x in floats]

    # Linear-interpolation resample to target_rate.
    if rate and rate != target_rate:
        ratio = target_rate / rate
        m = int(n * ratio)
        out = array.array("h", bytes(2 * m))
        for i in range(m):
            pos = i / ratio
            i0 = int(pos)
            frac = pos - i0
            a = floats[i0] if i0 < n else 0.0
            b = floats[i0 + 1] if i0 + 1 < n else a
            out[i] = _clamp16((a + (b - a) * frac) * 32767.0)
        rate = target_rate
    else:
        out = array.array("h", (_clamp16(x * 32767.0) for x in floats))

    return _wav16(out.tobytes(), 1, rate), rate


def speech_to_text(audio_bytes, sampling_rate=None, audio_format="wav"):
    """Gujarati ASR. Cleans up telephony audio first. Returns recognized text."""
    cfg = _resolve_config()
    audio_bytes, rate = _preprocess_asr(audio_bytes, target_rate=16000)
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    payload = {
        "pipelineTasks": [
            {
                "taskType": "asr",
                "config": {
                    "language": {"sourceLanguage": LANG},
                    "serviceId": cfg["asr_service_id"],
                    "audioFormat": audio_format,
                    "samplingRate": rate,
                },
            }
        ],
        "inputData": {"audio": [{"audioContent": audio_b64}]},
    }
    data = _inference(payload)
    try:
        return data["pipelineResponse"][0]["output"][0]["source"].strip()
    except (KeyError, IndexError):
        raise BhashiniError(f"Unexpected ASR response: {data}")


_AI_FULL = "આર્ટિફિશિયલ ઇન્ટેલિજન્સ"  # "Artificial Intelligence" — pronounced cleanly

# Educational abbreviations -> clear spoken Gujarati form (regex, case-insensitive).
_ABBR_REGEX = [
    (r"\bB\.?\s?Tech\b", "બી ટેક"),
    (r"\bM\.?\s?Tech\b", "એમ ટેક"),
    (r"\bB\.?\s?Com\b", "બી કોમ"),
    (r"\bB\.?\s?Sc\b", "બી એસસી"),
    (r"\bM\.?\s?Sc\b", "એમ એસસી"),
    (r"\bBCA\b", "બીસીએ"),
    (r"\bMCA\b", "એમસીએ"),
    (r"\bBBA\b", "બીબીએ"),
    (r"\bMBA\b", "એમબીએ"),
    (r"\bCSE\b", "સી એસ ઈ"),
    (r"\bML\b", "એમ એલ"),
    (r"\bPCM\b", "પી સી એમ"),
    (r"\bHSC\b", "એચ એસ સી"),
    (r"\bSSC\b", "એસ એસ સી"),
]
# Gujarati-script abbreviations with dots -> remove dots so they aren't read as "dot".
_ABBR_PLAIN = [
    ("બી.ટેક.", "બી ટેક"), ("બી.ટેક", "બી ટેક"),
    ("એમ.ટેક.", "એમ ટેક"), ("એમ.ટેક", "એમ ટેક"),
    ("બી.કોમ", "બી કોમ"), ("એમ.કોમ", "એમ કોમ"),
    ("બી.એસસી", "બી એસસી"), ("એમ.એસસી", "એમ એસસી"),
    ("એમ.એ.", "એમ એ"),
]


def _clean_for_tts(text):
    """
    Normalize text so the TTS engine speaks it smoothly and clearly:
    - expand "AI" and educational abbreviations into spoken form
    - "%" -> "ટકા", strip symbols Bhashini verbalizes (e.g. "!" -> "factorial")
    - keep full stops/commas so the voice gets natural pauses
    """
    # "AI" pronunciation.
    text = re.sub(r"\bA\.?I\.?\b", _AI_FULL, text, flags=re.IGNORECASE)
    for token in ("એઆઈ", "એઆઇ", "એ.આઈ.", "એ આઈ", "એ.આઇ.", "એ આઇ"):
        text = text.replace(token, _AI_FULL)

    # Educational abbreviations -> spoken form.
    for pat, repl in _ABBR_REGEX:
        text = re.sub(pat, repl, text, flags=re.IGNORECASE)
    for src, repl in _ABBR_PLAIN:
        text = text.replace(src, repl)

    # Symbols.
    text = text.replace("%", " ટકા ")
    text = text.replace("&", " અને ")
    for ch in "!":
        text = text.replace(ch, ".")
    for ch in "—–-*#`":  # dashes/markdown that get verbalized oddly
        text = text.replace(ch, " ")

    # Collapse leftover doubles (keep single . and , for natural pauses).
    while "  " in text:
        text = text.replace("  ", " ")
    while ".." in text:
        text = text.replace("..", ".")
    return text.strip()


def _parse_wav(b):
    """Return (fmt_tag, nchannels, rate, bits, data_bytes). Handles PCM + float."""
    pos, fmt, data = 12, None, b""
    while pos + 8 <= len(b):
        cid = b[pos:pos + 4]
        size = struct.unpack("<I", b[pos + 4:pos + 8])[0]
        body = b[pos + 8:pos + 8 + size]
        if cid == b"fmt ":
            fmt = struct.unpack("<HHIIHH", body[:16])
        elif cid == b"data":
            data = body
        pos += 8 + size + (size & 1)
    return fmt[0], fmt[1], fmt[2], fmt[5], data


def _wav16(body, nch, rate):
    """Wrap raw 16-bit PCM bytes in a canonical WAV header."""
    return (b"RIFF" + struct.pack("<I", 36 + len(body)) + b"WAVE"
            + b"fmt " + struct.pack("<IHHIIHH", 16, 1, nch, rate,
                                    rate * nch * 2, nch * 2, 16)
            + b"data" + struct.pack("<I", len(body)) + body)


def _clamp16(v):
    return 32767 if v > 32767 else -32768 if v < -32768 else int(v)


def _soften(wav_bytes, volume, softness=0.0):
    """Make the voice gentler and emit standard 16-bit PCM (Twilio-safe).

    softness 0..1 -> one-pole low-pass that rolls off harsh highs (warmer/softer),
    with makeup gain so it stays audible. volume scales overall loudness.
    """
    tag, nch, rate, bits, data = _parse_wav(wav_bytes)

    if tag == 3 and bits == 32:          # IEEE float32 in [-1, 1]
        raw = array.array("f"); raw.frombytes(data); norm = 1.0
    elif tag == 1 and bits == 16:        # PCM int16
        raw = array.array("h"); raw.frombytes(data); norm = 1.0 / 32768.0
    else:
        return wav_bytes

    n = len(raw)

    # Fast path: nothing to change.
    if volume == 1.0 and softness <= 0.0:
        if tag == 1:
            return wav_bytes
        out = array.array("h", (_clamp16(s * 32767.0) for s in raw))
        return _wav16(out.tobytes(), nch, rate)

    # Low-pass coefficient: more softness -> lower cutoff -> mellower voice.
    alpha = 0.0
    makeup = 1.0
    if softness > 0.0:
        cutoff = max(700.0, 4000.0 - softness * 3000.0)
        alpha = math.exp(-2.0 * math.pi * cutoff / rate)
        makeup = 1.0 + softness * 0.5     # compensate for removed high energy

    fade = min(int(rate * 0.04) * nch, n // 2)
    out = array.array("h", bytes(2 * n))
    y = 0.0
    for i in range(n):
        x = raw[i] * norm
        if alpha:
            y = (1.0 - alpha) * x + alpha * y
            x = y
        g = volume * makeup
        if fade and i < fade:
            g *= 0.4 + 0.6 * (i / fade)
        elif fade and i >= n - fade:
            g *= 0.4 + 0.6 * ((n - 1 - i) / fade)
        out[i] = _clamp16(x * g * 32767.0)
    return _wav16(out.tobytes(), nch, rate)


def text_to_speech(text, sampling_rate=None, gender=None, volume=None, softness=None):
    """Gujarati TTS -> WAV bytes (soft female voice by default).

    Tunable via .env:
      BHASHINI_TTS_GENDER         female | male   (default female)
      BHASHINI_TTS_SAMPLING_RATE  e.g. 22050      (default 16000)
      BHASHINI_TTS_VOLUME         0.0-1.0         (default 0.7)
      BHASHINI_TTS_SOFTNESS       0.0-1.0         (default 0.0; higher = mellower)
    """
    if gender is None:
        gender = os.getenv("BHASHINI_TTS_GENDER", "female").lower()
    if sampling_rate is None:
        sampling_rate = int(os.getenv("BHASHINI_TTS_SAMPLING_RATE", "16000"))
    if volume is None:
        volume = float(os.getenv("BHASHINI_TTS_VOLUME", "0.7"))
    if softness is None:
        softness = float(os.getenv("BHASHINI_TTS_SOFTNESS", "0.0"))

    text = _clean_for_tts(text)
    cfg = _resolve_config()
    payload = {
        "pipelineTasks": [
            {
                "taskType": "tts",
                "config": {
                    "language": {"sourceLanguage": LANG},
                    "serviceId": cfg["tts_service_id"],
                    "gender": gender,
                    "samplingRate": sampling_rate,
                },
            }
        ],
        "inputData": {"input": [{"source": text}]},
    }
    data = _inference(payload)
    try:
        audio_b64 = data["pipelineResponse"][0]["audio"][0]["audioContent"]
    except (KeyError, IndexError):
        raise BhashiniError(f"Unexpected TTS response: {data}")
    # Soften + normalize to 16-bit PCM for a gentle, Twilio-friendly voice.
    return _soften(base64.b64decode(audio_b64), volume, softness)
