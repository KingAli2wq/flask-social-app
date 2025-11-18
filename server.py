import base64
import json
import os
import time
from collections import defaultdict
from threading import Lock
from typing import Optional

from flask import Flask, jsonify, request, send_from_directory, abort
from flask_cors import CORS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "server_data")
os.makedirs(DATA_DIR, exist_ok=True)

FILES = {
    "users": os.path.join(DATA_DIR, "users.json"),
    "posts": os.path.join(DATA_DIR, "posts.json"),
    "messages": os.path.join(DATA_DIR, "messages.json"),
    "stories": os.path.join(DATA_DIR, "stories.json"),
    "videos": os.path.join(DATA_DIR, "videos.json"),
    "scheduled_posts": os.path.join(DATA_DIR, "scheduled_posts.json"),
    "notifications": os.path.join(DATA_DIR, "notifications.json"),
    "group_chats": os.path.join(DATA_DIR, "group_chats.json"),
}

MEDIA_ROOT = os.path.join(BASE_DIR, "media")
PROFILE_PICS_ROOT = os.path.join(BASE_DIR, "Profile Pictures")
os.makedirs(MEDIA_ROOT, exist_ok=True)
os.makedirs(PROFILE_PICS_ROOT, exist_ok=True)

_lock = Lock()

# Track last update time for each resource type
_last_updates = {
    "users": 0,
    "posts": 0, 
    "messages": 0,
    "stories": 0,
    "videos": 0,
    "scheduled_posts": 0,
    "notifications": 0,
    "group_chats": 0,
}

# Track client last seen times to know what they need
_client_last_seen = defaultdict(lambda: defaultdict(float))

def _mark_resource_updated(resource: str):
    """Mark a resource as updated with current timestamp"""
    _last_updates[resource] = time.time()

def _get_client_updates_needed(client_id: str) -> dict:
    """Get list of resources that have been updated since client last checked"""
    updates_needed = {}
    for resource, last_update in _last_updates.items():
        client_last_seen = _client_last_seen[client_id][resource]
        if last_update > client_last_seen:
            updates_needed[resource] = last_update
    return updates_needed

def _mark_client_updated(client_id: str, resource: str):
    """Mark that client has seen the latest version of this resource"""
    _client_last_seen[client_id][resource] = _last_updates.get(resource, time.time())




def _safe_media_path(rel_path: str) -> Optional[str]:
    rel_path = (rel_path or "").replace("\\", "/").strip()
    if not rel_path:
        return None
    if rel_path.startswith("..") or "../" in rel_path or "..\\" in rel_path:
        return None
    abs_path = os.path.normpath(os.path.join(BASE_DIR, rel_path))
    try:
        common = os.path.commonpath([abs_path, BASE_DIR])
    except ValueError:
        return None
    if common != BASE_DIR:
        return None
    return abs_path


def _read(name):
    path = FILES.get(name)
    if not path:
        return None
    if not os.path.exists(path):
        # initialize sensible defaults
        default = [] if name in {"posts", "stories", "videos", "scheduled_posts", "group_chats"} else {}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(default, fh, indent=4, ensure_ascii=False)
        return default
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None

def _write(name, payload):
    path = FILES.get(name)
    if not path:
        return False
    try:
        with _lock:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=4, ensure_ascii=False)
        return True
    except Exception:
        return False

app = Flask(__name__)
CORS(app)


# Simple token-based protection for LAN usage. If SOCIAL_SERVER_TOKEN is set in
# the environment, all /api/* endpoints (except /api/ping) will require the
# token. Clients may send it via the Authorization: Bearer <token> header or
# X-SOCIAL-TOKEN header.
def _check_token_allowed() -> bool:
    token = os.environ.get("SOCIAL_SERVER_TOKEN")
    if not token:
        return True
    auth = request.headers.get("Authorization") or ""
    if auth.startswith("Bearer ") and auth.split(" ", 1)[1].strip() == token:
        return True
    header = request.headers.get("X-SOCIAL-TOKEN")
    if header and header == token:
        return True
    return False


@app.before_request
def _require_token_for_api():
    # allow ping without token
    if request.path == "/api/ping":
        return None
    if request.path.startswith("/api/"):
        if not _check_token_allowed():
            return jsonify({"ok": False, "error": "unauthorized"}), 401
    return None


