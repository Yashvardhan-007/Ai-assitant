"""
lesson_planner.py — The "brain" of the AI Teacher.

Implements the Understand -> Plan -> Explain -> Demonstrate -> Question ->
Evaluate -> Adapt -> Continue loop described in the assessment brief.

Two modes:
  * With ANTHROPIC_API_KEY configured: Claude plans and writes the lesson,
    grounded in retrieved RAG chunks when material was uploaded.
  * Without a key: a deterministic rule-based fallback still produces a
    structured, leveled, time-boxed lesson (extractive from uploaded
    material when available) so the app is demoable out of the box.
"""
import re
from . import llm

TIME_PROFILES = {
    5:  {"segments": 2, "depth": "concise", "label": "quick overview"},
    20: {"segments": 4, "depth": "structured", "label": "structured lesson"},
    60: {"segments": 7, "depth": "deep", "label": "in-depth lesson"},
}


def _time_bucket(minutes: int):
    """Map an arbitrary minute value onto the closest defined depth profile."""
    if minutes is None:
        minutes = 20
    if minutes <= 10:
        return 5, TIME_PROFILES[5]
    if minutes <= 40:
        return 20, TIME_PROFILES[20]
    return 60, TIME_PROFILES[60]


LEVEL_GUIDANCE = {
    "beginner": "Use everyday language, analogies, and avoid jargon. Build intuition first.",
    "intermediate": "Use correct technical terminology with practical, applied examples.",
    "advanced": "Use precise technical/mathematical language, edge cases, and implementation depth.",
}

VISUAL_HINTS = {
    "mathematics": ["equation", "graph", "step-by-step solution"],
    "physics": ["diagram", "formula", "process animation"],
    "biology": ["labeled diagram", "process flow"],
    "history": ["timeline", "map"],
    "programming": ["code block", "execution flow diagram", "architecture diagram"],
    "general": ["concept diagram", "example illustration"],
}


def guess_subject(topic: str) -> str:
    t = topic.lower()
    if any(k in t for k in ["equation", "algebra", "calculus", "geometry", "math"]):
        return "mathematics"
    if any(k in t for k in ["force", "current", "voltage", "physics", "energy", "motion", "circuit"]):
        return "physics"
    if any(k in t for k in ["cell", "biology", "organism", "photosynthesis", "gene", "anatomy"]):
        return "biology"
    if any(k in t for k in ["war", "history", "empire", "revolution", "century", "dynasty"]):
        return "history"
    if any(k in t for k in ["code", "programming", "react", "python", "algorithm", "software", "api"]):
        return "programming"
    return "general"


def build_lesson_plan(topic: str, level: str, minutes: int, language: str,
                       style: str = "balanced", retrieved_chunks=None):
    """Returns a structured lesson plan dict, grounded in retrieved_chunks
    when provided (RAG mode) or generated from general knowledge otherwise."""
    level = (level or "beginner").lower()
    subject = guess_subject(topic)
    _, profile = _time_bucket(minutes)
    grounded = bool(retrieved_chunks)

    if llm.llm_available():
        plan = _plan_with_llm(topic, level, minutes, style, subject, profile, retrieved_chunks)
    else:
        plan = _plan_fallback(topic, level, minutes, subject, profile, retrieved_chunks)

    plan["meta"] = {
        "topic": topic,
        "level": level,
        "minutes": minutes,
        "language": language,
        "style": style,
        "subject": subject,
        "grounded_in_material": grounded,
        "llm_generated": llm.llm_available(),
    }
    return plan


