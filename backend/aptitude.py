"""
aptitude.py
Handles aptitude round logic:
- Loading questions from JSON
- Randomly selecting 15 questions
- Scoring submitted answers
- Calling the LLM (via Groq) to generate practice questions when score is low
"""

import json
import random
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Load question bank once at module startup
with open(os.path.join(os.path.dirname(__file__), "questions.json"), "r") as f:
    QUESTION_BANK = json.load(f)["questions"]


def get_random_questions(count: int = 15) -> list:
    """
    Randomly select 'count' questions from the question bank.
    Returns a list of question dicts (without leaking the answer to the client).
    """
    selected = random.sample(QUESTION_BANK, min(count, len(QUESTION_BANK)))
    return selected


def calculate_score(questions: list, user_answers: dict) -> dict:
    """
    Compare user answers against correct answers.
    user_answers: { "0": "selected option", "1": "selected option", ... }
    Returns a dict with score, correct_count, total, and percentage.
    """
    correct = 0
    total = len(questions)

    for i, q in enumerate(questions):
        user_ans = user_answers.get(str(i), "").strip()
        if user_ans == q["answer"]:
            correct += 1

    percentage = round((correct / total) * 100, 1) if total > 0 else 0

    return {
        "correct": correct,
        "total": total,
        "percentage": percentage,
        "passed": percentage >= 75
    }


def generate_practice_questions(resume_text: str, job_role: str) -> list:
    """
    Call the Groq LLM to generate 10 new practice aptitude questions
    tailored to the user's resume and job role.
    Returns a list of question dicts.
    """
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    prompt = f"""You are an expert technical recruiter creating aptitude test questions.

Resume Summary: {resume_text[:500] if resume_text else "Not provided"}
Target Job Role: {job_role}

Generate exactly 10 aptitude/technical questions relevant to this job role.
Return ONLY a valid JSON object in this exact format, no extra text:

{{
  "questions": [
    {{
      "question": "Question text here",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "answer": "Correct option text here"
    }}
  ]
}}"""

    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    data = json.loads(raw)
    return data.get("questions", [])