@app.route("/api/ping", methods=["GET"]) 
def ping():
    return jsonify({"ok": True, "message": "server running"})


@app.route("/api/check-updates", methods=["POST"])
def check_updates():
    """Check what resources have been updated since client last checked"""
    payload = request.get_json(silent=True) or {}
    client_id = payload.get("client_id", "unknown")
    
    updates_needed = _get_client_updates_needed(client_id)
    
    return jsonify({
        "ok": True, 
        "updates": updates_needed,
        "timestamp": time.time()
    })


@app.route("/api/mark-synced", methods=["POST"]) 
def mark_synced():
    """Mark that client has synced specific resources"""
    payload = request.get_json(silent=True) or {}
    client_id = payload.get("client_id", "unknown")
    resources = payload.get("resources", [])
    
    for resource in resources:
        if resource in _last_updates:
            _mark_client_updated(client_id, resource)
    
    return jsonify({"ok": True})


@app.route("/api/<resource>", methods=["GET"])
def get_resource(resource):
    if resource not in FILES:
        abort(404)
    data = _read(resource)
    return jsonify({"ok": True, "data": data})


@app.route("/api/<resource>", methods=["PUT", "POST"])
def put_resource(resource):
    if resource not in FILES:
        abort(404)
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"ok": False, "error": "invalid json"}), 400
    ok = _write(resource, payload)
    if not ok:
        return jsonify({"ok": False, "error": "write failed"}), 500
    
    # Mark this resource as updated so other clients know to fetch it
    _mark_resource_updated(resource)
    
    return jsonify({"ok": True})


@app.route("/api/messages/<conversation>", methods=["GET"])
def get_conversation(conversation):
    messages = _read("messages") or {}
    conv = messages.get(conversation, [])
    return jsonify({"ok": True, "data": conv})


@app.route("/api/messages/send", methods=["POST"])
def send_message():
    payload = request.get_json(silent=True) or {}
    conversation = payload.get("conversation")
    message = payload.get("message")
    if not conversation or not message:
        return jsonify({"ok": False, "error": "missing conversation or message"}), 400
    messages = _read("messages") or {}
    messages.setdefault(conversation, []).append(message)
    ok = _write("messages", messages)
    if not ok:
        return jsonify({"ok": False, "error": "write failed"}), 500
    return jsonify({"ok": True})


@app.route("/api/media/upload", methods=["POST"])
def upload_media():
    payload = request.get_json(silent=True) or {}
    rel_path = payload.get("path")
    content = payload.get("content")
    if not isinstance(rel_path, str) or not isinstance(content, str):
        return jsonify({"ok": False, "error": "invalid payload"}), 400
    abs_path = _safe_media_path(rel_path)
    if not abs_path:
        return jsonify({"ok": False, "error": "invalid path"}), 400
    try:
        data = base64.b64decode(content)
    except Exception:
        return jsonify({"ok": False, "error": "invalid base64"}), 400
    try:
        with _lock:
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "wb") as fh:
                fh.write(data)
        return jsonify({"ok": True})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/media/download", methods=["POST"])
def download_media():
    payload = request.get_json(silent=True) or {}
    rel_path = payload.get("path")
    if not isinstance(rel_path, str):
        return jsonify({"ok": False, "error": "invalid payload"}), 400
    abs_path = _safe_media_path(rel_path)
    if not abs_path or not os.path.exists(abs_path):
        return jsonify({"ok": False, "error": "not found"}), 404
    try:
        with _lock:
            with open(abs_path, "rb") as fh:
                data = fh.read()
        encoded = base64.b64encode(data).decode("ascii")
        return jsonify({"ok": True, "content": encoded})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/media/<path:filename>")
def serve_media(filename):
    # serve uploaded media from the repo media folder if exists
    media_dir = os.path.join(BASE_DIR, "media")
    if not os.path.exists(os.path.join(media_dir, filename)):
        abort(404)
    return send_from_directory(media_dir, filename)


if __name__ == "__main__":
    port = int(os.environ.get("SOCIAL_SERVER_PORT", "5000"))
    # Use threaded server for simplicity; production use a WSGI server
    app.run(host="0.0.0.0", port=port, threaded=True)
