"""
Brian robot control web app
============================

Simple Flask server that:
  * Serves the control web page (templates/index.html + static/app.js + static/style.css)
  * Acts as a proxy between the browser and the two Brian devices (one per team),
    so the browser never needs to talk cross-origin to the robots directly and
    the two device IP addresses live in one place (config.json).

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
from pathlib import Path

import requests
from flask import Flask, jsonify, render_template, request

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
CONSOLE_TIMEOUT = 1.5


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
        resp = requests.get(f"{base_url(ip)}/api/status", timeout=STATUS_TIMEOUT)
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

    ip = team_ip(team)
    if not ip:
        return jsonify({"error": "no IP configured for this team", "online": False}), 503

    body = request.get_data(as_text=True) or ""

    try:
        resp = requests.post(
            f"{base_url(ip)}/api/program/console",
            data=body,
            headers={"Content-Type": "text/plain"},
            timeout=CONSOLE_TIMEOUT,
        )
        return jsonify({"ok": resp.ok, "status_code": resp.status_code, "sent": body})
    except requests.RequestException as exc:
        return jsonify({"error": str(exc), "online": False, "sent": body}), 502


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)
