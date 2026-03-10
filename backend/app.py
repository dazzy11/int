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
from dotenv import load_dotenv

load_dotenv()

import resume_parser
import aptitude
import coding_eval
import interview_agent

app = Flask(__name__)
CORS(app)

VALID_USER = "person"
VALID_PASS = "123"

sessions = {}
UPLOAD_FOLDER = tempfile.mkdtemp()


# ════════════════════════════════════════════════════════════════════
#  AUTH
# ════════════════════════════════════════════════════════════════════

@app.route("/api/login", methods=["POST"])
def login():
    """Validate credentials. Returns session_id on success."""
    data = request.json or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if username == VALID_USER and password == VALID_PASS:
        sid = str(uuid.uuid4())
        sessions[sid] = {}
        return jsonify({"success": True, "session_id": sid})

    return jsonify({"success": False, "error": "Invalid credentials"}), 401


# ════════════════════════════════════════════════════════════════════
#  DASHBOARD / SETUP
# ════════════════════════════════════════════════════════════════════

@app.route("/api/resume/upload", methods=["POST"])
def upload_resume():
    """Accept PDF resume, extract text, store in session."""
    sid = request.form.get("session_id")
    if not sid or sid not in sessions:
        return jsonify({"error": "Invalid session"}), 403

    if "resume" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["resume"]
    if not file.filename.endswith(".pdf"):
        return jsonify({"error": "Only PDF files are accepted"}), 400

    path = os.path.join(UPLOAD_FOLDER, f"{sid}_resume.pdf")
    file.save(path)

    text = resume_parser.extract_text_from_pdf(path)
    resume_parser.save_resume(sid, text)
    sessions[sid]["resume_text"] = text

    return jsonify({
        "success": True,
        "preview": text[:300] + "..." if len(text) > 300 else text
    })


@app.route("/api/jobs", methods=["GET"])
def get_jobs():
    """Return all job roles."""
    with open(os.path.join(os.path.dirname(__file__), "jobs.json")) as f:
        data = json.load(f)
    return jsonify(data)


@app.route("/api/companies", methods=["GET"])
def get_companies():
    """Return companies for a given job role. Query param: ?job=..."""
    job = request.args.get("job", "")
    with open(os.path.join(os.path.dirname(__file__), "companies.json")) as f:
        data = json.load(f)
    return jsonify({"companies": data.get(job, [])})


@app.route("/api/session/setup", methods=["POST"])
def setup_session():
    """Save selected job and company to session."""
    data = request.json or {}
    sid = data.get("session_id")
    if not sid or sid not in sessions:
        return jsonify({"error": "Invalid session"}), 403

    sessions[sid]["job_role"] = data.get("job_role", "")
    sessions[sid]["company"]  = data.get("company", "")
    return jsonify({"success": True})


# ════════════════════════════════════════════════════════════════════
#  APTITUDE ROUND
# ════════════════════════════════════════════════════════════════════

@app.route("/api/aptitude/questions", methods=["GET"])
def get_aptitude_questions():
    """Return 15 random aptitude questions (answers hidden from client)."""
    sid = request.args.get("session_id")
    if not sid or sid not in sessions:
        return jsonify({"error": "Invalid session"}), 403

    questions = aptitude.get_random_questions(15)
    sessions[sid]["aptitude_questions"] = questions  # store for scoring

    client_qs = [{"question": q["question"], "options": q["options"]} for q in questions]
    return jsonify({"questions": client_qs})


@app.route("/api/aptitude/submit", methods=["POST"])
def submit_aptitude():
    """
    Score the aptitude test.
    - Always returns the result so the user can proceed.
    - If score < 50%, also returns a short AI performance report.
      The frontend offers Retest or Move On — no hard block either way.
    """
    data = request.json or {}
    sid = data.get("session_id")
    if not sid or sid not in sessions:
        return jsonify({"error": "Invalid session"}), 403

    user_answers = data.get("answers", {})
    questions    = sessions[sid].get("aptitude_questions", [])

    result = aptitude.calculate_score(questions, user_answers)
    sessions[sid]["aptitude_score"] = result["percentage"]

    response = {"result": result}

    # Generate AI report only when score is low (< 50%) — FIX: was "low_score"
    if result["needs_report"]:
        resume_text = sessions[sid].get("resume_text", "")
        job_role    = sessions[sid].get("job_role", "General")
        try:
            report = aptitude.generate_performance_report(
                resume_text, job_role,
                result["correct"], result["total"], result["percentage"]
            )
            response["performance_report"] = report
        except Exception as e:
            response["performance_report"] = (
                f"You scored {result['percentage']}%. "
                "Consider reviewing core CS fundamentals and practising more MCQs before the next round."
            )

    return jsonify(response)


