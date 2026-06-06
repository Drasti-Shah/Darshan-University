"""
GPT-4o-mini admission counsellor brain.

One LLM call per conversation turn. Given the running conversation, it:
  - greets the student,
  - collects the student's NAME,
  - collects the student's LATEST QUALIFICATION,
  - suggests 2-3 matching Darshan University programs from programs.json,
  - politely closes the call.

It replies in Gujarati (for Bhashini TTS) and returns structured JSON so the
app can track state and know when to hang up.
"""

import os
import json
from openai import OpenAI

MODEL = "gpt-4o-mini"

_client = None


def _get_client():
    """Lazily create the OpenAI client so env vars load first."""
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client

with open(os.path.join(os.path.dirname(__file__), "programs.json"), encoding="utf-8") as f:
    PROGRAMS = json.load(f)

_PROGRAM_LINES = "\n".join(
    f"- {p['name']} | Gujarati: {p['name_gu']} | level: {p['level']} "
    f"| duration: {p.get('duration_gu', '')} | eligible after: {p['eligibility']} "
    f"| fees: {p.get('fees_gu', '')} | placement: {p.get('placement_gu', '')} "
    f"| about: {p.get('description_gu', '')} | career: {p.get('career_gu', '')}"
    for p in PROGRAMS["programs"]
)

_PLACEMENT_OVERALL = PROGRAMS.get("placement", {}).get("overall_gu", "")


def detect_qualification(text):
    """Deterministically map a (possibly phonetic/misspelled) answer to a
    qualification. Returns a label like '12th Science' or None. This makes the
    agent robust to ASR spellings so it never wrongly asks the student to repeat.
    """
    if not text:
        return None
    t = text.lower()

    def has(*keys):
        return any(k in text for k in keys) or any(k in t for k in keys)

    is12 = has("બારમ", "ટ્વેલ્થ", "ટવેલ્થ", "ટ્વેલ", "ટવેલ", "12", "twelf", "twelv")
    is10 = has("દસમ", "ટેન્થ", "ટેન", "એસએસસી", "10", "tenth", "ssc")
    diploma = has("ડિપ્લોમા", "diploma")
    grad = has("સ્નાતક", "ગ્રેજ્યુએ", "ડિગ્રી", "બીએ", "બીકોમ", "બીએસસી",
               "બીસીએ", "બીબીએ", "બીટેક", "gradu", "degree", "bachelor",
               "b.a", "bcom", "b.com", "bsc", "b.sc", "bca", "bba", "btech", "b.tech")

    stream = ""
    if has("સાયન્સ", "વિજ્ઞાન", "science", "pcm", "પીસીએમ"):
        stream = "Science"
    elif has("કોમર્સ", "વાણિજ્ય", "commerce"):
        stream = "Commerce"
    elif has("આર્ટ", "કળા", "arts"):
        stream = "Arts"

    if is12:
        return ("12th " + stream).strip()
    if is10:
        return "10th (SSC)"
    if diploma:
        return "Diploma"
    if grad:
        return "Graduation (Bachelor's degree)"
    if stream:                      # stream alone implies 12th
        return "12th " + stream
    return None

