from __future__ import annotations

import atexit
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional
from uuid import uuid4

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

try:
	import winsound
except ImportError:  # pragma: no cover - platform specific
	winsound = None  # type: ignore

from DM import convo_id, render_dm, render_dm_sidebar
from data_layer import (
	BASE_DIR,
	DEFAULT_PROFILE_PIC,
	MEDIA_DIR,
	PROFILE_PICS_DIR,
	messages,
	now_ts,
	persist,
	posts,
	videos,
	stories,
	group_chats,
	users,
	scheduled_posts,
	purge_expired_stories,
	STORY_TTL_SECONDS,
	set_server_config,
	was_last_remote_sync_successful,
	last_remote_sync_error,
	upload_media_asset,
	ensure_media_local,
	get_remembered_user,
	remember_user,
)
from global_state.helpers import (
	configure_helpers,
	notify_followers,
	notify_mentions,
	push_notification,
	require_login,
	toggle_post_reaction,
	total_likes_for,
)
from achievements import ACHIEVEMENTS, compute_achievement_progress
from Media import copy_image_to_profile_pics, load_image_for_tk as media_load_image, open_image
from Media import copy_file_to_media
from Profile import (
    change_profile_picture,
    invalidate_profile_avatar,
    load_profile_avatar,
	profile_image_path,
    render_inspected_profile,
    update_profile_avatar_display,
)
from Auth import FeedCallbacks, FeedState, render_feed, render_post_card, render_profile

# Import component-based architecture
from ui_components import (
    component_registry,
    MessageListComponent,
    NotificationListComponent,
    FeedComponent,
    NotificationBadgeComponent,
)

try:
	from PIL import Image as _Image, ImageDraw as _ImageDraw, ImageOps as _ImageOps, ImageTk as _ImageTk  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - optional dependency
	Image = None  # type: ignore
	ImageDraw = None  # type: ignore
	ImageOps = None  # type: ignore
	ImageTk = None  # type: ignore
else:
	Image = _Image
	ImageDraw = _ImageDraw
	ImageOps = _ImageOps
	ImageTk = _ImageTk

try:
	import imageio  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
	imageio = None  # type: ignore


Palette = dict[str, str]

MAX_ATTACHMENT_BYTES = 200 * 1024 * 1024  # 200 MB limit per file

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
_AUDIO_EXTS = {".mp3", ".wav", ".aac", ".flac", ".ogg"}
_DOCUMENT_EXTS = {
	".pdf",
	".doc",
	".docx",
	".ppt",
	".pptx",
	".xls",
	".xlsx",
	".txt",
	".md",
	".csv",
	".zip",
	".rar",
	".7z",
}
MESSAGE_REACTIONS: list[str] = ["👍", "❤️", "😂"]
GROUP_INVITE_LINK_PREFIX = "https://social.local/invite/"
PROFILE_SUGGESTION_LIMIT = 5
TIMELINE_MAX_ITEMS = 6
ACHIEVEMENT_IDS: list[str] = [item["id"] for item in ACHIEVEMENTS]
ACHIEVEMENT_COUNT = len(ACHIEVEMENTS)
_INVITE_TOKEN_CHARS = set("0123456789ABCDEF")
@dataclass
class _UIState:
	current_user: Optional[str] = None
	inspected_user: Optional[str] = None
	active_dm_user: Optional[str] = None
	active_dm_conversation: Optional[str] = None
	active_view: str = "home"
	dirty_views: set[str] = field(default_factory=set)
	feed_state: FeedState = field(
		default_factory=lambda: FeedState(
			current_user=None,
			expanded_replies=set(),
			editing_post_index=None,
			editing_reply_target=None,
			reply_input_target=None,
			focus_post_id=None,
			focus_reply_id=None,
		)
	)
	search_query: str = ""
	search_results: list[str] = field(default_factory=list)


_ui_state = _UIState()
_palette: Palette = {}
_frames: dict[str, ctk.CTkFrame] = {}
_show_frame_cb: Optional[Callable[[str], None]] = None

_nav_controls: dict[str, ctk.CTkButton] = {}

# Performance optimization: cache frequently computed data
_view_cache: dict[str, dict] = {
	"home": {"last_render": 0, "post_count": 0},
	"profile": {"last_render": 0, "user": None},
	"search": {"last_render": 0, "query": ""},
	"dm": {"last_render": 0, "conversation": None},
	"notifications": {"last_render": 0, "count": 0},
	"achievements": {"last_render": 0, "user": None},
}

_view_signatures: dict[str, Any] = {}

# Component-based architecture instances
_notification_list_component: Optional[NotificationListComponent] = None
_notification_badge_component: Optional[NotificationBadgeComponent] = None
_message_list_component: Optional[MessageListComponent] = None
_feed_component: Optional[FeedComponent] = None


def _stable_signature_digest(payload: Any) -> str:
	"""Return a short, stable digest for arbitrary payloads."""
	try:
		serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
	except TypeError:
		serialized = repr(payload)
	return hashlib.sha1(serialized.encode("utf-8", "ignore")).hexdigest()[:16]


def _limit_iterable(items: list[Any], limit: int) -> list[Any]:
	return items[:limit] if len(items) > limit else items


def _achievement_progress_for(username: Optional[str]) -> list[dict[str, Any]]:
	return compute_achievement_progress(
		username,
		users=users,
		posts=posts,
		like_counter=total_likes_for,
	)


def _achievement_signature(progress: list[dict[str, Any]]) -> tuple:
	return tuple(
		(
			item.get("id"),
			bool(item.get("complete")),
			int(item.get("current", 0)),
		)
		for item in progress
	)


def _render_profile_achievements_preview(
	container: Optional[ctk.CTkFrame],
	progress: list[dict[str, Any]],
	*,
	text_color: str,
	muted_color: str,
	accent_color: str,
) -> None:
	if not container:
		return
	for child in container.winfo_children():
		child.destroy()

	if not progress:
		ctk.CTkLabel(
			container,
			text="No achievements tracked yet.",
			text_color=muted_color,
			anchor="w",
		).grid(sticky="we")
		return

	preview_items = progress[:3]
	for idx, item in enumerate(preview_items):
		tile = ctk.CTkFrame(container, fg_color="transparent")
		tile.grid(row=idx, column=0, sticky="we", pady=(0, 8))
		tile.grid_columnconfigure(0, weight=1)

		title = ctk.CTkLabel(
			tile,
			text=item.get("name", "Achievement"),
			text_color=text_color if not item.get("complete") else accent_color,
			font=ctk.CTkFont(size=12, weight="bold"),
			anchor="w",
		)
		title.grid(row=0, column=0, sticky="w")

		subtext = f"{int(item.get('current', 0))}/{int(item.get('target', 0))}"
		ctk.CTkLabel(
			tile,
			text=subtext,
			text_color=muted_color,
			font=ctk.CTkFont(size=11),
			anchor="w",
		).grid(row=1, column=0, sticky="w", pady=(2, 0))

		bar = ctk.CTkProgressBar(
			tile,
			fg_color=_palette.get("surface", "#111b2e"),
			progress_color=accent_color,
			height=8,
		)
		bar.grid(row=2, column=0, sticky="we", pady=(6, 0))
		percent_value = max(0.0, min(1.0, float(item.get("percent", 0)) / 100))
		bar.set(percent_value)

		status_text = "Complete" if item.get("complete") else f"{int(item.get('percent', 0))}%"
		ctk.CTkLabel(
			tile,
			text=status_text,
			text_color=accent_color if item.get("complete") else muted_color,
			font=ctk.CTkFont(size=10, slant="italic"),
			anchor="w",
		).grid(row=3, column=0, sticky="w", pady=(4, 0))

	if len(progress) > len(preview_items):
		ctk.CTkLabel(
			container,
			text="View all achievements to see more milestones.",
			text_color=muted_color,
			font=ctk.CTkFont(size=10, slant="italic"),
			anchor="w",
		).grid(row=len(preview_items), column=0, sticky="w")


def _render_achievements_view() -> None:
	list_frame: Optional[ctk.CTkScrollableFrame] = _achievements_widgets.get("list")
	summary_label: Optional[ctk.CTkLabel] = _achievements_widgets.get("summary")
	if not list_frame or not summary_label:
		return
	for child in list_frame.winfo_children():
		child.destroy()

	user = _ui_state.current_user
	accent = _palette.get("accent", "#4c8dff")
	muted = _palette.get("muted", "#94a3b8")
	text_color = _palette.get("text", "#e2e8f0")
	surface = _palette.get("card", "#18263f")

	if not user:
		summary_label.configure(text="Sign in to track achievements.", text_color=muted)
		return

	progress = _achievement_progress_for(user)
	if not progress:
		summary_label.configure(
			text="Start creating posts and connecting to unlock your first achievement.",
			text_color=muted,
		)
		return

	completed = sum(1 for item in progress if item.get("complete"))
	summary_label.configure(
		text=f"{completed} of {ACHIEVEMENT_COUNT} achievements complete.",
		text_color=muted,
	)

	for idx, item in enumerate(progress):
		row = ctk.CTkFrame(list_frame, corner_radius=12, fg_color=surface)
		row.grid(row=idx, column=0, sticky="we", padx=12, pady=(0, 8))
		row.grid_columnconfigure(0, weight=1)

		title = ctk.CTkLabel(
			row,
			text=item.get("name", "Achievement"),
			text_color=text_color if not item.get("complete") else accent,
			font=ctk.CTkFont(size=14, weight="bold"),
			anchor="w",
		)
		title.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))

		description = item.get("description") or ""
		if description:
			ctk.CTkLabel(
				row,
				text=str(description),
				text_color=muted,
				font=ctk.CTkFont(size=12),
				anchor="w",
				wraplength=520,
			).grid(row=1, column=0, sticky="w", padx=12)

		target = int(item.get("target", 0) or 0)
		current = int(item.get("current", 0) or 0)
		progress_label = ctk.CTkLabel(
			row,
			text=f"{current} / {target}",
			text_color=text_color,
			font=ctk.CTkFont(size=12, weight="bold"),
			anchor="w",
		)
		progress_label.grid(row=2, column=0, sticky="w", padx=12, pady=(8, 0))

		bar = ctk.CTkProgressBar(
			row,
			fg_color=_palette.get("surface", "#111b2e"),
			progress_color=accent,
			height=10,
		)
		bar.grid(row=3, column=0, sticky="we", padx=12, pady=(4, 4))
		percent_value = max(0.0, min(1.0, float(item.get("percent", 0)) / 100))
		bar.set(percent_value)

		status = "Complete" if item.get("complete") else f"{int(item.get('percent', 0))}%"
		ctk.CTkLabel(
			row,
			text=status,
			text_color=accent if item.get("complete") else muted,
			font=ctk.CTkFont(size=11, slant="italic"),
			anchor="w",
		).grid(row=4, column=0, sticky="w", padx=12, pady=(0, 10))

	list_frame.grid_columnconfigure(0, weight=1)


def _compute_view_signature(view: str) -> Optional[tuple]:
	feed_state = _ui_state.feed_state
	feed_state_marker = (
		tuple(sorted(feed_state.expanded_replies)),
		feed_state.editing_post_index,
		feed_state.editing_reply_target,
		feed_state.reply_input_target,
		feed_state.focus_post_id,
		feed_state.focus_reply_id,
	)
	if view == "home":
		post_entries: list[tuple] = []
		for post in _limit_iterable(posts, 24):
			if not isinstance(post, dict):
				continue
			replies_list = post.get("replies", [])
			if not isinstance(replies_list, list):
				replies_list = []
			reply_entries = []
			for reply in _limit_iterable(replies_list, 12):
				if not isinstance(reply, dict):
					continue
				reply_entries.append(
					(
						reply.get("id") or _stable_signature_digest((reply.get("author"), reply.get("content"))),
						reply.get("author"),
						reply.get("created_at"),
						reply.get("edited"),
						reply.get("edited_at"),
						len(reply.get("liked_by", [])) if isinstance(reply.get("liked_by"), list) else 0,
						len(reply.get("disliked_by", [])) if isinstance(reply.get("disliked_by"), list) else 0,
					),
				)
			post_entries.append(
				(
					post.get("id") or _stable_signature_digest((post.get("author"), post.get("content"))),
					post.get("author"),
					post.get("created_at"),
					post.get("edited"),
					post.get("edited_at"),
					len(replies_list),
					post.get("likes"),
					post.get("dislikes"),
					_stable_signature_digest(post.get("content", "")),
					tuple(reply_entries),
				),
			)
		return (len(posts), tuple(post_entries), feed_state_marker)
	if view == "profile":
		user = _ui_state.current_user or ""
		record = users.get(user, {}) if user else {}
		if not isinstance(record, dict):
			record = {}
		followers_list = record.get("followers", []) if isinstance(record.get("followers"), list) else []
		following_list = record.get("following", []) if isinstance(record.get("following"), list) else []
		progress = _achievement_progress_for(user) if user else []
		achievement_entries = _achievement_signature(progress)
		followers = tuple(sorted(_limit_iterable(followers_list, 20)))
		following = tuple(sorted(_limit_iterable(following_list, 20)))
		post_count = sum(1 for post in posts if isinstance(post, dict) and post.get("author") == user)
		return (
			user,
			_stable_signature_digest((record.get("bio"), record.get("location"), record.get("website"))),
			len(followers_list),
			len(following_list),
			post_count,
			achievement_entries,
			followers,
			following,
			feed_state_marker,
		)
	if view == "notifications":
		user = _ui_state.current_user or ""
		if not user:
			return ("", 0)
		record = users.get(user, {}) if user else {}
		if not isinstance(record, dict):
			record = {}
		notes = record.get("notifications", [])
		if not isinstance(notes, list):
			notes = []
		note_entries = []
		for note in _limit_iterable(list(reversed(notes)), 24):
			if not isinstance(note, dict):
				continue
			note_entries.append(
				(
					note.get("message"),
					note.get("time"),
					_stable_signature_digest(note.get("meta")),
				),
			)
		return (user, len(notes), tuple(note_entries))
	if view == "inspect_profile":
		target = _ui_state.inspected_user or ""
		record = users.get(target, {}) if target else {}
		if not isinstance(record, dict):
			record = {}
		followers_list = record.get("followers", []) if isinstance(record.get("followers"), list) else []
		following_list = record.get("following", []) if isinstance(record.get("following"), list) else []
		followers = tuple(sorted(_limit_iterable(followers_list, 20)))
		following = tuple(sorted(_limit_iterable(following_list, 20)))
		post_count = sum(1 for post in posts if isinstance(post, dict) and post.get("author") == target)
		return (
			target,
			len(followers_list),
			len(following_list),
			post_count,
			followers,
			following,
			_stable_signature_digest(record.get("bio")),
		)
	if view == "videos":
		video_entries = []
		for video in _limit_iterable(videos, 24):
			if not isinstance(video, dict):
				continue
			video_entries.append(
				(
					video.get("id") or _stable_signature_digest((video.get("path"), video.get("author"))),
					video.get("author"),
					video.get("created_at"),
					_stable_signature_digest(video.get("caption")),
					len(video.get("comments", [])) if isinstance(video.get("comments"), list) else 0,
					video.get("likes"),
					video.get("dislikes"),
				),
			)
		return (len(videos), tuple(video_entries))
	if view == "search":
		return (
			_stable_signature_digest(_ui_state.search_query),
			tuple(_limit_iterable(_ui_state.search_results, 20)),
		)
	if view == "dm":
		return None
	return None

_nav_icon_palette: Palette = {}
_nav_icon_bases: dict[str, "Image.Image"] = {}  # type: ignore[name-defined]
_nav_icon_variants: dict[str, dict[str, ctk.CTkImage]] = {}
_nav_buttons_for_icons: dict[str, ctk.CTkButton] = {}
_nav_button_icon_keys: dict[str, str] = {}
_nav_icon_overrides: dict[str, str] = {}
_nav_active_nav_key: Optional[str] = None

_NAV_ICON_SIZE: tuple[int, int] = (64, 64)
_NAV_ICON_DISPLAY_SIZE: tuple[int, int] = (36, 36)
_NAV_HIGHLIGHT_KEYS = {"home", "videos", "search", "profile", "notifications", "messages"}
_NAV_ALERT_ICON_MAP = {"notifications": "notifications_alert"}
_NAV_PRESERVE_ICON_KEYS = {"profile"}

_BUTTON_ICON_FILES = {
	"home": Path(BASE_DIR) / "media" / "Buttons" / "Home_button_icon.png",
	"videos": Path(BASE_DIR) / "media" / "Buttons" / "Video_page_icon_button.png",
	"messages": Path(BASE_DIR) / "media" / "Buttons" / "Message_button_icon.png",
	"notifications": Path(BASE_DIR) / "media" / "Buttons" / "Notfication_not_triggered.png",
	"notifications_alert": Path(BASE_DIR) / "media" / "Buttons" / "Notfication_triggered.png",
	"profile": Path(BASE_DIR) / "media" / "Buttons" / "Profile_icon.png",
	"sign_out": Path(BASE_DIR) / "media" / "Buttons" / "Sign_out_button.png",
	"exit": Path(BASE_DIR) / "media" / "Buttons" / "turn-off.png",
}

_COMMENT_ICON_PATH = Path(BASE_DIR) / "media" / "Buttons" / "Comment_button.png"
_LIKE_ICON_PATH = Path(BASE_DIR) / "media" / "Buttons" / "like-icon.png"
_DISLIKE_ICON_PATH = Path(BASE_DIR) / "media" / "Buttons" / "dislike_icon.png"

_remote_sync_alerts: dict[str, str] = {}


def _round_rect(box: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
	x1, y1, x2, y2 = box
	return (
		int(round(x1)),
		int(round(y1)),
		int(round(x2)),
		int(round(y2)),
	)


def _round_points(points: list[tuple[float, float]]) -> list[tuple[int, int]]:
	return [(int(round(x)), int(round(y))) for x, y in points]


def _ellipsize(text: str, limit: int) -> str:
	text = (text or "").strip()
	if len(text) <= limit:
		return text
	return text[: max(1, limit - 1)] + "…"


def _mask_profile(draw: "ImageDraw.ImageDraw", size: tuple[int, int]) -> None:  # type: ignore[name-defined]
	w, h = size
	head_r = 0.22 * min(w, h)
	cx, cy = 0.5 * w, 0.36 * h
	draw.ellipse(_round_rect((cx - head_r, cy - head_r, cx + head_r, cy + head_r)), fill=255)
	body_r = 0.36 * min(w, h)
	draw.ellipse(
		_round_rect((cx - body_r, 0.58 * h - body_r, cx + body_r, 0.90 * h + body_r)),
		fill=255,
	)
	draw.ellipse(
		_round_rect((cx - body_r * 0.7, 0.68 * h - body_r * 0.7, cx + body_r * 0.7, 0.92 * h)),
		fill=0,
	)


def _mask_signin(draw: "ImageDraw.ImageDraw", size: tuple[int, int]) -> None:  # type: ignore[name-defined]
	w, h = size
	head_r = 0.20 * min(w, h)
	cx, cy = 0.38 * w, 0.38 * h
	draw.ellipse(_round_rect((cx - head_r, cy - head_r, cx + head_r, cy + head_r)), fill=255)
	bust = [
		(0.18 * w, 0.72 * h),
		(0.58 * w, 0.72 * h),
		(0.58 * w, 0.60 * h),
		(0.18 * w, 0.60 * h),
	]
	draw.polygon(_round_points(bust), fill=255)
	draw.rectangle(_round_rect((0.22 * w, 0.60 * h, 0.54 * w, 0.86 * h)), fill=255)
	draw.rounded_rectangle(
		_round_rect((0.60 * w, 0.38 * h, 0.86 * w, 0.90 * h)),
		radius=int(0.18 * w),
		outline=255,
		width=int(max(2, 0.08 * w)),
	)
	draw.line(
		_round_points([(0.73 * w, 0.50 * h), (0.73 * w, 0.78 * h)]),
		fill=255,
		width=int(0.10 * w),
	)
	draw.line(
		_round_points([(0.64 * w, 0.64 * h), (0.82 * w, 0.64 * h)]),
		fill=255,
		width=int(0.10 * w),
	)


def _mask_sun(draw: "ImageDraw.ImageDraw", size: tuple[int, int]) -> None:  # type: ignore[name-defined]
	w, h = size
	r = 0.26 * min(w, h)
	cx, cy = 0.5 * w, 0.5 * h
	draw.ellipse(_round_rect((cx - r, cy - r, cx + r, cy + r)), fill=255)
	for angle in range(0, 360, 45):
		rad = math.radians(angle)
		inner = (cx + r * 0.9 * math.cos(rad), cy + r * 0.9 * math.sin(rad))
		outer = (cx + r * 1.45 * math.cos(rad), cy + r * 1.45 * math.sin(rad))
		draw.line(_round_points([inner, outer]), fill=255, width=int(max(2, 0.08 * w)))


def _mask_moon(draw: "ImageDraw.ImageDraw", size: tuple[int, int]) -> None:  # type: ignore[name-defined]
	w, h = size
	r = 0.32 * min(w, h)
	cx, cy = 0.52 * w, 0.48 * h
	draw.ellipse(_round_rect((cx - r, cy - r, cx + r, cy + r)), fill=255)
	draw.ellipse(
		_round_rect((cx - r * 0.6, cy - r * 1.2, cx + r * 1.1, cy + r * 0.4)),
		fill=0,
	)


def _mask_search(draw: "ImageDraw.ImageDraw", size: tuple[int, int]) -> None:  # type: ignore[name-defined]
	w, h = size
	r = 0.3 * min(w, h)
	cx, cy = 0.48 * w, 0.45 * h
	draw.ellipse(_round_rect((cx - r, cy - r, cx + r, cy + r)), fill=255)
	width = int(max(3, 0.12 * min(w, h)))
	start = (cx + r * 0.55, cy + r * 0.55)
	end = (cx + r * 1.4, cy + r * 1.4)
	draw.line(_round_points([start, end]), fill=255, width=width)
	cap = width / 2
	draw.ellipse(_round_rect((end[0] - cap, end[1] - cap, end[0] + cap, end[1] + cap)), fill=255)


_ICON_BUILDERS: dict[str, Callable[["ImageDraw.ImageDraw", tuple[int, int]], None]] = {  # type: ignore[name-defined]
	"profile": _mask_profile,
	"signin": _mask_signin,
	"search": _mask_search,
	"theme_sun": _mask_sun,
	"theme_moon": _mask_moon,
}


def _load_icon_from_path(path: Path) -> Optional["Image.Image"]:  # type: ignore[name-defined]
	if Image is None:
		return None
	if not path.exists():
		return None
	try:
		with Image.open(path) as source:
			icon = source.convert("RGBA")
	except OSError:
		return None
	resampling = getattr(Image, "Resampling", None)
	method = getattr(resampling, "LANCZOS", getattr(Image, "LANCZOS", getattr(Image, "BILINEAR", 2)))
	if ImageOps is not None:
		fitted = ImageOps.contain(icon, _NAV_ICON_SIZE, method=method)
	else:
		fitted = icon.resize(_NAV_ICON_SIZE, method)
	canvas = Image.new("RGBA", _NAV_ICON_SIZE, (0, 0, 0, 0))
	offset = (
		(_NAV_ICON_SIZE[0] - fitted.width) // 2,
		(_NAV_ICON_SIZE[1] - fitted.height) // 2,
	)
	canvas.paste(fitted, offset, fitted)
	return canvas


def _ensure_nav_icon_assets() -> None:
	if _nav_icon_bases:
		return
	if Image is None:
		return
	for key, path in _BUTTON_ICON_FILES.items():
		loaded = _load_icon_from_path(path)
		if loaded is not None:
			_nav_icon_bases[key] = loaded
	if ImageDraw is None:
		return
	for name, builder in _ICON_BUILDERS.items():
		if name in _nav_icon_bases:
			continue
		mask = Image.new("L", _NAV_ICON_SIZE, 0)
		drawer = ImageDraw.Draw(mask)
		builder(drawer, _NAV_ICON_SIZE)
		icon = Image.new("RGBA", _NAV_ICON_SIZE, (255, 255, 255, 0))
		icon.putalpha(mask)
		_nav_icon_bases[name] = icon


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
	hex_value = value.lstrip("#")
	if len(hex_value) == 3:
		hex_value = "".join(ch * 2 for ch in hex_value)
	r = int(hex_value[0:2], 16)
	g = int(hex_value[2:4], 16)
	b = int(hex_value[4:6], 16)
	return (r, g, b)


def _tint_icon(base: "Image.Image", color_hex: str) -> "Image.Image":  # type: ignore[name-defined]
	r, g, b = _hex_to_rgb(color_hex)
	colored = Image.new("RGBA", base.size, (0, 0, 0, 0))
	mask = base.split()[-1]
	solid = Image.new("RGBA", base.size, (r, g, b, 255))
	colored.paste(solid, mask=mask)
	return colored


def _make_ctk_image(pil_image: "Image.Image", size: tuple[int, int] = _NAV_ICON_DISPLAY_SIZE) -> ctk.CTkImage:  # type: ignore[name-defined]
	return ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=size)


def _nav_hover_color() -> str:
	if _nav_icon_palette:
		return _nav_icon_palette.get("card", "#1f2937")
	return "#1f2937"


def _apply_nav_icon_images() -> None:
	if not _nav_buttons_for_icons:
		return
	hover_color = _nav_hover_color()
	border_color = _nav_icon_palette.get("accent", "#2563eb")
	for key, btn in _nav_buttons_for_icons.items():
		variants = _nav_icon_variants.get(key, {})
		is_active = key == _nav_active_nav_key and key in _NAV_HIGHLIGHT_KEYS
		override = _nav_icon_overrides.get(key)
		image = None
		if override and override in variants:
			image = variants.get(override)
		elif is_active:
			image = variants.get("active")
		else:
			image = variants.get("normal")
		config: dict[str, Any] = {
			"fg_color": "transparent",
			"hover_color": hover_color,
			"border_width": 2 if is_active else 0,
			"border_color": border_color,
		}
		if image is not None:
			config["image"] = image
			config["text"] = ""
		btn.configure(**config)


def _refresh_nav_icons() -> None:
	if not _nav_button_icon_keys:
		return
	_ensure_nav_icon_assets()
	if not _nav_icon_bases:
		return
	_nav_icon_variants.clear()
	text_color = _nav_icon_palette.get("text", "#f8fafc")
	accent_color = _nav_icon_palette.get("accent", "#2563eb")
	for key, icon_key in _nav_button_icon_keys.items():
		base = _nav_icon_bases.get(icon_key)
		if base is None:
			continue
		variants: dict[str, ctk.CTkImage] = {}
		if icon_key in _NAV_PRESERVE_ICON_KEYS:
			variants["normal"] = _make_ctk_image(base)
			variants["active"] = _make_ctk_image(base)
		else:
			variants["normal"] = _make_ctk_image(_tint_icon(base, text_color))
			variants["active"] = _make_ctk_image(_tint_icon(base, accent_color))
		alert_key = _NAV_ALERT_ICON_MAP.get(key)
		if alert_key:
			alert_base = _nav_icon_bases.get(alert_key)
			if alert_base is not None:
				variants["alert"] = _make_ctk_image(alert_base)
		_nav_icon_variants[key] = variants
	_apply_nav_icon_images()


def _set_active_nav(key: Optional[str]) -> None:
	global _nav_active_nav_key
	_nav_active_nav_key = key
	_apply_nav_icon_images()


def set_nav_palette(palette: Palette) -> None:
	global _nav_icon_palette
	_nav_icon_palette = dict(palette)
	if _nav_button_icon_keys:
		_refresh_nav_icons()
	else:
		_apply_nav_icon_images()


def create_nav_button(
	key: str,
	icon_key: str,
	*,
	parent: ctk.CTkFrame,
	row: int,
	command: Optional[Callable[[], None]] = None,
	pady: tuple[int, int] | int = 6,
) -> ctk.CTkButton:
	btn = ctk.CTkButton(
		parent,
		text="",
		width=64,
		height=64,
		corner_radius=18,
		fg_color="transparent",
		hover_color=_nav_hover_color(),
		command=command,
	)
	btn.grid(row=row, column=0, padx=12, pady=pady)
	_nav_buttons_for_icons[key] = btn
	_nav_button_icon_keys[key] = icon_key
	return btn


def refresh_nav_icons() -> None:
	_refresh_nav_icons()


def set_active_nav(key: Optional[str]) -> None:
	_set_active_nav(key)


def set_nav_icon_override(key: str, override: Optional[str]) -> None:
	if override:
		_nav_icon_overrides[key] = override
	else:
		_nav_icon_overrides.pop(key, None)
	_apply_nav_icon_images()


def set_nav_signed_in_state(is_signed_in: bool) -> None:
	target = "sign_out" if is_signed_in else "signin"
	if _nav_button_icon_keys.get("signin") == target:
		return
	_nav_button_icon_keys["signin"] = target
	_refresh_nav_icons()


def set_nav_icon_key(key: str, icon_key: str) -> None:
	if _nav_button_icon_keys.get(key) == icon_key:
		return
	_nav_button_icon_keys[key] = icon_key
	_refresh_nav_icons()


def set_nav_notifications_alert(active: bool) -> None:
	set_nav_icon_override("notifications", "alert" if active else None)

_home_widgets: dict[str, Any] = {}
_videos_widgets: dict[str, Any] = {}
_video_cards: dict[str, dict[str, Any]] = {}
_video_focus_id: Optional[str] = None
_video_focus_open_comments = False
_comment_icon_image: Optional[ctk.CTkImage] = None
_reaction_icon_cache: dict[tuple[str, tuple[int, int]], Optional[ctk.CTkImage]] = {}
_video_fullscreen_windows: dict[str, dict[str, Any]] = {}
_post_attachments: list[dict[str, Any]] = []
_dm_draft_attachments: list[dict[str, Any]] = []
_profile_widgets: dict[str, Any] = {}
_notifications_widgets: dict[str, Any] = {}
_inspect_widgets: dict[str, Any] = {}
_dm_widgets: dict[str, Any] = {}
_group_modal_widgets: dict[str, Any] = {}
_search_widgets: dict[str, Any] = {}
_achievements_widgets: dict[str, Any] = {}
_dm_sidebar_dirty: bool = True
_dm_last_rendered_conversation: Optional[str] = None
_render_after_handles: dict[str, str] = {}
_search_after_handle: Optional[str] = None
_auth_widgets: dict[str, Any] = {}
_dm_typing_state: dict[str, dict[str, float]] = {}
_dm_typing_after_handle: Optional[str] = None
_dm_typing_local_events: dict[str, float] = {}
_dm_typing_hint_cache: dict[str, str] = {}
_last_activity_touch: float = 0.0

_MENTION_PATTERN = re.compile(r"@([A-Za-z0-9_]+)")
_HASHTAG_PATTERN = re.compile(r"#([A-Za-z0-9_]{2,30})")
_REACTION_ICON_SIZE: tuple[int, int] = (40, 40)

def _ensure_comment_icon(size: tuple[int, int] = (40, 40)) -> Optional[ctk.CTkImage]:
	global _comment_icon_image
	if _comment_icon_image is not None:
		return _comment_icon_image
	if Image is None or not _COMMENT_ICON_PATH.exists():
		return None
	try:
		with Image.open(_COMMENT_ICON_PATH) as source:  # type: ignore[name-defined]
			icon = source.convert("RGBA")
		resampling = getattr(Image, "Resampling", None)
		method = getattr(resampling, "LANCZOS", getattr(Image, "LANCZOS", getattr(Image, "BILINEAR", 2)))
		if ImageOps is not None:
			fitted = ImageOps.contain(icon, size, method=method)  # type: ignore[name-defined]
		else:
			fitted = icon.resize(size, method)
		_comment_icon_image = ctk.CTkImage(light_image=fitted, dark_image=fitted, size=size)
	except Exception:
		_comment_icon_image = None
	return _comment_icon_image

_profile_avatar_cache: dict[tuple[str, int], tk.PhotoImage] = {}
_video_sessions: dict[str, dict[str, Any]] = {}
_video_audio_temp_dirs: set[str] = set()
_stories_widgets: dict[str, Any] = {}
_story_thumbnail_cache: dict[str, Any] = {}
_active_story_viewer: Optional[dict[str, Any]] = None
_STORY_RING_PATHS = {
	"unwatched": os.path.join(BASE_DIR, "media", "Story", "dev_story_circle_icon.png"),
	"watched": os.path.join(BASE_DIR, "media", "Story", "dev_story_watched_icon.png"),
}
_story_ring_assets: dict[str, tuple[Optional["Image.Image"], Optional[tuple[int, int, int, int]]]] = {}  # type: ignore[name-defined]
_seen_story_authors_by_user: dict[str, set[str]] = {}


def _cleanup_video_audio_tempdirs() -> None:
	for path in list(_video_audio_temp_dirs):
		shutil.rmtree(path, ignore_errors=True)
		_video_audio_temp_dirs.discard(path)


atexit.register(_cleanup_video_audio_tempdirs)


def _bind_return_submit(widget: tk.Misc, callback: Callable[[], None], *, allow_shift_newline: bool = False) -> None:
	def _handler(event) -> str | None:
		if allow_shift_newline and bool(event.state & 0x1):
			return "break"
		callback()
		return "break"

	widget.bind("<Return>", _handler)


def _format_size(value: int) -> str:
	units = ["B", "KB", "MB", "GB", "TB"]
	float_value = float(value)
	for unit in units:
		if float_value < 1024.0 or unit == units[-1]:
			if unit == "B":
				return f"{int(float_value)} {unit}"
			return f"{float_value:.1f} {unit}"
		float_value /= 1024.0
	return f"{value} B"


def _classify_attachment(rel_path: str) -> str:
	_, ext = os.path.splitext(rel_path)
	ext = ext.lower()
	if ext in _IMAGE_EXTS:
		return "image"
	if ext in _VIDEO_EXTS:
		return "video"
	if ext in _AUDIO_EXTS:
		return "audio"
	if ext in _DOCUMENT_EXTS:
		return "document"
	return "file"


def _refresh_post_attachments() -> None:
	frame: Optional[ctk.CTkFrame] = _home_widgets.get("attachments_frame")
	if not frame:
		return
	for child in frame.winfo_children():
		child.destroy()

	if not _post_attachments:
		frame.grid_remove()
		return

	frame.grid()
	frame.grid_columnconfigure(0, weight=1)
	surface = _palette.get("surface", "#111b2e")
	text_color = _palette.get("text", "#e2e8f0")
	muted = _palette.get("muted", "#94a3b8")

	for idx, attachment in enumerate(_post_attachments):
		item = ctk.CTkFrame(frame, fg_color=surface, corner_radius=10)
		item.grid(row=idx, column=0, sticky="we", pady=4)
		item.grid_columnconfigure(0, weight=1)

		name = attachment.get("name") or os.path.basename(attachment.get("path", ""))
		type_label = attachment.get("type", "file").title()
		size_value = attachment.get("size")
		details = f"[{type_label}] {name}"
		if isinstance(size_value, int):
			details += f" • {_format_size(size_value)}"

		ctk.CTkLabel(
			item,
			text=details,
			text_color=text_color,
			anchor="w",
		).grid(row=0, column=0, sticky="we", padx=12, pady=10)

		buttons = ctk.CTkFrame(item, fg_color="transparent")
		buttons.grid(row=0, column=1, padx=12, pady=8)

		path = attachment.get("path")
		if path:
			label = "Play" if attachment.get("type") == "video" else "Open"
			ctk.CTkButton(
				buttons,
				text=label,
				width=70,
				command=lambda att=attachment: _open_attachment(att),
				fg_color=_palette.get("accent", "#4c8dff"),
				hover_color=_palette.get("accent_hover", "#3b6dd6"),
			).grid(row=0, column=0, padx=(0, 6))

		ctk.CTkButton(
			buttons,
			text="Remove",
			width=80,
			command=lambda i=idx: _remove_post_attachment(i),
			fg_color="transparent",
			border_width=1,
			border_color=muted,
			text_color=muted,
			hover_color=surface,
		).grid(row=0, column=1)


def _refresh_dm_attachments() -> None:
	frame: Optional[ctk.CTkFrame] = _dm_widgets.get("attachments_frame")
	if not frame:
		return
	for child in frame.winfo_children():
		child.destroy()

	if not _dm_draft_attachments:
		frame.grid_remove()
		return

	frame.grid()
	frame.grid_columnconfigure(0, weight=1)
	card = _palette.get("card", "#18263f")
	text_color = _palette.get("text", "#e2e8f0")
	muted = _palette.get("muted", "#94a3b8")

	for idx, attachment in enumerate(_dm_draft_attachments):
		item = ctk.CTkFrame(frame, fg_color=card, corner_radius=10)
		item.grid(row=idx, column=0, sticky="we", pady=4)
		item.grid_columnconfigure(0, weight=1)

		name = attachment.get("name") or os.path.basename(attachment.get("path", ""))
		type_label = attachment.get("type", "file").title()
		size_value = attachment.get("size")
		details = f"[{type_label}] {name}"
		if isinstance(size_value, int):
			details += f" • {_format_size(size_value)}"

		ctk.CTkLabel(
			item,
			text=details,
			text_color=text_color,
			anchor="w",
		).grid(row=0, column=0, sticky="we", padx=12, pady=8)

		buttons = ctk.CTkFrame(item, fg_color="transparent")
		buttons.grid(row=0, column=1, padx=12, pady=6)

		path = attachment.get("path")
		if path:
			label = "Play" if attachment.get("type") == "video" else "Open"
			ctk.CTkButton(
				buttons,
				text=label,
				width=70,
				command=lambda att=attachment: _open_attachment(att),
				fg_color=_palette.get("accent", "#4c8dff"),
				hover_color=_palette.get("accent_hover", "#3b6dd6"),
			).grid(row=0, column=0, padx=(0, 6))

		ctk.CTkButton(
			buttons,
			text="Remove",
			width=80,
			command=lambda i=idx: _remove_dm_attachment(i),
			fg_color="transparent",
			border_width=1,
			border_color=muted,
			text_color=muted,
			hover_color=card,
		).grid(row=0, column=1)


def _find_group_chat(chat_id: Optional[str]) -> Optional[dict[str, Any]]:
	if not chat_id:
		return None
	for chat in group_chats:
		if chat.get("id") == chat_id:
			return chat
	return None


