// ── State ───────────────────────────────────────────────────────────────────

const state = {
  ws: null,
  map: null,
  markers: new Map(),
  isPaused: false,
  speed: 5,
  timeline: { totalSteps: 0, currentStep: 0, startTime: "", endTime: "" },
  reconnectDelay: 1000,
  heatmapLayer: null,
  heatmapVisible: false,
  corridorLayer: null,
  corridorData: null,
  heroRouteLayer: null,
  trafficLightMarkers: new Map(),
  trafficLightsVisible: true,
  greenWaveActive: false,
  baselineStopped: 0,
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
VEHICLE_TYPES.forEach(function (type) {
  var size = ICON_SIZES[type] || [26, 26];
  ICON_CACHE[type] = L.icon({
    iconUrl: "assets/" + type + ".png",
    iconSize: size,
    iconAnchor: [size[0] / 2, size[1] / 2],
  });
});

// Hero car: glowing special marker
ICON_CACHE["hero"] = L.divIcon({
  className: "hero-car-icon",
  iconSize: [28, 28],
  iconAnchor: [14, 14],
  html: '<div class="hero-car-dot"></div><div class="hero-car-ring"></div>',
});

// ── DOM Refs ────────────────────────────────────────────────────────────────

const dom = {
  timestamp: document.getElementById("current-timestamp"),
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
  var d = new Date(ts);
  if (isNaN(d.getTime())) return ts;
  var day = d.getDate();
  var months = [
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
  var month = months[d.getMonth()];
  var year = d.getFullYear();
  var hours = String(d.getHours()).padStart(2, "0");
  var mins = String(d.getMinutes()).padStart(2, "0");
  return day + " " + month + " " + year + ", " + hours + ":" + mins;
}

function formatTimeShort(ts) {
  if (!ts) return "--";
  var d = new Date(ts);
  if (isNaN(d.getTime())) return ts;
  var day = d.getDate();
  var months = [
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
  return day + " " + months[d.getMonth()] + " " + d.getFullYear();
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

  document.getElementById("btn-heatmap").addEventListener("click", function () {
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
  var container = document.getElementById("alert-list");
  if (!anomalies.length) {
    container.innerHTML = '<div class="no-alerts">No alerts</div>';
    return;
  }
  container.innerHTML = anomalies
    .slice(0, 3)
    .map(function (a) {
      var severityClass = a.severity > 3 ? "danger" : "warning";
      var typeLabel =
        a.type === "high_traffic" ? "High Traffic Volume" : a.type;
      var sensorLabel = "Sensor " + a.sensor_id.slice(0, 8) + "...";
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
    var res = await fetch("/api/intelligence");
    if (!res.ok) return;
    var data = await res.json();
    var container = document.getElementById("peak-hours");
    if (data.peak_hours) {
      container.innerHTML =
        '<div class="section-label">PEAK HOURS</div>' +
        data.peak_hours
          .slice(0, 3)
          .map(function (p) {
            return (
              '<div class="peak-item">' +
              '<span class="peak-hour">' +
              p.hour +
              "</span>" +
              '<span class="peak-count">' +
              formatNumber(Math.round(p.avg_vehicles)) +
              " veh.</span>" +
              "</div>"
            );
          })
          .join("");
    }
  } catch (e) {
    // Intelligence endpoint may not be available yet
  }
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
      var el = existing.getElement();
      if (el) {
        var dot = el.querySelector(".tl-dot");
        if (dot) dot.style.background = TL_COLORS[tl.state] || TL_COLORS.red;
      }
    } else {
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
  var activeIds = new Set();

  for (var i = 0; i < vehicles.length; i++) {
    var v = vehicles[i];
    var id = v.ID;
    activeIds.add(id);

    var existing = state.markers.get(id);
    if (existing) {
      existing.setLatLng([v.X, v.Y]);
      if (existing._vehicleType !== v.TYPE) {
        existing.setIcon(ICON_CACHE[v.TYPE] || ICON_CACHE.car);
        existing._vehicleType = v.TYPE;
      }
    } else {
      var marker = L.marker([v.X, v.Y], {
        icon: ICON_CACHE[v.TYPE] || ICON_CACHE.car,
        interactive: false,
      }).addTo(state.map);
      marker._vehicleType = v.TYPE;
      state.markers.set(id, marker);
    }
  }

  // Remove markers no longer present
  state.markers.forEach(function (marker, id) {
    if (!activeIds.has(id)) {
      state.map.removeLayer(marker);
      state.markers.delete(id);
    }
  });
}

// ── Animated Counter ────────────────────────────────────────────────────────

function animateCount(element, targetValue) {
  var current = parseInt(element.textContent.replace(/\D/g, "")) || 0;
  var target = targetValue;
  if (current === target) return;

  var duration = 300;
  var start = performance.now();

  function step(now) {
    var elapsed = now - start;
    var progress = Math.min(elapsed / duration, 1);
    var eased = 1 - Math.pow(1 - progress, 3);
    var value = Math.round(current + (target - current) * eased);
    element.textContent = formatNumber(value);
    if (progress < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

// ── Dashboard Updates ───────────────────────────────────────────────────────

function updateTimeline(currentStep, totalSteps) {
  state.timeline.currentStep = currentStep;
  if (totalSteps) state.timeline.totalSteps = totalSteps;

  var total = state.timeline.totalSteps;
  if (total > 0) {
    var pct = (currentStep / total) * 100;
    dom.timelineProgress.style.width = pct + "%";
    dom.timelineThumb.style.left = pct + "%";
  }
  dom.stepCounter.textContent =
    "Step " +
    formatNumber(currentStep) +
    " / " +
    formatNumber(state.timeline.totalSteps);
}

// ── WebSocket ───────────────────────────────────────────────────────────────

function connectWebSocket() {
  var protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  var wsPort = window.location.port ? ":" + window.location.port : "";
  var wsUrl =
    protocol + "//" + window.location.hostname + wsPort + "/ws/traffic";

  dom.wsStatusDot.classList.remove("connected");
  dom.wsStatusText.textContent = "Connecting...";

  state.ws = new WebSocket(wsUrl);

  state.ws.onopen = function () {
    dom.wsStatusDot.classList.add("connected");
    dom.wsStatusText.textContent = "Connected";
    state.reconnectDelay = 1000;

    // Fade out loading overlay after brief delay
    setTimeout(function () {
      var overlay = document.getElementById("loading-overlay");
      if (overlay) overlay.classList.add("hidden");
    }, 500);

    // Send current speed setting
    state.ws.send(JSON.stringify({ speed: state.speed }));
  };

  state.ws.onmessage = function (event) {
    try {
      var data = JSON.parse(event.data);

      if (data.positions) {
        updateMarkers(data.positions);
      } else if (Array.isArray(data)) {
        updateMarkers(data);
      }

      if (data.timestamp) {
        dom.timestamp.textContent = formatTimestamp(data.timestamp);
      }
      if (data.step !== undefined) {
        updateTimeline(data.step, data.total_steps);
      }

      // Heatmap
      if (state.heatmapVisible && data.positions) {
        var heatPoints = data.positions.map(function (v) {
          return [v.X, v.Y, 0.12];
        });
        state.heatmapLayer.setLatLngs(heatPoints);
      }

      // Anomaly alerts
      if (data.anomalies) {
        renderAlerts(data.anomalies);
      }

      // Traffic lights
      if (data.traffic_lights) {
        updateTrafficLights(data.traffic_lights);
      }

      // Hero route — rendered as a prominent green glowing line
      if (data.hero_route !== undefined) {
        if (state.heroRouteLayer) {
          state.map.removeLayer(state.heroRouteLayer);
          state.heroRouteLayer = null;
        }
        if (data.hero_route && data.hero_route.length >= 2) {
          state.heroRouteLayer = L.layerGroup();
          // Wide glow
          var glow = L.polyline(data.hero_route, {
            color: "#22c55e",
            weight: 14,
            opacity: 0.12,
            lineCap: "round",
          });
          state.heroRouteLayer.addLayer(glow);
          // Core line
          var core = L.polyline(data.hero_route, {
            color: "#22c55e",
            weight: 4,
            opacity: 0.7,
            lineCap: "round",
          });
          state.heroRouteLayer.addLayer(core);
          state.heroRouteLayer.addTo(state.map);
        }
      }

      // Stopped at red counter
      if (data.stopped !== undefined) {
        if (!state.greenWaveActive) {
          animateCount(document.getElementById("stopped-count"), data.stopped);
          var pct = Math.round((data.stopped / 750) * 100);
          document.getElementById("stopped-pct").textContent = pct + "%";
          state.baselineStopped = data.stopped;
        } else {
          // Update "after" count
          animateCount(
            document.getElementById("stopped-count-after"),
            data.stopped,
          );
          var pctAfter = Math.round((data.stopped / 750) * 100);
          document.getElementById("stopped-pct-after").textContent =
            pctAfter + "%";
          // Compute improvement
          if (state.baselineStopped > 0) {
            var improvementPct = Math.round(
              ((state.baselineStopped - data.stopped) / state.baselineStopped) *
                100,
            );
            document.getElementById("improvement-pct").textContent =
              improvementPct + "%";
          }
        }

        // Efficiency score: composite metric (0-100)
        // 100 = all moving, 0 = all stopped
        var movingPct = Math.round((1 - data.stopped / 750) * 100);
        var score = Math.max(0, Math.min(100, movingPct));
        var scoreEl = document.getElementById("efficiency-score");
        var barEl = document.getElementById("efficiency-bar-fill");
        var trendEl = document.getElementById("efficiency-trend");
        if (scoreEl) animateCount(scoreEl, score);
        if (barEl) {
          barEl.style.width = score + "%";
          barEl.style.background =
            score > 75
              ? "var(--color-bicycle)"
              : score > 50
                ? "var(--color-motor_bike)"
                : "var(--color-truck)";
        }
        if (trendEl && state.greenWaveActive && state.baselineStopped > 0) {
          var baseScore = Math.round((1 - state.baselineStopped / 750) * 100);
          var diff = score - baseScore;
          trendEl.textContent = (diff >= 0 ? "+" : "") + diff + "pts";
          trendEl.className =
            "efficiency-trend " + (diff > 0 ? "positive" : "negative");
        } else if (trendEl) {
          trendEl.textContent = "";
        }
      }
    } catch (e) {
      console.error("WebSocket message parse error:", e);
    }
  };

  state.ws.onclose = function () {
    dom.wsStatusDot.classList.remove("connected");
    dom.wsStatusText.textContent = "Disconnected — Reconnecting...";

    setTimeout(connectWebSocket, state.reconnectDelay);
    state.reconnectDelay = Math.min(state.reconnectDelay * 1.5, 10000);
  };

  state.ws.onerror = function () {
    state.ws.close();
  };
}

function wsSend(msg) {
  if (state.ws && state.ws.readyState === WebSocket.OPEN) {
    state.ws.send(JSON.stringify(msg));
  }
}

// ── REST Fetches ────────────────────────────────────────────────────────────

async function fetchTimeline() {
  try {
    var res = await fetch("/api/timeline");
    if (!res.ok) return;
    var data = await res.json();
    state.timeline.totalSteps = data.total_steps || 0;
    state.timeline.currentStep = data.current_step || 0;
    var range = data.time_range || {};
    state.timeline.startTime = range.start || "";
    state.timeline.endTime = range.end || "";

    dom.timeStart.textContent = formatTimeShort(range.start);
    dom.timeEnd.textContent = formatTimeShort(range.end);
    updateTimeline(state.timeline.currentStep, state.timeline.totalSteps);
  } catch (e) {
    // Timeline endpoint may not be available yet
  }
}

// ── Signal Analysis (corridors only) ────────────────────────────────────────

async function fetchSignalAnalysis() {
  try {
    var corridorRes = await fetch("/api/corridors");
    state.corridorData = await corridorRes.json();

    // Update corridor count badge
    var countEl = document.getElementById("corridor-count");
    var syncedEl = document.getElementById("corridors-synced");
    if (countEl && state.corridorData) {
      countEl.textContent = state.corridorData.length;
    }
    if (syncedEl && state.corridorData) {
      syncedEl.textContent = state.corridorData.length;
    }
  } catch (e) {
    // Corridor endpoint may not be available yet
  }
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

// ── Controls ────────────────────────────────────────────────────────────────

function initControls() {
  // Play/Pause
  dom.btnPause.addEventListener("click", function () {
    state.isPaused = !state.isPaused;
    dom.iconPause.style.display = state.isPaused ? "none" : "block";
    dom.iconPlay.style.display = state.isPaused ? "block" : "none";
    wsSend({ pause: state.isPaused });
  });

  // Speed buttons (both in sidebar header and controls bar)
  document.querySelectorAll(".speed-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      document.querySelectorAll(".speed-btn").forEach(function (b) {
        b.classList.remove("active");
      });
      // Activate all buttons with same speed value
      var speed = btn.dataset.speed;
      document
        .querySelectorAll('.speed-btn[data-speed="' + speed + '"]')
        .forEach(function (b) {
          b.classList.add("active");
        });
      state.speed = parseInt(speed, 10);
      wsSend({ speed: state.speed });
    });
  });

  // Timeline click-to-jump
  dom.timelineTrack.addEventListener("click", function (e) {
    var rect = dom.timelineTrack.getBoundingClientRect();
    var pct = (e.clientX - rect.left) / rect.width;
    var step = Math.round(pct * state.timeline.totalSteps);
    wsSend({ jump_to: step });
    updateTimeline(step, state.timeline.totalSteps);
  });

  // Hero button — Green Wave toggle
  document
    .getElementById("btn-green-wave")
    .addEventListener("click", function () {
      state.greenWaveActive = !state.greenWaveActive;
      this.classList.toggle("active");
      wsSend({ green_wave: state.greenWaveActive });

      // Show/hide impact section with animation
      var impactSection = document.getElementById("impact-section");
      impactSection.style.display = state.greenWaveActive ? "block" : "none";

      // Store baseline stopped count for comparison
      if (state.greenWaveActive) {
        state.baselineStopped =
          parseInt(
            document
              .getElementById("stopped-count")
              .textContent.replace(/\D/g, ""),
          ) || 0;
      }

      // Update button text
      this.querySelector(".hero-btn-title").textContent = state.greenWaveActive
        ? "DISABLE GREEN WAVE"
        : "ENABLE GREEN WAVE";
      this.querySelector(".hero-btn-icon").textContent = state.greenWaveActive
        ? "\u23F9"
        : "\u25B6";

      // Toggle corridor lines on map
      if (state.greenWaveActive && state.corridorData) {
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
            var coords = (corridor.path || corridor.sensors).map(function (s) {
              return [s.lat, s.lon];
            });
            if (coords.length < 2) return;

            var color = colors[idx % colors.length];
            var glow = L.polyline(coords, {
              color: color,
              weight: 10,
              opacity: 0.15,
              lineCap: "round",
            });
            state.corridorLayer.addLayer(glow);

            var line = L.polyline(coords, {
              color: color,
              weight: 3,
              opacity: 0.9,
              dashArray: "8 6",
              className: "corridor-line-animated",
            });

            line.bindPopup(buildCorridorPopup(corridor, idx), {
              maxWidth: 300,
            });
            state.corridorLayer.addLayer(line);
          });
        }
        state.corridorLayer.addTo(state.map);
      } else if (state.corridorLayer) {
        state.map.removeLayer(state.corridorLayer);
      }
    });
}

// ── Init ────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", function () {
  initMap();
  initHeatmap();
  initControls();
  connectWebSocket();

  fetchTimeline();
  fetchIntelligence();
  fetchSignalAnalysis();
});
