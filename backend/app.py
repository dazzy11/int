"""
app.py
Main Flask backend for the AI Interview Simulator.
All routes are REST endpoints returning JSON.
Frontend communicates via fetch() calls.
"""

import os
import json
import uuid
import tempfile
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

import resume_parser
import aptitude
import coding_eval
import interview_agent

app = Flask(__name__)
CORS(app)  # Allow all cross-origin requests (frontend calling backend)

# ─── Simple hardcoded credentials ───────────────────────────────────────────
VALID_USER = "person"
VALID_PASS = "123"

# ─── In-memory session store ─────────────────────────────────────────────────
# Each session holds: job_role, company, coding_score, interview_history, etc.
sessions = {}

UPLOAD_FOLDER = tempfile.mkdtemp()  # Temp dir for uploaded resumes & audio


# ════════════════════════════════════════════════════════════════════════════
#  AUTH
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/login", methods=["POST"])
def login():
    """
    Validate username and password.
    Returns a session_id token on success.
    """
    data = request.json or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if username == VALID_USER and password == VALID_PASS:
        sid = str(uuid.uuid4())
        sessions[sid] = {}  # Initialize empty session
        return jsonify({"success": True, "session_id": sid})

    return jsonify({"success": False, "error": "Invalid credentials"}), 401


# ════════════════════════════════════════════════════════════════════════════
#  DASHBOARD / SETUP
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/resume/upload", methods=["POST"])
def upload_resume():
    """
    Accept a PDF resume upload, extract text, and store it in memory.
    """
    sid = request.form.get("session_id")
    if not sid or sid not in sessions:
        return jsonify({"error": "Invalid session"}), 403

    if "resume" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["resume"]
    if not file.filename.endswith(".pdf"):
        return jsonify({"error": "Only PDF files are accepted"}), 400

    # Save file temporarily
    path = os.path.join(UPLOAD_FOLDER, f"{sid}_resume.pdf")
    file.save(path)

    # Extract text
    text = resume_parser.extract_text_from_pdf(path)
    resume_parser.save_resume(sid, text)
    sessions[sid]["resume_text"] = text

    return jsonify({
        "success": True,
        "preview": text[:300] + "..." if len(text) > 300 else text
    })


@app.route("/api/jobs", methods=["GET"])
def get_jobs():
    """Return all available job roles."""
    with open(os.path.join(os.path.dirname(__file__), "jobs.json")) as f:
        data = json.load(f)
    return jsonify(data)


@app.route("/api/companies", methods=["GET"])
def get_companies():
    """
    Return companies for a given job role.
    Query param: ?job=Software Engineer
    """
    job = request.args.get("job", "")
    with open(os.path.join(os.path.dirname(__file__), "companies.json")) as f:
        data = json.load(f)

    companies = data.get(job, [])
    return jsonify({"companies": companies})


@app.route("/api/session/setup", methods=["POST"])
def setup_session():
    """
    Save selected job and company to the session.
    """
    data = request.json or {}
    sid = data.get("session_id")
    if not sid or sid not in sessions:
        return jsonify({"error": "Invalid session"}), 403

    sessions[sid]["job_role"] = data.get("job_role", "")
    sessions[sid]["company"] = data.get("company", "")
    return jsonify({"success": True})


# ════════════════════════════════════════════════════════════════════════════
#  APTITUDE ROUND
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/aptitude/questions", methods=["GET"])
def get_aptitude_questions():
    """
    Return 15 random aptitude questions.
    Stores them in the session so we can score answers later.
    """
    sid = request.args.get("session_id")
    if not sid or sid not in sessions:
        return jsonify({"error": "Invalid session"}), 403

    questions = aptitude.get_random_questions(15)
    sessions[sid]["aptitude_questions"] = questions  # Keep for scoring

    # Send questions WITHOUT the answer key (client shouldn't see answers)
    client_questions = [
        {"question": q["question"], "options": q["options"]}
        for q in questions
    ]
    return jsonify({"questions": client_questions})


@app.route("/api/aptitude/submit", methods=["POST"])
def submit_aptitude():
    """
    Receive answers, compute score, return result.
    If score < 75, generate LLM practice questions.
    """
    data = request.json or {}
    sid = data.get("session_id")
    if not sid or sid not in sessions:
        return jsonify({"error": "Invalid session"}), 403

    user_answers = data.get("answers", {})
    questions = sessions[sid].get("aptitude_questions", [])

    result = aptitude.calculate_score(questions, user_answers)
    sessions[sid]["aptitude_score"] = result["percentage"]

    response = {"result": result}

    if not result["passed"]:
        # Score too low - generate practice questions
        resume_text = sessions[sid].get("resume_text", "")
        job_role = sessions[sid].get("job_role", "General")
        try:
            practice_qs = aptitude.generate_practice_questions(resume_text, job_role)
            response["practice_questions"] = practice_qs
        except Exception as e:
            response["practice_error"] = str(e)

    return jsonify(response)


