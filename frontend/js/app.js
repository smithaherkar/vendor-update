// ---------------------------------------------------------
// Vendor Intelligence — Multi-Page SPA Logic
// ---------------------------------------------------------

const API_BASE_URL = window.location.port === "8000" ? "" : "http://localhost:8000";

// --- DOM Elements ---
const navLinks = document.querySelectorAll(".nav-link");
const pageViews = document.querySelectorAll(".page-view");

const invoiceForm = document.getElementById("invoiceForm");
const invoiceResult = document.getElementById("invoiceResult");

const freightForm = document.getElementById("freightForm");
const freightResult = document.getElementById("freightResult");

const assistantForm = document.getElementById("assistantForm");
const assistantInput = document.getElementById("assistantInput");
const assistantResult = document.getElementById("assistantResult");

const refreshBtn = document.getElementById("refreshHistory");
const historySourceFilter = document.getElementById("historySourceFilter");
const historyFlaggedFilter = document.getElementById("historyFlaggedFilter");
const historyBatchFilter = document.getElementById("historyBatchFilter");
const clearHistoryFilters = document.getElementById("clearHistoryFilters");

const explainModal = document.getElementById("explainModal");
const closeExplainModal = document.getElementById("closeExplainModal");
const modalTitle = document.getElementById("modalTitle");
const modalContent = document.getElementById("modalContent");

const batchErrorsModal = document.getElementById("batchErrorsModal");
const closeBatchErrorsModal = document.getElementById("closeBatchErrorsModal");
const batchErrorsModalTitle = document.getElementById("batchErrorsModalTitle");

// ---------- Helpers ----------

function money(value) {
  if (value === null || value === undefined) return "0.00";
  return Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function timestamp(value) {
  if (!value) return "—";
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
    headers: options.body instanceof FormData ? {} : { "Content-Type": "application/json" },
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

// ---------- Client-side Router ----------

function handleRoute() {
  const hash = window.location.hash || "#dashboard";
  const targetId = `view-${hash.replace("#", "")}`;

  let matched = false;
  pageViews.forEach((view) => {
    if (view.id === targetId) {
      view.classList.add("active");
      matched = true;
    } else {
      view.classList.remove("active");
    }
  });

  if (!matched && pageViews.length > 0) {
    document.getElementById("view-dashboard").classList.add("active");
  }

  navLinks.forEach((link) => {
    if (link.getAttribute("href") === hash) {
      link.classList.add("active");
    } else {
      link.classList.remove("active");
    }
  });

  // Reload relevant view data on navigation
  if (hash === "#dashboard") loadDashboardMetrics();
  if (hash === "#history") loadUnifiedHistory();
  if (hash === "#batches") loadBatchesRegistry();
}

window.addEventListener("hashchange", handleRoute);

// ---------- Health Check ----------

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

// ---------- Dashboard Metrics ----------

async function loadDashboardMetrics() {
  try {
    const [invoices, freight, batches] = await Promise.all([
      apiRequest("/api/invoice/history?limit=1000"),
      apiRequest("/api/freight/history?limit=1000"),
      apiRequest("/api/batches?limit=1000"),
    ]);

    document.getElementById("dashTotalInvoices").textContent = invoices.length;
    const flagged = invoices.filter(i => i.predicted_flag === 1).length;
    const flaggedPct = invoices.length ? ((flagged / invoices.length) * 100).toFixed(1) : 0;
    document.getElementById("dashFlaggedRate").textContent = `${flaggedPct}% Flagged`;

    document.getElementById("dashTotalFreight").textContent = freight.length;
    document.getElementById("dashTotalBatches").textContent = batches.length;
    const doneBatches = batches.filter(b => b.status === "DONE").length;
    document.getElementById("dashCompletedBatches").textContent = `${doneBatches} Completed`;
  } catch (err) {
    console.warn("Could not load metrics:", err);
  }
}

// ---------- Manual Invoice Form ----------

invoiceForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const formData = new FormData(invoiceForm);
  const payload = {
    vendor_number: formData.get("vendor_number") || null,
    po_number: formData.get("po_number") || null,
    invoice_date: formData.get("invoice_date") || null,
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
    loadDashboardMetrics();
  } catch (err) {
    invoiceResult.innerHTML = `<p class="error-note">Could not score this invoice: ${err.message}</p>`;
  } finally {
    setButtonLoading(invoiceForm, false);
  }
});

// ---------- Manual Freight Form ----------

freightForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const formData = new FormData(freightForm);
  const payload = {
    vendor_number: formData.get("vendor_number") || null,
    po_number: formData.get("po_number") || null,
    invoice_date: formData.get("invoice_date") || null,
    Dollars: Number(formData.get("Dollars")),
  };

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
    loadDashboardMetrics();
  } catch (err) {
    freightResult.innerHTML = `<p class="error-note">Could not estimate freight: ${err.message}</p>`;
  } finally {
    setButtonLoading(freightForm, false);
  }
});

// ---------- Batch Ingestion Logic & Dropzones ----------

function setupDropzone(dropzoneId, fileInputId, uploadEndpoint, progressWrapId, resultSlotId, isFreight = false) {
  const dropzone = document.getElementById(dropzoneId);
  const fileInput = document.getElementById(fileInputId);
  const progressWrap = document.getElementById(progressWrapId);
  const resultSlot = document.getElementById(resultSlotId);

  dropzone.addEventListener("click", () => fileInput.click());

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });

  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length) {
      handleBatchUpload(e.dataTransfer.files[0], uploadEndpoint, progressWrap, resultSlot, isFreight);
    }
  });

  fileInput.addEventListener("change", () => {
    if (fileInput.files.length) {
      handleBatchUpload(fileInput.files[0], uploadEndpoint, progressWrap, resultSlot, isFreight);
    }
  });
}

async function handleBatchUpload(file, endpoint, progressWrap, resultSlot, isFreight) {
  if (!file.name.toLowerCase().endswith?.(".csv") && !file.name.toLowerCase().endsWith(".csv")) {
    resultSlot.innerHTML = `<p class="error-note">Please select a valid .csv file.</p>`;
    return;
  }

  const formData = new FormData();
  formData.append("file", file);

  progressWrap.hidden = false;
  const statusText = progressWrap.querySelector("span:first-child");
  const uuidText = progressWrap.querySelector("span:last-child");
  const barFill = progressWrap.querySelector(".progress-bar-fill");

  statusText.textContent = `Uploading ${file.name}…`;
  uuidText.textContent = "";
  barFill.style.width = "25%";
  resultSlot.innerHTML = "";

  try {
    const res = await apiRequest(endpoint, {
      method: "POST",
      body: formData,
    });

    uuidText.textContent = `UUID: ${res.batch_uuid}`;

    if (res.is_async) {
      statusText.textContent = "Processing batch asynchronously in background…";
      barFill.style.width = "60%";
      pollBatchStatus(res.batch_uuid, endpoint.includes("invoice") ? "/api/invoice/batch-status" : "/api/freight/batch-status", progressWrap, resultSlot);
    } else {
      barFill.style.width = "100%";
      statusText.textContent = "Batch complete!";
      renderBatchSummary(res, resultSlot);
      loadDashboardMetrics();
    }
  } catch (err) {
    progressWrap.hidden = true;
    resultSlot.innerHTML = `<p class="error-note">Upload failed: ${err.message}</p>`;
  }
}

async function pollBatchStatus(batchUuid, statusEndpoint, progressWrap, resultSlot) {
  const barFill = progressWrap.querySelector(".progress-bar-fill");
  const statusText = progressWrap.querySelector("span:first-child");

  const interval = setInterval(async () => {
    try {
      const b = await apiRequest(`${statusEndpoint}/${batchUuid}`);
      if (b.status === "DONE" || b.status.startsWith("FAILED")) {
        clearInterval(interval);
        barFill.style.width = "100%";
        statusText.textContent = `Batch status: ${b.status}`;
        renderBatchSummary(b, resultSlot);
        loadDashboardMetrics();
      } else {
        const pct = b.row_count > 0 ? Math.min(90, Math.floor(((b.success_count + b.duplicate_count + b.error_count) / b.row_count) * 100)) : 50;
        barFill.style.width = `${pct}%`;
        statusText.textContent = `Processing rows (${b.success_count + b.duplicate_count + b.error_count} / ${b.row_count})…`;
      }
    } catch (err) {
      clearInterval(interval);
      resultSlot.innerHTML = `<p class="error-note">Status polling error: ${err.message}</p>`;
    }
  }, 2000);
}