def _get_user_group_chats(username: Optional[str]) -> list[dict[str, Any]]:
	if not username:
		return []
	return [chat for chat in group_chats if username in chat.get("members", [])]


def _generate_group_invite_token() -> str:
	return uuid4().hex[:8].upper()


def _ensure_group_invite_token(chat: dict[str, Any]) -> tuple[str, bool]:
	token = (chat.get("invite_token") or "").strip()
	if token:
		return token, False
	new_token = _generate_group_invite_token()
	chat["invite_token"] = new_token
	chat["invite_updated_at"] = now_ts()
	chat["updated_at"] = now_ts()
	return new_token, True


def _build_group_invite_link(token: str) -> str:
	token = token.strip()
	return f"{GROUP_INVITE_LINK_PREFIX}{token}" if token else GROUP_INVITE_LINK_PREFIX.rstrip("/")


def _extract_group_invite_token(value: str) -> Optional[str]:
	candidate = (value or "").strip()
	if not candidate:
		return None
	lower_prefix = GROUP_INVITE_LINK_PREFIX.lower()
	if candidate.lower().startswith(lower_prefix):
		candidate = candidate[len(GROUP_INVITE_LINK_PREFIX) :]
	if "/" in candidate:
		candidate = candidate.rsplit("/", 1)[-1]
	if "?" in candidate:
		candidate = candidate.split("?", 1)[0]
	stripped = candidate.strip().rstrip('.,!?:;)]}"\'')
	token = stripped.strip().upper()
	if not token:
		return None
	if not _is_valid_invite_token(token):
		return None
	return token


def _is_valid_invite_token(token: str) -> bool:
	if len(token) != 8:
		return False
	return all(ch in _INVITE_TOKEN_CHARS for ch in token)


def _discover_invite_tokens(message: str) -> list[str]:
	text = message or ""
	tokens: list[str] = []
	pattern = re.compile(re.escape(GROUP_INVITE_LINK_PREFIX) + r"([A-Za-z0-9]+)", re.IGNORECASE)
	for match in pattern.finditer(text):
		token = _extract_group_invite_token(match.group(0))
		if token and token not in tokens:
			tokens.append(token)
	if not tokens:
		for part in re.split(r"[\s,]+", text):
			token = _extract_group_invite_token(part)
			if token and token not in tokens:
				tokens.append(token)
	return tokens


def _resolve_invite_token_state(token: str) -> tuple[str, Optional[dict[str, Any]]]:
	normalized = (token or "").strip().upper()
	if not normalized:
		return "invalid", None
	for chat in group_chats:
		existing = str(chat.get("invite_token") or "").strip().upper()
		if existing == normalized:
			current_user = _ui_state.current_user or ""
			members = chat.get("members", []) or []
			if current_user and current_user in members:
				return "joined", chat
			return "available", chat
	return "invalid", None


def _create_invite_widget(container: ctk.CTkFrame, token: str) -> Optional[ctk.CTkButton]:
	state, chat = _resolve_invite_token_state(token)
	accent = _palette.get("accent", "#4c8dff")
	accent_hover = _palette.get("accent_hover", "#3b6dd6")
	muted = _palette.get("muted", "#94a3b8")
	danger = _palette.get("danger", "#ef4444")
	if state == "available" and chat:
		label = f"Join {chat.get('name') or 'group chat'}"
		return ctk.CTkButton(
			container,
			text=label,
			width=220,
			fg_color=accent,
			hover_color=accent_hover,
			command=lambda invite_token=token: _handle_join_group_invite(invite_token),
		)
	if state == "joined" and chat:
		label = f"Already in {chat.get('name') or 'this group'}"
		return ctk.CTkButton(
			container,
			text=label,
			width=220,
			fg_color="transparent",
			border_width=1,
			border_color=muted,
			text_color=muted,
			state="disabled",
		)
	label = "Invite expired"
	return ctk.CTkButton(
		container,
		text=label,
		width=220,
		fg_color="transparent",
		border_width=1,
		border_color=danger,
		text_color=danger,
		state="disabled",
	)


def _handle_join_group_invite(token: str) -> None:
	if not require_login("join group chats"):
		return
	state, chat = _resolve_invite_token_state(token)
	if state == "invalid" or not chat:
		messagebox.showerror("Invite expired", "That invite link is no longer valid.")
		_request_render("dm")
		return
	if state == "joined":
		messagebox.showinfo("Group chat", "You are already a member of that group chat.")
		if chat.get("id"):
			_open_group_chat(chat.get("id") or "")
		return
	current_user = _ui_state.current_user or ""
	if not current_user:
		return
	members = chat.setdefault("members", [])
	if current_user in members:
		_open_group_chat(chat.get("id") or "")
		_request_render("dm")
		return
	members.append(current_user)
	timestamp = now_ts()
	chat["updated_at"] = timestamp
	messages_list = chat.setdefault("messages", [])
	join_message = {
		"id": uuid4().hex,
		"sender": current_user,
		"content": f"@{current_user} joined the group",
		"time": timestamp,
		"attachments": [],
		"reactions": {},
		"seen_by": [current_user],
	}
	messages_list.append(join_message)
	persist()
	trigger_immediate_sync("group_chats")
	notifications_sent = False
	for member in members:
		if member == current_user:
			continue
		notifications_sent = (
			push_notification(
				member,
				f"@{current_user} joined {chat.get('name') or 'your group chat'}",
				meta={"type": "group_dm", "group": chat.get("id"), "from": current_user},
			)
			or notifications_sent
		)
	if notifications_sent:
		trigger_immediate_sync("notifications")
	_mark_dm_sidebar_dirty()
	_open_group_chat(chat.get("id") or "")
	_request_render("dm")
	_refresh_notifications_ui()
	messagebox.showinfo("Group chat", "You joined the group chat!")


def _get_active_group_chat() -> Optional[dict[str, Any]]:
	conversation_id = _ui_state.active_dm_conversation or ""
	if not conversation_id.startswith("group:"):
		return None
	return _find_group_chat(conversation_id)


def _locate_conversation_message(conversation_id: str, message_id: str) -> Optional[dict[str, Any]]:
	if not conversation_id or not message_id:
		return None
	needle = str(message_id).strip()
	if not needle:
		return None
	if conversation_id.startswith("group:"):
		chat = _find_group_chat(conversation_id)
		if not chat:
			return None
		for msg in chat.get("messages", []):
			if isinstance(msg, dict) and str(msg.get("id") or "").strip() == needle:
				return msg
	else:
		thread = messages.get(conversation_id, [])
		for msg in thread:
			if isinstance(msg, dict) and str(msg.get("id") or "").strip() == needle:
				return msg
	return None


def _ellipsize_text(text: Any, limit: int = 60) -> str:
	value = str(text or "").strip()
	if len(value) <= limit:
		return value
	return value[: max(1, limit - 1)].rstrip() + "…"


def _collect_activity_timeline(username: Optional[str]) -> list[tuple[datetime, str]]:
	if not username:
		return []
	entries: list[tuple[datetime, str]] = []
	for post in posts:
		if post.get("author") != username:
			continue
		ts = _parse_timestamp(post.get("created_at"))
		if ts:
			desc = _ellipsize_text(post.get("content", ""), 64) or "Posted an update"
			entries.append((ts, f"Posted: {desc}"))
	for story in stories:
		if story.get("author") != username:
			continue
		story_ts = _parse_timestamp(story.get("created_at"))
		if not story_ts:
			epoch = story.get("created_at_epoch")
			if isinstance(epoch, (int, float)):
				try:
					story_ts = datetime.fromtimestamp(epoch)
				except (OSError, ValueError):
					story_ts = None
		if story_ts:
			entries.append((story_ts, "Shared a story"))
	last_active = users.get(username, {}).get("last_active_at")
	active_ts = _parse_timestamp(last_active)
	if active_ts:
		entries.append((active_ts, "Active in messages"))
	entries.sort(key=lambda item: item[0], reverse=True)
	return entries[:TIMELINE_MAX_ITEMS]


def _compute_mutual_followers(viewer: Optional[str], target: Optional[str]) -> list[str]:
	if not viewer or not target or viewer == target:
		return []
	viewer_info = users.get(viewer, {})
	target_info = users.get(target, {})
	viewer_following = set(viewer_info.get("following", []))
	viewer_followers = set(viewer_info.get("followers", []))
	target_followers = set(target_info.get("followers", []))
	mutuals = sorted((viewer_following | viewer_followers) & target_followers, key=str.lower)
	return mutuals


def _compute_suggested_users(viewer: Optional[str], target: Optional[str] = None, *, limit: int = PROFILE_SUGGESTION_LIMIT) -> list[str]:
	if not viewer or viewer not in users:
		return []
	viewer_record = users.get(viewer, {})
	viewer_following = set(viewer_record.get("following", []))
	viewer_followers = set(viewer_record.get("followers", []))
	target_following = set(users.get(target, {}).get("following", [])) if target else set()
	candidates: list[tuple[int, int, str]] = []
	for username, record in users.items():
		if username == viewer or username in viewer_following:
			continue
		followers = set(record.get("followers", []))
		if viewer in followers:
			continue
		shared_with_viewer = len(followers & viewer_followers)
		shared_with_following = len(followers & viewer_following)
		is_followed_by_target = 1 if target and username in target_following else 0
		score_primary = (is_followed_by_target * 10) + shared_with_following + shared_with_viewer
		popularity = len(followers)
		candidates.append((score_primary, popularity, username))
	if not candidates:
		return []
	candidates.sort(key=lambda item: (-item[0], -item[1], item[2].lower()))
	ordered = [username for *_unused, username in candidates]
	return ordered[:limit]


def _touch_current_user_activity(*, force: bool = False) -> None:
	global _last_activity_touch
	user = _ui_state.current_user
	if not user:
		return
	now_value = time.time()
	if not force and now_value - _last_activity_touch < 60:
		return
	users.setdefault(user, {})["last_active_at"] = now_ts()
	_last_activity_touch = now_value
	persist()


def _derive_conversation_partner(username: str, conversation_id: str) -> Optional[str]:
	parts = [part for part in conversation_id.split("|") if part]
	if not parts:
		return None
	username_lc = username.lower()
	for handle in parts:
		if handle.lower() != username_lc:
			return handle
	return None


def _set_typing_state(conversation_id: Optional[str], username: Optional[str], *, duration: float = 5.0) -> None:
	if not conversation_id or not username:
		return
	if duration <= 0:
		return
	expiry = time.time() + duration
	state = _dm_typing_state.setdefault(conversation_id, {})
	state[username] = expiry
	_schedule_typing_prune()
	_refresh_typing_indicator(conversation_id)


def _clear_typing_state(conversation_id: Optional[str], username: Optional[str]) -> None:
	if not conversation_id or not username:
		return
	state = _dm_typing_state.get(conversation_id)
	if not state:
		return
	if username in state:
		state.pop(username, None)
		if not state:
			_dm_typing_state.pop(conversation_id, None)
	_refresh_typing_indicator(conversation_id)


def _prune_typing_state(*, now_value: Optional[float] = None) -> bool:
	now_value = now_value if now_value is not None else time.time()
	changed = False
	for convo, state in list(_dm_typing_state.items()):
		for username, expiry in list(state.items()):
			if expiry <= now_value:
				state.pop(username, None)
				changed = True
		if not state:
			_dm_typing_state.pop(convo, None)
	return changed


def _schedule_typing_prune() -> None:
	global _dm_typing_after_handle
	anchor = _get_after_anchor()
	if not anchor:
		return
	if _dm_typing_after_handle:
		try:
			anchor.after_cancel(_dm_typing_after_handle)
		except Exception:
			pass

	def _tick() -> None:
		global _dm_typing_after_handle
		_dm_typing_after_handle = None
		if _prune_typing_state():
			_refresh_typing_indicator(_ui_state.active_dm_conversation)
		if _dm_typing_state:
			_schedule_typing_prune()

	_dm_typing_after_handle = anchor.after(1200, _tick)


def _refresh_typing_indicator(conversation_id: Optional[str]) -> None:
	label: Optional[ctk.CTkLabel] = _dm_widgets.get("typing_label")
	if not label or not label.winfo_exists():
		return
	if not conversation_id:
		label.grid_remove()
		return
	state = _dm_typing_state.get(conversation_id)
	if not state:
		label.grid_remove()
		return
	now_value = time.time()
	participants = [
		user
		for user, expiry in state.items()
		if expiry > now_value and user != _ui_state.current_user
	]
	if not participants:
		label.grid_remove()
		return
	if len(participants) == 1:
		text = f"@{participants[0]} is typing…"
	else:
		text = f"{', '.join(f'@{name}' for name in participants[:2])} are typing…"
	label.configure(text=text, text_color=_palette.get("muted", "#94a3b8"))
	label.grid()


def _simulate_partner_typing(meta: dict[str, Any]) -> None:
	conversation_id = meta.get("conversation_id")
	if not conversation_id:
		return
	last_incoming = meta.get("last_incoming") or {}
	sender = last_incoming.get("sender")
	if not sender or sender == _ui_state.current_user:
		return
	timestamp = last_incoming.get("time")
	ts = _parse_timestamp(timestamp)
	if not ts:
		return
	delta = (datetime.now() - ts).total_seconds()
	if delta > 90:
		_dm_typing_hint_cache.pop(conversation_id, None)
		return
	states = _dm_typing_state.get(conversation_id, {})
	if sender in states:
		return
	marker = f"{sender}|{timestamp}"
	if _dm_typing_hint_cache.get(conversation_id) == marker:
		return
	_dm_typing_hint_cache[conversation_id] = marker
	_set_typing_state(conversation_id, sender, duration=5.0)


def _handle_dm_typing_event(_event: Any = None) -> None:
	conversation_id = _ui_state.active_dm_conversation
	user = _ui_state.current_user
	if not conversation_id or not user:
		return
	now_value = time.time()
	last = _dm_typing_local_events.get(conversation_id, 0.0)
	if now_value - last < 0.75:
		return
	_dm_typing_local_events[conversation_id] = now_value
	_set_typing_state(conversation_id, user, duration=3.5)


def _handle_dm_focus_in(_event: Any = None) -> None:
	conversation_id = _ui_state.active_dm_conversation
	user = _ui_state.current_user
	if not conversation_id or not user:
		return
	_dm_typing_local_events[conversation_id] = time.time()
	_set_typing_state(conversation_id, user, duration=3.5)


def _handle_dm_focus_out(_event: Any = None) -> None:
	conversation_id = _ui_state.active_dm_conversation
	user = _ui_state.current_user
	if not conversation_id or not user:
		return
	_dm_typing_local_events.pop(conversation_id, None)
	_clear_typing_state(conversation_id, user)


def _mark_messages_seen(conversation_id: Optional[str], thread: list[dict[str, Any]]) -> None:
	viewer = _ui_state.current_user
	if not viewer or not conversation_id or not thread:
		return
	changed = False
	for msg in thread:
		seen_by = msg.setdefault("seen_by", [])
		if viewer not in seen_by:
			seen_by.append(viewer)
			changed = True
	if not changed:
		return
	if conversation_id.startswith("group:"):
		chat = _find_group_chat(conversation_id)
		if chat is not None:
			chat["updated_at"] = now_ts()
	else:
		messages.setdefault(conversation_id, thread)
	persist()


def _handle_toggle_dm_reaction(conversation_id: str, message_id: str, emoji: str) -> None:
	if not require_login("react to messages"):
		return
	current_user = _ui_state.current_user
	if not current_user:
		return
	conversation = conversation_id or (_ui_state.active_dm_conversation or "")
	if not conversation:
		return
	if emoji not in MESSAGE_REACTIONS:
		return
	message = _locate_conversation_message(conversation, message_id)
	if not message:
		messagebox.showwarning("Message", "Could not locate that message.")
		return
	reactions = message.setdefault("reactions", {})
	if not isinstance(reactions, dict):
		reactions = {}
		message["reactions"] = reactions
	reactors = reactions.get(emoji)
	if not isinstance(reactors, list):
		reactors = []
		reactions[emoji] = reactors
	if current_user in reactors:
		reactors.remove(current_user)
	else:
		reactors.append(current_user)
	if not reactors:
		reactions.pop(emoji, None)
	message["updated_at"] = now_ts()
	if conversation.startswith("group:"):
		chat = _find_group_chat(conversation)
		if chat is not None:
			chat["updated_at"] = now_ts()
	else:
		messages.setdefault(conversation, [])
	persist()
	_request_render("dm")


def _set_active_dm_conversation(conversation_id: Optional[str], partner: Optional[str]) -> None:
	previous = _ui_state.active_dm_conversation
	if previous != conversation_id:
		_dm_draft_attachments.clear()
		_refresh_dm_attachments()
	_ui_state.active_dm_conversation = conversation_id
	_ui_state.active_dm_user = partner
	_ui_state.active_dm_user = partner


def _select_default_dm_conversation() -> None:
	user = _ui_state.current_user
	if not user:
		_set_active_dm_conversation(None, None)
		return
	conversation_id = _ui_state.active_dm_conversation
	if conversation_id:
		if conversation_id.startswith("group:"):
			chat = _find_group_chat(conversation_id)
			if chat and user in chat.get("members", []):
				_ui_state.active_dm_user = None
				return
		else:
			partner = _ui_state.active_dm_user or _derive_conversation_partner(user, conversation_id)
			if partner:
				_ui_state.active_dm_user = partner
				return
	following = list(users.get(user, {}).get("following", []))
	if following:
		partner = following[0]
		_set_active_dm_conversation(convo_id(user, partner), partner)
		return
	user_groups = _get_user_group_chats(user)
	if user_groups:
		_set_active_dm_conversation(user_groups[0].get("id"), None)
	else:
		_set_active_dm_conversation(None, None)


def _set_video_upload_path(path: str) -> None:
	_videos_widgets["upload_path"] = path
	label: ctk.CTkLabel = _videos_widgets.get("upload_path_label")
	if label:
		label.configure(text=os.path.basename(path) if path else "No video selected")


def _set_video_status(message: str, *, error: bool = False) -> None:
	status_lbl: ctk.CTkLabel = _videos_widgets.get("status_label")
	if not status_lbl:
		return
	mode = "error" if error else "info"
	_videos_widgets["status_mode"] = mode
	color_map = {
		"error": _palette.get("danger", "#ef4444"),
		"info": _palette.get("accent", "#2563eb"),
	}
	status_lbl.configure(
		text=message,
		text_color=color_map.get(mode, _palette.get("muted", "#94a3b8")),
	)


def _resolve_username(handle: str) -> Optional[str]:
	target = handle.strip().lower()
	if not target:
		return None
	for username in users:
		if username.lower() == target:
			return username
	return None


def _split_mentions(text: str, *, author: Optional[str] = None) -> tuple[list[str], list[str]]:
	resolved: list[str] = []
	missing: list[str] = []
	if not text:
		return resolved, missing
	seen: set[str] = set()
	for raw in _MENTION_PATTERN.findall(text):
		handle = raw.strip()
		if not handle or handle.lower() in seen:
			continue
		seen.add(handle.lower())
		real = _resolve_username(handle)
		if real and real != author and real not in resolved:
			resolved.append(real)
		elif real is None and handle not in missing:
			missing.append(handle)
	return resolved, missing


def _ensure_reaction_icon(kind: str, *, size: Optional[tuple[int, int]] = None) -> Optional[ctk.CTkImage]:
	if kind not in {"like", "dislike"}:
		return None
	target_size = size or _REACTION_ICON_SIZE
	cache_key = (kind, target_size)
	if cache_key in _reaction_icon_cache:
		return _reaction_icon_cache[cache_key]
	if Image is None:
		_reaction_icon_cache[cache_key] = None
		return None
	icon_path = _LIKE_ICON_PATH if kind == "like" else _DISLIKE_ICON_PATH
	if not icon_path.exists():
		_reaction_icon_cache[cache_key] = None
		return None
	try:
		with Image.open(icon_path) as source:
			icon_img = source.convert("RGBA")
	except OSError:
		_reaction_icon_cache[cache_key] = None
		return None
	resampling = getattr(Image, "Resampling", None)
	method = getattr(resampling, "LANCZOS", getattr(Image, "LANCZOS", getattr(Image, "BILINEAR", 2)))
	if ImageOps is not None:
		resized = ImageOps.contain(icon_img, target_size, method=method)
	else:
		resized = icon_img.resize(target_size, method)
	canvas = Image.new("RGBA", target_size, (0, 0, 0, 0))
	offset = (
		(target_size[0] - resized.width) // 2,
		(target_size[1] - resized.height) // 2,
	)
	canvas.paste(resized, offset, resized)
	icon = ctk.CTkImage(light_image=canvas, dark_image=canvas, size=target_size)
	_reaction_icon_cache[cache_key] = icon
	return icon


def _ensure_story_reaction_lists(story: dict[str, Any]) -> tuple[list[str], list[str]]:
	liked = story.get("liked_by")
	disliked = story.get("disliked_by")
	if not isinstance(liked, list):
		liked = []
		story["liked_by"] = liked
	if not isinstance(disliked, list):
		disliked = []
		story["disliked_by"] = disliked
	return liked, disliked


def _ensure_video_reaction_lists(video: dict[str, Any]) -> tuple[list[str], list[str]]:
	liked = video.get("liked_by")
	disliked = video.get("disliked_by")
	if not isinstance(liked, list):
		liked = []
		video["liked_by"] = liked
	if not isinstance(disliked, list):
		disliked = []
		video["disliked_by"] = disliked
	return liked, disliked


def _style_video_action_button(button: Optional[ctk.CTkButton], *, active: bool = False) -> None:
	if not button:
		return
	if active:
		button.configure(
			fg_color=_palette.get("accent", "#2563eb"),
			hover_color=_palette.get("accent_hover", "#1d4ed8"),
			text_color="#f8fafc",
		)
	else:
		button.configure(
			fg_color=_palette.get("surface", "#111b2e"),
			hover_color=_palette.get("card", "#1f2937"),
			text_color=_palette.get("text", "#e2e8f0"),
		)


def _update_video_reaction_ui(video_id: str) -> None:
	card = _video_cards.get(video_id)
	video = _find_video(video_id)
	if not card or not video:
		return
	liked, disliked = _ensure_video_reaction_lists(video)
	user = _ui_state.current_user or ""
	is_liked = user in liked
	is_disliked = user in disliked
	like_btn: ctk.CTkButton = card.get("like_button")
	dislike_btn: ctk.CTkButton = card.get("dislike_button")
	comment_btn: ctk.CTkButton = card.get("comment_button")
	comments = video.get("comments") if isinstance(video.get("comments"), list) else []
	if like_btn:
		like_btn.configure(text=f"Like {len(liked)}")
	if dislike_btn:
		dislike_btn.configure(text=f"Dislike {len(disliked)}")
	if comment_btn:
		comment_btn.configure(text=f"Comments {len(comments)}")
	_style_video_action_button(like_btn, active=is_liked)
	_style_video_action_button(dislike_btn, active=is_disliked)
	panel_visible = card.get("panel_visible", False)
	_style_video_action_button(comment_btn, active=panel_visible)


def _toggle_video_reaction(video_id: str, reaction: str) -> None:
	if reaction not in {"like", "dislike"}:
		return
	if not require_login("react to videos"):
		return
	video = _find_video(video_id)
	if not video:
		return
	liked, disliked = _ensure_video_reaction_lists(video)
	user = _ui_state.current_user or ""
	changed = False
	if reaction == "like":
		if user in liked:
			liked.remove(user)
			changed = True
		else:
			if user in disliked:
				disliked.remove(user)
			liked.append(user)
			changed = True
	else:
		if user in disliked:
			disliked.remove(user)
			changed = True
		else:
			disliked.append(user)
			if user in liked:
				liked.remove(user)
			changed = True
	if not changed:
		return
	video["likes"] = len(liked)
	video["dislikes"] = len(disliked)
	persist()
	_update_video_reaction_ui(video_id)
	_mark_dirty("videos")


def _toggle_story_reaction(story_id: str, reaction: str) -> None:
	if reaction not in {"like", "dislike"}:
		return
		return
	story = _find_story(story_id)
	if not story:
		return
	liked, disliked = _ensure_story_reaction_lists(story)
	user = _ui_state.current_user or ""
	changed = False
	if reaction == "like":
		if user in liked:
			liked.remove(user)
			changed = True
		else:
			if user in disliked:
				disliked.remove(user)
			liked.append(user)
			changed = True
	else:
		if user in disliked:
			disliked.remove(user)
			changed = True
		else:
			if user in liked:
				liked.remove(user)
			disliked.append(user)
			changed = True
	if not changed:
		return
	story["likes"] = len(liked)
	story["dislikes"] = len(disliked)
	persist()
	state = _active_story_viewer
	if state:
		_update_story_controls(state)
	_mark_dirty("home")


def _handle_story_reaction_click(reaction: str) -> None:
	state = _active_story_viewer
	if not state:
		return
	items = state.get("items", [])
	index = state.get("index", 0)
	if 0 <= index < len(items):
		story = items[index]
		story_id = str(story.get("id") or story.get("path") or "").strip()
		if story_id:
			_toggle_story_reaction(story_id, reaction)


def _handle_select_video_file() -> None:
	filetypes = [
		("Video files", "*.mp4;*.mov;*.avi;*.mkv;*.webm"),
		("All files", "*.*"),
	]
	path = filedialog.askopenfilename(title="Select video", filetypes=filetypes)
	if not path:
		return
	ext = os.path.splitext(path)[1].lower()
	if ext not in _VIDEO_EXTS:
		messagebox.showwarning(
			"Unsupported video",
			"Please choose a MP4, MOV, AVI, MKV, or WEBM file.",
		)
		return
	_set_video_upload_path(path)
	_set_video_status("Video ready to upload", error=False)


def _handle_upload_video() -> None:
	if not require_login("upload a video"):
		return
	path = _videos_widgets.get("upload_path")
	if not path:
		_set_video_status("Select a video first", error=True)
		return
	ext = os.path.splitext(path)[1].lower()
	if ext not in _VIDEO_EXTS:
		_set_video_status("Please choose a supported video file", error=True)
		return
	rel_path = copy_file_to_media(path, base_dir=BASE_DIR, media_dir=MEDIA_DIR)
	if not rel_path:
		_set_video_status("Failed to copy video", error=True)
		return
	media_sync_failed = not upload_media_asset(rel_path)
	caption_entry: ctk.CTkEntry = _videos_widgets.get("caption_entry")
	caption = caption_entry.get().strip() if caption_entry else ""
	video_id = str(uuid4())
	video_record: dict[str, Any] = {
		"id": video_id,
		"author": _ui_state.current_user,
		"path": rel_path,
		"created_at": now_ts(),
		"comments": [],
	}
	if caption:
		video_record["caption"] = caption
	videos.append(video_record)
	persist()
	followers_notified = notify_followers(
		_ui_state.current_user,
		message=f"@{_ui_state.current_user} uploaded a new video",
		meta_factory=lambda _user: {
			"type": "video_publish",
			"video_id": video_id,
			"from": _ui_state.current_user,
		},
	)
	missing_mentions: list[str] = []
	mentions_delivered = False
	if caption:
		resolved_mentions, missing_mentions = _split_mentions(caption, author=_ui_state.current_user)
		if resolved_mentions:
			mentions_delivered = notify_mentions(
				_ui_state.current_user,
				caption,
				"a video",
				mentions=resolved_mentions,
				meta_factory=lambda _user: {
					"type": "mention",
					"resource": "video",
					"video_id": video_id,
					"from": _ui_state.current_user,
				},
			)
	if caption_entry:
		caption_entry.delete(0, tk.END)
	_set_video_upload_path("")
	if media_sync_failed:
		_notify_remote_sync_issue("media", "upload the video file")
	if followers_notified or mentions_delivered:
		trigger_immediate_sync("notifications")
		_refresh_notifications_ui()
	trigger_immediate_sync("videos")
	_notify_remote_sync_issue("videos", "publish the video")
	if missing_mentions:
		_names = ", ".join(f"@{name}" for name in missing_mentions)
		_set_video_status(f"Video uploaded, but these mentions were not found: {_names}", error=True)
	else:
		_set_video_status("Video uploaded", error=False)
	_mark_dirty("videos")
	if _ui_state.active_view == "videos":
		_render_videos()


def _get_story_ring_asset(kind: str) -> tuple[Optional["Image.Image"], Optional[tuple[int, int, int, int]]]:  # type: ignore[name-defined]
	if kind in _story_ring_assets:
		return _story_ring_assets[kind]
	path = _STORY_RING_PATHS.get(kind)
	if Image is None or not path or not os.path.exists(path):
		_story_ring_assets[kind] = (None, None)
		return _story_ring_assets[kind]
	try:
		with Image.open(path) as source:  # type: ignore[name-defined]
			overlay = source.convert("RGBA")
		alpha = overlay.split()[-1]
		width, height = overlay.size
		threshold = 8
		min_x, min_y, max_x, max_y = width, height, -1, -1
		pixels = alpha.load()
		for y in range(height):
			for x in range(width):
				if pixels[x, y] <= threshold:
					if min_x == -1 or x < min_x:
						min_x = x
					if min_y == -1 or y < min_y:
						min_y = y
					if x > max_x:
						max_x = x
					if y > max_y:
						max_y = y
		inner_box = (min_x, min_y, max_x + 1, max_y + 1) if max_x >= 0 and max_y >= 0 else None
		_story_ring_assets[kind] = (overlay, inner_box)
	except Exception:
		_story_ring_assets[kind] = (None, None)
	return _story_ring_assets[kind]


def _current_seen_story_set() -> set[str]:
	key = _ui_state.current_user or "__anon__"
	return _seen_story_authors_by_user.setdefault(key, set())


def _invalidate_story_profile_cache(author: str) -> None:
	prefix = f"profile::{author}:"
	for cache_key in [k for k in list(_story_thumbnail_cache.keys()) if k.startswith(prefix)]:
		_story_thumbnail_cache.pop(cache_key, None)


def _mark_story_author_seen(author: str) -> None:
	if not author:
		return
	seen = _current_seen_story_set()
	if author in seen:
		return
	seen.add(author)
	_invalidate_story_profile_cache(author)
	_refresh_stories_bar()


def _mark_story_author_unseen_for_all(author: str) -> None:
	if not author:
		return
	for seen_set in _seen_story_authors_by_user.values():
		if author in seen_set:
			seen_set.discard(author)
	_invalidate_story_profile_cache(author)
	_refresh_stories_bar()


def _ensure_story_overlay_container() -> Optional[ctk.CTkFrame]:
	overlay: Optional[ctk.CTkFrame] = _stories_widgets.get("overlay")
	if overlay and overlay.winfo_exists():
		return overlay
	host: Optional[ctk.CTkFrame] = _home_widgets.get("frame")
	if not host or not host.winfo_exists():
		return None
	parent = host.winfo_toplevel()
	try:
		overlay = ctk.CTkFrame(parent, fg_color="#020617")
	except Exception:
		return None
	overlay.place_forget()
	overlay.configure(cursor="arrow")
	_stories_widgets["overlay"] = overlay
	return overlay


def _prepare_story_overlay() -> Optional[ctk.CTkFrame]:
	overlay = _ensure_story_overlay_container()
	if not overlay:
		return None
	for child in list(overlay.winfo_children()):
		child.destroy()
	overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
	overlay.lift()
	overlay.focus_set()
	overlay.unbind("<Escape>")
	return overlay


def _hide_story_overlay() -> None:
	overlay: Optional[ctk.CTkFrame] = _stories_widgets.get("overlay")
	if overlay and overlay.winfo_exists():
		overlay.unbind("<Escape>")
		for child in list(overlay.winfo_children()):
			child.destroy()
		overlay.place_forget()


