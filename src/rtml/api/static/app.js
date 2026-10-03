const state = {
  apiKey: "",
  modelInfo: null,
  history: [],
  localScores: 0,
  localFlags: 0,
  toastTimer: null,
};

const byId = (id) => document.getElementById(id);
const scoreForm = byId("score-form");
const apiKeyInput = byId("api-key");
const toast = byId("toast");

function apiHeaders(json = false) {
  const headers = {};
  if (state.apiKey) headers["X-API-Key"] = state.apiKey;
  if (json) headers["Content-Type"] = "application/json";
  return headers;
}

async function requestJson(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { ...apiHeaders(Boolean(options.body)), ...(options.headers || {}) },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(body.detail)
      ? body.detail.map((item) => item.msg).join("; ")
      : body.detail || `Request failed (${response.status})`;
    throw new Error(detail);
  }
  return body;
}

function setApiStatus(status, label) {
  const dot = byId("api-status-dot");
  dot.classList.toggle("connected", status === "connected");
  dot.classList.toggle("error", status === "error");
  byId("api-status-label").textContent = label;
}

function showToast(message, isError = false) {
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.add("show");
  window.clearTimeout(state.toastTimer);
  state.toastTimer = window.setTimeout(() => toast.classList.remove("show"), 3200);
}

function metricSum(text, metricName) {
  const escapedName = metricName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const expression = new RegExp(`^${escapedName}(?:\\{[^}]*\\})?\\s+([0-9.eE+-]+)$`, "gm");
  let total = 0;
  for (const match of text.matchAll(expression)) total += Number(match[1]);
  return total;
}

async function loadMetrics() {
  if (!state.apiKey) return;
  const response = await fetch("/metrics", { headers: apiHeaders() });
  const text = await response.text();
  if (!response.ok) throw new Error(`Metrics request failed (${response.status})`);
  const requests = metricSum(text, "rtml_requests_total");
  if (requests > 0) byId("metric-requests").textContent = Math.round(requests).toLocaleString();
  byId("metrics-output").textContent = text.split("\n").filter(Boolean).slice(0, 80).join("\n");
}

async function refreshStatus() {
  const healthPromise = fetch("/health").then((response) => response.json());
  const readyPromise = fetch("/ready").then(async (response) => ({
    ok: response.ok,
    body: await response.json().catch(() => ({})),
  }));
  try {
    const [health, ready] = await Promise.all([healthPromise, readyPromise]);
    byId("health-state").textContent = health.status === "ok" ? "Operational" : "Unavailable";
    byId("ready-state").textContent = ready.ok ? "Configured" : "Needs API key";
    if (!ready.ok) byId("ready-state").classList.add("bad");
    else byId("ready-state").classList.remove("bad");
    setApiStatus(health.status === "ok" ? "connected" : "error", health.status === "ok" ? "API online" : "API unavailable");
  } catch {
    byId("health-state").textContent = "Unreachable";
    byId("ready-state").textContent = "Unreachable";
    setApiStatus("error", "API unreachable");
  }

  if (!state.apiKey) {
    byId("key-state").textContent = "Not connected";
    return;
  }
  try {
    const model = await requestJson("/model/info");
    state.modelInfo = model;
    byId("model-state").textContent = model.model_version;
    byId("model-version-heading").textContent = model.model_version.toUpperCase();
    byId("key-state").textContent = "Authenticated";
    byId("connection-message").textContent = `Connected to ${model.model_name} · ${model.model_version}`;
    await loadMetrics();
  } catch (error) {
    byId("key-state").textContent = "Rejected";
    byId("model-state").textContent = "Unavailable";
    byId("model-state").classList.add("bad");
    byId("connection-message").textContent = error.message;
    setApiStatus("error", "Check API key");
  }
}

function buildPayload(values, customerId) {
  const average = values.get("average_transaction_amount");
  const age = values.get("customer_age");
  return {
    transaction_id: crypto.randomUUID(),
    timestamp: new Date().toISOString(),
    customer_id: customerId || String(values.get("customer_id") || "customer-demo"),
    amount: Number(values.get("amount")),
    merchant_category: String(values.get("merchant_category")),
    transaction_type: String(values.get("transaction_type")),
    payment_method: String(values.get("payment_method") || "card"),
    customer_age: age ? Number(age) : null,
    account_age_days: Number(values.get("account_age_days") || 0),
    transaction_count_24h: Number(values.get("transaction_count_24h") || 0),
    average_transaction_amount: average === "" ? null : Number(average),
    location: "US-NY",
    device_type: String(values.get("device_type") || "mobile"),
    previous_failed_transactions: Number(values.get("previous_failed_transactions") || 0),
  };
}

function addToHistory(result, amount) {
  state.localScores += 1;
  if (result.prediction === 1) state.localFlags += 1;
  state.history.unshift({ result, amount: Number(amount), at: new Date() });
  state.history = state.history.slice(0, 8);
  byId("metric-local-scores").textContent = state.localScores.toLocaleString();
  byId("metric-flagged").textContent = state.localFlags.toLocaleString();
  renderHistory();
}

function showResult(result) {
  byId("empty-result").hidden = true;
  byId("score-result").hidden = false;
  const flagged = result.prediction === 1;
  byId("result-title").textContent = flagged ? "FLAGGED" : "NORMAL";
  byId("result-title").style.color = flagged ? "#b94f37" : "#587d25";
  byId("decision-tag").textContent = String(result.prediction);
  byId("decision-tag").classList.toggle("flagged", flagged);
  byId("result-risk").textContent = Number(result.risk_score).toFixed(4);
  byId("result-threshold").textContent = `Threshold ${Number(result.threshold).toFixed(4)}`;
  byId("risk-track-fill").style.width = `${Math.max(0, Math.min(100, Number(result.risk_score) * 100))}%`;
  byId("threshold-marker").style.left = `${Math.max(0, Math.min(100, Number(result.threshold) * 100))}%`;
  byId("result-model").textContent = result.model_version;
  byId("result-route").textContent = result.routing_arm;
  byId("result-request").textContent = result.request_id;
  byId("result-latency").textContent = `${result.latency_ms} ms (reported)`;
}

