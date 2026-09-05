# AI Teacher — Project Documentation
### AI Innovation Hackathon 2026 — "Build a Human-Like AI Educator That Teaches Through Video"

> ⚠️ **Read this first.** This is a genuine, runnable working prototype, not a mockup — every
> feature below actually executes end-to-end (you can trace the code and run it yourself).
> But two pieces are deliberately built as clearly-labelled, swappable stand-ins rather than
> paid third-party services, because this was built inside a sandboxed environment with no
> access to paid AI-avatar or premium-TTS APIs:
> - **Voice**: uses free Google TTS (`gTTS`), not a premium neural voice.
> - **Avatar**: uses a lightweight animated 2D cartoon presenter (mouth-flap synced to
>   narration length), not a photorealistic talking head (D-ID/HeyGen/Synthesia).
>
> Both have a single, documented "swap point" in the code (see §7 and §8) where you drop in a
> paid API key to upgrade to production-grade voice/avatar without touching the rest of the
> pipeline. **Please disclose this honestly to the jury** — that's exactly what §16 of the
> assessment brief asks teams to do for third-party services, and overstating capability is
> worse than being upfront about what's a placeholder.

---

## 1. Problem Statement

Traditional e-learning is either static pre-recorded video or a text-based Q&A chatbot —
neither replicates how a real teacher plans a lesson, explains progressively, checks
understanding, and adapts. This project builds an **AI Teacher** that takes uploaded material
or a topic, plans a personalized lesson, delivers it as a narrated video with an avatar and
subject-aware visuals, questions the student during and after the lesson, detects
misconceptions, and produces a learning report with next-step recommendations.

## 2. Solution Overview

A Flask backend implements the full **Understand → Plan → Explain → Demonstrate → Question →
Evaluate → Adapt → Continue** loop as a pipeline of small, swappable modules, fronted by a
plain HTML/JS single-page UI. Every mandatory requirement in §17 of the brief is implemented:

| # | Mandatory requirement | Where it's implemented |
|---|---|---|
| 1 | Learning from uploaded material | `document_parser.py` + `rag.py` |
| 2 | Topic-based teaching | `lesson_planner.py` (works with or without material) |
| 3 | AI-generated lesson structure | `lesson_planner.build_lesson_plan()` |
| 4 | Personalized teaching | level/time/language/style params throughout |
| 5 | Human-like teaching interaction | segment → checkpoint question → evaluate → adapt loop |
| 6 | Video-based AI Teacher presentation | `video_builder.py` |
| 7 | AI voice | `tts.py` |
| 8 | Human-like AI avatar | `avatar.py` |
| 9 | Multilingual capability | `translator.py` + gTTS language codes |
| 10 | Student questioning and assessment | `assessment.py` |
| 11 | Adaptive response to student performance | `evaluate_answer()` + `build_learning_report()` |
| 12 | Working application/prototype | `frontend/` + `backend/` (runs locally, see §9) |

## 3. System Architecture

```
                 ┌───────────────────────────┐
                 │        Frontend (SPA)      │
                 │  upload / topic / prefs    │
                 │  plan viewer / video player│
                 │  quiz UI / report / profile│
                 └─────────────┬─────────────┘
                               │ REST (JSON / multipart)
                 ┌─────────────▼─────────────┐
                 │        Flask API           │
                 │        (main.py)           │
                 └───┬─────────┬──────────┬───┘
       ┌─────────────┘         │          └───────────────┐
       ▼                       ▼                          ▼
┌─────────────┐      ┌──────────────────┐        ┌──────────────────┐
│ document_    │      │ lesson_planner /  │        │ assessment.py     │
│ parser.py    │─────▶│ rag.py (RAG)      │        │ (quiz, evaluate,  │
│ (pdf/docx/   │      │ + llm.py (Claude) │        │ misconceptions,   │
│  pptx/txt)   │      └─────────┬────────┘        │ reports)          │
└─────────────┘                │                  └─────────┬────────┘
                                ▼                            │
                     ┌────────────────────┐                  │
                     │ video_builder.py    │                  │
                     │  ├─ tts.py (voice)  │                  │
                     │  ├─ visuals.py      │                  │
                     │  │  (subject-aware  │                  │
                     │  │   slides)        │                  │
                     │  └─ avatar.py       │                  │
                     │    (animated 2D     │                  │
                     │     presenter)      │                  │
                     └─────────┬──────────┘                  │
                               ▼                              ▼
                        static/videos/*.mp4          profile_store.py
                                                     (per-student progress)
```

## 4. AI/ML Models Used

