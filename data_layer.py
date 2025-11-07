import base64
import json
import os
import time
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Set
from uuid import uuid4

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Generate a unique client ID for this app instance
CLIENT_ID = str(uuid4())[:8]  # Short ID for this client

USERS_PATH = os.path.join(BASE_DIR, "data.json")
POSTS_PATH = os.path.join(BASE_DIR, "posts.json")
NOTIFICATIONS_PATH = os.path.join(BASE_DIR, "notfication.json")
MESSAGES_PATH = os.path.join(BASE_DIR, "messages.json")
STORIES_PATH = os.path.join(BASE_DIR, "stories.json")
VIDEOS_PATH = os.path.join(BASE_DIR, "videos.json")
GROUP_CHATS_PATH = os.path.join(BASE_DIR, "group_chats.json")
SCHEDULED_POSTS_PATH = os.path.join(BASE_DIR, "scheduled_posts.json")

MEDIA_DIR = os.path.join(BASE_DIR, "media")
PROFILE_PICS_DIR = os.path.join(BASE_DIR, "Profile Pictures")
DEFAULT_PROFILE_PIC = os.path.join(PROFILE_PICS_DIR, "image (6).png")

os.makedirs(MEDIA_DIR, exist_ok=True)
os.makedirs(PROFILE_PICS_DIR, exist_ok=True)

STORY_TTL_SECONDS = 24 * 60 * 60

SERVER_CONFIG_PATH = os.path.join(BASE_DIR, "server_config.json")

_REMOTE_SYNC_STATUS: Dict[str, Dict[str, Any]] = {}
_MEDIA_STATUS_KEY = "media"


def _record_remote_sync(resource: str, success: bool, error: Optional[str] = None) -> None:
    _REMOTE_SYNC_STATUS[resource] = {
        "ok": bool(success),
        "error": (error or "").strip(),
        "timestamp": time.time(),
    }


def _normalize_media_rel_path(rel_path: Any) -> Optional[str]:
    if not isinstance(rel_path, str):
        return None
    cleaned = rel_path.replace("\\", "/").strip()
    if not cleaned:
        return None
    if cleaned.startswith("../") or "/../" in cleaned or cleaned.startswith(".."):
        return None
    return cleaned


def _media_abs_path(rel_path: Any) -> Optional[str]:
    normalized = _normalize_media_rel_path(rel_path)
    if not normalized:
        return None
    candidate = os.path.normpath(os.path.join(BASE_DIR, normalized.replace("/", os.sep)))
    try:
        common = os.path.commonpath([candidate, BASE_DIR])
    except ValueError:
        return None
    if common != BASE_DIR:
        return None
    return candidate


def was_last_remote_sync_successful(resource: str) -> bool:
    entry = _REMOTE_SYNC_STATUS.get(resource)
    if not entry:
        return True
    return bool(entry.get("ok"))


def last_remote_sync_error(resource: str) -> Optional[str]:
    entry = _REMOTE_SYNC_STATUS.get(resource)
    if not entry or entry.get("ok"):
        return None
    message = str(entry.get("error") or "").strip()
    return message or None


