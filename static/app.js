// Brian robot control -- client logic
// Handles: key bindings -> console commands, 30s role rotation, status polling.

const ROLES = ['left', 'right', 'fork'];
const ROLE_LABELS = { left: 'Left Motor', right: 'Right Motor', fork: 'Forklift' };

const SEATS = {
  red: [
    { fwd: 'Q', back: 'A' },
    { fwd: 'W', back: 'S' },
    { fwd: 'E', back: 'D' },
  ],
  blue: [
    { fwd: 'U', back: 'J' },
    { fwd: 'I', back: 'K' },
    { fwd: 'O', back: 'L' },
  ],
};

let roundSeconds = 30;
let remaining = roundSeconds;
let roundNumber = 1;
let gameRunning = false;
const offsets = { red: 0, blue: 0 };
const pressedKeys = new Set(); // keys currently held, e.g. 'Q'

function roleForSeat(team, seatIndex) {
  return ROLES[(seatIndex + offsets[team]) % ROLES.length];
}

function commandFor(role, dir) {
  // dir: 'Forward' | 'Backward' | 'Stop'  ->  e.g. "LEFT_FORWARD", "FORK_STOP"
  return `${role.toUpperCase()}_${dir.toUpperCase()}`;
}

function buildSeatsUI() {
  for (const team of ['red', 'blue']) {
    const container = document.getElementById(`seats-${team}`);
    container.innerHTML = '';
    SEATS[team].forEach((seat, idx) => {
      const seatDiv = document.createElement('div');
      seatDiv.className = 'seat';
      // No role label on purpose: which motor a seat currently drives is
      // for the team to figure out/communicate themselves, not shown on screen.
      seatDiv.innerHTML = `
        <div class="keys">
          <div class="key" id="key-${team}-${seat.fwd}" data-team="${team}" data-key="${seat.fwd}" data-dir="Forward" data-seat="${idx}">
            ${seat.fwd}<span class="key-sub">fwd</span>
          </div>
          <div class="key" id="key-${team}-${seat.back}" data-team="${team}" data-key="${seat.back}" data-dir="Backward" data-seat="${idx}">
            ${seat.back}<span class="key-sub">back</span>
          </div>
        </div>`;
      container.appendChild(seatDiv);
    });
  }
}

// Build reverse lookup: uppercase letter -> { team, seatIndex, dir }
const KEY_MAP = {};
for (const team of ['red', 'blue']) {
  SEATS[team].forEach((seat, idx) => {
    KEY_MAP[seat.fwd] = { team, seatIndex: idx, dir: 'Forward' };
    KEY_MAP[seat.back] = { team, seatIndex: idx, dir: 'Backward' };
  });
}

// Commands are queued per (team, role) -- not per team -- so Forward/Stop
// for the *same* motor can never race out of order, but two different
// motors (e.g. one seat driving, another running the forklift) fire fully
// concurrently instead of waiting on each other's round trip.
const commandQueues = {};
for (const team of ['red', 'blue']) {
  for (const role of ROLES) {
    commandQueues[`${team}_${role}`] = Promise.resolve();
  }
}

function sendCommand(team, role, text) {
  const key = `${team}_${role}`;
  commandQueues[key] = commandQueues[key].then(() =>
    fetch(`/api/console/${team}`, {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain' },
      body: text,
    }).catch(() => {})
  );
}

function isTypingTarget(el) {
  return el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA');
}

window.addEventListener('keydown', (e) => {
  if (isTypingTarget(document.activeElement)) return;
  const key = e.key.length === 1 ? e.key.toUpperCase() : e.key;
  const mapping = KEY_MAP[key];
  if (!mapping) return;
  if (!gameRunning) return; // controls are dead until the round is started
  e.preventDefault();
  if (pressedKeys.has(key)) return; // ignore OS auto-repeat while held
  pressedKeys.add(key);

  const role = roleForSeat(mapping.team, mapping.seatIndex);
  sendCommand(mapping.team, role, commandFor(role, mapping.dir));

  const keyEl = document.getElementById(`key-${mapping.team}-${key}`);
  if (keyEl) keyEl.classList.add('pressed');
});

