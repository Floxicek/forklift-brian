# Brian Robot Control — Two-Team Game Console

A browser-based control panel for a live two-team robot game. Two teams
(Red, Blue) each drive their own Brian-firmware robot over Wi-Fi. Six
players total — three per team — each own one motor, and a shared round
timer periodically reshuffles which motor each player controls.

This document is the single source of truth for how the project works and
why it's built this way. Read this before making changes.

## Quick start

```bash
uv sync
uv run main.py
```

Open `http://localhost:5050` in a browser on the same network as both
Brian devices. Server port defaults to **5050** (overridable with
`PORT=<port> uv run main.py`) because macOS often has port 5000 taken by
AirPlay Receiver.

On first load, if no device IPs are configured yet, the settings panel
(gear icon, top right) opens automatically. Enter the Red and Blue Brian
device's IP address (or full URL) and the round length, click Save — these
persist to `config.json` so it's only needed once per venue.

## How the game works

- **Two teams, one Brian device each.** Every command generated on the Red
  side is sent only to the Red device; Blue-side keys only ever talk to the
  Blue device.
- **Six players, three motors per team.** Each team has a left drive motor,
  a right drive motor, and a forklift motor. Each of those 3 "seats" has a
  fixed pair of keyboard keys (forward / back) that **never changes**:

  | Team | Seat   | Forward | Back |
  |------|--------|---------|------|
  | Red  | Seat 1 | Q       | A    |
  | Red  | Seat 2 | W       | S    |
  | Red  | Seat 3 | E       | D    |
  | Blue | Seat 1 | U       | J    |
  | Blue | Seat 2 | I       | K    |
  | Blue | Seat 3 | O       | L    |

- **Role rotation every round.** A round timer counts down in the center of
  the screen (default 30s, configurable). When it hits zero: every motor on
  both devices gets stopped, the round counter increments, and *which motor*
  each seat controls rotates (Left → Right → Forklift → Left → …). The
  keys/seats themselves never move — only what they drive changes.
- **No on-screen role labels, on purpose.** The UI does not show which
  motor a seat currently controls. Figuring that out / communicating it
  within the team is intentionally part of the game.
- **Play / Reset toggle.** A pill button top-center starts idle, labeled
  "▶ PLAY", with all keys visually dimmed and totally inert (key presses are
  ignored, nothing is sent anywhere). Clicking it starts the round timer and
  arms the keys, and the button becomes "■ RESET" (red). Clicking it again
  stops all motors, resets the round counter to 1, resets role rotation back
  to the original assignment, and returns to the dimmed idle state — ready
  for another PLAY.
- **Status panels.** Each side shows battery %, charging state, SD card
  state, and Wi-Fi client count, or "offline" if the device doesn't respond.
  That team's `/api/status` is fetched once on page load and again whenever
  the settings panel is opened -- not on a recurring interval, since the
  Brian devices are busy enough handling motor console commands during play
  and don't need the extra polling traffic.

## Command protocol (browser → `main.py` → Brian console)

Holding a key sends **one** command on press, and the matching stop command
on release, as plain-text POST bodies to that team's `/api/console/<team>`
endpoint on `main.py`. This is edge-triggered, not repeated while held.

| Action                  | Command sent     |
|--------------------------|------------------|
| Left motor forward       | `LEFT_FORWARD`   |
| Left motor backward      | `LEFT_BACKWARD`  |
| Left motor stop          | `LEFT_STOP`      |
| Right motor forward      | `RIGHT_FORWARD`  |
| Right motor backward     | `RIGHT_BACKWARD` |
| Right motor stop         | `RIGHT_STOP`     |
| Forklift forward         | `FORK_FORWARD`   |
| Forklift backward        | `FORK_BACKWARD`  |
| Forklift stop            | `FORK_STOP`      |

