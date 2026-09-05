"""
profile_store.py — Persistent student learning profile (section 14).
Simple JSON-file store — swap for SQLite/Postgres for a production deploy.
"""
import json
import os
import threading
from datetime import datetime, timezone

_LOCK = threading.Lock()
_STORE_PATH = os.path.join(os.path.dirname(__file__), "storage", "profiles.json")


def _load_all():
    if not os.path.exists(_STORE_PATH):
        return {}
    with open(_STORE_PATH, "r") as f:
        return json.load(f)


def _save_all(data):
    os.makedirs(os.path.dirname(_STORE_PATH), exist_ok=True)
    with open(_STORE_PATH, "w") as f:
        json.dump(data, f, indent=2)


def get_profile(student_id: str) -> dict:
    with _LOCK:
        data = _load_all()
        return data.get(student_id, {
            "student_id": student_id,
            "topics_studied": [],
            "history": [],
            "strong_concepts": [],
            "weak_concepts": [],
            "current_learning_path": None,
        })


def record_session(student_id: str, topic: str, report: dict, learning_path=None):
    with _LOCK:
        data = _load_all()
        profile = data.get(student_id, {
            "student_id": student_id,
            "topics_studied": [],
            "history": [],
            "strong_concepts": [],
            "weak_concepts": [],
            "current_learning_path": None,
        })
        profile["topics_studied"].append(topic)
        profile["history"].append({
            "topic": topic,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "score_percent": report.get("score_percent"),
            "weak_areas": report.get("weak_areas", []),
            "strong_areas": report.get("strong_areas", []),
        })
        for c in report.get("strong_areas", []):
            if c not in profile["strong_concepts"]:
                profile["strong_concepts"].append(c)
        for c in report.get("weak_areas", []):
            if c not in profile["weak_concepts"]:
                profile["weak_concepts"].append(c)
        if learning_path:
            profile["current_learning_path"] = learning_path
        data[student_id] = profile
        _save_all(data)
        return profile
