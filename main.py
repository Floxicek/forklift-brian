"""
Brian robot control web app
============================

Simple Flask server that:
  * Serves the control web page (templates/index.html + static/app.js + static/style.css)
  * Drives each team's Brian device directly over its native motor REST API
    (no custom program needs to run on the device), so the browser never
    needs to talk cross-origin to the robots directly and the two device IP
    addresses live in one place (config.json).

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
# paying a fresh handshake on every single motor command -- meaningful
# overhead on Wi-Fi to a small embedded HTTP server.
_http = requests.Session()

APP_DIR = Path(__file__).parent
CONFIG_PATH = APP_DIR / "config.json"

app = Flask(__name__)

_config_lock = threading.Lock()

DEFAULT_CONFIG = {
    "red": {"ip": ""},
    "blue": {"ip": ""},
    "round_seconds": 30,
}

# Short timeouts so a dead/unreachable device never makes a key press feel
# laggy. Status polling can tolerate a slightly longer timeout than
# fire-and-forget motor commands.
STATUS_TIMEOUT = 2.0
MOTOR_TIMEOUT = 1.5
REGISTER_TIMEOUT = 3.0

TEAMS = ("red", "blue")

# Physical port wiring -- same on both robots. Adjust if a robot differs.
PORTS = {"left": "B", "right": "C", "fork": "A"}

SPEEDS_DEG_S = {"left": 720, "right": 720, "fork": 2020}

# Wheels brake for a crisp stop; the fork holds position instead so it
# doesn't sink under its own load once the key is released.
STOP_METHOD = {"left": "brake()", "right": "brake()", "fork": "hold()"}

MOTOR_COMMANDS = {
    "LEFT_FORWARD": ("left", "Forward"),
    "LEFT_BACKWARD": ("left", "Backward"),
    "LEFT_STOP": ("left", "Stop"),
    "RIGHT_FORWARD": ("right", "Forward"),
    "RIGHT_BACKWARD": ("right", "Backward"),
    "RIGHT_STOP": ("right", "Stop"),
    "FORK_FORWARD": ("fork", "Forward"),
    "FORK_BACKWARD": ("fork", "Backward"),
    "FORK_STOP": ("fork", "Stop"),
}

# How often the background loop wakes up, AND the window used to decide a
# role was "sent recently enough to skip." Both need to be this same value,
# and it must be well under half of DEVICE_HANDLER_EXPIRY_S: worst case, a
# real command lands just after one check, gets (correctly) treated as
# recent at the next check one interval later, and isn't re-sent until the
# check after *that* -- up to ~2x this interval after the real command. At
# 10s that worst case (~20s) blew past the device's 15s expiry, which is
# exactly why the handler was falling asleep after a burst of activity.
KEEPALIVE_INTERVAL = 5.0
DEVICE_HANDLER_EXPIRY_S = 15.0
assert 2 * KEEPALIVE_INTERVAL < DEVICE_HANDLER_EXPIRY_S

_motor_lock = threading.Lock()
_registered = {team: {role: False for role in PORTS} for team in TEAMS}
_last_command = {team: {role: None for role in PORTS} for team in TEAMS}
_last_sent_at = {team: {role: 0.0 for role in PORTS} for team in TEAMS}


def method_for(role, action):
    if action == "Stop":
        return STOP_METHOD[role]
    speed = SPEEDS_DEG_S[role] if action == "Forward" else -SPEEDS_DEG_S[role]
    return f"runAtSpeed({speed})"


def _has_handler(resp):
    # Both endpoints return {"probe": ..., "handler": ...|null} on success;
    # an error response has no "handler" key at all, so .get() reads as
    # None either way -- one check covers "device down", "no motor here",
    # and "call failed" without needing to branch on status code.
    try:
        return resp.json().get("handler") is not None
    except ValueError:
        return False


# Anything slower than this gets logged with a breakdown, so a slow command
# shows up as data (which call was slow, how slow) instead of just a vague
# "it feels slow" -- the two live hypotheses (device-side motor-readiness
# wait vs. Wi-Fi packet loss/retransmission) need real numbers to tell apart.
SLOW_CALL_LOG_THRESHOLD = 0.1


def _timed_post(url, **kwargs):
    start = time.monotonic()
    try:
        resp = _http.post(url, **kwargs)
        return resp, time.monotonic() - start, None
    except requests.RequestException as exc:
        return None, time.monotonic() - start, exc


def _try_register(base, port, label):
    resp, elapsed, exc = _timed_post(f"{base}/api/motor/{port}/autodetect", timeout=REGISTER_TIMEOUT)
    if elapsed > SLOW_CALL_LOG_THRESHOLD:
        print(f"[slow] {label} autodetect: {elapsed:.3f}s")
    if exc is not None:
        print(f"[unreachable] {label} autodetect: {exc}")
        return False
    return _has_handler(resp)


def _invoke(base, port, method, label):
    # Unlike registration, success here is just "the device took the
    # request" -- we don't re-check the handler field, since we don't
    # actually know it's guaranteed truthy after every Stop/brake() call,
    # and treating a false negative there as "re-register" would force a
    # slow autodetect round-trip before the next real command goes out.
    resp, elapsed, exc = _timed_post(
        f"{base}/api/motor/{port}",
        data=method,
        headers={"Content-Type": "text/plain"},
        timeout=MOTOR_TIMEOUT,
    )
    if elapsed > SLOW_CALL_LOG_THRESHOLD:
        print(f"[slow] {label} {method}: {elapsed:.3f}s")
    if exc is not None:
        print(f"[unreachable] {label} {method}: {exc}")
        return False
    return True


def ensure_handler(base, team, role):
    """Register the motor handler for a role if it isn't already, caching success."""
    with _motor_lock:
        if _registered[team][role]:
            return True
    label = f"{team}/{role}"
    ok = _try_register(base, PORTS[role], label)
    with _motor_lock:
        _registered[team][role] = ok
        if ok and _last_command[team][role] is None:
            _last_command[team][role] = STOP_METHOD[role]
    if ok:
        print(f"[connected] {label}: handler registered")
    return ok


