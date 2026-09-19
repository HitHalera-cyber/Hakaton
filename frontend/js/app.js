"use strict";

const API = "/api";
let state = {
  mode: "current",
  config: null,
  lastResponse: null,
  map: null,
  mapLayer: null,
  chart: null,
};

const $ = (sel) => document.querySelector(sel);

function isoUtc(datetimeLocalValue) {
  // datetime-local gives "YYYY-MM-DDTHH:MM" with no timezone; per the task
  // requirement all input/output times are UTC, so we interpret the field
  // as UTC directly rather than converting from the browser's local zone.
  return datetimeLocalValue.length === 16 ? datetimeLocalValue + ":00Z" : datetimeLocalValue + "Z";
}

function fmt(dtIso) {
  if (!dtIso) return "—";
  return dtIso.replace("T", " ").replace(/\.\d+/, "").replace("+00:00", "").replace("Z", "") + " UTC";
}

function confidenceLabel(c) {
  return { high: "высокая", medium: "средняя", low: "низкая", insufficient_data: "недостаточно данных" }[c] || c;
}
function provenanceLabel(p) {
  return { observation: "наблюдение", external_forecast: "внешний прогноз", team_calculation: "расчёт команды" }[p] || p;
}

async function init() {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  $("#reference_time").value = `${now.getUTCFullYear()}-${pad(now.getUTCMonth() + 1)}-${pad(now.getUTCDate())}T${pad(now.getUTCHours())}:${pad(now.getUTCMinutes())}`;

  document.querySelectorAll(".seg-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".seg-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.mode = btn.dataset.mode;
      $("#historical-hint").style.display = state.mode === "historical" ? "block" : "none";
      if (state.mode === "historical") {
        $("#reference_time").value = "2024-05-10T06:00";
      }
    });
  });
  $("#historical-hint").style.display = "none";

  try {
    const cfg = await fetch(`${API}/config`).then((r) => r.json());
    state.config = cfg;
  } catch (e) {
    console.warn("config fetch failed", e);
  }

  await refreshSourceToggles();

  $("#analyze-btn").addEventListener("click", runAnalyze);
  $("#experiment-btn").addEventListener("click", runExperiment);
  $("#export-btn").addEventListener("click", exportResult);
}

async function refreshSourceToggles() {
  let sources = [];
  try {
    sources = await fetch(`${API}/sources/status`).then((r) => r.json());
  } catch (e) {
    return;
  }
  const container = $("#sources-toggle-list");
  container.innerHTML = "";
  sources.forEach((s) => {
    const current = s.is_disabled ? "disabled" : s.is_frozen ? "frozen" : "normal";
    const row = document.createElement("div");
    row.className = "source-toggle-row";
    row.innerHTML = `
      <span>${s.name}</span>
      <select data-name="${s.name}">
        <option value="normal" ${current === "normal" ? "selected" : ""}>обычный режим</option>
        <option value="frozen" ${current === "frozen" ? "selected" : ""}>заморожен (кеш без обновления)</option>
        <option value="disabled" ${current === "disabled" ? "selected" : ""}>отключён (не используется)</option>
      </select>`;
    container.appendChild(row);
  });
  container.querySelectorAll("select").forEach((sel) => {
    sel.addEventListener("change", async () => {
      const name = sel.dataset.name;
      const value = sel.value;
      await fetch(`${API}/sources/toggle`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, disabled: value === "disabled", frozen: value === "frozen" }),
      });
    });
  });
}

function collectDisabledFrozen() {
  const disabled = [];
  const frozen = [];
  document.querySelectorAll("#sources-toggle-list select").forEach((sel) => {
    if (sel.value === "disabled") disabled.push(sel.dataset.name);
    else if (sel.value === "frozen") frozen.push(sel.dataset.name);
  });
  return { disabled, frozen };
}

