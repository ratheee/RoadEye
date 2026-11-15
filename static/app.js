// RoadEye frontend: polls detection status, shows alerts, plays warning beeps.

const $ = (id) => document.getElementById(id);

let soundOn = true;
let audioCtx = null;
let lastBeep = 0;
let settingsLoaded = false;

// ---------- Audio alerts (Web Audio API, no sound files needed) ----------
function beep(freq, duration) {
  if (!soundOn) return;
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = "square";
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration);
    osc.connect(gain).connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + duration);
  } catch (e) { /* audio blocked until user interacts with the page */ }
}

function soundAlert(level) {
  const now = performance.now();
  if (level === "danger" && now - lastBeep > 350) {
    beep(1200, 0.18);
    lastBeep = now;
  } else if (level === "warning" && now - lastBeep > 1200) {
    beep(700, 0.15);
    lastBeep = now;
  }
}

// ---------- Status polling ----------
const BANNER_TEXT = { safe: "ALL CLEAR", warning: "CAUTION", danger: "BRAKE! OBJECT TOO CLOSE" };

function render(s) {
  $("fps").textContent = s.fps;
  $("count").textContent = s.detections.length;
  $("source").textContent = s.source ?? "–";
  $("btn-pause").textContent = s.paused ? "Resume" : "Pause";

  const closest = s.detections[0];
  $("closest").textContent = closest ? `${closest.label} ${closest.distance_m} m` : "–";

  const banner = $("alert-banner");
  banner.className = "banner " + s.alert;
  banner.textContent = BANNER_TEXT[s.alert];
  document.querySelector(".video-wrap").classList.toggle("danger", s.alert === "danger");
  if (!s.paused) soundAlert(s.alert);

  $("det-body").innerHTML = s.detections.map((d) => `
    <tr class="${d.level}">
      <td><span class="dot ${d.level}"></span>${d.label}${d.in_zone ? "" : " <small>(side)</small>"}</td>
      <td>${d.distance_m} m</td>
      <td>${Math.round(d.confidence * 100)}%</td>
    </tr>`).join("") || `<tr><td colspan="3" style="color:var(--muted)">Nothing detected</td></tr>`;

  if (s.error) $("msg").textContent = s.error;
  if (!settingsLoaded) { loadSettings(s.settings); settingsLoaded = true; }
}

async function poll() {
  try {
    const res = await fetch("/api/status");
    render(await res.json());
  } catch (e) {
    $("msg").textContent = "Lost connection to server…";
  }
  setTimeout(poll, 200);
}

// ---------- Settings ----------
const SLIDERS = {
  danger_m: (v) => ($("v-danger").textContent = v),
  warning_m: (v) => ($("v-warning").textContent = v),
  confidence: (v) => ($("v-conf").textContent = v),
  zone_width: (v) => ($("v-zone").textContent = Math.round(v * 100)),
};

function loadSettings(settings) {
  for (const [key, show] of Object.entries(SLIDERS)) {
    $(key).value = settings[key];
    show(settings[key]);
  }
}

let settingsTimer;
for (const [key, show] of Object.entries(SLIDERS)) {
  $(key).addEventListener("input", (e) => {
    show(e.target.value);
    clearTimeout(settingsTimer);
    settingsTimer = setTimeout(async () => {
      const body = {};
      for (const k of Object.keys(SLIDERS)) body[k] = parseFloat($(k).value);
      const res = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      loadSettings(await res.json()); // server may clamp values
    }, 150);
  });
}

// ---------- Source controls ----------
function reloadFeed() {
  $("feed").src = "/video_feed?t=" + Date.now();
}

$("btn-cam").addEventListener("click", async () => {
  const source = $("cam-index").value || "0";
  $("msg").textContent = "Opening webcam " + source + "…";
  const res = await fetch("/api/source", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source }),
  });
  const data = await res.json();
  $("msg").textContent = data.ok ? "Webcam " + source + " active" : "Could not open webcam " + source;
  reloadFeed();
});

$("file").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  $("msg").textContent = "Uploading " + file.name + "…";
  const form = new FormData();
  form.append("video", file);
  const res = await fetch("/api/upload", { method: "POST", body: form });
  const data = await res.json();
  $("msg").textContent = data.ok ? "Playing " + data.source : (data.error || "Upload failed");
  e.target.value = "";
  reloadFeed();
});

$("btn-pause").addEventListener("click", () => fetch("/api/pause", { method: "POST" }));

$("btn-sound").addEventListener("click", (e) => {
  soundOn = !soundOn;
  e.target.textContent = "Sound: " + (soundOn ? "ON" : "OFF");
  e.target.classList.toggle("on", soundOn);
  if (soundOn) beep(900, 0.08); // also unlocks audio in the browser
});

// Browsers block audio until the user interacts once.
document.addEventListener("click", () => {
  audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
  if (audioCtx.state === "suspended") audioCtx.resume();
}, { once: true });

poll();