def _get_story_profile_thumbnail(author: Optional[str], size: int = 72) -> Optional[Any]:
	if not author:
		return None
	seen_authors = _current_seen_story_set()
	kind = "watched" if author in seen_authors else "unwatched"
	cache_key = f"profile::{author}:{size}:{kind}"
	cached = _story_thumbnail_cache.get(cache_key)
	if cached is not None:
		return cached
	path = profile_image_path(
		author,
		users=users,
		base_dir=BASE_DIR,
		default_profile_pic=DEFAULT_PROFILE_PIC,
	)
	if not path:
		return None
	if Image is None or ImageDraw is None:
		avatar_photo = _load_profile_avatar(author, size)
		if avatar_photo:
			_story_thumbnail_cache[cache_key] = avatar_photo
		return avatar_photo
	try:
		with Image.open(path) as source:  # type: ignore[name-defined]
			avatar_rgba = source.convert("RGBA")
	except Exception:
		avatar_photo = _load_profile_avatar(author, size)
		if avatar_photo:
			_story_thumbnail_cache[cache_key] = avatar_photo
		return avatar_photo
	resampling = getattr(Image, "Resampling", None)
	lanczos = getattr(resampling, "LANCZOS", None) if resampling else getattr(Image, "LANCZOS", None)
	fallback = (
		getattr(resampling, "BICUBIC", None) if resampling else getattr(Image, "BICUBIC", None)
	) or getattr(Image, "BILINEAR", None) or getattr(Image, "NEAREST", 0)
	overlay, inner_box = _get_story_ring_asset(kind)
	if (overlay is None or inner_box is None) and kind == "watched":
		overlay, inner_box = _get_story_ring_asset("unwatched")
	thumb_image: Optional["Image.Image"] = None  # type: ignore[name-defined]
	if overlay and inner_box:
		base_width, base_height = overlay.size
		if base_width > 0 and base_height > 0:
			scale_x = size / base_width
			scale_y = size / base_height
			scaled_inner = (
				int(round(inner_box[0] * scale_x)),
				int(round(inner_box[1] * scale_y)),
				int(round(inner_box[2] * scale_x)),
				int(round(inner_box[3] * scale_y)),
			)
			inner_width = max(1, scaled_inner[2] - scaled_inner[0])
			inner_height = max(1, scaled_inner[3] - scaled_inner[1])
			avatar_edge = max(2, min(inner_width, inner_height))
			avatar_resized = avatar_rgba.resize((avatar_edge, avatar_edge), lanczos or fallback)
			mask = Image.new("L", (avatar_edge, avatar_edge), 0)
			ImageDraw.Draw(mask).ellipse((0, 0, avatar_edge, avatar_edge), fill=255)
			overlay_resized = overlay.resize((size, size), lanczos or fallback)
			center_x = (scaled_inner[0] + scaled_inner[2]) / 2
			center_y = (scaled_inner[1] + scaled_inner[3]) / 2
			offset_x = int(round(center_x - avatar_edge / 2))
			offset_y = int(round(center_y - avatar_edge / 2))
			offset_x = max(0, min(size - avatar_edge, offset_x))
			offset_y = max(0, min(size - avatar_edge, offset_y))
			composite = Image.new("RGBA", (size, size), (0, 0, 0, 0))
			composite.paste(avatar_resized, (offset_x, offset_y), mask)
			thumb_image = Image.alpha_composite(composite, overlay_resized)
	if thumb_image is None:
		ring_width = max(4, size // 8)
		inner_size = max(2, size - ring_width * 2)
		avatar_resized = avatar_rgba.resize((inner_size, inner_size), lanczos or fallback)
		mask = Image.new("L", (inner_size, inner_size), 0)
		ImageDraw.Draw(mask).ellipse((0, 0, inner_size, inner_size), fill=255)
		ring = Image.new("RGBA", (size, size), (0, 0, 0, 0))
		draw = ImageDraw.Draw(ring)
		segments = [
			("#f9ce34", -30, 90),
			("#ee2a7b", 90, 210),
			("#6228d7", 210, 330),
			("#f99d00", 330, 390),
		]
		for color, start, end in segments:
			draw.pieslice((0, 0, size, size), start=start, end=end, fill=color)
		draw.ellipse((ring_width, ring_width, size - ring_width, size - ring_width), fill=(0, 0, 0, 0))
		ring.paste(avatar_resized, (ring_width, ring_width), mask)
		thumb_image = ring
	thumb = ctk.CTkImage(light_image=thumb_image, dark_image=thumb_image, size=(size, size))
	_story_thumbnail_cache[cache_key] = thumb
	return thumb


def _get_story_thumbnail_image(story: dict[str, Any], size: int = 72) -> Optional[Any]:
	profile_thumb = _get_story_profile_thumbnail(story.get("author"), size)
	if profile_thumb is not None:
		return profile_thumb
	if Image is None:
		return None
	cache_key = _story_thumbnail_key(story, size)
	cached = _story_thumbnail_cache.get(cache_key)
	if cached:
		return cached
	try:
		if story.get("type") == "video":
			session = _ensure_video_session(story.get("path", ""))
			_ensure_video_preview(session)
			preview_pil = session.get("preview_pil")
			if preview_pil is None:
				return None
			thumbnail_source = preview_pil.copy()
		else:
			abs_path = _resolve_media_path(str(story.get("path", "")))
			with Image.open(abs_path) as source:  # type: ignore[name-defined]
				thumbnail_source = source.convert("RGBA")
		sampling = getattr(Image, "Resampling", None)
		lanczos = getattr(sampling, "LANCZOS", None) if sampling else getattr(Image, "LANCZOS", None)
		thumbnail_source.thumbnail((size, size), lanczos or getattr(Image, "BICUBIC", 3))
		ctk_image = ctk.CTkImage(light_image=thumbnail_source, dark_image=thumbnail_source, size=(size, size))
		_story_thumbnail_cache[cache_key] = ctk_image
		return ctk_image
	except Exception:
		return None


def _remove_post_attachment(index: int) -> None:
	if 0 <= index < len(_post_attachments):
		_post_attachments.pop(index)
		_refresh_post_attachments()


def _remove_dm_attachment(index: int) -> None:
	if 0 <= index < len(_dm_draft_attachments):
		_dm_draft_attachments.pop(index)
		_refresh_dm_attachments()


def _handle_add_post_attachment() -> None:
	if not require_login("attach files"):
		return
	paths = filedialog.askopenfilenames(title="Select attachments")
	if not paths:
		return

	added = False
	for selected in paths:
		rel_path = copy_file_to_media(selected, base_dir=BASE_DIR, media_dir=MEDIA_DIR)
		if not rel_path:
			continue
		try:
			abs_path = os.path.join(BASE_DIR, rel_path)
			size_bytes = os.path.getsize(abs_path)
		except OSError:
			size_bytes = None
		attachment = {
			"type": _classify_attachment(rel_path),
			"path": rel_path,
			"name": os.path.basename(rel_path),
			"size": size_bytes,
		}
		_post_attachments.append(attachment)
		added = True

	if added:
		_refresh_post_attachments()
	else:
		messagebox.showinfo("No files attached", "No files were added to the post.")


def _handle_add_dm_attachment() -> None:
	if not require_login("attach files"):
		return
	conversation_id = _ui_state.active_dm_conversation or ""
	current_user = _ui_state.current_user
	if not conversation_id or not current_user:
		messagebox.showinfo("Direct messages", "Open a conversation before attaching files.")
		return
	if conversation_id.startswith("group:"):
		chat = _find_group_chat(conversation_id)
		if not chat or current_user not in chat.get("members", []):
			messagebox.showwarning("Group chat", "You are no longer a member of that group chat.")
			_select_default_dm_conversation()
			_request_render("dm")
			return
	else:
		partner = _ui_state.active_dm_user or _derive_conversation_partner(current_user, conversation_id)
		if not partner:
			messagebox.showinfo("Direct messages", "Open a conversation before attaching files.")
			return
	paths = filedialog.askopenfilenames(title="Select attachments")
	if not paths:
		return

	added = False
	for selected in paths:
		rel_path = copy_file_to_media(selected, base_dir=BASE_DIR, media_dir=MEDIA_DIR, max_bytes=MAX_ATTACHMENT_BYTES)
		if not rel_path:
			continue
		try:
			abs_path = os.path.join(BASE_DIR, rel_path)
			size_bytes = os.path.getsize(abs_path)
		except OSError:
			size_bytes = None
		attachment = {
			"type": _classify_attachment(rel_path),
			"path": rel_path,
			"name": os.path.basename(rel_path),
			"size": size_bytes,
		}
		_dm_draft_attachments.append(attachment)
		added = True

	if added:
		_refresh_dm_attachments()
	else:
		messagebox.showinfo("No files attached", "No files were added to the message.")


def _purge_story_cache_if_needed() -> None:
	if purge_expired_stories():
		persist()


def _story_thumbnail_key(story: dict[str, Any], size: int) -> str:
	story_id = story.get("id") or story.get("path") or "story"
	return f"{story_id}:{size}"

def _refresh_stories_bar() -> None:
	entries: list[dict[str, Any]] = _stories_widgets.get("entries", [])
	entries = [entry for entry in entries if entry.get("bar") and entry.get("bar").winfo_exists()]  # type: ignore[union-attr]
	if not entries:
		bar = _stories_widgets.get("bar")
		if not bar or not bar.winfo_exists():
			return
		entries = [{"bar": bar, "placeholder": _stories_widgets.get("placeholder")}]  # type: ignore[arg-type]
	else:
		_stories_widgets["entries"] = entries
	_purge_story_cache_if_needed()
	_story_thumbnail_cache.clear()
	story_by_author: dict[str, list[dict[str, Any]]] = {}
	for entry in stories:
		author = entry.get("author") or "unknown"
		story_by_author.setdefault(author, []).append(entry)
	authors = sorted(
		story_by_author.items(),
		key=lambda pair: max(s.get("created_at_epoch", 0) for s in pair[1]),
		reverse=True,
	)
	for entry in entries:
		bar: Optional[ctk.CTkFrame] = entry.get("bar")  # type: ignore[assignment]
		if not bar:
			continue
		placeholder: Optional[ctk.CTkLabel] = entry.get("placeholder")
		placeholder = _render_story_bar_instance(bar, placeholder, authors)
		entry["placeholder"] = placeholder
	if entries:
		primary = entries[0]
		_stories_widgets["bar"] = primary.get("bar")
		if primary.get("placeholder"):
			_stories_widgets["placeholder"] = primary.get("placeholder")


def _render_story_bar_instance(
	bar: ctk.CTkFrame,
	placeholder: Optional[ctk.CTkLabel],
	authors: list[tuple[str, list[dict[str, Any]]]],
) -> Optional[ctk.CTkLabel]:
	placeholder_lbl = placeholder if placeholder and placeholder.winfo_exists() else None
	for child in list(bar.winfo_children()):
		if placeholder_lbl and child is placeholder_lbl:
			continue
		child.destroy()
	if not authors:
		if placeholder_lbl is None:
			placeholder_lbl = ctk.CTkLabel(
				bar,
				text="No stories yet",
				text_color=_palette.get("muted", "#94a3b8"),
			)
		else:
			placeholder_lbl.configure(text_color=_palette.get("muted", "#94a3b8"))
		placeholder_lbl.grid(row=0, column=0, padx=12, pady=12, sticky="w")
		return placeholder_lbl
	if placeholder_lbl:
		placeholder_lbl.grid_remove()
	for column, (author, items) in enumerate(authors):
		if not items:
			continue
		latest_story = max(items, key=lambda s: s.get("created_at_epoch", 0))
		thumb = _get_story_thumbnail_image(latest_story)
		label_text = _ellipsize(f"@{author}", 14)
		button = ctk.CTkButton(
			bar,
			text=label_text,
			image=thumb,
			compound="top",
			width=100,
			height=110,
			fg_color=_palette.get("card", "#18263f"),
			hover_color=_palette.get("surface", "#111b2e"),
			command=lambda name=author: _open_story_viewer(name),
		)
		if thumb is not None:
			setattr(button, "_story_thumb", thumb)
		if author == _ui_state.current_user:
			button.configure(border_width=2, border_color=_palette.get("accent", "#4c8dff"))
		button.grid(row=0, column=column, padx=(0 if column else 0, 12), pady=8)
	return placeholder_lbl


def _register_story_bar(bar: ctk.CTkFrame, placeholder: Optional[ctk.CTkLabel]) -> None:
	entries: list[dict[str, Any]] = _stories_widgets.setdefault("entries", [])
	for entry in entries:
		if entry.get("bar") is bar:
			entry["placeholder"] = placeholder
			break
	else:
		entries.append({"bar": bar, "placeholder": placeholder})
	_stories_widgets["entries"] = entries
	if entries:
		_stories_widgets["bar"] = entries[0].get("bar")
		first_placeholder = entries[0].get("placeholder")
		if first_placeholder:
			_stories_widgets["placeholder"] = first_placeholder


def _search_usernames(query: str, limit: int = 25) -> list[str]:
	if not users:
		return []
	query = (query or "").strip().lower()
	handles = list(users.keys())
	if not query:
		handles.sort(key=lambda name: (-len(users.get(name, {}).get("followers", [])), name.lower()))
		return handles[:limit]
	starts: list[str] = []
	contains: list[str] = []
	for name in handles:
		lower = name.lower()
		if query in lower:
			if lower.startswith(query):
				starts.append(name)
			else:
				contains.append(name)
	starts.sort(key=str.lower)
	contains.sort(key=str.lower)
	ordered = starts + contains
	return ordered[:limit]


_TS_PARSE_FORMATS = (
	"%Y-%m-%d %H:%M:%S",
	"%Y-%m-%d %H:%M",
)


def _parse_timestamp(value: Any) -> Optional[datetime]:
	if not value:
		return None
	if isinstance(value, datetime):
		return value
	if isinstance(value, (int, float)):
		try:
			return datetime.fromtimestamp(float(value))
		except (ValueError, OSError):
			return None
	text = str(value).strip()
	for fmt in _TS_PARSE_FORMATS:
		try:
			return datetime.strptime(text, fmt)
		except ValueError:
			continue
	return None


def _format_relative_time(ts: Optional[datetime]) -> str:
	if ts is None:
		return "unknown"
	delta = datetime.now() - ts
	seconds = max(int(delta.total_seconds()), 0)
	if seconds < 60:
		return "just now"
	minutes = seconds // 60
	if minutes < 60:
		return f"{minutes}m ago"
	hours = minutes // 60
	if hours < 24:
		return f"{hours}h ago"
	days = hours // 24
	if days < 7:
		return f"{days}d ago"
	if days < 60:
		weeks = max(days // 7, 1)
		return f"{weeks}w ago"
	return ts.strftime("%b %d")


def _format_count(value: int) -> str:
	return f"{value:,}"


def _extract_hashtags_from_text(text: str) -> list[str]:
	if not text:
		return []
	return [match.group(1) for match in _HASHTAG_PATTERN.finditer(text)]


def _collect_hashtag_stats() -> dict[str, dict[str, Any]]:
	stats: dict[str, dict[str, Any]] = {}
	for idx, post in enumerate(posts):
		content = post.get("content", "")
		tags = {tag.lower() for tag in _extract_hashtags_from_text(content)}
		if not tags:
			continue
		likes = len(post.get("liked_by", []))
		replies_count = len(post.get("replies", []))
		attachments_count = len(post.get("attachments", []))
		ts = _parse_timestamp(post.get("created_at"))
		author = post.get("author") or "unknown"
		for tag in tags:
			entry = stats.setdefault(
				tag,
				{
					"count": 0,
					"total_likes": 0,
					"total_replies": 0,
					"total_attachments": 0,
					"authors": set(),
					"latest": None,
					"posts": [],
				},
			)
			entry["count"] += 1
			entry["total_likes"] += likes
			entry["total_replies"] += replies_count
			entry["total_attachments"] += attachments_count
			entry["authors"].add(author)
			entry["posts"].append(
				{
					"post": post,
					"index": idx,
					"timestamp": ts,
				}
			)
			if ts and (entry["latest"] is None or (isinstance(entry["latest"], datetime) and ts > entry["latest"])):
				entry["latest"] = ts
	return stats


def _score_hashtag_entry(entry: dict[str, Any]) -> float:
	base = (
		float(entry.get("count", 0)) * 2
		+ float(entry.get("total_likes", 0)) * 3
		+ float(entry.get("total_replies", 0)) * 2
		+ float(entry.get("total_attachments", 0))
	)
	latest = entry.get("latest")
	if isinstance(latest, datetime):
		hours = max((datetime.now() - latest).total_seconds() / 3600.0, 1.0)
		base *= 48.0 / (hours + 8.0)
	return base


def _normalize_hashtag_payload(tag: str, entry: dict[str, Any]) -> dict[str, Any]:
	payload = {
		"tag": tag,
		"display": f"#{tag}",
		"count": entry.get("count", 0),
		"likes": entry.get("total_likes", 0),
		"replies": entry.get("total_replies", 0),
		"attachments": entry.get("total_attachments", 0),
		"authors": sorted(entry.get("authors", [])),
		"latest": entry.get("latest"),
		"posts": list(entry.get("posts", [])),
	}
	payload["score"] = _score_hashtag_entry(entry)
	return payload


def _get_trending_hashtags(limit: int = 6, *, stats: Optional[dict[str, dict[str, Any]]] = None) -> list[dict[str, Any]]:
	if stats is None:
		stats = _collect_hashtag_stats()
	entries = [_normalize_hashtag_payload(tag, data) for tag, data in stats.items()]
	entries.sort(key=lambda item: (item.get("score", 0.0), item.get("count", 0)), reverse=True)
	return entries[:limit]


def _search_hashtag_entries(
	query: str,
	limit: int = 8,
	*,
	stats: Optional[dict[str, dict[str, Any]]] = None,
) -> list[dict[str, Any]]:
	if stats is None:
		stats = _collect_hashtag_stats()
	needle = (query or "").lstrip("#").strip().lower()
	if not needle:
		return []
	matches: list[dict[str, Any]] = []
	for tag, data in stats.items():
		if needle in tag.lower():
			matches.append(_normalize_hashtag_payload(tag, data))
	matches.sort(key=lambda item: (item.get("score", 0.0), item.get("count", 0)), reverse=True)
	return matches[:limit]


def _get_top_accounts(limit: int = 5) -> list[dict[str, Any]]:
	if not users:
		return []
	posts_by_author: dict[str, list[dict[str, Any]]] = {}
	for post in posts:
		author = post.get("author") or "unknown"
		posts_by_author.setdefault(author, []).append(post)
	now = datetime.now()
	entries: list[dict[str, Any]] = []
	for username, data in users.items():
		followers_count = len(data.get("followers", []))
		following_count = len(data.get("following", []))
		authored_posts = posts_by_author.get(username, [])
		post_count = len(authored_posts)
		total_likes = sum(len(post.get("liked_by", [])) for post in authored_posts)
		total_replies = sum(len(post.get("replies", [])) for post in authored_posts)
		latest_ts: Optional[datetime] = None
		for post in authored_posts:
			ts = _parse_timestamp(post.get("created_at"))
			if ts and (latest_ts is None or ts > latest_ts):
				latest_ts = ts
		recency_score = 0.0
		if latest_ts:
			hours = max((now - latest_ts).total_seconds() / 3600.0, 1.0)
			recency_score = 48.0 / (hours + 8.0)
		score = (
			followers_count * 3
			+ total_likes * 2
			+ total_replies
			+ post_count
			+ recency_score
		)
		entries.append(
			{
				"username": username,
				"followers": followers_count,
				"following": following_count,
				"posts": post_count,
				"likes": total_likes,
				"replies": total_replies,
				"score": score,
			}
		)
	entries.sort(key=lambda item: (item.get("score", 0.0), item.get("followers", 0), item.get("posts", 0)), reverse=True)
	return entries[:limit]


def _build_discovery_metrics(stats: Optional[dict[str, dict[str, Any]]] = None) -> list[tuple[str, str]]:
	now = datetime.now()
	day_ago = now - timedelta(hours=24)
	week_ago = now - timedelta(days=7)
	recent_authors: set[str] = set()
	for post in posts:
		ts = _parse_timestamp(post.get("created_at"))
		if ts and ts >= day_ago:
			recent_authors.add(post.get("author") or "unknown")
	new_signups = 0
	for info in users.values():
		ts = _parse_timestamp(info.get("registered_at"))
		if ts and ts >= week_ago:
			new_signups += 1
	total_messages = sum(len(thread) for thread in messages.values())
	hashtag_total = len(stats) if stats is not None else len(_collect_hashtag_stats())
	return [
		("Total users", _format_count(len(users))),
		("Active today", _format_count(len(recent_authors))),
		("Posts shared", _format_count(len(posts))),
		("Messages sent", _format_count(total_messages)),
		("New this week", _format_count(new_signups)),
		("Trending tags", _format_count(hashtag_total)),
	]


def _render_discovery_metrics_card(
	container: ctk.CTkScrollableFrame,
	metrics: list[tuple[str, str]],
	row: int,
) -> int:
	if not metrics:
		return row
	palette = _palette
	card = ctk.CTkFrame(container, corner_radius=14, fg_color=palette.get("card", "#18263f"))
	card.grid(row=row, column=0, sticky="we", padx=0, pady=6)
	columns = 3
	for col in range(columns):
		card.grid_columnconfigure(col, weight=1)
	for idx, (label, value) in enumerate(metrics):
		r = idx // columns
		c = idx % columns
		title = ctk.CTkLabel(
			card,
			text=value,
			font=ctk.CTkFont(size=18, weight="bold"),
			text_color=palette.get("text", "#e2e8f0"),
		)
		title.grid(row=r * 2, column=c, padx=16, pady=(12, 0), sticky="we")
		sub = ctk.CTkLabel(
			card,
			text=label,
			font=ctk.CTkFont(size=12),
			text_color=palette.get("muted", "#94a3b8"),
		)
		sub.grid(row=r * 2 + 1, column=c, padx=16, pady=(0, 12), sticky="we")
	return row + 1


def _get_trending_posts(limit: int = 4) -> list[dict[str, Any]]:
	if not posts:
		return []
	now = datetime.now()
	entries: list[dict[str, Any]] = []
	for idx, post in enumerate(posts):
		likes = len(post.get("liked_by", []))
		replies_count = len(post.get("replies", []))
		attachments_count = len(post.get("attachments", []))
		ts = _parse_timestamp(post.get("created_at"))
		hours = 720.0
		if ts:
			hours = max((now - ts).total_seconds() / 3600.0, 1.0)
		score = (
			likes * 3
			+ replies_count * 2
			+ attachments_count
			+ 1
		) * (72.0 / (hours + 12.0))
		entries.append(
			{
				"post": post,
				"index": idx,
				"score": score,
				"likes": likes,
				"replies": replies_count,
				"attachments": attachments_count,
				"created_at": ts,
				"author": post.get("author") or "unknown",
			}
		)
	entries.sort(key=lambda item: item.get("score", 0.0), reverse=True)
	return entries[:limit]


def _render_trending_post_card(
	container: ctk.CTkScrollableFrame,
	row: int,
	entry: dict[str, Any],
) -> int:
	palette = _palette
	post = entry.get("post", {})
	author = entry.get("author", "unknown")
	card = ctk.CTkFrame(container, corner_radius=12, fg_color=palette.get("card", "#18263f"))
	card.grid(row=row, column=0, sticky="we", padx=0, pady=6)
	card.grid_columnconfigure(0, weight=1)
	card.grid_columnconfigure(1, weight=0)
	headline = ctk.CTkLabel(
		card,
		text=f"@{author} · {_format_relative_time(entry.get('created_at'))}",
		font=ctk.CTkFont(size=14, weight="bold"),
		text_color=palette.get("text", "#e2e8f0"),
	)
	headline.grid(row=0, column=0, sticky="w", padx=16, pady=(12, 4))
	content = (post.get("content") or "").strip().replace("\n", " ")
	if not content:
		content = "[Attachment]"
	snippet = _ellipsize(content, 120)
	body = ctk.CTkLabel(
		card,
		text=snippet,
		justify="left",
		wraplength=520,
		text_color=palette.get("text", "#e2e8f0"),
		font=ctk.CTkFont(size=12),
	)
	body.grid(row=1, column=0, sticky="we", padx=16, pady=(0, 4))
	metrics_bits = [f"{entry.get('likes', 0)} likes", f"{entry.get('replies', 0)} replies"]
	attachments_count = entry.get("attachments", 0)
	if attachments_count:
		metrics_bits.append(f"{attachments_count} attachments")
	metrics = ctk.CTkLabel(
		card,
		text=" · ".join(metrics_bits),
		text_color=palette.get("muted", "#94a3b8"),
		font=ctk.CTkFont(size=11),
	)
	metrics.grid(row=2, column=0, sticky="w", padx=16, pady=(0, 12))
	actions = ctk.CTkFrame(card, fg_color="transparent")
	actions.grid(row=0, column=1, rowspan=3, sticky="e", padx=12, pady=12)
	ctk.CTkButton(
		actions,
		text="View profile",
		width=110,
		fg_color=palette.get("surface", "#111b2e"),
		hover_color=palette.get("surface", "#111b2e"),
		text_color=palette.get("text", "#e2e8f0"),
		command=lambda user=author: _open_profile(user),
	).grid(row=0, column=0)
	return row + 1


def _render_hashtag_card(
	container: ctk.CTkScrollableFrame,
	row: int,
	item: dict[str, Any],
) -> int:
	palette = _palette
	card = ctk.CTkFrame(container, corner_radius=12, fg_color=palette.get("card", "#18263f"))
	card.grid(row=row, column=0, sticky="we", padx=0, pady=6)
	card.grid_columnconfigure(0, weight=1)
	card.grid_columnconfigure(1, weight=0)
	ctk.CTkLabel(
		card,
		text=item.get("display", f"#{item.get('tag', '')}"),
		font=ctk.CTkFont(size=14, weight="bold"),
		text_color=palette.get("text", "#e2e8f0"),
	).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 2))
	metrics_bits = [f"{item.get('count', 0)} posts", f"{len(item.get('authors', []))} creators"]
	likes = item.get("likes", 0)
	if likes:
		metrics_bits.append(f"{likes} likes")
	replies = item.get("replies", 0)
	if replies:
		metrics_bits.append(f"{replies} replies")
	ctk.CTkLabel(
		card,
		text=" · ".join(metrics_bits),
		text_color=palette.get("muted", "#94a3b8"),
		font=ctk.CTkFont(size=11),
	).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 4))
	latest = item.get("latest")
	if isinstance(latest, datetime):
		timing = _format_relative_time(latest)
		ctk.CTkLabel(
			card,
			text=f"Updated {timing}",
			text_color=palette.get("muted", "#94a3b8"),
			font=ctk.CTkFont(size=11),
		).grid(row=2, column=0, sticky="w", padx=16, pady=(0, 12))
	actions = ctk.CTkFrame(card, fg_color="transparent")
	actions.grid(row=0, column=1, rowspan=3, sticky="e", padx=12, pady=12)
	ctk.CTkButton(
		actions,
		text="View posts",
		width=110,
		fg_color=palette.get("accent", "#4c8dff"),
		hover_color=palette.get("accent_hover", "#3b6dd6"),
		command=lambda tag=item.get("display", ""): _open_hashtag_explorer(tag),
	).grid(row=0, column=0)
	return row + 1


def _render_hashtag_section(
	container: ctk.CTkScrollableFrame,
	items: list[dict[str, Any]],
	row: int,
	*,
	header: str,
) -> int:
	if not items:
		return row
	palette = _palette
	ctk.CTkLabel(
		container,
		text=header,
		font=ctk.CTkFont(size=15, weight="bold"),
		text_color=palette.get("text", "#e2e8f0"),
	).grid(row=row, column=0, sticky="w", padx=0, pady=(12, 0))
	row += 1
	for item in items:
		row = _render_hashtag_card(container, row, item)
	return row


def _render_user_section(
	container: ctk.CTkScrollableFrame,
	usernames: list[str],
	row: int,
	*,
	header: str,
) -> int:
	if not usernames:
		return row
	palette = _palette
	ctk.CTkLabel(
		container,
		text=header,
		font=ctk.CTkFont(size=15, weight="bold"),
		text_color=palette.get("text", "#e2e8f0"),
	).grid(row=row, column=0, sticky="w", padx=0, pady=(12, 0))
	row += 1
	for username in usernames:
		_render_search_result(container, row, username)
		row += 1
	return row


def _render_search_overview(
	container: ctk.CTkScrollableFrame,
	stats: dict[str, dict[str, Any]],
	*,
	start_row: int = 0,
	compact: bool = False,
) -> int:
	row = start_row
	metrics = _build_discovery_metrics(stats)
	row = _render_discovery_metrics_card(container, metrics, row)
	top_accounts = _get_top_accounts(3 if compact else 5)
	row = _render_user_section(container, [entry["username"] for entry in top_accounts], row, header="Popular accounts")
	trending_posts = _get_trending_posts(3 if compact else 4)
	if trending_posts:
		palette = _palette
		ctk.CTkLabel(
			container,
			text="Trending posts",
			font=ctk.CTkFont(size=15, weight="bold"),
			text_color=palette.get("text", "#e2e8f0"),
		).grid(row=row, column=0, sticky="w", padx=0, pady=(12, 0))
		row += 1
		for entry in trending_posts:
			row = _render_trending_post_card(container, row, entry)
	trending_hashtags = _get_trending_hashtags(4 if compact else 6, stats=stats)
	row = _render_hashtag_section(container, trending_hashtags, row, header="Trending hashtags")
	return row


def _open_hashtag_explorer(tag: str) -> None:
	canonical = tag.lstrip("#").lower()
	stats: dict[str, dict[str, Any]] = _search_widgets.get("hashtag_stats", {})  # type: ignore[assignment]
	entry = stats.get(canonical)
	if not entry:
		messagebox.showinfo("No posts", f"No posts for #{canonical} yet.")
		return
	payload = _normalize_hashtag_payload(canonical, entry)
	existing = _search_widgets.get("hashtag_window")
	if existing and hasattr(existing, "winfo_exists") and existing.winfo_exists():  # type: ignore[attr-defined]
		existing.destroy()  # type: ignore[attr-defined]
	parent_frame: Optional[ctk.CTkFrame] = _search_widgets.get("frame")  # type: ignore[assignment]
	parent_window = parent_frame.winfo_toplevel() if parent_frame else None
	window = ctk.CTkToplevel(parent_window)
	window.title(f"#{canonical} posts")
	window.geometry("480x560")
	window.configure(fg_color=_palette.get("bg", "#0b1120"))
	window.lift()
	_search_widgets["hashtag_window"] = window

	ctk.CTkLabel(
		window,
		text=payload.get("display", f"#{canonical}"),
		font=ctk.CTkFont(size=18, weight="bold"),
		text_color=_palette.get("text", "#e2e8f0"),
	).pack(fill="x", padx=24, pady=(24, 12))

	body_frame = ctk.CTkScrollableFrame(window, corner_radius=12, fg_color=_palette.get("surface", "#111b2e"))
	body_frame.pack(expand=True, fill="both", padx=24, pady=(0, 24))
	body_frame.grid_columnconfigure(0, weight=1)
	posts_for_tag = sorted(
		payload.get("posts", []),
		key=lambda item: item.get("timestamp") or datetime.fromtimestamp(0),
		reverse=True,
	)
	for idx, item in enumerate(posts_for_tag[:20]):
		post = item.get("post", {})
		author = post.get("author") or "unknown"
		card = ctk.CTkFrame(body_frame, corner_radius=10, fg_color=_palette.get("card", "#18263f"))
		card.grid(row=idx, column=0, sticky="we", padx=0, pady=6)
		card.grid_columnconfigure(0, weight=1)
		headline = ctk.CTkLabel(
			card,
			text=f"@{author} · {_format_relative_time(item.get('timestamp'))}",
			font=ctk.CTkFont(size=14, weight="bold"),
			text_color=_palette.get("text", "#e2e8f0"),
		)
		headline.grid(row=0, column=0, sticky="w", padx=16, pady=(12, 4))
		content = (post.get("content") or "").strip().replace("\n", " ")
		if not content:
			content = "[Attachment]"
		ctk.CTkLabel(
			card,
			text=_ellipsize(content, 110),
			justify="left",
			wraplength=400,
			text_color=_palette.get("text", "#e2e8f0"),
			font=ctk.CTkFont(size=12),
		).grid(row=1, column=0, sticky="we", padx=16, pady=(0, 4))
		ctk.CTkLabel(
			card,
			text=f"{len(post.get('liked_by', []))} likes · {len(post.get('replies', []))} replies",
			text_color=_palette.get("muted", "#94a3b8"),
			font=ctk.CTkFont(size=11),
		).grid(row=2, column=0, sticky="w", padx=16, pady=(0, 12))
		actions = ctk.CTkFrame(card, fg_color="transparent")
		actions.grid(row=0, column=1, rowspan=3, sticky="e", padx=12, pady=12)
		ctk.CTkButton(
			actions,
			text="View profile",
			width=100,
			fg_color=_palette.get("surface", "#111b2e"),
			hover_color=_palette.get("surface", "#111b2e"),
			text_color=_palette.get("text", "#e2e8f0"),
			command=lambda user=author: _open_profile(user),
		).grid(row=0, column=0)


def _render_search_result(container: ctk.CTkScrollableFrame, row: int, username: str) -> None:
	palette = _palette
	card = ctk.CTkFrame(container, corner_radius=12, fg_color=palette.get("card", "#18263f"))
	card.grid(row=row, column=0, sticky="we", padx=0, pady=6)
	card.grid_columnconfigure(0, weight=1)
	label_text = _ellipsize(f"@{username}", 26)
	title = ctk.CTkLabel(
		card,
		text=label_text,
		font=ctk.CTkFont(size=14, weight="bold"),
		text_color=palette.get("text", "#e2e8f0"),
	)
	title.grid(row=0, column=0, sticky="w", padx=16, pady=(12, 2))
	data = users.get(username, {})
	followers = len(data.get("followers", []))
	following = len(data.get("following", []))
	metrics = ctk.CTkLabel(
		card,
		text=f"{followers} followers · {following} following",
		text_color=palette.get("muted", "#94a3b8"),
		font=ctk.CTkFont(size=12),
	)
	metrics.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 12))
	actions = ctk.CTkFrame(card, fg_color="transparent")
	actions.grid(row=0, column=1, rowspan=2, sticky="e", padx=12, pady=12)
	actions.grid_columnconfigure(0, weight=1)
	is_self = username == _ui_state.current_user
	view_btn = ctk.CTkButton(
		actions,
		text="View",
		width=80,
		fg_color=palette.get("surface", "#111b2e"),
		hover_color=palette.get("card", "#18263f"),
		text_color=palette.get("text", "#e2e8f0"),
		command=lambda user=username: _open_profile(user),
	)
	view_btn.grid(row=0, column=0, sticky="e", padx=(0, 6))
	if is_self:
		ctk.CTkLabel(
			actions,
			text="This is you",
			text_color=palette.get("muted", "#94a3b8"),
			font=ctk.CTkFont(size=12, slant="italic"),
		).grid(row=0, column=1, sticky="e")
		return
	current = _ui_state.current_user or ""
	is_following = current and username in users.get(current, {}).get("following", [])
	if is_following:
		follow_btn = ctk.CTkButton(
			actions,
			text="Following",
			width=100,
			fg_color="transparent",
			border_width=1,
			border_color=palette.get("muted", "#94a3b8"),
			text_color=palette.get("muted", "#94a3b8"),
			hover_color=palette.get("surface", "#111b2e"),
			command=lambda user=username: _handle_unfollow(user),
		)
	else:
		follow_btn = ctk.CTkButton(
			actions,
			text="Follow",
			width=100,
			fg_color=palette.get("accent", "#4c8dff"),
			hover_color=palette.get("accent_hover", "#3b6dd6"),
			command=lambda user=username: _handle_follow(user),
		)
	follow_btn.grid(row=0, column=1, sticky="e")


def _render_search() -> None:
	results: Optional[ctk.CTkScrollableFrame] = _search_widgets.get("results")
	entry: Optional[ctk.CTkEntry] = _search_widgets.get("entry")
	status: Optional[ctk.CTkLabel] = _search_widgets.get("status")
	if not results:
		return
	results.grid_columnconfigure(0, weight=1)
	for child in results.winfo_children():
		child.destroy()
	query = _ui_state.search_query
	if entry and entry.get().strip() != query:
		entry.delete(0, tk.END)
		if query:
			entry.insert(0, query)
	if entry and _ui_state.active_view == "search":
		entry.focus_set()
		entry.icursor(len(entry.get()))
	hashtag_stats = _collect_hashtag_stats()
	_search_widgets["hashtag_stats"] = hashtag_stats
	if status:
		status.grid_remove()
	row = 0
	if not query:
		_ui_state.search_results = []
		_render_search_overview(results, hashtag_stats, start_row=row, compact=False)
		return
	if query.startswith("#"):
		tag_matches = _search_hashtag_entries(query, limit=8, stats=hashtag_stats)
		_ui_state.search_results = []
		if tag_matches:
			row = _render_hashtag_section(results, tag_matches, row, header="Hashtags")
		else:
			if status:
				status.configure(text="No hashtags found.", text_color=_palette.get("muted", "#94a3b8"))
				status.grid(row=2, column=0, sticky="w", padx=16, pady=16)
		_render_search_overview(results, hashtag_stats, start_row=row, compact=True)
		return
	matches = _search_usernames(query)
	_ui_state.search_results = matches
	row = _render_user_section(results, matches, row, header="People")
	if not matches and status:
		status.configure(text="No users found.", text_color=_palette.get("muted", "#94a3b8"))
		status.grid(row=2, column=0, sticky="w", padx=16, pady=16)
	related_tags = _search_hashtag_entries(query, limit=6, stats=hashtag_stats)
	row = _render_hashtag_section(results, related_tags, row, header="Related hashtags")
	_render_search_overview(results, hashtag_stats, start_row=row, compact=True)


def _set_search_query(value: str) -> None:
	value = (value or "").strip()
	if value == _ui_state.search_query and "search" not in _ui_state.dirty_views:
		_render_search()
		return
	_ui_state.search_query = value
	_mark_dirty("search")
	if _ui_state.active_view == "search":
		_request_render("search")


def _handle_search_submit(event: Optional[Any] = None) -> None:
	entry: Optional[ctk.CTkEntry] = _search_widgets.get("entry")
	if not entry:
		return
	_set_search_query(entry.get())
	if event:
		return "break"


def _handle_search_change(event: Optional[Any] = None) -> None:
	global _search_after_handle
	entry: Optional[ctk.CTkEntry] = _search_widgets.get("entry")
	if not entry:
		return
	if _search_after_handle:
		try:
			entry.after_cancel(_search_after_handle)
		except Exception:
			pass

	def _apply() -> None:
		global _search_after_handle
		_search_after_handle = None
		_set_search_query(entry.get())

	_search_after_handle = entry.after(180, _apply)


def _load_story_display_image(story: dict[str, Any]) -> Optional[tk.PhotoImage]:
	path = story.get("path")
	if not path:
		return None
	abs_path = _resolve_media_path(str(path))
	if Image is not None and ImageTk is not None:
		try:
			with Image.open(abs_path) as source:
				display = source.convert("RGBA")
			return _make_photo_image(display, 640, 900)
		except Exception:
			pass
	return _load_image_for_tk(str(path), max_width=640)


def _handle_add_story() -> None:
	if not require_login("add a story"):
		return
	selected = filedialog.askopenfilename(title="Select image or video")
	if not selected:
		return
	ext_type = _classify_attachment(selected)
	if ext_type not in {"image", "video"}:
		messagebox.showwarning("Unsupported file", "Stories support images or videos only.")
		return
	rel_path = copy_file_to_media(selected, base_dir=BASE_DIR, media_dir=MEDIA_DIR)
	if not rel_path:
		return
	_open_story_editor(rel_path, ext_type)


def _open_story_editor(rel_path: str, story_type: str) -> None:
	overlay = _prepare_story_overlay()
	if not overlay:
		_delete_media_file(rel_path)
		return

	panel = ctk.CTkFrame(overlay, corner_radius=24, fg_color=_palette.get("surface", "#111b2e"))
	panel.pack(expand=True, fill="both", padx=40, pady=40)
	panel.grid_rowconfigure(2, weight=1)
	panel.grid_columnconfigure(0, weight=1)

	header = ctk.CTkFrame(panel, fg_color="transparent")
	header.grid(row=0, column=0, sticky="we", padx=20, pady=(20, 10))
	header.grid_columnconfigure(0, weight=1)

	title = ctk.CTkLabel(
		header,
		text="Edit Story",
		font=ctk.CTkFont(size=20, weight="bold"),
		text_color=_palette.get("text", "#e2e8f0"),
	)
	title.grid(row=0, column=0, sticky="w")

	def _close_editor_remove() -> None:
		_delete_media_file(rel_path)
		_hide_story_overlay()

	close_btn = ctk.CTkButton(
		header,
		text="Close",
		width=70,
		command=_close_editor_remove,
		fg_color="transparent",
		border_width=1,
		border_color=_palette.get("muted", "#94a3b8"),
		text_color=_palette.get("muted", "#94a3b8"),
		hover_color=_palette.get("card", "#18263f"),
	)
	close_btn.grid(row=0, column=1, sticky="e")

	preview_frame = ctk.CTkFrame(panel, corner_radius=16, fg_color=_palette.get("card", "#18263f"))
	preview_frame.grid(row=1, column=0, sticky="nswe", padx=20, pady=(0, 12))
	preview_frame.grid_rowconfigure(0, weight=1)
	preview_frame.grid_columnconfigure(0, weight=1)
	preview_story = {"path": rel_path, "type": story_type}
	preview_photo = _load_story_display_image(preview_story)
	if preview_photo is not None:
		image_label = tk.Label(preview_frame, image=preview_photo, bd=0, bg=_palette.get("card", "#18263f"))
		image_label.image = preview_photo  # type: ignore[attr-defined]
		image_label.grid(row=0, column=0, sticky="nswe", padx=12, pady=12)
	else:
		ctk.CTkLabel(
			preview_frame,
			text="Preview unavailable",
			text_color=_palette.get("muted", "#94a3b8"),
		).grid(row=0, column=0, sticky="nswe", padx=16, pady=16)

	caption_box = ctk.CTkTextbox(panel, height=120, wrap="word")
	caption_box.grid(row=2, column=0, sticky="we", padx=20, pady=(0, 10))
	caption_box.focus_set()

	ctk.CTkLabel(
		panel,
		text="Add text for your story. Type @username to mention someone.",
		text_color=_palette.get("muted", "#94a3b8"),
		wraplength=460,
		justify="left",
	).grid(row=3, column=0, sticky="we", padx=24, pady=(0, 8))

	button_row = ctk.CTkFrame(panel, fg_color="transparent")
	button_row.grid(row=4, column=0, sticky="we", padx=20, pady=(8, 20))
	button_row.grid_columnconfigure(0, weight=1)
	button_row.grid_columnconfigure(1, weight=1)

	def _post_story() -> None:
		author = _ui_state.current_user
		if not author:
			messagebox.showinfo("Sign in required", "You must sign in to post a story.")
			_delete_media_file(rel_path)
			_hide_story_overlay()
			return
		text_content = caption_box.get("1.0", "end").strip()
		mention_candidates = re.findall(r"@([A-Za-z0-9_]+)", text_content)
		lookup = {name.lower(): name for name in users.keys()}
		resolved_mentions: list[str] = []
		missing_mentions: list[str] = []
		for raw in mention_candidates:
			resolved = lookup.get(raw.lower())
			if resolved:
				if resolved not in resolved_mentions and resolved != author:
					resolved_mentions.append(resolved)
			else:
				missing_mentions.append(raw)
		created_epoch = time.time()
		story_entry = {
			"id": str(uuid4()),
			"author": author,
			"path": rel_path,
			"type": story_type,
			"created_at": now_ts(),
			"created_at_epoch": created_epoch,
			"expires_at": created_epoch + STORY_TTL_SECONDS,
		}
		if text_content:
			story_entry["text"] = text_content
		if resolved_mentions:
			story_entry["mentions"] = resolved_mentions
		media_sync_failed = not upload_media_asset(rel_path)
		stories.append(story_entry)
		stories.sort(key=lambda s: s.get("created_at_epoch", 0))
		
		# Immediate real-time sync for stories
		trigger_immediate_sync("stories")
		if media_sync_failed:
			_notify_remote_sync_issue("media", "upload the story media")
		_mark_story_author_unseen_for_all(author)
		mentions_delivered = False
		if text_content and resolved_mentions:
			mentions_delivered = notify_mentions(
				author,
				text_content,
				"their story",
				mentions=resolved_mentions,
				meta_factory=lambda _user: {
					"type": "mention",
					"resource": "story",
					"story_id": story_entry.get("id"),
					"from": author,
				},
			)
		if missing_mentions:
			messagebox.showwarning(
				"Some mentions not found",
				"The following usernames were not recognized and were ignored: "
				+ ", ".join(sorted(set(missing_mentions))),
			)
		if mentions_delivered:
			trigger_immediate_sync("notifications")
			_refresh_notifications_ui()
		messagebox.showinfo("Story posted", "Your story has been added.")
		_hide_story_overlay()

	cancel_btn = ctk.CTkButton(
		button_row,
		text="Cancel",
		command=_close_editor_remove,
		fg_color="transparent",
		border_width=1,
		border_color=_palette.get("muted", "#94a3b8"),
		text_color=_palette.get("muted", "#94a3b8"),
		hover_color=_palette.get("card", "#18263f"),
	)
	cancel_btn.grid(row=0, column=0, sticky="we", padx=(0, 6))

	post_btn = ctk.CTkButton(
		button_row,
		text="Post Story",
		command=_post_story,
		fg_color=_palette.get("accent", "#4c8dff"),
		hover_color=_palette.get("accent_hover", "#3b6dd6"),
	)
	post_btn.grid(row=0, column=1, sticky="we", padx=(6, 0))

	def _handle_escape(event) -> str:
		_close_editor_remove()
		return "break"

	overlay.bind("<Escape>", _handle_escape)


