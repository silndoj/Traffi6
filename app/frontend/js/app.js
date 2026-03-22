// ── State ───────────────────────────────────────────────────────────────────

const state = {
  ws: null,
  map: null,
  markers: new Map(), // ID -> L.Marker
  sensorMarkers: [],
  isPaused: false,
  speed: 5,
  timeline: { totalSteps: 0, currentStep: 0, startTime: "", endTime: "" },
  reconnectDelay: 1000,
  counts: { car: 0, truck: 0, motor_bike: 0, bicycle: 0, foot: 0 },
  heatmapLayer: null,
  heatmapVisible: false,
  analysisLayer: null,
  analysisVisible: false,
  corridorLayer: null,
  corridorsVisible: false,
  signalData: null,
  corridorData: null,
  trafficLightMarkers: new Map(),
  trafficLightsVisible: true,
};

const VEHICLE_TYPES = ["car", "truck", "motor_bike", "bicycle", "foot"];

const ICON_SIZES = {
  car: [16, 16],
  truck: [22, 16],
  motor_bike: [20, 18],
  bicycle: [18, 16],
  foot: [16, 16],
};

const ICON_CACHE = {};
VEHICLE_TYPES.forEach((type) => {
  const size = ICON_SIZES[type] || [26, 26];
  ICON_CACHE[type] = L.icon({
    iconUrl: `assets/${type}.png`,
    iconSize: size,
    iconAnchor: [size[0] / 2, size[1] / 2],
  });
});

// ── DOM Refs ────────────────────────────────────────────────────────────────

const dom = {
  timestamp: document.getElementById("current-timestamp"),
  totalVehicles: document.getElementById("total-vehicles"),
  activeSensors: document.getElementById("active-sensors"),
  wsStatusDot: document.getElementById("ws-status-dot"),
  wsStatusText: document.getElementById("ws-status-text"),
  btnPause: document.getElementById("btn-pause"),
  iconPause: document.getElementById("icon-pause"),
  iconPlay: document.getElementById("icon-play"),
  timelineProgress: document.getElementById("timeline-progress"),
  timelineThumb: document.getElementById("timeline-thumb"),
  timelineTrack: document.getElementById("timeline-track"),
  timeStart: document.getElementById("time-start"),
  timeEnd: document.getElementById("time-end"),
  stepCounter: document.getElementById("step-counter"),
};

// ── Formatting ──────────────────────────────────────────────────────────────

function formatNumber(n) {
  return Number(n).toLocaleString("en-US");
}

function formatTimestamp(ts) {
  if (!ts) return "--";
  const d = new Date(ts);
  if (isNaN(d.getTime())) return ts;
  const day = d.getDate();
  const months = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
  const month = months[d.getMonth()];
  const year = d.getFullYear();
  const hours = String(d.getHours()).padStart(2, "0");
  const mins = String(d.getMinutes()).padStart(2, "0");
  return `${day} ${month} ${year}, ${hours}:${mins}`;
}

function formatTimeShort(ts) {
  if (!ts) return "--";
  const d = new Date(ts);
  if (isNaN(d.getTime())) return ts;
  const day = d.getDate();
  const months = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
  return `${day} ${months[d.getMonth()]} ${d.getFullYear()}`;
}

// ── Map Init ────────────────────────────────────────────────────────────────

function initMap() {
  state.map = L.map("map", {
    center: [49.00587, 8.40162],
    zoom: 14,
    zoomControl: true,
  });

  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
    subdomains: "abcd",
    maxZoom: 19,
  }).addTo(state.map);
}

// ── Heatmap ─────────────────────────────────────────────────────────────────

function initHeatmap() {
  state.heatmapLayer = L.heatLayer([], {
    radius: 45,
    blur: 30,
    maxZoom: 20,
    minOpacity: 0.1,
    max: 1.0,
    gradient: {
      0.0: "transparent",
      0.1: "#3b82f6",
      0.3: "#22c55e",
      0.5: "#f59e0b",
      0.75: "#ef4444",
      1.0: "#dc2626",
    },
  });

  document.getElementById("btn-heatmap").addEventListener("click", () => {
    state.heatmapVisible = !state.heatmapVisible;
    document.getElementById("btn-heatmap").classList.toggle("active");
    if (state.heatmapVisible) {
      state.heatmapLayer.addTo(state.map);
    } else {
      state.map.removeLayer(state.heatmapLayer);
    }
  });
}