def send_motor_command(team, role, action):
    ip = team_ip(team)
    if not ip:
        return False
    base = base_url(ip)
    if not ensure_handler(base, team, role):
        return False
    label = f"{team}/{role}"
    method = method_for(role, action)
    ok = _invoke(base, PORTS[role], method, label)
    with _motor_lock:
        if ok:
            _last_command[team][role] = method
            _last_sent_at[team][role] = time.monotonic()
        else:
            _registered[team][role] = False
    if not ok:
        print(f"[disconnected] {label}: lost while sending {method}")
    return ok


def keepalive_loop():
    while True:
        time.sleep(KEEPALIVE_INTERVAL)
        now = time.monotonic()
        for team in TEAMS:
            ip = team_ip(team)
            if not ip:
                continue
            base = base_url(ip)
            for role, port in PORTS.items():
                label = f"{team}/{role}"
                with _motor_lock:
                    registered = _registered[team][role]
                if not registered:
                    ensure_handler(base, team, role)
                    continue
                with _motor_lock:
                    method = _last_command[team][role]
                    sent_recently = (now - _last_sent_at[team][role]) < KEEPALIVE_INTERVAL
                # Real gameplay traffic already resets the device's 15s
                # handler-expiry clock -- sending a redundant keepalive on
                # top of that only adds background load during exactly the
                # moments the device is busiest.
                if sent_recently or not method:
                    continue
                if _invoke(base, port, method, label):
                    with _motor_lock:
                        _last_sent_at[team][role] = time.monotonic()
                else:
                    with _motor_lock:
                        _registered[team][role] = False
                    print(f"[disconnected] {label}: lost during keepalive")


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


@app.route("/api/motor/<team>", methods=["POST"])
def proxy_motor_command(team):
    team, err = _team_or_404(team)
    if err:
        return err

    body = (request.get_data(as_text=True) or "").strip()
    mapping = MOTOR_COMMANDS.get(body)
    if mapping is None:
        return jsonify({"error": f"unknown command {body!r}", "sent": body}), 400

    if not team_ip(team):
        return jsonify({"error": "no IP configured for this team", "online": False, "sent": body}), 503

    role, action = mapping
    ok = send_motor_command(team, role, action)
    if not ok:
        return jsonify({"ok": False, "online": False, "sent": body}), 502
    return jsonify({"ok": True, "sent": body})


threading.Thread(target=keepalive_loop, daemon=True).start()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)