def _hydrate_server_config() -> None:
    """Load persisted server settings into environment, if present."""
    if os.environ.get("SOCIAL_SERVER_URL"):
        return
    try:
        with open(SERVER_CONFIG_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return
    except Exception:
        return
    url = str(data.get("url") or "").strip()
    token = str(data.get("token") or "").strip()
    if url:
        os.environ["SOCIAL_SERVER_URL"] = url
        if token:
            os.environ["SOCIAL_SERVER_TOKEN"] = token
        else:
            os.environ.pop("SOCIAL_SERVER_TOKEN", None)


def set_server_config(url: Optional[str], token: Optional[str]) -> None:
    """Update env vars and persist server settings for future launches."""
    url_value = (url or "").strip()
    token_value = (token or "").strip()
    if url_value:
        os.environ["SOCIAL_SERVER_URL"] = url_value
        if token_value:
            os.environ["SOCIAL_SERVER_TOKEN"] = token_value
        else:
            os.environ.pop("SOCIAL_SERVER_TOKEN", None)
        payload = {"url": url_value}
        if token_value:
            payload["token"] = token_value
        else:
            payload["token"] = ""
        try:
            with open(SERVER_CONFIG_PATH, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
        except Exception:
            pass
    else:
        os.environ.pop("SOCIAL_SERVER_URL", None)
        os.environ.pop("SOCIAL_SERVER_TOKEN", None)
        try:
            os.remove(SERVER_CONFIG_PATH)
        except FileNotFoundError:
            pass
        except Exception:
            pass


_hydrate_server_config()


def _server_headers() -> Dict[str, str]:
    headers: Dict[str, str] = {}
    token = os.environ.get("SOCIAL_SERVER_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-SOCIAL-TOKEN"] = token
    return headers


def load_json(path: str, default: Any):
    # If a server is configured via env, attempt to fetch resource from server
    server_url = os.environ.get("SOCIAL_SERVER_URL")
    if server_url:
        try:
            import requests

            name = os.path.basename(path)
            mapping = {
                "data.json": "users",
                "posts.json": "posts",
                "messages.json": "messages",
                "stories.json": "stories",
                "videos.json": "videos",
                "scheduled_posts.json": "scheduled_posts",
                "notfication.json": "notifications",
                "group_chats.json": "group_chats",
            }
            resource = mapping.get(name)
            if resource:
                headers = _server_headers()
                resp = requests.get(f"{server_url.rstrip('/')}/api/{resource}", headers=headers, timeout=2)
                if resp.status_code == 200:
                    data = resp.json().get("data")
                    if data is not None:
                        return data
                # if unauthorized, bubble up to caller via None -> fallback to local
        except Exception:
            # fall back to local file reads on any failure
            pass
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default
    except Exception:
        return default


def save_json(path: str, payload: Any) -> None:
    server_url = os.environ.get("SOCIAL_SERVER_URL")
    name = os.path.basename(path)
    mapping = {
        "data.json": "users",
        "posts.json": "posts",
        "messages.json": "messages",
        "stories.json": "stories",
        "videos.json": "videos",
        "scheduled_posts.json": "scheduled_posts",
        "notfication.json": "notifications",
        "group_chats.json": "group_chats",
    }
    resource = mapping.get(name)

    if server_url and resource:
        remote_ok = False
        error_detail = "remote request failed"
        try:
            import requests

            headers = _server_headers()

            endpoint = f"{server_url.rstrip('/')}/api/{resource}"
            resp = requests.put(endpoint, json=payload, headers=headers, timeout=10)
            if resp.status_code in (200, 204):
                remote_ok = True
            else:
                error_detail = f"HTTP {resp.status_code}"
                try:
                    body = resp.json()
                    if isinstance(body, dict) and body.get("error"):
                        error_detail += f": {body['error']}"
                except Exception:
                    text = (resp.text or "").strip()
                    if text:
                        error_detail += f": {text[:200]}"

                if resp.status_code >= 400:
                    try:
                        alt = requests.post(endpoint, json=payload, headers=headers, timeout=10)
                        if alt.status_code in (200, 204):
                            remote_ok = True
                        else:
                            error_detail = f"HTTP {alt.status_code}"
                            try:
                                body = alt.json()
                                if isinstance(body, dict) and body.get("error"):
                                    error_detail += f": {body['error']}"
                            except Exception:
                                text = (alt.text or "").strip()
                                if text:
                                    error_detail += f": {text[:200]}"
                    except Exception as post_exc:
                        error_detail = f"POST failed: {post_exc}"
        except Exception as exc:
            error_detail = str(exc)
        if remote_ok:
            _record_remote_sync(resource, True)
        else:
            _record_remote_sync(resource, False, error_detail)
    elif resource:
        _record_remote_sync(resource, True)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=4, ensure_ascii=False)


def upload_media_asset(rel_path: Any) -> bool:
    server_url = (os.environ.get("SOCIAL_SERVER_URL") or "").strip()
    if not server_url:
        return True
    normalized = _normalize_media_rel_path(rel_path)
    abs_path = _media_abs_path(normalized)
    if not normalized or not abs_path or not os.path.exists(abs_path):
        _record_remote_sync(_MEDIA_STATUS_KEY, False, "file missing" if abs_path else "invalid path")
        return False
    try:
        import requests
    except Exception as exc:  # pragma: no cover - network dependency
        _record_remote_sync(_MEDIA_STATUS_KEY, False, f"requests unavailable: {exc}")
        return False
    try:
        with open(abs_path, "rb") as fh:
            binary = fh.read()
    except OSError as exc:
        _record_remote_sync(_MEDIA_STATUS_KEY, False, str(exc))
        return False
    payload = {
        "path": normalized,
        "content": base64.b64encode(binary).decode("ascii"),
    }
    endpoint = f"{server_url.rstrip('/')}/api/media/upload"
    error_detail = "unknown error"
    try:
        resp = requests.post(endpoint, json=payload, headers=_server_headers(), timeout=15)
        ok = False
        body: Dict[str, Any] = {}
        if resp.status_code == 200:
            try:
                maybe_body = resp.json()
                if isinstance(maybe_body, dict):
                    body = maybe_body
            except Exception:
                body = {}
            ok = body.get("ok") is True
        if ok:
            _record_remote_sync(_MEDIA_STATUS_KEY, True)
            return True
        error_detail = f"HTTP {resp.status_code}"
        if not body:
            try:
                maybe_body = resp.json()
                if isinstance(maybe_body, dict):
                    body = maybe_body
            except Exception:
                body = {}
        if isinstance(body, dict) and body.get("error"):
            error_detail += f": {body['error']}"
        else:
            text = (resp.text or "").strip()
            if text:
                error_detail += f": {text[:200]}"
    except Exception as exc:  # pragma: no cover - network dependency
        error_detail = str(exc)
    _record_remote_sync(_MEDIA_STATUS_KEY, False, error_detail)
    return False


def download_media_asset(rel_path: Any) -> bool:
    normalized = _normalize_media_rel_path(rel_path)
    if not normalized:
        return False
    abs_path = _media_abs_path(normalized)
    if abs_path and os.path.exists(abs_path):
        return True
    server_url = (os.environ.get("SOCIAL_SERVER_URL") or "").strip()
    if not server_url:
        return False
    try:
        import requests
    except Exception:  # pragma: no cover - network dependency
        return False
    endpoint = f"{server_url.rstrip('/')}/api/media/download"
    try:
        # Shorter timeout during startup to prevent hangs
        # Use much shorter timeout for cross-device connections
        timeout = 1  # 1 second timeout to avoid lag
        resp = requests.post(endpoint, json={"path": normalized}, headers=_server_headers(), timeout=timeout)
    except Exception:  # pragma: no cover - network dependency
        return False
    if resp.status_code != 200:
        return False
    try:
        body = resp.json()
    except Exception:
        return False
    if not isinstance(body, dict) or body.get("ok") is not True:
        return False
    content = body.get("content")
    if not isinstance(content, str):
        return False
    try:
        data = base64.b64decode(content)
    except Exception:
        return False
    abs_path = _media_abs_path(normalized)
    if not abs_path:
        return False
    try:
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "wb") as fh:
            fh.write(data)
        return True
    except Exception:
        return False