// ── Alerts ──────────────────────────────────────────────────────────────────

function renderAlerts(anomalies) {
  const container = document.getElementById("alert-list");
  if (!anomalies.length) {
    container.innerHTML = '<div class="no-alerts">No alerts</div>';
    return;
  }
  container.innerHTML = anomalies
    .slice(0, 3)
    .map((a) => {
      const severityClass = a.severity > 3 ? "danger" : "warning";
      const typeLabel =
        a.type === "high_traffic" ? "High Traffic Volume" : a.type;
      const sensorLabel = "Sensor " + a.sensor_id.slice(0, 8) + "...";
      return (
        '<div class="alert-card ' +
        severityClass +
        '">' +
        '<div class="alert-severity">' +
        a.severity.toFixed(1) +
        "\u03C3</div>" +
        '<div class="alert-info">' +
        '<div class="alert-type">' +
        typeLabel +
        "</div>" +
        '<div class="alert-sensor">' +
        sensorLabel +
        "</div>" +
        "</div>" +
        "</div>"
      );
    })
    .join("");
}

// ── Intelligence ────────────────────────────────────────────────────────────

async function fetchIntelligence() {
  try {
    const res = await fetch("/api/intelligence");
    if (!res.ok) return;
    const data = await res.json();
    const container = document.getElementById("peak-hours");
    if (data.peak_hours) {
      container.innerHTML =
        '<div class="section-label">PEAK HOURS</div>' +
        data.peak_hours
          .slice(0, 3)
          .map(
            (p) =>
              '<div class="peak-item">' +
              '<span class="peak-hour">' +
              p.hour +
              "</span>" +
              '<span class="peak-count">' +
              formatNumber(Math.round(p.avg_vehicles)) +
              " veh.</span>" +
              "</div>",
          )
          .join("");
    }
  } catch (e) {
    // Intelligence endpoint may not be available yet
  }
}

// ── QR Code ─────────────────────────────────────────────────────────────────

function generateQR() {
  const port = window.location.port ? ":" + window.location.port : "";
  const url =
    window.location.protocol +
    "//" +
    window.location.hostname +
    port +
    "/mobile.html";
  new QRCode(document.getElementById("qr-code"), {
    text: url,
    width: 100,
    height: 100,
    colorDark: "#e4e4e7",
    colorLight: "#1a1d27",
  });
}

// ── Traffic Lights ──────────────────────────────────────────────────────────

var TL_COLORS = { green: "#22c55e", yellow: "#f59e0b", red: "#ef4444" };

function updateTrafficLights(lights) {
  if (!state.trafficLightsVisible) return;

  var seen = new Set();
  for (var i = 0; i < lights.length; i++) {
    var tl = lights[i];
    var key = tl.lat + "," + tl.lon;
    seen.add(key);

    var existing = state.trafficLightMarkers.get(key);
    if (existing) {
      // Update color
      var el = existing.getElement();
      if (el) {
        var dot = el.querySelector(".tl-dot");
        if (dot) dot.style.background = TL_COLORS[tl.state] || TL_COLORS.red;
      }
    } else {
      // Create new traffic light marker
      var size = tl.degree >= 5 ? 6 : 4;
      var opacity = tl.state === "green" ? 0.5 : tl.state === "red" ? 0.7 : 0.9;
      var icon = L.divIcon({
        className: "tl-icon",
        iconSize: [size, size],
        iconAnchor: [size / 2, size / 2],
        html:
          '<div class="tl-dot" style="width:' +
          size +
          "px;height:" +
          size +
          "px;background:" +
          TL_COLORS[tl.state] +
          ";border-radius:50%;opacity:" +
          opacity +
          ";box-shadow:0 0 3px " +
          TL_COLORS[tl.state] +
          ';"></div>',
      });
      var marker = L.marker([tl.lat, tl.lon], {
        icon: icon,
        interactive: false,
        pane: "markerPane",
      });
      marker.addTo(state.map);
      state.trafficLightMarkers.set(key, marker);
    }
  }
}