function renderBatchSummary(batch, resultSlot) {
  const hasErrors = batch.error_count > 0;
  resultSlot.innerHTML = `
    <div class="assistant-response" style="border-left-color: ${hasErrors ? 'var(--brick)' : 'var(--forest)'};">
      <div class="assistant-head">📋 Batch Execution Summary (${batch.status})</div>
      <div class="assistant-body">
        <p>File: <strong>${batch.filename}</strong> &middot; UUID: <code>${batch.batch_uuid}</code></p>
        <ul>
          <li>Total Rows Processed: <strong>${batch.row_count}</strong></li>
          <li>Successful Predictions: <strong style="color: var(--forest);">${batch.success_count}</strong></li>
          <li>Duplicate Rows Skipped: <strong style="color: var(--rust);">${batch.duplicate_count}</strong></li>
          <li>Validation Error Rows: <strong style="color: var(--brick);">${batch.error_count}</strong></li>
        </ul>
        <div style="display:flex; gap:12px; margin-top:14px; flex-wrap:wrap;">
          <a href="#history" onclick="filterHistoryByBatch('${batch.batch_uuid}')" class="btn btn--ghost btn--sm">View Records in History</a>
          ${hasErrors ? `<button type="button" onclick="viewBatchErrors('${batch.batch_uuid}')" class="btn btn--ghost btn--sm" style="color:var(--brick); border-color:var(--brick);">View Row Error Details (${batch.error_count})</button>` : ''}
        </div>
      </div>
    </div>
  `;
}

setupDropzone("invoiceDropzone", "invoiceFileInput", "/api/invoice/batch-upload", "invoiceBatchProgress", "invoiceBatchResult");
setupDropzone("freightDropzone", "freightFileInput", "/api/freight/batch-upload", "freightBatchProgress", "freightBatchResult", true);

// ---------- History Ledger & Filters ----------

async function loadUnifiedHistory() {
  const source = historySourceFilter.value;
  const flaggedOnly = historyFlaggedFilter.checked;
  const batchUuid = historyBatchFilter.value.trim();

  let invoiceParams = new URLSearchParams({ limit: 50 });
  let freightParams = new URLSearchParams({ limit: 50 });

  if (source) {
    invoiceParams.append("source", source);
    freightParams.append("source", source);
  }
  if (flaggedOnly) invoiceParams.append("flagged_only", "true");
  if (batchUuid) {
    invoiceParams.append("batch_uuid", batchUuid);
    freightParams.append("batch_uuid", batchUuid);
  }

  const tbodyInv = document.querySelector("#invoiceHistoryTable tbody");
  const emptyInv = document.getElementById("invoiceHistoryEmpty");

  const tbodyFrt = document.querySelector("#freightHistoryTable tbody");
  const emptyFrt = document.getElementById("freightHistoryEmpty");

  try {
    const [invRows, frtRows] = await Promise.all([
      apiRequest(`/api/invoice/history?${invoiceParams}`),
      apiRequest(`/api/freight/history?${freightParams}`),
    ]);

    tbodyInv.innerHTML = invRows.map((r) => `
      <tr>
        <td>${r.id}</td>
        <td>${r.vendor_number || "—"} / ${r.po_number || "—"}<br/><small style="color:var(--muted-text);">${r.invoice_date || ""}</small></td>
        <td>$${money(r.invoice_dollars)}</td>
        <td>$${money(r.freight)}</td>
        <td>
          <span class="source-badge ${r.source.toLowerCase()}">${r.source}</span>
          ${r.batch_uuid ? `<br/><a href="#batches" class="batch-chip" onclick="filterHistoryByBatch('${r.batch_uuid}')">b/${r.batch_uuid.slice(0, 6)}</a>` : ''}
        </td>
        <td><span class="verdict-tag ${r.risk_label === "FLAGGED" ? "flagged" : "cleared"}">${r.risk_label}</span></td>
        <td>${(r.risk_probability * 100).toFixed(1)}%</td>
        <td><button type="button" class="btn-link" onclick="explainInvoice(${r.id})">Why Flagged?</button></td>
        <td>${timestamp(r.created_at)}</td>
      </tr>
    `).join("");
    emptyInv.style.display = invRows.length ? "none" : "block";

    tbodyFrt.innerHTML = frtRows.map((r) => `
      <tr>
        <td>${r.id}</td>
        <td>${r.vendor_number || "—"} / ${r.po_number || "—"}<br/><small style="color:var(--muted-text);">${r.invoice_date || ""}</small></td>
        <td>$${money(r.dollars)}</td>
        <td>$${money(r.predicted_freight)}</td>
        <td>
          <span class="source-badge ${r.source.toLowerCase()}">${r.source}</span>
          ${r.batch_uuid ? `<br/><a href="#batches" class="batch-chip" onclick="filterHistoryByBatch('${r.batch_uuid}')">b/${r.batch_uuid.slice(0, 6)}</a>` : ''}
        </td>
        <td>${timestamp(r.created_at)}</td>
      </tr>
    `).join("");
    emptyFrt.style.display = frtRows.length ? "none" : "block";

  } catch (err) {
    emptyInv.textContent = `Error loading history: ${err.message}`;
    emptyInv.style.display = "block";
  }
}

