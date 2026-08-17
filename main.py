"""
Brian robot control web app
============================

Simple Flask server that:
  * Serves the control web page (templates/index.html + static/app.js + static/style.css)
  * Proxies motor commands from the browser to each team's Brian device's
    running console program (brian-code/forklift.py), so the browser never
    needs to talk cross-origin to the robots directly and the two device IP
    addresses live in one place (config.json).

This is the console/custom-program variant, kept alongside the motor-REST-API
variant (see git history, commit "Using motor API") specifically to compare
real-world latency between the two approaches -- same HTTP-client fixes
(session reuse, timing/connection logging) apply to both, only the transport
to the device differs.

Run (with uv):
    uv sync
    uv run main.py

Then open http://localhost:5050 in a browser on the same network as the two
Brian devices, and set the Red/Blue device IP addresses in the settings panel
(or edit config.json directly before starting).

By default the server listens on port 5050 (macOS often has port 5000 taken
by AirPlay Receiver). Override with the PORT environment variable, e.g.:
    PORT=8080 uv run main.py
"""

import json
import os
import threading
import time
from pathlib import Path

import requests
from flask import Flask, jsonify, render_template, request

# A shared session reuses TCP connections per host (keep-alive) instead of
# paying a fresh handshake on every single command -- meaningful overhead on
# Wi-Fi to a small embedded HTTP server.
_http = requests.Session()

APP_DIR = Path(__file__).parent
CONFIG_PATH = APP_DIR / "config.json"
FORKLIFT_SOURCE = APP_DIR / "brian-code" / "forklift.py"

# Path forklift.py is uploaded to and run from on the device's SD card.
# GET /api/program/status's "file" field and POST /api/program/run's body
# both use the leading-slash form; PUT /api/sd/{path} does not.
PROGRAM_RUN_PATH = "/forklift.py"
PROGRAM_SD_PATH = "forklift.py"

app = Flask(__name__)

_config_lock = threading.Lock()

DEFAULT_CONFIG = {
    "red": {"ip": ""},
    "blue": {"ip": ""},
    "round_seconds": 30,
}

# Short timeouts so a dead/unreachable device never makes a key press feel
# laggy. Status polling can tolerate a slightly longer timeout than
# fire-and-forget console commands. Uploading the program file and starting
# it are rarer, one-off operations, so they get more slack.
STATUS_TIMEOUT = 2.0
COMMAND_TIMEOUT = 1.5
DEPLOY_TIMEOUT = 5.0

# How often the background watchdog checks whether each configured device
# is actually running forklift.py, and (re)deploys it if not -- covers the
# first-ever connection to a fresh device as well as the program having
# crashed or never been started, without needing a manual upload step.
DEPLOY_CHECK_INTERVAL = 10.0

TEAMS = ("red", "blue")

# The complete command vocabulary -- forklift.py on the device owns port
# wiring, speeds, and Forward/Backward/Stop -> motor-method translation
# entirely; main.py here only validates and forwards the text.
VALID_COMMANDS = frozenset({
    "LEFT_FORWARD", "LEFT_BACKWARD", "LEFT_STOP",
    "RIGHT_FORWARD", "RIGHT_BACKWARD", "RIGHT_STOP",
    "FORK_FORWARD", "FORK_BACKWARD", "FORK_STOP",
})

# Anything slower than this gets logged with a breakdown, so a slow command
# shows up as data instead of just a vague "it feels slow".
SLOW_CALL_LOG_THRESHOLD = 0.1

_conn_lock = threading.Lock()
# Assume online until proven otherwise, so the very first command to a team
# doesn't print a spurious "disconnected" before we've ever heard from it.
_team_online = {team: True for team in TEAMS}


def _timed_post(url, **kwargs):
    start = time.monotonic()
    try:
        resp = _http.post(url, **kwargs)
        return resp, time.monotonic() - start, None
    except requests.RequestException as exc:
        return None, time.monotonic() - start, exc


def send_console_command(team, base, command):
    # input() on the Brian side only returns once it sees a newline -- the
    # console POST body needs one appended, the device doesn't add it.
    resp, elapsed, exc = _timed_post(
        f"{base}/api/program/console",
        data=command + "\n",
        headers={"Content-Type": "text/plain"},
        timeout=COMMAND_TIMEOUT,
    )
    if elapsed > SLOW_CALL_LOG_THRESHOLD:
        print(f"[slow] {team} console {command}: {elapsed:.3f}s")

    ok = exc is None
    with _conn_lock:
        was_online = _team_online[team]
        _team_online[team] = ok
    if ok and not was_online:
        print(f"[connected] {team}: console reachable again")
    elif not ok and was_online:
        print(f"[disconnected] {team}: {exc}")

    return ok, resp