// ── Marker Pool ─────────────────────────────────────────────────────────────

function updateMarkers(vehicles) {
  const activeIds = new Set();

  for (const v of vehicles) {
    const id = v.ID;
    activeIds.add(id);

    const existing = state.markers.get(id);
    if (existing) {
      existing.setLatLng([v.X, v.Y]);
      if (existing._vehicleType !== v.TYPE) {
        existing.setIcon(ICON_CACHE[v.TYPE] || ICON_CACHE.car);
        existing._vehicleType = v.TYPE;
      }
    } else {
      const marker = L.marker([v.X, v.Y], {
        icon: ICON_CACHE[v.TYPE] || ICON_CACHE.car,
        interactive: false,
      }).addTo(state.map);
      marker._vehicleType = v.TYPE;
      state.markers.set(id, marker);
    }
  }

  // Remove markers no longer present
  for (const [id, marker] of state.markers) {
    if (!activeIds.has(id)) {
      state.map.removeLayer(marker);
      state.markers.delete(id);
    }
  }
}

// ── Animated Counter ────────────────────────────────────────────────────────

function animateCount(element, targetValue) {
  const current = parseInt(element.textContent.replace(/\D/g, "")) || 0;
  const target = targetValue;
  if (current === target) return;

  const duration = 300;
  const start = performance.now();

  function step(now) {
    const elapsed = now - start;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
    const value = Math.round(current + (target - current) * eased);
    element.textContent = formatNumber(value);
    if (progress < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

// ── Dashboard Updates ───────────────────────────────────────────────────────

function updateCounts(vehicles) {
  const counts = { car: 0, truck: 0, motor_bike: 0, bicycle: 0, foot: 0 };
  for (const v of vehicles) {
    if (counts[v.TYPE] !== undefined) {
      counts[v.TYPE]++;
    }
  }

  state.counts = counts;
  let total = 0;
  for (const type of VEHICLE_TYPES) {
    const el = document.getElementById(`count-${type}`);
    if (el) animateCount(el, counts[type]);
    total += counts[type];
  }
  animateCount(dom.totalVehicles, total);
}

function updateTimeline(currentStep, totalSteps) {
  state.timeline.currentStep = currentStep;
  if (totalSteps) state.timeline.totalSteps = totalSteps;

  const total = state.timeline.totalSteps;
  if (total > 0) {
    const pct = (currentStep / total) * 100;
    dom.timelineProgress.style.width = pct + "%";
    dom.timelineThumb.style.left = pct + "%";
  }
  dom.stepCounter.textContent = `Step ${formatNumber(currentStep)} / ${formatNumber(state.timeline.totalSteps)}`;
}

// ── WebSocket ───────────────────────────────────────────────────────────────

function connectWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsPort = window.location.port ? ":" + window.location.port : "";
  const wsUrl = `${protocol}//${window.location.hostname}${wsPort}/ws/traffic`;

  dom.wsStatusDot.classList.remove("connected");
  dom.wsStatusText.textContent = "Connecting...";

  state.ws = new WebSocket(wsUrl);

  state.ws.onopen = () => {
    dom.wsStatusDot.classList.add("connected");
    dom.wsStatusText.textContent = "Connected";
    state.reconnectDelay = 1000;

    // Fade out loading overlay after brief delay
    setTimeout(() => {
      const overlay = document.getElementById("loading-overlay");
      if (overlay) overlay.classList.add("hidden");
    }, 500);

    // Send current speed setting
    state.ws.send(JSON.stringify({ speed: state.speed }));
  };

  state.ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);

      // Server sends: {positions: [...], timestamp, step, total_steps, tick}
      if (data.positions) {
        updateMarkers(data.positions);
        updateCounts(data.positions);
      } else if (Array.isArray(data)) {
        updateMarkers(data);
        updateCounts(data);
      }

      if (data.timestamp) {
        dom.timestamp.textContent = formatTimestamp(data.timestamp);
      }
      if (data.step !== undefined) {
        updateTimeline(data.step, data.total_steps);
      }

      // Heatmap: use vehicle positions as heat points
      // Intensity 0.12 per vehicle — 3 overlapping = visible, 8+ = red
      if (state.heatmapVisible && data.positions) {
        const heatPoints = data.positions.map(function (v) {
          return [v.X, v.Y, 0.12];
        });
        state.heatmapLayer.setLatLngs(heatPoints);
      }

      // Anomaly alerts from WebSocket
      if (data.anomalies) {
        renderAlerts(data.anomalies);
      }

      // Traffic lights from WebSocket
      if (data.traffic_lights) {
        updateTrafficLights(data.traffic_lights);
      }

      // Stopped at red counter
      if (data.stopped !== undefined) {
        var stoppedEl = document.getElementById("stopped-count");
        var pctEl = document.getElementById("stopped-pct");
        var badgeEl = document.getElementById("gw-badge");
        var hintEl = document.getElementById("impact-hint");
        if (stoppedEl) {
          animateCount(stoppedEl, data.stopped);
          var pct = Math.round((data.stopped / 750) * 100);
          pctEl.textContent = pct + "% of vehicles";
        }
        if (badgeEl) {
          var gwOn = data.green_wave_active;
          badgeEl.textContent = gwOn ? "ON" : "OFF";
          badgeEl.className = "impact-badge" + (gwOn ? " active" : "");
        }
        if (hintEl) {
          hintEl.textContent = data.green_wave_active
            ? "Green Wave active — signals synchronized"
            : "Enable Green Wave in Analysis tab to compare";
        }
      }
    } catch (e) {
      console.error("WebSocket message parse error:", e);
    }
  };

  state.ws.onclose = () => {
    dom.wsStatusDot.classList.remove("connected");
    dom.wsStatusText.textContent = "Disconnected — Reconnecting...";

    // Exponential backoff reconnect
    setTimeout(connectWebSocket, state.reconnectDelay);
    state.reconnectDelay = Math.min(state.reconnectDelay * 1.5, 10000);
  };

  state.ws.onerror = () => {
    state.ws.close();
  };
}