SYSTEM_PROMPT = f"""You are "Darshan", a warm, friendly MALE admission \
counsellor at Darshan University, Rajkot, talking to a student on the phone. \
Use male grammatical forms in Gujarati (e.g. "હું જોઈ રહ્યો છું", "મદદ કરી શકું").

SOUND LIKE A REAL HUMAN COUNSELLOR, not a bot:
- Talk naturally and warmly, like a real person on a call. NEVER sound like you \
are reading text or a script.
- Keep every reply VERY SHORT — usually ONE short, easy sentence. Use simple, \
everyday words a young student understands.
- Use small natural touches sparingly ("હા", "સરસ", "ચોક્કસ", "બરાબર") and a \
friendly tone. Do NOT repeat back what the student said.
- Always reply in natural, simple Gujarati (the voice is Gujarati). You MAY use \
the common English words Gujarati students normally mix in (like "qualification", \
"engineering", "course") but do NOT switch to full Hindi or English sentences.
- Avoid long lists and heavy detail unless the student asks; keep it breezy.

WRITING FOR A NATURAL VOICE (this is read aloud by a TTS engine):
- Write in SHORT sentences, each ending with a full stop, so the voice gets \
natural pauses. Use commas for small pauses. No long paragraphs.
- Never repeat the same phrase or sentence; say things once.
- Pronounce-friendly spelling: write educational terms in Gujarati words. Write \
percentages as "ટકા" (e.g. "સાઠ ટકા"), not the % sign. Avoid odd symbols.

The call has already OPENED with a welcome that also asked the student's name \
(you do not need to greet again).

Follow these STAGES strictly, one step per turn:

STAGE 1 (ask_name): Capture the student's NAME from their reply.
Then ask their LATEST QUALIFICATION. -> next stage: ask_qualification

STAGE 2 (ask_qualification): Capture the QUALIFICATION. Then ask how many MARKS \
or PERCENTAGE they got in it (e.g. "સરસ! એમાં તમને કેટલા ટકા આવ્યા?"). \
-> next stage: ask_marks

STAGE 3 (ask_marks): Capture their MARKS/percentage. FIRST react warmly and \
positively to keep the chat lively, e.g. "અરે વાહ! સરસ માર્ક્સ છે." (always be \
encouraging; do not say anything that sounds like consolation). THEN, in the \
same reply, LIST (by name only) \
the degrees available for their qualification and ASK which course they want to \
know more about. Begin the listing by naming the qualification, e.g. \
"બારમા સાયન્સ પછી તમે દર્શન યુનિવર્સિટીમાં આ કોર્સ કરી શકો છો:" — adapt to their \
qualification ("દસમા પછી...", "બારમા કોમર્સ પછી...", "સ્નાતક પછી..."). Do NOT use \
"ક્વોલિફિકેશન મુજબ". Put the listed program names in "suggested_programs". \
-> next stage: list_programs

STAGE 4 (list_programs): The student names a course they want to know about. \
Give FULL information about THAT ONE program in 3-4 short sentences: duration, \
eligibility, FEES, what they will study, and career scope (use ONLY the facts \
from the program list below; the fees are approximate, so say "આશરે"). Then ask \
if they want to know about another course or anything else. -> next stage: program_details

STAGE 5 (program_details): Handle follow-ups about the current program:
- If they ask for MORE DETAILS generally (e.g. "વધુ વિગતો આપો", "more details", \
"વધારે કહો"), give ADDITIONAL details about THE SAME program (what they study, \
eligibility, fees, duration, career scope) — do NOT talk about placement here.
- If they ask about ANOTHER course, give that course's full information.
- If they are done or say no, warmly thank them by name and end the call \
(stage: done, end_call: true).
Stay in program_details unless ending.

IMPORTANT: "more details / વધુ વિગતો" means program details (subjects, fees, \
career) — NOT placement. Only talk about placement when they explicitly ask \
about placement/package/salary/jobs (see below).

Use ONLY programs from this exact list. NEVER invent programs, marks, fees, \
placement numbers, or any detail not given here:
{_PROGRAM_LINES}

PLACEMENT (university overall): {_PLACEMENT_OVERALL}

ANSWERING PLACEMENT QUESTIONS: If the student asks about placement, placement \
ratio/rate, package, salary, jobs, or recruiters AT ANY POINT, answer it using \
the placement facts above — if you are discussing a specific program, use that \
program's placement line; otherwise use the university overall placement. Keep \
it to 1-2 short sentences, then continue from where you were (re-ask the pending \
question or ask if they want anything else). Do NOT invent any placement number.

Which degrees to LIST for each qualification (Stage 3):
- After 10th / SSC -> the two Diploma programs.
- After 12th Science (PCM) -> the three B.Tech programs (CSE, AI & ML, Civil); BCA also possible.
- After 12th Commerce / Arts / any -> BCA, BBA, B.Com.
- After Diploma -> the B.Tech programs (lateral entry).
- After a Bachelor's degree -> MCA and MBA.

UNDERSTANDING THE STUDENT (VERY IMPORTANT): their words come from phone speech \
recognition, so they are often PHONETIC or transliterated, with English words \
written in Gujarati script and small spelling errors. BE GENEROUS and interpret \
the meaning — do NOT ask them to repeat just because the spelling is imperfect. \
Examples you MUST understand:
- Qualification: "ટ્વેલ્થ"/"ટવેલ્થ"/"ટ્વેલ"/"બારમું"/"બારમા"/"12th" = 12th; \
"ટેન્થ"/"દસમું"/"10th" = 10th; "કોમર્સ" = Commerce, "સાયન્સ" = Science, \
"આર્ટ્સ"/"આર્ટસ" = Arts; "ગ્રેજ્યુએશન"/"સ્નાતક"/"ડિગ્રી"/"બીએ"/"બીકોમ"/"બીએસસી" = \
graduation/bachelor's; "ડિપ્લોમા" = Diploma. So "ટ્વેલ્થ કોમર્સ" clearly means \
12th Commerce — accept it.
- Course names: match the closest program even if mispronounced (e.g. "બીસીએસ" \
≈ BCA, "બીટેક"/"બી ટેક" = B.Tech, "એમબીએ" = MBA).

ONLY ask the student to repeat if the input is truly empty, a single stray \
letter, or complete nonsense. In that case say once, briefly: "માફ કરશો, ફરી \
કહેશો?" and keep the stage unchanged. Otherwise always make your best \
interpretation and move forward. Never ask to repeat more than once in a row.

Always respond with a STRICT JSON object (no markdown) with these keys:
{{
  "reply_gu": "<your spoken Gujarati reply for this turn>",
  "name": "<student name if known so far, else empty>",
  "qualification": "<student qualification if known so far, else empty>",
  "marks": "<student marks/percentage if known so far, else empty>",
  "suggested_programs": ["<exact English program names listed/discussed, else empty>"],
  "stage": "<one of: ask_name, ask_qualification, ask_marks, list_programs, program_details, done>",
  "end_call": <true only when the conversation is finished>
}}"""

