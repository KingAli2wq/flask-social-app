import os
from typing import Any, Callable, Optional

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog

from achievements import compute_achievement_progress
from data_layer import ensure_media_local

try:
    from PIL import Image, ImageDraw, ImageTk  # type: ignore
except ImportError:
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    ImageTk = None  # type: ignore

Palette = dict[str, str]
UserDict = dict[str, Any]
PostDict = dict[str, Any]

PostRenderer = Callable[[int, PostDict], None]
NotificationCallback = Callable[[str, str, Optional[dict[str, Any]]], bool]


def _clear_children(widget: Optional[Any]) -> None:
    if not widget:
        return
    for child in widget.winfo_children():
        child.destroy()


def profile_image_path(
    username: str,
    *,
    users: UserDict,
    base_dir: str,
    default_profile_pic: Optional[str],
) -> Optional[str]:
    path = users.get(username, {}).get("profile_picture")
    if path:
        if not os.path.isabs(path):
            ensure_media_local(path)
        abs_path = path if os.path.isabs(path) else os.path.join(base_dir, path)
        if os.path.exists(abs_path):
            return abs_path
    if default_profile_pic:
        default_abs = default_profile_pic if os.path.isabs(default_profile_pic) else os.path.join(
            base_dir, default_profile_pic
        )
        if os.path.exists(default_abs):
            return default_abs
    return None


