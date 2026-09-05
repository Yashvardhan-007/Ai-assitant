# AI Teacher — AI Innovation Hackathon 2026 Submission

A human-like AI educator that turns uploaded material or any topic into a personalized,
narrated teaching video with an animated avatar, subject-aware visuals, in-lesson questions,
misconception detection, and an adaptive learning report.

📖 **Full documentation (architecture, AI/ML details, RAG design, honest limitations,
setup & deployment instructions) is in [`docs/README.md`](docs/README.md) — please read it
before the demo/jury walkthrough.**

## Quickstart

```bash
# 1. Backend
cd backend
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."     # optional but recommended
python main.py                             # http://localhost:5000

# 2. Frontend (new terminal)
cd frontend
python3 -m http.server 8080                # http://localhost:8080
```

Open `http://localhost:8080`, upload a document (or just type a topic), set level / time /
language, generate the lesson plan, generate the teaching video, then take the quiz to see
adaptive feedback and the final learning report.

## Project Layout

```
ai-teacher/
├── backend/            Flask API + all AI pipeline modules
│   ├── main.py
│   ├── requirements.txt
│   └── app/
│       ├── llm.py               Claude API wrapper (with offline fallback)
│       ├── parsers/document_parser.py   PDF/DOCX/PPTX/TXT extraction
│       ├── rag.py               chunking + TF-IDF retrieval
│       ├── lesson_planner.py    Understand -> Plan -> Explain
│       ├── assessment.py        quiz, grading, misconception detection
│       ├── translator.py        multilingual text
│       ├── tts.py                narration audio
│       ├── visuals.py           subject-aware slide rendering
│       ├── avatar.py            animated 2D presenter
│       ├── video_builder.py     assembles the final MP4 lesson
│       └── profile_store.py     per-student progress tracking
├── frontend/            plain HTML/CSS/JS single-page app
├── sample_data/          a sample chapter you can upload to try RAG mode
└── docs/README.md        full project documentation (read this for submission)
```

## Mandatory Requirements Coverage

See the table in `docs/README.md` §2 mapping every mandatory requirement (§17 of the
assessment) to the exact module that implements it.

## Honesty Note

Two components are implemented as clearly-labelled, working **stand-ins** rather than paid
third-party services (no paid avatar/TTS API access was available while building this): the
AI avatar is a 2D animated presenter, and voice uses free Google TTS. Both have a documented
swap-point in the code to upgrade to a paid provider. See `docs/README.md` §7–8 for details —
please disclose this to the jury as instructed in §16/§20 of the brief.