window.addEventListener('keyup', (e) => {
  const key = e.key.length === 1 ? e.key.toUpperCase() : e.key;
  const mapping = KEY_MAP[key];
  if (!mapping) return;
  if (!pressedKeys.has(key)) return;
  pressedKeys.delete(key);

  const role = roleForSeat(mapping.team, mapping.seatIndex);
  sendCommand(mapping.team, role, commandFor(role, 'Stop'));

  const keyEl = document.getElementById(`key-${mapping.team}-${key}`);
  if (keyEl) keyEl.classList.remove('pressed');
});

// Safety net: if the browser window loses focus, release everything so a
// motor never keeps "running" because a keyup was missed. Both events are
// wired to the same handler -- `blur` isn't 100% reliable for OS-level
// alt-tab in every browser, `visibilitychange` covers tab/window hiding --
// so between the two, losing focus any way it can happen is covered.
function releaseAllKeys() {
  for (const key of Array.from(pressedKeys)) {
    const mapping = KEY_MAP[key];
    if (!mapping) continue;
    const role = roleForSeat(mapping.team, mapping.seatIndex);
    sendCommand(mapping.team, role, commandFor(role, 'Stop'));
    const keyEl = document.getElementById(`key-${mapping.team}-${key}`);
    if (keyEl) keyEl.classList.remove('pressed');
  }
  pressedKeys.clear();
}

window.addEventListener('blur', releaseAllKeys);
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') releaseAllKeys();
});

// ---- Timer / role rotation ----
const timerEl = document.getElementById('timer');
const roundNumberEl = document.getElementById('roundNumber');
const rotateFlashEl = document.getElementById('rotateFlash');

function renderTimer() {
  timerEl.textContent = remaining;
  timerEl.classList.toggle('warning', remaining <= 10 && remaining > 5);
  timerEl.classList.toggle('critical', remaining <= 5);
}

function stopAllMotors() {
  for (const team of ['red', 'blue']) {
    for (const role of ROLES) {
      sendCommand(team, role, commandFor(role, 'Stop'));
    }
  }
}

function rotateRoles() {
  offsets.red = (offsets.red + 1) % ROLES.length;
  offsets.blue = (offsets.blue + 1) % ROLES.length;
  // Roles aren't displayed on screen — teams have to track/communicate
  // amongst themselves which seat now drives which motor.
  roundNumber += 1;
  roundNumberEl.textContent = roundNumber;

  rotateFlashEl.classList.add('show');
  setTimeout(() => rotateFlashEl.classList.remove('show'), 1200);
}

function tick() {
  remaining -= 1;
  if (remaining <= 0) {
    // Stop every motor before handing roles to new operators, so nothing
    // keeps running under a role/key it's no longer assigned to.
    stopAllMotors();
    pressedKeys.clear();
    document.querySelectorAll('.key.pressed').forEach((el) => el.classList.remove('pressed'));
    rotateRoles();
    remaining = roundSeconds;
  }
  renderTimer();
}

let timerInterval = null;
function startTimer() {
  if (timerInterval) clearInterval(timerInterval);
  timerInterval = setInterval(tick, 1000);
}

// ---- Play / reset toggle ----
const playButton = document.getElementById('playButton');
const boardEl = document.getElementById('board');

function setRunningUI(running) {
  boardEl.classList.toggle('not-started', !running);
  playButton.classList.toggle('state-play', !running);
  playButton.classList.toggle('state-reset', running);
  playButton.textContent = running ? '■ RESET' : '▶ PLAY';
}

function startGame() {
  gameRunning = true;
  setRunningUI(true);
  startTimer();
}

