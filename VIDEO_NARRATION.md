# PulseTraffic — 3-Minute Demo Video Narration

## Instructions
1. Start screen recording (OBS or QuickTime)
2. Open http://localhost:8000 in Chrome fullscreen (F11)
3. Play this audio narration while recording
4. Follow the action cues below

---

## NARRATION TEXT (for AI voice generation)

### [0:00 - 0:10] Opening
"What if we could make every driver in Karlsruhe hit green lights across the entire city? This is PulseTraffic."

**ACTION:** Page loads, loading screen fades to map

### [0:10 - 0:30] The Living City
"You're looking at seven hundred and fifty vehicles driving on real Karlsruhe roads. Every vehicle obeys traffic signals — stopping at red lights, queuing behind other cars, and resuming when the light turns green. This isn't a simulation pulled from thin air. It's powered by three hundred thousand real sensor readings from fifty traffic sensors across six days."

**ACTION:** Map is live, vehicles moving, let it run at 5x speed

### [0:30 - 0:55] The Problem
"But here's the problem. Look at the sidebar. Right now, one hundred and seventy vehicles — twenty-three percent — are stuck at red lights that don't adapt to real traffic. Our analysis of the sensor data proves that eighty-six percent of Karlsruhe's intersections have traffic too unpredictable for fixed signal timing. Peak hour at five PM sees twice the traffic of off-peak hours. But the signals never change."

**ACTION:** Point cursor at THE PROBLEM section and the stopped counter

### [0:55 - 1:05] The Moment
"So we built a solution. Watch what happens when we enable Green Wave."

**ACTION:** Move cursor to the ENABLE GREEN WAVE button. PAUSE for dramatic effect. Then CLICK it.

### [1:05 - 1:35] The Solution
"Green Wave synchronizes traffic lights along five corridors — each two to three kilometers of real Karlsruhe roads. See the glowing green line? That's our hero vehicle driving from Spassbecken in the south all the way to Heidesee in the northeast — and it's hitting every green light along the way."

**ACTION:** Let the hero car drive. Point at the green line on the map. Point at corridor lines.

### [1:35 - 1:55] The Impact
"Now look at the numbers. The stopped count dropped from one seventy to one forty-six. That's seventeen percent fewer vehicles waiting at red lights. The efficiency score went up. Across the entire city, that translates to nine hundred seventy-seven vehicle-hours saved every single day."

**ACTION:** Point at the stopped counter (should show lower number), point at efficiency score, point at the impact section that slid in

### [1:55 - 2:15] Heatmap
"We can also visualize where traffic concentrates."

**ACTION:** Click the Heatmap button in the footer. Let it render for 3 seconds.

"The blue areas are light traffic. Amber and red show where congestion builds. All of this updates in real time as vehicles move through the network."

### [2:15 - 2:30] Speed Demo
"And we can fast-forward through the entire six days of data."

**ACTION:** Click 50x speed. Let the timeline progress visibly. Watch vehicles move faster. Then click back to 5x.

"Watch how traffic patterns shift between morning, afternoon, and evening rush hours."

### [2:30 - 2:50] Summary
"Let me recap. Three hundred four thousand sensor readings prove the problem. Five green-wave corridors demonstrate the solution. Seventeen percent reduction in stopped vehicles, with real data, real roads, and a system ready to scale to every intersection in the city."

**ACTION:** Slow down, let the map settle at 5x

### [2:50 - 3:00] Closing
"This is PulseTraffic. Smart signal optimization for Karlsruhe."

**ACTION:** Pause playback. Hold on the final frame for 2 seconds.

---

## AI Voice Generation

Use one of these services to generate the narration audio:
1. **ElevenLabs** (best quality) — https://elevenlabs.io — "Adam" or "Antoni" voice, Stability 0.5, Clarity 0.7
2. **Google Cloud TTS** — Neural2 voices, en-US-Neural2-J (male) or en-US-Neural2-F (female)
3. **macOS** (free, decent) — `say -v Daniel -r 160 -o narration.aiff "text here"`

### Quick macOS generation:
```bash
say -v Daniel -r 155 -o narration.aiff "$(cat << 'EOF'
What if we could make every driver in Karlsruhe hit green lights across the entire city? This is PulseTraffic.

You're looking at seven hundred and fifty vehicles driving on real Karlsruhe roads. Every vehicle obeys traffic signals, stopping at red lights, queuing behind other cars, and resuming when the light turns green. This isn't a simulation pulled from thin air. It's powered by three hundred thousand real sensor readings from fifty traffic sensors across six days.

But here's the problem. Right now, one hundred and seventy vehicles, twenty-three percent, are stuck at red lights that don't adapt to real traffic. Our analysis proves that eighty-six percent of Karlsruhe's intersections have traffic too unpredictable for fixed signal timing.

So we built a solution. Watch what happens when we enable Green Wave.

Green Wave synchronizes traffic lights along five corridors, each two to three kilometers of real Karlsruhe roads. See the glowing green line? That's our hero vehicle driving from Spassbecken all the way to Heidesee, hitting every green light along the way.

Now look at the numbers. Seventeen percent fewer vehicles waiting at red lights. The efficiency score went up. Across the city, that's nine hundred seventy-seven vehicle-hours saved every single day.

We can also visualize where traffic concentrates. Blue areas are light traffic. Red shows congestion.

Three hundred four thousand sensor readings prove the problem. Five green-wave corridors demonstrate the solution. Seventeen percent reduction, with real data, real roads, and a system ready to scale.

This is PulseTraffic. Smart signal optimization for Karlsruhe.
EOF
)"
```
