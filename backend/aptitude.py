"""
aptitude.py
Handles aptitude round logic:
- Loading questions from JSON
- Randomly selecting 15 questions
- Scoring submitted answers
- Calling the LLM to generate a SHORT performance report when score < 50%
  (no hard block — user always gets the option to retest OR move on)
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
    """
    return random.sample(QUESTION_BANK, min(count, len(QUESTION_BANK)))


def calculate_score(questions: list, user_answers: dict) -> dict:
    """
    Compare user answers against correct answers.
    user_answers: { "0": "selected option text", "1": "...", ... }

    Returns:
        correct     – number of correct answers
        total       – total questions
        percentage  – rounded score percentage
        needs_report – True when percentage < 50 (triggers AI report, but does NOT block)
    """
    correct = 0
    total = len(questions)

    for i, q in enumerate(questions):
        if user_answers.get(str(i), "").strip() == q["answer"]:
            correct += 1

    percentage = round((correct / total) * 100, 1) if total > 0 else 0

    return {
        "correct": correct,
        "total": total,
        "percentage": percentage,
        "needs_report": percentage < 50,   # soft flag — no hard block
    }


def generate_performance_report(
    resume_text: str,
    job_role: str,
    correct: int,
    total: int,
    percentage: float,
) -> str:
    """
    Ask the LLM for a SHORT (3-5 sentence) performance report.
    Highlights weak areas and gives 2-3 actionable study tips.
    Returns plain text (not JSON).
    """
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    prompt = f"""You are a friendly technical career coach reviewing an aptitude test result.

Candidate details:
- Target role : {job_role}
- Resume snippet: {resume_text[:300] if resume_text else "Not provided"}

Test result: {correct} correct out of {total} ({percentage}%)

Write a SHORT performance report (3-5 sentences max).
- Identify likely weak areas based on the score and role.
- Give 2-3 specific, actionable study tips.
- Keep the tone encouraging but honest.
- Do NOT use bullet points or markdown — plain paragraph text only."""

    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6,
    )

    return response.choices[0].message.content.strip()