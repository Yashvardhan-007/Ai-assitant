"""
main.py — AI Teacher backend API (Flask).

Run:
    cd backend
    pip install -r requirements.txt
    export ANTHROPIC_API_KEY=sk-ant-...   # optional but recommended
    python main.py

Endpoints (all JSON unless noted):
  POST /api/upload                 multipart file upload -> {session_id, headings, filename}
  POST /api/lesson/plan            build a lesson plan (topic or uploaded doc)
  POST /api/lesson/video           render the plan into an MP4 (calls /lesson/plan output)
  POST /api/quiz/generate          generate quiz from a lesson plan
  POST /api/quiz/answer            evaluate one student answer -> feedback + misconception
  POST /api/quiz/report            build final learning report from a list of results
  GET  /api/profile/<student_id>   fetch stored learner profile
  GET  /static/<path>              serves generated audio/video/slide files
"""
from dotenv import load_dotenv
load_dotenv()
import os
import uuid
import traceback
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from app.parsers.document_parser import parse_file
from app.rag import chunk_pages, DocumentIndex
from app.lesson_planner import build_lesson_plan
from app.video_builder import build_lesson_video
from app.assessment import generate_quiz, evaluate_answer, build_learning_report
from app.profile_store import get_profile, record_session
from app import llm

BASE_DIR = os.path.dirname(__file__)
UPLOAD_DIR = os.path.join(BASE_DIR, "app", "storage", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "app", "static"), static_url_path="/static")
CORS(app)

# In-memory registry of active document indexes, keyed by session_id.
# For a multi-user production deploy, back this with Redis/DB instead.
_SESSIONS = {}


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "llm_configured": llm.llm_available()})


@app.route("/api/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "no file provided"}), 400
    f = request.files["file"]
    session_id = str(uuid.uuid4())[:10]
    save_path = os.path.join(UPLOAD_DIR, f"{session_id}_{f.filename}")
    f.save(save_path)

    try:
        parsed = parse_file(save_path)
    except Exception as e:
        return jsonify({"error": f"failed to parse file: {e}"}), 400

    chunks = chunk_pages(parsed["pages"])
    index = DocumentIndex(chunks)
    _SESSIONS[session_id] = {"index": index, "filename": parsed["filename"]}

    return jsonify({
        "session_id": session_id,
        "filename": parsed["filename"],
        "num_pages": len(parsed["pages"]),
        "num_chunks": len(chunks),
        "suggested_headings": index.top_headings(),
    })


@app.route("/api/lesson/plan", methods=["POST"])
def lesson_plan():
    """
    body: {
      "topic": "Chapter 4" | "Newton's Laws" ...,
      "session_id": "<from /upload>"  (optional — omit for pure topic-based teaching),
      "level": "beginner|intermediate|advanced",
      "minutes": 20,
      "language": "Hindi",
      "style": "example-heavy" (optional)
    }
    """
    body = request.get_json(force=True)
    topic = body.get("topic", "").strip()
    if not topic:
        return jsonify({"error": "topic is required"}), 400

    level = body.get("level", "beginner")
    minutes = int(body.get("minutes", 20))
    language = body.get("language", "English")
    style = body.get("style", "balanced")
    session_id = body.get("session_id")

    chunks = None
    if session_id and session_id in _SESSIONS:
        chunks = _SESSIONS[session_id]["index"].retrieve(topic, top_k=8)

    try:
        plan = build_lesson_plan(topic, level, minutes, language, style, retrieved_chunks=chunks)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    return jsonify(plan)


@app.route("/api/lesson/video", methods=["POST"])
def lesson_video():
    """body: { "plan": <lesson plan JSON from /lesson/plan>, "language": "Hindi" }"""
    body = request.get_json(force=True)
    plan = body.get("plan")
    language = body.get("language", plan.get("meta", {}).get("language", "English") if plan else "English")
    if not plan:
        return jsonify({"error": "plan is required (output of /api/lesson/plan)"}), 400
    try:
        result = build_lesson_video(plan, language)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    return jsonify(result)


@app.route("/api/quiz/generate", methods=["POST"])
def quiz_generate():
    body = request.get_json(force=True)
    plan = body.get("plan")
    n = int(body.get("n_questions", 5))
    if not plan:
        return jsonify({"error": "plan is required"}), 400
    topic = plan.get("meta", {}).get("topic", "the lesson")
    level = plan.get("meta", {}).get("level", "beginner")
    quiz = generate_quiz(topic, plan.get("segments", []), level, n_questions=n)
    return jsonify({"topic": topic, "questions": quiz})


@app.route("/api/quiz/answer", methods=["POST"])
def quiz_answer():
    """body: { "question": {...one item from quiz.questions...}, "answer": "student text" }"""
    body = request.get_json(force=True)
    question = body.get("question")
    answer = body.get("answer", "")
    if not question:
        return jsonify({"error": "question is required"}), 400
    result = evaluate_answer(question, answer)
    return jsonify(result)


@app.route("/api/quiz/report", methods=["POST"])
def quiz_report():
    """body: { "topic": "...", "results": [{"question":..,"concept":..,"correct":bool}], "student_id": "optional" }"""
    body = request.get_json(force=True)
    topic = body.get("topic", "this lesson")
    results = body.get("results", [])
    student_id = body.get("student_id")
    report = build_learning_report(topic, results)
    if student_id:
        profile = record_session(student_id, topic, report)
        report["profile"] = profile
    return jsonify(report)


@app.route("/api/profile/<student_id>", methods=["GET"])
def profile(student_id):
    return jsonify(get_profile(student_id))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
