// ---------------------------------------------------------
// Vendor Intelligence — Multi-Page SPA Logic
// ---------------------------------------------------------

const API_BASE_URL = window.location.port === "8000" ? "" : "http://localhost:8000";

// ---- Chart.js instances (kept so we can destroy/re-draw on refresh) ----
let riskDonutInstance = null;
let spendBarInstance   = null;

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

const batchErrorsModal = document.getElementById("batchErrorsModal");
const closeBatchErrorsModal = document.getElementById("closeBatchErrorsModal");
const batchErrorsModalTitle = document.getElementById("batchErrorsModalTitle");

const invoiceExplainModal = document.getElementById("invoiceExplainModal");
const closeInvoiceExplainModal = document.getElementById("closeInvoiceExplainModal");
const invoiceExplainModalTitle = document.getElementById("invoiceExplainModalTitle");
const invoiceExplainModalBody = document.getElementById("invoiceExplainModalBody");

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

function inlineFormat(str) {
  if (!str) return "";
  return str
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.*?)\*/g, "<em>$1</em>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
}

function renderMarkdown(text) {
  if (!text) return "";

  // 1. If marked.js is available via CDN, use it
  if (window.marked && typeof window.marked.parse === "function") {
    try {
      return window.marked.parse(text);
    } catch (e) {
      console.warn("marked.parse failed, falling back to local parser", e);
    }
  }

  // 2. High-reliability line-by-line state-machine parser fallback
  const lines = text.split(/\r?\n/);
  let html = [];
  let inTable = false;
  let tableRows = [];
  let inList = false;

  function flushTable() {
    if (!inTable) return;
    inTable = false;
    if (tableRows.length < 2) {
      tableRows.forEach((r) => html.push(`<p>${inlineFormat(r)}</p>`));
      tableRows = [];
      return;
    }
    const sep = tableRows[1].trim();
    if (/^\|(?:\s*:?-+:?\s*\|)+$/.test(sep)) {
      const headers = tableRows[0].slice(1, -1).split("|").map((c) => c.trim());
      let t = '<div class="table-wrap"><table class="assistant-table"><thead><tr>';
      headers.forEach((h) => {
        t += `<th>${inlineFormat(h)}</th>`;
      });
      t += "</tr></thead><tbody>";
      for (let i = 2; i < tableRows.length; i++) {
        const cells = tableRows[i].slice(1, -1).split("|").map((c) => c.trim());
        t += "<tr>";
        cells.forEach((c) => {
          t += `<td>${inlineFormat(c)}</td>`;
        });
        t += "</tr>";
      }
      t += "</tbody></table></div>";
      html.push(t);
    } else {
      tableRows.forEach((r) => html.push(`<p>${inlineFormat(r)}</p>`));
    }
    tableRows = [];
  }

  function flushList() {
    if (inList) {
      html.push("</ul>");
      inList = false;
    }
  }

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i];
    const trimmed = rawLine.trim();

    // Table rows
    if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
      flushList();
      inTable = true;
      tableRows.push(trimmed);
      continue;
    } else if (inTable) {
      flushTable();
    }

    // Empty lines
    if (!trimmed) {
      flushList();
      continue;
    }

    // Headings
    if (trimmed.startsWith("#### ")) {
      flushList();
      html.push(`<h4>${inlineFormat(trimmed.slice(5))}</h4>`);
      continue;
    }
    if (trimmed.startsWith("### ")) {
      flushList();
      html.push(`<h3>${inlineFormat(trimmed.slice(4))}</h3>`);
      continue;
    }
    if (trimmed.startsWith("## ") || trimmed.startsWith("** ")) {
      flushList();
      html.push(`<h2>${inlineFormat(trimmed.slice(3))}</h2>`);
      continue;
    }
    if (trimmed.startsWith("# ")) {
      flushList();
      html.push(`<h1>${inlineFormat(trimmed.slice(2))}</h1>`);
      continue;
    }

    // Blockquote
    if (trimmed.startsWith("> ")) {
      flushList();
      html.push(`<blockquote>${inlineFormat(trimmed.slice(2))}</blockquote>`);
      continue;
    }

    // List item
    if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      if (!inList) {
        html.push("<ul>");
        inList = true;
      }
      html.push(`<li>${inlineFormat(trimmed.slice(2))}</li>`);
      continue;
    } else if (inList) {
      flushList();
    }

    // Normal paragraph line
    html.push(`<p>${inlineFormat(trimmed)}</p>`);
  }

  flushTable();
  flushList();

  return html.join("");
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
  try {
    await apiRequest("/api/health");
  } catch (err) {
    console.warn("API health check:", err.message);
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
    const cleared = invoices.length - flagged;
    const flaggedPct = invoices.length ? ((flagged / invoices.length) * 100).toFixed(1) : 0;
    document.getElementById("dashFlaggedRate").textContent = `${flaggedPct}% Flagged`;

    document.getElementById("dashTotalFreight").textContent = freight.length;
    document.getElementById("dashTotalBatches").textContent = batches.length;
    const doneBatches = batches.filter(b => b.status === "DONE").length;
    document.getElementById("dashCompletedBatches").textContent = `${doneBatches} Completed`;

    // ── Chart 1: Risk Donut ──────────────────────────────────────────
    const donutCanvas = document.getElementById("riskDonutChart");
    const donutEmpty  = document.getElementById("riskChartEmpty");
    if (invoices.length === 0) {
      donutCanvas.style.display = "none";
      donutEmpty.style.display  = "block";
    } else {
      donutCanvas.style.display = "block";
      donutEmpty.style.display  = "none";
      if (riskDonutInstance) riskDonutInstance.destroy();
      riskDonutInstance = new Chart(donutCanvas, {
        type: "doughnut",
        data: {
          labels: ["Flagged", "Cleared"],
          datasets: [{
            data: [flagged, cleared],
            backgroundColor: ["#A83A32", "#2E6B4F"],
            borderColor: ["#F6F1E6", "#F6F1E6"],
            borderWidth: 3,
            hoverOffset: 6,
          }],
        },
        options: {
          cutout: "68%",
          plugins: {
            legend: {
              position: "bottom",
              labels: { font: { family: "JetBrains Mono", size: 11 }, color: "#1D2C3B", padding: 14 },
            },
            tooltip: {
              callbacks: {
                label: ctx => ` ${ctx.label}: ${ctx.parsed} (${((ctx.parsed / invoices.length) * 100).toFixed(1)}%)`,
              },
            },
          },
        },
      });
    }

    // ── Chart 2: Top-5 Vendors by Spend Bar ─────────────────────────
    const barCanvas = document.getElementById("spendBarChart");
    const barEmpty  = document.getElementById("spendChartEmpty");

    // Aggregate spend from invoice history
    const spendMap = {};
    invoices.forEach(inv => {
      const v = inv.vendor_number || "Unknown";
      spendMap[v] = (spendMap[v] || 0) + (inv.invoice_dollars || 0);
    });
    const sorted = Object.entries(spendMap)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5);

    if (sorted.length === 0) {
      barCanvas.style.display = "none";
      barEmpty.style.display  = "block";
    } else {
      barCanvas.style.display = "block";
      barEmpty.style.display  = "none";
      if (spendBarInstance) spendBarInstance.destroy();
      spendBarInstance = new Chart(barCanvas, {
        type: "bar",
        data: {
          labels: sorted.map(([v]) => v),
          datasets: [{
            label: "Total Spend ($)",
            data: sorted.map(([, s]) => s),
            backgroundColor: [
              "rgba(192,89,44,0.80)",
              "rgba(192,89,44,0.65)",
              "rgba(192,89,44,0.50)",
              "rgba(192,89,44,0.38)",
              "rgba(192,89,44,0.26)",
            ],
            borderColor: "rgba(192,89,44,1)",
            borderWidth: 1,
            borderRadius: 4,
          }],
        },
        options: {
          indexAxis: "y",
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: ctx => ` $${Number(ctx.parsed.x).toLocaleString(undefined, { minimumFractionDigits: 2 })}`,
              },
            },
          },
          scales: {
            x: {
              ticks: { font: { family: "JetBrains Mono", size: 10 }, color: "#5B6B7A",
                callback: v => "$" + Number(v).toLocaleString() },
              grid: { color: "rgba(203,191,166,0.4)" },
            },
            y: { ticks: { font: { family: "JetBrains Mono", size: 11 }, color: "#1D2C3B" }, grid: { display: false } },
          },
        },
      });
    }

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

  setButtonLoading(invoiceForm, true, "Evaluating…");
  invoiceResult.innerHTML = "";

  try {
    const result = await apiRequest("/api/invoice/predict", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    const isFlagged = result.predicted_flag === 1;
    const confidencePct = isFlagged
      ? (result.risk_probability * 100).toFixed(1)
      : ((1 - result.risk_probability) * 100).toFixed(1);

    invoiceResult.innerHTML = `
      <div class="stamp-wrap">
        <div class="stamp ${isFlagged ? "flagged" : "cleared"}">
          ${isFlagged ? "Flagged" : "Cleared"}
          <small>confidence ${confidencePct}% &middot; entry #${result.id}</small>
        </div>
      </div>
      <div id="manualInvoiceShapSlot">
        <div style="text-align:center; padding:12px; color:var(--muted-text); font-family:var(--font-mono); font-size:0.82rem;">
          ⚡ Computing SHAP feature attribution breakdown…
        </div>
      </div>
    `;

    // Fetch SHAP feature attribution immediately
    try {
      const explanation = await apiRequest(`/api/invoice/${result.id}/explain`);
      const shapSlot = document.getElementById("manualInvoiceShapSlot");
      if (shapSlot) {
        shapSlot.innerHTML = renderShapCard(explanation);
      }
    } catch (shapErr) {
      console.warn("Could not load SHAP breakdown:", shapErr);
      const shapSlot = document.getElementById("manualInvoiceShapSlot");
      if (shapSlot) shapSlot.innerHTML = "";
    }

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

    tbodyInv.innerHTML = invRows.map((r) => {
      const isFlagged = r.predicted_flag === 1;
      const conf = isFlagged
        ? (r.risk_probability * 100).toFixed(1)
        : ((1 - r.risk_probability) * 100).toFixed(1);
      return `
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
        <td>${conf}%</td>
        <td>${timestamp(r.created_at)}</td>
        <td>
          <button type="button" class="btn btn--ghost btn--sm" onclick="explainInvoice(${r.id})" title="SHAP Feature Attribution">
            🔍 Explain
          </button>
        </td>
      </tr>
    `}).join("");
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

// ── CSV Export ──────────────────────────────────────────────────────────────

function exportTableAsCSV(tableId, filename) {
  const table = document.getElementById(tableId);
  if (!table) return;
  const rows = Array.from(table.querySelectorAll("tr"));
  const csvLines = rows.map(row => {
    return Array.from(row.querySelectorAll("th, td"))
      .map(cell => {
        // Strip HTML tags, trim whitespace
        const text = cell.innerText.replace(/\n/g, " ").trim();
        // Wrap in quotes if contains comma, quote, or newline
        return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
      })
      .join(",");
  });
  const blob = new Blob([csvLines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url  = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href     = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

document.getElementById("exportInvoiceCSV").addEventListener("click", () => {
  exportTableAsCSV("invoiceHistoryTable", `invoice_history_${Date.now()}.csv`);
});

document.getElementById("exportFreightCSV").addEventListener("click", () => {
  exportTableAsCSV("freightHistoryTable", `freight_history_${Date.now()}.csv`);
});

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

if (closeInvoiceExplainModal) {
  closeInvoiceExplainModal.addEventListener("click", () => invoiceExplainModal.hidden = true);
}
if (invoiceExplainModal) {
  invoiceExplainModal.addEventListener("click", (e) => { if (e.target === invoiceExplainModal) invoiceExplainModal.hidden = true; });
}

window.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    batchErrorsModal.hidden = true;
    if (invoiceExplainModal) invoiceExplainModal.hidden = true;
  }
});

// ── SHAP Explainability Renderer & Modal Handler ─────────────────────────────

function formatFeatureValue(name, val) {
  if (name.includes("dollars") || name.toLowerCase() === "freight") {
    return `$${money(val)}`;
  }
  return Number(val).toLocaleString();
}

function renderShapCard(data) {
  const isFlagged = data.predicted_flag === 1;
  const riskPct = (data.risk_probability * 100).toFixed(1);
  const basePct = (data.base_risk * 100).toFixed(1);
  const riskDelta = ((data.risk_probability - data.base_risk) * 100).toFixed(1);
  const sign = data.risk_probability >= data.base_risk ? "+" : "";

  // Max absolute shap value to scale bars relative to each other
  const maxAbs = Math.max(...data.features.map(f => Math.abs(f.shap_value)), 0.05);

  const featuresHtml = data.features.map(f => {
    const absVal = Math.abs(f.shap_value);
    const barWidthPct = Math.min(100, Math.max(8, Math.round((absVal / maxAbs) * 100)));
    const isRisk = f.shap_value > 0.0001;
    const isSafe = f.shap_value < -0.0001;
    const badgeClass = isRisk ? "risk" : (isSafe ? "safe" : "neutral");
    const deltaText = (f.shap_value >= 0 ? "+" : "") + (f.shap_value * 100).toFixed(1) + "%";
    const dirLabel = isRisk ? "▲ Risk Factor" : (isSafe ? "▼ Mitigating Factor" : "— Neutral");

    return `
      <div class="shap-feature-row">
        <div class="shap-feature-meta">
          <div>
            <span class="shap-feature-name">${f.label || f.display_name || f.feature}</span>
            <span class="shap-feature-raw">(${formatFeatureValue(f.feature || f.feature_name, f.raw_value ?? f.feature_value)})</span>
          </div>
          <span class="shap-delta-badge ${badgeClass}">${deltaText} (${dirLabel})</span>
        </div>
        <div class="shap-bar-track">
          <div class="shap-bar-fill ${isRisk ? 'risk' : 'safe'}" style="width: ${barWidthPct}%;"></div>
        </div>
        <div class="shap-feature-desc">${f.description || (f.impact_pct + "% impact share &middot; " + (f.impact === 'INCREASES_RISK' ? 'Increases anomaly risk' : 'Reduces anomaly risk'))}</div>
      </div>
    `;
  }).join("");

  return `
    <div class="shap-card">
      <div class="shap-header">
        <span class="shap-badge">⚡ TreeExplainer &middot; Exact Feature Risk Attribution</span>
        <span class="shap-verdict-pill ${isFlagged ? 'flagged' : 'cleared'}">
          ${isFlagged ? '🔴 High Risk Anomaly' : '🟢 Cleared Invoice'} &middot; ${riskPct}% Risk
        </span>
      </div>

      <div class="shap-summary-box ${isFlagged ? 'flagged' : 'cleared'}">
        <strong>Diagnostic Summary:</strong> ${data.summary}
      </div>

      <div class="shap-metrics-row">
        <div class="shap-metric-item">
          <span class="lbl">Invoice Total</span>
          <span class="val">$${money(data.invoice_dollars)}</span>
        </div>
        <div class="shap-metric-item">
          <span class="lbl">PO Items Total</span>
          <span class="val">$${money(data.total_item_dollars)}</span>
        </div>
        <div class="shap-metric-item">
          <span class="lbl">Dollar Mismatch</span>
          <span class="val" style="${data.dollar_mismatch > 0 ? 'color:var(--brick);' : ''}">$${money(data.dollar_mismatch)}</span>
        </div>
        <div class="shap-metric-item">
          <span class="lbl">Base Population Risk</span>
          <span class="val">${basePct}%</span>
        </div>
        <div class="shap-metric-item">
          <span class="lbl">Model Risk Score</span>
          <span class="val" style="color:${isFlagged ? 'var(--brick)' : 'var(--forest)'};">${riskPct}% (${sign}${riskDelta}%)</span>
        </div>
      </div>

      <div style="font-family:var(--font-mono); font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:0.8px; color:var(--muted-text); margin-bottom:8px;">
        Feature Risk Contributors (Shapley Values)
      </div>

      <div class="shap-features-wrap">
        ${featuresHtml}
      </div>

      <div class="shap-footnote">
        🧮 <strong>Mathematical Guarantee:</strong> Baseline population risk (${basePct}%) plus sum of all feature SHAP contributions equals exactly the model's output risk (${riskPct}%). Computed in &lt;15ms via TreeExplainer on Random Forest.
      </div>
    </div>
  `;
}

window.explainInvoice = async function(invoiceId) {
  if (!invoiceExplainModal) return;
  invoiceExplainModalTitle.textContent = `Invoice #${invoiceId} · SHAP Risk Audit`;
  invoiceExplainModalBody.innerHTML = `
    <div style="text-align:center; padding:36px; color:var(--muted-text); font-family:var(--font-mono);">
      <div style="font-size:1.8rem; margin-bottom:8px;">⚡</div>
      Calculating exact TreeExplainer Shapley values for Invoice #${invoiceId}…
    </div>
  `;
  invoiceExplainModal.hidden = false;

  try {
    const data = await apiRequest(`/api/invoice/${invoiceId}/explain`);
    invoiceExplainModalBody.innerHTML = renderShapCard(data);
  } catch (err) {
    invoiceExplainModalBody.innerHTML = `<div class="error-note">Failed to retrieve SHAP explanation for Invoice #${invoiceId}: ${err.message}</div>`;
  }
};

// ── AI Assistant Query History (sessionStorage, max 5) ────────────────────

const HISTORY_KEY = "vi_query_history";

function getQueryHistory() {
  try { return JSON.parse(sessionStorage.getItem(HISTORY_KEY) || "[]"); }
  catch { return []; }
}

function saveQueryToHistory(query) {
  let history = getQueryHistory().filter(q => q !== query); // deduplicate
  history.unshift(query);
  history = history.slice(0, 5); // keep last 5
  sessionStorage.setItem(HISTORY_KEY, JSON.stringify(history));
  renderQueryHistory();
}

function renderQueryHistory() {
  const wrap = document.getElementById("queryHistoryWrap");
  const list = document.getElementById("queryHistoryList");
  const history = getQueryHistory();
  if (history.length === 0) { wrap.style.display = "none"; return; }
  wrap.style.display = "block";
  list.innerHTML = history.map(q => `
    <button type="button" class="query-history-item" data-query="${q.replace(/"/g, '&quot;')}">
      <span class="qh-icon">↩</span>
      <span>${q}</span>
    </button>
  `).join("");
  // Wire clicks
  list.querySelectorAll(".query-history-item").forEach(btn => {
    btn.addEventListener("click", () => {
      assistantInput.value = btn.dataset.query;
      assistantInput.focus();
    });
  });
}

// Render on page load
renderQueryHistory();

// ── Vendor AI Assistant ───────────────────────────────────────────────────

assistantForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = assistantInput.value.trim();
  if (!msg) return;

  // Save to query history before sending
  saveQueryToHistory(msg);

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
renderQueryHistory();