def _cancel_story_auto(state: dict[str, Any]) -> None:
	after_id = state.get("auto_after")
	owner: Optional[tk.Misc] = state.get("window")
	if after_id and owner and owner.winfo_exists():
		try:
			owner.after_cancel(after_id)
		except Exception:
			pass
	state["auto_after"] = None


def _close_story_viewer() -> None:
	global _active_story_viewer
	state = _active_story_viewer
	if not state:
		return
	_cancel_story_auto(state)
	session = state.get("video_session")
	if session:
		_stop_inline_video(session)
	_hide_story_overlay()
	_active_story_viewer = None


def _schedule_story_auto(state: dict[str, Any], delay_ms: int) -> None:
	owner: Optional[tk.Misc] = state.get("window")
	if not owner or not owner.winfo_exists():
		return
	_cancel_story_auto(state)
	state["auto_after"] = owner.after(delay_ms, _show_next_story)


def _update_story_controls(state: dict[str, Any]) -> None:
	items = state.get("items", [])
	index = state.get("index", 0)
	prev_btn: Optional[ctk.CTkButton] = state.get("prev_btn")
	next_btn: Optional[ctk.CTkButton] = state.get("next_btn")
	count = len(items)
	if prev_btn:
		prev_btn.configure(state="normal" if index > 0 else "disabled")
	if next_btn:
		next_btn.configure(state="normal" if index < count - 1 else "disabled")
	progress: Optional[ctk.CTkProgressBar] = state.get("progress")
	if progress and count:
		progress.set((index + 1) / count)
	like_btn: Optional[ctk.CTkButton] = state.get("like_btn")
	dislike_btn: Optional[ctk.CTkButton] = state.get("dislike_btn")
	story = items[index] if 0 <= index < count else None
	muted = _palette.get("muted", "#94a3b8")
	accent = _palette.get("accent", "#2563eb")
	accent_hover = _palette.get("accent_hover", "#1d4ed8")
	danger = _palette.get("danger", "#ef4444")
	danger_hover = _palette.get("danger_hover", "#dc2626")
	user = _ui_state.current_user or ""
	if story:
		liked, disliked = _ensure_story_reaction_lists(story)
		likes = story.get("likes") if isinstance(story.get("likes"), int) else len(liked)
		dislikes = story.get("dislikes") if isinstance(story.get("dislikes"), int) else len(disliked)
		is_liked = user in liked
		is_disliked = user in disliked
		if like_btn:
			like_btn.configure(
				text=f"Like ({likes})",
				state="normal" if user else "disabled",
				fg_color=accent if is_liked else "transparent",
				text_color="#f8fafc" if is_liked else muted,
				hover_color=accent_hover,
				border_width=0 if is_liked else 1,
				border_color=muted,
			)
		if dislike_btn:
			dislike_btn.configure(
				text=f"Dislike ({dislikes})",
				state="normal" if user else "disabled",
				fg_color=danger if is_disliked else "transparent",
				text_color="#f8fafc" if is_disliked else muted,
				hover_color=danger_hover,
				border_width=0 if is_disliked else 1,
				border_color=muted,
			)
	else:
		if like_btn:
			like_btn.configure(
				text="Like (0)",
				state="disabled",
				fg_color="transparent",
				text_color=muted,
				border_width=1,
				border_color=muted,
			)
		if dislike_btn:
			dislike_btn.configure(
				text="Dislike (0)",
				state="disabled",
				fg_color="transparent",
				text_color=muted,
				border_width=1,
				border_color=muted,
			)


def _find_video(video_id: str) -> Optional[dict[str, Any]]:
	for item in videos:
		if item.get("id") == video_id:
			return item
	return None


def _find_story(story_id: str) -> Optional[dict[str, Any]]:
	needle = str(story_id or "").strip()
	if not needle:
		return None
	for story in stories:
		story_key = str(story.get("id") or "").strip()
		if story_key and story_key == needle:
			return story
		path_key = str(story.get("path") or "").strip()
		if path_key and path_key == needle:
			return story
	return None


def _find_post_index(post_id: str) -> Optional[int]:
	target = str(post_id or "").strip()
	if not target:
		return None
	for idx, post in enumerate(posts):
		if str(post.get("id") or "").strip() == target:
			return idx
	return None


def _focus_post_from_notification(post_id: str, *, reply_id: Optional[str] = None) -> None:
	if not post_id:
		return
	index = _find_post_index(post_id)
	if index is None:
		messagebox.showinfo("Post unavailable", "That post is no longer available.")
		return
	_feed_state = _ui_state.feed_state
	_feed_state.focus_post_id = str(post_id)
	_feed_state.focus_reply_id = str(reply_id) if reply_id else None
	if reply_id:
		_feed_state.expanded_replies.add(index)
	_mark_dirty("home")
	_request_render("home")
	if _show_frame_cb:
		_show_frame_cb("home")


def _open_story_from_notification(story_id: str) -> None:
	if not story_id:
		return
	story = _find_story(story_id)
	if not story:
		messagebox.showinfo("Story unavailable", "That story has expired or was removed.")
		return
	author = story.get("author") or ""
	_open_story_viewer(author, story_id=story_id)


def _open_video_from_notification(video_id: str, *, open_comments: bool = False) -> None:
	if not video_id:
		return
	global _video_focus_id, _video_focus_open_comments
	_video_focus_id = video_id
	_video_focus_open_comments = open_comments
	_mark_dirty("videos")
	_request_render("videos")
	if _show_frame_cb:
		_show_frame_cb("videos")


def _find_video_comment(video: dict[str, Any], comment_id: str) -> Optional[dict[str, Any]]:
	for comment in video.get("comments", []):
		if comment.get("id") == comment_id:
			return comment
	return None


def _render_video_comments(video_id: str) -> None:
	card = _video_cards.get(video_id)
	if not card:
		return
	comments_frame: ctk.CTkScrollableFrame = card.get("comments_list")
	if not comments_frame:
		return
	for child in comments_frame.winfo_children():
		child.destroy()
	video = _find_video(video_id)
	if not video:
		return
	reply_vars: dict[str, tk.StringVar] = card.setdefault("reply_vars", {})
	comment_items = video.get("comments", [])
	if not comment_items:
		ctk.CTkLabel(
			comments_frame,
			text="No comments yet",
			text_color=_palette.get("muted", "#94a3b8"),
		).grid(row=0, column=0, padx=12, pady=12, sticky="w")
		return
	for idx, comment in enumerate(comment_items):
		comment_id = comment.get("id") or str(uuid4())
		comment["id"] = comment_id
		replies = comment.get("replies")
		if not isinstance(replies, list):
			replies = []
			comment["replies"] = replies
		item = ctk.CTkFrame(
			comments_frame,
			fg_color=_palette.get("surface", "#111b2e"),
			corner_radius=10,
		)
		item.grid(row=idx, column=0, sticky="we", padx=8, pady=(4, 8))
		item.grid_columnconfigure(0, weight=1)
		item.grid_columnconfigure(1, weight=0)
		author = f"@{comment.get('author', 'unknown')}"
		ctk.CTkLabel(
			item,
			text=author,
			font=ctk.CTkFont(size=13, weight="bold"),
			text_color=_palette.get("text", "#e2e8f0"),
		).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 4))
		ctk.CTkLabel(
			item,
			text=str(comment.get("text", "")),
			text_color=_palette.get("text", "#e2e8f0"),
			wraplength=220,
			justify="left",
		).grid(row=1, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 6))
		ctk.CTkLabel(
			item,
			text=str(comment.get("created_at", "")),
			text_color=_palette.get("muted", "#94a3b8"),
			font=ctk.CTkFont(size=11),
		).grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 6))
		replies_holder = ctk.CTkFrame(item, fg_color=_palette.get("card", "#1f2937"))
		replies_holder.grid(row=3, column=0, columnspan=2, sticky="we", padx=10, pady=(0, 8))
		replies_holder.grid_columnconfigure(0, weight=1)
		if replies:
			for r_idx, reply in enumerate(replies):
				reply_frame = ctk.CTkFrame(
					replies_holder,
					fg_color="transparent",
					corner_radius=8,
				)
				reply_frame.grid(row=r_idx, column=0, sticky="we", pady=(4 if r_idx else 0, 4))
				reply_frame.grid_columnconfigure(0, weight=1)
				ctk.CTkLabel(
					reply_frame,
					text=f"@{reply.get('author', 'unknown')}",
					font=ctk.CTkFont(size=12, weight="bold"),
					text_color=_palette.get("text", "#e2e8f0"),
				).grid(row=0, column=0, sticky="w", padx=8, pady=(2, 2))
				ctk.CTkLabel(
					reply_frame,
					text=str(reply.get("text", "")),
					text_color=_palette.get("text", "#e2e8f0"),
					wraplength=200,
					justify="left",
				).grid(row=1, column=0, sticky="w", padx=8)
				ctk.CTkLabel(
					reply_frame,
					text=str(reply.get("created_at", "")),
					text_color=_palette.get("muted", "#94a3b8"),
					font=ctk.CTkFont(size=10),
				).grid(row=2, column=0, sticky="w", padx=8, pady=(0, 2))
		reply_var = reply_vars.get(comment_id)
		if reply_var is None:
			reply_var = tk.StringVar()
			reply_vars[comment_id] = reply_var
		reply_controls = ctk.CTkFrame(item, fg_color="transparent")
		reply_controls.grid(row=4, column=0, columnspan=2, sticky="we", padx=10, pady=(0, 6))
		reply_controls.grid_columnconfigure(0, weight=1)
		reply_entry = ctk.CTkEntry(
			reply_controls,
			textvariable=reply_var,
			placeholder_text=f"Reply to {author}",
		)
		reply_entry.grid(row=0, column=0, sticky="we")
		_bind_return_submit(
			reply_entry,
			lambda vid=video_id, cid=comment_id, var=reply_var: _submit_video_comment_reply(vid, cid, var),
		)
		send_btn = ctk.CTkButton(
			reply_controls,
			text="Reply",
			width=90,
			command=lambda vid=video_id, cid=comment_id, var=reply_var: _submit_video_comment_reply(vid, cid, var),
		)
		send_btn.grid(row=1, column=0, sticky="e", pady=(6, 0))
		reply_entry.bind(
			"<FocusIn>",
			lambda _evt, entry=reply_entry: entry.configure(placeholder_text=""),
		)
		reply_entry.bind(
			"<FocusOut>",
			lambda _evt, entry=reply_entry, author_name=author: entry.configure(placeholder_text=f"Reply to {author_name}"),
		)
	_update_video_reaction_ui(video_id)


def _submit_video_comment(video_id: str) -> None:
	if not require_login("comment on videos"):
		return
	card = _video_cards.get(video_id)
	if not card:
		return
	entry: ctk.CTkEntry = card.get("entry")
	if not entry:
		return
	text = entry.get().strip()
	if not text:
		_set_video_status("Write a comment first", error=True)
		return
	video = _find_video(video_id)
	if not video:
		return
	comment = {
		"id": str(uuid4()),
		"author": _ui_state.current_user,
		"text": text,
		"created_at": now_ts(),
		"replies": [],
	}
	video.setdefault("comments", []).append(comment)
	resolved, missing = _split_mentions(text, author=_ui_state.current_user)
	mentions_delivered = False
	if resolved:
		comment_id = comment.get("id")
		mentions_delivered = notify_mentions(
			_ui_state.current_user,
			text,
			"a video comment",
			mentions=resolved,
			meta_factory=lambda _user: {
				"type": "mention",
				"resource": "video_comment",
				"video_id": video_id,
				"comment_id": comment_id,
				"from": _ui_state.current_user,
			},
		)
	entry.delete(0, tk.END)
	if missing:
		_set_video_status(
			"Some mentions were not found: " + ", ".join(f"@{name}" for name in missing),
			error=True,
		)
	persist()
	if mentions_delivered:
		trigger_immediate_sync("notifications")
		_refresh_notifications_ui()
	_render_video_comments(video_id)


def _submit_video_comment_reply(video_id: str, comment_id: str, text_var: tk.StringVar) -> None:
	if not require_login("reply to video comments"):
		return
	text = text_var.get().strip()
	if not text:
		_set_video_status("Write a reply first", error=True)
		return
	video = _find_video(video_id)
	if not video:
		return
	comment = _find_video_comment(video, comment_id)
	if not comment:
		return
	replies = comment.setdefault("replies", [])
	if not isinstance(replies, list):
		replies = []
		comment["replies"] = replies
	reply = {
		"id": str(uuid4()),
		"author": _ui_state.current_user,
		"text": text,
		"created_at": now_ts(),
	}
	replies.append(reply)
	resolved, missing = _split_mentions(text, author=_ui_state.current_user)
	mentions_delivered = False
	if resolved:
		reply_id = reply.get("id")
		mentions_delivered = notify_mentions(
			_ui_state.current_user,
			text,
			"a video reply",
			mentions=resolved,
			meta_factory=lambda _user: {
				"type": "mention",
				"resource": "video_reply",
				"video_id": video_id,
				"comment_id": comment_id,
				"reply_id": reply_id,
				"from": _ui_state.current_user,
			},
		)
	text_var.set("")
	if missing:
		_set_video_status(
			"Some mentions were not found: " + ", ".join(f"@{name}" for name in missing),
			error=True,
		)
	persist()
	if mentions_delivered:
		trigger_immediate_sync("notifications")
		_refresh_notifications_ui()
	_render_video_comments(video_id)


def _toggle_video_comments(video_id: str) -> None:
	card = _video_cards.get(video_id)
	if not card:
		return
	panel: ctk.CTkFrame = card.get("panel")
	if not panel:
		return
	comment_btn: ctk.CTkButton = card.get("comment_button")
	visible = card.get("panel_visible", False)
	if visible:
		panel.grid_remove()
		card["panel_visible"] = False
		_style_video_action_button(comment_btn, active=False)
	else:
		panel.grid()
		card["panel_visible"] = True
		_render_video_comments(video_id)
		_style_video_action_button(comment_btn, active=True)
	_update_video_reaction_ui(video_id)


def _open_video_fullscreen(video_id: str) -> None:
	card = _video_cards.get(video_id)
	if not card:
		return
	attachment = card.get("attachment")
	if not isinstance(attachment, dict):
		_set_video_status("Unable to open video", error=True)
		return
	root = _videos_widgets.get("frame")
	if not root:
		return
	existing = _video_fullscreen_windows.get(video_id)
	window: Optional[ctk.CTkToplevel] = None
	if existing:
		window = existing.get("window")
		if window and window.winfo_exists():
			window.deiconify()
			window.lift()
			window.focus_set()
			return
		_video_fullscreen_windows.pop(video_id, None)
	window = ctk.CTkToplevel(root)
	window.title("Full Screen Video")
	window.configure(fg_color=_palette.get("base", "#0f172a"))
	try:
		window.state("zoomed")
	except Exception:
		window.geometry("960x720")
	shell = ctk.CTkFrame(window, fg_color="transparent")
	shell.pack(fill="both", expand=True, padx=24, pady=24)
	shell.grid_columnconfigure(0, weight=1)
	shell.grid_rowconfigure(0, weight=1)
	video_frame = ctk.CTkFrame(shell, fg_color=_palette.get("card", "#1f2937"), corner_radius=18)
	video_frame.grid(row=0, column=0, sticky="nsew")
	video_frame.grid_columnconfigure(0, weight=1)
	video_frame.grid_rowconfigure(0, weight=1)
	inner = ctk.CTkFrame(video_frame, fg_color="transparent")
	inner.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
	_render_inline_video(attachment, inner, controls=True, click_to_toggle=True)
	controls_row = ctk.CTkFrame(shell, fg_color="transparent")
	controls_row.grid(row=1, column=0, sticky="e", pady=(12, 0))
	exit_btn = ctk.CTkButton(
		controls_row,
		text="Exit Full Screen",
		width=150,
		command=lambda vid=video_id: _close_video_fullscreen(vid),
	)
	exit_btn.grid(row=0, column=0, sticky="e")
	window.protocol("WM_DELETE_WINDOW", lambda vid=video_id: _close_video_fullscreen(vid))
	_video_fullscreen_windows[video_id] = {"window": window}
	window.focus_set()
	window.lift()


def _close_video_fullscreen(video_id: str) -> None:
	info = _video_fullscreen_windows.pop(video_id, None)
	window: Optional[ctk.CTkToplevel] = None
	if info:
		window = info.get("window")
		if window and window.winfo_exists():
			try:
				window.destroy()
			except Exception:
				pass
	attachment = None
	card = _video_cards.get(video_id)
	if card:
		attachment = card.get("attachment")
	if isinstance(attachment, dict):
		rel_path = attachment.get("path")
		if rel_path:
			session = _ensure_video_session(rel_path)
			_stop_inline_video(session)
	_render_videos()


def _render_videos() -> None:
	global _video_focus_id, _video_focus_open_comments
	feed: ctk.CTkScrollableFrame = _videos_widgets.get("feed")
	if not feed:
		return
	for child in feed.winfo_children():
		child.destroy()
	_video_cards.clear()
	feed.grid_columnconfigure(0, weight=1)
	comment_icon = _ensure_comment_icon()
	if not videos:
		ctk.CTkLabel(
			feed,
			text="No videos yet",
			text_color=_palette.get("muted", "#94a3b8"),
		).grid(row=0, column=0, padx=24, pady=24)
		return
	for idx, video in enumerate(reversed(videos)):
		video_id = video.get("id") or str(uuid4())
		video["id"] = video_id
		_ensure_video_reaction_lists(video)
		card = ctk.CTkFrame(
			feed,
			fg_color=_palette.get("surface", "#111b2e"),
			corner_radius=18,
		)
		card.grid(row=idx, column=0, sticky="nsew", padx=24, pady=(12 if idx else 18, 18))
		card.grid_columnconfigure(0, weight=6)
		card.grid_columnconfigure(1, weight=1)
		card.grid_columnconfigure(2, weight=3)
		card.grid_rowconfigure(0, weight=1)
		if _video_focus_id and video_id == _video_focus_id:
			try:
				card.configure(border_width=2, border_color=_palette.get("accent", "#4c8dff"))
			except Exception:
				card.configure(fg_color="#132036")
		video_container = ctk.CTkFrame(
			card,
			fg_color=_palette.get("card", "#1f2937"),
			corner_radius=18,
		)
		video_container.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)
		video_container.grid_columnconfigure(0, weight=1)
		video_container.grid_rowconfigure(0, weight=1)
		video_container.configure(width=640, height=860)
		video_container.grid_propagate(False)
		video_holder = ctk.CTkFrame(video_container, fg_color="transparent")
		video_holder.grid(row=0, column=0, sticky="nsew")
		attachment = {"type": "video", "path": video.get("path", "")}
		_render_inline_video(
			attachment,
			video_holder,
			controls=False,
			click_to_toggle=True,
		)
		base_children = video_holder.winfo_children()
		overlay_parent = base_children[0] if base_children else video_holder
		avatar_photo = _load_profile_avatar(video.get("author", ""), 48)
		overlay_bg = "#020617"
		overlay = tk.Frame(overlay_parent, bg=overlay_bg, bd=0)
		overlay.place(relx=0.02, rely=0.98, anchor="sw")
		if avatar_photo:
			a_label = tk.Label(overlay, image=avatar_photo, bd=0, bg=overlay_bg)
			a_label.image = avatar_photo  # keep reference
			a_label.pack(side="left", padx=(6, 8), pady=6)
		name_lbl = tk.Label(
			overlay,
			text=f"@{video.get('author', 'unknown')}",
			font=("Segoe UI", 12, "bold"),
			fg=_palette.get("text", "#f8fafc"),
			bg=overlay_bg,
		)
		name_lbl.pack(side="left", pady=6, padx=(0, 10))
		full_btn = ctk.CTkButton(
			overlay_parent,
			text="Full Screen",
			width=110,
			command=lambda vid=video_id: _open_video_fullscreen(vid),
			fg_color=_palette.get("surface", "#111b2e"),
			hover_color=_palette.get("accent", "#2563eb"),
		)
		full_btn.place(relx=0.98, rely=0.05, anchor="ne")
		caption = video.get("caption")
		if caption:
			ctk.CTkLabel(
				video_container,
				text=str(caption),
				text_color=_palette.get("text", "#e2e8f0"),
				wraplength=520,
				justify="left",
			).grid(row=1, column=0, sticky="we", padx=16, pady=(12, 0))
		actions = ctk.CTkFrame(card, fg_color="transparent")
		actions.grid(row=0, column=1, sticky="ns", padx=(12, 6), pady=24)
		actions.grid_columnconfigure(0, weight=1)
		like_icon = _ensure_reaction_icon("like")
		dislike_icon = _ensure_reaction_icon("dislike")
		like_btn = ctk.CTkButton(
			actions,
			text="Like 0",
			width=90,
			image=like_icon,
			compound="top",
			command=lambda vid=video_id: _toggle_video_reaction(vid, "like"),
		)
		like_btn.grid(row=0, column=0, sticky="we", pady=(0, 12))
		dislike_btn = ctk.CTkButton(
			actions,
			text="Dislike 0",
			width=90,
			image=dislike_icon,
			compound="top",
			command=lambda vid=video_id: _toggle_video_reaction(vid, "dislike"),
		)
		dislike_btn.grid(row=1, column=0, sticky="we", pady=(0, 12))
		if comment_icon is not None:
			comment_btn = ctk.CTkButton(
				actions,
				text="Comments 0",
				width=90,
				image=comment_icon,
				compound="top",
				command=lambda vid=video_id: _toggle_video_comments(vid),
			)
		else:
			comment_btn = ctk.CTkButton(
				actions,
				text="Comments 0",
				width=90,
				command=lambda vid=video_id: _toggle_video_comments(vid),
			)
		comment_btn.grid(row=2, column=0, sticky="we")
		panel = ctk.CTkFrame(
			card,
			fg_color=_palette.get("surface", "#111b2e"),
			corner_radius=18,
			width=280,
		)
		panel.grid(row=0, column=2, sticky="ns", padx=(12, 18), pady=16)
		panel.grid_rowconfigure(1, weight=1)
		panel.grid_columnconfigure(0, weight=1)
		header = ctk.CTkLabel(
			panel,
			text="Comments",
			font=ctk.CTkFont(size=16, weight="bold"),
			text_color=_palette.get("text", "#e2e8f0"),
		)
		header.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 8))
		comments_frame = ctk.CTkScrollableFrame(panel, fg_color=_palette.get("card", "#1f2937"))
		comments_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))
		entry = ctk.CTkEntry(panel, placeholder_text="Add a comment")
		entry.grid(row=2, column=0, sticky="we", padx=12, pady=(0, 8))
		_bind_return_submit(entry, lambda vid=video_id: _submit_video_comment(vid))
		submit_btn = ctk.CTkButton(
			panel,
			text="Post",
			command=lambda vid=video_id: _submit_video_comment(vid),
		)
		submit_btn.grid(row=3, column=0, sticky="we", padx=12, pady=(0, 12))
		panel.grid_remove()
		_video_cards[video_id] = {
			"panel": panel,
			"panel_visible": False,
			"comments_list": comments_frame,
			"entry": entry,
			"comment_button": comment_btn,
			"like_button": like_btn,
			"dislike_button": dislike_btn,
			"avatar_photo": avatar_photo,
			"video_holder": video_holder,
			"attachment": attachment,
			"fullscreen_button": full_btn,
			"reply_vars": {},
			"card_frame": card,
		}
		if _video_focus_id and video_id == _video_focus_id and _video_focus_open_comments:
			if not _video_cards[video_id]["panel_visible"]:
				_toggle_video_comments(video_id)
		_update_video_reaction_ui(video_id)

	_video_focus_id = None
	_video_focus_open_comments = False

def _show_story_slide() -> None:
	state = _active_story_viewer
	if not state:
		return
	items: list[dict[str, Any]] = state.get("items", [])
	if not items:
		_close_story_viewer()
		return
	index = max(0, min(state.get("index", 0), len(items) - 1))
	state["index"] = index
	item = items[index]
	media_frame: Optional[ctk.CTkFrame] = state.get("media_frame")
	if not media_frame or not media_frame.winfo_exists():
		_close_story_viewer()
		return
	_cancel_story_auto(state)
	session = state.get("video_session")
	if session:
		_stop_inline_video(session)
	state["video_session"] = None
	for child in media_frame.winfo_children():
		child.destroy()
	media_frame.grid_rowconfigure(0, weight=1)
	media_frame.grid_rowconfigure(1, weight=0)
	media_frame.grid_columnconfigure(0, weight=1)
	if item.get("type") == "video":
		video_holder = ctk.CTkFrame(media_frame, fg_color="transparent")
		video_holder.grid(row=0, column=0, sticky="nswe", padx=12, pady=12)
		attachment = {"type": "video", "path": item.get("path")}
		_render_inline_video(attachment, video_holder, controls=False, click_to_toggle=True)
		session = _ensure_video_session(str(item.get("path", "")))
		state["video_session"] = session
	else:
		photo = _load_story_display_image(item)
		if photo:
			label = tk.Label(media_frame, image=photo, bd=0, bg=_palette.get("card", "#18263f"))
			label.image = photo  # type: ignore[attr-defined]
			label.grid(row=0, column=0, sticky="nswe", padx=12, pady=12)
		else:
			ctk.CTkLabel(
				media_frame,
				text="Story media unavailable",
				text_color=_palette.get("muted", "#94a3b8"),
			).grid(row=0, column=0, sticky="nswe", padx=12, pady=12)
		_schedule_story_auto(state, 5000)
	overlay_text = (item.get("text") or "").strip()
	if overlay_text:
		overlay_frame = ctk.CTkFrame(media_frame, fg_color="#0f172a", corner_radius=10)
		overlay_frame.grid(row=1, column=0, sticky="we", padx=16, pady=(0, 16))
		overlay_frame.grid_columnconfigure(0, weight=1)
		ctk.CTkLabel(
			overlay_frame,
			text=overlay_text,
			text_color="#f8fafc",
			wraplength=420,
			justify="center",
			anchor="center",
		).grid(row=0, column=0, padx=12, pady=10)
	_update_story_controls(state)


def _show_next_story() -> None:
	state = _active_story_viewer
	if not state:
		return
	items = state.get("items", [])
	if state.get("index", 0) < len(items) - 1:
		state["index"] = state.get("index", 0) + 1
		_show_story_slide()
	else:
		_close_story_viewer()


def _show_prev_story() -> None:
	state = _active_story_viewer
	if not state:
		return
	if state.get("index", 0) > 0:
		state["index"] = state.get("index", 0) - 1
		_show_story_slide()


def _open_story_viewer(author: str, story_id: Optional[str] = None) -> None:
	global _active_story_viewer
	_purge_story_cache_if_needed()
	items = [s for s in stories if (s.get("author") or "unknown") == author]
	if not items:
		messagebox.showinfo("No stories", f"@{author} has no active stories right now.")
		return
	items.sort(key=lambda s: s.get("created_at_epoch", 0))
	if _active_story_viewer:
		_close_story_viewer()
	_mark_story_author_seen(author)
	overlay = _prepare_story_overlay()
	if not overlay:
		return

	panel = ctk.CTkFrame(overlay, corner_radius=24, fg_color=_palette.get("surface", "#111b2e"))
	panel.pack(expand=True, fill="both", padx=32, pady=32)
	panel.grid_rowconfigure(2, weight=1)
	panel.grid_columnconfigure(0, weight=1)

	header = ctk.CTkFrame(panel, fg_color="transparent")
	header.grid(row=0, column=0, sticky="we", padx=20, pady=(20, 10))
	header.grid_columnconfigure(0, weight=1)

	title = ctk.CTkLabel(
		header,
		text=f"@{author}",
		font=ctk.CTkFont(size=18, weight="bold"),
		text_color=_palette.get("text", "#e2e8f0"),
	)
	title.grid(row=0, column=0, sticky="w")

	close_btn = ctk.CTkButton(
		header,
		text="Close",
		width=70,
		command=_close_story_viewer,
		fg_color="transparent",
		border_width=1,
		border_color=_palette.get("muted", "#94a3b8"),
		text_color=_palette.get("muted", "#94a3b8"),
		hover_color=_palette.get("card", "#18263f"),
	)
	close_btn.grid(row=0, column=1, sticky="e")

	progress = ctk.CTkProgressBar(
		panel,
		mode="determinate",
		progress_color=_palette.get("accent", "#4c8dff"),
		fg_color=_palette.get("card", "#18263f"),
	)
	progress.grid(row=1, column=0, sticky="we", padx=20, pady=(0, 12))

	media_frame = ctk.CTkFrame(panel, corner_radius=16, fg_color=_palette.get("card", "#18263f"))
	media_frame.grid(row=2, column=0, sticky="nswe", padx=20, pady=(0, 12))

	controls = ctk.CTkFrame(panel, fg_color="transparent")
	controls.grid(row=3, column=0, sticky="we", padx=20, pady=(0, 20))
	controls.grid_columnconfigure(0, weight=1)
	controls.grid_columnconfigure(1, weight=0)
	controls.grid_columnconfigure(2, weight=1)

	prev_btn = ctk.CTkButton(controls, text="Previous", width=100, command=_show_prev_story)
	prev_btn.grid(row=0, column=0, sticky="we", padx=(0, 8))
	reaction_frame = ctk.CTkFrame(controls, fg_color="transparent")
	reaction_frame.grid(row=0, column=1, sticky="n", padx=8)
	reaction_frame.grid_columnconfigure(0, weight=1)
	muted = _palette.get("muted", "#94a3b8")
	accent_hover = _palette.get("accent_hover", "#1d4ed8")
	danger_hover = _palette.get("danger_hover", "#dc2626")
	like_icon = _ensure_reaction_icon("like", size=(34, 34))
	dislike_icon = _ensure_reaction_icon("dislike", size=(34, 34))
	like_btn = ctk.CTkButton(
		reaction_frame,
		text="Like (0)",
		width=140,
		image=like_icon,
		compound="left" if like_icon else "center",
		fg_color="transparent",
		text_color=muted,
		border_width=1,
		border_color=muted,
		hover_color=accent_hover,
		command=lambda: _handle_story_reaction_click("like"),
	)
	like_btn.grid(row=0, column=0, sticky="we", pady=(0, 8))
	if like_icon:
		like_btn._icon_ref = like_icon  # type: ignore[attr-defined]
	dislike_btn = ctk.CTkButton(
		reaction_frame,
		text="Dislike (0)",
		width=140,
		image=dislike_icon,
		compound="left" if dislike_icon else "center",
		fg_color="transparent",
		text_color=muted,
		border_width=1,
		border_color=muted,
		hover_color=danger_hover,
		command=lambda: _handle_story_reaction_click("dislike"),
	)
	dislike_btn.grid(row=1, column=0, sticky="we")
	if dislike_icon:
		dislike_btn._icon_ref = dislike_icon  # type: ignore[attr-defined]
	next_btn = ctk.CTkButton(controls, text="Next", width=100, command=_show_next_story)
	next_btn.grid(row=0, column=2, sticky="we", padx=(8, 0))

	start_index = 0
	if story_id:
		target = str(story_id).strip()
		for idx, candidate in enumerate(items):
			candidate_id = str(candidate.get("id") or candidate.get("path") or "").strip()
			if candidate_id and candidate_id == target:
				start_index = idx
				break

	state = {
		"window": overlay,
		"items": items,
		"index": start_index,
		"media_frame": media_frame,
		"progress": progress,
		"prev_btn": prev_btn,
		"next_btn": next_btn,
		"like_btn": like_btn,
		"dislike_btn": dislike_btn,
		"auto_after": None,
		"video_session": None,
	}
	_active_story_viewer = state

	def _handle_escape(event) -> str:
		_close_story_viewer()
		return "break"

	overlay.bind("<Escape>", _handle_escape)
	_show_story_slide()

def register_nav_controls(
		*,
		home: ctk.CTkButton,
		videos: ctk.CTkButton,
		search: ctk.CTkButton,
		profile: ctk.CTkButton,
		signin: ctk.CTkButton,
		notifications: ctk.CTkButton,
		messages_btn: ctk.CTkButton,
	) -> None:
		_nav_controls.update(
			{
				"home": home,
				"videos": videos,
				"search": search,
				"profile": profile,
				"signin": signin,
				"notifications": notifications,
				"messages": messages_btn,
			}
		)


def register_show_frame_callback(callback: Callable[[str], None]) -> None:
		global _show_frame_cb
		_show_frame_cb = callback


def _set_palette(palette: Palette) -> None:
		global _palette
		_palette = dict(palette)


def _style_primary_button(button: Optional[ctk.CTkButton]) -> None:
		if button:
			button.configure(
				fg_color=_palette.get("accent", "#4c8dff"),
				hover_color=_palette.get("accent_hover", "#3b6dd6"),
				text_color="white",
			)