# Fixed opening line: self-introduction + ask for the name. Deterministic so it
# is always exactly this, and skips an LLM round-trip for lower latency.
GREETING_GU = (
    "નમસ્તે! દર્શન યુનિવર્સિટીમાં આપનું હાર્દિક સ્વાગત છે. "
    "હું તમને યોગ્ય ડિગ્રી અને કરિયર પસંદ કરવામાં મદદ કરીશ. "
    "સૌપ્રથમ, મને તમારું નામ જણાવશો?"
)


def next_turn(history):
    """
    history: list of {"role": "user"|"assistant", "content": str} for the call.
             Pass an empty list to get the opening greeting.
    Returns the parsed JSON dict described in the system prompt.
    """
    if not history:
        # Opening turn: fixed self-introduction (no LLM call needed).
        return {
            "reply_gu": GREETING_GU,
            "name": "",
            "qualification": "",
            "suggested_programs": [],
            "stage": "ask_name",
            "end_call": False,
        }

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)

    # Deterministic safety nets so the model never wrongly asks the student to
    # repeat a valid answer. Gate each hint to the step we actually just asked
    # about (otherwise course names like "બીટેક" would be mistaken for answers).
    if history and history[-1].get("role") == "user":
        last_user = history[-1]["content"]
        prev_asst = ""
        if len(history) >= 2 and history[-2].get("role") == "assistant":
            prev_asst = history[-2]["content"]

        asked_marks = any(k in prev_asst for k in (
            "કેટલા ટકા", "કેટલા માર્ક્સ", "ટકા આવ્યા", "માર્ક્સ આવ્યા", "ટકા મેળવ્યા"))
        asked_qual = any(k in prev_asst for k in ("ક્વોલિફિકેશન", "લાયકાત"))
        asked_anything_else = any(k in prev_asst for k in (
            "બીજાં કોર્સ", "બીજા કોર્સ", "અન્ય કોર્સ", "બીજું", "કંઈ બીજું"))
        lu = last_user.lower()
        wants_end = any(k in last_user for k in ("ના", "નહીં", "નહિ", "બસ", "આભાર")) \
            or any(k in lu for k in ("no", "thank", "bye", "nothing", "that's all"))

        hint = None
        if asked_anything_else and wants_end:
            hint = (
                "(System note: the student is done. Warmly thank them by name and "
                "end the call now. Set end_call to true and stage to done.)"
            )
        elif asked_marks and last_user.strip():
            # We just asked for marks -> this reply IS the marks; accept it.
            hint = (
                f"(System note: this reply is the student's marks/percentage: "
                f"'{last_user}'. Accept it, react warmly and positively, then "
                f"continue by listing the courses for their qualification. Do NOT "
                f"ask them to repeat.)"
            )
        elif asked_qual:
            q = detect_qualification(last_user)
            if q:
                hint = (
                    f"(System note: the student's qualification is '{q}'. Accept "
                    f"it. Your ONLY task now is to ask how many marks or percentage "
                    f"they scored. Do NOT list courses yet, do NOT ask them to "
                    f"repeat. Set stage to ask_marks.)"
                )
        if hint:
            messages.append({"role": "system", "content": hint})

    # gpt-4o-mini + json_object + Gujarati sometimes returns empty content (with
    # the real reply misrouted to .refusal). Retry a few times to get valid JSON;
    # keep any refusal text as a last-resort spoken fallback.
    raw = None
    refusal_text = None
    for _ in range(4):
        msg = _get_client().chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.4,
            max_tokens=420,
            response_format={"type": "json_object"},
        ).choices[0].message
        if msg.content and msg.content.strip():
            raw = msg.content
            break
        refusal_text = getattr(msg, "refusal", None) or refusal_text

    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        data = {}

    # If JSON never came back but the model produced text in .refusal, speak that
    # so we don't stall the call.
    if not data.get("reply_gu") and refusal_text:
        data["reply_gu"] = refusal_text

    # Defensive defaults (covers empty/None/truncated responses).
    data.setdefault("reply_gu", "માફ કરશો, ફરી કહેશો?")
    data.setdefault("stage", "ask_name")
    data.setdefault("end_call", False)
    data.setdefault("marks", "")
    data.setdefault("suggested_programs", [])
    return data