def ensure_media_local(rel_path: Any) -> bool:
    abs_path = _media_abs_path(rel_path)
    if abs_path and os.path.exists(abs_path):
        return True
    return download_media_asset(rel_path)


def ensure_media_paths(paths: Iterable[Any]) -> int:
    normalized_paths = {
        norm for norm in (_normalize_media_rel_path(item) for item in paths) if norm
    }
    ensured = 0
    for norm in normalized_paths:
        if ensure_media_local(norm):
            ensured += 1
    return ensured


def gather_all_media_paths() -> Set[str]:
    paths: Set[str] = set()

    def _add(value: Any) -> None:
        normalized = _normalize_media_rel_path(value)
        if normalized:
            paths.add(normalized)

    for post in posts:
        if not isinstance(post, dict):
            continue
        for attachment in post.get("attachments", []) or []:
            if isinstance(attachment, dict):
                _add(attachment.get("path"))
                _add(attachment.get("thumbnail"))
    for entry in scheduled_posts:
        if not isinstance(entry, dict):
            continue
        for attachment in entry.get("attachments", []) or []:
            if isinstance(attachment, dict):
                _add(attachment.get("path"))
                _add(attachment.get("thumbnail"))
    for story in stories:
        if not isinstance(story, dict):
            continue
        _add(story.get("path"))
        _add(story.get("thumbnail"))
    for video in videos:
        if not isinstance(video, dict):
            continue
        _add(video.get("path"))
        _add(video.get("thumbnail"))
    for convo in messages.values():
        if not isinstance(convo, list):
            continue
        for message in convo:
            if not isinstance(message, dict):
                continue
            for attachment in message.get("attachments", []) or []:
                if isinstance(attachment, dict):
                    _add(attachment.get("path"))
                    _add(attachment.get("thumbnail"))
    for chat in group_chats:
        if not isinstance(chat, dict):
            continue
        for message in chat.get("messages", []) or []:
            if not isinstance(message, dict):
                continue
            for attachment in message.get("attachments", []) or []:
                if isinstance(attachment, dict):
                    _add(attachment.get("path"))
                    _add(attachment.get("thumbnail"))
    for record in users.values():
        if not isinstance(record, dict):
            continue
        _add(record.get("profile_picture"))
    return paths


def ensure_all_media_local() -> int:
    return ensure_media_paths(gather_all_media_paths())


def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    return list(value) if isinstance(value, tuple) else []