- **LLM**: Anthropic Claude (`claude-sonnet-4-6` by default, configurable via
  `ANTHROPIC_MODEL`) — used for lesson planning, explanation generation, quiz generation,
  answer evaluation/misconception detection, when `ANTHROPIC_API_KEY` is set.
- **Retrieval**: TF-IDF + cosine similarity (`scikit-learn`) over chunked document text — no
  embedding API required, fully offline-capable.
- **TTS**: gTTS (Google Translate TTS), free tier, no key required.
- **Translation**: `deep-translator` (Google Translate backend), free, no key required.

**No fallback ever fabricates facts**: when no LLM key is configured, the system falls back
to an *extractive* approach (pulling real sentences from retrieved document chunks) instead of
generating plausible-sounding but unverified text — this directly follows the brief's
instruction (§3) to minimize hallucinated information.

## 5. RAG / Knowledge-Grounding Implementation

1. Uploaded file → `document_parser.py` extracts per-page/per-slide text (PDF via `pypdf`,
   DOCX via `python-docx`, PPTX via `python-pptx`, including speaker notes).
2. `rag.chunk_pages()` splits text into ~700-character overlapping chunks, keeping the
   source page/slide number attached to each chunk.
3. `rag.DocumentIndex` builds a TF-IDF matrix over the chunks for the session.
4. When planning a lesson, the student's topic/instruction is used as the retrieval query;
   the top-k most relevant chunks are passed to the LLM as grounding context (or, in
   fallback mode, directly extracted from).
5. This keeps every generated explanation traceable back to a specific page/slide of the
   source material, and prevents the system from inventing facts not present in it.

**Swap point** for higher-quality retrieval: replace `TfidfVectorizer` in `rag.py` with
sentence-transformer embeddings + a vector DB (FAISS/Chroma) — the `retrieve()` interface is
unchanged.

## 6. Prompt / Agent Architecture

Three focused system prompts (in `llm.py`-driven modules), each scoped to one job so outputs
stay structured and JSON-parseable rather than free-form chat:
- **Lesson planning prompt** (`lesson_planner._plan_with_llm`): plans + writes segment-by-
  segment content, grounded in retrieved material when present, tailored to level/time/style.
- **Quiz generation prompt** (`assessment.generate_quiz`): writes assessment questions
  strictly from the lesson content just taught.
- **Answer evaluation prompt** (`assessment.evaluate_answer`): grades one answer, explicitly
  asked to name the *misconception* behind a wrong answer rather than just marking it wrong
  (directly implementing §12 of the brief).

Each has a deterministic, non-LLM fallback so the pipeline never breaks if the API is
unavailable (see §4).

## 7. Voice / TTS Implementation — honest limitations

