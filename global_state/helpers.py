from __future__ import annotations

from typing import Callable, MutableMapping, MutableSequence, Any
import re

_ctx: dict[str, Any] = {}


def configure_helpers(
    *,
    current_user_getter: Callable[[], str | None],
    users: MutableMapping[str, dict],
    posts: MutableSequence[dict],
    messagebox_mod: Any,
    persist_cb: Callable[[], None],
    render_feed_cb: Callable[[], None],
    render_profile_cb: Callable[[], None],
    render_notifications_cb: Callable[[], None],
    render_dm_sidebar_cb: Callable[[], None],
    render_inspected_profile_cb: Callable[[], None],
    now_ts_cb: Callable[[], str],
) -> None:
    _ctx.update(
        current_user_getter=current_user_getter,
        users=users,
        posts=posts,
        messagebox=messagebox_mod,
        persist=persist_cb,
        render_feed=render_feed_cb,
        render_profile=render_profile_cb,
        render_notifications=render_notifications_cb,
        render_dm_sidebar=render_dm_sidebar_cb,
        render_inspected_profile=render_inspected_profile_cb,
        now_ts=now_ts_cb,
    )


def _require(name: str) -> Any:
    if name not in _ctx:
        raise RuntimeError("helpers not configured: {name}")
    return _ctx[name]


def _call_if_present(name: str) -> None:
    func = _ctx.get(name)
    if callable(func):
        func()


def require_login(action: str = "perform this action") -> bool:
    current_user = _require("current_user_getter")()
    if not current_user:
        _require("messagebox").showinfo("Sign in required", f"You must sign in to {action}.")
        return False
    return True


def push_notification(username: str, message: str, *, meta: dict | None = None) -> bool:
    users = _require("users")
    if username not in users:
        return False
    payload = {"message": message, "time": _require("now_ts")()}
    if meta:
        payload["meta"] = meta
    users[username].setdefault("notifications", []).append(payload)
    return True


def notify_mentions(author: str, text: str, context: str) -> bool:
    users = _require("users")
    mentioned = {name.lower() for name in re.findall(r"@(\w+)", text or "")}
    delivered = False
    for username in users:
        if username != author and username.lower() in mentioned:
            if push_notification(username, f"@{author} mentioned you in {context}"):
                delivered = True
    return delivered


def notify_followers(author: str) -> int:
    users = _require("users")
    followers = users.get(author, {}).get("followers", [])
    count = 0
    for follower in followers:
        if push_notification(follower, f"@{author} posted a new update"):
            count += 1
    return count


def _toggle_reaction(entity: dict, username: str, kind: str) -> None:
    entity.setdefault("liked_by", [])
    entity.setdefault("disliked_by", [])
    liked = entity["liked_by"] if isinstance(entity["liked_by"], list) else []
    disliked = entity["disliked_by"] if isinstance(entity["disliked_by"], list) else []
    if kind == "like":
        if username in liked:
            liked.remove(username)
        else:
            liked.append(username)
            if username in disliked:
                disliked.remove(username)
    else:
        if username in disliked:
            disliked.remove(username)
        else:
            disliked.append(username)
            if username in liked:
                liked.remove(username)
    entity["liked_by"] = liked
    entity["disliked_by"] = disliked
    entity["likes"] = len(liked)
    entity["dislikes"] = len(disliked)


def toggle_post_reaction(post_idx: int, kind: str) -> None:
    if not require_login(f"{kind} a post"):
        return
    posts = _require("posts")
    current_user = _require("current_user_getter")()
    if 0 <= post_idx < len(posts):
        _toggle_reaction(posts[post_idx], current_user, kind)
        _require("persist")()
        _call_if_present("render_feed")
        _call_if_present("render_profile")


def toggle_reply_reaction(post_idx: int, reply_idx: int, kind: str) -> None:
    if not require_login(f"{kind} a reply"):
        return
    posts = _require("posts")
    current_user = _require("current_user_getter")()
    if 0 <= post_idx < len(posts):
        replies = posts[post_idx].get("replies", [])
        if 0 <= reply_idx < len(replies):
            _toggle_reaction(replies[reply_idx], current_user, kind)
            _require("persist")()
            _call_if_present("render_feed")
            _call_if_present("render_profile")


def total_likes_for(username: str) -> int:
    posts = _require("posts")
    return sum(
        len(p.get("liked_by", []))
        for p in posts
        if p.get("author") == username
    ) + sum(
        len(r.get("liked_by", []))
        for p in posts
        for r in p.get("replies", [])
        if r.get("author") == username
    )


def follow_user(username: str) -> None:
    if not require_login("follow users"):
        return
    current_user = _require("current_user_getter")()
    if username == current_user:
        return
    users = _require("users")
    me = users.get(current_user, {})
    target = users.get(username, {})
    me.setdefault("following", [])
    target.setdefault("followers", [])
    if username not in me["following"]:
        me["following"].append(username)
    if current_user not in target["followers"]:
        target["followers"].append(current_user)
        push_notification(
            username,
            f"@{current_user} started following you",
            meta={"type": "follow", "from": current_user},
        )
    _require("persist")()
    _call_if_present("render_inspected_profile")
    _call_if_present("render_dm_sidebar")
    _call_if_present("render_notifications")


def unfollow_user(username: str) -> None:
    if not require_login("unfollow users"):
        return
    current_user = _require("current_user_getter")()
    if username == current_user:
        return
    users = _require("users")
    me = users.get(current_user, {})
    target = users.get(username, {})
    me.setdefault("following", [])
    target.setdefault("followers", [])
    if username in me["following"]:
        me["following"].remove(username)
    if current_user in target["followers"]:
        target["followers"].remove(current_user)
    _require("persist")()
    _call_if_present("render_inspected_profile")
    _call_if_present("render_dm_sidebar")
    _call_if_present("render_notifications")