function wsSend(msg) {
  if (state.ws && state.ws.readyState === WebSocket.OPEN) {
    state.ws.send(JSON.stringify(msg));
  }
}

// ── REST Fetches ────────────────────────────────────────────────────────────

async function fetchStats() {
  // Don't fetch historical totals — WebSocket provides live pool counts
  // Historical data (589K total) would flash before live counts (750) appear
}

async function fetchTimeline() {
  try {
    const res = await fetch("/api/timeline");
    if (!res.ok) return;
    const data = await res.json();
    state.timeline.totalSteps = data.total_steps || 0;
    state.timeline.currentStep = data.current_step || 0;
    const range = data.time_range || {};
    state.timeline.startTime = range.start || "";
    state.timeline.endTime = range.end || "";

    dom.timeStart.textContent = formatTimeShort(range.start);
    dom.timeEnd.textContent = formatTimeShort(range.end);
    updateTimeline(state.timeline.currentStep, state.timeline.totalSteps);
  } catch (e) {
    // Timeline endpoint may not be available yet
  }
}

async function fetchSensors() {
  try {
    const res = await fetch("/api/sensors");
    if (!res.ok) return;
    const sensors = await res.json();

    dom.activeSensors.textContent = formatNumber(sensors.length);

    for (const sensor of sensors) {
      const lat = sensor.lat || sensor.X;
      const lon = sensor.lon || sensor.Y;
      if (lat && lon) {
        const pulseIcon = L.divIcon({
          className: "sensor-pulse",
          iconSize: [12, 12],
          iconAnchor: [6, 6],
          html: '<div class="pulse-dot"></div><div class="pulse-ring"></div>',
        });
        const marker = L.marker([lat, lon], {
          icon: pulseIcon,
          interactive: false,
        }).addTo(state.map);
        state.sensorMarkers.push(marker);
      }
    }
  } catch (e) {
    // Sensors endpoint may not be available yet
  }
}

// ── Controls ────────────────────────────────────────────────────────────────

