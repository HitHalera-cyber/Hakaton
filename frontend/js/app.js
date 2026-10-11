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

function toLocalInputValue(date) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}T${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}`;
}

async function init() {
  const now = new Date();
  $("#reference_time").value = toLocalInputValue(now);
  $("#compare_date_a").value = toLocalInputValue(now);
  $("#compare_date_b").value = toLocalInputValue(new Date(now.getTime() + 24 * 3600 * 1000));

  document.querySelectorAll(".seg-btn[data-mode]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".seg-btn[data-mode]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.mode = btn.dataset.mode;
      $("#historical-hint").style.display = state.mode === "historical" ? "block" : "none";
      if (state.mode === "historical") {
        $("#reference_time").value = "2024-05-10T06:00";
        $("#compare_date_a").value = "2024-05-10T06:00";
        $("#compare_date_b").value = "2024-05-21T06:00";
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
  $("#compare-dates-btn").addEventListener("click", runCompareDates);
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
    force_refresh: $("#force_refresh").checked,
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

function setCompareLoading(v) {
  const btn = $("#compare-dates-btn");
  const status = $("#compare-dates-status");
  btn.disabled = v;
  status.hidden = !v;
  status.textContent = v ? "Выполняется расчёт обеих дат…" : "";
}

// Buckets a window's combined_score (0..1, "team calculation" per O2/O4 —
// see analysis.py's module docstring for the underlying weighted-average
// rule) into a plain-language go/no-go verdict. Deliberately NOT presented
// as an authoritative safety threshold: it is a stylised simplification of
// the same number already shown in the windows table, meant to give a
// non-specialist user an immediate first read — the detailed reason text
// and the footer's "требует допуска уполномоченных специалистов" disclaimer
// stay right next to it.
function verdictFromScore(score) {
  if (score === null || score === undefined) {
    return { level: "unknown", title: "Недостаточно данных для вердикта" };
  }
  if (score <= 0.15) return { level: "ok", title: "Можно выходить" };
  if (score <= 0.4) return { level: "caution", title: "Выход возможен, требуется повышенное внимание" };
  return { level: "danger", title: "Не рекомендуется без дополнительной проверки" };
}

function verdictForWindow(recommendation, w) {
  if (!recommendation.has_recommendation || !w) {
    return {
      level: "unknown",
      title: "Недостаточно данных для вердикта",
      detail: recommendation.reason + (recommendation.caveats.length ? " " + recommendation.caveats.join(" ") : ""),
    };
  }
  const incomplete = w.data_completeness === "insufficient_data";
  const { level, title } = verdictFromScore(w.combined_score);
  let detail = recommendation.reason;
  if (recommendation.caveats.length) detail += " " + recommendation.caveats.join(" ");
  if (incomplete) detail += " Внимание: часть факторов для этого окна не имеет данных — вердикт может измениться, когда данные появятся.";
  return { level, title, detail };
}

function verdictBadgeHtml(v) {
  return (
    `<div class="verdict-badge verdict-${v.level}"><span class="verdict-title">${v.title}</span></div>` +
    `<p class="verdict-detail">${v.detail}</p>`
  );
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

  // Plain-language go/no-go verdict, first thing shown — see verdictForWindow.
  const v = verdictForWindow(data.recommendation, data.windows[data.recommendation.recommended_window_index]);
  $("#verdict-badge").className = "verdict-badge verdict-" + v.level;
  $("#verdict-title").textContent = v.title;
  $("#verdict-detail").textContent = v.detail;

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
  let spanNote = "";
  if (o.track.length > 1) {
    const spanHours = (new Date(o.track[o.track.length - 1].t) - new Date(o.track[0].t)) / 3_600_000;
    const orbits = spanHours / 1.545; // ISS orbital period ~92.68 min
    spanNote = ` · показан период ${fmt(o.track[0].t)} — ${fmt(o.track[o.track.length - 1].t)} (${spanHours.toFixed(1)} ч ≈ ${orbits.toFixed(1)} витка МКС) — охватывает все сравниваемые окна, а не только одну длительность ВКД`;
  }
  $("#orbit-meta").textContent =
    `Источник: ${o.source_name} · эпоха ${fmt(o.epoch)} · давность данных ${o.age_hours.toFixed(1)} ч` +
    (o.is_reconstruction ? " · РЕКОНСТРУКЦИЯ (см. пояснение)" : "") + spanNote;

  // Each panel below is rendered independently and wrapped so a failure in
  // one (e.g. the map/globe throwing because a CDN script like Leaflet
  // didn't load) can't silently cascade into the others never rendering —
  // previously an exception here aborted the rest of render() outright, so
  // a single broken panel could make the windows table/chart/factors look
  // completely empty even though the underlying data was fine.
  safeRender("trajectory", () => renderTrajectory(o));
  safeRender("windows", () => renderWindows(data));
  safeRender("factors", () => renderFactors(data.factors));
  safeRender("sources", () => renderSources(data.sources));

  $("#result-id-label").textContent = `ID результата: ${data.result_id} · версия алгоритма ${data.algorithm_version}`;
}

function safeRender(label, fn) {
  try {
    fn();
  } catch (e) {
    console.error(`render step "${label}" failed:`, e);
  }
}

// Deliberately not pure yellow/blue: a swatch pair that close to Ukraine's
// flag colors, stacked in the legend, was reading as the flag rather than
// as "day/night" — shifted to amber/indigo, still warm=day, cool=night.
const DAY_COLOR = "#e0a83e";
const NIGHT_COLOR = "#4a3f8c";
const TRACK_DENSIFY_STEPS = 8;
const TRANSITION_GRADIENT_STEPS = 8;

function hexToRgb(hex) {
  const v = parseInt(hex.slice(1), 16);
  return [(v >> 16) & 255, (v >> 8) & 255, v & 255];
}

// Linear RGB interpolation between two hex colors: used to draw a short
// gradient band across a day/night transition edge instead of a hard
// color cut, since dawn/dusk is gradual in reality, not instantaneous.
// A stylised visual approximation spread evenly over one sample gap, not
// a physical twilight/penumbra model.
function colorLerp(hexA, hexB, t) {
  const [r1, g1, b1] = hexToRgb(hexA);
  const [r2, g2, b2] = hexToRgb(hexB);
  const lerp = (a, b) => Math.round(a + (b - a) * t);
  return "#" + [lerp(r1, r2), lerp(g1, g2), lerp(b1, b2)].map((c) => c.toString(16).padStart(2, "0")).join("");
}

// Splits a track only at antimeridian (+/-180 degree longitude) crossings.
// On the flat 2D map, connecting a point pair from either side of the
// seam draws a spurious straight line across the whole map, so those runs
// must never share a polyline; in the 3D Cartesian view there is no real
// seam, so callers pass breakAtWrap=false to keep one continuous curve,
// matching the previous (correct) 3D behavior. Day/night coloring,
// including the transition gradient, is handled separately per-edge (see
// buildDayNightPieces2D/3D below), so this no longer also splits on
// daylight change the way it used to.
function splitWrapRuns(track, breakAtWrap) {
  if (!track.length) return [];
  if (!breakAtWrap) return [track];
  const runs = [];
  let run = [track[0]];
  for (let i = 1; i < track.length; i++) {
    const prev = track[i - 1];
    const cur = track[i];
    if (Math.abs(cur.lon - prev.lon) > 180) {
      if (run.length > 1) runs.push(run);
      run = [cur];
    } else {
      run.push(cur);
    }
  }
  if (run.length > 1) runs.push(run);
  return runs;
}

// Same sparseness problem as the 3D globe (see densifyTrackPoints below),
// but for a flat [lat, lon] polyline: a straight line between samples up
// to ~10 minutes (~38 degrees of arc) apart looks like short straight
// facets, not the gentle curve a real ground track has. Inserting
// great-circle intermediate points (the standard "intermediate point on a
// great circle" formula) between each pair fixes that without needing a
// smoothing spline that might drift off the true path.
function densifyLatLon(points, stepsBetween) {
  if (points.length < 2) return points.map((p) => [p.lat, p.lon]);
  const out = [];
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i], b = points[i + 1];
    const lat1 = (a.lat * Math.PI) / 180, lon1 = (a.lon * Math.PI) / 180;
    const lat2 = (b.lat * Math.PI) / 180, lon2 = (b.lon * Math.PI) / 180;
    const d = 2 * Math.asin(Math.sqrt(
      Math.sin((lat2 - lat1) / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin((lon2 - lon1) / 2) ** 2
    ));
    out.push([a.lat, a.lon]);
    if (d > 1e-8) {
      for (let s = 1; s < stepsBetween; s++) {
        const f = s / stepsBetween;
        const A = Math.sin((1 - f) * d) / Math.sin(d);
        const B = Math.sin(f * d) / Math.sin(d);
        const x = A * Math.cos(lat1) * Math.cos(lon1) + B * Math.cos(lat2) * Math.cos(lon2);
        const y = A * Math.cos(lat1) * Math.sin(lon1) + B * Math.cos(lat2) * Math.sin(lon2);
        const z = A * Math.sin(lat1) + B * Math.sin(lat2);
        const latI = Math.atan2(z, Math.sqrt(x * x + y * y));
        const lonI = Math.atan2(y, x);
        out.push([(latI * 180) / Math.PI, (lonI * 180) / Math.PI]);
      }
    }
  }
  out.push([points[points.length - 1].lat, points[points.length - 1].lon]);
  return out;
}

// Turns one wrap-free run into drawable [lat, lon] pieces: consecutive
// same-state points are grouped into a single densified polyline (solid
// color), and each point pair where day/night actually flips is rendered
// as several short color-interpolated sub-pieces spanning that one edge —
// the gradual-dawn effect. (Previously every polyline here was colored
// from the *first* point of its group; after a day/night change that
// first point was still the old state, so the new group — mostly the new
// state's points — was drawn in the old color. Coloring per-edge instead
// fixes that along with adding the gradient.)
function buildDayNightPieces2D(run) {
  const pieces = [];
  let group = [run[0]];
  const flushGroup = () => {
    if (group.length > 1) {
      pieces.push({
        latlngs: densifyLatLon(group, TRACK_DENSIFY_STEPS),
        color: group[0].is_daylight ? DAY_COLOR : NIGHT_COLOR,
      });
    }
  };
  for (let i = 1; i < run.length; i++) {
    const prev = run[i - 1];
    const cur = run[i];
    if (cur.is_daylight !== prev.is_daylight) {
      flushGroup();
      const latlngs = densifyLatLon([prev, cur], TRANSITION_GRADIENT_STEPS);
      const colorA = prev.is_daylight ? DAY_COLOR : NIGHT_COLOR;
      const colorB = cur.is_daylight ? DAY_COLOR : NIGHT_COLOR;
      for (let s = 0; s < latlngs.length - 1; s++) {
        const t = (s + 0.5) / (latlngs.length - 1);
        pieces.push({ latlngs: [latlngs[s], latlngs[s + 1]], color: colorLerp(colorA, colorB, t) });
      }
      group = [cur];
    } else {
      group.push(cur);
    }
  }
  flushGroup();
  return pieces;
}

function updateViewHint() {
  $("#view-hint").textContent =
    state.viewMode === "3d"
      ? "Золотистый участок — станция освещена Солнцем (день), фиолетовый — в тени Земли (ночь). Освещение глобуса декоративное, ориентируйтесь по цвету трассы. Тяните мышью, крутите колесо для приближения."
      : "Золотистая линия — станция освещена Солнцем (день), тёмно-фиолетовая — станция в тени Земли (ночь). Зелёная метка — начало показанного периода, оранжевая — конец. Карта автоматически приближена к участку трассы.";
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
    // A multi-orbit ground track can span close to the full 360° of
    // longitude, which used to make Leaflet zoom out far enough (combined
    // with worldCopyJump) to render the whole world map two or three
    // times side by side ("glued" copies) instead of one continuous map.
    // Locking the map to a single world copy — no wrap-jumping, tiles
    // that don't repeat past +/-180°, and hard bounds so it can never
    // zoom out past showing that one copy — fixes this regardless of how
    // wide the track's bounding box is.
    state.map = L.map("map", {
      worldCopyJump: false,
      maxBounds: [[-90, -180], [90, 180]],
      maxBoundsViscosity: 1.0,
      minZoom: 2,
    }).setView([0, 0], 2);
    // Leaflet's default attribution control prepends its own "Leaflet"
    // branding (with a small flag icon) before whatever the tile layer
    // contributes; drop that prefix and keep only the OSM credit their
    // tile usage policy actually requires.
    state.map.attributionControl.setPrefix(false);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap",
      maxZoom: 8,
      noWrap: true,
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
    splitWrapRuns(track, true).forEach((run) => {
      buildDayNightPieces2D(run).forEach((piece) => {
        L.polyline(piece.latlngs, { color: piece.color, weight: 3, opacity: 0.9 }).addTo(group);
      });
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

// Server track points can be up to ~10 minutes apart, which for the ISS
// (~7.7 km/s) is tens of degrees of arc — a straight Catmull-Rom spline
// through such sparse 3D points cuts corners and looks like a jagged
// "star" instead of an orbit. Inserting spherical-linear-interpolated
// (slerp) points between each pair keeps every inserted point on the true
// great-circle path at the correct altitude, so the curve actually hugs
// the globe the way a real ground track does.
function densifyTrackPoints(points, stepsBetween) {
  if (points.length < 2) return points.map((p) => latLonAltToVec3(p.lat, p.lon, p.alt_km));
  const out = [];
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i], b = points[i + 1];
    const va = latLonAltToVec3(a.lat, a.lon, a.alt_km);
    const vb = latLonAltToVec3(b.lat, b.lon, b.alt_km);
    const ra = va.length(), rb = vb.length();
    const ua = va.clone().normalize(), ub = vb.clone().normalize();
    const cosTheta = Math.max(-1, Math.min(1, ua.dot(ub)));
    const theta = Math.acos(cosTheta);
    out.push(va);
    if (theta > 1e-6) {
      for (let s = 1; s < stepsBetween; s++) {
        const t = s / stepsBetween;
        const w1 = Math.sin((1 - t) * theta) / Math.sin(theta);
        const w2 = Math.sin(t * theta) / Math.sin(theta);
        const dir = ua.clone().multiplyScalar(w1).add(ub.clone().multiplyScalar(w2)).normalize();
        out.push(dir.multiplyScalar(ra + (rb - ra) * t));
      }
    }
  }
  out.push(latLonAltToVec3(points[points.length - 1].lat, points[points.length - 1].lon, points[points.length - 1].alt_km));
  return out;
}

// 3D counterpart of buildDayNightPieces2D: same grouping/gradient logic,
// but producing THREE.Vector3 point arrays and numeric colors for tubes.
function buildDayNightPieces3D(run) {
  const pieces = [];
  let group = [run[0]];
  const flushGroup = () => {
    if (group.length > 1) {
      pieces.push({
        points: densifyTrackPoints(group, TRACK_DENSIFY_STEPS),
        color: group[0].is_daylight ? 0xe0a83e : 0x4a3f8c,
      });
    }
  };
  for (let i = 1; i < run.length; i++) {
    const prev = run[i - 1];
    const cur = run[i];
    if (cur.is_daylight !== prev.is_daylight) {
      flushGroup();
      const pts = densifyTrackPoints([prev, cur], TRANSITION_GRADIENT_STEPS);
      const colorA = prev.is_daylight ? DAY_COLOR : NIGHT_COLOR;
      const colorB = cur.is_daylight ? DAY_COLOR : NIGHT_COLOR;
      for (let s = 0; s < pts.length - 1; s++) {
        const t = (s + 0.5) / (pts.length - 1);
        pieces.push({ points: [pts[s], pts[s + 1]], color: parseInt(colorLerp(colorA, colorB, t).slice(1), 16) });
      }
      group = [cur];
    } else {
      group.push(cur);
    }
  }
  flushGroup();
  return pieces;
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

  // Flat blue placeholder shown immediately; swapped for a real Earth
  // photo texture once it loads (see below) — never left blocking globe
  // render on a slow/unreachable CDN, and degrades gracefully to the
  // placeholder colour if the texture fails to load at all.
  const earthMaterial = new THREE.MeshPhongMaterial({ color: 0x123a5e, shininess: 6, specular: 0x223344 });
  const earth = new THREE.Mesh(new THREE.SphereGeometry(GLOBE_RADIUS, 64, 48), earthMaterial);
  scene.add(earth);
  new THREE.TextureLoader().load(
    "https://cdn.jsdelivr.net/gh/mrdoob/three.js@r128/examples/textures/planets/earth_atmos_2048.jpg",
    (tex) => {
      earthMaterial.map = tex;
      earthMaterial.color.set(0xffffff);
      earthMaterial.needsUpdate = true;
    },
    undefined,
    () => {} // texture unreachable: keep the flat-colour fallback already on screen
  );

  // Soft atmospheric haze at the limb, replacing the previous wireframe
  // grid overlay — a plain colour shell reads far closer to a real photo
  // of Earth from orbit than a technical-looking grid does.
  scene.add(
    new THREE.Mesh(
      new THREE.SphereGeometry(GLOBE_RADIUS * 1.02, 48, 32),
      new THREE.MeshBasicMaterial({ color: 0x6ab7ff, transparent: true, opacity: 0.12, side: THREE.BackSide })
    )
  );

  // Studio-style lighting attached to the camera (always lights whatever
  // faces the viewer). Deliberately NOT positioned to represent the real
  // sun direction, so it never contradicts the server-computed day/night
  // colouring on the track itself, which is the one authoritative signal.
  scene.add(new THREE.AmbientLight(0x8fa5ff, 0.45));
  const keyLight = new THREE.DirectionalLight(0xffffff, 1.0);
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
  splitWrapRuns(track, false).forEach((run) => {
    buildDayNightPieces3D(run).forEach((piece) => {
      if (piece.points.length < 2) return;
      const curve = new THREE.CatmullRomCurve3(piece.points, false, "catmullrom", 0.5);
      const tube = new THREE.TubeGeometry(curve, Math.max(2, piece.points.length * 2), 0.014, 8, false);
      group.add(new THREE.Mesh(tube, new THREE.MeshBasicMaterial({ color: piece.color })));
    });
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

function windowSummaryHtml(result, idx, isWinner, isWorst) {
  const w = result.windows[idx];
  const factorLines = w.factor_contributions
    .map((c) => {
      const label = { space_weather: "Космическая погода", conjunction_mmod: "Сближения/MMOD" }[c.factor] || c.factor;
      const driving = c.driving_signals.length ? c.driving_signals.join("; ") : "значимых сигналов нет";
      return `<li><b>${label}:</b> ${driving} (пересечение ${c.overlap_minutes.toFixed(0)} мин, серьёзность до ${(c.max_severity * 100).toFixed(0)}%)</li>`;
    })
    .join("");
  const score = w.combined_score === null || w.combined_score === undefined ? "нет оценки (недостаточно данных)" : w.combined_score.toFixed(2);
  const cls = isWinner ? "compare-window-winner" : isWorst ? "compare-window-worst" : "";
  const badge = isWinner
    ? '<span class="badge rec">Лучший вариант</span>'
    : isWorst
    ? '<span class="badge worst">Худший вариант</span>'
    : "";
  return `
    <div class="compare-window ${cls}">
      ${badge}
      <p><b>Окно:</b> ${fmt(w.start)} — ${fmt(w.end)}</p>
      <p><b>Совокупная оценка риска:</b> ${score} · <b>Полнота данных:</b> ${confidenceLabel(w.data_completeness)}</p>
      <ul>${factorLines}</ul>
    </div>`;
}

// Worst = highest combined_score across BOTH dates' windows (the backend
// already picks the cross-date best via _recommend/winning_date/
// winning_window_index; this mirrors that for the other end of the range).
// Returns null if there's no real spread (worst ties with best), so a
// uniformly-quiet or uniformly-scored comparison doesn't show a
// contradictory "best"+"worst" badge on the same window.
function findWorstWindow(resultA, resultB, bestDate, bestIdx) {
  const entries = [];
  resultA.windows.forEach((w, i) => entries.push({ w, date: "a", idx: i }));
  resultB.windows.forEach((w, i) => entries.push({ w, date: "b", idx: i }));
  const scored = entries.filter((e) => e.w.combined_score !== null && e.w.combined_score !== undefined);
  if (!scored.length) return null;
  let worst = scored[0];
  for (const e of scored) if (e.w.combined_score > worst.w.combined_score) worst = e;
  if (bestDate && worst.date === bestDate && worst.idx === bestIdx) return null;
  return worst;
}

async function runCompareDates() {
  const panel = $("#compare-dates-panel");
  const content = $("#compare-dates-content");
  panel.hidden = false;
  content.textContent = "Выполняется…";

  const dateAVal = $("#compare_date_a").value;
  const dateBVal = $("#compare_date_b").value;
  if (!dateAVal || !dateBVal) {
    content.textContent = "Укажите обе даты для сравнения.";
    return;
  }
  const { disabled, frozen } = collectDisabledFrozen();
  const req = {
    mode: state.mode,
    date_a: isoUtc(dateAVal),
    date_b: isoUtc(dateBVal),
    duration_hours: parseFloat($("#duration_hours").value),
    search_period_hours: parseFloat($("#search_period_hours").value),
    step_minutes: parseFloat($("#step_minutes").value),
    disabled_sources: disabled,
    frozen_sources: frozen,
    force_refresh: $("#force_refresh").checked,
  };

  setCompareLoading(true);
  try {
    const res = await fetch(`${API}/compare-dates`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Ошибка сервера (${res.status})`);
    }
    const data = await res.json();

    const bestIdxA = data.winning_date === "a" ? data.winning_window_index : null;
    const bestIdxB = data.winning_date === "b" ? data.winning_window_index : null;
    const worst = findWorstWindow(data.result_a, data.result_b, data.winning_date, data.winning_window_index);
    const worstIdxA = worst && worst.date === "a" ? worst.idx : null;
    const worstIdxB = worst && worst.date === "b" ? worst.idx : null;
    const windowsA = data.result_a.windows
      .map((_, i) => windowSummaryHtml(data.result_a, i, i === bestIdxA, i === worstIdxA))
      .join("");
    const windowsB = data.result_b.windows
      .map((_, i) => windowSummaryHtml(data.result_b, i, i === bestIdxB, i === worstIdxB))
      .join("");

    const winningWindow =
      data.winning_date === "a" ? data.result_a.windows[data.winning_window_index] :
      data.winning_date === "b" ? data.result_b.windows[data.winning_window_index] :
      null;
    const v = verdictForWindow(data.overall_recommendation, winningWindow);

    content.innerHTML = `
      <div class="compare-verdict">${verdictBadgeHtml(v)}</div>
      <div class="compare-grid">
        <div class="compare-col">
          <h3>Дата А — ${fmt(data.result_a.request.reference_time)}${data.winning_date === "a" ? " ✓" : ""}</h3>
          ${windowsA}
        </div>
        <div class="compare-col">
          <h3>Дата Б — ${fmt(data.result_b.request.reference_time)}${data.winning_date === "b" ? " ✓" : ""}</h3>
          ${windowsB}
        </div>
      </div>
    `;
  } catch (e) {
    content.textContent = "Не удалось сравнить даты: " + e.message;
  } finally {
    setCompareLoading(false);
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
