// ── State ───────────────────────────────────────────────────────────────────

const state = {
  ws: null,
  map: null,
  markers: new Map(),       // ID -> L.Marker
  sensorMarkers: [],
  isPaused: false,
  speed: 1,
  timeline: { totalSteps: 0, currentStep: 0, startTime: '', endTime: '' },
  reconnectDelay: 1000,
  counts: { car: 0, truck: 0, motor_bike: 0, bicycle: 0, foot: 0 },
};

const VEHICLE_TYPES = ['car', 'truck', 'motor_bike', 'bicycle', 'foot'];

const ICON_CACHE = {};
VEHICLE_TYPES.forEach(type => {
  ICON_CACHE[type] = L.icon({
    iconUrl: `assets/${type}.png`,
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  });
});

// ── DOM Refs ────────────────────────────────────────────────────────────────

const dom = {
  timestamp: document.getElementById('current-timestamp'),
  totalVehicles: document.getElementById('total-vehicles'),
  activeSensors: document.getElementById('active-sensors'),
  wsStatusDot: document.getElementById('ws-status-dot'),
  wsStatusText: document.getElementById('ws-status-text'),
  btnPause: document.getElementById('btn-pause'),
  iconPause: document.getElementById('icon-pause'),
  iconPlay: document.getElementById('icon-play'),
  timelineProgress: document.getElementById('timeline-progress'),
  timelineThumb: document.getElementById('timeline-thumb'),
  timelineTrack: document.getElementById('timeline-track'),
  timeStart: document.getElementById('time-start'),
  timeEnd: document.getElementById('time-end'),
  stepCounter: document.getElementById('step-counter'),
};

// ── Formatting ──────────────────────────────────────────────────────────────

function formatNumber(n) {
  return Number(n).toLocaleString('de-DE');
}

function formatTimestamp(ts) {
  if (!ts) return '--';
  const d = new Date(ts);
  if (isNaN(d.getTime())) return ts;
  const day = d.getDate();
  const months = ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez'];
  const month = months[d.getMonth()];
  const year = d.getFullYear();
  const hours = String(d.getHours()).padStart(2, '0');
  const mins = String(d.getMinutes()).padStart(2, '0');
  return `${day} ${month} ${year}, ${hours}:${mins}`;
}

function formatTimeShort(ts) {
  if (!ts) return '--';
  const d = new Date(ts);
  if (isNaN(d.getTime())) return ts;
  const day = d.getDate();
  const months = ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez'];
  return `${day} ${months[d.getMonth()]} ${d.getFullYear()}`;
}

// ── Map Init ────────────────────────────────────────────────────────────────

function initMap() {
  state.map = L.map('map', {
    center: [49.00587, 8.40162],
    zoom: 14,
    zoomControl: true,
  });

  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
    subdomains: 'abcd',
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
    dom.timelineProgress.style.width = pct + '%';
    dom.timelineThumb.style.left = pct + '%';
  }
  dom.stepCounter.textContent = `Step ${formatNumber(currentStep)} / ${formatNumber(state.timeline.totalSteps)}`;
}

// ── WebSocket ───────────────────────────────────────────────────────────────

function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.hostname}:8000/ws/traffic`;

  dom.wsStatusDot.classList.remove('connected');
  dom.wsStatusText.textContent = 'Verbinde...';

  state.ws = new WebSocket(wsUrl);

  state.ws.onopen = () => {
    dom.wsStatusDot.classList.add('connected');
    dom.wsStatusText.textContent = 'Verbunden';
    state.reconnectDelay = 1000;

    // Send current speed setting
    state.ws.send(JSON.stringify({ speed: state.speed }));
  };

  state.ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);

      // Handle different message types
      if (Array.isArray(data)) {
        // Vehicle position array
        updateMarkers(data);
        updateCounts(data);
      } else if (data.type === 'state') {
        // State update with metadata
        if (data.vehicles) {
          updateMarkers(data.vehicles);
          updateCounts(data.vehicles);
        }
        if (data.timestamp) {
          dom.timestamp.textContent = formatTimestamp(data.timestamp);
        }
        if (data.current_step !== undefined) {
          updateTimeline(data.current_step, data.total_steps);
        }
      } else if (data.timestamp) {
        // Fallback: object with timestamp
        dom.timestamp.textContent = formatTimestamp(data.timestamp);
        if (data.current_step !== undefined) {
          updateTimeline(data.current_step, data.total_steps);
        }
      }
    } catch (e) {
      console.error('WebSocket message parse error:', e);
    }
  };

  state.ws.onclose = () => {
    dom.wsStatusDot.classList.remove('connected');
    dom.wsStatusText.textContent = 'Getrennt — Neuverbindung...';

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
    const res = await fetch('/api/stats');
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
    const res = await fetch('/api/timeline');
    if (!res.ok) return;
    const data = await res.json();
    state.timeline.totalSteps = data.total_steps || 0;
    state.timeline.currentStep = data.current_step || 0;
    state.timeline.startTime = data.start_time || '';
    state.timeline.endTime = data.end_time || '';

    dom.timeStart.textContent = formatTimeShort(data.start_time);
    dom.timeEnd.textContent = formatTimeShort(data.end_time);
    updateTimeline(state.timeline.currentStep, state.timeline.totalSteps);
  } catch (e) {
    // Timeline endpoint may not be available yet
  }
}

async function fetchSensors() {
  try {
    const res = await fetch('/api/sensors');
    if (!res.ok) return;
    const sensors = await res.json();

    dom.activeSensors.textContent = formatNumber(sensors.length);

    for (const sensor of sensors) {
      const lat = sensor.lat || sensor.X;
      const lon = sensor.lon || sensor.Y;
      if (lat && lon) {
        const circle = L.circleMarker([lat, lon], {
          radius: 4,
          color: '#3b82f6',
          fillColor: '#3b82f6',
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
  dom.btnPause.addEventListener('click', () => {
    state.isPaused = !state.isPaused;
    dom.iconPause.style.display = state.isPaused ? 'none' : 'block';
    dom.iconPlay.style.display = state.isPaused ? 'block' : 'none';
    wsSend({ pause: state.isPaused });
  });

  // Speed buttons
  document.querySelectorAll('.speed-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.speed-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.speed = parseInt(btn.dataset.speed, 10);
      wsSend({ speed: state.speed });
    });
  });

  // Timeline click-to-jump
  dom.timelineTrack.addEventListener('click', (e) => {
    const rect = dom.timelineTrack.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    const step = Math.round(pct * state.timeline.totalSteps);
    wsSend({ jump_to: step });
    updateTimeline(step, state.timeline.totalSteps);
  });
}

// ── Init ────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  initMap();
  initControls();
  connectWebSocket();

  // Fetch initial data from REST endpoints
  fetchStats();
  fetchTimeline();
  fetchSensors();
});
