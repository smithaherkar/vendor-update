// ---------------------------------------------------------
// Vendor Intelligence — frontend logic
// Talks to the FastAPI backend running at API_BASE_URL.
// ---------------------------------------------------------

const API_BASE_URL = window.location.port === "8000" ? "" : "http://localhost:8000";

const invoiceForm = document.getElementById("invoiceForm");
const invoiceResult = document.getElementById("invoiceResult");

const freightForm = document.getElementById("freightForm");
const freightResult = document.getElementById("freightResult");

const assistantForm = document.getElementById("assistantForm");
const assistantInput = document.getElementById("assistantInput");
const assistantResult = document.getElementById("assistantResult");

const refreshBtn = document.getElementById("refreshHistory");

const explainModal = document.getElementById("explainModal");
const closeExplainModal = document.getElementById("closeExplainModal");
const modalTitle = document.getElementById("modalTitle");
const modalContent = document.getElementById("modalContent");

// ---------- helpers ----------

function money(value) {
  return Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function timestamp(value) {
  const d = new Date(value);
  return d.toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function setButtonLoading(form, isLoading, loadingText) {
  const btn = form.querySelector("button[type=submit]");
  if (!btn) return;
  if (isLoading) {
    btn.dataset.originalText = btn.innerHTML;
    btn.innerHTML = `<span>${loadingText}</span>`;
    btn.disabled = true;
  } else {
    btn.innerHTML = btn.dataset.originalText || btn.innerHTML;
    btn.disabled = false;
  }
}

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    let msg = `Request failed (${response.status})`;
    if (body && body.detail) {
      msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    }
    throw new Error(msg);
  }
  return response.json();
}

function renderMarkdown(text) {
  if (!text) return "";
  let html = text
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^#### (.*$)/gim, '<h4>$1</h4>')
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    .replace(/^\*\* (.*$)/gim, '<h2>$1</h2>')
    .replace(/^\> (.*$)/gim, '<blockquote>$1</blockquote>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
    .replace(/^\- (.*$)/gim, '<li>$1</li>')
    .replace(/\n\n/g, '<br/><br/>');

  html = html.replace(/(<li>.*<\/li>)/gms, '<ul>$1</ul>');
  return html;
}

// ---------- health check ----------

async function checkHealth() {
  const dot = document.getElementById("apiDot");
  const text = document.getElementById("apiStatusText");
  try {
    await apiRequest("/api/health");
    dot.className = "dot online";
    text.textContent = "Connected to desk API";
  } catch (err) {
    dot.className = "dot offline";
    text.textContent = "API unreachable — is uvicorn running?";
  }
}

// ---------- invoice risk ----------

invoiceForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const formData = new FormData(invoiceForm);
  const payload = {
    invoice_quantity: Number(formData.get("invoice_quantity")),
    invoice_dollars: Number(formData.get("invoice_dollars")),
    Freight: Number(formData.get("Freight")),
    total_item_quantity: Number(formData.get("total_item_quantity")),
    total_item_dollars: Number(formData.get("total_item_dollars")),
  };

  setButtonLoading(invoiceForm, true, "Stamping…");
  invoiceResult.innerHTML = "";

  try {
    const result = await apiRequest("/api/invoice/predict", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    const isFlagged = result.predicted_flag === 1;
    invoiceResult.innerHTML = `
      <div class="stamp-wrap">
        <div class="stamp ${isFlagged ? "flagged" : "cleared"}">
          ${isFlagged ? "Flagged" : "Cleared"}
          <small>confidence ${(result.risk_probability * 100).toFixed(1)}% &middot; entry #${result.id}</small>
        </div>
        <button type="button" class="btn btn--ghost btn--sm explain-btn" onclick="explainInvoice(${result.id})">
          Why Flagged? (Audit RAG)
        </button>
      </div>
    `;
    loadInvoiceHistory();
  } catch (err) {
    invoiceResult.innerHTML = `<p class="error-note">Could not score this invoice: ${err.message}</p>`;
  } finally {
    setButtonLoading(invoiceForm, false);
  }
});

// ---------- freight cost ----------

freightForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const formData = new FormData(freightForm);
  const payload = { Dollars: Number(formData.get("Dollars")) };

  setButtonLoading(freightForm, true, "Estimating…");
  freightResult.innerHTML = "";

  try {
    const result = await apiRequest("/api/freight/predict", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    freightResult.innerHTML = `
      <div class="freight-readout">
        <span class="figure">$${money(result.predicted_freight)}</span>
        <span class="label">projected freight &middot; entry #${result.id}</span>
      </div>
    `;
    loadFreightHistory();
  } catch (err) {
    freightResult.innerHTML = `<p class="error-note">Could not estimate freight: ${err.message}</p>`;
  } finally {
    setButtonLoading(freightForm, false);
  }
});