def update_theme_palette(palette: Palette) -> None:
	_set_palette(palette)
	set_nav_palette(palette)
	_reaction_icon_cache.clear()
	surface = _palette.get("surface", "#111b2e")
	card = _palette.get("card", "#18263f")
	text_color = _palette.get("text", "#e2e8f0")
	muted = _palette.get("muted", "#94a3b8")

	# Home view components
	status_lbl: ctk.CTkLabel = _home_widgets.get("status")
	server_status_lbl: ctk.CTkLabel = _home_widgets.get("server_status_label")
	server_check_btn: ctk.CTkButton = _home_widgets.get("server_check_button")
	server_config_btn: ctk.CTkButton = _home_widgets.get("server_config_button")
	stories_frame: ctk.CTkFrame = _home_widgets.get("stories_frame")
	stories_bar: ctk.CTkFrame = _home_widgets.get("stories_bar")
	add_story_btn: ctk.CTkButton = _home_widgets.get("add_story_button")
	story_entries: list[dict[str, Any]] = _stories_widgets.get("entries", [])
	stories_placeholder: ctk.CTkLabel = _stories_widgets.get("placeholder")
	composer: ctk.CTkFrame = _home_widgets.get("composer")
	post_text: ctk.CTkTextbox = _home_widgets.get("post_text")
	post_btn: ctk.CTkButton = _home_widgets.get("post_button")
	attach_btn: ctk.CTkButton = _home_widgets.get("attach_button")
	attachments_frame: ctk.CTkFrame = _home_widgets.get("attachments_frame")
	feed: ctk.CTkScrollableFrame = _home_widgets.get("feed")

	if status_lbl:
		status_lbl.configure(
			text=f"Signed in as @{_ui_state.current_user}" if _ui_state.current_user else "Signed out",
			text_color=text_color if _ui_state.current_user else muted,
		)
	if server_status_lbl:
		server_status_lbl.configure(text_color=muted)
	if server_check_btn:
		server_check_btn.configure(
			fg_color="transparent",
			border_width=1,
			border_color=muted,
			text_color=muted,
			hover_color=surface,
		)
	if server_config_btn:
		server_config_btn.configure(
			fg_color="transparent",
			border_width=1,
			border_color=_palette.get("accent", "#4c8dff"),
			text_color=_palette.get("accent", "#4c8dff"),
			hover_color=surface,
		)
	if stories_frame:
		stories_frame.configure(fg_color=surface)
	if stories_bar:
		stories_bar.configure(fg_color="transparent")
	for entry in story_entries:
		bar = entry.get("bar")
		placeholder = entry.get("placeholder")
		if isinstance(bar, ctk.CTkFrame):
			bar.configure(fg_color="transparent")
		if isinstance(placeholder, ctk.CTkLabel):
			placeholder.configure(text_color=muted)
	if stories_placeholder and isinstance(stories_placeholder, ctk.CTkLabel):
		stories_placeholder.configure(text_color=muted)
	_style_primary_button(add_story_btn)
	if composer:
		composer.configure(fg_color=surface)
	if post_text:
		post_text.configure(fg_color=card, text_color=text_color)
	_style_primary_button(post_btn)
	if attach_btn:
		attach_btn.configure(
			fg_color="transparent",
			border_width=1,
			border_color=_palette.get("accent", "#4c8dff"),
			text_color=_palette.get("accent", "#4c8dff"),
			hover_color=surface,
		)
	if attachments_frame:
		attachments_frame.configure(fg_color="transparent")
	if feed:
		feed.configure(fg_color="transparent")

	_refresh_stories_bar()
	_refresh_post_attachments()
	_update_server_status()

	# Profile view components
	profile_name: ctk.CTkLabel = _profile_widgets.get("name")
	profile_info: ctk.CTkLabel = _profile_widgets.get("info")
	profile_change_btn: ctk.CTkButton = _profile_widgets.get("change_btn")
	profile_avatar_label: tk.Label = _profile_widgets.get("avatar_label")
	profile_posts: ctk.CTkScrollableFrame = _profile_widgets.get("posts")
	profile_stories_card: ctk.CTkFrame = _profile_widgets.get("stories_card")
	profile_stories_bar: ctk.CTkFrame = _profile_widgets.get("stories_bar")
	profile_stories_placeholder: ctk.CTkLabel = _profile_widgets.get("stories_placeholder")
	if profile_name:
		profile_name.configure(text_color=text_color)
	if profile_info:
		profile_info.configure(text_color=muted)
	_style_primary_button(profile_change_btn)
	if profile_avatar_label:
		profile_avatar_label.configure(bg=surface)
	if profile_posts:
		profile_posts.configure(fg_color="transparent")
	if profile_stories_card:
		profile_stories_card.configure(fg_color=surface)
	if profile_stories_bar:
		profile_stories_bar.configure(fg_color="transparent")
	if profile_stories_placeholder:
		profile_stories_placeholder.configure(text_color=muted)

	inspect_stories_card: ctk.CTkFrame = _inspect_widgets.get("stories_card")
	inspect_stories_bar: ctk.CTkFrame = _inspect_widgets.get("stories_bar")
	inspect_stories_placeholder: ctk.CTkLabel = _inspect_widgets.get("stories_placeholder")
	if inspect_stories_card:
		inspect_stories_card.configure(fg_color=surface)
	if inspect_stories_bar:
		inspect_stories_bar.configure(fg_color="transparent")
	if inspect_stories_placeholder:
		inspect_stories_placeholder.configure(text_color=muted)

	# Inspect profile components
	inspect_header: ctk.CTkLabel = _inspect_widgets.get("header")
	inspect_info: ctk.CTkLabel = _inspect_widgets.get("info")
	inspect_message_btn: ctk.CTkButton = _inspect_widgets.get("message_btn")
	inspect_avatar_label: tk.Label = _inspect_widgets.get("avatar_label")
	inspect_posts: ctk.CTkScrollableFrame = _inspect_widgets.get("posts")
	if inspect_header:
		inspect_header.configure(text_color=text_color)
	if inspect_info:
		inspect_info.configure(text_color=muted)
	_style_primary_button(inspect_message_btn)
	if inspect_avatar_label:
		inspect_avatar_label.configure(bg=surface)
	if inspect_posts:
		inspect_posts.configure(fg_color="transparent")

	# Notifications list
	notes_list: ctk.CTkScrollableFrame = _notifications_widgets.get("list")
	if notes_list:
		notes_list.configure(fg_color="transparent")

	# Direct message components
	dm_header: ctk.CTkLabel = _dm_widgets.get("header")
	dm_thread: ctk.CTkScrollableFrame = _dm_widgets.get("thread")
	dm_sidebar: ctk.CTkScrollableFrame = _dm_widgets.get("sidebar")
	dm_entry: ctk.CTkEntry = _dm_widgets.get("entry")
	dm_send: ctk.CTkButton = _dm_widgets.get("send")
	dm_composer: ctk.CTkFrame = _dm_widgets.get("composer")
	dm_attach: ctk.CTkButton = _dm_widgets.get("attach_button")
	dm_attachments_frame: ctk.CTkFrame = _dm_widgets.get("attachments_frame")
	if dm_header:
		dm_header.configure(text_color=text_color)
	if dm_thread:
		dm_thread.configure(fg_color=surface)
	if dm_sidebar:
		dm_sidebar.configure(fg_color="transparent")
	if dm_entry:
		dm_entry.configure(fg_color=surface, text_color=text_color)
	_style_primary_button(dm_send)
	if dm_composer:
		dm_composer.configure(fg_color="transparent")
	if dm_attach:
		dm_attach.configure(
			fg_color="transparent",
			border_width=1,
			border_color=_palette.get("accent", "#4c8dff"),
			text_color=_palette.get("accent", "#4c8dff"),
			hover_color=surface,
		)
	if dm_attachments_frame:
		dm_attachments_frame.configure(fg_color="transparent")
	_refresh_dm_attachments()

	# Videos view components
	videos_header: ctk.CTkLabel = _videos_widgets.get("header_label")
	videos_instruction: ctk.CTkLabel = _videos_widgets.get("instruction_label")
	videos_card: ctk.CTkFrame = _videos_widgets.get("upload_card")
	videos_select: ctk.CTkButton = _videos_widgets.get("select_button")
	videos_upload: ctk.CTkButton = _videos_widgets.get("upload_button")
	videos_caption: ctk.CTkEntry = _videos_widgets.get("caption_entry")
	videos_status: ctk.CTkLabel = _videos_widgets.get("status_label")
	videos_path: ctk.CTkLabel = _videos_widgets.get("upload_path_label")
	videos_feed: ctk.CTkScrollableFrame = _videos_widgets.get("feed")
	if videos_header:
		videos_header.configure(text_color=text_color)
	if videos_instruction:
		videos_instruction.configure(text_color=muted)
	if videos_card:
		videos_card.configure(fg_color=surface)
	_style_primary_button(videos_select)
	_style_primary_button(videos_upload)
	if videos_caption:
		videos_caption.configure(fg_color=card, text_color=text_color)
	if videos_path:
		videos_path.configure(text_color=muted)
	if videos_feed:
		videos_feed.configure(fg_color="transparent")
	if videos_status:
		mode = _videos_widgets.get("status_mode")
		if mode == "error":
			videos_status.configure(text_color=_palette.get("danger", "#ef4444"))
		elif mode == "info":
			videos_status.configure(text_color=_palette.get("accent", "#2563eb"))
		else:
			videos_status.configure(text_color=muted)
	for vid in list(_video_cards.keys()):
		_update_video_reaction_ui(vid)

	# Auth modal components
	auth_window: ctk.CTkToplevel = _auth_widgets.get("window")
	auth_title: ctk.CTkLabel = _auth_widgets.get("title")
	auth_username: ctk.CTkEntry = _auth_widgets.get("username")
	auth_password: ctk.CTkEntry = _auth_widgets.get("password")
	auth_submit: ctk.CTkButton = _auth_widgets.get("submit_button")
	auth_switch: ctk.CTkButton = _auth_widgets.get("switch_button")
	if auth_window:
		auth_window.configure(fg_color=surface)
	if auth_title:
		auth_title.configure(text_color=text_color)
	if auth_username:
		auth_username.configure(fg_color=surface, text_color=text_color)
	if auth_password:
		auth_password.configure(fg_color=surface, text_color=text_color)
	_style_primary_button(auth_submit)
	_style_primary_button(auth_switch)

	_mark_dirty("home", "profile", "notifications", "inspect_profile", "dm", "videos", "search")
	_update_videos_controls()
	if _frames:
		refresh_views(_frames)
	else:
		_render_active_view()


def _mark_dirty(*views: str) -> None:
	for view in views:
		if view:
			_ui_state.dirty_views.add(view)

def _mark_smart_dirty(*views: str) -> None:
	"""Only mark views as dirty if they're actually visible or active"""
	for view in views:
		if view and (view == _ui_state.active_view or view in ("notifications", "dm")):
			_ui_state.dirty_views.add(view)


def _mark_dm_sidebar_dirty() -> None:
	global _dm_sidebar_dirty
	_dm_sidebar_dirty = True


def _get_after_anchor() -> Optional[Any]:
	if _frames:
		for widget in _frames.values():
			if widget:
				return widget
	frame = _dm_widgets.get("frame")
	if frame:
		return frame
	return None


# Real-time push notifications ---------------------------------------------
# Instead of polling every 30 seconds, we now push changes immediately when they occur
# and use lightweight polling only as a backup for missed updates
_BACKUP_POLL_SECONDS = int(os.environ.get("BACKUP_POLL_SECONDS", "300"))  # 5 minutes backup check
_REALTIME_POLL_INTERVAL_MS = int(os.environ.get("REALTIME_POLL_MS", "800"))
_IMMEDIATE_PUSH_ENABLED = True  # Enable real-time push system
_REALTIME_LISTENER_STARTED = False


def _apply_remote_refresh_changes(changes: dict[str, bool]) -> None:
	if not changes:
		return

	dirty_views: set[str] = set()

	if changes.get("posts") or changes.get("users"):
		dirty_views.update({"home", "profile", "inspect_profile", "search"})
	if changes.get("stories"):
		dirty_views.add("home")
	if changes.get("videos"):
		dirty_views.add("videos")
	if changes.get("messages"):
		dirty_views.add("dm")
		_mark_dm_sidebar_dirty()
	if changes.get("users"):
		dirty_views.update({"notifications", "dm"})
		_profile_avatar_cache.clear()
		_mark_dm_sidebar_dirty()
	if changes.get("group_chats"):
		dirty_views.add("dm")
		_mark_dm_sidebar_dirty()
	if changes.get("notifications"):
		dirty_views.add("notifications")

	if dirty_views:
		_mark_dirty(*dirty_views)
		for view in dirty_views:
			_request_render(view)

	if changes.get("stories"):
		_refresh_stories_bar()


def _poll_messages_once() -> dict[str, bool]:
	"""Check for remote updates and return which resources changed."""
	changes: dict[str, bool] = {}
	try:
		# Import here to avoid circular imports
		from data_layer import smart_sync_updates
		
		# Check for updates and sync only what's changed
		changes = smart_sync_updates() or {}
		
		# Update UI for any changed resources
		if changes.get("messages"):
			_mark_dirty("dm")
			_request_render("dm")
		if changes.get("group_chats"):
			_mark_dm_sidebar_dirty()
			_mark_dirty("dm")
			_request_render("dm")
		if changes.get("stories"):
			_mark_dirty("home")
			_request_render("home")
		if changes.get("posts"):
			_mark_dirty("home")
			_request_render("home")
		if changes.get("videos"):
			_mark_dirty("videos")
			_request_render("videos")
		if changes.get("users"):
			_mark_dirty("profile", "home")
			_request_render("profile")
		if changes.get("notifications"):
			_mark_dirty("notifications")
			_request_render("notifications")
	except Exception:
		changes = {}

	return changes


def _notify_remote_sync_issue(resource: str, action: str) -> None:
	if not os.environ.get("SOCIAL_SERVER_URL"):
		return
	if was_last_remote_sync_successful(resource):
		_remote_sync_alerts.pop(resource, None)
		return
	error_text = last_remote_sync_error(resource) or "unknown error"
	if _remote_sync_alerts.get(resource) == error_text:
		return
	_remote_sync_alerts[resource] = error_text
	messagebox.showerror(
		"Server sync failed",
		(
			f"Could not {action} on the server.\n"
			f"Latest error: {error_text}.\n"
			"Changes were saved locally, but other devices may not see them until the issue is resolved."
		),
	)


def _start_backup_sync_checker() -> None:
	"""Start lightweight backup sync checker (5 minutes) as failsafe for missed real-time updates"""
	anchor = _get_after_anchor()
	if not anchor:
		return

	def _backup_check() -> None:
		# Only check for updates if real-time push is enabled
		if _IMMEDIATE_PUSH_ENABLED:
			try:
				changes = _poll_messages_once()
				if changes:
					_apply_remote_refresh_changes(changes)
			except Exception:
				pass
		
		# Schedule next backup check in 5 minutes
		try:
			anchor.after(_BACKUP_POLL_SECONDS * 1000, _backup_check)
		except Exception:
			return

	# Start backup checker after 1 minute (let real-time system work first)
	try:
		anchor.after(60000, _backup_check)  
	except Exception:
		pass


def _start_realtime_listener() -> None:
	"""Continuously poll the server for updates when push notifications are enabled."""
	global _REALTIME_LISTENER_STARTED
	if _REALTIME_LISTENER_STARTED or not _IMMEDIATE_PUSH_ENABLED:
		return

	anchor = _get_after_anchor()
	if not anchor:
		return

	_REALTIME_LISTENER_STARTED = True

	def _tick() -> None:
		global _REALTIME_LISTENER_STARTED
		if not _IMMEDIATE_PUSH_ENABLED:
			return

		changes = {}
		try:
			changes = _poll_messages_once()
		except Exception:
			changes = {}

		if changes:
			_apply_remote_refresh_changes(changes)

		next_anchor = _get_after_anchor()
		if not next_anchor or not getattr(next_anchor, "winfo_exists", lambda: False)():
			# Could not reschedule; allow future restarts
			_REALTIME_LISTENER_STARTED = False
			return

		try:
			next_anchor.after(_REALTIME_POLL_INTERVAL_MS, _tick)
		except Exception:
			_REALTIME_LISTENER_STARTED = False
			return

	try:
		anchor.after(_REALTIME_POLL_INTERVAL_MS, _tick)
	except Exception:
		_REALTIME_LISTENER_STARTED = False

def trigger_immediate_sync(resource_type: str) -> None:
	"""Trigger immediate synchronization when local changes occur"""
	if not _IMMEDIATE_PUSH_ENABLED:
		return
		
	try:
		from data_layer import push_immediate_update
		
		# Push the change immediately 
		push_immediate_update(resource_type, delay_ms=50)
		
		# Also do a light refresh to get any concurrent changes from other clients
		def _light_refresh():
			try:
				changes = _poll_messages_once()
				if changes:
					# Apply any concurrent updates we received
					_apply_remote_refresh_changes(changes)
			except Exception:
				pass
		
		# Schedule light refresh after a short delay to catch concurrent updates
		anchor = _get_after_anchor()
		if anchor:
			anchor.after(200, _light_refresh)
			
	except Exception:
		# Fallback to old polling if push fails
		pass


def _server_summary_text(include_url: bool = True) -> Optional[str]:
	server_url = (os.environ.get("SOCIAL_SERVER_URL") or "").strip()
	if not server_url:
		return None
	token = os.environ.get("SOCIAL_SERVER_TOKEN")
	token_note = "token set" if token else "token missing"
	if include_url:
		return f"Server: {server_url} ({token_note})"
	return f"Server configured ({token_note})"


def _apply_server_status_result(text: str, color: str) -> None:
	anchor = _get_after_anchor()

	def _update() -> None:
		label = _home_widgets.get("server_status_label")
		if label and getattr(label, "winfo_exists", lambda: False)():
			try:
				label.configure(text=text, text_color=color)
			except Exception:
				return

	if anchor:
		try:
			# Check if the anchor widget still exists and is in a valid state
			if getattr(anchor, "winfo_exists", lambda: False)():
				anchor.after(0, _update)
			# If anchor doesn't exist, skip the update silently
		except Exception:
			# If any error occurs, skip the update to avoid crashes
			pass
	else:
		try:
			_update()
		except Exception:
			# If direct update fails, skip silently
			pass


def _update_server_status(*, check: bool = False) -> None:
	label = _home_widgets.get("server_status_label")
	if not label:
		return
	muted = _palette.get("muted", "#94a3b8")
	server_url = (os.environ.get("SOCIAL_SERVER_URL") or "").strip()
	if not server_url:
		try:
			label.configure(text="Server: local mode (no remote URL)", text_color=muted)
		except Exception:
			pass
		return
	token = os.environ.get("SOCIAL_SERVER_TOKEN")
	token_note = "token set" if token else "token missing"
	base_text = f"Server: {server_url} ({token_note})"
	try:
		label.configure(text=f"{base_text}{' — checking...' if check else ''}", text_color=muted)
	except Exception:
		pass
	if not check:
		return

	def _worker(base: str, url: str, token_value: Optional[str]) -> None:
		try:
			import requests  # type: ignore
		except Exception:
			_apply_server_status_result(base + " — install 'requests' to check", _palette.get("danger", "#ef4444"))
			return
		headers: dict[str, str] = {}
		if token_value:
			headers["Authorization"] = f"Bearer {token_value}"
			headers["X-SOCIAL-TOKEN"] = token_value
		try:
			resp = requests.get(f"{url.rstrip('/')}/api/ping", headers=headers, timeout=2)
			if resp.status_code == 200:
				payload = resp.json()
				if isinstance(payload, dict) and payload.get("ok"):
					text = base + " — online"
					color = _palette.get("accent", "#2563eb")
				else:
					text = base + " — unexpected response"
					color = _palette.get("danger", "#ef4444")
			elif resp.status_code == 401:
				text = base + " — unauthorized (token rejected)"
				color = _palette.get("danger", "#ef4444")
			else:
				text = base + f" — error {resp.status_code}"
				color = _palette.get("danger", "#ef4444")
		except Exception:
			text = base + " — offline"
			color = _palette.get("danger", "#ef4444")
		_apply_server_status_result(text, color)

	threading.Thread(target=_worker, args=(base_text, server_url, token), daemon=True).start()


def _open_server_settings() -> None:
	current_url = os.environ.get("SOCIAL_SERVER_URL", "")
	prompt = simpledialog.askstring(
		"Server URL",
		"Enter the server URL (leave blank to disable remote sync):",
		initialvalue=current_url,
	)
	if prompt is None:
		return
	new_url = (prompt or "").strip()
	if new_url and not new_url.lower().startswith(("http://", "https://")):
		messagebox.showerror("Invalid URL", "Please enter a URL starting with http:// or https://.")
		return
	if not new_url:
		set_server_config(None, None)
		_update_server_status()
		_update_videos_controls()
		return

	current_token = os.environ.get("SOCIAL_SERVER_TOKEN", "")
	token_prompt = simpledialog.askstring(
		"Server token",
		"Enter the access token (leave blank to clear):",
		initialvalue=current_token,
		show="*",
	)
	if token_prompt is None:
		set_server_config(new_url, current_token or None)
	else:
		token_value = token_prompt.strip()
		set_server_config(new_url, token_value or None)

	_update_server_status(check=True)
	_update_videos_controls()


def _render_view(view: str) -> None:
	import time
	
	# Skip rendering if view is not dirty or doesn't need re-rendering
	if view not in _ui_state.dirty_views or not _check_render_needed(view):
		return
	
	pre_signature = _compute_view_signature(view)
	if pre_signature is not None:
		previous = _view_signatures.get(view)
		if previous == pre_signature and view != "dm":
			_ui_state.dirty_views.discard(view)
			return

	# Update cache timestamp
	_view_cache.setdefault(view, {})["last_render"] = time.time()
		
	if view == "home":
		_view_cache[view]["post_count"] = len(posts)
		_render_feed_section()
	elif view == "profile":
		_view_cache[view]["user"] = _ui_state.current_user
		_render_profile_section()
		_render_profile_avatar()
	elif view == "achievements":
		_view_cache[view]["user"] = _ui_state.current_user
		_render_achievements_view()
	elif view == "notifications":
		_render_notifications()
	elif view == "inspect_profile":
		_render_inspected_profile()
	elif view == "videos":
		_render_videos()
	elif view == "search":
		_render_search()
	elif view == "dm":
		_view_cache[view]["conversation"] = _ui_state.active_dm_conversation
		_render_dm_sidebar()
		_render_dm()

	if pre_signature is not None and view != "dm":
		_view_signatures[view] = pre_signature
	_ui_state.dirty_views.discard(view)


def _request_render(view: str) -> None:
	global _render_after_handles
	_mark_dirty(view)
	if _ui_state.active_view != view:
		return
	anchor = _get_after_anchor()
	if anchor is None:
		_render_view(view)
		return
	prev = _render_after_handles.get(view)
	if prev:
		try:
			anchor.after_cancel(prev)
		except Exception:
			pass

	def _run_render() -> None:
		_render_after_handles.pop(view, None)
		if _ui_state.active_view == view and view in _ui_state.dirty_views:
			_render_view(view)

	# Reduce render delay for faster tab switching (was 16ms, now 8ms)
	_handle = anchor.after(8, _run_render)
	_render_after_handles[view] = _handle

def _check_render_needed(view: str) -> bool:
	"""Check if a view actually needs re-rendering based on cache"""
	import time
	cache = _view_cache.get(view, {})
	current_time = time.time()
	
	# Skip render if rendered recently (within 100ms) and data hasn't changed
	if current_time - cache.get("last_render", 0) < 0.1:
		# Check if data actually changed for this view
		if view == "home" and cache.get("post_count") == len(posts):
			return False
		elif view == "profile" and cache.get("user") == _ui_state.current_user:
			return False
		elif view == "dm" and cache.get("conversation") == _ui_state.active_dm_conversation:
			return False
		elif view == "achievements" and cache.get("user") == _ui_state.current_user:
			return False
	
	return True


def _render_active_view() -> None:
	active = _ui_state.active_view
	if active in _ui_state.dirty_views:
		_render_view(active)


def handle_frame_shown(name: str) -> None:
	prev_view = _ui_state.active_view
	_ui_state.active_view = name
	
	# Immediate render for fast tab switching
	if name in _ui_state.dirty_views:
		_render_view(name)
	else:
		# Use light render for already-clean views
		_request_render(name)
	
	# Update nav controls without blocking
	_update_nav_controls()
	
	# Defer marking other related views as dirty to avoid cascade re-renders
	def _defer_related_updates():
		if prev_view != name:
			# Only mark closely related views as dirty, not everything
			if name == "profile" and prev_view != "inspect_profile":
				_mark_smart_dirty("inspect_profile")
			elif name in ("dm", "notifications") and prev_view not in ("dm", "notifications"):
				_mark_smart_dirty("notifications", "dm")
	
	anchor = _get_after_anchor()
	if anchor:
		anchor.after(50, _defer_related_updates)


def build_videos_frame(container: ctk.CTkFrame, palette: Palette) -> ctk.CTkFrame:
	_set_palette(palette)
	frame = ctk.CTkFrame(container, corner_radius=12, fg_color="transparent")
	frame.grid_rowconfigure(1, weight=1)
	frame.grid_columnconfigure(0, weight=1)

	header = ctk.CTkLabel(
		frame,
		text="Videos",
		font=ctk.CTkFont(size=20, weight="bold"),
		text_color=palette.get("text", "#e2e8f0"),
	)
	header.grid(row=0, column=0, sticky="w", padx=16, pady=(18, 10))

	upload_card = ctk.CTkFrame(frame, corner_radius=16, fg_color=palette.get("surface", "#111b2e"))
	upload_card.grid(row=0, column=0, sticky="we", padx=16, pady=(0, 10))
	upload_card.grid_columnconfigure(1, weight=1)

	instruction = ctk.CTkLabel(
		upload_card,
		text="Share a short clip with your followers",
		text_color=palette.get("muted", "#94a3b8"),
	)
	instruction.grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(16, 8))

	select_btn = ctk.CTkButton(
		upload_card,
		text="Choose video",
		command=_handle_select_video_file,
	)
	select_btn.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 8))

	path_lbl = ctk.CTkLabel(
		upload_card,
		text="No video selected",
		anchor="w",
		text_color=palette.get("muted", "#94a3b8"),
	)
	path_lbl.grid(row=1, column=1, sticky="we", padx=(0, 16), pady=(0, 8))

	caption_entry = ctk.CTkEntry(
		upload_card,
		placeholder_text="Write a caption (optional)",
	)
	caption_entry.grid(row=2, column=0, columnspan=2, sticky="we", padx=16, pady=(0, 8))

	upload_btn = ctk.CTkButton(
		upload_card,
		text="Upload",
		width=110,
		command=_handle_upload_video,
	)
	upload_btn.grid(row=3, column=0, sticky="w", padx=16, pady=(0, 16))

	status_lbl = ctk.CTkLabel(
		upload_card,
		text="",
		anchor="e",
		text_color=palette.get("muted", "#94a3b8"),
	)
	status_lbl.grid(row=3, column=1, sticky="e", padx=16, pady=(0, 16))

	feed = ctk.CTkScrollableFrame(frame, corner_radius=18, fg_color="transparent")
	feed.grid(row=1, column=0, sticky="nswe", padx=16, pady=(0, 16))
	feed.grid_columnconfigure(0, weight=1)

	_videos_widgets.update(
		{
			"frame": frame,
			"header_label": header,
			"upload_card": upload_card,
			"instruction_label": instruction,
			"select_button": select_btn,
			"upload_button": upload_btn,
			"caption_entry": caption_entry,
			"status_label": status_lbl,
			"upload_path_label": path_lbl,
			"feed": feed,
		}
	)
	_videos_widgets["upload_path"] = ""
	_videos_widgets["status_mode"] = "muted"
	_set_video_upload_path("")
	_update_videos_controls()
	_render_videos()
	return frame


def build_search_frame(container: ctk.CTkFrame, palette: Palette) -> ctk.CTkFrame:
	_set_palette(palette)
	frame = ctk.CTkFrame(container, corner_radius=12, fg_color="transparent")
	frame.grid_rowconfigure(3, weight=1)
	frame.grid_columnconfigure(0, weight=1)

	header = ctk.CTkLabel(
		frame,
		text="Search",
		font=ctk.CTkFont(size=20, weight="bold"),
		text_color=palette.get("text", "#e2e8f0"),
	)
	header.grid(row=0, column=0, sticky="w", padx=16, pady=(18, 8))

	search_row = ctk.CTkFrame(frame, fg_color="transparent")
	search_row.grid(row=1, column=0, sticky="we", padx=16, pady=(0, 8))
	search_row.grid_columnconfigure(0, weight=1)

	entry = ctk.CTkEntry(
		search_row,
		placeholder_text="Search people or #hashtags...",
		fg_color=palette.get("surface", "#111b2e"),
		text_color=palette.get("text", "#e2e8f0"),
	)
	entry.grid(row=0, column=0, sticky="we", padx=(0, 8))
	entry.bind("<Return>", _handle_search_submit)
	entry.bind("<KeyRelease>", _handle_search_change)

	button = ctk.CTkButton(
		search_row,
		text="Search",
		width=100,
		fg_color=palette.get("accent", "#4c8dff"),
		hover_color=palette.get("accent_hover", "#3b6dd6"),
		command=_handle_search_submit,
	)
	button.grid(row=0, column=1)

	status_lbl = ctk.CTkLabel(
		frame,
		text="Discover trending creators, posts, and hashtags.",
		text_color=palette.get("muted", "#94a3b8"),
		font=ctk.CTkFont(size=13),
	)
	status_lbl.grid(row=2, column=0, sticky="w", padx=16, pady=(0, 4))

	results = ctk.CTkScrollableFrame(frame, corner_radius=16, fg_color="transparent")
	results.grid(row=3, column=0, sticky="nswe", padx=16, pady=(0, 16))
	results.grid_columnconfigure(0, weight=1)

	_search_widgets.update(
		{
			"frame": frame,
			"entry": entry,
			"button": button,
			"status": status_lbl,
			"results": results,
			"hashtag_stats": {},
			"hashtag_window": None,
		}
	)

	return frame


def build_home_frame(container: ctk.CTkFrame, palette: Palette) -> ctk.CTkFrame:
	_set_palette(palette)
	frame = ctk.CTkFrame(container, corner_radius=12, fg_color="transparent")
	frame.grid_rowconfigure(4, weight=1)
	frame.grid_columnconfigure(0, weight=1)

	status_lbl = ctk.CTkLabel(
		frame,
		text="Signed out",
		anchor="w",
		font=ctk.CTkFont(size=14),
		text_color=palette.get("muted", "#94a3b8"),
	)
	status_lbl.grid(row=0, column=0, sticky="we", padx=16, pady=(16, 6))

	server_row = ctk.CTkFrame(frame, fg_color="transparent")
	server_row.grid(row=1, column=0, sticky="we", padx=16, pady=(0, 12))
	server_row.grid_columnconfigure(0, weight=1)

	server_status_lbl = ctk.CTkLabel(
		server_row,
		text="Server: local mode (no remote URL)",
		anchor="w",
		justify="left",
		wraplength=420,
		font=ctk.CTkFont(size=12),
		text_color=palette.get("muted", "#94a3b8"),
	)
	server_status_lbl.grid(row=0, column=0, sticky="w")

	server_check_btn = ctk.CTkButton(
		server_row,
		text="Check",
		width=80,
		fg_color="transparent",
		border_width=1,
		border_color=palette.get("muted", "#94a3b8"),
		text_color=palette.get("muted", "#94a3b8"),
		hover_color=palette.get("surface", "#111b2e"),
		command=lambda: _update_server_status(check=True),
	)
	server_check_btn.grid(row=0, column=1, padx=(8, 0))

	server_config_btn = ctk.CTkButton(
		server_row,
		text="Configure",
		width=110,
		fg_color="transparent",
		border_width=1,
		border_color=palette.get("accent", "#4c8dff"),
		text_color=palette.get("accent", "#4c8dff"),
		hover_color=palette.get("surface", "#111b2e"),
		command=_open_server_settings,
	)
	server_config_btn.grid(row=0, column=2, padx=(8, 0))

	stories_card = ctk.CTkFrame(frame, corner_radius=16, fg_color=palette.get("surface", "#111b2e"))
	stories_card.grid(row=2, column=0, sticky="we", padx=16, pady=(0, 16))
	stories_card.grid_columnconfigure(1, weight=1)

	add_story_btn = ctk.CTkButton(
		stories_card,
		text="Add story",
		width=120,
		command=_handle_add_story,
	)
	add_story_btn.grid(row=0, column=0, padx=12, pady=12, sticky="ns")

	stories_bar = ctk.CTkFrame(stories_card, fg_color="transparent")
	stories_bar.grid(row=0, column=1, sticky="we", padx=(0, 12), pady=12)

	placeholder_lbl = ctk.CTkLabel(
		stories_bar,
		text="No stories yet",
		text_color=palette.get("muted", "#94a3b8"),
	)
	placeholder_lbl.grid(row=0, column=0, padx=12, pady=12, sticky="w")

	composer = ctk.CTkFrame(frame, corner_radius=16, fg_color=palette.get("surface", "#111b2e"))
	composer.grid(row=3, column=0, sticky="we", padx=16, pady=(0, 16))
	composer.grid_columnconfigure(0, weight=1)
	composer.grid_rowconfigure(0, weight=1)

	post_text = ctk.CTkTextbox(
		composer,
		height=110,
		fg_color=palette.get("card", "#18263f"),
		text_color=palette.get("text", "#e2e8f0"),
		border_width=0,
	)
	post_text.grid(row=0, column=0, columnspan=1, sticky="nswe", padx=12, pady=12)

	post_btn = ctk.CTkButton(
		composer,
		text="Post",
		width=120,
		fg_color=palette.get("accent", "#4c8dff"),
		hover_color=palette.get("accent_hover", "#3b6dd6"),
		command=_handle_submit_post,
	)
	post_btn.grid(row=0, column=1, padx=(0, 12), pady=12, sticky="ns")

	attach_btn = ctk.CTkButton(
		composer,
		text="Attach file",
		width=120,
		fg_color="transparent",
		border_width=1,
		border_color=palette.get("accent", "#4c8dff"),
		text_color=palette.get("accent", "#4c8dff"),
		hover_color=palette.get("surface", "#111b2e"),
		command=_handle_add_post_attachment,
	)
	attach_btn.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="w")

	attachments_frame = ctk.CTkFrame(composer, fg_color="transparent")
	attachments_frame.grid(row=2, column=0, columnspan=2, sticky="we", padx=12, pady=(0, 12))
	attachments_frame.grid_remove()

	feed_frame = ctk.CTkScrollableFrame(frame, corner_radius=16, fg_color="transparent")
	feed_frame.grid(row=4, column=0, sticky="nswe", padx=16, pady=(0, 16))
	feed_frame.grid_columnconfigure(0, weight=1)

	_bind_return_submit(post_text, _handle_submit_post, allow_shift_newline=True)

	def _submit_post_ctrl(event) -> str:
		_handle_submit_post()
		return "break"

	post_text.bind("<Control-Return>", _submit_post_ctrl)
	post_text.bind("<Control-KP_Enter>", _submit_post_ctrl)

	_home_widgets.update(
		{
			"frame": frame,
			"status": status_lbl,
			"server_status_label": server_status_lbl,
			"server_check_button": server_check_btn,
			"server_config_button": server_config_btn,
			"stories_frame": stories_card,
			"stories_bar": stories_bar,
			"add_story_button": add_story_btn,
			"composer": composer,
			"post_text": post_text,
			"post_button": post_btn,
			"attach_button": attach_btn,
			"attachments_frame": attachments_frame,
			"feed": feed_frame,
		}
	)

	_update_server_status()

	_stories_widgets.update(
		{
			"container": stories_card,
			"add_button": add_story_btn,
		}
	)
	_register_story_bar(stories_bar, placeholder_lbl)

	_refresh_stories_bar()
	_refresh_post_attachments()

	return frame


def build_achievements_frame(container: ctk.CTkFrame, palette: Palette) -> ctk.CTkFrame:
		"""Standalone achievements view hosted by the shell."""
		_set_palette(palette)
		frame = ctk.CTkFrame(container, corner_radius=12, fg_color="transparent")
		frame.grid_rowconfigure(1, weight=1)
		frame.grid_columnconfigure(0, weight=1)

		header = ctk.CTkLabel(
			frame,
			text="Achievements",
			font=ctk.CTkFont(size=20, weight="bold"),
			text_color=palette.get("text", "#e2e8f0"),
		)
		header.grid(row=0, column=0, sticky="w", padx=16, pady=(16, 6))

		summary_label = ctk.CTkLabel(
			frame,
			text="",
			anchor="w",
			justify="left",
			wraplength=520,
			text_color=palette.get("muted", "#94a3b8"),
		)
		summary_label.grid(row=1, column=0, sticky="we", padx=16, pady=(0, 12))

		list_frame = ctk.CTkScrollableFrame(
			frame,
			corner_radius=16,
			fg_color="transparent",
		)
		list_frame.grid(row=2, column=0, sticky="nswe", padx=16, pady=(0, 16))
		list_frame.grid_columnconfigure(0, weight=1)

		_achievements_widgets.update(
			{
				"frame": frame,
				"header": header,
				"summary": summary_label,
				"list": list_frame,
			}
		)

		_render_achievements_view()
		return frame