def _normalize_attachment(payload: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return None
    att_type = str(payload.get("type") or "file").strip() or "file"
    path = str(payload.get("path") or "").strip()
    name = str(payload.get("name") or "").strip() or os.path.basename(path)
    size_value = payload.get("size")
    size = None
    if size_value is not None:
        try:
            size = int(size_value)
            if size < 0:
                size = None
        except (TypeError, ValueError):
            size = None
    record: Dict[str, Any] = {
        "type": att_type,
        "path": path,
    }
    if name:
        record["name"] = name
    if size is not None:
        record["size"] = size
    # Preserve optional metadata when present.
    for optional_key in ("mime", "thumbnail"):
        if optional_key in payload:
            record[optional_key] = payload[optional_key]
    return record


def _normalize_badge(payload: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return None
    name = _clean_str(payload.get("name"))
    if not name:
        return None
    description = _clean_str(payload.get("description"))
    awarded_at = _clean_str(payload.get("awarded_at")) or now_ts()
    badge_id = str(payload.get("id") or uuid4())
    icon = _clean_str(payload.get("icon"))
    highlight = bool(payload.get("highlight"))
    badge: Dict[str, Any] = {
        "id": badge_id,
        "name": name[:48],
        "awarded_at": awarded_at,
    }
    if description:
        badge["description"] = description[:200]
    if icon:
        badge["icon"] = icon[:80]
    if highlight:
        badge["highlight"] = True
    return badge


def _normalize_badges(value: Any) -> List[Dict[str, Any]]:
    badges: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()
    seen_names: Set[str] = set()
    if not isinstance(value, list):
        return badges
    for raw in value:
        normalized = _normalize_badge(raw)
        if not normalized:
            continue
        badge_id = normalized.get("id")
        name_key = normalized.get("name", "").strip().lower()
        if not badge_id or badge_id in seen_ids or (name_key and name_key in seen_names):
            continue
        seen_ids.add(badge_id)
        if name_key:
            seen_names.add(name_key)
        badges.append(normalized)
    return badges


def normalize_reply(reply_dict: Dict[str, Any]) -> Dict[str, Any]:
    reply_dict.setdefault("author", "unknown")
    reply_dict.setdefault("content", "")
    reply_dict.setdefault("created_at", now_ts())
    reply_dict.setdefault("edited", False)
    reply_dict.setdefault("edited_at", None)
    reply_dict["liked_by"] = _safe_list(reply_dict.get("liked_by") or [])
    reply_dict["disliked_by"] = _safe_list(reply_dict.get("disliked_by") or [])
    reply_dict["likes"] = len(reply_dict["liked_by"])
    reply_dict["dislikes"] = len(reply_dict["disliked_by"])
    reply_dict.setdefault("attachments", [])
    return reply_dict


def normalize_post(post_dict: Dict[str, Any]) -> Dict[str, Any]:
    post_dict.setdefault("edited", False)
    post_dict.setdefault("edited_at", None)
    post_dict.setdefault("replies", [])
    post_dict["replies"] = [normalize_reply(r) for r in post_dict["replies"]]
    post_dict["liked_by"] = _safe_list(post_dict.get("liked_by") or [])
    post_dict["disliked_by"] = _safe_list(post_dict.get("disliked_by") or [])
    post_dict["likes"] = len(post_dict["liked_by"])
    post_dict["dislikes"] = len(post_dict["disliked_by"])
    post_dict.setdefault("attachments", [])
    return post_dict


def _clean_str(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text


def _build_normalized_users(
    raw_users_data: Any,
    notifications_data: Any,
) -> Dict[str, Dict[str, Any]]:
    normalized: Dict[str, Dict[str, Any]] = {}
    notifications_map: Dict[str, Any] = notifications_data if isinstance(notifications_data, dict) else {}

    if isinstance(raw_users_data, dict):
        for username, info in raw_users_data.items():
            if not isinstance(username, str) or not isinstance(info, dict):
                continue
            record: Dict[str, Any] = {
                "password": info.get("password", ""),
                "registered_at": info.get("registered_at", now_ts()),
                "notifications": [note for note in notifications_map.get(username, []) if isinstance(note, dict)],
                "following": list(info.get("following", [])),
                "followers": list(info.get("followers", [])),
                "profile_picture": info.get("profile_picture"),
                "bio": info.get("bio"),
                "location": info.get("location"),
                "website": info.get("website"),
                "last_active_at": info.get("last_active_at"),
                "badges": info.get("badges"),
            }
            normalized[username] = record

    for username, notes in notifications_map.items():
        if not isinstance(username, str) or not isinstance(notes, list):
            continue
        record = normalized.setdefault(
            username,
            {
                "password": "",
                "registered_at": now_ts(),
                "notifications": [],
                "following": [],
                "followers": [],
                "profile_picture": None,
                "bio": "",
                "location": "",
                "website": "",
                "last_active_at": now_ts(),
                "badges": [],
            },
        )
        record["notifications"] = [note for note in notes if isinstance(note, dict)]

    for username, record in normalized.items():
        record["following"] = [str(name).strip() for name in record.get("following", []) if isinstance(name, str)]
        record["followers"] = [str(name).strip() for name in record.get("followers", []) if isinstance(name, str)]
        record["notifications"] = [note for note in record.get("notifications", []) if isinstance(note, dict)]
        record["bio"] = _clean_str(record.get("bio"))
        record["location"] = _clean_str(record.get("location"))
        record["website"] = _clean_str(record.get("website"))
        record["last_active_at"] = record.get("last_active_at") or now_ts()
        badges_value = record.get("badges")
        if isinstance(badges_value, list):
            record["badges"] = _normalize_badges(badges_value)
        else:
            record["badges"] = []

    return normalized


def _coerce_epoch(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_story(story_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(story_dict, dict):
        return None
    path = story_dict.get("path")
    if not path:
        return None
    story_type = story_dict.get("type")
    if story_type not in {"image", "video"}:
        story_type = "image"
    author = story_dict.get("author") or "unknown"
    created_label = story_dict.get("created_at") or now_ts()
    created_epoch = _coerce_epoch(story_dict.get("created_at_epoch"))
    if created_epoch is None:
        created_epoch = time.time()
    expires_at = _coerce_epoch(story_dict.get("expires_at"))
    if expires_at is None:
        expires_at = created_epoch + STORY_TTL_SECONDS
    story_id = str(story_dict.get("id") or uuid4())
    text_value = str(story_dict.get("text") or "").strip()
    raw_mentions = story_dict.get("mentions")
    mentions_value: List[str] = []
    if isinstance(raw_mentions, list):
        for raw in raw_mentions:
            if not isinstance(raw, str):
                continue
            cleaned = raw.strip()
            if cleaned and cleaned not in mentions_value:
                mentions_value.append(cleaned)

    liked_raw = story_dict.get("liked_by")
    liked_by: List[str] = []
    if isinstance(liked_raw, list):
        for raw in liked_raw:
            if not isinstance(raw, str):
                continue
            handle = raw.strip()
            if handle and handle not in liked_by:
                liked_by.append(handle)

    disliked_raw = story_dict.get("disliked_by")
    disliked_by: List[str] = []
    if isinstance(disliked_raw, list):
        for raw in disliked_raw:
            if not isinstance(raw, str):
                continue
            handle = raw.strip()
            if handle and handle not in disliked_by and handle not in liked_by:
                disliked_by.append(handle)

    story = {
        "id": story_id,
        "author": str(author),
        "path": str(path),
        "type": story_type,
        "created_at": created_label,
        "created_at_epoch": float(created_epoch),
        "expires_at": float(expires_at),
        "liked_by": liked_by,
        "disliked_by": disliked_by,
        "likes": len(liked_by),
        "dislikes": len(disliked_by),
    }
    if text_value:
        story["text"] = text_value
    if mentions_value:
        story["mentions"] = mentions_value
    return story


def normalize_video_comment(comment_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(comment_dict, dict):
        return None
    text = str(comment_dict.get("text") or "").strip()
    if not text:
        return None
    author = str(comment_dict.get("author") or "unknown")
    comment_id = str(comment_dict.get("id") or uuid4())
    created_at = comment_dict.get("created_at") or now_ts()
    return {
        "id": comment_id,
        "author": author,
        "text": text,
        "created_at": created_at,
    }


def normalize_video(video_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(video_dict, dict):
        return None
    path = str(video_dict.get("path") or "").strip()
    if not path:
        return None
    author = str(video_dict.get("author") or "unknown")
    created_at = video_dict.get("created_at") or now_ts()
    caption = str(video_dict.get("caption") or "").strip()
    video_id = str(video_dict.get("id") or uuid4())
    comments: List[Dict[str, Any]] = []
    raw_comments = video_dict.get("comments")
    if isinstance(raw_comments, list):
        for comment in raw_comments:
            normalized = normalize_video_comment(comment)
            if normalized:
                comments.append(normalized)
    liked_raw = _safe_list(video_dict.get("liked_by") or [])
    disliked_raw = _safe_list(video_dict.get("disliked_by") or [])
    liked_by = []
    disliked_by = []
    for entry in liked_raw:
        if isinstance(entry, str) and entry not in liked_by:
            liked_by.append(entry)
    for entry in disliked_raw:
        if isinstance(entry, str) and entry not in disliked_by and entry not in liked_by:
            disliked_by.append(entry)
    payload: Dict[str, Any] = {
        "id": video_id,
        "author": author,
        "path": path,
        "created_at": created_at,
        "comments": comments,
        "liked_by": liked_by,
        "disliked_by": disliked_by,
        "likes": len(liked_by),
        "dislikes": len(disliked_by),
    }
    if caption:
        payload["caption"] = caption
    return payload


def normalize_scheduled_post(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(entry, dict):
        return None
    author = _clean_str(entry.get("author"))
    scheduled_at = _clean_str(entry.get("scheduled_at"))
    if not author or not scheduled_at:
        return None
    content = str(entry.get("content", ""))
    created_at = _clean_str(entry.get("created_at")) or now_ts()
    scheduled_id = str(entry.get("id") or uuid4())
    attachments: List[Dict[str, Any]] = []
    raw_attachments = entry.get("attachments")
    if isinstance(raw_attachments, list):
        for item in raw_attachments:
            normalized = _normalize_attachment(item)
            if normalized:
                attachments.append(normalized)
    return {
        "id": scheduled_id,
        "author": author,
        "content": content,
        "scheduled_at": scheduled_at,
        "created_at": created_at,
        "attachments": attachments,
    }


# Initialize data structures as empty to avoid blocking network calls during import
# Data will be loaded on-demand when needed to prevent startup delays
raw_users: Dict[str, Dict[str, Any]] = {}
notifications_data: Dict[str, List[Dict[str, Any]]] = {}
raw_posts = []
messages: Dict[str, List[Dict[str, Any]]] = {}
raw_stories = []
raw_videos = []
raw_group_chats = []
raw_scheduled_posts = []

# Flag to track if initial data has been loaded
_initial_data_loaded = False

def _ensure_initial_data_loaded():
    """Load initial data if not already loaded. Call this before accessing data."""
    global _initial_data_loaded, raw_users, notifications_data, raw_posts
    global messages, raw_stories, raw_videos, raw_group_chats, raw_scheduled_posts
    
    if _initial_data_loaded:
        return
        
    try:
        # Load data with short timeouts to avoid blocking
        raw_users.update(load_json(USERS_PATH, {}))
        notifications_data.update(load_json(NOTIFICATIONS_PATH, {}))
        raw_posts.extend(load_json(POSTS_PATH, []))
        messages.update(load_json(MESSAGES_PATH, {}))
        raw_stories.extend(load_json(STORIES_PATH, []))
        raw_videos.extend(load_json(VIDEOS_PATH, []))
        raw_group_chats.extend(load_json(GROUP_CHATS_PATH, []))
        raw_scheduled_posts.extend(load_json(SCHEDULED_POSTS_PATH, []))
        _initial_data_loaded = True
    except Exception:
        # If loading fails, continue with empty data
        # This prevents the app from hanging on startup
        _initial_data_loaded = True  # Mark as loaded to prevent retries

# Ensure data is loaded before processing
_ensure_initial_data_loaded()

if isinstance(raw_posts, list):
    posts: List[Dict[str, Any]] = [normalize_post(p) for p in raw_posts]
else:
    posts = []
    for author, plist in raw_posts.items():
        for post in plist:
            posts.append(
                normalize_post(
                    {
                        "author": author,
                        "content": post.get("post", ""),
                        "created_at": post.get("posted_at", now_ts()),
                    }
                )
            )


stories: List[Dict[str, Any]] = []
if isinstance(raw_stories, list):
    current_time = time.time()
    for item in raw_stories:
        normalized_story = normalize_story(item)
        if not normalized_story:
            continue
        if normalized_story["expires_at"] <= current_time:
            continue
        stories.append(normalized_story)

videos: List[Dict[str, Any]] = []
if isinstance(raw_videos, list):
    for item in raw_videos:
        normalized_video = normalize_video(item)
        if normalized_video:
            videos.append(normalized_video)


def _coerce_members(raw_members: Any) -> List[str]:
    if not isinstance(raw_members, list):
        return []
    members: List[str] = []
    for entry in raw_members:
        if not isinstance(entry, str):
            continue
        handle = entry.strip()
        if handle and handle not in members:
            members.append(handle)
    return members


def _coerce_messages(raw_messages: Any) -> List[Dict[str, Any]]:
    if isinstance(raw_messages, list):
        result: List[Dict[str, Any]] = []
        for msg in raw_messages:
            if not isinstance(msg, dict):
                continue
            payload = {
                "sender": msg.get("sender"),
                "content": msg.get("content", ""),
                "time": msg.get("time", now_ts()),
                "attachments": msg.get("attachments", []),
            }
            result.append(payload)
        return result
    return []


def normalize_group_chat(chat_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(chat_dict, dict):
        return None
    chat_id = str(chat_dict.get("id") or f"group:{uuid4()}")
    name = str(chat_dict.get("name") or "Group chat")
    owner = str(chat_dict.get("owner") or "")
    members = _coerce_members(chat_dict.get("members") or [])
    if owner and owner not in members:
        members.insert(0, owner)
    messages_list = _coerce_messages(chat_dict.get("messages") or [])
    created_at = chat_dict.get("created_at") or now_ts()
    updated_at = chat_dict.get("updated_at") or created_at
    announcement = str(chat_dict.get("announcement") or "").strip()
    invite_token = str(chat_dict.get("invite_token") or "").strip()
    invite_updated_at = chat_dict.get("invite_updated_at")
    if not owner and members:
        owner = members[0]
    payload: Dict[str, Any] = {
        "id": chat_id,
        "name": name,
        "owner": owner,
        "members": members,
        "messages": messages_list,
        "created_at": created_at,
        "updated_at": updated_at,
    }
    if announcement:
        payload["announcement"] = announcement
    if invite_token:
        payload["invite_token"] = invite_token
    if invite_updated_at:
        payload["invite_updated_at"] = invite_updated_at
    return payload


group_chats: List[Dict[str, Any]] = []
if isinstance(raw_group_chats, list):
    for item in raw_group_chats:
        normalized_chat = normalize_group_chat(item)
        if normalized_chat:
            group_chats.append(normalized_chat)


scheduled_posts: List[Dict[str, Any]] = []
if isinstance(raw_scheduled_posts, list):
    for item in raw_scheduled_posts:
        normalized_scheduled = normalize_scheduled_post(item)
        if normalized_scheduled:
            scheduled_posts.append(normalized_scheduled)


users: Dict[str, Dict[str, Any]] = _build_normalized_users(raw_users, notifications_data)


def purge_expired_stories(now_value: Optional[float] = None) -> bool:
    now_value = now_value if now_value is not None else time.time()
    before = len(stories)
    stories[:] = [s for s in stories if s.get("expires_at", 0) > now_value]
    return len(stories) != before


def persist() -> None:
    save_json(USERS_PATH, users)
    save_json(POSTS_PATH, posts)
    save_json(NOTIFICATIONS_PATH, {user: users[user].get("notifications", []) for user in users})
    save_json(MESSAGES_PATH, messages)
    save_json(STORIES_PATH, stories)
    save_json(VIDEOS_PATH, videos)
    save_json(SCHEDULED_POSTS_PATH, scheduled_posts)
    save_json(GROUP_CHATS_PATH, group_chats)

def push_immediate_update(resource: str, delay_ms: int = 100) -> None:
    """
    Immediately push a specific resource update to server and notify other clients.
    Uses debouncing to prevent spam from rapid changes.
    """
    import threading
    import time
    
    # Debouncing: prevent multiple rapid updates to same resource
    current_time = time.time()
    if not hasattr(push_immediate_update, '_last_push'):
        push_immediate_update._last_push = {}
    
    last_push = push_immediate_update._last_push.get(resource, 0)
    if current_time - last_push < (delay_ms / 1000):
        # Too soon, skip this push
        return
    
    push_immediate_update._last_push[resource] = current_time
    
    def _async_push():
        try:
            # Map resource names to file paths
            resource_map = {
                "users": USERS_PATH,
                "posts": POSTS_PATH, 
                "messages": MESSAGES_PATH,
                "stories": STORIES_PATH,
                "videos": VIDEOS_PATH,
                "notifications": NOTIFICATIONS_PATH,
                "group_chats": GROUP_CHATS_PATH,
                "scheduled_posts": SCHEDULED_POSTS_PATH,
            }
            
            path = resource_map.get(resource)
            if not path:
                return
                
            # Save the specific resource
            if resource == "users":
                save_json(path, users)
            elif resource == "posts":
                save_json(path, posts)
            elif resource == "messages":
                save_json(path, messages)
            elif resource == "stories":
                save_json(path, stories)
            elif resource == "videos":
                save_json(path, videos)
            elif resource == "notifications":
                save_json(path, {user: users[user].get("notifications", []) for user in users})
            elif resource == "group_chats":
                save_json(path, group_chats)
            elif resource == "scheduled_posts":
                save_json(path, scheduled_posts)
                
        except Exception:
            # Fail silently to avoid disrupting UI
            pass
    
    # Run push in background thread to avoid blocking UI
    thread = threading.Thread(target=_async_push, daemon=True)
    thread.start()

def persist_and_push(resource: str = None) -> None:
    """Enhanced persist that also triggers immediate push for specific resource"""
    if resource:
        # Push only the changed resource immediately
        push_immediate_update(resource)
    else:
        # Full persist (fallback for bulk operations)
        persist()


def check_for_updates() -> Dict[str, float]:
    """Check server for what resources have been updated since we last synced"""
    server_url = (os.environ.get("SOCIAL_SERVER_URL") or "").strip()
    if not server_url:
        return {}
        
    try:
        import requests
        endpoint = f"{server_url.rstrip('/')}/api/check-updates"
        payload = {"client_id": CLIENT_ID}
        resp = requests.post(endpoint, json=payload, headers=_server_headers(), timeout=2)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                return data.get("updates", {})
    except Exception:
        pass
    return {}


def mark_resources_synced(resources: List[str]) -> bool:
    """Tell server that we've synced these resources"""
    server_url = (os.environ.get("SOCIAL_SERVER_URL") or "").strip()
    if not server_url:
        return True
        
    try:
        import requests
        endpoint = f"{server_url.rstrip('/')}/api/mark-synced"
        payload = {"client_id": CLIENT_ID, "resources": resources}
        resp = requests.post(endpoint, json=payload, headers=_server_headers(), timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


def smart_sync_updates() -> Dict[str, bool]:
    """Check for updates and sync only changed resources. Much more efficient than full refresh."""
    updates_needed = check_for_updates()
    if not updates_needed:
        return {}
    
    changes: Dict[str, bool] = {}
    synced_resources: List[str] = []

    def _mark_synced(resource_name: str) -> None:
        if resource_name not in synced_resources:
            synced_resources.append(resource_name)
    
    # Only sync resources that have actually changed
    for resource, _timestamp in updates_needed.items():
        try:
            if resource == "posts":
                raw_posts_remote = load_json(POSTS_PATH, [])
                if isinstance(raw_posts_remote, list):
                    normalized_posts = [normalize_post(dict(item)) for item in raw_posts_remote if isinstance(item, dict)]
                    if normalized_posts != posts:
                        posts[:] = normalized_posts
                        changes["posts"] = True
                        _mark_synced("posts")
            
            elif resource == "users":
                raw_users_remote = load_json(USERS_PATH, {})
                notifications_remote = load_json(NOTIFICATIONS_PATH, {})
                if isinstance(raw_users_remote, dict):
                    normalized_users = _build_normalized_users(raw_users_remote, notifications_remote)
                    if normalized_users != users:
                        users.clear()
                        users.update(normalized_users)
                        changes["users"] = True
                        _mark_synced("users")
                        _mark_synced("notifications")
            
            elif resource == "messages":
                raw_messages_remote = load_json(MESSAGES_PATH, {})
                if isinstance(raw_messages_remote, dict):
                    if raw_messages_remote != messages:
                        messages.clear()
                        messages.update(raw_messages_remote)
                        changes["messages"] = True
                        _mark_synced("messages")
            elif resource == "stories":
                raw_stories_remote = load_json(STORIES_PATH, [])
                if isinstance(raw_stories_remote, list):
                    now_value = time.time()
                    normalized_stories: List[Dict[str, Any]] = []
                    for entry in raw_stories_remote:
                        if not isinstance(entry, dict):
                            continue
                        normalized_story = normalize_story(dict(entry))
                        if normalized_story and normalized_story.get("expires_at", 0) > now_value:
                            normalized_stories.append(normalized_story)
                    if normalized_stories != stories:
                        stories[:] = normalized_stories
                        changes["stories"] = True
                        _mark_synced("stories")

            elif resource == "videos":
                raw_videos_remote = load_json(VIDEOS_PATH, [])
                if isinstance(raw_videos_remote, list):
                    normalized_videos: List[Dict[str, Any]] = []
                    for entry in raw_videos_remote:
                        if not isinstance(entry, dict):
                            continue
                        normalized_video = normalize_video(dict(entry))
                        if normalized_video:
                            normalized_videos.append(normalized_video)
                    if normalized_videos != videos:
                        videos[:] = normalized_videos
                        changes["videos"] = True
                        _mark_synced("videos")

            elif resource == "group_chats":
                raw_group_chats_remote = load_json(GROUP_CHATS_PATH, [])
                if isinstance(raw_group_chats_remote, list):
                    normalized_group_chats: List[Dict[str, Any]] = []
                    for entry in raw_group_chats_remote:
                        if not isinstance(entry, dict):
                            continue
                        normalized_chat = normalize_group_chat(dict(entry))
                        if normalized_chat:
                            normalized_group_chats.append(normalized_chat)
                    if normalized_group_chats != group_chats:
                        group_chats[:] = normalized_group_chats
                        changes["group_chats"] = True
                        _mark_synced("group_chats")

            elif resource == "notifications":
                raw_users_remote = load_json(USERS_PATH, {})
                notifications_remote = load_json(NOTIFICATIONS_PATH, {})
                if isinstance(raw_users_remote, dict):
                    normalized_users = _build_normalized_users(raw_users_remote, notifications_remote)
                    if normalized_users != users:
                        users.clear()
                        users.update(normalized_users)
                        changes["notifications"] = True
                        changes["users"] = True
                        _mark_synced("notifications")
                        _mark_synced("users")
            
            # Add other resources as needed (stories, videos, etc.)
            
        except Exception:
            # If sync fails for this resource, continue with others
            continue
    
    # Mark successfully synced resources
    if synced_resources:
        mark_resources_synced(synced_resources)
    
    return changes


def refresh_remote_state() -> Dict[str, bool]:
    """Re-fetch remote datasets and update in-memory structures. Returns changed sections."""
    changes: Dict[str, bool] = {}

    try:
        raw_posts_remote = load_json(POSTS_PATH, [])
        if isinstance(raw_posts_remote, list):
            normalized_posts = [normalize_post(dict(item)) for item in raw_posts_remote if isinstance(item, dict)]
            if normalized_posts != posts:
                posts[:] = normalized_posts
                changes["posts"] = True
    except Exception:
        pass

    try:
        raw_stories_remote = load_json(STORIES_PATH, [])
        if isinstance(raw_stories_remote, list):
            now_value = time.time()
            normalized_stories: List[Dict[str, Any]] = []
            for entry in raw_stories_remote:
                if not isinstance(entry, dict):
                    continue
                normalized_story = normalize_story(dict(entry))
                if normalized_story and normalized_story.get("expires_at", 0) > now_value:
                    normalized_stories.append(normalized_story)
            if normalized_stories != stories:
                stories[:] = normalized_stories
                changes["stories"] = True
    except Exception:
        pass

    try:
        raw_videos_remote = load_json(VIDEOS_PATH, [])
        if isinstance(raw_videos_remote, list):
            normalized_videos: List[Dict[str, Any]] = []
            for entry in raw_videos_remote:
                if not isinstance(entry, dict):
                    continue
                normalized_video = normalize_video(dict(entry))
                if normalized_video:
                    normalized_videos.append(normalized_video)
            if normalized_videos != videos:
                videos[:] = normalized_videos
                changes["videos"] = True
    except Exception:
        pass

    try:
        raw_users_remote = load_json(USERS_PATH, {})
        notifications_remote = load_json(NOTIFICATIONS_PATH, {})
        normalized_users = _build_normalized_users(raw_users_remote, notifications_remote)
        if normalized_users != users:
            users.clear()
            users.update(normalized_users)
            changes["users"] = True
    except Exception:
        pass

    if os.environ.get("SOCIAL_SERVER_URL"):
        try:
            ensure_all_media_local()
        except Exception:
            pass

    return changes


__all__ = [
    "BASE_DIR",
    "USERS_PATH",
    "POSTS_PATH",
    "NOTIFICATIONS_PATH",
    "MESSAGES_PATH",
    "STORIES_PATH",
    "VIDEOS_PATH",
    "GROUP_CHATS_PATH",
    "SCHEDULED_POSTS_PATH",
    "MEDIA_DIR",
    "PROFILE_PICS_DIR",
    "DEFAULT_PROFILE_PIC",
    "set_server_config",
    "refresh_remote_state",
    "was_last_remote_sync_successful",
    "last_remote_sync_error",
    "load_json",
    "save_json",
    "now_ts",
    "normalize_post",
    "normalize_reply",
    "normalize_story",
    "normalize_video",
    "normalize_video_comment",
    "normalize_scheduled_post",
    "users",
    "posts",
    "messages",
    "stories",
    "videos",
    "group_chats",
    "scheduled_posts",
    "persist",
    "push_immediate_update",
    "persist_and_push",
    "notifications_data",
    "purge_expired_stories",
    "STORY_TTL_SECONDS",
    "upload_media_asset",
    "download_media_asset",
    "ensure_media_local",
    "ensure_media_paths",
    "gather_all_media_paths",
    "ensure_all_media_local",
]
