import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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
                headers = {}
                token = os.environ.get("SOCIAL_SERVER_TOKEN")
                if token:
                    # prefer Authorization header but accept X-SOCIAL-TOKEN too
                    headers["Authorization"] = f"Bearer {token}"
                    headers["X-SOCIAL-TOKEN"] = token
                resp = requests.get(f"{server_url.rstrip('/')}/api/{resource}", headers=headers, timeout=6)
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
    # If a server is configured, attempt to push payload to server resource
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
                headers = {}
                token = os.environ.get("SOCIAL_SERVER_TOKEN")
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    headers["X-SOCIAL-TOKEN"] = token
                # prefer PUT for idempotent update
                resp = requests.put(f"{server_url.rstrip('/')}/api/{resource}", json=payload, headers=headers, timeout=10)
                if resp.status_code in (200, 204):
                    return
                # some servers may accept POST
                if resp.status_code >= 400:
                    try:
                        requests.post(f"{server_url.rstrip('/')}/api/{resource}", json=payload, headers=headers, timeout=10)
                        return
                    except Exception:
                        pass
        except Exception:
            # on any failure, fall back to local file write
            pass
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=4, ensure_ascii=False)


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


raw_users: Dict[str, Dict[str, Any]] = load_json(USERS_PATH, {})
notifications_data: Dict[str, List[Dict[str, Any]]] = load_json(NOTIFICATIONS_PATH, {})
raw_posts = load_json(POSTS_PATH, [])
messages: Dict[str, List[Dict[str, Any]]] = load_json(MESSAGES_PATH, {})
raw_stories = load_json(STORIES_PATH, [])
raw_videos = load_json(VIDEOS_PATH, [])
raw_group_chats = load_json(GROUP_CHATS_PATH, [])
raw_scheduled_posts = load_json(SCHEDULED_POSTS_PATH, [])

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
    if not owner and members:
        owner = members[0]
    return {
        "id": chat_id,
        "name": name,
        "owner": owner,
        "members": members,
        "messages": messages_list,
        "created_at": created_at,
        "updated_at": updated_at,
    }


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


users: Dict[str, Dict[str, Any]] = {}
for username, info in raw_users.items():
    users[username] = {
        "password": info.get("password", ""),
        "registered_at": info.get("registered_at", now_ts()),
        "notifications": notifications_data.get(username, []),
        "following": list(info.get("following", [])),
        "followers": list(info.get("followers", [])),
        "profile_picture": info.get("profile_picture"),
        "bio": _clean_str(info.get("bio")),
        "location": _clean_str(info.get("location")),
        "website": _clean_str(info.get("website")),
        "last_active_at": info.get("last_active_at") or now_ts(),
        "badges": _normalize_badges(info.get("badges")),
    }


for username, notes in notifications_data.items():
    users.setdefault(
        username,
        {
            "password": "",
            "registered_at": now_ts(),
            "notifications": notes,
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


for uname in users:
    users[uname].setdefault("following", [])
    users[uname].setdefault("followers", [])
    users[uname].setdefault("bio", "")
    users[uname].setdefault("location", "")
    users[uname].setdefault("website", "")
    users[uname].setdefault("last_active_at", now_ts())
    badges_value = users[uname].get("badges")
    if isinstance(badges_value, list):
        users[uname]["badges"] = _normalize_badges(badges_value)
    else:
        users[uname]["badges"] = []


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
    "notifications_data",
    "purge_expired_stories",
    "STORY_TTL_SECONDS",
]
