# PulseTraffic — Demo Script (3 minutes)

## Setup
```bash
cd app/backend && python3 server.py
```
Open http://localhost:8000 in Chrome (fullscreen, F11)

---

## ACT 1: The Living City (45 seconds)

**What to show:** Live tab — 750 vehicles driving on real Karlsruhe roads

**What to say:**
"This is PulseTraffic — a smart traffic signal optimization platform for Karlsruhe. What you're seeing is a real-time simulation of 750 vehicles driving on 3,914 actual road intersections from OpenStreetMap. The simulation is powered by 589,000 real IoT sensor readings from 50 traffic sensors collected over 6 days."

**Point out:**
- Vehicles moving along actual roads
- Traffic lights cycling green/yellow/red at intersections
- Vehicles stopping and queuing at red lights
- The "Stopped at Red" counter: "Right now, 160 vehicles — 21% — are stopped at red lights."
- Speed up to 10x briefly to show time progression

---

## ACT 2: The Problem (45 seconds)

**Click:** Analysis tab

**What to say:**
"Here's the problem we discovered. After analyzing all 589,000 sensor readings, we found that 86% of Karlsruhe's monitored intersections have traffic too unpredictable for fixed signal timing. Peak hour at 5pm sees 2x more traffic than off-peak — but the signals don't adapt."

**Point out:**
- "THE PROBLEM" card with real data stats
- Peak hours: 17:00 (241 vehicles), 16:00, 09:00
- Anomaly alerts if they're showing
- Click "Analysis" button to show colored intersection circles
- Click one circle to show the sparkline hourly profile

---

## ACT 3: The Solution — Green Wave (60 seconds)

**This is the hero moment.**

**Click:** "Green Wave" button

**What to say:**
"Our solution: Green Wave coordination. We identified 8 corridors where traffic lights can be synchronized to create green waves — timed so a driver hitting one green light hits all subsequent greens without stopping."

**Point out on the map:**
- Animated dashed corridor lines following real roads
- Click a corridor to show timing details

**Now switch to Live tab:**

**What to say:**
"Watch the Stopped at Red counter. Before Green Wave: 160 stopped, 21%. Now with Green Wave active..."

**The counter should drop to ~137, 18%.**

"13% fewer vehicles stopped — 977 vehicle-hours saved daily across the city."

---

## ACT 4: Mobile & Wrap-up (30 seconds)

**Click:** Mobile tab, show QR code

**What to say:**
"Citizens can scan this QR code to get a live traffic card on their phone — see congestion level, active alerts, and sensor status in real time."

**Click:** Heatmap toggle in Analysis tab

**What to say:**
"The heatmap shows where traffic concentrates. All of this is powered by real IoT sensor data — not simulated, not estimated. Real measurements from real roads."

**Final statement:**
"PulseTraffic: data-driven signal optimization that turns 589,000 sensor readings into actionable intelligence. 86% of intersections need adaptive timing. We have the proof, and the prototype to deliver it."