def build_profile_frame(container: ctk.CTkFrame, palette: Palette) -> ctk.CTkFrame:
	_set_palette(palette)
	frame = ctk.CTkFrame(container, corner_radius=12, fg_color="transparent")
	frame.grid_rowconfigure(3, weight=1)
	frame.grid_columnconfigure(0, weight=1)

	header = ctk.CTkLabel(
		frame,
		text="Profile",
		font=ctk.CTkFont(size=20, weight="bold"),
		text_color=palette.get("text", "#e2e8f0"),
	)
	header.grid(row=0, column=0, sticky="w", padx=16, pady=(16, 6))

	hero = ctk.CTkFrame(frame, fg_color="transparent")
	hero.grid(row=1, column=0, sticky="nwe", padx=16, pady=(0, 16))
	hero.grid_columnconfigure(0, weight=0)
	hero.grid_columnconfigure(1, weight=1)

	left_col = ctk.CTkFrame(hero, fg_color="transparent")
	left_col.grid(row=0, column=0, sticky="nw")
	left_col.grid_columnconfigure(0, weight=1)

	avatar_panel = ctk.CTkFrame(left_col, fg_color="transparent")
	avatar_panel.grid(row=0, column=0, sticky="nw")
	avatar_panel.grid_columnconfigure(0, weight=1)

	avatar_label = tk.Label(avatar_panel, bg=palette.get("surface", "#111b2e"), bd=0)
	avatar_label.grid(row=0, column=0, sticky="n", pady=(0, 12))

	name_lbl = ctk.CTkLabel(
		left_col,
		text="",
		font=ctk.CTkFont(size=18, weight="bold"),
		text_color=palette.get("text", "#e2e8f0"),
	)
	name_lbl.grid(row=1, column=0, sticky="w", pady=(0, 6))

	info_lbl = ctk.CTkLabel(
		left_col,
		text="",
		justify="left",
		anchor="w",
		wraplength=260,
		text_color=palette.get("muted", "#94a3b8"),
	)
	info_lbl.grid(row=2, column=0, sticky="we")

	change_btn = ctk.CTkButton(
		left_col,
		text="Change picture",
		width=140,
		command=_handle_change_profile_picture,
	)
	change_btn.grid(row=3, column=0, sticky="w", pady=(8, 12))

	details_card = ctk.CTkFrame(left_col, corner_radius=12, fg_color=palette.get("surface", "#111b2e"))
	details_card.grid(row=4, column=0, sticky="we")
	details_card.grid_columnconfigure(0, weight=1)

	bio_label = ctk.CTkLabel(
		details_card,
		text="Bio",
		text_color=palette.get("text", "#e2e8f0"),
		font=ctk.CTkFont(size=13, weight="bold"),
	)
	bio_label.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))

	bio_input = ctk.CTkTextbox(
		details_card,
		height=80,
		fg_color=palette.get("card", "#18263f"),
		text_color=palette.get("text", "#e2e8f0"),
		border_width=0,
	)
	bio_input.grid(row=1, column=0, sticky="we", padx=12)

	location_label = ctk.CTkLabel(
		details_card,
		text="Location",
		text_color=palette.get("text", "#e2e8f0"),
		font=ctk.CTkFont(size=13, weight="bold"),
	)
	location_label.grid(row=2, column=0, sticky="w", padx=12, pady=(10, 2))

	location_entry = ctk.CTkEntry(
		details_card,
		fg_color=palette.get("card", "#18263f"),
		text_color=palette.get("text", "#e2e8f0"),
	)
	location_entry.grid(row=3, column=0, sticky="we", padx=12)

	website_label = ctk.CTkLabel(
		details_card,
		text="Website",
		text_color=palette.get("text", "#e2e8f0"),
		font=ctk.CTkFont(size=13, weight="bold"),
	)
	website_label.grid(row=4, column=0, sticky="w", padx=12, pady=(10, 2))

	website_entry = ctk.CTkEntry(
		details_card,
		fg_color=palette.get("card", "#18263f"),
		text_color=palette.get("text", "#e2e8f0"),
	)
	website_entry.grid(row=5, column=0, sticky="we", padx=12)

	save_btn = ctk.CTkButton(
		details_card,
		text="Save profile",
		width=130,
		fg_color=palette.get("accent", "#4c8dff"),
		hover_color=palette.get("accent_hover", "#3b6dd6"),
		command=_handle_save_profile_details,
	)
	save_btn.grid(row=6, column=0, sticky="e", padx=12, pady=(12, 10))

	status_lbl = ctk.CTkLabel(
		details_card,
		text="",
		text_color=palette.get("muted", "#94a3b8"),
		font=ctk.CTkFont(size=11, slant="italic"),
	)
	status_lbl.grid(row=7, column=0, sticky="w", padx=12, pady=(0, 10))

	right_col = ctk.CTkFrame(hero, fg_color="transparent")
	right_col.grid(row=0, column=1, sticky="nwe", padx=(24, 0))
	right_col.grid_columnconfigure(0, weight=1)

	stats_card = ctk.CTkFrame(right_col, corner_radius=12, fg_color=palette.get("surface", "#111b2e"))
	stats_card.grid(row=0, column=0, sticky="we")
	for col in range(4):
		stats_card.grid_columnconfigure(col, weight=1)
	metrics = [
		("Followers", "followers"),
		("Following", "following"),
		("Posts", "posts"),
		("Likes received", "likes"),
	]
	stats_labels: dict[str, ctk.CTkLabel] = {}
	for col, (title, key) in enumerate(metrics):
		slot = ctk.CTkFrame(stats_card, fg_color="transparent")
		slot.grid(row=0, column=col, sticky="we", padx=10, pady=10)
		slot.grid_columnconfigure(0, weight=1)
		value_lbl = ctk.CTkLabel(
			slot,
			text="0",
			font=ctk.CTkFont(size=18, weight="bold"),
			text_color=palette.get("text", "#e2e8f0"),
		)
		value_lbl.grid(row=0, column=0, sticky="w")
		title_lbl = ctk.CTkLabel(
			slot,
			text=title,
			font=ctk.CTkFont(size=11),
			text_color=palette.get("muted", "#94a3b8"),
		)
		title_lbl.grid(row=1, column=0, sticky="w", pady=(2, 0))
		stats_labels[key] = value_lbl

	achievements_card = ctk.CTkFrame(right_col, corner_radius=12, fg_color=palette.get("surface", "#111b2e"))
	achievements_card.grid(row=1, column=0, sticky="we", pady=(12, 0))
	achievements_card.grid_columnconfigure(0, weight=1)

	achievements_header = ctk.CTkFrame(achievements_card, fg_color="transparent")
	achievements_header.grid(row=0, column=0, sticky="we", padx=12, pady=(10, 4))
	achievements_header.grid_columnconfigure(0, weight=1)

	ctk.CTkLabel(
		achievements_header,
		text="Achievements",
		text_color=palette.get("text", "#e2e8f0"),
		font=ctk.CTkFont(size=13, weight="bold"),
	).grid(row=0, column=0, sticky="w")

	achievements_btn = ctk.CTkButton(
		achievements_header,
		text="View progress",
		width=130,
		fg_color=palette.get("accent", "#4c8dff"),
		hover_color=palette.get("accent_hover", "#3b6dd6"),
		command=_open_achievements_view,
	)
	achievements_btn.grid(row=0, column=1, padx=(8, 0))

	achievements_status = ctk.CTkLabel(
		achievements_card,
		text="",
		text_color=palette.get("muted", "#94a3b8"),
		font=ctk.CTkFont(size=11, slant="italic"),
		justify="left",
	)
	achievements_status.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 2))

	achievements_preview = ctk.CTkFrame(achievements_card, fg_color="transparent")
	achievements_preview.grid(row=2, column=0, sticky="we", padx=12, pady=(0, 12))
	achievements_preview.grid_columnconfigure(0, weight=1)

	timeline_card = ctk.CTkFrame(right_col, corner_radius=12, fg_color=palette.get("surface", "#111b2e"))
	timeline_card.grid(row=2, column=0, sticky="we")
	timeline_card.grid_columnconfigure(0, weight=1)

	ctk.CTkLabel(
		timeline_card,
		text="Activity timeline",
		text_color=palette.get("text", "#e2e8f0"),
		font=ctk.CTkFont(size=13, weight="bold"),
	).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))

	timeline_list = ctk.CTkFrame(timeline_card, fg_color="transparent")
	timeline_list.grid(row=1, column=0, sticky="we", padx=12, pady=(0, 10))
	timeline_list.grid_columnconfigure(0, weight=1)

	suggested_card = ctk.CTkFrame(right_col, corner_radius=12, fg_color=palette.get("surface", "#111b2e"))
	suggested_card.grid(row=3, column=0, sticky="we", pady=(12, 0))
	suggested_card.grid_columnconfigure(0, weight=1)

	ctk.CTkLabel(
		suggested_card,
		text="Suggested follows",
		text_color=palette.get("text", "#e2e8f0"),
		font=ctk.CTkFont(size=13, weight="bold"),
	).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))

	suggested_list = ctk.CTkFrame(suggested_card, fg_color="transparent")
	suggested_list.grid(row=1, column=0, sticky="we", padx=12, pady=(0, 10))
	suggested_list.grid_columnconfigure(0, weight=1)

	stories_card = ctk.CTkFrame(frame, corner_radius=16, fg_color=palette.get("surface", "#111b2e"))
	stories_card.grid(row=2, column=0, sticky="we", padx=16, pady=(0, 16))
	stories_card.grid_columnconfigure(0, weight=1)

	ctk.CTkLabel(
		stories_card,
		text="Stories",
		text_color=palette.get("text", "#e2e8f0"),
		font=ctk.CTkFont(size=14, weight="bold"),
	).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))

	stories_bar = ctk.CTkFrame(stories_card, fg_color="transparent")
	stories_bar.grid(row=1, column=0, sticky="we", padx=12, pady=(0, 12))

	stories_placeholder = ctk.CTkLabel(
		stories_bar,
		text="No stories yet",
		text_color=palette.get("muted", "#94a3b8"),
	)
	stories_placeholder.grid(row=0, column=0, padx=12, pady=12, sticky="w")

	posts_frame = ctk.CTkScrollableFrame(frame, corner_radius=8)
	posts_frame.grid(row=3, column=0, sticky="nswe", padx=16, pady=(0, 16))
	posts_frame.grid_columnconfigure(0, weight=1)

	_register_story_bar(stories_bar, stories_placeholder)
	_refresh_stories_bar()

	_profile_widgets.update(
		{
			"frame": frame,
			"summary": hero,
			"info": info_lbl,
			"avatar_panel": avatar_panel,
			"avatar_label": avatar_label,
			"name": name_lbl,
			"change_btn": change_btn,
			"posts": posts_frame,
			"bio_input": bio_input,
			"location_entry": location_entry,
			"website_entry": website_entry,
			"details_status": status_lbl,
			"save_button": save_btn,
			"timeline_frame": timeline_list,
			"suggested_frame": suggested_list,
			"stats_labels": stats_labels,
			"achievements_preview": achievements_preview,
			"achievements_status": achievements_status,
			"achievements_button": achievements_btn,
			"achievements_card": achievements_card,
			"stories_card": stories_card,
			"stories_bar": stories_bar,
			"stories_placeholder": stories_placeholder,
		}
	)

	return frame


def build_notifications_frame(container: ctk.CTkFrame, palette: Palette) -> ctk.CTkFrame:
	_set_palette(palette)
	frame = ctk.CTkFrame(container, corner_radius=12, fg_color="transparent")
	frame.grid_rowconfigure(1, weight=1)
	frame.grid_columnconfigure(0, weight=1)

	header_row = ctk.CTkFrame(frame, fg_color="transparent")
	header_row.grid(row=0, column=0, sticky="we", padx=16, pady=(16, 8))
	header_row.grid_columnconfigure(0, weight=1)

	ctk.CTkLabel(
		header_row,
		text="Notifications",
		font=ctk.CTkFont(size=20, weight="bold"),
		text_color=palette.get("text", "#e2e8f0"),
	).grid(row=0, column=0, sticky="w")

	clear_btn = ctk.CTkButton(
		header_row,
		text="Clear all",
		width=90,
		fg_color=palette.get("danger", "#ef4444"),
		hover_color=palette.get("danger_hover", "#dc2626"),
		command=_handle_clear_notifications,
	)
	clear_btn.grid(row=0, column=1, padx=(8, 0))

	list_frame = ctk.CTkScrollableFrame(frame, corner_radius=8)
	list_frame.grid(row=1, column=0, sticky="nswe", padx=16, pady=(0, 16))
	list_frame.grid_columnconfigure(0, weight=1)

	_notifications_widgets.update(
		{
			"frame": frame,
			"list": list_frame,
		}
	)

	return frame


def build_inspect_profile_frame(container: ctk.CTkFrame, palette: Palette) -> ctk.CTkFrame:
	_set_palette(palette)
	frame = ctk.CTkFrame(container, corner_radius=12, fg_color="transparent")
	frame.grid_rowconfigure(2, weight=1)
	frame.grid_columnconfigure(0, weight=1)

	hero = ctk.CTkFrame(frame, fg_color="transparent")
	hero.grid(row=0, column=0, sticky="nwe", padx=16, pady=(16, 12))
	hero.grid_columnconfigure(0, weight=0)
	hero.grid_columnconfigure(1, weight=1)

	left_col = ctk.CTkFrame(hero, fg_color="transparent")
	left_col.grid(row=0, column=0, sticky="nw")
	left_col.grid_columnconfigure(0, weight=1)

	avatar_panel = ctk.CTkFrame(left_col, fg_color="transparent")
	avatar_panel.grid(row=0, column=0, sticky="nw")
	avatar_panel.grid_columnconfigure(0, weight=1)

	avatar_label = tk.Label(avatar_panel, bg=palette.get("surface", "#111b2e"), bd=0)
	avatar_label.grid(row=0, column=0, sticky="n", pady=(0, 12))

	header = ctk.CTkLabel(
		left_col,
		text="Profile",
		font=ctk.CTkFont(size=20, weight="bold"),
		text_color=palette.get("text", "#e2e8f0"),
	)
	header.grid(row=1, column=0, sticky="w")

	info_lbl = ctk.CTkLabel(
		left_col,
		text="",
		justify="left",
		anchor="w",
		wraplength=260,
		text_color=palette.get("muted", "#94a3b8"),
	)
	info_lbl.grid(row=2, column=0, sticky="we", pady=(6, 0))

	button_row = ctk.CTkFrame(left_col, fg_color="transparent")
	button_row.grid(row=3, column=0, sticky="w", pady=(12, 0))
	button_row.grid_columnconfigure(0, weight=1)
	button_row.grid_columnconfigure(1, weight=1)

	message_btn = ctk.CTkButton(button_row, text="Message", width=120, command=lambda: None)
	message_btn.grid(row=0, column=0, padx=(0, 6))

	follow_btn = ctk.CTkButton(button_row, text="Follow", width=120)
	follow_btn.grid(row=0, column=1, padx=(6, 0))

	right_col = ctk.CTkFrame(hero, fg_color="transparent")
	right_col.grid(row=0, column=1, sticky="nwe", padx=(24, 0))
	right_col.grid_columnconfigure(0, weight=1)

	stats_card = ctk.CTkFrame(right_col, corner_radius=12, fg_color=palette.get("surface", "#111b2e"))
	stats_card.grid(row=0, column=0, sticky="we")
	for col in range(4):
		stats_card.grid_columnconfigure(col, weight=1)
	metrics = [
		("Followers", "followers"),
		("Following", "following"),
		("Posts", "posts"),
		("Likes", "likes"),
	]
	inspect_stats_labels: dict[str, ctk.CTkLabel] = {}
	for col, (title, key) in enumerate(metrics):
		slot = ctk.CTkFrame(stats_card, fg_color="transparent")
		slot.grid(row=0, column=col, sticky="we", padx=10, pady=10)
		slot.grid_columnconfigure(0, weight=1)
		value_lbl = ctk.CTkLabel(
			slot,
			text="0",
			font=ctk.CTkFont(size=18, weight="bold"),
			text_color=palette.get("text", "#e2e8f0"),
		)
		value_lbl.grid(row=0, column=0, sticky="w")
		title_lbl = ctk.CTkLabel(
			slot,
			text=title,
			font=ctk.CTkFont(size=11),
			text_color=palette.get("muted", "#94a3b8"),
		)
		title_lbl.grid(row=1, column=0, sticky="w", pady=(2, 0))
		inspect_stats_labels[key] = value_lbl

	mutual_card = ctk.CTkFrame(right_col, corner_radius=12, fg_color=palette.get("surface", "#111b2e"))
	mutual_card.grid(row=1, column=0, sticky="we", pady=(12, 0))
	mutual_card.grid_columnconfigure(0, weight=1)

	ctk.CTkLabel(
		mutual_card,
		text="Mutual followers",
		text_color=palette.get("text", "#e2e8f0"),
		font=ctk.CTkFont(size=13, weight="bold"),
	).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))

	mutual_list = ctk.CTkFrame(mutual_card, fg_color="transparent")
	mutual_list.grid(row=1, column=0, sticky="we", padx=12, pady=(0, 10))
	mutual_list.grid_columnconfigure(0, weight=1)

	stories_card = ctk.CTkFrame(frame, corner_radius=16, fg_color=palette.get("surface", "#111b2e"))
	stories_card.grid(row=1, column=0, sticky="we", padx=16, pady=(0, 16))
	stories_card.grid_columnconfigure(0, weight=1)

	ctk.CTkLabel(
		stories_card,
		text="Stories",
		text_color=palette.get("text", "#e2e8f0"),
		font=ctk.CTkFont(size=14, weight="bold"),
	).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))

	stories_bar = ctk.CTkFrame(stories_card, fg_color="transparent")
	stories_bar.grid(row=1, column=0, sticky="we", padx=12, pady=(0, 12))

	stories_placeholder = ctk.CTkLabel(
		stories_bar,
		text="No stories yet",
		text_color=palette.get("muted", "#94a3b8"),
	)
	stories_placeholder.grid(row=0, column=0, padx=12, pady=12, sticky="w")

	posts_frame = ctk.CTkScrollableFrame(frame, corner_radius=8)
	posts_frame.grid(row=2, column=0, sticky="nswe", padx=16, pady=(0, 16))
	posts_frame.grid_columnconfigure(0, weight=1)

	_register_story_bar(stories_bar, stories_placeholder)
	_refresh_stories_bar()

	_inspect_widgets.update(
		{
			"frame": frame,
			"summary": hero,
			"avatar_panel": avatar_panel,
			"avatar_label": avatar_label,
			"header": header,
			"info": info_lbl,
			"mutual_card": mutual_card,
			"mutual_list": mutual_list,
			"follow_btn": follow_btn,
			"message_btn": message_btn,
			"posts": posts_frame,
			"stats_labels": inspect_stats_labels,
			"stories_card": stories_card,
			"stories_bar": stories_bar,
			"stories_placeholder": stories_placeholder,
		}
	)

	return frame


def build_dm_frame(container: ctk.CTkFrame, palette: Palette) -> ctk.CTkFrame:
	_set_palette(palette)
	frame = ctk.CTkFrame(container, corner_radius=12, fg_color="transparent")
	frame.grid_rowconfigure(2, weight=1)
	frame.grid_columnconfigure(0, weight=0)
	frame.grid_columnconfigure(1, weight=1)

	header_row = ctk.CTkFrame(frame, fg_color="transparent")
	header_row.grid(row=0, column=0, columnspan=2, sticky="we", padx=16, pady=(16, 6))
	header_row.grid_columnconfigure(0, weight=1)

	header_lbl = ctk.CTkLabel(
		header_row,
		text="Direct Message",
		font=ctk.CTkFont(size=20, weight="bold"),
		text_color=palette.get("text", "#e2e8f0"),
	)
	header_lbl.grid(row=0, column=0, sticky="w")

	back_btn = ctk.CTkButton(
		header_row,
		text="Back",
		width=70,
		fg_color="transparent",
		border_width=1,
		border_color=palette.get("muted", "#94a3b8"),
		text_color=palette.get("muted", "#94a3b8"),
		hover_color=palette.get("surface", "#111b2e"),
		command=lambda: _show_frame_cb("inspect_profile") if _show_frame_cb else None,
	)
	back_btn.grid(row=0, column=1, padx=(8, 0))

	sidebar = ctk.CTkScrollableFrame(frame, corner_radius=10)
	sidebar.grid(row=2, column=0, rowspan=2, sticky="nswe", padx=(16, 8), pady=(0, 16))
	sidebar.grid_columnconfigure(0, weight=1)

	thread = ctk.CTkScrollableFrame(frame, corner_radius=10, fg_color=palette.get("surface", "#111b2e"))
	thread.grid(row=2, column=1, sticky="nswe", padx=(0, 16), pady=(0, 8))
	thread.grid_columnconfigure(0, weight=1)

	info_card = ctk.CTkFrame(frame, corner_radius=10, fg_color=palette.get("surface", "#111b2e"))
	info_card.grid(row=1, column=1, sticky="we", padx=(0, 16), pady=(0, 8))
	info_card.grid_columnconfigure(0, weight=1)
	info_card.grid_columnconfigure(1, weight=0)
	info_card.grid_remove()

	info_title = ctk.CTkLabel(
		info_card,
		text="Group chat",
		font=ctk.CTkFont(size=16, weight="bold"),
		text_color=palette.get("text", "#e2e8f0"),
	)
	info_title.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))

	rename_btn = ctk.CTkButton(
		info_card,
		text="Rename",
		width=90,
		fg_color="transparent",
		border_width=1,
		border_color=palette.get("muted", "#94a3b8"),
		text_color=palette.get("muted", "#94a3b8"),
		hover_color=palette.get("surface", "#111b2e"),
		command=_handle_edit_group_name,
	)
	rename_btn.grid(row=0, column=1, sticky="e", padx=(0, 12), pady=(12, 4))

	info_members = ctk.CTkLabel(
		info_card,
		text="",
		font=ctk.CTkFont(size=13),
		text_color=palette.get("muted", "#94a3b8"),
		wraplength=400,
		justify="left",
	)
	info_members.grid(row=1, column=0, columnspan=2, sticky="w", padx=12)

	owner_label = ctk.CTkLabel(
		info_card,
		text="",
		font=ctk.CTkFont(size=12),
		text_color=palette.get("muted", "#94a3b8"),
	)
	owner_label.grid(row=2, column=0, sticky="w", padx=12, pady=(8, 0))

	owner_btn = ctk.CTkButton(
		info_card,
		text="Transfer owner",
		width=120,
		fg_color="transparent",
		border_width=1,
		border_color=palette.get("muted", "#94a3b8"),
		text_color=palette.get("muted", "#94a3b8"),
		hover_color=palette.get("surface", "#111b2e"),
		command=_handle_transfer_group_owner,
	)
	owner_btn.grid(row=2, column=1, sticky="e", padx=(0, 12), pady=(8, 0))

	announcement_title = ctk.CTkLabel(
		info_card,
		text="Announcement",
		font=ctk.CTkFont(size=13, weight="bold"),
		text_color=palette.get("text", "#e2e8f0"),
	)
	announcement_title.grid(row=3, column=0, sticky="w", padx=12, pady=(10, 0))

	announcement_btn = ctk.CTkButton(
		info_card,
		text="Edit",
		width=80,
		fg_color="transparent",
		border_width=1,
		border_color=palette.get("muted", "#94a3b8"),
		text_color=palette.get("muted", "#94a3b8"),
		hover_color=palette.get("surface", "#111b2e"),
		command=_handle_edit_group_announcement,
	)
	announcement_btn.grid(row=3, column=1, sticky="e", padx=(0, 12), pady=(10, 0))

	announcement_label = ctk.CTkLabel(
		info_card,
		text="",
		font=ctk.CTkFont(size=12),
		text_color=palette.get("muted", "#94a3b8"),
		wraplength=400,
		justify="left",
	)
	announcement_label.grid(row=4, column=0, columnspan=2, sticky="w", padx=12, pady=(2, 6))

	invite_title = ctk.CTkLabel(
		info_card,
		text="Invite link",
		font=ctk.CTkFont(size=13, weight="bold"),
		text_color=palette.get("text", "#e2e8f0"),
	)
	invite_title.grid(row=5, column=0, sticky="w", padx=12, pady=(6, 0))

	copy_invite_btn = ctk.CTkButton(
		info_card,
		text="Copy",
		width=80,
		fg_color=palette.get("accent", "#4c8dff"),
		hover_color=palette.get("accent_hover", "#3b6dd6"),
		command=_handle_copy_group_invite,
	)
	copy_invite_btn.grid(row=5, column=1, sticky="e", padx=(0, 12), pady=(6, 0))

	invite_value = ctk.CTkLabel(
		info_card,
		text="",
		font=ctk.CTkFont(size=12),
		text_color=palette.get("muted", "#94a3b8"),
		wraplength=400,
		justify="left",
	)
	invite_value.grid(row=6, column=0, columnspan=2, sticky="w", padx=12, pady=(2, 4))

	regen_invite_btn = ctk.CTkButton(
		info_card,
		text="Regenerate",
		width=110,
		fg_color="transparent",
		border_width=1,
		border_color=palette.get("muted", "#94a3b8"),
		text_color=palette.get("muted", "#94a3b8"),
		hover_color=palette.get("surface", "#111b2e"),
		command=_handle_regenerate_group_invite,
	)
	regen_invite_btn.grid(row=7, column=1, sticky="e", padx=(0, 12), pady=(0, 4))

	leave_btn = ctk.CTkButton(
		info_card,
		text="Leave group",
		width=120,
		fg_color=palette.get("danger", "#ef4444"),
		hover_color=palette.get("danger_hover", "#dc2626"),
		command=_handle_leave_group_chat,
	)
	leave_btn.grid(row=8, column=0, sticky="w", padx=12, pady=(12, 12))

	composer = ctk.CTkFrame(frame, fg_color="transparent")
	composer.grid(row=3, column=1, sticky="we", padx=(0, 16), pady=(0, 16))
	composer.grid_columnconfigure(0, weight=1)
	composer.grid_columnconfigure(1, weight=0)
	composer.grid_columnconfigure(2, weight=0)

	entry = ctk.CTkEntry(
		composer,
		placeholder_text="Write a message...",
		fg_color=palette.get("surface", "#111b2e"),
		text_color=palette.get("text", "#e2e8f0"),
	)
	entry.grid(row=0, column=0, sticky="we", padx=(0, 6))
	_bind_return_submit(entry, _handle_send_dm)
	entry.bind("<KeyRelease>", _handle_dm_typing_event)
	entry.bind("<FocusIn>", _handle_dm_focus_in)
	entry.bind("<FocusOut>", _handle_dm_focus_out)

	attach_btn = ctk.CTkButton(
		composer,
		text="Attach",
		width=80,
		fg_color="transparent",
		border_width=1,
		border_color=palette.get("accent", "#4c8dff"),
		text_color=palette.get("accent", "#4c8dff"),
		hover_color=palette.get("surface", "#111b2e"),
		command=_handle_add_dm_attachment,
	)
	attach_btn.grid(row=0, column=1, padx=(0, 6))

	send_btn = ctk.CTkButton(
		composer,
		text="Send",
		width=70,
		fg_color=palette.get("accent", "#4c8dff"),
		hover_color=palette.get("accent_hover", "#3b6dd6"),
		command=_handle_send_dm,
	)
	send_btn.grid(row=0, column=2)

	attachments_frame = ctk.CTkFrame(composer, fg_color="transparent")
	attachments_frame.grid(row=1, column=0, columnspan=3, sticky="we", padx=(0, 6), pady=(6, 0))
	attachments_frame.grid_remove()

	typing_label = ctk.CTkLabel(
		composer,
		text="",
		font=ctk.CTkFont(size=11, slant="italic"),
		text_color=palette.get("muted", "#94a3b8"),
	)
	typing_label.grid(row=2, column=0, columnspan=3, sticky="w", padx=(0, 6), pady=(4, 0))
	typing_label.grid_remove()

	_dm_widgets.update(
		{
			"frame": frame,
			"header": header_lbl,
			"sidebar": sidebar,
			"thread": thread,
			"info_card": info_card,
			"info_title": info_title,
			"info_members": info_members,
			"owner_label": owner_label,
			"owner_button": owner_btn,
			"leave_button": leave_btn,
			"rename_button": rename_btn,
			"announcement_label": announcement_label,
			"announcement_button": announcement_btn,
			"copy_invite_button": copy_invite_btn,
			"invite_label": invite_value,
			"regen_invite_button": regen_invite_btn,
			"typing_label": typing_label,
			"entry": entry,
			"send": send_btn,
			"composer": composer,
			"attach_button": attach_btn,
			"attachments_frame": attachments_frame,
		}
	)

	return frame


def initialize_ui(frames: dict[str, ctk.CTkFrame]) -> None:
	global _frames
	_frames = frames

	configure_helpers(
		current_user_getter=lambda: _ui_state.current_user,
		users=users,
		posts=posts,
		messagebox_mod=messagebox,
		persist_cb=persist,
		render_feed_cb=lambda: _request_render("home"),
		render_profile_cb=lambda: _request_render("profile"),
		render_notifications_cb=lambda: _request_render("notifications"),
		render_dm_sidebar_cb=lambda: _request_render("dm"),
		render_inspected_profile_cb=lambda: _request_render("inspect_profile"),
		now_ts_cb=now_ts,
		render_achievements_cb=lambda: _request_render("achievements"),
	)

	_auto_sign_in_if_remembered()

	# Only mark active view as dirty during startup to reduce initial lag
	_mark_smart_dirty("home", "profile", "notifications", "inspect_profile", "dm", "videos", "search", "achievements")
	_update_home_status()
	# Defer server check until after startup
	_update_server_status(check=False)
	_update_videos_controls()
	
	# Defer rendering and server check until after startup to avoid blocking
	def _delayed_startup_tasks():
		_render_active_view()
		# Now check server status after UI is rendered
		_update_server_status(check=True)
	
	# Schedule tasks after a short delay to let startup complete
	if _frames:
		anchor = next(iter(_frames.values()))
		anchor.after(100, _delayed_startup_tasks)

	# Start lightweight backup sync checker (5-minute intervals) as failsafe
	# Real-time updates happen immediately when changes occur
	_start_realtime_listener()
	_start_backup_sync_checker()


def refresh_views(_frames_unused: dict[str, ctk.CTkFrame]) -> None:
	_ui_state.feed_state.current_user = _ui_state.current_user
	_update_nav_controls()
	_update_home_status()
	_update_videos_controls()
	_render_active_view()


def handle_sign_in() -> None:
	if _ui_state.current_user:
		if messagebox.askyesno("Sign out", "Do you really want to sign out?"):
			remember_user(None)
			_set_current_user(None)
			refresh_views(_frames)
	else:
		_show_auth_window("login")


def handle_show_notifications() -> None:
	_request_render("notifications")
	if _show_frame_cb:
		_show_frame_cb("notifications")


def handle_open_messages() -> None:
	if not require_login("view messages"):
		return
	_select_default_dm_conversation()
	_request_render("dm")
	if _show_frame_cb:
		_show_frame_cb("dm")


def _open_achievements_view() -> None:
	"""Navigate to the achievements view when triggered from profile."""
	if not _ui_state.current_user:
		messagebox.showinfo("Achievements", "Sign in to track your achievements.")
		return
	_request_render("achievements")
	if _show_frame_cb:
		_show_frame_cb("achievements")


def _set_current_user(username: Optional[str]) -> None:
	previous_user = _ui_state.current_user
	_ui_state.current_user = username
	_ui_state.feed_state.current_user = username
	if previous_user != username:
		_set_active_dm_conversation(None, None)
	_dm_draft_attachments.clear()
	_refresh_dm_attachments()
	if not username:
		_ui_state.inspected_user = None
		_post_attachments.clear()
		_refresh_post_attachments()
	else:
		_select_default_dm_conversation()
	# Use smart dirty marking to avoid unnecessary re-renders when user changes
	_mark_smart_dirty("home", "profile", "notifications", "inspect_profile", "dm", "videos", "achievements")
	_update_videos_controls()


def _auto_sign_in_if_remembered() -> None:
	remembered = get_remembered_user()
	if not remembered:
		return
	if remembered not in users:
		remember_user(None)
		return
	_set_current_user(remembered)


def _update_nav_controls() -> None:
	"""Component-based nav control updates - only changes what's needed"""
	global _notification_badge_component
	
	signin = _nav_controls.get("signin")
	profile = _nav_controls.get("profile")
	notifications_btn = _nav_controls.get("notifications")
	messages_btn = _nav_controls.get("messages")

	signed_in = bool(_ui_state.current_user)
	if signin:
		signin.configure(state="normal")
	set_nav_signed_in_state(signed_in)
	state = "normal" if signed_in else "disabled"
	if profile:
		profile.configure(state=state)
	if notifications_btn:
		notifications_btn.configure(state=state)
		
	# Initialize badge component on first use
	if _notification_badge_component is None and notifications_btn:
		_notification_badge_component = NotificationBadgeComponent(palette=_palette)
		_notification_badge_component.set_button(notifications_btn)
		component_registry.register(_notification_badge_component)
	
	# Update badge using component (avoids full nav re-render)
	if signed_in:
		user_notes = users.get(_ui_state.current_user or "", {}).get("notifications", [])
		has_alert = bool(user_notes) and _ui_state.active_view != "notifications"
		notification_count = len(user_notes) if has_alert else 0
		
		# Component only updates if count changed
		if _notification_badge_component:
			_notification_badge_component.update(notification_count)
	else:
		has_alert = False
		if _notification_badge_component:
			_notification_badge_component.update(0)
			
	set_nav_notifications_alert(has_alert)
	if messages_btn:
		messages_btn.configure(state=state)
	for vid in list(_video_cards.keys()):
		_update_video_reaction_ui(vid)


def _refresh_notifications_ui() -> None:
	"""Ensure the notifications view and nav badge reflect current state."""
	_request_render("notifications")
	_update_nav_controls()


def _handle_notification_click(notification_data: dict[str, Any]) -> None:
	"""Handle clicks on notifications - navigate to the appropriate content"""
	meta = notification_data.get("meta", {})
	if not isinstance(meta, dict):
		return
		
	meta_type = meta.get("type")
	
	if meta_type == "dm":
		sender = meta.get("from")
		if sender:
			_open_dm_from_notification(sender)
	elif meta_type == "group_dm":
		group_target = meta.get("group")
		if group_target:
			_open_group_from_notification(group_target)
	elif meta_type == "mention":
		resource = meta.get("resource")
		if resource in {"post", "reply"}:
			post_id = meta.get("post_id")
			reply_id = meta.get("reply_id") if resource == "reply" else None
			if post_id:
				_focus_post_from_notification(post_id, reply_id=reply_id)
		elif resource == "story":
			story_id = meta.get("story_id")
			if story_id:
				_open_story_from_notification(story_id)
		elif resource == "video":
			video_id = meta.get("video_id")
			if video_id:
				_open_video_from_notification(video_id)
		elif resource in {"video_comment", "video_reply"}:
			video_id = meta.get("video_id")
			if video_id:
				_open_video_from_notification(video_id, open_comments=True)
	elif meta_type == "post_publish":
		post_id = meta.get("post_id")
		if post_id:
			_focus_post_from_notification(post_id)
	elif meta_type == "story_publish":
		story_id = meta.get("story_id")
		if story_id:
			_open_story_from_notification(story_id)
	elif meta_type == "video_publish":
		video_id = meta.get("video_id")
		if video_id:
			_open_video_from_notification(video_id)


def _update_home_status() -> None:
	status_lbl: ctk.CTkLabel = _home_widgets.get("status")
	post_btn: ctk.CTkButton = _home_widgets.get("post_button")
	attach_btn: ctk.CTkButton = _home_widgets.get("attach_button")
	add_story_btn: ctk.CTkButton = _home_widgets.get("add_story_button")
	if not status_lbl or not post_btn:
		return
	if _ui_state.current_user:
		status_lbl.configure(text=f"Signed in as @{_ui_state.current_user}")
		post_btn.configure(state="normal")
		if attach_btn:
			attach_btn.configure(state="normal")
		if add_story_btn:
			add_story_btn.configure(state="normal")
	else:
		status_lbl.configure(text="Signed out")
		post_btn.configure(state="disabled")
		if attach_btn:
			attach_btn.configure(state="disabled")
		if add_story_btn:
			add_story_btn.configure(state="disabled")
	_update_server_status()


def _update_videos_controls() -> None:
	select_btn: ctk.CTkButton = _videos_widgets.get("select_button")
	upload_btn: ctk.CTkButton = _videos_widgets.get("upload_button")
	caption_entry: ctk.CTkEntry = _videos_widgets.get("caption_entry")
	status_lbl: ctk.CTkLabel = _videos_widgets.get("status_label")
	signed_in = bool(_ui_state.current_user)
	state = "normal" if signed_in else "disabled"
	for btn in (select_btn, upload_btn):
		if btn:
			btn.configure(state=state)
	if caption_entry:
		caption_entry.configure(state=state)
		if not signed_in:
			caption_entry.delete(0, tk.END)
	if not signed_in:
		_set_video_upload_path("")
		_videos_widgets["status_mode"] = "muted"
		if status_lbl:
			status_lbl.configure(
				text="Sign in to upload videos",
				text_color=_palette.get("muted", "#94a3b8"),
			)
		return

	server_note = _server_summary_text()
	if status_lbl:
		text_lines = ["Choose a video to share"]
		if server_note:
			text_lines.append(server_note)
		status_lbl.configure(
			text="\n".join(text_lines),
			text_color=_palette.get("muted", "#94a3b8"),
		)
		_videos_widgets["status_mode"] = "muted"


def _render_feed_section() -> None:
	_refresh_stories_bar()
	feed_container: ctk.CTkScrollableFrame = _home_widgets.get("feed")
	if not feed_container:
		return

	callbacks = FeedCallbacks(
		open_profile=_open_profile,
		toggle_post_reaction=_handle_toggle_post_reaction,
		toggle_replies=_handle_toggle_replies,
		open_reply_box=_handle_open_reply_box,
		start_edit=_handle_start_edit,
		cancel_edit=_handle_cancel_edit,
		apply_edit=_handle_apply_edit,
		delete_post=_handle_delete_post,
		start_reply_edit=_handle_start_reply_edit,
		cancel_reply_edit=_handle_cancel_reply_edit,
		apply_reply_edit=_handle_apply_reply_edit,
		delete_reply=_handle_delete_reply,
		submit_reply=_handle_submit_reply,
		create_reply_toolbar=_create_reply_toolbar,
		open_attachment=_open_attachment,
		render_inline_video=_render_inline_video,
		get_reaction_icon=lambda kind, size: _ensure_reaction_icon(kind, size=size),
	)

	render_feed(
		feed_container=feed_container,
		posts=posts,
		palette=_palette,
		state=_ui_state.feed_state,
		callbacks=callbacks,
		load_profile_avatar=_load_profile_avatar,
		load_image_for_tk=_load_image_for_tk,
		open_image=_open_image,
	)

	if _ui_state.feed_state.focus_post_id or _ui_state.feed_state.focus_reply_id:
		def _clear_focus_markers() -> None:
			_ui_state.feed_state.focus_post_id = None
			_ui_state.feed_state.focus_reply_id = None

		try:
			feed_container.after(800, _clear_focus_markers)
		except Exception:
			_clear_focus_markers()