historySourceFilter.addEventListener("change", loadUnifiedHistory);
historyFlaggedFilter.addEventListener("change", loadUnifiedHistory);
historyBatchFilter.addEventListener("input", loadUnifiedHistory);

clearHistoryFilters.addEventListener("click", () => {
  historySourceFilter.value = "";
  historyFlaggedFilter.checked = false;
  historyBatchFilter.value = "";
  loadUnifiedHistory();
});

refreshBtn.addEventListener("click", loadUnifiedHistory);

function filterHistoryByBatch(batchUuid) {
  window.location.hash = "#history";
  historyBatchFilter.value = batchUuid;
  loadUnifiedHistory();
}

// ---------- Upload Batches Registry ----------

async function loadBatchesRegistry() {
  const tbody = document.querySelector("#batchesTable tbody");
  const empty = document.getElementById("batchesEmpty");

  try {
    const batches = await apiRequest("/api/batches?limit=100");
    tbody.innerHTML = batches.map((b) => `
      <tr>
        <td>
          <code>${b.batch_uuid.slice(0, 8)}…</code><br/>
          <span class="source-badge batch">${b.batch_type}</span>
        </td>
        <td>${b.filename}</td>
        <td>${b.row_count}</td>
        <td style="color:var(--forest); font-weight:600;">${b.success_count}</td>
        <td style="color:var(--rust); font-weight:600;">${b.duplicate_count}</td>
        <td style="color:${b.error_count ? 'var(--brick)' : 'inherit'}; font-weight:${b.error_count ? '700' : 'normal'};">${b.error_count}</td>
        <td><span class="status-tag ${b.status.toLowerCase()}">${b.status}</span></td>
        <td>${timestamp(b.uploaded_at)}</td>
        <td>
          <button type="button" class="btn-link" onclick="filterHistoryByBatch('${b.batch_uuid}')">History</button>
          ${b.error_count > 0 ? `<button type="button" class="btn-link" style="color:var(--brick);" onclick="viewBatchErrors('${b.batch_uuid}')">Errors</button>` : ''}
        </td>
      </tr>
    `).join("");
    empty.style.display = batches.length ? "none" : "block";
  } catch (err) {
    empty.textContent = `Error loading batches: ${err.message}`;
    empty.style.display = "block";
  }
}

async function viewBatchErrors(batchUuid) {
  batchErrorsModalTitle.textContent = `Row Errors for Batch ${batchUuid.slice(0, 8)}`;
  const tbody = document.querySelector("#batchErrorsTable tbody");
  const empty = document.getElementById("batchErrorsEmpty");

  tbody.innerHTML = "<tr><td colspan='3'>Loading errors…</td></tr>";
  empty.style.display = "none";
  batchErrorsModal.hidden = false;

  try {
    const errors = await apiRequest(`/api/batches/${batchUuid}/errors`);
    if (errors.length === 0) {
      tbody.innerHTML = "";
      empty.style.display = "block";

    } else {
      tbody.innerHTML = errors.map((err) => `
        <tr>
          <td>Row #${err.row_number}</td>
          <td style="color:var(--brick); font-weight:500;">${err.error_message}</td>
          <td><code>${err.raw_row_json || "—"}</code></td>
        </tr>
      `).join("");
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan='3' class="error-note">Failed to load errors: ${err.message}</td></tr>`;
  }
}

closeBatchErrorsModal.addEventListener("click", () => batchErrorsModal.hidden = true);
batchErrorsModal.addEventListener("click", (e) => { if (e.target === batchErrorsModal) batchErrorsModal.hidden = true; });

// ---------- Audit Explanation Modal ----------

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

closeExplainModal.addEventListener("click", () => explainModal.hidden = true);
explainModal.addEventListener("click", (e) => { if (e.target === explainModal) explainModal.hidden = true; });

window.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    explainModal.hidden = true;
    batchErrorsModal.hidden = true;
  }
});

// ---------- Vendor AI Assistant ----------

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

// ---------- Init ----------

checkHealth();
handleRoute();