def _plan_with_llm(topic, level, minutes, style, subject, profile, chunks):
    context_block = ""
    if chunks:
        context_block = "\n\n".join(f"[Source p.{c['page']}] {c['text']}" for c in chunks)

    system = (
        "You are an expert, patient human teacher creating a personalized lesson. "
        "You must behave like a real teacher: introduce the topic, explain concepts "
        "progressively, give examples, ask checking questions at suitable points, "
        "and never just dump information. Only use facts present in the provided "
        "source material when source material is given — do not hallucinate facts "
        "that aren't supported by it. Respond with ONLY valid JSON, no commentary."
    )
    prompt = f"""
Topic: {topic}
Learner level: {level} ({LEVEL_GUIDANCE.get(level, LEVEL_GUIDANCE['beginner'])})
Time available: {minutes} minutes -> aim for about {profile['segments']} teaching segments, depth={profile['depth']}
Teaching style preference: {style}
Subject area (for visual style): {subject}
{"Grounding material (cite page numbers implicitly by staying faithful to it):" if chunks else "No uploaded material — teach from general knowledge, being conservative about precise facts/figures."}
{context_block}

Produce a JSON lesson plan with this exact shape:
{{
  "title": "...",
  "introduction": "1-2 sentence hook introducing the topic",
  "segments": [
    {{
      "title": "...",
      "explanation": "the actual teaching explanation, {LEVEL_GUIDANCE.get(level,'')}",
      "example": "a concrete example or analogy",
      "visual_type": "one of: equation | graph | diagram | timeline | code | image | process",
      "visual_description": "what the visual should show, described concretely enough to render",
      "checkpoint_question": "a question to ask the student after this segment, or null if not needed here",
      "checkpoint_type": "mcq | short_answer | conceptual | none"
      "checkpoint_options": ["a","b","c","d"] or null (only for mcq)
      "checkpoint_correct": "the correct option text or short answer, or null"
    }}
  ],
  "closing_summary": "wrap-up of what was covered and transition to assessment"
}}
Segments count should be approximately {profile['segments']}.
"""
    try:
        return llm.call_json(system, prompt, max_tokens=3000)
    except Exception:
        return _plan_fallback(topic, level, minutes, subject, profile, chunks)


def _split_sentences(text):
    sents = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sents if len(s.strip()) > 15]


def _plan_fallback(topic, level, minutes, subject, profile, chunks):
    """Deterministic, no-LLM lesson generation. When material is supplied,
    this is extractive (grounded, no hallucination) — pulling real sentences
    from the retrieved chunks. Without material, it produces an honest
    scaffold explaining that rich original explanation needs an LLM key."""
    n = profile["segments"]
    hints = VISUAL_HINTS.get(subject, VISUAL_HINTS["general"])
    segments = []

    if chunks:
        # Build segments by grouping retrieved chunks and pulling out
        # informative sentences (basic extractive summarization).
        pool = []
        for c in chunks:
            pool.extend(_split_sentences(c["text"]))
        if not pool:
            pool = [f"(Source material for '{topic}' did not contain extractable sentences.)"]
        per_seg = max(1, len(pool) // n)
        for i in range(n):
            seg_sents = pool[i * per_seg: (i + 1) * per_seg] or pool[:2]
            explanation = " ".join(seg_sents[:4])
            example = seg_sents[4] if len(seg_sents) > 4 else (
                "Consider how this idea applies in a real, everyday situation related to "
                f"'{topic}'."
            )
            segments.append({
                "title": f"Part {i + 1}: Key idea from the material",
                "explanation": explanation or f"Reviewing material relevant to {topic}.",
                "example": example,
                "visual_type": hints[i % len(hints)],
                "visual_description": f"Illustrate: {explanation[:120]}",
                "checkpoint_question": f"In your own words, what is the main idea of Part {i + 1}?",
                "checkpoint_type": "short_answer",
                "checkpoint_options": None,
                "checkpoint_correct": None,
            })
    else:
        # No material, no LLM: transparent scaffold rather than fabricated
        # "facts" — still structurally complete and demoable.
        level_note = LEVEL_GUIDANCE.get(level, LEVEL_GUIDANCE["beginner"])
        for i in range(n):
            segments.append({
                "title": f"Part {i + 1} of '{topic}'",
                "explanation": (
                    f"[No ANTHROPIC_API_KEY configured — connect an LLM to generate real "
                    f"{level} explanations here.] This segment would explain a key sub-concept "
                    f"of '{topic}' at {level} depth. {level_note}"
                ),
                "example": f"An example illustrating part {i + 1} of {topic} would appear here.",
                "visual_type": hints[i % len(hints)],
                "visual_description": f"Illustration for part {i + 1} of {topic}.",
                "checkpoint_question": f"What did you understand about part {i + 1}?",
                "checkpoint_type": "short_answer",
                "checkpoint_options": None,
                "checkpoint_correct": None,
            })

    return {
        "title": f"Lesson: {topic}",
        "introduction": f"Today we'll learn about {topic}, tailored for a {level} learner in about {minutes} minutes.",
        "segments": segments,
        "closing_summary": f"We covered {n} key parts of {topic}. Let's check your understanding with a short assessment.",
    }