# ════════════════════════════════════════════════════════════════════
#  CODING ROUND
# ════════════════════════════════════════════════════════════════════

@app.route("/api/coding/problems", methods=["GET"])
def get_coding_problems():
    """
    Return 2 randomly selected coding problems.
    Passes session_id so problems stay consistent within the same session.
    """
    sid = request.args.get("session_id")
    if not sid or sid not in sessions:
        return jsonify({"error": "Invalid session"}), 403

    # FIX: pass session_id so the same problems are returned on refresh
    # but a new session always gets a fresh random pair
    problems = coding_eval.get_problems(2, session_id=sid)
    sessions[sid]["coding_problems"] = problems
    return jsonify({"problems": problems})


@app.route("/api/coding/run", methods=["POST"])
def run_code():
    """Execute user Python code and return stdout / stderr."""
    data = request.json or {}
    code = data.get("code", "")
    if not code.strip():
        return jsonify({"stdout": "", "stderr": "No code provided.", "success": False})
    result = coding_eval.run_code(code)
    return jsonify(result)


@app.route("/api/coding/submit", methods=["POST"])
def submit_code():
    """Evaluate user code with LLM. Returns score (0-100) + feedback."""
    data = request.json or {}
    sid  = data.get("session_id")
    if not sid or sid not in sessions:
        return jsonify({"error": "Invalid session"}), 403

    problem_id = data.get("problem_id")
    user_code  = data.get("code", "")

    problems = sessions[sid].get("coding_problems", [])
    problem  = next((p for p in problems if p["id"] == problem_id), None)

    if not problem:
        return jsonify({"error": "Problem not found in session"}), 404

    try:
        evaluation = coding_eval.evaluate_code(problem, user_code)
        sessions[sid]["coding_score"] = evaluation.get("score", 0)
        return jsonify(evaluation)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ════════════════════════════════════════════════════════════════════
#  INTERVIEW ROUND
# ════════════════════════════════════════════════════════════════════

@app.route("/api/interview/start", methods=["POST"])
def start_interview():
    """Begin the mock interview — returns first question."""
    data = request.json or {}
    sid  = data.get("session_id")
    if not sid or sid not in sessions:
        return jsonify({"error": "Invalid session"}), 403

    sess = sessions[sid]
    sessions[sid]["interview_history"] = []

    try:
        result = interview_agent.start_interview(
            sess.get("resume_text", ""),
            sess.get("job_role", "Software Engineer"),
            sess.get("company", "Tech Company"),
            sess.get("coding_score", 0)
        )
        sessions[sid]["interview_history"].append(
            {"role": "interviewer", "content": result["question"]}
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/interview/answer", methods=["POST"])
def submit_answer():
    """Evaluate candidate's answer, return feedback + next question."""
    data = request.json or {}
    sid  = data.get("session_id")
    if not sid or sid not in sessions:
        return jsonify({"error": "Invalid session"}), 403

    answer = data.get("answer", "")
    sess   = sessions[sid]

    sessions[sid]["interview_history"].append({"role": "candidate", "content": answer})

    try:
        result = interview_agent.evaluate_and_continue(
            resume_text=sess.get("resume_text", ""),
            job_role=sess.get("job_role", ""),
            company=sess.get("company", ""),
            conversation_history=sess["interview_history"],
            latest_answer=answer
        )
        sessions[sid]["interview_history"].append(
            {"role": "interviewer", "content": result["question"]}
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/interview/transcribe", methods=["POST"])
def transcribe_audio():
    """Transcribe uploaded audio file with Whisper."""
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
    """Convert text to speech and return MP3 file."""
    data = request.json or {}
    text = data.get("text", "")
    output_path = os.path.join(UPLOAD_FOLDER, "interviewer_speech.mp3")

    try:
        interview_agent.text_to_speech(text, output_path)
        return send_file(output_path, mimetype="audio/mpeg")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🚀 AI Interview Simulator backend starting on http://localhost:5000")
    app.run(debug=True, port=5000)