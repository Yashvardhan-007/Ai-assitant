"""
assessment.py — Interaction, evaluation, misconception detection, and
adaptive re-teaching. Implements section 12 & 13 of the brief.
"""
from . import llm


def generate_quiz(topic: str, segments: list, level: str, n_questions: int = 5):
    if llm.llm_available():
        system = (
            "You are a rigorous teacher writing a short end-of-lesson quiz. "
            "Base every question strictly on the lesson content provided. "
            "Respond with ONLY valid JSON."
        )
        lesson_text = "\n".join(
            f"{s['title']}: {s['explanation']}" for s in segments
        )
        prompt = f"""
Lesson content on "{topic}" (level: {level}):
{lesson_text}

Write {n_questions} quiz questions as a JSON array, mixing MCQ and short-answer:
[
  {{"id":"q1","type":"mcq","question":"...","options":["a","b","c","d"],"correct":"a","concept":"short concept tag"}},
  {{"id":"q2","type":"short_answer","question":"...","correct":"expected answer","concept":"short concept tag"}}
]
"""
        try:
            data = llm.call_json(system, prompt, max_tokens=1500)
            if isinstance(data, dict):
                data = data.get("questions", [])
            return data
        except Exception:
            pass
    # fallback: turn each segment's checkpoint question into a quiz item
    quiz = []
    for i, s in enumerate(segments[:n_questions]):
        quiz.append({
            "id": f"q{i+1}",
            "type": s.get("checkpoint_type") or "short_answer",
            "question": s.get("checkpoint_question") or f"Explain the main idea of: {s['title']}",
            "options": s.get("checkpoint_options"),
            "correct": s.get("checkpoint_correct") or s["title"],
            "concept": s["title"],
        })
    return quiz


def evaluate_answer(question: dict, student_answer: str):
    """Returns {"correct": bool, "feedback": str, "misconception": str|None}"""
    if llm.llm_available():
        system = (
            "You are a supportive but rigorous teacher grading one answer. "
            "If the answer reveals a misconception, name it precisely and explain "
            "the correct reasoning — do not just say 'wrong'. Respond with ONLY JSON."
        )
        prompt = f"""
Question: {question.get('question')}
Expected/correct answer or concept: {question.get('correct')}
Student's answer: {student_answer}

Return JSON:
{{"correct": true/false, "score": 0-1, "feedback": "constructive explanation",
  "misconception": "short description of the misconception, or null if answer is correct/reasonable"}}
"""
        try:
            return llm.call_json(system, prompt, max_tokens=500)
        except Exception:
            pass

    # fallback: simple keyword-overlap heuristic
    expected = str(question.get("correct", "")).lower()
    given = (student_answer or "").lower().strip()
    correct = False
    if question.get("type") == "mcq":
        correct = given == expected or given == expected[:1]
    else:
        expected_words = set(w for w in expected.split() if len(w) > 3)
        given_words = set(given.split())
        overlap = len(expected_words & given_words)
        correct = overlap >= max(1, len(expected_words) // 3)

    if correct:
        return {"correct": True, "score": 1.0,
                "feedback": "Correct — good understanding of this concept.",
                "misconception": None}
    return {"correct": False, "score": 0.0,
            "feedback": f"Not quite. The key idea here is: {question.get('correct')}. "
                        f"Let's revisit this concept with another explanation and example.",
            "misconception": f"Answer did not match expected concept for '{question.get('concept','this topic')}'."}


def build_learning_report(topic: str, results: list):
    """results: list of {"question":..., "concept":..., "correct":bool}"""
    total = len(results) or 1
    correct = sum(1 for r in results if r["correct"])
    score_pct = round(100 * correct / total)
    strong = sorted({r["concept"] for r in results if r["correct"]})
    weak = sorted({r["concept"] for r in results if not r["correct"]})

    recommendation = (
        f"Great grasp of {topic}! Consider moving on to more advanced material."
        if score_pct >= 80 else
        f"Revise: {', '.join(weak) if weak else topic} and retry a couple of practice questions."
    )

    return {
        "topic": topic,
        "score_percent": score_pct,
        "correct": correct,
        "total": total,
        "strong_areas": strong,
        "weak_areas": weak,
        "recommendation": recommendation,
        "next_topic_suggestion": _suggest_next(topic, weak),
    }


def _suggest_next(topic, weak_areas):
    if weak_areas:
        return f"Revise: {weak_areas[0]}"
    return f"Next topic after '{topic}' in a typical learning path."