# ════════════════════════════════════════════════════════════════════════════
#  CODING ROUND
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/coding/problems", methods=["GET"])
def get_coding_problems():
    """Return 2 random coding problems for the round."""
    sid = request.args.get("session_id")
    if not sid or sid not in sessions:
        return jsonify({"error": "Invalid session"}), 403

    problems = coding_eval.get_problems(2)
    sessions[sid]["coding_problems"] = problems
    return jsonify({"problems": problems})


@app.route("/api/coding/run", methods=["POST"])
def run_code():
    """
    Execute user code and return stdout/stderr.
    """
    data = request.json or {}
    code = data.get("code", "")
    result = coding_eval.run_code(code)
    return jsonify(result)


@app.route("/api/coding/submit", methods=["POST"])
def submit_code():
    """
    Evaluate user code with LLM and return score + feedback.
    """
    data = request.json or {}
    sid = data.get("session_id")
    if not sid or sid not in sessions:
        return jsonify({"error": "Invalid session"}), 403

    problem_id = data.get("problem_id")
    user_code = data.get("code", "")

    # Find the problem from session
    problems = sessions[sid].get("coding_problems", [])
    problem = next((p for p in problems if p["id"] == problem_id), None)

    if not problem:
        return jsonify({"error": "Problem not found"}), 404

    try:
        evaluation = coding_eval.evaluate_code(problem, user_code)
        sessions[sid]["coding_score"] = evaluation.get("score", 0)
        return jsonify(evaluation)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ════════════════════════════════════════════════════════════════════════════
#  INTERVIEW ROUND
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/interview/start", methods=["POST"])
def start_interview():
    """
    Begin the mock interview - returns the first question.
    """
    data = request.json or {}
    sid = data.get("session_id")
    if not sid or sid not in sessions:
        return jsonify({"error": "Invalid session"}), 403

    sess = sessions[sid]
    resume_text = sess.get("resume_text", "")
    job_role = sess.get("job_role", "Software Engineer")
    company = sess.get("company", "Tech Company")
    coding_score = sess.get("coding_score", 0)

    # Initialize interview history
    sessions[sid]["interview_history"] = []

    try:
        result = interview_agent.start_interview(
            resume_text, job_role, company, coding_score
        )
        # Log the first question
        sessions[sid]["interview_history"].append({
            "role": "interviewer",
            "content": result["question"]
        })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/interview/answer", methods=["POST"])
def submit_answer():
    """
    Receive candidate's text answer, evaluate it, return next question.
    """
    data = request.json or {}
    sid = data.get("session_id")
    if not sid or sid not in sessions:
        return jsonify({"error": "Invalid session"}), 403

    answer = data.get("answer", "")
    sess = sessions[sid]

    # Log the candidate's answer
    sessions[sid]["interview_history"].append({
        "role": "candidate",
        "content": answer
    })

    try:
        result = interview_agent.evaluate_and_continue(
            resume_text=sess.get("resume_text", ""),
            job_role=sess.get("job_role", ""),
            company=sess.get("company", ""),
            conversation_history=sess["interview_history"],
            latest_answer=answer
        )
        # Log the next question
        sessions[sid]["interview_history"].append({
            "role": "interviewer",
            "content": result["question"]
        })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/interview/transcribe", methods=["POST"])
def transcribe_audio():
    """
    Accept audio file upload, transcribe with Whisper, return text.
    """
    sid = request.form.get("session_id")
    if not sid or sid not in sessions:
        return jsonify({"error": "Invalid session"}), 403

    if "audio" not in request.files:
        return jsonify({"error": "No audio file"}), 400

    audio_file = request.files["audio"]
    path = os.path.join(UPLOAD_FOLDER, f"{sid}_audio.webm")
    audio_file.save(path)

    try:
        text = interview_agent.transcribe_audio(path)
        return jsonify({"text": text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/interview/tts", methods=["POST"])
def text_to_speech():
    """
    Convert interviewer question text to speech audio file.
    Returns the audio file as a download.
    """
    data = request.json or {}
    text = data.get("text", "")
    output_path = os.path.join(UPLOAD_FOLDER, "interviewer_speech.mp3")

    try:
        interview_agent.text_to_speech(text, output_path)
        return send_file(output_path, mimetype="audio/mpeg")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🚀 AI Interview Simulator backend starting on http://localhost:5000")
    app.run(debug=True, port=5000)