def _is_forklift_running(base):
    try:
        resp = _http.get(f"{base}/api/program/status", timeout=STATUS_TIMEOUT)
        resp.raise_for_status()
        info = resp.json()
    except (requests.RequestException, ValueError):
        return None  # unreachable/unparseable -- distinct from "reachable but not running"
    if info.get("status") != "RUNNING":
        return False
    # Compare by basename, not exact string -- we don't actually know
    # whether the device reports "file" with or without a leading slash
    # (or some other path form), and a false mismatch here would make the
    # watchdog repeatedly try to (re-)run an already-running program, which
    # the firmware correctly rejects with 400 instead of being a no-op.
    file = (info.get("file") or "").rstrip("/").split("/")[-1]
    return file == PROGRAM_SD_PATH


def deploy_forklift(team, base):
    """Upload brian-code/forklift.py to the device's SD card and start it."""
    try:
        source = FORKLIFT_SOURCE.read_bytes()
        put_resp = _http.put(
            f"{base}/api/sd/{PROGRAM_SD_PATH}",
            data=source,
            headers={"Content-Type": "text/plain"},
            timeout=DEPLOY_TIMEOUT,
        )
        put_resp.raise_for_status()
        run_resp = _http.post(
            f"{base}/api/program/run",
            data=PROGRAM_RUN_PATH,
            timeout=DEPLOY_TIMEOUT,
        )
        run_resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"[deploy] {team}: failed to upload/start {PROGRAM_RUN_PATH}: {exc}")
        return False
    print(f"[deploy] {team}: {PROGRAM_RUN_PATH} uploaded and running")
    return True


def deploy_watchdog_loop():
    while True:
        for team in TEAMS:
            ip = team_ip(team)
            if not ip:
                continue
            base = base_url(ip)
            running = _is_forklift_running(base)
            if running is False:
                deploy_forklift(team, base)
            # running is None (device unreachable right now) -- nothing to
            # do, next tick will check again; running is True -- nothing to do.
        time.sleep(DEPLOY_CHECK_INTERVAL)


def load_config():
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r") as f:
                data = json.load(f)
            merged = dict(DEFAULT_CONFIG)
            merged.update(data)
            merged["red"] = {**DEFAULT_CONFIG["red"], **data.get("red", {})}
            merged["blue"] = {**DEFAULT_CONFIG["blue"], **data.get("blue", {})}
            return merged
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULT_CONFIG)


def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


_config = load_config()


def team_ip(team):
    with _config_lock:
        team_cfg = _config.get(team)
    if not team_cfg:
        return None
    ip = team_cfg.get("ip", "").strip()
    return ip or None


def base_url(ip):
    # Allow the user to type either "192.168.1.101" or a full URL.
    if ip.startswith("http://") or ip.startswith("https://"):
        return ip.rstrip("/")
    return f"http://{ip}"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/config", methods=["GET"])
def get_config():
    with _config_lock:
        return jsonify(_config)


@app.route("/api/config", methods=["POST"])
def update_config():
    payload = request.get_json(force=True, silent=True) or {}
    with _config_lock:
        if "red_ip" in payload:
            _config["red"]["ip"] = (payload.get("red_ip") or "").strip()
        if "blue_ip" in payload:
            _config["blue"]["ip"] = (payload.get("blue_ip") or "").strip()
        if "round_seconds" in payload:
            try:
                _config["round_seconds"] = max(5, int(payload["round_seconds"]))
            except (TypeError, ValueError):
                pass
        save_config(_config)
        return jsonify(_config)


def _team_or_404(team):
    if team not in ("red", "blue"):
        return None, (jsonify({"error": f"unknown team '{team}'"}), 404)
    return team, None


@app.route("/api/status/<team>", methods=["GET"])
def proxy_status(team):
    team, err = _team_or_404(team)
    if err:
        return err

    ip = team_ip(team)
    if not ip:
        return jsonify({"error": "no IP configured for this team", "online": False}), 503

    try:
        resp = _http.get(f"{base_url(ip)}/api/status", timeout=STATUS_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        data["online"] = True
        return jsonify(data)
    except requests.RequestException as exc:
        return jsonify({"error": str(exc), "online": False}), 502


@app.route("/api/console/<team>", methods=["POST"])
def proxy_console(team):
    team, err = _team_or_404(team)
    if err:
        return err

    body = (request.get_data(as_text=True) or "").strip()
    if body not in VALID_COMMANDS:
        return jsonify({"error": f"unknown command {body!r}", "sent": body}), 400

    ip = team_ip(team)
    if not ip:
        return jsonify({"error": "no IP configured for this team", "online": False, "sent": body}), 503

    ok, resp = send_console_command(team, base_url(ip), body)
    if not ok:
        return jsonify({"ok": False, "online": False, "sent": body}), 502
    return jsonify({"ok": True, "status_code": resp.status_code, "sent": body})


threading.Thread(target=deploy_watchdog_loop, daemon=True).start()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)