`tts.py` uses `gTTS` (Google's free text-to-speech). It supports ~20 languages including
Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati, Kannada, Malayalam, Punjabi, Urdu, and
several international languages (see `translator.py:LANGUAGES`).

If the TTS provider is unreachable (e.g. restricted network), `tts.generate_speech()`
automatically falls back to a placeholder audio track of the correct estimated duration so
the rest of the pipeline (timing, avatar sync, video length) keeps working — this fallback
is logged clearly to the console and is **not** meant to be presented as real narration.

**Swap point**: replace the body of `generate_speech()` with a call to ElevenLabs / Azure
Neural TTS / OpenAI TTS for production-quality, more human voices. The function signature
(`text, language_name, out_path → path`) is designed to make this a drop-in change.

## 8. Avatar / Video Generation — honest limitations

`avatar.py` draws a simple, friendly 2D animated presenter (PIL-rendered) whose mouth cycles
through open/closed states approximately timed to the narration length, with occasional
blinking. This is **not** a photorealistic talking-head avatar. Building one requires a paid
third-party avatar API (D-ID, HeyGen, Synthesia, etc.) which needs network access and API
keys this environment doesn't have.

`video_builder.py` composites, per lesson segment: the narration audio (§7) + a subject-aware
slide (`visuals.py`: equations/graphs for math, diagrams/formulas for physics, timelines for
history, code blocks for programming, etc., per §10 of the brief) + the animated avatar
overlay, into one MP4 per segment, then concatenates all segments into the final lesson video.

**Swap point**: in `video_builder.build_segment_clip()`, replace the `_avatar_clip()` call
with: send the generated `audio_path` to a real avatar API, receive back a talking-head video
clip, and composite that instead of the PIL frames — nothing else in the pipeline changes.

## 9. Personalization Approach

Every lesson plan call takes `level` (beginner/intermediate/advanced — mapped to concrete
language/depth guidance in `LEVEL_GUIDANCE`), `minutes` (mapped to a segment-count/depth
profile in `TIME_PROFILES`, per §7 of the brief: 5/20/60 minutes → 2/4/7 segments), and
`language`. The subject area is auto-detected from the topic (`guess_subject()`) to choose
appropriate visual types (§10).

## 10. Assessment Methodology

After the lesson, `assessment.generate_quiz()` produces MCQ + short-answer questions tied to
each segment/concept taught. `evaluate_answer()` grades each answer and — critically — asks
the LLM (or a keyword-overlap heuristic, in fallback mode) to name the *specific
misconception*, not just mark right/wrong, matching the worked example in §12 of the brief.
`build_learning_report()` aggregates results into a score, strong/weak concept lists, and a
plain-language recommendation + suggested next topic (§13).

## 11. Multilingual Implementation

`translator.py` maps a human-readable language name to both a translation code and a gTTS
voice code, covering major Indian languages (Hindi, Bengali, Tamil, Telugu, Marathi,
Gujarati, Kannada, Malayalam, Punjabi, Urdu) plus international ones. The LLM lesson prompt
is asked to write directly in the requested language when an LLM is configured; in fallback
mode, `deep-translator` translates the generated text before narration. "Hinglish" is mapped
to Hindi voice/translation with a note in the prompt to keep code-mixed phrasing when an LLM
is available.

## 12. Student Learning Profile

`profile_store.py` is a simple JSON-file-backed store (swap for SQLite/Postgres in
production) keyed by `student_id`, recording topics studied, timestamps, scores, and
strong/weak concepts across sessions — used to personalize future recommendations (§14).

## 13. APIs and Third-Party Services Used

| Service | Used for | Cost | Required? |
|---|---|---|---|
| Anthropic Claude API | lesson planning, quiz gen, grading | paid (your key) | Optional — richer output when configured |
| Google Translate TTS (via `gTTS`) | narration audio | free | Yes (or supply your own TTS) |
| Google Translate (via `deep-translator`) | text translation | free | Yes (or supply your own) |
| — | avatar video | — | Not used — see §8 for the honest placeholder + swap point |

No other third-party APIs, models, or paid services are used, per the disclosure requirement
in §16/§20 of the brief.

## 14. Setup Instructions

```bash
cd backend
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."   # optional, but strongly recommended for full quality
python main.py                          # starts API on http://localhost:5000
```

In a second terminal:
```bash
cd frontend
python3 -m http.server 8080             # serves the UI on http://localhost:8080
```
Open `http://localhost:8080` in a browser. If your backend runs on a different host/port, set
`window.API_BASE` at the top of `app.js` (or via a `<script>` before `app.js` loads).

## 15. Deployment Instructions

- **Backend**: any host that can run Python + ffmpeg (e.g. a small VM, Render, Railway,
  Fly.io). Ensure `ffmpeg` is installed on the host (used by `moviepy` for video encoding).
  Set `ANTHROPIC_API_KEY` as an environment variable/secret.
- **Frontend**: any static host (Netlify, Vercel, GitHub Pages, or served by Flask itself).
  Set `window.API_BASE` to your deployed backend URL.
- Generated audio/video/slide files are written to `backend/app/static/...` and served by
  Flask's static route — for scale, point these at object storage (S3-compatible) instead.

## 16. Known Limitations

- Avatar is a stylized 2D animation, not a photoreal talking head (see §8 for the swap point).
- Voice uses free gTTS, which is lower quality than paid neural TTS (see §7).
- RAG uses TF-IDF, not semantic embeddings — works well for keyword-adjacent queries, less
  well for queries phrased very differently from the source wording.
- Without an `ANTHROPIC_API_KEY`, topic-based teaching (no uploaded material) falls back to a
  transparent scaffold rather than fabricated explanations — by design, to avoid
  hallucination, but it means the fallback mode is a structural demo rather than a full
  lesson. Configuring the API key unlocks full lesson quality.
- `profile_store.py` is single-file JSON — fine for a hackathon demo, not for concurrent
  production users.
- Heading/table-of-contents auto-detection (`rag.top_headings()`) is a lightweight regex
  heuristic and may miss headings in inconsistently formatted documents.

## 17. Demo Video Script Suggestion (3–7 min)

1. Upload a sample chapter PDF → show detected sections (10s)
2. Type an instruction like the brief's example scenario, set level/time/language (15s)
3. Show generated lesson plan segments (20s)
4. Play the generated AI teaching video (60–90s)
5. Answer a couple of quiz questions, show adaptive misconception feedback (45s)
6. Show the learning report + profile update (20s)
7. Repeat steps 2–4 quickly with a different topic + language to show generality (30s)
