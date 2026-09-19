"use strict";

const API = "/api";
let state = {
  mode: "current",
  viewMode: "2d",
  config: null,
  lastResponse: null,
  lastOrbit: null,
  map: null,
  mapLayer: null,
  chart: null,
  globe: null, // lazily-created three.js state, see renderGlobe()
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

  document.querySelectorAll(".seg-btn[data-mode]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".seg-btn[data-mode]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.mode = btn.dataset.mode;
      $("#historical-hint").style.display = state.mode === "historical" ? "block" : "none";
      if (state.mode === "historical") {
        $("#reference_time").value = "2024-05-10T06:00";
      }
    });
  });
  $("#historical-hint").style.display = "none";

  document.querySelectorAll(".seg-btn[data-view]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".seg-btn[data-view]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.viewMode = btn.dataset.view;
      updateViewHint();
      if (state.lastOrbit) renderTrajectory(state.lastOrbit);
    });
  });
  updateViewHint();

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
  renderTrajectory(o);

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

// Splits a track into contiguous day/night runs (and at antimeridian
// crossings), so both the 2D map and the 3D globe draw the same
// server-computed illumination without a false line jumping across the
// map or a seam at +/-180 degrees longitude. This is the single place
// that logic lives, shared by both renderers.
function splitDaylightSegments(track) {
  if (!track.length) return [];
  const segments = [];
  let segment = [track[0]];
  for (let i = 1; i < track.length; i++) {
    const prev = track[i - 1];
    const cur = track[i];
    const wrapped = Math.abs(cur.lon - prev.lon) > 180;
    const dayChanged = cur.is_daylight !== prev.is_daylight;
    if (wrapped || dayChanged) {
      if (segment.length > 1) segments.push(segment);
      segment = [prev];
    }
    segment.push(cur);
  }
  if (segment.length > 1) segments.push(segment);
  return segments;
}

function updateViewHint() {
  $("#view-hint").textContent =
    state.viewMode === "3d"
      ? "Жёлтый участок — станция освещена Солнцем (день), синий — в тени Земли (ночь), по тем же данным, что и в 2D. Освещение самого глобуса декоративное (студийный свет), реальное положение Солнца не отражает — ориентируйтесь по цвету трассы. Тяните мышью, крутите колесо для приближения."
      : "Жёлтая линия — станция освещена Солнцем (день), тёмно-синяя — станция в тени Земли (ночь). Зелёная метка — начало показанного периода, оранжевая — конец. Карта автоматически приближена к участку трассы.";
}

function renderTrajectory(orbit) {
  state.lastOrbit = orbit;
  if (state.viewMode === "3d") {
    $("#map").hidden = true;
    $("#globe-box").hidden = false;
    renderGlobe(orbit);
  } else {
    $("#globe-box").hidden = true;
    $("#map").hidden = false;
    renderMap(orbit);
  }
}

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
    splitDaylightSegments(track).forEach((segment) => {
      L.polyline(segment.map((p) => [p.lat, p.lon]), {
        color: segment[0].is_daylight ? DAY_COLOR : NIGHT_COLOR,
        weight: 3,
        opacity: 0.9,
      }).addTo(group);
    });

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

const EARTH_RADIUS_KM = 6371;
const GLOBE_RADIUS = 2;

function latLonAltToVec3(lat, lon, altKm) {
  const r = GLOBE_RADIUS * (EARTH_RADIUS_KM + altKm) / EARTH_RADIUS_KM;
  const phi = (lat * Math.PI) / 180;
  const lambda = (lon * Math.PI) / 180;
  return new THREE.Vector3(
    r * Math.cos(phi) * Math.cos(lambda),
    r * Math.sin(phi),
    r * Math.cos(phi) * Math.sin(lambda)
  );
}

function setGlobeStatus(kind, html) {
  const el = $("#globe-status");
  if (kind === null) {
    el.classList.add("hidden");
    return;
  }
  el.classList.remove("hidden");
  el.classList.toggle("error", kind === "error");
  el.innerHTML = html;
}