def load_profile_avatar(
    username: str,
    size: int,
    *,
    users: UserDict,
    base_dir: str,
    default_profile_pic: Optional[str],
    cache: dict[tuple[str, int], tk.PhotoImage],
) -> Optional[tk.PhotoImage]:
    key = (username, size)
    if key in cache:
        return cache[key]

    path = profile_image_path(username, users=users, base_dir=base_dir, default_profile_pic=default_profile_pic)
    if not path:
        return None

    try:
        if Image and ImageTk and ImageDraw:
            img = Image.open(path).convert("RGBA")
            resampling = getattr(Image, "Resampling", None)
            lanczos = getattr(resampling, "LANCZOS", None) if resampling else getattr(Image, "LANCZOS", None)
            fallback = (
                getattr(resampling, "BICUBIC", None) if resampling else getattr(Image, "BICUBIC", None)
            ) or getattr(Image, "BILINEAR", None) or getattr(Image, "NEAREST", 0)
            img = img.resize((size, size), lanczos or fallback)
            mask = Image.new("L", (size, size), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
            img.putalpha(mask)
            photo = ImageTk.PhotoImage(img)
        else:
            photo = tk.PhotoImage(file=path)
            if photo.width() > size:
                factor = max(1, photo.width() // size)
                photo = photo.subsample(factor, factor)
    except Exception:
        return None

    cache[key] = photo
    return photo


def invalidate_profile_avatar(cache: dict[tuple[str, int], tk.PhotoImage], username: str) -> None:
    for key in [k for k in list(cache.keys()) if k[0] == username]:
        cache.pop(key, None)


def update_profile_avatar_display(
    *,
    current_user: Optional[str],
    profile_avatar_panel: Optional[ctk.CTkFrame],
    profile_avatar_label: Optional[tk.Label],
    profile_change_pic_btn: Optional[ctk.CTkButton],
    load_avatar: Callable[[str, int], Optional[tk.PhotoImage]],
    size: int = 112,
) -> None:
    if not profile_change_pic_btn or not profile_avatar_label or not profile_avatar_panel:
        return

    if not current_user:
        profile_change_pic_btn.configure(state="disabled")
        profile_avatar_panel.grid_remove()
        profile_avatar_label.configure(image="", text="")
        profile_avatar_label.image = None  # type: ignore[attr-defined]
        return

    avatar = load_avatar(current_user, size)
    if avatar:
        profile_avatar_label.configure(image=avatar, text="")
        profile_avatar_label.image = avatar  # type: ignore[attr-defined]
    else:
        profile_avatar_label.configure(image="", text="No photo")
        profile_avatar_label.image = None  # type: ignore[attr-defined]

    profile_avatar_panel.grid()
    profile_change_pic_btn.configure(state="normal")


def change_profile_picture(
    *,
    current_user: Optional[str],
    require_login: Callable[[str], bool],
    copy_image_to_profile_pics: Callable[[Optional[str]], Optional[str]],
    users: UserDict,
    base_dir: str,
    profile_pics_dir: str,
    default_profile_pic: Optional[str],
    invalidate_avatar: Callable[[str], None],
    persist: Callable[[], None],
    update_display: Callable[[], None],
    render_dm: Optional[Callable[[], None]] = None,
    render_inspected_profile: Optional[Callable[[], None]] = None,
    filedialog_module: Any = filedialog,
) -> None:
    if not require_login("change your profile picture"):
        return

    path = filedialog_module.askopenfilename(
        title="Choose profile picture",
        filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.gif;*.webp"), ("All files", "*.*")],
    )
    rel_path = copy_image_to_profile_pics(path)
    if not current_user or not rel_path:
        return

    prev_rel = users[current_user].get("profile_picture")
    if prev_rel:
        prev_abs = prev_rel if os.path.isabs(prev_rel) else os.path.join(base_dir, prev_rel)
        new_abs = rel_path if os.path.isabs(rel_path) else os.path.join(base_dir, rel_path)
        default_abs = (
            default_profile_pic
            if default_profile_pic and os.path.isabs(default_profile_pic)
            else os.path.join(base_dir, default_profile_pic) if default_profile_pic else ""
        )
        try:
            prev_abs_real = os.path.abspath(prev_abs)
            new_abs_real = os.path.abspath(new_abs)
            profile_dir_abs = os.path.abspath(profile_pics_dir)
            if (
                prev_abs_real != new_abs_real
                and prev_abs_real != os.path.abspath(default_abs)
                and os.path.commonpath([prev_abs_real, profile_dir_abs]) == profile_dir_abs
                and os.path.exists(prev_abs_real)
            ):
                os.remove(prev_abs_real)
        except Exception:
            pass

    users[current_user]["profile_picture"] = rel_path
    invalidate_avatar(current_user)
    persist()
    update_display()
    if render_dm:
        render_dm()
    if render_inspected_profile:
        render_inspected_profile()


def follow_user(
    *,
    follower: str,
    target: str,
    users: UserDict,
    persist: Optional[Callable[[], None]] = None,
    notify: Optional[NotificationCallback] = None,
) -> bool:
    if follower == target:
        return False

    follower_rec = users.setdefault(follower, {})
    target_rec = users.setdefault(target, {})

    following = follower_rec.setdefault("following", [])
    followers = target_rec.setdefault("followers", [])

    changed = False
    if target not in following:
        following.append(target)
        changed = True
    if follower not in followers:
        followers.append(follower)
        changed = True

    if changed and notify:
        notify(target, f"@{follower} started following you", {"type": "follow", "from": follower})

    if changed and persist:
        persist()

    return changed


def unfollow_user(
    *,
    follower: str,
    target: str,
    users: UserDict,
    persist: Optional[Callable[[], None]] = None,
) -> bool:
    if follower == target:
        return False

    follower_rec = users.setdefault(follower, {})
    target_rec = users.setdefault(target, {})

    following = follower_rec.setdefault("following", [])
    followers = target_rec.setdefault("followers", [])

    changed = False
    if target in following:
        following.remove(target)
        changed = True
    if follower in followers:
        followers.remove(follower)
        changed = True

    if changed and persist:
        persist()

    return changed


def render_inspected_profile(
    *,
    inspected_user: Optional[str],
    current_user: Optional[str],
    users: UserDict,
    posts: list[PostDict],
    palette: Palette,
    total_likes_for: Callable[[str], int],
    inspect_header: ctk.CTkLabel,
    inspect_info: ctk.CTkLabel,
    inspect_posts: ctk.CTkScrollableFrame,
    inspect_follow_btn: ctk.CTkButton,
    inspect_message_btn: ctk.CTkButton,
    inspect_stats_labels: Optional[dict[str, ctk.CTkLabel]] = None,
    post_renderer: Optional[PostRenderer],
    open_dm_with: Optional[Callable[[str], None]] = None,
    follow_callback: Optional[Callable[[str], None]] = None,
    unfollow_callback: Optional[Callable[[str], None]] = None,
    empty_message: str = "No posts yet.",
) -> None:
    muted = palette.get("muted", "#94a3b8")
    accent = palette.get("accent", "#4c8dff")
    accent_hover = palette.get("accent_hover", "#3b6dd6")
    danger = palette.get("danger", "#ef4444")
    danger_hover = palette.get("danger_hover", "#dc2626")
    text = palette.get("text", "#e2e8f0")

    _clear_children(inspect_posts)

    inspect_header.configure(text="Profile", text_color=text)
    inspect_info.configure(text="", text_color=muted)
    inspect_follow_btn.configure(state="disabled", text="Follow", fg_color=accent, hover_color=accent_hover)
    inspect_message_btn.configure(state="disabled")

    if not inspected_user:
        inspect_info.configure(text="No profile selected.", text_color=muted)
        return

    info = users.get(inspected_user)
    if not info:
        inspect_info.configure(text="User not found.", text_color=muted)
        return

    followers = len(info.get("followers", []))
    following = len(info.get("following", []))
    user_posts = [(idx, post) for idx, post in enumerate(posts) if post.get("author") == inspected_user]
    likes = total_likes_for(inspected_user)
    achievements = compute_achievement_progress(
        inspected_user,
        users=users,
        posts=posts,
        like_counter=total_likes_for,
    )
    achievements_preview = "Achievements: None yet"
    if achievements:
        completed = [item for item in achievements if item.get("complete")]
        if completed:
            top_names = ", ".join(item.get("name", "") for item in completed[:3] if item.get("name"))
            achievements_preview = f"Achievements: {top_names or len(completed)} completed"
        else:
            achievement = achievements[0]
            achievements_preview = f"Achievements: {achievement.get('name', 'In progress')}"

    inspect_header.configure(text=f"@{inspected_user}", text_color=text)
    details: list[str] = []
    registered = info.get("registered_at", "Unknown")
    details.append(f"Registered: {registered}")
    bio = info.get("bio")
    if bio:
        details.append(f"Bio: {bio}")
    location = info.get("location")
    if location:
        details.append(f"Location: {location}")
    website = info.get("website")
    if website:
        details.append(f"Website: {website}")
    details.append(achievements_preview)
    inspect_info.configure(text="\n".join(details), text_color=muted, justify="left", anchor="w")

    if inspect_stats_labels:
        stats_payload = {
            "followers": followers,
            "following": following,
            "posts": len(user_posts),
            "likes": likes,
        }
        for key, label in inspect_stats_labels.items():
            if isinstance(label, ctk.CTkLabel):
                label.configure(text=str(stats_payload.get(key, 0)))

    if current_user and inspected_user != current_user:
        is_following = inspected_user in users.get(current_user, {}).get("following", [])
        if is_following:
            inspect_follow_btn.configure(
                state="normal",
                text="Unfollow",
                fg_color=danger,
                hover_color=danger_hover,
                command=(lambda u=inspected_user: unfollow_callback(u)) if unfollow_callback else None,
            )
        else:
            inspect_follow_btn.configure(
                state="normal",
                text="Follow",
                fg_color=accent,
                hover_color=accent_hover,
                command=(lambda u=inspected_user: follow_callback(u)) if follow_callback else None,
            )
        if open_dm_with:
            inspect_message_btn.configure(
                state="normal",
                fg_color=accent,
                hover_color=accent_hover,
                command=lambda u=inspected_user: open_dm_with(u),
            )
    else:
        inspect_follow_btn.configure(state="disabled", text="Follow")
        inspect_message_btn.configure(state="disabled")

    if not user_posts:
        ctk.CTkLabel(
            inspect_posts,
            text=empty_message,
            text_color=muted,
            anchor="w",
        ).grid(sticky="w", padx=20, pady=20)
        return

    if not post_renderer:
        return

    for idx, post in reversed(user_posts):
        post_renderer(idx, post)