function initControls() {
  // Play/Pause
  dom.btnPause.addEventListener("click", () => {
    state.isPaused = !state.isPaused;
    dom.iconPause.style.display = state.isPaused ? "none" : "block";
    dom.iconPlay.style.display = state.isPaused ? "block" : "none";
    wsSend({ pause: state.isPaused });
  });

  // Speed buttons
  document.querySelectorAll(".speed-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document
        .querySelectorAll(".speed-btn")
        .forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.speed = parseInt(btn.dataset.speed, 10);
      wsSend({ speed: state.speed });
    });
  });

  // Timeline click-to-jump
  dom.timelineTrack.addEventListener("click", (e) => {
    const rect = dom.timelineTrack.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    const step = Math.round(pct * state.timeline.totalSteps);
    wsSend({ jump_to: step });
    updateTimeline(step, state.timeline.totalSteps);
  });
}

// ── Signal Analysis ──────────────────────────────────────────────────────────

async function fetchSignalAnalysis() {
  try {
    const [signalRes, corridorRes, summaryRes] = await Promise.all([
      fetch("/api/signals"),
      fetch("/api/corridors"),
      fetch("/api/city-summary"),
    ]);

    state.signalData = await signalRes.json();
    state.corridorData = await corridorRes.json();
    var summary = await summaryRes.json();

    renderCitySummary(summary);
  } catch (e) {
    console.error("Signal fetch failed:", e);
  }
}

function renderCitySummary(s) {
  var container = document.getElementById("summary-content");
  container.textContent = "";
  var grid = document.createElement("div");
  grid.className = "summary-grid";

  // Problem statement
  var problem = document.createElement("div");
  problem.className = "summary-problem";
  var pt = document.createElement("div");
  pt.className = "problem-title";
  pt.textContent = "THE PROBLEM";
  problem.appendChild(pt);
  var problems = [
    [
      s.pct_needs_adaptive + "%",
      "of intersections too unpredictable for fixed signals",
    ],
    [
      (s.peak_vs_offpeak_ratio || "2.0") + "x",
      "more traffic at peak vs off-peak",
    ],
    [
      s.coordination_pairs + "",
      "intersection pairs need green-wave coordination",
    ],
  ];
  problems.forEach(function (p) {
    var row = document.createElement("div");
    row.className = "problem-stat";
    var v = document.createElement("span");
    v.className = "problem-value";
    v.textContent = p[0];
    row.appendChild(v);
    row.appendChild(document.createTextNode(" " + p[1]));
    problem.appendChild(row);
  });
  container.appendChild(problem);

  // Solution impact
  var solution = document.createElement("div");
  solution.className = "summary-solution";
  var st = document.createElement("div");
  st.className = "solution-title";
  st.textContent = "ESTIMATED IMPACT";
  solution.appendChild(st);
  var impacts = [
    [
      formatNumber(s.estimated_daily_savings_hours || 977),
      "vehicle-hours saved daily",
    ],
    [s.peak_hour + " peak", formatNumber(s.peak_hour_volume) + " vehicles"],
  ];
  impacts.forEach(function (p) {
    var row = document.createElement("div");
    row.className = "problem-stat";
    var v = document.createElement("span");
    v.className = "solution-value";
    v.textContent = p[0];
    row.appendChild(v);
    row.appendChild(document.createTextNode(" " + p[1]));
    solution.appendChild(row);
  });
  container.appendChild(solution);

  // Key numbers grid
  var stats = [
    [s.total_sensors, "Sensors"],
    [formatNumber(s.total_readings), "Readings"],
    [s.peak_hour, "Peak Hour"],
    [s.coordination_pairs, "Green Waves"],
  ];
  stats.forEach(function (pair) {
    var stat = document.createElement("div");
    stat.className = "summary-stat";
    var val = document.createElement("span");
    val.className = "summary-value";
    val.textContent = pair[0];
    var lbl = document.createElement("span");
    lbl.className = "summary-label";
    lbl.textContent = pair[1];
    stat.appendChild(val);
    stat.appendChild(lbl);
    grid.appendChild(stat);
  });
  container.appendChild(grid);
}

function buildSparkBars(hourly) {
  var maxH = Math.max.apply(null, hourly.concat([1]));
  var container = document.createElement("div");
  container.style.cssText =
    "display:flex;align-items:flex-end;gap:1px;height:35px;margin-top:4px;";
  hourly.forEach(function (v, i) {
    var h = Math.max(1, (v / maxH) * 30);
    var isRush = i >= 16 && i <= 18;
    var bar = document.createElement("div");
    bar.style.cssText =
      "width:4px;height:" +
      h +
      "px;background:" +
      (isRush ? "#ef4444" : "#3b82f6") +
      ";border-radius:1px;";
    container.appendChild(bar);
  });
  return container;
}