function initGlobeScene() {
  if (typeof THREE === "undefined") {
    setGlobeStatus(
      "error",
      'Не удалось загрузить библиотеку 3D (three.js). Проверьте подключение к интернету.<br><button id="globe-retry">Повторить</button>'
    );
    $("#globe-retry")?.addEventListener("click", () => {
      state.globe = null;
      renderGlobe(state.lastOrbit);
    });
    return null;
  }
  const box = $("#globe-box");
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, box.clientWidth / Math.max(1, box.clientHeight), 0.1, 100);
  const renderer = new THREE.WebGLRenderer({ canvas: $("#globe-canvas"), antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));

  const starGeo = new THREE.BufferGeometry();
  const starPos = [];
  for (let i = 0; i < 500; i++) {
    const r = 40, th = Math.random() * Math.PI * 2, ph = Math.acos(2 * Math.random() - 1);
    starPos.push(r * Math.sin(ph) * Math.cos(th), r * Math.sin(ph) * Math.sin(th), r * Math.cos(ph));
  }
  starGeo.setAttribute("position", new THREE.Float32BufferAttribute(starPos, 3));
  scene.add(new THREE.Points(starGeo, new THREE.PointsMaterial({ color: 0x445077, size: 0.06 })));

  const earth = new THREE.Mesh(
    new THREE.SphereGeometry(GLOBE_RADIUS, 64, 48),
    new THREE.MeshPhongMaterial({ color: 0x123a5e, shininess: 10, specular: 0x224466 })
  );
  scene.add(earth);
  scene.add(
    new THREE.Mesh(
      new THREE.SphereGeometry(GLOBE_RADIUS * 1.003, 24, 16),
      new THREE.MeshBasicMaterial({ color: 0x5eead4, wireframe: true, transparent: true, opacity: 0.1 })
    )
  );

  // Studio-style lighting attached to the camera (always lights whatever
  // faces the viewer). Deliberately NOT positioned to represent the real
  // sun direction, so it never contradicts the server-computed day/night
  // colouring on the track itself, which is the one authoritative signal.
  scene.add(new THREE.AmbientLight(0x8fa5ff, 0.55));
  const keyLight = new THREE.DirectionalLight(0xffffff, 0.9);
  camera.add(keyLight);
  scene.add(camera);

  const globeState = {
    scene, camera, renderer, earth,
    orbitGroup: null,
    rotX: 0.3, rotY: 0.6, dist: 6.2,
    autoRotate: true, lastInteract: 0,
    dragging: false, lastX: 0, lastY: 0,
  };

  const box2 = box;
  box2.addEventListener("pointerdown", (e) => {
    globeState.dragging = true; globeState.autoRotate = false;
    globeState.lastX = e.clientX; globeState.lastY = e.clientY;
    box2.setPointerCapture(e.pointerId);
  });
  box2.addEventListener("pointerup", () => { globeState.dragging = false; globeState.lastInteract = performance.now(); });
  box2.addEventListener("pointermove", (e) => {
    if (!globeState.dragging) return;
    globeState.rotY += (e.clientX - globeState.lastX) * 0.006;
    globeState.rotX = Math.max(-1.2, Math.min(1.2, globeState.rotX + (e.clientY - globeState.lastY) * 0.006));
    globeState.lastX = e.clientX; globeState.lastY = e.clientY;
  });
  box2.addEventListener(
    "wheel",
    (e) => {
      e.preventDefault();
      globeState.autoRotate = false; globeState.lastInteract = performance.now();
      globeState.dist = Math.max(3.2, Math.min(14, globeState.dist + (e.deltaY > 0 ? 0.4 : -0.4)));
    },
    { passive: false }
  );

  return globeState;
}

function resizeGlobe() {
  const g = state.globe;
  if (!g || !g.inited) return;
  const box = $("#globe-box");
  g.camera.aspect = box.clientWidth / Math.max(1, box.clientHeight);
  g.camera.updateProjectionMatrix();
  g.renderer.setSize(box.clientWidth, box.clientHeight, false);
}

function globeLoop() {
  requestAnimationFrame(globeLoop);
  const g = state.globe;
  if (state.viewMode !== "3d" || !g || !g.inited || g.failed) return;
  if (g.autoRotate) g.rotY += 0.0025;
  else if (!g.dragging && performance.now() - g.lastInteract > 4000) g.autoRotate = true;
  try {
    g.camera.position.set(
      g.dist * Math.cos(g.rotX) * Math.sin(g.rotY),
      g.dist * Math.sin(g.rotX),
      g.dist * Math.cos(g.rotX) * Math.cos(g.rotY)
    );
    g.camera.lookAt(0, 0, 0);
    g.renderer.render(g.scene, g.camera);
  } catch (err) {
    g.failed = true;
    setGlobeStatus(
      "error",
      "Ошибка при отрисовке 3D-сцены: " + (err && err.message ? err.message : String(err)) +
        '<br><button id="globe-retry">Повторить</button>'
    );
    $("#globe-retry")?.addEventListener("click", () => { state.globe = null; renderGlobe(state.lastOrbit); });
  }
}
requestAnimationFrame(globeLoop);

