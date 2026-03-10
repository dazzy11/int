"""
interview_agent.py
Manages the AI mock interview:
- Generates interview questions using the Groq LLM
- Asks easy questions across 3 rotating categories:
    1. Technical  (basic concept questions for the job role)
    2. Resume     (simple questions based on what the candidate wrote)
    3. HR         (common behavioural / motivation questions)
- Transcribes audio responses using Whisper via Groq
- Evaluates answers and generates follow-up questions
"""

import json
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Rotate through the three question categories in order.
# The cycle restarts after every 3 questions.
CATEGORY_CYCLE = ["technical", "resume", "hr"]


def start_interview(resume_text: str, job_role: str, company: str, coding_score: int) -> dict:
    """
    Begin the interview with an easy opening HR question so the candidate
    feels comfortable right away.
    """
    prompt = f"""You are a friendly interviewer at {company} for a {job_role} position.

Candidate Resume:
{resume_text[:800] if resume_text else "Not provided"}

Coding Round Score: {coding_score}/100

Ask ONE easy, welcoming HR/introductory question to open the interview.
Examples of the level you want:
- "Tell me a little about yourself."
- "Why are you interested in this role?"
- "What made you choose {job_role} as a career?"

Keep it simple and approachable — this is just the opener.

Return ONLY a valid JSON object, no extra text:
{{
  "question": "<your opening question>",
  "feedback": "",
  "score": 0,
  "category": "hr"
}}"""

    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6
    )

    return _parse_response(response.choices[0].message.content)


def evaluate_and_continue(
    resume_text: str,
    job_role: str,
    company: str,
    conversation_history: list,
    latest_answer: str,
    question_number: int = 1,       # 1-indexed count of answers given so far
) -> dict:
    """
    Evaluate the candidate's last answer and ask the next question.

    question_number drives the category rotation:
        1 → technical
        2 → resume
        3 → hr
        4 → technical  … and so on

    conversation_history: [{"role": "interviewer"/"candidate", "content": "..."}]
    """
    # Determine the next category
    category = CATEGORY_CYCLE[question_number % len(CATEGORY_CYCLE)]

    # Build readable history string
    history_str = ""
    for turn in conversation_history:
        label = "Interviewer" if turn["role"] == "interviewer" else "Candidate"
        history_str += f"{label}: {turn['content']}\n\n"

    # Category-specific instructions keep questions genuinely easy
    category_instructions = {
        "technical": f"""Ask ONE easy technical question for a {job_role}.
Target beginner-to-intermediate level — things like:
- Basic data structures (arrays, lists, dicts)
- Simple OOP concepts (class, object, inheritance)
- Common tools/frameworks the role uses at a surface level
- "What is X?" or "How does Y work?" style questions
Do NOT ask hard algorithm or system-design questions.""",

        "resume": f"""Ask ONE easy, friendly question directly about something in the candidate's resume.
Keep it conversational — just ask them to expand on something they already know well.
Examples:
- "I see you used [technology] — can you tell me what you liked about it?"
- "What was your role in [project] exactly?"
- "How long did you work with [skill]?"
Do NOT ask them to prove deep expertise.""",

        "hr": f"""Ask ONE easy, standard HR / behavioural question.
Keep it positive and simple — the kind every candidate expects:
- "What are your strengths?"
- "Where do you see yourself in 2 years?"
- "How do you handle tight deadlines?"
- "Tell me about a time you worked in a team."
Avoid stress questions or trick questions.""",
    }

    prompt = f"""You are a friendly, encouraging interviewer at {company} for a {job_role} role.

Candidate Resume: {resume_text[:500] if resume_text else "Not provided"}

Interview so far:
{history_str}
Candidate's latest answer: "{latest_answer}"

Step 1 — Briefly evaluate the answer (2 sentences max, keep it constructive).
Step 2 — {category_instructions[category]}

Return ONLY a valid JSON object, no extra text:
{{
  "question": "<your next question>",
  "feedback": "<short, kind evaluation of the last answer>",
  "score": <integer 1-10>,
  "category": "{category}"
}}"""

    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6
    )

    return _parse_response(response.choices[0].message.content)


def transcribe_audio(audio_file_path: str) -> str:
    """
    Transcribe an audio file using Groq's Whisper implementation.
    Returns the transcribed text string.
    """
    with open(audio_file_path, "rb") as f:
        transcription = client.audio.transcriptions.create(
            file=(os.path.basename(audio_file_path), f.read()),
            model="whisper-large-v3-turbo",
            temperature=0
        )
    return transcription.text


def text_to_speech(text: str, output_path: str) -> str:
    """
    Convert text to speech using gTTS and save as an MP3 file.
    Returns the path to the audio file.
    """
    from gtts import gTTS
    tts = gTTS(text=text, lang="en", slow=False)
    tts.save(output_path)
    return output_path


def _parse_response(raw: str) -> dict:
    """
    Parse LLM JSON response, stripping markdown fences if present.
    Falls back to finding the outermost { } block as a safety net.
    """
    raw = raw.strip()

    # Strip markdown code fences
    if "```" in raw:
        parts = raw.split("```")
        raw = parts[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    # Safety net: extract outermost JSON object
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start != -1 and end > start:
        raw = raw[start:end]

    return json.loads(raw)