function resetGame() {
  gameRunning = false;
  if (timerInterval) clearInterval(timerInterval);
  timerInterval = null;

  stopAllMotors();
  pressedKeys.clear();
  document.querySelectorAll('.key.pressed').forEach((el) => el.classList.remove('pressed'));

  offsets.red = 0;
  offsets.blue = 0;
  roundNumber = 1;
  roundNumberEl.textContent = roundNumber;
  remaining = roundSeconds;
  renderTimer();

  setRunningUI(false);
}

playButton.addEventListener('click', () => {
  if (gameRunning) {
    resetGame();
  } else {
    startGame();
  }
});

// ---- Status polling ----
function renderStatus(team, data, ok) {
  const dot = document.getElementById(`dot-${team}`);
  const text = document.getElementById(`status-text-${team}`);
  if (!ok) {
    dot.className = 'status-dot offline';
    text.textContent = 'offline';
    return;
  }
  dot.className = 'status-dot online';
  const battery = typeof data.batteryPct === 'number' ? `${data.batteryPct}%` : '—';
  const charge = data.charging ? (data.chargingSlow ? ' (slow charge)' : ' (charging)') : '';
  const sd = data.sdCard || '—';
  const wifiClients = typeof data.wifiClients === 'number' ? data.wifiClients : '—';
  text.textContent = `Batt ${battery}${charge} · SD ${sd} · WiFi clients ${wifiClients}`;
}

async function pollStatus(team) {
  try {
    const resp = await fetch(`/api/status/${team}`);
    const data = await resp.json();
    renderStatus(team, data, resp.ok && data.online !== false);
  } catch (e) {
    renderStatus(team, null, false);
  }
}

// Status is polled on a slow 5s interval, not more often -- the Brian
// devices are busy enough handling motor console commands during play, and
// battery/SD/Wi-Fi info doesn't need to be any fresher than that.
function startStatusPolling() {
  pollStatus('red');
  pollStatus('blue');
  setInterval(() => {
    pollStatus('red');
    pollStatus('blue');
  }, 5000);
}

// ---- Settings panel ----
const settingsToggle = document.getElementById('settingsToggle');
const settingsPanel = document.getElementById('settingsPanel');
const redIpInput = document.getElementById('redIpInput');
const blueIpInput = document.getElementById('blueIpInput');
const roundSecondsInput = document.getElementById('roundSecondsInput');
const saveSettingsBtn = document.getElementById('saveSettings');
const settingsMsg = document.getElementById('settingsMsg');

settingsToggle.addEventListener('click', () => {
  settingsPanel.classList.toggle('hidden');
});

async function loadConfig() {
  try {
    const resp = await fetch('/api/config');
    const cfg = await resp.json();
    redIpInput.value = (cfg.red && cfg.red.ip) || '';
    blueIpInput.value = (cfg.blue && cfg.blue.ip) || '';
    roundSeconds = cfg.round_seconds || 30;
    remaining = roundSeconds;
    roundSecondsInput.value = roundSeconds;
    renderTimer();
    const missingIp = !(cfg.red && cfg.red.ip) || !(cfg.blue && cfg.blue.ip);
    if (missingIp) {
      settingsPanel.classList.remove('hidden');
    }
  } catch (e) {
    settingsMsg.textContent = 'Could not load config from server.';
  }
}

saveSettingsBtn.addEventListener('click', async () => {
  try {
    const resp = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        red_ip: redIpInput.value.trim(),
        blue_ip: blueIpInput.value.trim(),
        round_seconds: parseInt(roundSecondsInput.value, 10) || 30,
      }),
    });
    const cfg = await resp.json();
    roundSeconds = cfg.round_seconds || 30;
    remaining = roundSeconds;
    renderTimer();
    settingsMsg.textContent = 'Saved.';
    setTimeout(() => { settingsMsg.textContent = ''; }, 2000);
  } catch (e) {
    settingsMsg.textContent = 'Failed to save.';
  }
});

// ---- Init ----
buildSeatsUI();
renderTimer();
setRunningUI(false);
loadConfig().then(() => {
  startStatusPolling();
});