function renderGlobe(orbit) {
  if (!orbit) return;
  if (!state.globe) {
    setGlobeStatus("normal", "Загружаю 3D-движок…");
    const g = initGlobeScene();
    if (!g) return; // error already shown by initGlobeScene
    g.inited = true;
    g.failed = false;
    state.globe = g;
    resizeGlobe();
    setGlobeStatus(null);
  }
  const g = state.globe;
  if (g.orbitGroup) {
    g.scene.remove(g.orbitGroup);
  }
  const group = new THREE.Group();
  const track = orbit.track;
  splitDaylightSegments(track).forEach((segment) => {
    if (segment.length < 2) return;
    const pts = segment.map((p) => latLonAltToVec3(p.lat, p.lon, p.alt_km));
    const curve = new THREE.CatmullRomCurve3(pts, false);
    const tube = new THREE.TubeGeometry(curve, Math.max(4, segment.length * 2), 0.014, 6, false);
    group.add(new THREE.Mesh(tube, new THREE.MeshBasicMaterial({ color: segment[0].is_daylight ? 0xfbbf24 : 0x3355c4 })));
  });
  if (track.length) {
    const first = track[0], last = track[track.length - 1];
    const mk = (p, color) =>
      new THREE.Mesh(new THREE.SphereGeometry(0.045, 16, 16), new THREE.MeshBasicMaterial({ color }));
    const m1 = mk(first, 0x4fd18c); m1.position.copy(latLonAltToVec3(first.lat, first.lon, first.alt_km + 5));
    const m2 = mk(last, 0xff9d47); m2.position.copy(latLonAltToVec3(last.lat, last.lon, last.alt_km + 5));
    group.add(m1); group.add(m2);
  }
  g.scene.add(group);
  g.orbitGroup = group;
}

window.addEventListener("resize", resizeGlobe);

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
  const colors = { space_weather: "#f5c451", conjunction_mmod: "#c9a8ff" };
  const datasets = factorNames.map((f) => ({
    label: f === "space_weather" ? "Космическая погода" : "Сближения/MMOD",
    data: data.windows.map((w) => {
      const c = w.factor_contributions.find((c) => c.factor === f);
      return c ? c.time_weighted_severity : 0;
    }),
    backgroundColor: colors[f] || "#bfe6ff",
  }));

  if (state.chart) state.chart.destroy();
  state.chart = new Chart(ctx, {
    type: "bar",
    data: { labels, datasets },
    options: {
      responsive: true,
      scales: {
        x: { stacked: true, ticks: { color: "#9fb7d6" } },
        y: { stacked: true, beginAtZero: true, max: 1, ticks: { color: "#9fb7d6" } },
      },
      plugins: { legend: { labels: { color: "#f3f8ff" } } },
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
      <pre style="white-space:pre-wrap;background:rgba(255,255,255,.06);padding:12px;border-radius:14px;">${JSON.stringify(data.metrics, null, 2)}</pre>
    `;
  } catch (e) {
    content.textContent = "Не удалось выполнить эксперимент: " + e.message;
  }
}

/* Decorative twinkling starfield behind the whole page (the "Классика"
   gradient background chosen for the site). Purely cosmetic — runs
   independently of everything else and never touches app state. */
function initStarfield() {
  const cv = document.getElementById("bgfx");
  if (!cv) return;
  const ctx = cv.getContext("2d");
  let stars = [];
  function resize() {
    cv.width = window.innerWidth;
    cv.height = window.innerHeight;
    stars = Array.from({ length: 140 }, () => ({
      x: Math.random() * cv.width,
      y: Math.random() * cv.height,
      r: Math.random() * 1.4 + 0.3,
      p: Math.random() * Math.PI * 2,
      s: Math.random() * 0.02 + 0.01,
    }));
  }
  window.addEventListener("resize", resize);
  resize();
  let t = 0;
  function loop() {
    requestAnimationFrame(loop);
    t += 1;
    ctx.clearRect(0, 0, cv.width, cv.height);
    stars.forEach((s) => {
      const alpha = 0.35 + 0.65 * Math.abs(Math.sin(s.p + t * s.s));
      ctx.beginPath();
      ctx.fillStyle = `rgba(230,238,255,${alpha.toFixed(2)})`;
      ctx.arc(s.x, s.y, s.r, 0, 7);
      ctx.fill();
    });
  }
  loop();
}
initStarfield();

init();