function buildPopupContent(sid, data) {
  var cv = data.cv || 0;
  var wrap = document.createElement("div");
  wrap.style.cssText = "font-family:system-ui;min-width:220px;";

  var title = document.createElement("div");
  title.style.cssText = "font-weight:600;margin-bottom:4px;";
  title.textContent = "Sensor " + sid.slice(0, 12) + "...";
  wrap.appendChild(title);

  var badge = document.createElement("span");
  badge.style.cssText =
    "color:white;padding:2px 6px;border-radius:4px;font-size:10px;background:" +
    (data.needs_adaptive ? "#ef4444" : "#22c55e") +
    ";";
  badge.textContent = data.needs_adaptive ? "Needs Adaptive" : "Stable";
  wrap.appendChild(badge);

  var detail = document.createElement("div");
  detail.style.cssText = "margin-top:8px;font-size:11px;color:#666;";
  detail.textContent =
    "Variability: " + cv.toFixed(2) + " | Stoßzeit: " + data.peak_hour + ":00";
  wrap.appendChild(detail);

  var label = document.createElement("div");
  label.style.cssText = "margin-top:8px;font-size:10px;color:#888;";
  label.textContent = "Hourly Profile (red = rush hour)";
  wrap.appendChild(label);

  var hourly = data.hourly_profile || [];
  wrap.appendChild(buildSparkBars(hourly));

  return wrap;
}

function toggleAnalysis() {
  state.analysisVisible = !state.analysisVisible;
  document.getElementById("btn-analysis").classList.toggle("active");

  if (state.analysisVisible && state.signalData) {
    if (!state.analysisLayer) {
      state.analysisLayer = L.layerGroup();
      for (var sid in state.signalData) {
        if (!state.signalData.hasOwnProperty(sid)) continue;
        var data = state.signalData[sid];
        if (!data.lat || !data.lon) continue;
        var cv = data.cv || 0;
        var color = cv > 1.0 ? "#ef4444" : cv > 0.7 ? "#f59e0b" : "#22c55e";
        var radius = Math.max(6, Math.min(20, (data.daily_avg || 1) / 5));

        var circle = L.circleMarker([data.lat, data.lon], {
          radius: radius,
          color: color,
          fillColor: color,
          fillOpacity: 0.6,
          weight: 2,
        });

        circle.bindPopup(buildPopupContent(sid, data), { maxWidth: 280 });
        state.analysisLayer.addLayer(circle);
      }
    }
    state.analysisLayer.addTo(state.map);
    document.getElementById("signal-recommendations").style.display = "block";
    renderRecommendations();
  } else {
    if (state.analysisLayer) state.map.removeLayer(state.analysisLayer);
    document.getElementById("signal-recommendations").style.display = "none";
  }
}

function renderRecommendations() {
  if (!state.signalData) return;
  var entries = Object.entries(state.signalData)
    .filter(function (e) {
      return e[1].needs_adaptive;
    })
    .sort(function (a, b) {
      return (b[1].cv || 0) - (a[1].cv || 0);
    })
    .slice(0, 5);

  var container = document.getElementById("recs-list");
  container.textContent = "";
  entries.forEach(function (entry) {
    var sid = entry[0];
    var d = entry[1];
    var improvement = Math.min(30, Math.round((d.cv || 0) * 15));

    var card = document.createElement("div");
    card.className = "rec-card";

    var badgeEl = document.createElement("div");
    badgeEl.className = "rec-badge";
    badgeEl.textContent = "PROTOTYP";
    card.appendChild(badgeEl);

    var sensor = document.createElement("div");
    sensor.className = "rec-sensor";
    sensor.textContent = "Sensor " + sid.slice(0, 8) + "...";
    card.appendChild(sensor);

    var detail = document.createElement("div");
    detail.className = "rec-detail";
    detail.textContent =
      "CV: " + (d.cv || 0).toFixed(2) + " | Stoßzeit: " + d.peak_hour + ":00";
    card.appendChild(detail);

    var suggestion = document.createElement("div");
    suggestion.className = "rec-suggestion";
    suggestion.textContent = "Estimated Improvement: ~" + improvement + "%";
    card.appendChild(suggestion);

    container.appendChild(card);
  });
}

