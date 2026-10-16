const views = ["dashboard", "bottlenecks", "forecast", "ask"];

function switchView(name) {
  document.querySelectorAll(".nav-link").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === name);
  });
  views.forEach((view) => {
    document.getElementById(`view-${view}`).classList.toggle("active", view === name);
  });
}

document.querySelectorAll(".nav-link").forEach((button) => {
  button.addEventListener("click", () => switchView(button.dataset.view));
});

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail || "The request could not be completed.");
  return body;
}

function riskClass(risk) {
  return risk.toLowerCase();
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

function showError(container, message, columns = 1) {
  container.innerHTML = `<tr><td class="loading-cell" colspan="${columns}">${escapeHtml(message)}</td></tr>`;
}

async function loadStatus() {
  const banner = document.getElementById("mode-banner");
  try {
    const status = await fetchJson("/api/status");
    const local = status.mode === "local";
    banner.classList.toggle("local", local);
    banner.textContent = local ? "AI running locally (Ollama)" : "Fallback mode (rule-based)";
  } catch {
    banner.classList.remove("local");
    banner.textContent = "Fallback mode (rule-based)";
  }
}

async function loadDashboard() {
  const tbody = document.getElementById("department-rows");
  try {
    const data = await fetchJson("/api/dashboard");
    const counts = [data.counts.normal, data.counts.warning, data.counts.critical];
    document.querySelectorAll(".metric-value").forEach((element, index) => {
      element.textContent = counts[index];
    });
    tbody.innerHTML = data.departments.map((row) => `
      <tr>
        <td>${escapeHtml(row.department)}</td>
        <td>${escapeHtml(row.appointments)}</td>
        <td>${escapeHtml(row.staff_available)}</td>
        <td>${escapeHtml(row.emergency_cases)}</td>
        <td class="util-cell">${(row.utilization * 100).toFixed(1)}%</td>
        <td><span class="risk-badge ${escapeHtml(riskClass(row.risk))}">${escapeHtml(row.risk)}</span></td>
      </tr>`).join("");
  } catch (error) {
    showError(tbody, `Unable to load metrics: ${error.message}`, 6);
  }
}

async function loadBottlenecks() {
  const container = document.getElementById("bottleneck-list");
  try {
    const { bottlenecks } = await fetchJson("/api/bottlenecks");
    if (!bottlenecks.length) {
      container.innerHTML = '<article class="panel loading-cell">No departments are currently flagged.</article>';
      return;
    }
    container.innerHTML = bottlenecks.map((item) => `
      <article class="panel bottleneck-card">
        <div class="bottleneck-top"><h3>${escapeHtml(item.department)}</h3><span class="risk-badge ${escapeHtml(riskClass(item.risk))}">${escapeHtml(item.risk)}</span></div>
        <div class="bottleneck-grid">
          <div><h4>Evidence</h4><table class="evidence-table"><tbody>
            <tr><td>Appointments</td><td>${escapeHtml(item.evidence.appointments)}</td></tr>
            <tr><td>Available staff</td><td>${escapeHtml(item.evidence.staff)}</td></tr>
            <tr><td>Avg. task time</td><td>${escapeHtml(item.evidence.avg_task_minutes)} min</td></tr>
            <tr><td>Emergency cases</td><td>${escapeHtml(item.evidence.emergency_cases)}</td></tr>
            <tr><td>Utilization</td><td>${escapeHtml(item.evidence.utilization_percent)}%</td></tr>
          </tbody></table></div>
          <div><h4>What the data suggests</h4><p class="explanation">${escapeHtml(item.explanation.problem)}</p><p class="risk-window">${escapeHtml(item.explanation.risk_window)}</p></div>
          <div><h4>Management actions</h4><ol class="action-list">${item.explanation.actions.map((action) => `<li>${escapeHtml(action)}</li>`).join("")}</ol></div>
        </div>
      </article>`).join("");
  } catch (error) {
    container.innerHTML = `<article class="panel loading-cell">Unable to load bottlenecks: ${escapeHtml(error.message)}</article>`;
  }
}

async function loadForecast() {
  const container = document.getElementById("forecast-chart");
  try {
    const { departments } = await fetchJson("/api/forecast");
    container.innerHTML = departments.map((row) => {
      const percent = row.utilization * 100;
      const width = Math.min(percent / 150 * 100, 100);
      return `<div class="forecast-row">
        <span class="forecast-department">${escapeHtml(row.department)}</span>
        <div class="bar-track"><div class="bar-fill ${escapeHtml(riskClass(row.risk))}" style="width:${width}%"></div><span class="forecast-value" style="--bar-width:${width}%">${percent.toFixed(1)}%</span></div>
      </div>`;
    }).join("");
  } catch (error) {
    container.innerHTML = `<p class="loading-cell">Unable to load forecast: ${escapeHtml(error.message)}</p>`;
  }
}

const form = document.getElementById("ask-form");
const questionInput = document.getElementById("question-input");
const answerBox = document.getElementById("answer-box");
const charCount = document.getElementById("char-count");
questionInput.addEventListener("input", () => {
  charCount.textContent = `${questionInput.value.length} / 300`;
});
document.querySelectorAll(".example-question").forEach((button) => {
  button.addEventListener("click", () => {
    questionInput.value = button.textContent;
    charCount.textContent = `${questionInput.value.length} / 300`;
    questionInput.focus();
  });
});
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = form.querySelector("button[type=submit]");
  button.disabled = true;
  button.textContent = "Thinking…";
  answerBox.hidden = false;
  answerBox.classList.remove("error");
  answerBox.textContent = "Looking at the operational data…";
  try {
    const result = await fetchJson("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: questionInput.value }),
    });
    answerBox.textContent = result.answer;
  } catch (error) {
    answerBox.classList.add("error");
    answerBox.textContent = error.message || "Unable to answer right now. Please try again.";
  } finally {
    button.disabled = false;
    button.innerHTML = 'Ask question <span>→</span>';
  }
});

loadStatus();
loadDashboard();
loadBottlenecks();
loadForecast();