async function runAnalyze() {
  const refVal = $("#reference_time").value;
  if (!refVal) return showError("Укажите дату и время начала ВКД.");
  const { disabled, frozen } = collectDisabledFrozen();

  const req = {
    mode: state.mode,
    reference_time: isoUtc(refVal),
    duration_hours: parseFloat($("#duration_hours").value),
    search_period_hours: parseFloat($("#search_period_hours").value),
    step_minutes: parseFloat($("#step_minutes").value),
    disabled_sources: disabled,
    frozen_sources: frozen,
  };

  setLoading(true);
  hideError();
  try {
    const res = await fetch(`${API}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    });
    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      throw new Error(errBody.detail || `Ошибка сервера (${res.status})`);
    }
    const data = await res.json();
    state.lastResponse = data;
    render(data);
  } catch (e) {
    showError(e.message || String(e));
  } finally {
    setLoading(false);
    await refreshSourceToggles();
  }
}

function setLoading(v) {
  $("#loading").hidden = !v;
  $("#analyze-btn").disabled = v;
}
function showError(msg) {
  const el = $("#error-banner");
  el.textContent = "Ошибка: " + msg;
  el.hidden = false;
}
function hideError() {
  $("#error-banner").hidden = true;
}

function render(data) {
  $("#results-content").hidden = false;

  // Historical panel
  const hp = $("#historical-panel");
  if (data.historical_info.is_historical) {
    hp.hidden = false;
    $("#historical-note").textContent = data.historical_info.note;
  } else {
    hp.hidden = true;
  }

  // Orbit + map
  const o = data.orbit;
  $("#orbit-meta").textContent =
    `Источник: ${o.source_name} · эпоха ${fmt(o.epoch)} · давность данных ${o.age_hours.toFixed(1)} ч` +
    (o.is_reconstruction ? " · РЕКОНСТРУКЦИЯ (см. пояснение)" : "");
  renderMap(o);

  // Windows table + chart + recommendation
  renderWindows(data);

  // Factors
  renderFactors(data.factors);

  // Sources
  renderSources(data.sources);

  $("#result-id-label").textContent = `ID результата: ${data.result_id} · версия алгоритма ${data.algorithm_version}`;
}

const DAY_COLOR = "#f5c451";
const NIGHT_COLOR = "#3355a8";

function renderMap(orbit) {
  if (!state.map) {
    state.map = L.map("map", { worldCopyJump: true }).setView([0, 0], 2);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap",
      maxZoom: 8,
    }).addTo(state.map);

    const legend = L.control({ position: "bottomright" });
    legend.onAdd = () => {
      const div = L.DomUtil.create("div", "map-legend");
      div.innerHTML = `
        <div><span class="swatch" style="background:${DAY_COLOR}"></span>день (станция освещена)</div>
        <div><span class="swatch" style="background:${NIGHT_COLOR}"></span>ночь (станция в тени Земли)</div>
        <div>🟢 начало периода &nbsp; 🟠 конец периода</div>`;
      return div;
    };
    legend.addTo(state.map);
  }
  if (state.mapLayer) {
    state.map.removeLayer(state.mapLayer);
  }
  const group = L.layerGroup();
  const track = orbit.track;

  if (track.length) {
    // Split the ground track into contiguous day/night runs, and further at
    // antimeridian crossings, so nothing draws a false line across the map.
    let segment = [track[0]];
    const flush = () => {
      if (segment.length > 1) {
        const daylight = segment[0].is_daylight;
        L.polyline(segment.map((p) => [p.lat, p.lon]), {
          color: daylight ? DAY_COLOR : NIGHT_COLOR,
          weight: 3,
          opacity: 0.9,
        }).addTo(group);
      }
      segment = [];
    };
    for (let i = 1; i < track.length; i++) {
      const prev = track[i - 1];
      const cur = track[i];
      const wrapped = Math.abs(cur.lon - prev.lon) > 180;
      const dayChanged = cur.is_daylight !== prev.is_daylight;
      if (wrapped || dayChanged) {
        flush();
        segment = [prev];
      }
      segment.push(cur);
    }
    flush();

    const first = track[0];
    const last = track[track.length - 1];
    L.marker([first.lat, first.lon], {
      icon: L.divIcon({ className: "", html: '<div style="background:#4fd18c;width:14px;height:14px;border-radius:50%;border:2px solid #06210f;"></div>', iconSize: [14, 14] }),
    }).bindTooltip("Начало периода: " + fmt(first.t), { permanent: false }).addTo(group);
    L.marker([last.lat, last.lon], {
      icon: L.divIcon({ className: "", html: '<div style="background:#ff9d47;width:14px;height:14px;border-radius:50%;border:2px solid #3a1900;"></div>', iconSize: [14, 14] }),
    }).bindTooltip("Конец периода: " + fmt(last.t), { permanent: false }).addTo(group);

    const bounds = L.latLngBounds(track.map((p) => [p.lat, p.lon]));
    state.map.fitBounds(bounds.pad(0.25), { maxZoom: 6 });
  }

  group.addTo(state.map);
  state.mapLayer = group;
}

function renderWindows(data) {
  const rec = data.recommendation;
  $("#recommendation-text").textContent = rec.has_recommendation
    ? rec.reason + (rec.caveats.length ? " " + rec.caveats.join(" ") : "")
    : rec.reason;

  const tbody = document.querySelector("#windows-table tbody");
  tbody.innerHTML = "";
  data.windows.forEach((w, i) => {
    const tr = document.createElement("tr");
    if (w.is_recommended) tr.classList.add("recommended");
    else if (w.is_tied_with_recommended) tr.classList.add("tied");
    const badge = w.is_recommended
      ? '<span class="badge rec">Рекомендовано</span>'
      : w.is_tied_with_recommended
      ? '<span class="badge tie">Равнозначно</span>'
      : "";
    tr.innerHTML = `
      <td>#${i + 1}</td>
      <td>${fmt(w.start)}</td>
      <td>${fmt(w.end)}</td>
      <td>${w.combined_score === null ? "н/д" : w.combined_score.toFixed(2)}</td>
      <td><span class="confidence-pill confidence-${w.data_completeness}">${confidenceLabel(w.data_completeness)}</span></td>
      <td>${(w.daylight_fraction * 100).toFixed(0)}%</td>
      <td>${badge}</td>`;
    tbody.appendChild(tr);
  });

  const ctx = document.getElementById("windows-chart");
  const labels = data.windows.map((w, i) => `#${i + 1} ${fmt(w.start).slice(5, 16)}`);
  const factorNames = [...new Set(data.windows.flatMap((w) => w.factor_contributions.map((c) => c.factor)))];
  const colors = { space_weather: "#f5c451", conjunction_mmod: "#ff5c93" };
  const datasets = factorNames.map((f) => ({
    label: f === "space_weather" ? "Космическая погода" : "Сближения/MMOD",
    data: data.windows.map((w) => {
      const c = w.factor_contributions.find((c) => c.factor === f);
      return c ? c.time_weighted_severity : 0;
    }),
    backgroundColor: colors[f] || "#4fd1c5",
  }));

  if (state.chart) state.chart.destroy();
  state.chart = new Chart(ctx, {
    type: "bar",
    data: { labels, datasets },
    options: {
      responsive: true,
      scales: {
        x: { stacked: true, ticks: { color: "#93a3bd" } },
        y: { stacked: true, beginAtZero: true, max: 1, ticks: { color: "#93a3bd" } },
      },
      plugins: { legend: { labels: { color: "#e7edf7" } } },
    },
  });
}

function renderFactors(factors) {
  const container = $("#factors-list");
  container.innerHTML = "";
  factors.forEach((f) => {
    const block = document.createElement("div");
    block.className = "factor-block";
    const header = document.createElement("h3");
    header.textContent = f.title;
    const meta = document.createElement("div");
    meta.className = "factor-meta";
    meta.innerHTML =
      `${f.mechanism_description} <br/>` +
      `Данные достаточны: ${f.data_sufficient ? "да" : "нет"} · ` +
      `<span class="confidence-pill confidence-${f.overall_confidence}">${confidenceLabel(f.overall_confidence)}</span>` +
      (f.notes ? `<br/>${f.notes}` : "");
    block.appendChild(header);
    block.appendChild(meta);

    if (!f.signals.length) {
      const p = document.createElement("p");
      p.className = "hint";
      p.textContent = "Предупреждений в рассматриваемом периоде нет.";
      block.appendChild(p);
    }

    f.signals.forEach((s) => {
      const det = document.createElement("details");
      det.className = "signal";
      const summary = document.createElement("summary");
      summary.innerHTML = `<span>${s.label} <span class="prov-pill prov-${s.provenance}">${provenanceLabel(s.provenance)}</span></span><span>серьёзность ${(s.severity * 100).toFixed(0)}%</span>`;
      det.appendChild(summary);
      const detail = document.createElement("div");
      detail.className = "signal-detail";
      detail.innerHTML = `
        <div><span class="k">Описание:</span> ${s.description}</div>
        <div><span class="k">Период:</span> ${fmt(s.observed_or_expected_start)} — ${fmt(s.observed_or_expected_end)} ${s.is_time_uncertain ? "(время приблизительное)" : ""}</div>
        <div><span class="k">Значение:</span> ${s.value !== null ? s.value + " " + (s.unit || "") : "—"}</div>
        <div><span class="k">Источник:</span> <a href="${s.source_url}" target="_blank" rel="noopener">${s.source_name}</a></div>
        <div><span class="k">Публикация:</span> ${fmt(s.published_at)}</div>
        <div><span class="k">Правило:</span> ${s.rule_applied}</div>
        <div><span class="k">Уверенность:</span> ${confidenceLabel(s.confidence)} — ${s.confidence_rationale}</div>
        <div><span class="k">Ограничения:</span> ${s.limitations}</div>
      `;
      det.appendChild(detail);
      block.appendChild(det);
    });
    container.appendChild(block);
  });
}

function renderSources(sources) {
  const container = $("#sources-status-list");
  container.innerHTML = "";
  sources.forEach((s) => {
    const row = document.createElement("div");
    row.className = "source-row";
    let dotClass = "ok";
    let statusText = "актуально";
    if (s.is_disabled) { dotClass = "err"; statusText = "отключён пользователем"; }
    else if (s.last_error) { dotClass = "err"; statusText = "ошибка: " + s.last_error; }
    else if (s.is_frozen) { dotClass = "stale"; statusText = "заморожен"; }
    else if (s.is_stale) { dotClass = "stale"; statusText = "устарел"; }
    row.innerHTML = `<span><span class="dot ${dotClass}"></span>${s.name}</span><span>${statusText}${s.last_success_at ? " · " + fmt(s.last_success_at) : ""}</span>`;
    container.appendChild(row);
  });
}

async function exportResult() {
  if (!state.lastResponse) return;
  const id = state.lastResponse.result_id;
  const res = await fetch(`${API}/export/${id}`);
  if (!res.ok) return showError("Не удалось выгрузить отчёт");
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `eva-report-${id}.zip`;
  a.click();
}

async function runExperiment() {
  const panel = $("#experiment-panel");
  const content = $("#experiment-content");
  panel.hidden = false;
  content.textContent = "Выполняется…";
  try {
    const res = await fetch(`${API}/experiment`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "ошибка эксперимента");
    }
    const data = await res.json();
    content.innerHTML = `
      <p>${data.description}</p>
      <p><b>Период события:</b> ${fmt(data.event_period[0])} — ${fmt(data.event_period[1])}<br/>
      <b>Контрольный период:</b> ${fmt(data.control_period[0])} — ${fmt(data.control_period[1])}</p>
      <pre style="white-space:pre-wrap;background:#0e1626;padding:10px;border-radius:6px;">${JSON.stringify(data.metrics, null, 2)}</pre>
    `;
  } catch (e) {
    content.textContent = "Не удалось выполнить эксперимент: " + e.message;
  }
}

init();
