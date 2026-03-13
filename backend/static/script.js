/**
 * script.js
 * Shared utilities used across all frontend pages.
 * Handles: API calls, session management, UI helpers
 */

// ─── Config ──────────────────────────────────────────────────────────────────
const API_BASE = "/api";

// ─── Session helpers ──────────────────────────────────────────────────────────

/** Save a value to sessionStorage */
function setSession(key, value) {
  sessionStorage.setItem(key, JSON.stringify(value));
}

/** Get a value from sessionStorage, parsed from JSON */
function getSession(key) {
  const val = sessionStorage.getItem(key);
  if (val === null) return null;
  try { return JSON.parse(val); } catch { return val; }
}

/** Get the session_id token. Redirect to login if missing. */
function requireAuth() {
  const sid = getSession("session_id");
  if (!sid) {
    window.location.href = "/login";
    return null;
  }
  return sid;
}

// ─── API helper ───────────────────────────────────────────────────────────────

/**
 * Simple fetch wrapper.
 * method: "GET" | "POST"
 * body: object (for POST, will be JSON-stringified)
 */
async function apiFetch(path, { method = "GET", body = null, formData = null } = {}) {
  const options = {
    method,
    headers: {}
  };

  if (formData) {
    options.body = formData; // Let browser set multipart headers
  } else if (body) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  const res = await fetch(API_BASE + path, options);
  const data = await res.json();
  return { ok: res.ok, status: res.status, data };
}

// ─── UI helpers ───────────────────────────────────────────────────────────────

/** Show a loading spinner inside a button */
function setButtonLoading(btn, loading) {
  if (loading) {
    btn._original = btn.innerHTML;
    btn.innerHTML = '<span class="spinner"></span>';
    btn.disabled = true;
  } else {
    btn.innerHTML = btn._original || btn.innerHTML;
    btn.disabled = false;
  }
}

/** Show an alert message in a target element */
function showAlert(el, message, type = "error") {
  el.className = `alert alert-${type}`;
  el.textContent = message;
  el.classList.remove("hidden");
}

/** Hide an alert element */
function hideAlert(el) {
  el.classList.add("hidden");
}

/** Animate a score ring SVG */
function animateRing(ringEl, percentage, color) {
  const fill = ringEl.querySelector(".ring-fill");
  const number = ringEl.querySelector(".ring-number");
  const circumference = 339;
  const offset = circumference - (percentage / 100) * circumference;

  fill.style.stroke = color || (percentage >= 75 ? "#10b981" : percentage >= 50 ? "#f59e0b" : "#ef4444");
  fill.style.strokeDashoffset = offset;
  number.textContent = percentage + "%";
}

/** Build a score ring HTML (call animateRing after inserting) */
function buildScoreRing() {
  return `
    <div class="score-ring">
      <svg viewBox="0 0 120 120" width="120" height="120">
        <circle class="ring-bg" cx="60" cy="60" r="54"/>
        <circle class="ring-fill" cx="60" cy="60" r="54"/>
      </svg>
      <div class="ring-label">
        <span class="ring-number">0%</span>
        <span class="ring-unit">score</span>
      </div>
    </div>`;
}

/** Play text-to-speech audio from the backend */
async function playTTS(text) {
  try {
    const res = await fetch(API_BASE + "/interview/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text })
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.play();
    return audio;
  } catch (e) {
    console.warn("TTS failed:", e);
    return null;
  }
}

// ─── Auto-init nav info ───────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  const jobEl = document.getElementById("nav-job");
  const compEl = document.getElementById("nav-company");
  if (jobEl) jobEl.textContent = getSession("job_role") || "—";
  if (compEl) compEl.textContent = getSession("company") || "—";
});
