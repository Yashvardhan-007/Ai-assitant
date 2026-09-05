// Point this at wherever backend/main.py is running.
const API_BASE = window.API_BASE || "http://localhost:5000";

let sessionId = null;
let currentPlan = null;
let currentQuiz = [];
let quizResults = [];

const $ = (id) => document.getElementById(id);

async function checkHealth() {
  try {
    const r = await fetch(`${API_BASE}/api/health`);
    const d = await r.json();
    $("apiStatus").textContent = d.llm_configured
      ? "✅ Backend connected — LLM configured (full AI-generated lessons)"
      : "⚠️ Backend connected — no ANTHROPIC_API_KEY set (running in rule-based fallback mode; see docs/README.md)";
  } catch (e) {
    $("apiStatus").textContent = "❌ Cannot reach backend at " + API_BASE + " — start backend/main.py first.";
  }
}
checkHealth();

// ---------- Step 1: upload ----------
$("uploadBtn").onclick = async () => {
  const file = $("fileInput").files[0];
  if (!file) { $("uploadResult").textContent = "Choose a file first."; return; }
  const fd = new FormData();
  fd.append("file", file);
  $("uploadResult").textContent = "Uploading & indexing...";
  const r = await fetch(`${API_BASE}/api/upload`, { method: "POST", body: fd });
  const d = await r.json();
  if (d.error) { $("uploadResult").textContent = "Error: " + d.error; return; }
  sessionId = d.session_id;
  $("uploadResult").textContent =
    `Indexed "${d.filename}" — ${d.num_pages} pages/slides, ${d.num_chunks} chunks.` +
    (d.suggested_headings.length ? `\nDetected sections: ${d.suggested_headings.join(", ")}` : "");
};

// ---------- Step 2/3: lesson plan ----------
$("planBtn").onclick = async () => {
  const topic = $("topicInput").value.trim();
  if (!topic) { alert("Enter a topic or chapter name (even if you uploaded material, tell me what to teach from it)."); return; }
  const body = {
    topic,
    session_id: sessionId,
    level: $("level").value,
    minutes: parseInt($("minutes").value, 10),
    language: $("language").value,
  };
  $("planSection").style.display = "block";
  $("planMeta").textContent = "Planning lesson...";
  $("planSegments").innerHTML = "";
  const r = await fetch(`${API_BASE}/api/lesson/plan`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const plan = await r.json();
  if (plan.error) { $("planMeta").textContent = "Error: " + plan.error; return; }
  currentPlan = plan;
  renderPlan(plan);
  $("quizSection").style.display = "block";
};

function renderPlan(plan) {
  const m = plan.meta;
  $("planMeta").innerHTML =
    `<strong>${plan.title}</strong><br>${plan.introduction}<br>` +
    `<span class="badge">${m.level}</span><span class="badge">${m.minutes} min</span>` +
    `<span class="badge">${m.language}</span><span class="badge">${m.subject}</span>` +
    `<span class="badge">${m.grounded_in_material ? "grounded in your material" : "general knowledge"}</span>` +
    `<span class="badge">${m.llm_generated ? "LLM-generated" : "rule-based fallback"}</span>`;
  $("planSegments").innerHTML = plan.segments.map((s, i) => `
    <div class="segment">
      <h4>${i + 1}. ${s.title} <span class="badge">${s.visual_type}</span></h4>
      <div>${s.explanation}</div>
      ${s.example ? `<div class="ex"><em>Example:</em> ${s.example}</div>` : ""}
    </div>
  `).join("");
}

// ---------- Step 3b: video ----------
$("videoBtn").onclick = async () => {
  if (!currentPlan) return;
  $("videoStatus").textContent = "Rendering AI teaching video (audio + slides + avatar)... this can take a bit.";
  const r = await fetch(`${API_BASE}/api/lesson/video`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plan: currentPlan, language: $("language").value }),
  });
  const d = await r.json();
  if (d.error) { $("videoStatus").textContent = "Error: " + d.error; return; }
  $("videoStatus").textContent = `Done — ${Math.round(d.duration_seconds)}s video.`;
  const v = $("lessonVideo");
  v.src = `${API_BASE}${d.video_url}`;
  v.style.display = "block";
};

// ---------- Step 4: quiz ----------
$("quizBtn").onclick = async () => {
  quizResults = [];
  $("reportArea").innerHTML = "";
  $("reportBtn").style.display = "none";
  const r = await fetch(`${API_BASE}/api/quiz/generate`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plan: currentPlan, n_questions: 5 }),
  });
  const d = await r.json();
  currentQuiz = d.questions;
  renderQuiz();
};

function renderQuiz() {
  $("quizArea").innerHTML = currentQuiz.map((q, i) => `
    <div class="question-block" id="q-${i}">
      <div><strong>Q${i + 1}.</strong> ${q.question}</div>
      ${q.type === "mcq" && q.options ? q.options.map((opt, oi) =>
        `<button class="option-btn" onclick="submitAnswer(${i}, '${opt.replace(/'/g, "\\'")}')">${opt}</button>`
      ).join("") : `
        <input type="text" id="ans-${i}" placeholder="Type your answer..." style="width:100%;margin-top:6px" />
        <button onclick="submitAnswer(${i}, document.getElementById('ans-${i}').value)">Submit</button>
      `}
      <div class="feedback" id="fb-${i}"></div>
    </div>
  `).join("");
}

async function submitAnswer(i, answer) {
  const q = currentQuiz[i];
  const r = await fetch(`${API_BASE}/api/quiz/answer`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question: q, answer }),
  });
  const result = await r.json();
  const fb = document.getElementById(`fb-${i}`);
  fb.className = "feedback " + (result.correct ? "correct" : "incorrect");
  fb.textContent = (result.correct ? "✅ " : "❌ ") + result.feedback +
    (result.misconception ? `\nMisconception noted: ${result.misconception}` : "");
  quizResults[i] = { question: q.question, concept: q.concept, correct: !!result.correct };
  if (quizResults.filter(Boolean).length === currentQuiz.length) {
    $("reportBtn").style.display = "block";
  }
}
window.submitAnswer = submitAnswer;

$("reportBtn").onclick = async () => {
  const r = await fetch(`${API_BASE}/api/quiz/report`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      topic: currentPlan.meta.topic,
      results: quizResults,
      student_id: $("studentId").value.trim() || null,
    }),
  });
  const report = await r.json();
  $("reportArea").innerHTML = `
    <div class="report-card">
      <div class="score-big">${report.score_percent}%</div>
      <div>Topic: <strong>${report.topic}</strong> — ${report.correct}/${report.total} correct</div>
      <div>Strong areas: ${report.strong_areas.join(", ") || "—"}</div>
      <div>Needs improvement: ${report.weak_areas.join(", ") || "—"}</div>
      <div style="margin-top:8px"><em>${report.recommendation}</em></div>
    </div>
  `;
};

// ---------- Step 5: profile ----------
$("profileBtn").onclick = async () => {
  const id = $("studentId").value.trim();
  if (!id) return;
  const r = await fetch(`${API_BASE}/api/profile/${encodeURIComponent(id)}`);
  const p = await r.json();
  $("profileArea").textContent = JSON.stringify(p, null, 2);
};