def _render_profile_section() -> None:
	info_lbl = _profile_widgets.get("info")
	posts_frame = _profile_widgets.get("posts")
	name_lbl = _profile_widgets.get("name")
	bio_input = _profile_widgets.get("bio_input")
	location_entry = _profile_widgets.get("location_entry")
	website_entry = _profile_widgets.get("website_entry")
	save_button = _profile_widgets.get("save_button")
	status_lbl = _profile_widgets.get("details_status")
	timeline_frame = _profile_widgets.get("timeline_frame")
	suggested_frame = _profile_widgets.get("suggested_frame")
	stats_labels: dict[str, ctk.CTkLabel] = _profile_widgets.get("stats_labels") or {}
	achievements_preview: Optional[ctk.CTkFrame] = _profile_widgets.get("achievements_preview")
	achievements_status: Optional[ctk.CTkLabel] = _profile_widgets.get("achievements_status")
	achievements_button: Optional[ctk.CTkButton] = _profile_widgets.get("achievements_button")
	text_color = _palette.get("text", "#e2e8f0")
	muted_color = _palette.get("muted", "#94a3b8")
	if not info_lbl or not posts_frame:
		return

	signed_in = bool(_ui_state.current_user)
	current_user = _ui_state.current_user
	record = users.get(current_user, {}) if signed_in else {}
	progress = _achievement_progress_for(current_user) if signed_in else []

	if name_lbl:
		if signed_in:
			name_lbl.configure(text=f"@{current_user}", text_color=text_color)
		else:
			name_lbl.configure(text="Sign in to view your profile", text_color=muted_color)

	if save_button:
		save_button.configure(state="normal" if signed_in else "disabled")

	if not signed_in and status_lbl:
		status_lbl.configure(text="Sign in to edit your profile.", text_color=muted_color)

	if achievements_button:
		achievements_button.configure(state="normal" if signed_in else "disabled")

	stats_payload = {
		"followers": 0,
		"following": 0,
		"posts": 0,
		"likes": 0,
	}
	if signed_in:
		stats_payload["followers"] = len(record.get("followers", []))
		stats_payload["following"] = len(record.get("following", []))
		stats_payload["posts"] = sum(1 for post in posts if post.get("author") == current_user)
		stats_payload["likes"] = total_likes_for(current_user)
	for key, label in stats_labels.items():
		try:
			label.configure(text=str(stats_payload.get(key, 0)))
		except Exception:
			pass

	if bio_input:
		focus_widget = None
		try:
			focus_widget = bio_input.focus_get()
		except tk.TclError:
			focus_widget = None
		inner_text = getattr(bio_input, "_textbox", None)
		bio_has_focus = focus_widget in {bio_input, inner_text}
		if signed_in:
			bio_input.configure(state="normal")
			desired_bio = record.get("bio", "")
			current_bio = bio_input.get("1.0", "end").strip()
			if desired_bio != current_bio and not bio_has_focus:
				bio_input.delete("1.0", "end")
				if desired_bio:
					bio_input.insert("1.0", desired_bio)
		else:
			bio_input.configure(state="normal")
			bio_input.delete("1.0", "end")
			bio_input.insert("1.0", "Sign in to update your bio.")
			bio_input.configure(state="disabled")

	if location_entry:
		focus_widget = None
		try:
			focus_widget = location_entry.focus_get()
		except tk.TclError:
			focus_widget = None
		inner_entry = getattr(location_entry, "_entry", None)
		location_has_focus = focus_widget in {location_entry, inner_entry}
		if signed_in:
			location_entry.configure(state="normal")
			desired_location = record.get("location", "")
			current_location = location_entry.get().strip()
			if desired_location != current_location and not location_has_focus:
				location_entry.delete(0, tk.END)
				if desired_location:
					location_entry.insert(0, desired_location)
		else:
			location_entry.configure(state="normal")
			location_entry.delete(0, tk.END)
			location_entry.insert(0, "Sign in to add a location")
			location_entry.configure(state="disabled")

	if website_entry:
		focus_widget = None
		try:
			focus_widget = website_entry.focus_get()
		except tk.TclError:
			focus_widget = None
		inner_entry = getattr(website_entry, "_entry", None)
		website_has_focus = focus_widget in {website_entry, inner_entry}
		if signed_in:
			website_entry.configure(state="normal")
			desired_website = record.get("website", "")
			current_website = website_entry.get().strip()
			if desired_website != current_website and not website_has_focus:
				website_entry.delete(0, tk.END)
				if desired_website:
					website_entry.insert(0, desired_website)
		else:
			website_entry.configure(state="normal")
			website_entry.delete(0, tk.END)
			website_entry.insert(0, "Sign in to share your website")
			website_entry.configure(state="disabled")

	if timeline_frame:
		for child in timeline_frame.winfo_children():
			child.destroy()
		if signed_in:
			timeline_entries = _collect_activity_timeline(current_user)
			if timeline_entries:
				for ts, description in timeline_entries:
					row = ctk.CTkFrame(timeline_frame, fg_color="transparent")
					row.grid(sticky="ew", padx=0, pady=(0, 8))
					row.grid_columnconfigure(0, weight=1)
					desc_lbl = ctk.CTkLabel(
						row,
						text=description,
						text_color=text_color,
						anchor="w",
						justify="left",
						wraplength=360,
					)
					desc_lbl.grid(row=0, column=0, sticky="w")
					time_str = ts.strftime("%b %d, %Y · %I:%M %p")
					ctk.CTkLabel(
						row,
						text=time_str,
						text_color=muted_color,
						font=ctk.CTkFont(size=11),
						anchor="w",
					).grid(row=1, column=0, sticky="w", pady=(2, 0))
			else:
				ctk.CTkLabel(
					timeline_frame,
					text="No recent activity yet.",
					text_color=muted_color,
					anchor="w",
				).grid(sticky="w", padx=4, pady=4)
		else:
			ctk.CTkLabel(
				timeline_frame,
				text="Sign in to see your activity timeline.",
				text_color=muted_color,
				anchor="w",
			).grid(sticky="w", padx=4, pady=4)

	if suggested_frame:
		for child in suggested_frame.winfo_children():
			child.destroy()
		if signed_in:
			suggestions = _compute_suggested_users(current_user)
			if suggestions:
				viewer_following = set(record.get("following", [])) if record else set()
				for suggested in suggestions:
					row = ctk.CTkFrame(suggested_frame, fg_color=_palette.get("surface", "#111b2e"), corner_radius=8)
					row.grid(sticky="ew", padx=0, pady=(0, 8))
					row.grid_columnconfigure(0, weight=1)
					name_lbl = ctk.CTkLabel(
						row,
						text=f"@{suggested}",
						text_color=text_color,
						font=ctk.CTkFont(size=13, weight="bold"),
						anchor="w",
						justify="left",
					)
					name_lbl.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 0))
					name_lbl.configure(cursor="hand2")
					name_lbl.bind("<Button-1>", lambda _event, user=suggested: _open_profile(user))
					preview = _ellipsize_text(users.get(suggested, {}).get("bio", ""), 80)
					if preview:
						ctk.CTkLabel(
							row,
							text=preview,
							text_color=muted_color,
							anchor="w",
							justify="left",
							wraplength=220,
							font=ctk.CTkFont(size=11),
						).grid(row=1, column=0, sticky="w", padx=12, pady=(2, 10))
					else:
						ctk.CTkLabel(
							row,
							text="No bio yet",
							text_color=muted_color,
							anchor="w",
							font=ctk.CTkFont(size=11),
						).grid(row=1, column=0, sticky="w", padx=12, pady=(2, 10))
					already_following = suggested in viewer_following
					button_kwargs = {
						"width": 96,
						"height": 32,
						"corner_radius": 18,
					}
					if already_following:
						button_kwargs.update(
							{
								"text": "Following",
								"fg_color": _palette.get("surface", "#111b2e"),
								"text_color": muted_color,
								"hover_color": _palette.get("surface", "#111b2e"),
							}
						)

						def _make_unfollow_handler() -> None:
							_handle_unfollow(suggested)

						follow_cmd = _make_unfollow_handler
					else:
						button_kwargs.update(
							{
								"text": "Follow",
								"fg_color": _palette.get("accent", "#38bdf8"),
								"text_color": _palette.get("buttonText", "#0f172a"),
								"hover_color": _palette.get("accentHighlight", "#0ea5e9"),
							}
						)

						def _make_follow_handler() -> None:
							_handle_follow(suggested)

						follow_cmd = _make_follow_handler
					action_btn = ctk.CTkButton(row, command=follow_cmd, **button_kwargs)
					action_btn.grid(row=0, column=1, rowspan=2, padx=12, pady=12)
			else:
				ctk.CTkLabel(
					suggested_frame,
					text="No suggestions available right now.",
					text_color=muted_color,
					anchor="w",
				).grid(sticky="w", padx=4, pady=4)
		else:
			ctk.CTkLabel(
				suggested_frame,
				text="Sign in to see suggested follows.",
				text_color=muted_color,
				anchor="w",
			).grid(sticky="w", padx=4, pady=4)

	if achievements_status:
		if not signed_in:
			achievements_status.configure(text="Sign in to track achievements.", text_color=muted_color)
		elif progress:
			completed = sum(1 for item in progress if item.get("complete"))
			achievements_status.configure(
				text=f"{completed} of {ACHIEVEMENT_COUNT} achievements complete.",
				text_color=muted_color,
			)
		else:
			achievements_status.configure(
				text="Start creating to unlock your first achievement.",
				text_color=muted_color,
			)

	if achievements_preview:
		preview_data = progress if signed_in else []
		accent = _palette.get("accent", "#4c8dff")
		_render_profile_achievements_preview(
			achievements_preview,
			preview_data,
			text_color=text_color,
			muted_color=muted_color,
			accent_color=accent,
		)
		if not signed_in:
			for child in achievements_preview.winfo_children():
				child.configure(text_color=muted_color) if isinstance(child, ctk.CTkLabel) else None

	callbacks = FeedCallbacks(
		open_profile=_open_profile,
		toggle_post_reaction=_handle_toggle_post_reaction,
		toggle_replies=_handle_toggle_replies,
		open_reply_box=_handle_open_reply_box,
		start_edit=_handle_start_edit,
		cancel_edit=_handle_cancel_edit,
		apply_edit=_handle_apply_edit,
		delete_post=_handle_delete_post,
		start_reply_edit=_handle_start_reply_edit,
		cancel_reply_edit=_handle_cancel_reply_edit,
		apply_reply_edit=_handle_apply_reply_edit,
		delete_reply=_handle_delete_reply,
		submit_reply=_handle_submit_reply,
		create_reply_toolbar=_create_reply_toolbar,
		open_attachment=_open_attachment,
		render_inline_video=_render_inline_video,
		get_reaction_icon=lambda kind, size: _ensure_reaction_icon(kind, size=size),
	)

	render_profile(
		profile_info_label=info_lbl,
		profile_posts_frame=posts_frame,
		users=users,
		posts=posts,
		palette=_palette,
		state=_ui_state.feed_state,
		callbacks=callbacks,
		total_likes_for=total_likes_for,
		load_profile_avatar=_load_profile_avatar,
		load_image_for_tk=_load_image_for_tk,
		open_image=_open_image,
	)
	info_lbl.configure(justify="left", anchor="w", wraplength=260)


def _render_profile_avatar() -> None:
	panel = _profile_widgets.get("avatar_panel")
	avatar_label = _profile_widgets.get("avatar_label")
	change_btn = _profile_widgets.get("change_btn")
	if not panel or not avatar_label or not change_btn:
		return

	update_profile_avatar_display(
		current_user=_ui_state.current_user,
		profile_avatar_panel=panel,
		profile_avatar_label=avatar_label,
		profile_change_pic_btn=change_btn,
		load_avatar=lambda user, size: load_profile_avatar(
			user,
			size,
			users=users,
			base_dir=BASE_DIR,
			default_profile_pic=DEFAULT_PROFILE_PIC,
			cache=_profile_avatar_cache,
		),
	)


def _render_notifications() -> None:
	"""Component-based notification rendering - only updates changed notifications"""
	global _notification_list_component
	
	list_frame: ctk.CTkScrollableFrame = _notifications_widgets.get("list")
	if not list_frame:
		return
		
	# Initialize component on first render
	if _notification_list_component is None:
		_notification_list_component = NotificationListComponent(
			palette=_palette,
			on_notification_click=_handle_notification_click,
			on_follow_click=_handle_follow_from_notification,
			get_current_user=lambda: _ui_state.current_user,
			users=users,
		)
		_notification_list_component.mount(list_frame)
		component_registry.register(_notification_list_component)
	
	def _clear_placeholders() -> None:
		for child in list_frame.winfo_children():
			if getattr(child, "_notification_placeholder", False):
				child.destroy()

	# Handle empty states
	if not _ui_state.current_user:
		_notification_list_component.update([])
		# Clear components for signed-out state
		for child in list_frame.winfo_children():
			child.destroy()
		placeholder = ctk.CTkLabel(
			list_frame,
			text="Please sign in to view notifications.",
			text_color=_palette.get("muted", "#94a3b8"),
		)
		placeholder._notification_placeholder = True
		placeholder.pack(anchor="w", padx=20, pady=20)
		return

	notes = users.get(_ui_state.current_user, {}).get("notifications", [])
	if not notes:
		_notification_list_component.update([])
		# Clear components for empty state
		for child in list_frame.winfo_children():
			child.destroy()
		placeholder = ctk.CTkLabel(
			list_frame,
			text="No notifications yet.",
			text_color=_palette.get("muted", "#94a3b8"),
		)
		placeholder._notification_placeholder = True
		placeholder.pack(anchor="w", padx=20, pady=20)
		return
	
	_clear_placeholders()
	# Use component-based update - only changed notifications re-render
	_notification_list_component.update(notes)


def _handle_follow_from_notification(username: str) -> None:
	"""Handle follow-back button from notifications component."""
	if not username:
		return
	_handle_follow(username)
	_refresh_notifications_ui()


def _render_dm_sidebar() -> None:
	global _dm_sidebar_dirty
	sidebar: ctk.CTkScrollableFrame = _dm_widgets.get("sidebar")
	if not sidebar:
		return

	render_dm_sidebar(
		dm_following_list=sidebar,
		palette=_palette,
		current_user=_ui_state.current_user,
		users=users,
		group_chats=group_chats,
		active_dm_user=_ui_state.active_dm_user,
		active_conversation_id=_ui_state.active_dm_conversation,
		open_dm_with=_open_dm_with,
		open_group_chat=_open_group_chat,
		create_group_chat=_open_create_group_modal,
	)
	_dm_sidebar_dirty = False


def _render_dm() -> None:
	global _dm_sidebar_dirty, _dm_last_rendered_conversation
	thread: ctk.CTkScrollableFrame = _dm_widgets.get("thread")
	header: ctk.CTkLabel = _dm_widgets.get("header")
	entry: ctk.CTkEntry = _dm_widgets.get("entry")
	if not thread or not header or not entry:
		return
	send_btn: Optional[ctk.CTkButton] = _dm_widgets.get("send")
	attach_btn: Optional[ctk.CTkButton] = _dm_widgets.get("attach_button")
	info_card: Optional[ctk.CTkFrame] = _dm_widgets.get("info_card")
	info_title: Optional[ctk.CTkLabel] = _dm_widgets.get("info_title")
	info_members: Optional[ctk.CTkLabel] = _dm_widgets.get("info_members")
	owner_label: Optional[ctk.CTkLabel] = _dm_widgets.get("owner_label")
	owner_btn: Optional[ctk.CTkButton] = _dm_widgets.get("owner_button")
	leave_btn: Optional[ctk.CTkButton] = _dm_widgets.get("leave_button")
	signed_in = bool(_ui_state.current_user)
	target_conversation = _ui_state.active_dm_conversation
	if _dm_sidebar_dirty or _dm_last_rendered_conversation != target_conversation:
		_render_dm_sidebar()
		_dm_last_rendered_conversation = target_conversation

	meta = render_dm(
		dm_header=header,
		dm_thread=thread,
		palette=_palette,
		current_user=_ui_state.current_user,
		active_dm_user=_ui_state.active_dm_user,
		active_conversation_id=_ui_state.active_dm_conversation,
		users=users,
		messages=messages,
		group_chats=group_chats,
		load_profile_avatar=lambda user, size: load_profile_avatar(
			user,
			size,
			users=users,
			base_dir=BASE_DIR,
			default_profile_pic=DEFAULT_PROFILE_PIC,
			cache=_profile_avatar_cache,
		),
		open_profile=_open_profile,
		load_image_for_tk=_load_image_for_tk,
		open_image=_open_image,
		open_attachment=_open_attachment,
		render_inline_video=_render_inline_video,
		invite_token_parser=_discover_invite_tokens,
		invite_widget_factory=_create_invite_widget,
		sidebar_renderer=None,
		on_toggle_reaction=_handle_toggle_dm_reaction,
		reaction_emojis=MESSAGE_REACTIONS,
	)
	if meta.get("signature") is not None:
		_view_signatures["dm"] = meta["signature"]
	conversation_id = meta.get("conversation_id")
	can_send = bool(meta.get("can_send")) and signed_in
	if meta.get("conversation_type") == "dm":
		participants = [p for p in meta.get("participants", []) if p != _ui_state.current_user]
		partner = participants[0] if participants else None
		if partner:
			_ui_state.active_dm_user = partner
	elif meta.get("conversation_type") == "group":
		_ui_state.active_dm_user = None
	if not can_send:
		_dm_draft_attachments.clear()
	entry.configure(state="normal")
	entry.delete(0, tk.END)
	entry_state = "normal" if can_send else "disabled"
	entry.configure(state=entry_state)
	if send_btn:
		send_btn.configure(state="normal" if can_send else "disabled")
	if attach_btn:
		attach_btn.configure(state="normal" if can_send else "disabled")

	thread_messages = meta.get("messages") if isinstance(meta.get("messages"), list) else []
	if meta.get("assigned_message_ids"):
		persist()
	_mark_messages_seen(conversation_id, thread_messages)
	_simulate_partner_typing(meta)
	_refresh_typing_indicator(conversation_id)

	announcement_label: Optional[ctk.CTkLabel] = _dm_widgets.get("announcement_label")
	announcement_btn: Optional[ctk.CTkButton] = _dm_widgets.get("announcement_button")
	copy_invite_btn: Optional[ctk.CTkButton] = _dm_widgets.get("copy_invite_button")
	invite_value: Optional[ctk.CTkLabel] = _dm_widgets.get("invite_label")
	regen_invite_btn: Optional[ctk.CTkButton] = _dm_widgets.get("regen_invite_button")

	if info_card and info_title and info_members and leave_btn and announcement_label and invite_value:
		info_card.configure(fg_color=_palette.get("surface", "#111b2e"))
		info_title.configure(text_color=_palette.get("text", "#e2e8f0"))
		info_members.configure(text_color=_palette.get("muted", "#94a3b8"))
		leave_btn.configure(
			fg_color=_palette.get("danger", "#ef4444"),
			hover_color=_palette.get("danger_hover", "#dc2626"),
			text_color=_palette.get("text_on_danger", "white"),
		)
		if meta.get("conversation_type") == "group" and meta.get("group_chat"):
			chat = meta["group_chat"]
			name = chat.get("name") or "Group chat"
			members = chat.get("members", [])
			owner = chat.get("owner")
			labels: list[str] = []
			for member in members:
				label = f"@{member}"
				if owner and member == owner:
					label += " (owner)"
				if member == _ui_state.current_user:
					label += " (you)"
				labels.append(label)
			member_list = ", ".join(labels) if labels else "No members"
			info_title.configure(text=name)
			info_members.configure(text=f"Members ({len(members)}): {member_list}")
			leave_btn.configure(state="normal" if can_send else "disabled")
			if owner_label:
				owner_label.configure(text=f"Owner: @{owner}" if owner else "Owner: —", text_color=_palette.get("muted", "#94a3b8"))
			if owner_btn:
				can_transfer = bool(owner and _ui_state.current_user == owner and len(members) > 1)
				owner_btn.configure(state="normal" if can_transfer else "disabled")
			rename_btn = _dm_widgets.get("rename_button")
			is_owner = owner and _ui_state.current_user == owner
			if isinstance(rename_btn, ctk.CTkButton):
				rename_btn.configure(state="normal" if is_owner else "disabled")
			if announcement_btn:
				announcement_btn.configure(state="normal" if is_owner else "disabled")
			if regen_invite_btn:
				regen_invite_btn.configure(state="normal" if is_owner else "disabled")
			announcement_text = chat.get("announcement") or "No announcement set."
			announcement_label.configure(text=announcement_text)
			token, changed = _ensure_group_invite_token(chat)
			if changed:
				persist()
			invite_text = _build_group_invite_link(token)
			invite_value.configure(text=invite_text)
			if copy_invite_btn:
				copy_invite_btn.configure(state="normal")
			info_card.grid()
		else:
			info_card.grid_remove()
			if owner_btn:
				owner_btn.configure(state="disabled")
			rename_btn = _dm_widgets.get("rename_button")
			if isinstance(rename_btn, ctk.CTkButton):
				rename_btn.configure(state="disabled")
			if announcement_btn:
				announcement_btn.configure(state="disabled")
			if copy_invite_btn:
				copy_invite_btn.configure(state="disabled")
			if regen_invite_btn:
				regen_invite_btn.configure(state="disabled")
			if owner_label:
				owner_label.configure(text="Owner: —", text_color=_palette.get("muted", "#94a3b8"))

	_ui_state.active_dm_conversation = conversation_id
	_refresh_dm_attachments()


def _render_inspected_profile() -> None:
	header: ctk.CTkLabel = _inspect_widgets.get("header")
	info = _inspect_widgets.get("info")
	posts_frame: ctk.CTkScrollableFrame = _inspect_widgets.get("posts")
	follow_btn: ctk.CTkButton = _inspect_widgets.get("follow_btn")
	message_btn: ctk.CTkButton = _inspect_widgets.get("message_btn")
	avatar_panel = _inspect_widgets.get("avatar_panel")
	avatar_label: tk.Label = _inspect_widgets.get("avatar_label")
	mutual_card = _inspect_widgets.get("mutual_card")
	mutual_list = _inspect_widgets.get("mutual_list")
	inspect_stats_labels: dict[str, ctk.CTkLabel] = _inspect_widgets.get("stats_labels") or {}
	text_color = _palette.get("text", "#e2e8f0")
	muted_color = _palette.get("muted", "#94a3b8")
	if not header or not info or not posts_frame or not follow_btn or not message_btn:
		return

	def _post_renderer(idx: int, post: dict) -> None:
		render_post_card(
			container=posts_frame,
			idx=idx,
			post=post,
			palette=_palette,
			state=_ui_state.feed_state,
			callbacks=FeedCallbacks(
				open_profile=_open_profile,
				toggle_post_reaction=_handle_toggle_post_reaction,
				toggle_replies=_handle_toggle_replies,
				open_reply_box=_handle_open_reply_box,
				start_edit=_handle_start_edit,
				cancel_edit=_handle_cancel_edit,
				apply_edit=_handle_apply_edit,
				delete_post=_handle_delete_post,
				start_reply_edit=_handle_start_reply_edit,
				cancel_reply_edit=_handle_cancel_reply_edit,
				apply_reply_edit=_handle_apply_reply_edit,
				delete_reply=_handle_delete_reply,
				submit_reply=_handle_submit_reply,
				create_reply_toolbar=_create_reply_toolbar,
				open_attachment=_open_attachment,
				render_inline_video=_render_inline_video,
				get_reaction_icon=lambda kind, size: _ensure_reaction_icon(kind, size=size),
			),
			load_profile_avatar=_load_profile_avatar,
			load_image_for_tk=_load_image_for_tk,
			open_image=_open_image,
		)

	render_inspected_profile(
		inspected_user=_ui_state.inspected_user,
		current_user=_ui_state.current_user,
		users=users,
		posts=posts,
		palette=_palette,
		total_likes_for=total_likes_for,
		inspect_header=header,
		inspect_info=info,
		inspect_posts=posts_frame,
		inspect_follow_btn=follow_btn,
		inspect_message_btn=message_btn,
		inspect_stats_labels=inspect_stats_labels,
		post_renderer=_post_renderer,
		open_dm_with=_open_dm_with,
		follow_callback=_handle_follow,
		unfollow_callback=_handle_unfollow,
	)

	if mutual_card and mutual_list:
		for child in mutual_list.winfo_children():
			child.destroy()
		viewer = _ui_state.current_user
		target = _ui_state.inspected_user
		if viewer and target and viewer != target:
			mutuals = _compute_mutual_followers(viewer, target)
			mutual_card.grid()
			if mutuals:
				for handle in mutuals:
					item = ctk.CTkFrame(mutual_list, fg_color=_palette.get("surface", "#111b2e"), corner_radius=8)
					item.grid(sticky="we", padx=0, pady=(0, 6))
					item.grid_columnconfigure(0, weight=1)
					handle_lbl = ctk.CTkLabel(
						item,
						text=f"@{handle}",
						text_color=text_color,
						font=ctk.CTkFont(size=12, weight="bold"),
						anchor="w",
					)
					handle_lbl.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 0))
					handle_lbl.configure(cursor="hand2")
					handle_lbl.bind("<Button-1>", lambda _event, user=handle: _open_profile(user))
					preview = _ellipsize_text(users.get(handle, {}).get("bio", ""), 80)
					if preview:
						ctk.CTkLabel(
							item,
							text=preview,
							text_color=muted_color,
							anchor="w",
							justify="left",
							wraplength=220,
							font=ctk.CTkFont(size=11),
						).grid(row=1, column=0, sticky="w", padx=12, pady=(2, 10))
					else:
						ctk.CTkLabel(
							item,
							text="No bio yet",
							text_color=muted_color,
							anchor="w",
							font=ctk.CTkFont(size=11),
						).grid(row=1, column=0, sticky="w", padx=12, pady=(2, 10))
			else:
				ctk.CTkLabel(
					mutual_list,
					text="No mutual followers yet.",
					text_color=muted_color,
					anchor="w",
				).grid(sticky="w", padx=12, pady=(8, 10))
		elif viewer:
			mutual_card.grid()
			ctk.CTkLabel(
				mutual_list,
				text="Mutual followers appear when you view other profiles.",
				text_color=muted_color,
				anchor="w",
				justify="left",
			).grid(sticky="w", padx=12, pady=(8, 10))
		else:
			mutual_card.grid()
			ctk.CTkLabel(
				mutual_list,
				text="Sign in to discover mutual followers.",
				text_color=muted_color,
				anchor="w",
			).grid(sticky="w", padx=12, pady=(8, 10))

	if avatar_panel and avatar_label:
		user = _ui_state.inspected_user
		if user and user in users:
			avatar = _load_profile_avatar(user, 128)
			if avatar:
				avatar_label.configure(image=avatar, text="")
				avatar_label.image = avatar  # type: ignore[attr-defined]
			else:
				avatar_label.configure(image="", text="No photo")
				avatar_label.image = None  # type: ignore[attr-defined]
			avatar_panel.grid()
		else:
			avatar_label.configure(image="", text="")
			avatar_label.image = None  # type: ignore[attr-defined]
			avatar_panel.grid_remove()


def _handle_submit_post() -> None:
	if not require_login("post"):
		return
	post_text: ctk.CTkTextbox = _home_widgets.get("post_text")
	if not post_text:
		return
	content = post_text.get("1.0", "end").strip()
	if not content:
		messagebox.showwarning("Empty post", "Your post cannot be empty!")
		return
	attachments = [dict(att) for att in _post_attachments]
	media_paths: set[str] = set()
	for att in attachments:
		if not isinstance(att, dict):
			continue
		path_value = att.get("path")
		if isinstance(path_value, str):
			media_paths.add(path_value)
		thumb_value = att.get("thumbnail")
		if isinstance(thumb_value, str):
			media_paths.add(thumb_value)
	media_sync_failed = False
	for media_path in media_paths:
		if not upload_media_asset(media_path):
			media_sync_failed = True
	post_id = uuid4().hex
	post_record = {
		"id": post_id,
		"author": _ui_state.current_user,
		"content": content,
		"created_at": now_ts(),
		"edited": False,
		"edited_at": None,
		"replies": [],
		"liked_by": [],
		"disliked_by": [],
		"likes": 0,
		"dislikes": 0,
		"attachments": attachments,
	}
	posts.append(post_record)
	resolved_mentions, missing_mentions = _split_mentions(content, author=_ui_state.current_user)
	if missing_mentions:
		messagebox.showwarning(
			"Mentions not found",
			"These usernames were not recognized: " + ", ".join(f"@{name}" for name in sorted(missing_mentions)),
		)
	mentions_sent = False
	if resolved_mentions:
		mentions_sent = notify_mentions(
			_ui_state.current_user,
			content,
			"a post",
			mentions=resolved_mentions,
			meta_factory=lambda _user: {
				"type": "mention",
				"resource": "post",
				"post_id": post_id,
				"from": _ui_state.current_user,
			},
		)
	followers_notified = notify_followers(
		_ui_state.current_user,
		message=f"@{_ui_state.current_user} shared a new post",
		meta_factory=lambda _user: {
			"type": "post_publish",
			"post_id": post_id,
			"from": _ui_state.current_user,
		},
	)
	if mentions_sent or followers_notified:
		trigger_immediate_sync("notifications")
		_refresh_notifications_ui()

	# Immediate real-time sync for posts
	trigger_immediate_sync("posts")
	_notify_remote_sync_issue("posts", "publish the post")
	if media_sync_failed:
		_notify_remote_sync_issue("media", "upload the post attachments")
	post_text.delete("1.0", "end")
	_post_attachments.clear()
	_refresh_post_attachments()
	_request_render("home")
	if _ui_state.current_user:
		_request_render("profile")
		if _ui_state.inspected_user == _ui_state.current_user:
			_request_render("inspect_profile")


def _handle_delete_post(idx: int) -> None:
	if not require_login("delete posts"):
		return
	if posts[idx].get("author") != _ui_state.current_user:
		messagebox.showerror("Not allowed", "You can only delete your own posts.")
		return
	if not messagebox.askyesno("Delete post", "Are you sure you want to delete this post?"):
		return
	post_record = posts[idx]
	attachments = [dict(att) for att in post_record.get("attachments", []) if isinstance(att, dict)]
	posts.pop(idx)
	persist()
	_notify_remote_sync_issue("posts", "delete the post")
	for att in attachments:
		path = att.get("path")
		if path and not _attachment_in_use(path):
			_delete_media_file(path)
		thumb = att.get("thumbnail")
		if thumb and not _attachment_in_use(thumb):
			_delete_media_file(thumb)
	_request_render("home")
	_request_render("profile")
	if _ui_state.inspected_user == _ui_state.current_user:
		_request_render("inspect_profile")


def _handle_toggle_post_reaction(idx: int, kind: str) -> None:
	toggle_post_reaction(idx, kind)


def _handle_toggle_replies(idx: int) -> None:
	replies = _ui_state.feed_state.expanded_replies
	if idx in replies:
		replies.remove(idx)
	else:
		replies.add(idx)
	_request_render("home")


def _handle_open_reply_box(target: Optional[int]) -> None:
	_ui_state.feed_state.reply_input_target = target
	_request_render("home")


def _handle_start_edit(idx: int) -> None:
	_ui_state.feed_state.editing_post_index = idx
	_ui_state.feed_state.editing_reply_target = None
	_ui_state.feed_state.reply_input_target = None
	_request_render("home")


def _handle_cancel_edit() -> None:
	_ui_state.feed_state.editing_post_index = None
	_request_render("home")


def _handle_apply_edit(idx: int, textbox: ctk.CTkTextbox) -> None:
	content = textbox.get("1.0", "end").strip()
	if not content:
		messagebox.showwarning("Empty", "Post content cannot be empty.")
		return
	post = posts[idx]
	post["content"] = content
	post["edited"] = True
	post["edited_at"] = now_ts()
	persist()
	_ui_state.feed_state.editing_post_index = None
	_request_render("home")
	_request_render("profile")
	if _ui_state.inspected_user == post.get("author"):
		_request_render("inspect_profile")


def _handle_start_reply_edit(post_idx: int, reply_idx: int) -> None:
	_ui_state.feed_state.editing_post_index = None
	_ui_state.feed_state.reply_input_target = None
	_ui_state.feed_state.expanded_replies.add(post_idx)
	_ui_state.feed_state.editing_reply_target = (post_idx, reply_idx)
	_request_render("home")
	if posts[post_idx].get("author") == _ui_state.inspected_user:
		_request_render("inspect_profile")


def _handle_cancel_reply_edit() -> None:
	target = _ui_state.feed_state.editing_reply_target
	_ui_state.feed_state.editing_reply_target = None
	_request_render("home")
	if target and posts[target[0]].get("author") == _ui_state.inspected_user:
		_request_render("inspect_profile")


def _handle_apply_reply_edit(post_idx: int, reply_idx: int, textbox: tk.Text) -> None:
	content = textbox.get("1.0", "end").strip()
	if not content:
		messagebox.showwarning("Empty reply", "Reply cannot be empty.")
		return
	reply = posts[post_idx]["replies"][reply_idx]
	reply["content"] = content
	reply["edited"] = True
	reply["edited_at"] = now_ts()
	persist()
	_ui_state.feed_state.editing_reply_target = None
	_request_render("home")
	if posts[post_idx].get("author") == _ui_state.inspected_user:
		_request_render("inspect_profile")


def _handle_delete_reply(post_idx: int, reply_idx: int) -> None:
	if not require_login("delete replies"):
		return
	reply = posts[post_idx]["replies"][reply_idx]
	if reply.get("author") != _ui_state.current_user:
		messagebox.showerror("Not allowed", "You can only delete your own replies.")
		return
	if not messagebox.askyesno("Delete reply", "Are you sure you want to delete this reply?"):
		return
	posts[post_idx]["replies"].pop(reply_idx)
	persist()
	_request_render("home")
	if posts[post_idx].get("author") == _ui_state.inspected_user:
		_request_render("inspect_profile")


def _handle_submit_reply(post_idx: int, var: tk.StringVar) -> None:
	if not require_login("reply"):
		return
	content = var.get().strip()
	if not content:
		messagebox.showwarning("Empty reply", "Please write something before sending.")
		return
	posts[post_idx].setdefault("replies", []).append(
		{
			"id": uuid4().hex,
			"author": _ui_state.current_user,
			"content": content,
			"created_at": now_ts(),
			"edited": False,
			"edited_at": None,
			"liked_by": [],
			"disliked_by": [],
			"likes": 0,
			"dislikes": 0,
			"attachments": [],
		}
	)
	reply_record = posts[post_idx]["replies"][-1]
	post_record = posts[post_idx]
	post_id = str(post_record.get("id") or "")
	resolved_mentions, missing_mentions = _split_mentions(content, author=_ui_state.current_user)
	if missing_mentions:
		messagebox.showwarning(
			"Mentions not found",
			"These usernames were not recognized: " + ", ".join(f"@{name}" for name in sorted(missing_mentions)),
		)
	mentions_delivered = False
	if resolved_mentions:
		reply_id = reply_record.get("id") or ""
		mentions_delivered = notify_mentions(
			_ui_state.current_user,
			content,
			"a reply",
			mentions=resolved_mentions,
			meta_factory=lambda _user: {
				"type": "mention",
				"resource": "reply",
				"post_id": post_id,
				"reply_id": reply_id,
				"from": _ui_state.current_user,
			},
		)
	if mentions_delivered:
		trigger_immediate_sync("notifications")
		_refresh_notifications_ui()
	persist()
	var.set("")
	_ui_state.feed_state.reply_input_target = None
	_ui_state.feed_state.expanded_replies.add(post_idx)
	_request_render("home")
	if posts[post_idx].get("author") == _ui_state.inspected_user:
		_request_render("inspect_profile")


def _create_reply_toolbar(_container: ctk.CTkFrame, _post_idx: int, _reply_var: tk.StringVar) -> None:
	# Placeholder for future toolbar features (emoji picker, attachments, etc.).
	return


def _handle_clear_notifications() -> None:
	if not require_login("clear notifications"):
		return
	if _ui_state.current_user in users:
		users[_ui_state.current_user]["notifications"] = []
		persist()
		_request_render("notifications")
		_update_nav_controls()


def _handle_change_profile_picture() -> None:
	def _update_after_pic_change() -> None:
		_request_render("profile")
		_request_render("home")

	def _copy_profile_pic_and_sync(path: Optional[str]) -> Optional[str]:
		rel = copy_image_to_profile_pics(
			path,
			base_dir=BASE_DIR,
			profile_pics_dir=PROFILE_PICS_DIR,
		)
		if rel and not upload_media_asset(rel):
			_notify_remote_sync_issue("media", "upload the profile picture")
		return rel

	change_profile_picture(
		current_user=_ui_state.current_user,
		require_login=require_login,
		copy_image_to_profile_pics=_copy_profile_pic_and_sync,
		users=users,
		base_dir=BASE_DIR,
		profile_pics_dir=PROFILE_PICS_DIR,
		default_profile_pic=DEFAULT_PROFILE_PIC,
		invalidate_avatar=lambda username: invalidate_profile_avatar(_profile_avatar_cache, username),
		persist=persist,
		update_display=_update_after_pic_change,
		render_dm=lambda: _request_render("dm"),
		render_inspected_profile=lambda: _request_render("inspect_profile"),
	)
def _handle_save_profile_details() -> None:
	if not require_login("update your profile details"):
		return
	user = _ui_state.current_user
	if not user:
		return
	bio_input: Optional[ctk.CTkTextbox] = _profile_widgets.get("bio_input")
	location_entry: Optional[ctk.CTkEntry] = _profile_widgets.get("location_entry")
	website_entry: Optional[ctk.CTkEntry] = _profile_widgets.get("website_entry")
	status_label: Optional[ctk.CTkLabel] = _profile_widgets.get("details_status")
	if not bio_input or not location_entry or not website_entry:
		return
	bio_value = bio_input.get("1.0", "end").strip()
	location_value = location_entry.get().strip()
	website_value = website_entry.get().strip()

	bio_value = bio_value[:300]
	location_value = location_value[:120]
	website_value = website_value[:200]
	if website_value and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", website_value):
		website_value = f"https://{website_value}"

	record = users.setdefault(user, {})
	record["bio"] = bio_value
	record["location"] = location_value
	record["website"] = website_value
	record.setdefault("last_active_at", now_ts())
	if status_label:
		status_label.configure(text="Profile updated.", text_color=_palette.get("muted", "#94a3b8"))
	_touch_current_user_activity(force=True)
	_request_render("profile")
	if _ui_state.inspected_user == user:
		_request_render("inspect_profile")
	bio_input.delete("1.0", "end")
	bio_input.insert("1.0", bio_value)
	location_entry.delete(0, tk.END)
	location_entry.insert(0, location_value)
	website_entry.delete(0, tk.END)
	if website_value:
		website_entry.insert(0, website_value)
def _open_profile(username: str) -> None:
	_ui_state.inspected_user = username
	_request_render("inspect_profile")
	if _show_frame_cb:
		_show_frame_cb("inspect_profile")


def _handle_follow(username: str) -> None:
	if not require_login("follow users"):
		return
	if username == _ui_state.current_user:
		return
	current = _ui_state.current_user
	if not current:
		return
	following = users.setdefault(current, {}).setdefault("following", [])
	if username not in following:
		following.append(username)
	followers = users.setdefault(username, {}).setdefault("followers", [])
	if current not in followers:
		followers.append(current)
		notification_delivered = push_notification(
			username,
			f"@{current} started following you",
			meta={"type": "follow", "from": current},
		)
		if notification_delivered:
			trigger_immediate_sync("notifications")
			_refresh_notifications_ui()
	
	# Immediate real-time sync for follow changes
	trigger_immediate_sync("users")
	_mark_dm_sidebar_dirty()
	_mark_dirty("search")
	_request_render("dm")
	_request_render("inspect_profile")
	if current:
		_request_render("profile")
	if _ui_state.active_view == "search":
		_request_render("search")


def _open_group_chat(chat_id: str) -> None:
	if not require_login("view group chats"):
		return
	user = _ui_state.current_user
	chat = _find_group_chat(chat_id)
	if not chat or not user or user not in chat.get("members", []):
		messagebox.showwarning("Group chat", "You are no longer a member of that group chat.")
		_select_default_dm_conversation()
		_request_render("dm")
		return
	_set_active_dm_conversation(chat_id, None)
	_request_render("dm")
	if _show_frame_cb:
		_show_frame_cb("dm")


def _handle_edit_group_name() -> None:
	if not require_login("rename group chats"):
		return
	chat = _get_active_group_chat()
	if not chat:
		messagebox.showinfo("Group chat", "Select a group chat first.")
		return
	owner = chat.get("owner")
	if _ui_state.current_user != owner:
		messagebox.showwarning("Group chat", "Only the owner can rename this group chat.")
		return
	current_name = chat.get("name") or ""
	anchor = _get_after_anchor()
	new_name = simpledialog.askstring(
		"Rename group",
		"Enter a new name for the group chat:",
		initialvalue=current_name,
		parent=anchor,
	)
	if new_name is None:
		return
	cleaned = new_name.strip()
	if not cleaned:
		messagebox.showwarning("Group chat", "Group name cannot be empty.")
		return
	if cleaned == current_name:
		return
	chat["name"] = cleaned
	chat["updated_at"] = now_ts()
	persist()
	trigger_immediate_sync("group_chats")
	_mark_dm_sidebar_dirty()
	_request_render("dm")


