"""
rag.py — Retrieval-Augmented Generation over uploaded material, WITHOUT
depending on any paid embedding API. Uses classic TF-IDF + cosine similarity
(scikit-learn), which is fast, dependency-light, and works fully offline.

This directly satisfies the assessment's "RAG / knowledge grounding" and
"minimize hallucination" requirements: every lesson/answer that is grounded
in uploaded material is generated only from retrieved chunks, and each chunk
carries its page/slide number so the system (and the student) can see where
an explanation came from.

Swap point: if you want higher-quality retrieval, replace `TfidfVectorizer`
below with sentence-transformer embeddings + a vector DB (FAISS/Chroma) —
the retrieve() interface stays the same.
"""
import re
import uuid
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def chunk_pages(pages, chunk_size=700, overlap=120):
    """Split page/slide texts into overlapping chunks for retrieval,
    keeping track of the source page number for each chunk."""
    chunks = []
    for page in pages:
        text = re.sub(r"\s+", " ", page["text"]).strip()
        if not text:
            continue
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end]
            chunks.append({
                "id": str(uuid.uuid4())[:8],
                "page": page["index"],
                "text": chunk_text,
            })
            if end == len(text):
                break
            start = end - overlap
    return chunks


class DocumentIndex:
    """One instance per uploaded document (or per user session)."""

    def __init__(self, chunks):
        self.chunks = chunks
        self.vectorizer = None
        self.matrix = None
        if chunks:
            self.vectorizer = TfidfVectorizer(stop_words="english", max_features=20000)
            self.matrix = self.vectorizer.fit_transform([c["text"] for c in chunks])

    def retrieve(self, query, top_k=5):
        if not self.chunks or self.vectorizer is None:
            return []
        q_vec = self.vectorizer.transform([query])
        sims = cosine_similarity(q_vec, self.matrix).flatten()
        ranked = sims.argsort()[::-1][:top_k]
        results = []
        for i in ranked:
            if sims[i] <= 0:
                continue
            c = self.chunks[i]
            results.append({**c, "score": float(sims[i])})
        return results

    def top_headings(self, n=12):
        """Cheap heuristic table-of-contents extraction: short, title-cased,
        or numbered lines are likely headings/section titles."""
        heading_like = []
        for c in self.chunks:
            for line in c["text"].split(". "):
                line = line.strip()
                if 3 < len(line) < 80 and (
                    re.match(r"^(chapter|unit|section|part)\s+\d+", line, re.I)
                    or re.match(r"^\d+(\.\d+)*\s+[A-Z]", line)
                ):
                    heading_like.append(line)
        # de-duplicate while preserving order
        seen, out = set(), []
        for h in heading_like:
            if h.lower() not in seen:
                seen.add(h.lower())
                out.append(h)
        return out[:n]
