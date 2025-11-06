from flask import Flask, jsonify, request, send_from_directory, abort
from flask_cors import CORS
import os
import json
from threading import Lock

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

_lock = Lock()

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


@app.route("/api/ping", methods=["GET"]) 
def ping():
    return jsonify({"ok": True, "message": "server running"})


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