def _handle_transfer_group_owner() -> None:
	if not require_login("transfer ownership"):
		return
	chat = _get_active_group_chat()
	if not chat:
		messagebox.showinfo("Group chat", "Select a group chat first.")
		return
	owner = chat.get("owner")
	if _ui_state.current_user != owner:
		messagebox.showwarning("Group chat", "Only the current owner can transfer ownership.")
		return
	members = [member for member in chat.get("members", []) if member != owner]
	if not members:
		messagebox.showinfo("Group chat", "No other members to transfer ownership to.")
		return
	member_list = "\n".join(f"@{name}" for name in members)
	anchor = _get_after_anchor()
	selection = simpledialog.askstring(
		"Transfer ownership",
		f"Enter the username of the new owner:\n\n{member_list}",
		parent=anchor,
	)
	if selection is None:
		return
	cleaned = selection.strip().lstrip("@")
	if not cleaned:
		messagebox.showwarning("Group chat", "Provide a username to transfer ownership.")
		return
	lookup = {member.lower(): member for member in members}
	chosen = lookup.get(cleaned.lower())
	if not chosen:
		messagebox.showerror("Group chat", "That user is not a member of this group chat.")
		return
	if not messagebox.askyesno("Transfer ownership", f"Transfer group ownership to @{chosen}?", parent=anchor):
		return
	chat["owner"] = chosen
	chat["updated_at"] = now_ts()
	persist()
	trigger_immediate_sync("group_chats")
	_mark_dm_sidebar_dirty()
	_request_render("dm")
	notification_delivered = push_notification(
		chosen,
		f"You are now the owner of {chat.get('name') or 'your group chat'}",
		meta={"type": "group_dm", "group": chat.get("id"), "from": _ui_state.current_user},
	)
	if notification_delivered:
		trigger_immediate_sync("notifications")
	_refresh_notifications_ui()


def _handle_edit_group_announcement() -> None:
	if not require_login("update announcements"):
		return
	chat = _get_active_group_chat()
	if not chat:
		messagebox.showinfo("Group chat", "Select a group chat first.")
		return
	owner = chat.get("owner")
	if _ui_state.current_user != owner:
		messagebox.showwarning("Group chat", "Only the owner can update the announcement.")
		return
	anchor = _get_after_anchor()
	current_value = chat.get("announcement") or ""
	value = simpledialog.askstring(
		"Group announcement",
		"Update the announcement message (leave blank to clear):",
		initialvalue=current_value,
		parent=anchor,
	)
	if value is None:
		return
	cleaned = value.strip()
	chat["announcement"] = cleaned
	chat["updated_at"] = now_ts()
	persist()
	trigger_immediate_sync("group_chats")
	_request_render("dm")


def _handle_copy_group_invite() -> None:
	if not require_login("copy invite links"):
		return
	chat = _get_active_group_chat()
	if not chat:
		messagebox.showinfo("Group chat", "Select a group chat first.")
		return
	token, changed = _ensure_group_invite_token(chat)
	invite_link = _build_group_invite_link(token)
	if changed:
		persist()
		trigger_immediate_sync("group_chats")
	anchor = _get_after_anchor()
	if anchor:
		try:
			root = anchor.winfo_toplevel()
			root.clipboard_clear()
			root.clipboard_append(invite_link)
		except Exception:
			pass
	messagebox.showinfo("Invite link", f"Invite link copied to clipboard:\n{invite_link}")
	_request_render("dm")


def _handle_regenerate_group_invite() -> None:
	if not require_login("regenerate invites"):
		return
	chat = _get_active_group_chat()
	if not chat:
		messagebox.showinfo("Group chat", "Select a group chat first.")
		return
	owner = chat.get("owner")
	if _ui_state.current_user != owner:
		messagebox.showwarning("Group chat", "Only the owner can regenerate the invite link.")
		return
	if not messagebox.askyesno("Regenerate invite", "Create a new invite link? Current link will stop working."):
		return
	new_token = _generate_group_invite_token()
	chat["invite_token"] = new_token
	chat["invite_updated_at"] = now_ts()
	chat["updated_at"] = now_ts()
	persist()
	trigger_immediate_sync("group_chats")
	_request_render("dm")


def _dismiss_group_modal() -> None:
	window = _group_modal_widgets.get("window")
	if window and window.winfo_exists():
		try:
			window.grab_release()
		except Exception:
			pass
		window.destroy()
	_group_modal_widgets.clear()


def _handle_create_group_chat() -> None:
	if not _ui_state.current_user:
		return
	name_entry: Optional[ctk.CTkEntry] = _group_modal_widgets.get("name_entry")
	status: Optional[ctk.CTkLabel] = _group_modal_widgets.get("status_label")
	member_vars: dict[str, tk.BooleanVar] = _group_modal_widgets.get("member_vars", {})  # type: ignore[assignment]
	if not name_entry or not member_vars:
		return
	name = name_entry.get().strip()
	selected = [username for username, var in member_vars.items() if var.get()]
	if not selected:
		if status:
			status.configure(
				text="Select at least one person to add to the group.",
				text_color=_palette.get("danger", "#ef4444"),
			)
		return
	if status:
		status.configure(text="", text_color=_palette.get("muted", "#94a3b8"))
	group_id = f"group:{uuid4().hex}"
	timestamp = now_ts()
	members = list(dict.fromkeys([_ui_state.current_user, *selected]))
	group_name = name or "Group chat"
	group_chat = {
		"id": group_id,
		"name": group_name,
		"owner": _ui_state.current_user,
		"members": members,
		"messages": [],
		"created_at": timestamp,
		"updated_at": timestamp,
	}
	group_chats.append(group_chat)
	notifications_sent = False
	for member in selected:
		notifications_sent = push_notification(
			member,
			f"@{_ui_state.current_user} added you to {group_name}",
			meta={"type": "group_dm", "group": group_id, "from": _ui_state.current_user},
		) or notifications_sent
	
	# Immediate real-time sync for group chats
	trigger_immediate_sync("group_chats")
	if notifications_sent:
		trigger_immediate_sync("notifications")
	_mark_dm_sidebar_dirty()
	_dismiss_group_modal()
	_set_active_dm_conversation(group_id, None)
	_request_render("dm")
	_refresh_notifications_ui()
	if _show_frame_cb:
		_show_frame_cb("dm")


def _handle_leave_group_chat() -> None:
	if not require_login("leave group chats"):
		return
	conversation_id = _ui_state.active_dm_conversation or ""
	if not conversation_id.startswith("group:"):
		messagebox.showinfo("Group chat", "Select a group chat to leave.")
		return
	chat = _find_group_chat(conversation_id)
	user = _ui_state.current_user
	if not chat or not user or user not in chat.get("members", []):
		messagebox.showwarning("Group chat", "You are no longer a member of that group chat.")
		_select_default_dm_conversation()
		_request_render("dm")
		return
	chat_name = chat.get("name") or "this group chat"
	if not messagebox.askyesno("Leave group", f"Leave {chat_name}?"):
		return
	members = list(chat.get("members", []))
	if user in members:
		members.remove(user)
	chat_owner = chat.get("owner")
	notifications_sent = False
	if not members:
		group_chats.remove(chat)
	else:
		chat["members"] = members
		if chat_owner == user:
			chat["owner"] = members[0]
		chat["updated_at"] = now_ts()
		for member in members:
			notifications_sent = push_notification(
				member,
				f"@{user} left {chat_name}",
				meta={"type": "group_dm", "group": conversation_id, "from": user},
			) or notifications_sent
	persist()
	trigger_immediate_sync("group_chats")
	if notifications_sent:
		trigger_immediate_sync("notifications")
	_mark_dm_sidebar_dirty()
	_set_active_dm_conversation(None, None)
	_select_default_dm_conversation()
	_request_render("dm")
	_refresh_notifications_ui()


def _open_create_group_modal() -> None:
	if not require_login("create group chats"):
		return
	user = _ui_state.current_user
	if not user:
		return
	following = sorted(set(users.get(user, {}).get("following", [])), key=str.lower)
	if not following:
		messagebox.showinfo("No contacts", "Follow people to create a group chat with them.")
		return
	parent = _dm_widgets.get("frame") or _frames.get("dm")
	if not parent:
		return
	_dismiss_group_modal()
	window = ctk.CTkToplevel(parent)
	window.title("Create group chat")
	window.geometry("420x520")
	try:
		window.transient(parent.winfo_toplevel())
	except Exception:
		pass
	window.grab_set()
	window.protocol("WM_DELETE_WINDOW", _dismiss_group_modal)
	window.focus_force()

	header = ctk.CTkLabel(
		window,
		text="Add members to your group chat.",
		text_color=_palette.get("text", "#e2e8f0"),
		font=ctk.CTkFont(size=16, weight="bold"),
	)
	header.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))

	name_entry = ctk.CTkEntry(window, placeholder_text="Group name (optional)")
	name_entry.grid(row=1, column=0, sticky="we", padx=20, pady=(0, 12))
	name_entry.focus_set()

	members_frame = ctk.CTkScrollableFrame(window, corner_radius=10)
	members_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 12))
	members_frame.grid_columnconfigure(0, weight=1)
	window.grid_rowconfigure(2, weight=1)
	window.grid_columnconfigure(0, weight=1)

	member_vars: dict[str, tk.BooleanVar] = {}
	for idx, username in enumerate(following):
		var = tk.BooleanVar(value=False)
		chk = ctk.CTkCheckBox(
			members_frame,
			text=f"@{username}",
			variable=var,
			text_color=_palette.get("text", "#e2e8f0"),
		)
		chk.grid(row=idx, column=0, sticky="w", padx=12, pady=4)
		member_vars[username] = var

	status = ctk.CTkLabel(
		window,
		text="Select at least one person.",
		text_color=_palette.get("muted", "#94a3b8"),
	)
	status.grid(row=3, column=0, sticky="w", padx=20, pady=(0, 8))

	controls = ctk.CTkFrame(window, fg_color="transparent")
	controls.grid(row=4, column=0, sticky="e", padx=20, pady=(0, 20))
	create_btn = ctk.CTkButton(
		controls,
		text="Create",
		fg_color=_palette.get("accent", "#4c8dff"),
		hover_color=_palette.get("accent_hover", "#3b6dd6"),
		command=_handle_create_group_chat,
	)
	create_btn.grid(row=0, column=1, padx=(8, 0))
	ctk.CTkButton(
		controls,
		text="Cancel",
		fg_color="transparent",
		border_width=1,
		border_color=_palette.get("muted", "#94a3b8"),
		text_color=_palette.get("muted", "#94a3b8"),
		hover_color=_palette.get("surface", "#111b2e"),
		command=_dismiss_group_modal,
	).grid(row=0, column=0)

	_group_modal_widgets.update(
		{
			"window": window,
			"name_entry": name_entry,
			"status_label": status,
			"member_vars": member_vars,
			"create_button": create_btn,
		}
	)

	if username not in users[_ui_state.current_user]["following"]:
		users[_ui_state.current_user]["following"].append(username)
		users.setdefault(username, {}).setdefault("followers", [])
		if _ui_state.current_user not in users[username]["followers"]:
			users[username]["followers"].append(_ui_state.current_user)
			notification_delivered = push_notification(
				username,
				f"@{_ui_state.current_user} started following you",
				meta={"type": "follow", "from": _ui_state.current_user},
			)
			if notification_delivered:
				trigger_immediate_sync("notifications")
				_refresh_notifications_ui()
		persist()
	_request_render("dm")
	_request_render("notifications")
	_request_render("inspect_profile")
	if _ui_state.current_user:
		_request_render("profile")


def _handle_unfollow(username: str) -> None:
	if not require_login("unfollow users"):
		return
	if username == _ui_state.current_user:
		return
	followers = users.get(username, {}).setdefault("followers", [])
	following = users.get(_ui_state.current_user, {}).setdefault("following", [])
	if username in following:
		following.remove(username)
	if _ui_state.current_user in followers:
		followers.remove(_ui_state.current_user)
	persist()
	_mark_dm_sidebar_dirty()
	_mark_dirty("search")
	_request_render("dm")
	_request_render("notifications")
	_request_render("inspect_profile")
	_request_render("profile")
	if _ui_state.active_view == "search":
		_request_render("search")


def _open_dm_with(username: str) -> None:
	if not require_login("send direct messages"):
		return
	if username == _ui_state.current_user:
		messagebox.showinfo("Direct message", "You cannot message yourself.")
		return
	conversation_id = convo_id(_ui_state.current_user, username)
	_set_active_dm_conversation(conversation_id, username)
	_request_render("dm")
	if _show_frame_cb:
		_show_frame_cb("dm")


def _open_dm_from_notification(username: str) -> None:
	if not require_login("view messages"):
		return
	if username == _ui_state.current_user:
		return
	conversation_id = convo_id(_ui_state.current_user, username)
	_set_active_dm_conversation(conversation_id, username)
	_request_render("dm")
	if _show_frame_cb:
		_show_frame_cb("dm")


def _open_group_from_notification(chat_id: str) -> None:
	if not chat_id:
		return
	_open_group_chat(chat_id)


def _handle_send_dm() -> None:
	if not _ui_state.current_user:
		return
	entry: ctk.CTkEntry = _dm_widgets.get("entry")
	if not entry:
		return
	content = entry.get().strip()
	attachments = [dict(att) for att in _dm_draft_attachments]
	media_paths: set[str] = set()
	for att in attachments:
		if not isinstance(att, dict):
			continue
		path_value = att.get("path")
		if isinstance(path_value, str):
			media_paths.add(path_value)
		thumb_value = att.get("thumbnail")
		if isinstance(thumb_value, str):
			media_paths.add(thumb_value)
	media_sync_failed = False
	for media_path in media_paths:
		if not upload_media_asset(media_path):
			media_sync_failed = True
	if not content and not attachments:
		messagebox.showwarning("Empty message", "Write something or attach files before sending.")
		return
	conversation_id = _ui_state.active_dm_conversation or ""
	current_user = _ui_state.current_user
	message_record = {
		"sender": current_user,
		"content": content,
		"time": now_ts(),
		"attachments": attachments,
		"id": uuid4().hex,
		"reactions": {},
		"seen_by": [current_user],
	}
	notifications_sent = False
	is_group_message = False
	if conversation_id.startswith("group:"):
		chat = _find_group_chat(conversation_id)
		if not chat or current_user not in chat.get("members", []):
			messagebox.showerror("Unavailable", "You are no longer part of this group chat.")
			_select_default_dm_conversation()
			_request_render("dm")
			return
		chat.setdefault("messages", []).append(message_record)
		chat["updated_at"] = message_record["time"]
		_mark_dm_sidebar_dirty()
		is_group_message = True
		for member in chat.get("members", []):
			if member != current_user:
				notifications_sent = push_notification(
					member,
					f"@{current_user} sent a message in {chat.get('name') or 'your group chat'}",
					meta={"type": "group_dm", "group": conversation_id, "from": current_user},
				) or notifications_sent
	else:
		partner = _ui_state.active_dm_user
		if not partner and conversation_id:
			partner = _derive_conversation_partner(current_user, conversation_id)
		if not partner:
			messagebox.showwarning("Select conversation", "Choose someone to message first.")
			return
		key = convo_id(current_user, partner)
		messages.setdefault(key, []).append(message_record)
		notifications_sent = push_notification(
			partner,
			f"@{current_user} sent you a direct message",
			meta={"type": "dm", "from": current_user},
		) or notifications_sent
		_set_active_dm_conversation(key, partner)
		_mark_dm_sidebar_dirty()

	# Immediate real-time sync for the updated thread
	if is_group_message:
		trigger_immediate_sync("group_chats")
		_notify_remote_sync_issue("group_chats", "deliver the group message")
	else:
		trigger_immediate_sync("messages")
		_notify_remote_sync_issue("messages", "deliver the message")
	if notifications_sent:
		trigger_immediate_sync("notifications")
		_refresh_notifications_ui()
	if media_sync_failed:
		_notify_remote_sync_issue("media", "upload the message attachments")
	entry.delete(0, tk.END)
	_dm_draft_attachments.clear()
	_refresh_dm_attachments()
	_request_render("dm")
	_request_render("notifications")


def _load_profile_avatar(username: str, size: int) -> Optional[tk.PhotoImage]:
	return load_profile_avatar(
		username,
		size,
		users=users,
		base_dir=BASE_DIR,
		default_profile_pic=DEFAULT_PROFILE_PIC,
		cache=_profile_avatar_cache,
	)


def _load_image_for_tk(rel_path: str, max_width: int) -> Optional[tk.PhotoImage]:
	return media_load_image(rel_path, base_dir=BASE_DIR, max_width=max_width)


def _open_image(rel_path: str) -> None:
	open_image(rel_path, base_dir=BASE_DIR)


def _resolve_media_path(rel_path: str) -> str:
	rel_path = (rel_path or "").strip()
	if not rel_path:
		return ""
	if os.path.isabs(rel_path):
		return os.path.normpath(rel_path)
	ensure_media_local(rel_path)
	normalized = rel_path.replace("\\", "/")
	relative = normalized.replace("/", os.sep)
	return os.path.normpath(os.path.join(BASE_DIR, relative))


def _delete_media_file(rel_path: str) -> None:
	abs_path = _resolve_media_path(rel_path)
	if not abs_path or not os.path.exists(abs_path):
		return
	try:
		os.remove(abs_path)
	except OSError:
		pass


def _normalized_rel_path(rel_path: Optional[str]) -> str:
	if not rel_path:
		return ""
	return rel_path.replace("\\", "/").strip()


def _attachment_in_use(rel_path: str) -> bool:
	norm = _normalized_rel_path(rel_path)
	if not norm:
		return False
	for post in posts:
		for att in post.get("attachments", []):
			if isinstance(att, dict) and _normalized_rel_path(att.get("path")) == norm:
				return True
	for entry in scheduled_posts:
		for att in entry.get("attachments", []):
			if isinstance(att, dict) and _normalized_rel_path(att.get("path")) == norm:
				return True
	for story in stories:
		if _normalized_rel_path(story.get("path")) == norm:
			return True
	for video in videos:
		if _normalized_rel_path(video.get("path")) == norm:
			return True
	for convo in messages.values():
		for message in convo:
			for att in message.get("attachments", []):
				if isinstance(att, dict) and _normalized_rel_path(att.get("path")) == norm:
					return True
	for chat in group_chats:
		for msg in chat.get("messages", []) or []:
			for att in msg.get("attachments", []):
				if isinstance(att, dict) and _normalized_rel_path(att.get("path")) == norm:
					return True
	return False


def _make_photo_image(image: "Image.Image", max_width: int, max_height: int) -> Optional[tk.PhotoImage]:  # type: ignore[name-defined]
	if Image is None or ImageTk is None:
		return None
	max_width = max(1, max_width)
	max_height = max(1, max_height)
	width, height = image.size
	scale = min(max_width / width, max_height / height, 1.0)
	if scale <= 0:
		scale = 1.0
	resampling = getattr(Image, "Resampling", None)
	lanczos = getattr(resampling, "LANCZOS", None) if resampling else getattr(Image, "LANCZOS", None)
	fallback = (
		getattr(resampling, "BICUBIC", None) if resampling else getattr(Image, "BICUBIC", None)
	) or getattr(Image, "BILINEAR", None) or getattr(Image, "NEAREST", 0)
	display = image if scale >= 0.999 else image.resize(
		(max(1, int(width * scale)), max(1, int(height * scale))), lanczos or fallback
	)
	return ImageTk.PhotoImage(display)


def _ensure_video_session(rel_path: str) -> dict[str, Any]:
	norm_rel_path = (rel_path or "").replace("\\", "/").strip()
	abs_path = _resolve_media_path(norm_rel_path)
	session = _video_sessions.get(norm_rel_path)
	if not session:
		session = {
			"path": norm_rel_path,
			"abs_path": abs_path,
			"label": None,
			"button": None,
			"controls": None,
			"playing": False,
			"ended": False,
			"delay": 33,
			"reader": None,
			"iterator": None,
			"after_id": None,
			"after_widget": None,
			"frame_duration": None,
			"next_tick": None,
			"display_size": None,
			"target_size": None,
			"preview_pil": None,
			"current_pil": None,
			"current_photo": None,
			"error": None,
			"audio_path": None,
			"audio_tempdir": None,
			"audio_prepared": False,
			"audio_playing": False,
			"audio_error": None,
		}
		_video_sessions[norm_rel_path] = session
	else:
		session["path"] = norm_rel_path
		session["abs_path"] = abs_path
	return session


def _ensure_video_preview(session: dict[str, Any]) -> None:
	if session.get("preview_pil") or session.get("error"):
		return
	if imageio is None or Image is None:
		session["error"] = "Video playback requires Pillow and imageio."
		return
	abs_path = session.get("abs_path")
	if not abs_path or not os.path.exists(abs_path):
		session["error"] = "Video file missing at render time."
		return
	try:
		reader = imageio.get_reader(abs_path)
		frame = reader.get_data(0)
		reader.close()
		session["preview_pil"] = Image.fromarray(frame)
	except Exception as exc:
		session["error"] = f"Preview unavailable: {exc}"


def _display_video_image(session: dict[str, Any], image: Optional["Image.Image"]) -> None:  # type: ignore[name-defined]
	label: Optional[tk.Label] = session.get("label")
	if not label or not label.winfo_exists():
		return
	if image is None:
		label.configure(text="Video preview unavailable", image="")
		label.image = None
		session["current_photo"] = None
		return
	width_hint = label.winfo_width()
	height_hint = label.winfo_height()
	max_width = width_hint if width_hint and width_hint > 10 else 640
	max_height = height_hint if height_hint and height_hint > 10 else 360
	photo = _make_photo_image(image, max_width, max_height)
	if photo is None:
		label.configure(text="Video preview unavailable", image="")
		label.image = None
		session["current_photo"] = None
		return
	label.configure(image=photo, text="")
	label.image = photo  # type: ignore[attr-defined]
	session["current_photo"] = photo
	session["current_pil"] = image
	try:
		session["display_size"] = (photo.width(), photo.height())  # type: ignore[attr-defined]
	except Exception:
		pass


def _get_ffmpeg_executable() -> Optional[str]:
	try:
		from imageio_ffmpeg import get_ffmpeg_exe  # type: ignore
		exe_path = get_ffmpeg_exe()
		if exe_path and os.path.exists(exe_path):
			return exe_path
	except Exception:
		pass
	return shutil.which("ffmpeg")


def _prepare_video_audio(session: dict[str, Any]) -> Optional[str]:
	if os.name != "nt" or winsound is None:
		return None
	if session.get("audio_prepared") and session.get("audio_path") and os.path.exists(session["audio_path"]):
		return session["audio_path"]
	abs_path = session.get("abs_path")
	if not abs_path or not os.path.exists(abs_path):
		return None
	ffmpeg_exe = _get_ffmpeg_executable()
	if not ffmpeg_exe:
		session["audio_error"] = "Audio playback requires ffmpeg."
		return None
	temp_dir = session.get("audio_tempdir")
	if not temp_dir:
		temp_dir = tempfile.mkdtemp(prefix="inline-audio-")
		session["audio_tempdir"] = temp_dir
		_video_audio_temp_dirs.add(temp_dir)
	audio_path = os.path.join(temp_dir, "audio.wav")
	try:
		source_mtime = os.path.getmtime(abs_path)
		needs_extract = True
		if os.path.exists(audio_path):
			audio_mtime = os.path.getmtime(audio_path)
			needs_extract = audio_mtime < source_mtime
		if needs_extract:
			result = subprocess.run(
				[
					ffmpeg_exe,
					"-y",
					"-i",
					abs_path,
					"-vn",
					"-acodec",
					"pcm_s16le",
					"-ar",
					"44100",
					"-ac",
					"2",
					audio_path,
				],
				stdout=subprocess.DEVNULL,
				stderr=subprocess.DEVNULL,
				check=False,
			)
			if result.returncode != 0:
				raise RuntimeError(f"ffmpeg exited with code {result.returncode}")
		session["audio_path"] = audio_path
		session["audio_prepared"] = True
		session.pop("audio_error", None)
		return audio_path
	except Exception as exc:
		session["audio_error"] = f"Audio unavailable: {exc}"
		session["audio_prepared"] = False
		return None


def _start_video_audio(session: dict[str, Any]) -> None:
	if os.name != "nt" or winsound is None:
		return
	if session.get("audio_playing"):
		_stop_video_audio(session)
	audio_path = _prepare_video_audio(session)
	if not audio_path:
		return
	try:
		winsound.PlaySound(audio_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
		session["audio_playing"] = True
	except Exception as exc:
		session["audio_error"] = f"Audio playback failed: {exc}"
		session["audio_playing"] = False


def _stop_video_audio(session: dict[str, Any]) -> None:
	if os.name != "nt" or winsound is None:
		return
	if session.get("audio_playing"):
		try:
			winsound.PlaySound(None, winsound.SND_PURGE)
		except Exception:
			pass
	session["audio_playing"] = False


def _handle_video_label_resize(session: dict[str, Any]) -> None:
	if session.get("error"):
		return
	if session.get("playing") and session.get("current_pil") is not None:
		_display_video_image(session, session.get("current_pil"))
	else:
		if session.get("current_pil") is not None:
			_display_video_image(session, session.get("current_pil"))
		else:
			_ensure_video_preview(session)
			_display_video_image(session, session.get("preview_pil"))


def _update_video_session_ui(session: dict[str, Any]) -> None:
	button: Optional[ctk.CTkButton] = session.get("button")
	if session.get("playing"):
		if button:
			button.configure(text="Pause", state="normal")
		return
	if button:
		label_text = "Replay" if session.get("ended") else "Play"
		state = "disabled" if session.get("error") else "normal"
		button.configure(text=label_text, state=state)
	if session.get("error"):
		label: Optional[tk.Label] = session.get("label")
		if label and label.winfo_exists():
			label.configure(text=session["error"], image="")
			label.image = None
		return
	image = session.get("current_pil") if session.get("current_pil") is not None else None
	if image is None:
		_ensure_video_preview(session)
		image = session.get("preview_pil")
	_display_video_image(session, image)


def _determine_target_size(session: dict[str, Any]) -> Optional[tuple[int, int]]:
	preview: Optional["Image.Image"] = session.get("preview_pil")  # type: ignore[name-defined]
	label: Optional[tk.Label] = session.get("label")
	width_hint = 0
	height_hint = 0
	if label and label.winfo_exists():
		label.update_idletasks()
		width_hint = label.winfo_width()
		height_hint = label.winfo_height()
	if width_hint < 20 or height_hint < 20:
		display_size = session.get("display_size")
		if display_size:
			width_hint, height_hint = display_size
	if not preview:
		return None
	src_w, src_h = preview.size
	if not src_w or not src_h:
		return None
	if width_hint < 1 or height_hint < 1:
		return None
	scale = min(width_hint / float(src_w), height_hint / float(src_h), 1.0)
	if scale >= 0.999:
		return None
	target_w = max(1, int(src_w * scale))
	target_h = max(1, int(src_h * scale))
	return target_w, target_h


def _locate_after_widget(session: dict[str, Any]) -> Optional[tk.Misc]:
	label = session.get("label")
	if label and label.winfo_exists():
		return label
	controls = session.get("controls")
	if controls and controls.winfo_exists():
		return controls
	frame = _home_widgets.get("frame")
	if frame and frame.winfo_exists():
		return frame
	return None


def _cancel_video_callback(session: dict[str, Any]) -> None:
	after_id = session.get("after_id")
	widget: Optional[tk.Misc] = session.get("after_widget")
	if after_id and widget and widget.winfo_exists():
		try:
			widget.after_cancel(after_id)
		except Exception:
			pass
		session["after_id"] = None
		session["after_widget"] = None


def _advance_video_frame(session: dict[str, Any]) -> None:
	if not session.get("playing"):
		return
	iterator = session.get("iterator")
	if iterator is None:
		_stop_inline_video(session, ended=True)
		return
	if Image is None or imageio is None:
		session["error"] = "Video playback requires Pillow and imageio."
		_stop_inline_video(session)
		return
	try:
		frame = next(iterator)
	except StopIteration:
		_stop_inline_video(session, ended=True)
		return
	except Exception as exc:
		session["error"] = f"Video playback failed: {exc}"
		_stop_inline_video(session)
		return
	frame_image = Image.fromarray(frame)
	_display_video_image(session, frame_image)
	session["current_pil"] = frame_image
	owner = _locate_after_widget(session)
	if not owner:
		_stop_inline_video(session)
		return
	frame_duration = session.get("frame_duration")
	if frame_duration is None:
		delay = session.get("delay", 33)
		wait_ms = max(1, int(delay))
	else:
		now = time.perf_counter()
		target_time = session.get("next_tick")
		if target_time is None:
			target_time = now + frame_duration
		else:
			target_time += frame_duration
		session["next_tick"] = target_time
		remaining = max(0.0, target_time - now)
		wait_ms = max(1, int(remaining * 1000))
	session["after_widget"] = owner
	session["after_id"] = owner.after(wait_ms, lambda: _advance_video_frame(session))


def _start_inline_video(session: dict[str, Any]) -> None:
	if session.get("error"):
		_update_video_session_ui(session)
		return
	if session.get("playing"):
		return
	if imageio is None or Image is None:
		session["error"] = "Video playback requires Pillow and imageio."
		_update_video_session_ui(session)
		return
	abs_path = session.get("abs_path")
	if not abs_path or not os.path.exists(abs_path):
		session["error"] = "Video file missing."
		_update_video_session_ui(session)
		return
	plugin_kwargs: dict[str, Any] = {}
	target_size = _determine_target_size(session)
	if target_size:
		plugin_kwargs["size"] = target_size
	used_target_size = target_size
	try:
		reader = imageio.get_reader(abs_path, **plugin_kwargs)
	except TypeError:
		used_target_size = None
		try:
			reader = imageio.get_reader(abs_path)
		except Exception as exc:
			session["error"] = f"Could not start video: {exc}"
			_update_video_session_ui(session)
			return
	except Exception as exc:
		session["error"] = f"Could not start video: {exc}"
		_update_video_session_ui(session)
		return
	try:
		meta = reader.get_meta_data() or {}
		fps_value = meta.get("fps") or 24
		fps = float(fps_value)
	except Exception:
		fps = 24.0
	frame_duration = 1.0 / fps if fps else None
	session["target_size"] = used_target_size
	session["frame_duration"] = frame_duration
	session["delay"] = max(1, int(round(1000 / fps))) if fps else 40
	session["reader"] = reader
	try:
		iterator = reader.iter_data()
	except Exception:
		iterator = iter(reader)
	session["iterator"] = iterator
	session["next_tick"] = time.perf_counter()
	session["playing"] = True
	session["ended"] = False
	_update_video_session_ui(session)
	_start_video_audio(session)
	_cancel_video_callback(session)
	_advance_video_frame(session)


def _stop_inline_video(session: dict[str, Any], *, ended: bool = False) -> None:
	if not session.get("playing") and not session.get("reader"):
		session["ended"] = ended
		_update_video_session_ui(session)
		return
	session["playing"] = False
	_cancel_video_callback(session)
	_stop_video_audio(session)
	reader = session.get("reader")
	if reader is not None:
		try:
			reader.close()
		except Exception:
			pass
	session["reader"] = None
	session["iterator"] = None
	session["ended"] = ended
	session["next_tick"] = None
	session["frame_duration"] = None
	_update_video_session_ui(session)


def _toggle_inline_video(session: dict[str, Any]) -> None:
	if session.get("playing"):
		_stop_inline_video(session)
	else:
		_start_inline_video(session)


def _render_inline_video(
	attachment: dict[str, Any],
	container: tk.Misc,
	*,
	controls: bool = True,
	click_to_toggle: bool = False,
) -> None:
	if attachment.get("type") != "video":
		return
	rel_path = (attachment.get("path") or "").strip()
	if not rel_path:
		ctk.CTkLabel(container, text="Video unavailable").grid(sticky="w", padx=12, pady=12)
		return
	session = _ensure_video_session(rel_path)
	container.grid_columnconfigure(0, weight=1)
	container.grid_rowconfigure(0, weight=1)
	video_frame = ctk.CTkFrame(container, corner_radius=12, fg_color=_palette.get("surface", "#111b2e"))
	video_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
	video_frame.grid_columnconfigure(0, weight=1)
	video_frame.grid_rowconfigure(0, weight=1)
	label = tk.Label(
		video_frame,
		bd=0,
		bg=_palette.get("surface", "#111b2e"),
		fg=_palette.get("text", "#e2e8f0"),
		anchor="center",
	)
	label.grid(row=0, column=0, sticky="nswe", padx=12, pady=12)
	controls_frame: Optional[ctk.CTkFrame] = None
	play_btn: Optional[ctk.CTkButton] = None
	if controls:
		controls_frame = ctk.CTkFrame(video_frame, fg_color="transparent")
		controls_frame.grid(row=1, column=0, sticky="we", padx=12, pady=(0, 12))
		controls_frame.grid_columnconfigure(0, weight=0)
		play_btn = ctk.CTkButton(
			controls_frame,
			text="Play",
			width=90,
			command=lambda s=session: _toggle_inline_video(s),
		)
		play_btn.grid(row=0, column=0, sticky="w")
		open_btn = ctk.CTkButton(
			controls_frame,
			text="Open externally",
			width=140,
			fg_color="transparent",
			border_width=1,
			border_color=_palette.get("accent", "#4c8dff"),
			text_color=_palette.get("accent", "#4c8dff"),
			hover_color=_palette.get("surface", "#111b2e"),
			command=lambda p=rel_path: _open_image(p),
		)
		open_btn.grid(row=0, column=1, padx=(12, 0), sticky="w")
	if click_to_toggle:
		label.configure(cursor="hand2")
		label.bind("<Button-1>", lambda _evt, s=session: _toggle_inline_video(s))
	label.bind("<Configure>", lambda _evt, s=session: _handle_video_label_resize(s))
	session["label"] = label
	session["button"] = play_btn
	session["controls"] = controls_frame
	_update_video_session_ui(session)


def _open_attachment(attachment: dict[str, Any]) -> None:
	rel_path = attachment.get("path")
	if rel_path:
		_open_image(rel_path)


def _show_auth_window(mode: str) -> None:
	root = _home_widgets.get("frame")
	if not root:
		return
	if not _auth_widgets:
		_create_auth_window(root.winfo_toplevel())
	_set_auth_mode(mode)
	window: ctk.CTkToplevel = _auth_widgets["window"]
	window.deiconify()
	window.lift()
	window.grab_set()


def _create_auth_window(master: tk.Misc) -> None:
	window = ctk.CTkToplevel(master)
	window.withdraw()
	window.title("Sign in / Register")
	window.geometry("360x300")
	window.resizable(False, False)

	mode_var = tk.StringVar(value="login")

	title_lbl = ctk.CTkLabel(window, text="Sign in", font=ctk.CTkFont(size=18, weight="bold"))
	title_lbl.pack(pady=(18, 12))

	ctk.CTkLabel(window, text="Username").pack(anchor="w", padx=24)
	username_entry = ctk.CTkEntry(window, width=300)
	username_entry.pack(padx=24, pady=(0, 12))

	ctk.CTkLabel(window, text="Password").pack(anchor="w", padx=24)
	password_entry = ctk.CTkEntry(window, width=300, show="*")
	password_entry.pack(padx=24, pady=(0, 8))

	remember_var = tk.BooleanVar(value=True)
	remember_check = ctk.CTkCheckBox(window, text="Stay signed in", variable=remember_var)
	remember_check.pack(anchor="w", padx=24, pady=(0, 16))

	def submit_handler() -> None:
		username = username_entry.get().strip()
		password = password_entry.get().strip()
		if not username or not password:
			messagebox.showwarning("Missing info", "Please provide username and password.")
			return
		if mode_var.get() == "login":
			if username not in users or users[username].get("password") != password:
				messagebox.showerror("Login failed", "Invalid username or password.")
				return
			users[username].setdefault("notifications", [])
			users[username].setdefault("following", [])
			users[username].setdefault("followers", [])
			_set_current_user(username)
		else:
			if username in users:
				messagebox.showerror("Exists", "That username is already registered.")
				return
			users[username] = {
				"password": password,
				"registered_at": now_ts(),
				"notifications": [],
				"following": [],
				"followers": [],
				"profile_picture": None,
			}
			persist()
			_set_current_user(username)
		if remember_var.get():
			remember_user(username)
		else:
			remember_user(None)
		hide_handler()
		refresh_views(_frames)

	submit_btn = ctk.CTkButton(window, text="Login", width=200, command=submit_handler)
	submit_btn.pack(pady=(0, 8))

	def toggle_mode_handler() -> None:
		new_mode = "register" if mode_var.get() == "login" else "login"
		set_mode_handler(new_mode)

	switch_btn = ctk.CTkButton(window, text="Switch to register", width=200, command=toggle_mode_handler)
	switch_btn.pack()

	def set_mode_handler(new_mode: str) -> None:
		mode_var.set(new_mode)
		title_lbl.configure(text="Sign in" if new_mode == "login" else "Register")
		submit_btn.configure(text="Login" if new_mode == "login" else "Register")
		switch_btn.configure(text="Switch to register" if new_mode == "login" else "Switch to login")

	def hide_handler() -> None:
		try:
			window.grab_release()
		except Exception:
			pass
		window.withdraw()
		master.focus_set()

	_auth_widgets.update(
		{
			"window": window,
			"mode": mode_var,
			"title": title_lbl,
			"username": username_entry,
			"password": password_entry,
			"remember_var": remember_var,
			"remember_check": remember_check,
			"submit_button": submit_btn,
			"switch_button": switch_btn,
			"submit_fn": submit_handler,
			"toggle_fn": toggle_mode_handler,
			"set_mode_fn": set_mode_handler,
			"hide_fn": hide_handler,
		}
	)

	window.protocol("WM_DELETE_WINDOW", hide_handler)

	def _submit_auth_event(_event) -> str:
		submit_handler()
		return "break"

	username_entry.bind("<Return>", _submit_auth_event)
	username_entry.bind("<KP_Enter>", _submit_auth_event)
	password_entry.bind("<Return>", _submit_auth_event)
	password_entry.bind("<KP_Enter>", _submit_auth_event)


def _set_auth_mode(mode: str) -> None:
	set_mode: Callable[[str], None] = _auth_widgets.get("set_mode_fn")
	if set_mode:
		set_mode(mode)
	username: ctk.CTkEntry = _auth_widgets.get("username")
	password: ctk.CTkEntry = _auth_widgets.get("password")
	remember_var: tk.BooleanVar = _auth_widgets.get("remember_var")
	if username:
		username.delete(0, tk.END)
	if password:
		password.delete(0, tk.END)
	if remember_var:
		remember_var.set(True)


def _handle_auth_submit() -> None:
	submit_fn: Callable[[], None] = _auth_widgets.get("submit_fn")
	if submit_fn:
		submit_fn()


def _toggle_auth_mode() -> None:
	toggle_fn: Callable[[], None] = _auth_widgets.get("toggle_fn")
	if toggle_fn:
		toggle_fn()


def _hide_auth_window() -> None:
	hide_fn: Callable[[], None] = _auth_widgets.get("hide_fn")
	if hide_fn:
		hide_fn()
