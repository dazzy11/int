"""
interview_agent.py
Manages the AI mock interview:
- Generates interview questions using the Groq LLM
- Transcribes audio responses using Whisper via Groq
- Evaluates answers and generates follow-up questions
"""

import json
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def start_interview(resume_text: str, job_role: str, company: str, coding_score: int) -> dict:
    """
    Start the mock interview by generating the first question.
    The LLM acts as a technical interviewer at the specified company.
    """
    prompt = f"""You are a senior technical interviewer at {company} hiring for a {job_role} position.

Candidate's Resume Summary:
{resume_text[:800] if resume_text else "Not provided"}

Coding Round Score: {coding_score}/100

Start the interview with a single, specific opening technical question appropriate for {job_role} at {company}.
Do not give a greeting or explanation - just the question.

Return ONLY a valid JSON object in this exact format:
{{
  "question": "<your interview question here>",
  "feedback": "",
  "score": 0
}}"""

    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )

    return _parse_response(response.choices[0].message.content)


def evaluate_and_continue(
    resume_text: str,
    job_role: str,
    company: str,
    conversation_history: list,
    latest_answer: str
) -> dict:
    """
    Evaluate the candidate's latest answer and generate a follow-up question.
    conversation_history: list of {"role": "interviewer"/"candidate", "content": "..."}
    """
    # Build conversation context string
    history_str = ""
    for turn in conversation_history:
        role = "Interviewer" if turn["role"] == "interviewer" else "Candidate"
        history_str += f"{role}: {turn['content']}\n\n"

    prompt = f"""You are a senior technical interviewer at {company} for a {job_role} role.

Candidate Resume: {resume_text[:500] if resume_text else "Not provided"}

Interview so far:
{history_str}

Candidate's latest answer: "{latest_answer}"

Evaluate the answer and ask a relevant follow-up or next question.
Keep the interview progressing naturally - mix technical depth with practical experience questions.

Return ONLY a valid JSON object in this exact format:
{{
  "question": "<your next interview question>",
  "feedback": "<brief evaluation of the candidate's last answer>",
  "score": <integer 1-10 rating the last answer>
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
    Helper: parse the LLM response JSON, stripping markdown fences if needed.
    """
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())