The nine strings above are the complete vocabulary `commandFor()` in
`static/app.js` can produce. `main.py` validates the command (against
`VALID_COMMANDS`) and forwards it as-is, with a trailing `\n` appended
(`send_console_command()`), to that team's device at `POST
/api/program/console` — which feeds it to `brian-code/forklift.py`'s
`input()` loop, running as the device's program. **All motor-specific
logic (port wiring, speeds, Forward/Backward/Stop → `run_at_speed()` /
`brake()` / `hold()`, `set_wait_until_timeout_ms()`) lives entirely in
`forklift.py`, not `main.py`** — see that file for `PORTS` / motor speed
constants / stop method per role.

This requires `forklift.py` to actually be the program running on each
Brian device — `main.py` handles that itself, automatically: a background
watchdog thread (`deploy_watchdog_loop`, every `DEPLOY_CHECK_INTERVAL` =
10s) checks each configured team's `GET /api/program/status`, and if it
isn't `RUNNING` with `file` equal to `/forklift.py`, uploads the current
`brian-code/forklift.py` via `PUT /api/sd/forklift.py` and starts it via
`POST /api/program/run`. This covers the very first connection to a fresh
device, the program having crashed, or it never having been started —
without a manual upload step — but also means it will override *any* other
program already running on that device the first time it's pointed at
`main.py`, since this project's whole purpose for that device is running
forklift.py. Unlike the motor-REST-API variant (see below), there's no
separate registration/keepalive step needed once it's running, since a
program's console just stays available for as long as the program itself
is alive; there's no per-port Wi-Fi handler with its own expiry to defend
against.

Safety behavior: all 9 stop commands (3 roles per team, sent per-team) are
broadcast to both devices at every round rotation and whenever the browser
tab loses focus, so nothing is ever left spinning under a role it's no
longer assigned to.

### Alternative: driving motors via the native REST API instead

An earlier version of `main.py` (git commit "Using motor API") skipped
`forklift.py` entirely and drove each motor directly via the Brian's own
`/api/motor/{port}` endpoints from `main.py` itself — see that commit for
the full implementation (port/speed/stop-method tables in `main.py`,
`autodetect`-based handler registration, and a background keepalive thread
re-sending each motor's last instruction so its Wi-Fi handler doesn't
expire after 15s of silence). The two variants exist specifically to A/B
real-world latency between talking to a custom on-device program's console
vs. the firmware's own motor API directly; `git log`/`git show` that commit
to compare.

## Architecture

- **`main.py`** — Flask server. Serves the page and, per team (`red` /
  `blue`):
  - `GET /api/status/<team>` → proxies `GET {device}/api/status`
  - `POST /api/console/<team>` → validates one of the nine command strings
    above and forwards it to `POST {device}/api/program/console`, feeding
    `forklift.py`'s `input()` loop on the device (see "Command protocol"
    above)
  - `GET/POST /api/config` → read/write `config.json` (device IPs + round
    length)

  It also runs `deploy_watchdog_loop` in the background, which
  auto-uploads and starts `forklift.py` on any configured device that
  isn't already running it (see "Command protocol" above).

  Talking to the robots only through Flask means the browser never needs
  cross-origin requests (no CORS issues) and both device IPs live in one
  place.

- **`templates/index.html` + `static/style.css` + `static/app.js`** — the
  single-page UI: team panels, the 3×2 key grid per team, center timer +
  round counter, settings panel, play/reset button. All game logic (key
  binding → command, round timer, role rotation, status polling) lives in
  `app.js`.

- **`config.json`** — `{ "red": {"ip": ...}, "blue": {"ip": ...},
  "round_seconds": 30 }`. Editable live from the settings panel (no server
  restart needed) or by hand before starting.

- **`pyproject.toml` / `uv.lock`** — dependencies (`flask`, `requests`)
  managed via `uv`. Run with `uv sync` + `uv run main.py`.

- **`brian-code/`** — firmware-side Python that runs **on** a Brian device
  (a separate runtime from the Flask app above). `brian/` is the vendored
  Brian motor/sensor/runtime library, kept for reference/type-checking;
  `forklift.py` is the program that must actually be running on each
  device — it owns the `input()` loop, port wiring, speeds, and
  Forward/Backward/Stop → motor-method dispatch (see "Command protocol"
  above).

## Customization pointers

- Key bindings, motor roles, seat layout: `SEATS` / `ROLES` /
  `ROLE_LABELS` at the top of `static/app.js`.
- Command wording sent from the browser: `commandFor()` in
  `static/app.js`.
- Motor port wiring, speeds, stop method (brake vs. hold),
  `set_wait_until_timeout_ms()`: top of `brian-code/forklift.py`.
- Default round length / device IP defaults: `DEFAULT_CONFIG` in
  `main.py`, or `config.json` directly.
- Visual style (team colors, key size, centering, layout breakpoints):
  `static/style.css`.
- Server port default: `main.py`, bottom (`PORT` env var, default 5050).

## Design decisions worth knowing before changing things

- Motor commands are **edge-triggered**: one command on keydown, one Stop
  on keyup — never repeated while held. Don't add OS key-repeat handling;
  it's deliberately filtered out (`pressedKeys` set in `app.js`).
- Commands are queued client-side per **(team, role)**, not per team
  (`commandQueues` in `app.js`) — this guarantees Forward/Stop for the same
  motor can never arrive out of order, without forcing unrelated motors
  (e.g. two different seats on the same team) to wait on each other's
  round trip. Keying this queue by team alone was tried first and made
  simultaneous multi-player input feel needlessly slow.
- Role rotation state (`offsets` in `app.js`) is client-side only, not
  persisted, and resets on RESET — there is no server-side game state.
- The settings panel auto-opens on load only if a device IP is missing.
- Status/command timeouts are short on purpose (2s / 1.5s) so a
  dead/unreachable device never makes a key press feel laggy; a failed
  call returns HTTP 502/503 with `{"online": false}` and the UI shows
  "offline" rather than erroring.
- `main.py` reuses one `requests.Session()` (`_http`) for every call to a
  device instead of opening a fresh connection per request — connection
  setup on Wi-Fi to a small embedded HTTP server is real, avoidable
  overhead when it happens on every single command.
- `forklift.py` calls `set_wait_until_timeout_ms()` once at import: every
  `Motor` method (`run_at_speed`, `brake`, `hold`) otherwise waits
  indefinitely for the motor to report "ready," and a missing/mis-wired
  motor's first command would then block that whole `input()` loop (and
  the device's HTTP server along with it) forever, with no way to recover
  short of a reboot.
- `forklift.py` connects each motor **once at startup**, not lazily per
  command — retrying construction on every command for a genuinely
  missing/wrong-port motor was tried and stalled the whole device under
  load (autodetect can itself be slow). Its one `try`/`except` around the
  whole command loop (`MotorException` logs and keeps going;
  `KeyboardInterrupt` stops every connected motor and exits) replaced an
  earlier nested-try version for the same reason: fewer places for the
  two failure modes to interact unexpectedly.
- Calls slower than `SLOW_CALL_LOG_THRESHOLD` (0.1s, in `main.py`) print a
  `[slow] <team> console <command>: <seconds>s` line to the server
  console, and an outright failed call prints `[disconnected]`/
  `[connected]` on each state change — added specifically to turn "it got
  disconnected"-style reports into a timeline (which team, what the actual
  network exception was, when it recovered) instead of a guess.

## Appendix: Brian firmware REST API reference

The full API the Brian firmware exposes (only `/api/status` and the
`/api/program/console` endpoints are currently used by this project's
`main.py`; `/api/motor/*` is used by the alternative variant described
under "Command protocol" above; the rest is here for reference if this
project grows to use more of it, e.g. file management or sensors).

### File System Operations
- `GET /api/sd` — list contents of root directory. Returns JSON array of
  file/folder objects. Errors: 503, 404.
- `GET /api/sd/{path}` — get file content or directory listing.
  `Content-Type` header gives MIME type for files. Errors: 503, 404.
- `PUT /api/sd/{path}` — create/update file or folder. Body = file content
  (files) or empty (folders). Errors: 503, 400.
- `DELETE /api/sd/{path}` — delete file or folder. Errors: 503, 404.
- `PATCH /api/sd/{path}` — rename file or folder; body = new name. Errors:
  503, 400.

### Status
- `GET /api/status` → `{ batteryPct, charging, chargingSlow, sdCard,
  wifiStatus, wifiClients }`. `sdCard` ∈ MOUNTED, MOUNTED_USB,
  INSERTED_NOT_MOUNTED, UNMOUNTING, UNMOUNTED_NOT_REMOVED, IO_ERROR,
  IO_ERROR_UNMOUNTED_NOT_REMOVED, ERROR. `wifiStatus` ∈ OFF, ERR, AP, STA
  (currently only AP implemented). `wifiClients` 0–3 (UI shows a star above
  3). Errors: 500.

### Identity
- `GET /api/identity` → `{ hw, mac, fw, version }`.

### Settings
- `GET /api/settings` → key=value pairs, one per line (booleans/numbers
  parsed by the client). Errors: 500.
- `POST /api/settings` → body is key=value pairs, one per line, to update.
  Errors: 400, 500.
- Known keys: `lcdBrightness`, `audioVolume`, `menuClickSoundsEnabled`,
  `ledIntensity`, `ledEffectEnabled`, `ledEffectColor` (Brian color index
  0-7, R, G, B), `mscEnabled`, `mscNext`, `defaultProgramPath`,
  `shouldRunDefaultOnBoot`, `shouldRunDefaultOnCharger`, `dimAfterS`,
  `powerOffAfterM`, `shouldAutoPowerOffOnCharger`.

### Program
- `GET /api/program/status` → `{ status, killEnabled, file }`. `status` ∈
  NOT_STARTED, RUNNING, FINISHED, CRASHED, KILLED. Errors: 500.
- `POST /api/program/run` → body = file path to run. Errors: 400, 404, 500.
- `POST /api/program/interrupt` → sends SIGINT to the running program.
  Errors: 404, 500.
- `POST /api/program/kill` → sends SIGKILL. Errors: 404, 500.

### Console (used by this project)
- `GET /api/program/console/{fromLine}` → new console text since that
  line, or empty. `Console-Lines-Dropped` header = lines dropped on buffer
  overflow. Errors: 400 (no new lines), 404 (console unavailable), 500.
- `POST /api/program/console` → plain-text body is sent as user input to
  the running program's stdin. **This is what `main.py`'s
  `/api/console/<team>` proxies to**, carrying the nine command strings
  documented above. Errors: 404 (not running), 400 (invalid input), 500.

### Motor (not currently used — this project drives motors via console
input to a custom program instead, see above)
- `GET /api/motor/all` — probe + handler info for ports A–D.
- `GET /api/motor/{port}` — same, single port.
- `POST /api/motor/{port}/{handlerType}` — create a Wi-Fi handler
  (`autodetect`, `EV3LargeMotor`, `EV3MediumMotor`, `NXTMotor`).
- `POST /api/motor/{port}` — invoke a method, e.g. body `runAtSpeed(360)`.
- `DELETE /api/motor/{port}` — release the handler.

### Sensor (not currently used)
- `GET /api/sensor/all` — probe + handler info for ports 1–4.
- `GET /api/sensor/{port}` — same, single port.
- `POST /api/sensor/{port}/{handlerName}` — create a handler
  (`autodetect`, `ColorSensorEV3`, `GyroSensorEV3`, `UltrasonicSensorEV3`,
  `TouchSensorNXT`, etc.).
- `POST /api/sensor/{port}` — invoke a method, e.g. body
  `setMode(AMBIENT)`.
- `DELETE /api/sensor/{port}` — release the handler.

### Error codes
- `400` Bad Request — invalid file name / operation / file already exists.
- `404` Not Found — file/folder or path doesn't exist.
- `500` Internal Server Error — server-side error / operation failed.
- `503` Service Unavailable — SD card not mounted / SD card error / device
  busy.