function buildCorridorPopup(corridor, idx) {
  var wrap = document.createElement("div");
  wrap.style.cssText = "font-family:system-ui;";

  var title = document.createElement("div");
  title.style.fontWeight = "600";
  title.textContent = "Green Wave #" + (idx + 1);
  wrap.appendChild(title);

  var info = document.createElement("div");
  info.style.cssText = "font-size:11px;margin-top:4px;";
  info.textContent =
    corridor.sensors.length +
    " intersections | " +
    corridor.total_length_m.toFixed(0) +
    "m";
  wrap.appendChild(info);

  var travel = document.createElement("div");
  travel.style.fontSize = "11px";
  travel.textContent =
    "Travel time: " + corridor.travel_time_sec.toFixed(1) + "s at 30 km/h";
  wrap.appendChild(travel);

  var offsets = corridor.sensors
    .map(function (s) {
      return s.offset_sec.toFixed(1) + "s";
    })
    .join(" \u2192 ");
  var offsetEl = document.createElement("div");
  offsetEl.style.cssText = "font-size:10px;color:#888;margin-top:4px;";
  offsetEl.textContent = "Signal offset: " + offsets;
  wrap.appendChild(offsetEl);

  var disclaimer = document.createElement("div");
  disclaimer.style.cssText =
    "font-size:9px;color:#aaa;margin-top:4px;font-style:italic;";
  disclaimer.textContent = "Modeled \u2014 based on 30 km/h assumption";
  wrap.appendChild(disclaimer);

  return wrap;
}

function toggleCorridors() {
  state.corridorsVisible = !state.corridorsVisible;
  document.getElementById("btn-corridors").classList.toggle("active");

  // Send green wave command to backend — actually syncs traffic light phases
  wsSend({ green_wave: state.corridorsVisible });

  if (state.corridorsVisible && state.corridorData) {
    if (!state.corridorLayer) {
      state.corridorLayer = L.layerGroup();
      var colors = [
        "#3b82f6",
        "#22c55e",
        "#f59e0b",
        "#a855f7",
        "#ef4444",
        "#06b6d4",
        "#ec4899",
        "#84cc16",
      ];

      state.corridorData.forEach(function (corridor, idx) {
        // Use road path if available, otherwise fall back to sensor positions
        var coords = (corridor.path || corridor.sensors).map(function (s) {
          return [s.lat, s.lon];
        });
        if (coords.length < 2) return;

        var color = colors[idx % colors.length];
        // Glow underlay for visibility
        var glow = L.polyline(coords, {
          color: color,
          weight: 10,
          opacity: 0.15,
          lineCap: "round",
        });
        state.corridorLayer.addLayer(glow);

        // Main dashed line
        var line = L.polyline(coords, {
          color: color,
          weight: 3,
          opacity: 0.9,
          dashArray: "8 6",
          className: "corridor-line-animated",
        });

        line.bindPopup(buildCorridorPopup(corridor, idx), { maxWidth: 300 });
        state.corridorLayer.addLayer(line);
      });
    }
    state.corridorLayer.addTo(state.map);
  } else {
    if (state.corridorLayer) state.map.removeLayer(state.corridorLayer);
  }
}

// ── Init ────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  initMap();
  initHeatmap();
  initControls();
  connectWebSocket();

  // Tab switching
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document
        .querySelectorAll(".tab-btn")
        .forEach((b) => b.classList.remove("active"));
      document
        .querySelectorAll(".tab-panel")
        .forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
    });
  });

  // Fetch initial data from REST endpoints
  fetchStats();
  fetchTimeline();
  fetchSensors();
  fetchIntelligence();
  generateQR();

  // Signal intelligence
  document
    .getElementById("btn-analysis")
    .addEventListener("click", toggleAnalysis);
  document
    .getElementById("btn-corridors")
    .addEventListener("click", toggleCorridors);
  fetchSignalAnalysis();
});
