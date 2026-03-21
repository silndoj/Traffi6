// ── State ───────────────────────────────────────────────────────────────────

const state = {
  ws: null,
  map: null,
  markers: new Map(), // ID -> L.Marker
  sensorMarkers: [],
  isPaused: false,
  speed: 1,
  timeline: { totalSteps: 0, currentStep: 0, startTime: "", endTime: "" },
  reconnectDelay: 1000,
  counts: { car: 0, truck: 0, motor_bike: 0, bicycle: 0, foot: 0 },
};

const VEHICLE_TYPES = ["car", "truck", "motor_bike", "bicycle", "foot"];

// SVG icons — crisp at any size, colored per type, designed for dark map
const VEHICLE_SVGS = {
  car: (
    color,
  ) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
    <rect x="3" y="8" width="18" height="8" rx="3" fill="${color}" opacity="0.9"/>
    <rect x="5" y="5" width="14" height="6" rx="2" fill="${color}" opacity="0.7"/>
    <circle cx="7" cy="16" r="2" fill="#1a1d27" stroke="${color}" stroke-width="1"/>
    <circle cx="17" cy="16" r="2" fill="#1a1d27" stroke="${color}" stroke-width="1"/>
    <rect x="6" y="6" width="5" height="4" rx="1" fill="#1a1d27" opacity="0.5"/>
    <rect x="13" y="6" width="5" height="4" rx="1" fill="#1a1d27" opacity="0.5"/>
  </svg>`,
  truck: (
    color,
  ) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 28 24" width="28" height="24">
    <rect x="1" y="6" width="18" height="12" rx="2" fill="${color}" opacity="0.9"/>
    <rect x="19" y="9" width="8" height="9" rx="2" fill="${color}" opacity="0.7"/>
    <rect x="20" y="10" width="6" height="4" rx="1" fill="#1a1d27" opacity="0.5"/>
    <circle cx="6" cy="18" r="2.5" fill="#1a1d27" stroke="${color}" stroke-width="1"/>
    <circle cx="14" cy="18" r="2.5" fill="#1a1d27" stroke="${color}" stroke-width="1"/>
    <circle cx="24" cy="18" r="2.5" fill="#1a1d27" stroke="${color}" stroke-width="1"/>
  </svg>`,
  motor_bike: (
    color,
  ) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
    <circle cx="5" cy="16" r="3.5" fill="none" stroke="${color}" stroke-width="1.5" opacity="0.9"/>
    <circle cx="19" cy="16" r="3.5" fill="none" stroke="${color}" stroke-width="1.5" opacity="0.9"/>
    <path d="M7 14 L11 8 L15 8 L17 14" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round"/>
    <circle cx="12" cy="8" r="2" fill="${color}" opacity="0.8"/>
    <line x1="11" y1="8" x2="8" y2="14" stroke="${color}" stroke-width="1.5"/>
  </svg>`,
  bicycle: (
    color,
  ) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
    <circle cx="6" cy="16" r="4" fill="none" stroke="${color}" stroke-width="1.5" opacity="0.9"/>
    <circle cx="18" cy="16" r="4" fill="none" stroke="${color}" stroke-width="1.5" opacity="0.9"/>
    <path d="M6 16 L10 8 L14 16" fill="none" stroke="${color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
    <line x1="10" y1="8" x2="18" y2="16" stroke="${color}" stroke-width="1.5" stroke-linecap="round"/>
    <line x1="8" y1="8" x2="13" y2="8" stroke="${color}" stroke-width="1.5" stroke-linecap="round"/>
    <circle cx="10" cy="7" r="1.5" fill="${color}" opacity="0.6"/>
  </svg>`,
  foot: (
    color,
  ) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
    <circle cx="12" cy="4" r="3" fill="${color}" opacity="0.9"/>
    <line x1="12" y1="7" x2="12" y2="15" stroke="${color}" stroke-width="2" stroke-linecap="round"/>
    <line x1="12" y1="10" x2="8" y2="13" stroke="${color}" stroke-width="1.5" stroke-linecap="round"/>
    <line x1="12" y1="10" x2="16" y2="13" stroke="${color}" stroke-width="1.5" stroke-linecap="round"/>
    <line x1="12" y1="15" x2="9" y2="21" stroke="${color}" stroke-width="1.5" stroke-linecap="round"/>
    <line x1="12" y1="15" x2="15" y2="21" stroke="${color}" stroke-width="1.5" stroke-linecap="round"/>
  </svg>`,
};

const VEHICLE_COLORS = {
  car: "#3b82f6",
  truck: "#ef4444",
  motor_bike: "#f59e0b",
  bicycle: "#22c55e",
  foot: "#a855f7",
};

function svgToDataUri(svgString) {
  return "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svgString);
}

const ICON_CACHE = {};
VEHICLE_TYPES.forEach((type) => {
  const color = VEHICLE_COLORS[type] || "#ffffff";
  const svg = VEHICLE_SVGS[type](color);
  const size = type === "truck" ? [28, 24] : [24, 24];
  const anchor = type === "truck" ? [14, 12] : [12, 12];
  ICON_CACHE[type] = L.icon({
    iconUrl: svgToDataUri(svg),
    iconSize: size,
    iconAnchor: anchor,
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
  return Number(n).toLocaleString("de-DE");
}

function formatTimestamp(ts) {
  if (!ts) return "--";
  const d = new Date(ts);
  if (isNaN(d.getTime())) return ts;
  const day = d.getDate();
  const months = [
    "Jan",
    "Feb",
    "Mär",
    "Apr",
    "Mai",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Okt",
    "Nov",
    "Dez",
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
    "Mär",
    "Apr",
    "Mai",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Okt",
    "Nov",
    "Dez",
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
    if (el) el.textContent = formatNumber(counts[type]);
    total += counts[type];
  }
  dom.totalVehicles.textContent = formatNumber(total);
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
  const wsUrl = `${protocol}//${window.location.hostname}:8000/ws/traffic`;

  dom.wsStatusDot.classList.remove("connected");
  dom.wsStatusText.textContent = "Verbinde...";

  state.ws = new WebSocket(wsUrl);

  state.ws.onopen = () => {
    dom.wsStatusDot.classList.add("connected");
    dom.wsStatusText.textContent = "Verbunden";
    state.reconnectDelay = 1000;

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
    } catch (e) {
      console.error("WebSocket message parse error:", e);
    }
  };

  state.ws.onclose = () => {
    dom.wsStatusDot.classList.remove("connected");
    dom.wsStatusText.textContent = "Getrennt — Neuverbindung...";

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
  try {
    const res = await fetch("/api/stats");
    if (!res.ok) return;
    const data = await res.json();
    if (data.by_type) {
      for (const type of VEHICLE_TYPES) {
        const el = document.getElementById(`count-${type}`);
        if (el && data.by_type[type] !== undefined) {
          el.textContent = formatNumber(data.by_type[type]);
        }
      }
    }
    if (data.total !== undefined) {
      dom.totalVehicles.textContent = formatNumber(data.total);
    }
  } catch (e) {
    // Stats endpoint may not be available yet
  }
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
        const circle = L.circleMarker([lat, lon], {
          radius: 4,
          color: "#3b82f6",
          fillColor: "#3b82f6",
          fillOpacity: 0.4,
          weight: 1,
          interactive: false,
        }).addTo(state.map);
        state.sensorMarkers.push(circle);
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

// ── Init ────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  initMap();
  initControls();
  connectWebSocket();

  // Fetch initial data from REST endpoints
  fetchStats();
  fetchTimeline();
  fetchSensors();
});