function renderHistory() {
  const body = byId("history-body");
  if (!state.history.length) {
    body.innerHTML = '<tr class="empty-row"><td colspan="5">No assessments in this browser session.</td></tr>';
    return;
  }
  body.replaceChildren(...state.history.map(({ result, amount, at }) => {
    const row = document.createElement("tr");
    const values = [
      `${result.transaction_id.slice(0, 8)}...${result.transaction_id.slice(-4)}`,
      at.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
      `$${amount.toFixed(2)}`,
      Number(result.risk_score).toFixed(4),
    ];
    for (const value of values) {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    }
    const decisionCell = document.createElement("td");
    const pill = document.createElement("span");
    pill.className = `decision-pill${result.prediction === 1 ? " flagged" : ""}`;
    pill.textContent = result.prediction === 1 ? "Flagged" : "Normal";
    decisionCell.append(pill);
    row.append(decisionCell);
    return row;
  }));
}

function showError(elementId, message) {
  const element = byId(elementId);
  element.textContent = message;
  element.hidden = false;
}

function clearError(elementId) {
  const element = byId(elementId);
  element.textContent = "";
  element.hidden = true;
}

function activateView(viewId, navButton) {
  document.querySelectorAll(".view").forEach((view) => {
    const active = view.id === viewId;
    view.classList.toggle("active", active);
    view.hidden = !active;
  });
  document.querySelectorAll(".nav-item").forEach((button) => {
    const active = button === navButton;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  byId("breadcrumb-current").textContent = navButton.textContent.trim().replace(/^\d+/, "").trim().toUpperCase();
  if (viewId === "activity-view") loadMetrics().catch((error) => {
    byId("metrics-output").textContent = error.message;
  });
}

byId("connect-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const key = apiKeyInput.value.trim();
  if (key.length < 32) {
    state.apiKey = "";
    showToast("API key must be at least 32 characters.", true);
    return;
  }
  state.apiKey = key;
  byId("key-state").textContent = "Checking";
  await refreshStatus();
  if (byId("key-state").textContent === "Authenticated") showToast("Connected. The key stays in this tab's memory.");
});

scoreForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError("score-error");
  if (!state.apiKey) {
    showError("score-error", "Connect with the API key above before scoring.");
    return;
  }
  if (!scoreForm.reportValidity()) return;
  const submitButton = byId("score-button");
  submitButton.disabled = true;
  submitButton.querySelector("span").textContent = "Scoring...";
  try {
    const values = new FormData(scoreForm);
    const payload = buildPayload(values);
    const result = await requestJson("/predict", { method: "POST", body: JSON.stringify(payload) });
    showResult(result);
    addToHistory(result, payload.amount);
    loadMetrics().catch(() => {});
    showToast(result.prediction === 1 ? "Transaction returned as flagged." : "Transaction returned as normal.");
  } catch (error) {
    showError("score-error", error.message);
  } finally {
    submitButton.disabled = false;
    submitButton.querySelector("span").textContent = "Run assessment";
  }
});

byId("load-batch-example").addEventListener("click", () => {
  const values = new FormData(scoreForm);
  const first = buildPayload(values, "customer-batch-01");
  const second = buildPayload(values, "customer-batch-02");
  second.amount = Number((second.amount * 4.7).toFixed(2));
  second.transaction_count_24h = 0;
  byId("batch-json").value = JSON.stringify([first, second], null, 2);
});

byId("batch-button").addEventListener("click", async () => {
  clearError("batch-error");
  if (!state.apiKey) {
    showError("batch-error", "Connect with the API key above before scoring.");
    return;
  }
  let payloads;
  try {
    payloads = JSON.parse(byId("batch-json").value);
    if (!Array.isArray(payloads) || payloads.length < 1 || payloads.length > 100) {
      throw new Error("Provide an array containing between 1 and 100 transactions.");
    }
  } catch (error) {
    showError("batch-error", error.message);
    return;
  }
  const button = byId("batch-button");
  button.disabled = true;
  try {
    const response = await requestJson("/predict/batch", { method: "POST", body: JSON.stringify(payloads) });
    byId("batch-output").textContent = JSON.stringify(response, null, 2);
    for (const prediction of response.predictions) {
      const original = payloads.find((payload) => payload.transaction_id === prediction.transaction_id);
      addToHistory(prediction, original?.amount ?? 0);
    }
    loadMetrics().catch(() => {});
    showToast(`${response.predictions.length} transactions scored.`);
  } catch (error) {
    showError("batch-error", error.message);
  } finally {
    button.disabled = false;
  }
});

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => activateView(button.dataset.view, button));
});

byId("refresh-button").addEventListener("click", refreshStatus);
byId("refresh-signals").addEventListener("click", refreshStatus);
byId("clear-history").addEventListener("click", () => {
  state.history = [];
  state.localScores = 0;
  state.localFlags = 0;
  byId("metric-local-scores").textContent = "0";
  byId("metric-flagged").textContent = "0";
  renderHistory();
  showToast("Session history cleared.");
});

refreshStatus();
window.setInterval(refreshStatus, 20000);