// ---------- vendor ai assistant (MANIFEST 03) ----------

assistantForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = assistantInput.value.trim();
  if (!msg) return;

  setButtonLoading(assistantForm, true, "Thinking…");
  assistantResult.innerHTML = "";

  try {
    const data = await apiRequest("/api/rag/ask", {
      method: "POST",
      body: JSON.stringify({ message: msg }),
    });

    assistantResult.innerHTML = `
      <div class="assistant-response">
        <div class="assistant-head">🤖 Vendor AI Assistant Response</div>
        <div class="assistant-body">${renderMarkdown(data.reply)}</div>
      </div>
    `;
  } catch (err) {
    assistantResult.innerHTML = `<p class="error-note">Assistant error: ${err.message}</p>`;
  } finally {
    setButtonLoading(assistantForm, false);
  }
});

document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    assistantInput.value = chip.dataset.prompt;
    assistantInput.focus();
  });
});

// ---------- audit explanation RAG modal ----------

async function explainInvoice(invoiceId) {
  modalTitle.textContent = `Invoice Audit Explanation #${invoiceId}`;
  modalContent.innerHTML = `<p class="loading-text">Fetching RAG audit report for entry #${invoiceId}…</p>`;
  explainModal.hidden = false;

  try {
    const data = await apiRequest(`/api/invoice/${invoiceId}/explain`);
    modalContent.innerHTML = `
      <div class="modal-report">
        ${data.used_fallback ? `<div class="fallback-banner">ℹ️ Standard Audit Fallback (Set GEMINI_API_KEY for AI Narrative)</div>` : ''}
        <div class="report-text">${renderMarkdown(data.explanation_markdown)}</div>
      </div>
    `;
  } catch (err) {
    modalContent.innerHTML = `<p class="error-note">Failed to load audit explanation: ${err.message}</p>`;
  }
}

closeExplainModal.addEventListener("click", () => {
  explainModal.hidden = true;
});

explainModal.addEventListener("click", (e) => {
  if (e.target === explainModal) explainModal.hidden = true;
});

window.addEventListener("keydown", (e) => {
  if (e.key === "Escape") explainModal.hidden = true;
});

// ---------- history tables ----------

async function loadInvoiceHistory() {
  const tbody = document.querySelector("#invoiceHistoryTable tbody");
  const empty = document.getElementById("invoiceHistoryEmpty");
  try {
    const rows = await apiRequest("/api/invoice/history?limit=20");
    tbody.innerHTML = rows.map((r) => `
      <tr>
        <td>${r.id}</td>
        <td>$${money(r.invoice_dollars)}</td>
        <td>$${money(r.freight)}</td>
        <td><span class="verdict-tag ${r.risk_label === "FLAGGED" ? "flagged" : "cleared"}">${r.risk_label}</span></td>
        <td>${(r.risk_probability * 100).toFixed(1)}%</td>
        <td>
          <button type="button" class="btn-link" onclick="explainInvoice(${r.id})">Why Flagged?</button>
        </td>
        <td>${timestamp(r.created_at)}</td>
      </tr>
    `).join("");
    empty.style.display = rows.length ? "none" : "block";
  } catch (err) {
    empty.textContent = `Could not load history: ${err.message}`;
    empty.style.display = "block";
  }
}

async function loadFreightHistory() {
  const tbody = document.querySelector("#freightHistoryTable tbody");
  const empty = document.getElementById("freightHistoryEmpty");
  try {
    const rows = await apiRequest("/api/freight/history?limit=20");
    tbody.innerHTML = rows.map((r) => `
      <tr>
        <td>${r.id}</td>
        <td>$${money(r.dollars)}</td>
        <td>$${money(r.predicted_freight)}</td>
        <td>${timestamp(r.created_at)}</td>
      </tr>
    `).join("");
    empty.style.display = rows.length ? "none" : "block";
  } catch (err) {
    empty.textContent = `Could not load history: ${err.message}`;
    empty.style.display = "block";
  }
}

refreshBtn.addEventListener("click", () => {
  loadInvoiceHistory();
  loadFreightHistory();
});

// ---------- init ----------

checkHealth();
loadInvoiceHistory();
loadFreightHistory();
