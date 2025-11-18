"""Legacy standalone version of the DevEcho UI."""

# ruff: noqa

import os
import json
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, scrolledtext
from datetime import datetime
import re
from tkinter import filedialog
import shutil
import sys
from typing import TYPE_CHECKING, Callable
try:
    from PIL import Image, ImageTk, ImageDraw  # optional image helpers
except ImportError:
    Image = None  # type: ignore[assignment]
    ImageTk = None  # type: ignore[assignment]
    ImageDraw = None  # type: ignore[assignment]

if TYPE_CHECKING:
    notifications_list: ctk.CTkScrollableFrame
    toggle_replies: Callable[[int], None]
    open_reply_box: Callable[[int | None], None]
    render_dm: Callable[[], None]
    send_dm: Callable[[], None]
    open_dm_with: Callable[[str], None]

frames: dict[str, ctk.CTkFrame] = {}

# Define show_frame function early to avoid assignment errors
def show_frame(name: str) -> None:
    for frame_name, frame in frames.items():
        frame.grid_remove()
    if name in frames:
        frames[name].grid(row=0, column=0, sticky="nswe")

# ---------- persistence helpers ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_PATH = os.path.join(BASE_DIR, "data.json")
POSTS_PATH = os.path.join(BASE_DIR, "posts.json")
NOTIFICATIONS_PATH = os.path.join(BASE_DIR, "notfication.json")
# NEW: messages store
MESSAGES_PATH = os.path.join(BASE_DIR, "messages.json")
# NEW: media directory for uploads
MEDIA_DIR = os.path.join(BASE_DIR, "media")
os.makedirs(MEDIA_DIR, exist_ok=True)
PROFILE_PICS_DIR = os.path.join(BASE_DIR, "Profile Pictures")
os.makedirs(PROFILE_PICS_DIR, exist_ok=True)
DEFAULT_PROFILE_PIC = os.path.join(PROFILE_PICS_DIR, "image (6).png")
profile_avatar_cache: dict[tuple[str, int], tk.PhotoImage] = {}

def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default

def save_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=4, ensure_ascii=False)

def now_ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

raw_users = load_json(USERS_PATH, {})
users = {}
notifications_data = load_json(NOTIFICATIONS_PATH, {})
raw_posts = load_json(POSTS_PATH, [])
# NEW: load messages dict: { "Ali|Ben": [ {sender, content, time, attachments: []}, ... ] }
messages = load_json(MESSAGES_PATH, {})
posts = []
def normalize_post(post_dict):
    post_dict.setdefault("edited", False)
    post_dict.setdefault("edited_at", None)
    post_dict.setdefault("replies", [])
    post_dict["replies"] = [normalize_reply(r) for r in post_dict["replies"]]
    # add reaction fields
    liked_by = post_dict.get("liked_by") or []
    disliked_by = post_dict.get("disliked_by") or []
    if not isinstance(liked_by, list): liked_by = []
    if not isinstance(disliked_by, list): disliked_by = []
    post_dict["liked_by"] = liked_by
    post_dict["disliked_by"] = disliked_by
    post_dict["likes"] = len(liked_by)
    post_dict["dislikes"] = len(disliked_by)
    # NEW: attachments list
    post_dict.setdefault("attachments", [])
    return post_dict

def normalize_reply(reply_dict):
    reply_dict.setdefault("author", "unknown")
    reply_dict.setdefault("content", "")
    reply_dict.setdefault("created_at", now_ts())
    reply_dict.setdefault("edited", False)
    reply_dict.setdefault("edited_at", None)
    # add reaction fields
    liked_by = reply_dict.get("liked_by") or []
    disliked_by = reply_dict.get("disliked_by") or []
    if not isinstance(liked_by, list): liked_by = []
    if not isinstance(disliked_by, list): disliked_by = []
    reply_dict["liked_by"] = liked_by
    reply_dict["disliked_by"] = disliked_by
    reply_dict["likes"] = len(liked_by)
    reply_dict["dislikes"] = len(disliked_by)
    # NEW: attachments list
    reply_dict.setdefault("attachments", [])
    return reply_dict
if isinstance(raw_posts, list):
    posts = [normalize_post(p) for p in raw_posts]
else:
    for author, plist in raw_posts.items():
        for post in plist:
            posts.append(normalize_post({
                "author": author,
                "content": post.get("post", ""),
                "created_at": post.get("posted_at", now_ts())
            }))

for username, info in raw_users.items():
    users[username] = {
        "password": info.get("password", ""),
        "registered_at": info.get("registered_at", now_ts())
    }
    users[username]["notifications"] = notifications_data.get(username, [])
    users[username]["following"] = list(info.get("following", []))
    users[username]["followers"] = list(info.get("followers", []))
    users[username]["profile_picture"] = info.get("profile_picture")

# ensure following/followers exist for each user
for uname in users:
    users[uname].setdefault("following", [])
    users[uname].setdefault("followers", [])

def persist():
    save_json(USERS_PATH, users)
    save_json(POSTS_PATH, posts)
    save_json(NOTIFICATIONS_PATH, {user: users[user].get("notifications", []) for user in users})
    save_json(MESSAGES_PATH, messages)  # NEW: persist DMs

# ---------- app state ----------
current_user = None
# frames = {}
editing_post_index = None  # track which post is being edited
editing_reply_target = None  # (post_idx, reply_idx) when editing a reply
expanded_replies = set()
reply_input_target = None
inspected_user = None  # currently opened profile (inspection)
# NEW: DM state
active_dm_user = None
dm_draft_attachments = []
dm_following_list: ctk.CTkScrollableFrame | None = None
notifications_list: ctk.CTkScrollableFrame | None = None
# NEW: post/reply attachment drafts remain above
post_draft_attachments = []         # list of relative paths for the main post composer
reply_draft_attachments = []        # list for the currently open reply composer

# ---------- utility: images and emoji ----------
# NEW: safe copy to media, return relative path "media/<name>"
def copy_image_to_media(src_path):
    if not src_path:
        return None
    try:
        # keep only filename, ensure unique
        base = os.path.basename(src_path)
        name, ext = os.path.splitext(base)
        ext = ext.lower()
        if ext not in [".png", ".gif", ".jpg", ".jpeg", ".webp"]:
            messagebox.showwarning("Unsupported image", "Please select PNG, GIF, JPG, or WEBP.")
            return None
        dst = os.path.join(MEDIA_DIR, base)
        i = 1
        while os.path.exists(dst):
            dst = os.path.join(MEDIA_DIR, f"{name}_{i}{ext}")
            i += 1
        shutil.copy2(src_path, dst)
        return os.path.relpath(dst, BASE_DIR).replace("\\", "/")
    except Exception as e:
        messagebox.showerror("Attach image failed", f"Could not attach image:\n{e}")
        return None

def copy_image_to_profile_pics(src_path):
    if not src_path:
        return None
    try:
        base = os.path.basename(src_path)
        name, ext = os.path.splitext(base)
        ext = ext.lower()
        if ext not in [".png", ".gif", ".jpg", ".jpeg", ".webp"]:
            messagebox.showwarning("Unsupported image", "Please select PNG, GIF, JPG, or WEBP.")
            return None
        dst = os.path.join(PROFILE_PICS_DIR, base)
        i = 1
        while os.path.exists(dst):
            dst = os.path.join(PROFILE_PICS_DIR, f"{name}_{i}{ext}")
            i += 1
        shutil.copy2(src_path, dst)
        return os.path.relpath(dst, BASE_DIR).replace("\\", "/")
    except Exception as e:
        messagebox.showerror("Profile picture failed", f"Could not set profile picture:\n{e}")
        return None

# NEW: load image for Tk, scaled to max_width
def load_image_for_tk(rel_path, max_width):
    abs_path = os.path.join(BASE_DIR, rel_path)
    if Image:
        try:
            resample = getattr(Image, "Resampling", None)
            lanczos = getattr(resample, "LANCZOS", None) if resample else getattr(Image, "LANCZOS", None)
            fallback = (
                getattr(resample, "BICUBIC", None) if resample else getattr(Image, "BICUBIC", None)
            ) or getattr(Image, "BILINEAR", None) or getattr(Image, "NEAREST", 0)
            img = Image.open(abs_path)
            w, h = img.size
            if w > max_width:
                scale = max_width / float(w)
                img = img.resize((int(w * scale), int(h * scale)), lanczos or fallback)
            return ImageTk.PhotoImage(img)
        except Exception:
            pass
    # Fallback: PhotoImage (best with PNG/GIF); crude downscale using subsample
    try:
        photo = tk.PhotoImage(file=abs_path)
        w = photo.width()
        if w > max_width:
            factor = max(1, int(w / max_width))
            photo = photo.subsample(factor, factor)
        return photo
    except Exception:
        return None

# NEW: open image with OS
def open_image(rel_path):
    try:
        abs_path = os.path.join(BASE_DIR, rel_path)
        if os.name == "nt":
            os.startfile(abs_path)
        elif sys.platform == "darwin":
            os.system(f'open "{abs_path}"')
        else:
            os.system(f'xdg-open "{abs_path}"')
    except Exception:
        pass

# NEW: minimal emoji picker
EMOJI_CHOICES = ["😀","😂","😍","😎","😢","😡","👍","🙏","🔥","🎉","❤️","👏","🤝","🤔","✅","❌","📷","🎯"]

class EmojiPicker:
    def __init__(self, root):
        self.root = root
        self.popup = None

    def open(self, anchor_widget, insert_target_widget):
        self.close()
        self.popup = tk.Toplevel(self.root)
        self.popup.overrideredirect(True)
        try:
            self.popup.attributes("-topmost", True)
        except Exception:
            pass
        self.popup.configure(bg=PALETTE["surface"])
        frame = tk.Frame(self.popup, bg=PALETTE["surface"])
        frame.pack(padx=6, pady=6)
        # grid of buttons
        cols = 6
        for i, ch in enumerate(EMOJI_CHOICES):
            btn = tk.Button(
                frame, text=ch, bd=0, font=("Segoe UI Emoji", 14),
                bg=PALETTE["surface"], fg=PALETTE["text"],
                activebackground=PALETTE["card"], activeforeground=PALETTE["text"],
                command=lambda c=ch: self._insert(c, insert_target_widget)
            )
            btn.grid(row=i // cols, column=i % cols, padx=2, pady=2, sticky="nsew")
        # position near anchor
        x = anchor_widget.winfo_rootx()
        y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height()
        self.popup.geometry(f"+{x}+{y}")
        self.popup.bind("<FocusOut>", lambda _e: self.close())
        self.popup.focus_force()

    def _insert(self, ch, widget):
        try:
            if isinstance(widget, tk.Text):
                widget.insert("insert", ch)
                widget.focus_set()
            else:
                # CTkEntry / tk.Entry
                try:
                    cur = widget.index("insert")
                except Exception:
                    try:
                        cur = widget._entry.index("insert")
                    except Exception:
                        cur = len(widget.get())
                val = widget.get()
                new_val = val[:cur] + ch + val[cur:]
                widget.delete(0, tk.END)
                widget.insert(0, new_val)
                try:
                    widget.icursor(cur + len(ch))
                except Exception:
                    pass
                widget.focus_set()
        finally:
            self.close()

    def close(self):
        if self.popup:
            try:
                self.popup.destroy()
            except Exception:
                pass
            self.popup = None

# ---------- profile picture helpers ----------
def profile_image_path(username: str) -> str | None:
    path = users.get(username, {}).get("profile_picture")
    if path:
        abs_path = path if os.path.isabs(path) else os.path.join(BASE_DIR, path)
        if os.path.exists(abs_path):
            return abs_path
    return DEFAULT_PROFILE_PIC if os.path.exists(DEFAULT_PROFILE_PIC) else None

def load_profile_avatar(username: str, size: int = 48) -> tk.PhotoImage | None:
    key = (username, size)
    if key in profile_avatar_cache:
        return profile_avatar_cache[key]
    path = profile_image_path(username)
    if not path:
        return None
    try:
        if Image and ImageTk and ImageDraw:
            img = Image.open(path).convert("RGBA")
            img = img.resize((size, size), getattr(Image, "LANCZOS", Image.BICUBIC))
            mask = Image.new("L", (size, size), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
            img.putalpha(mask)
            photo = ImageTk.PhotoImage(img)
        else:
            photo = tk.PhotoImage(file=path)
            if photo.width() > size:
                factor = max(1, photo.width() // size)
                photo = photo.subsample(factor, factor)
        profile_avatar_cache[key] = photo
        return photo
    except Exception:
        return None

def invalidate_profile_avatar(username: str) -> None:
    for key in [k for k in profile_avatar_cache if k[0] == username]:
        del profile_avatar_cache[key]

def update_profile_avatar_display() -> None:
    if not profile_avatar_panel or not profile_avatar_label or not profile_change_pic_btn:
        return
    if not current_user:
        profile_change_pic_btn.configure(state="disabled")
        profile_avatar_panel.grid_remove()
        profile_avatar_label.configure(image="", text="")
        profile_avatar_label.image = None
        return
    photo = load_profile_avatar(current_user, size=112)
    if photo:
        profile_avatar_label.configure(image=photo, text="")
        profile_avatar_label.image = photo
    else:
        profile_avatar_label.configure(image="", text="No photo")
        profile_avatar_label.image = None
    profile_avatar_panel.grid()
    profile_change_pic_btn.configure(state="normal")

def change_profile_picture() -> None:
    if not require_login("change your profile picture"):
        return
    path = filedialog.askopenfilename(
        title="Choose profile picture",
        filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.gif;*.webp"), ("All files", "*.*")]
    )
    rel = copy_image_to_profile_pics(path)
    if not rel:
        return
    prev_rel = users[current_user].get("profile_picture")
    if prev_rel:
        prev_abs = prev_rel if os.path.isabs(prev_rel) else os.path.join(BASE_DIR, prev_rel)
        new_abs = rel if os.path.isabs(rel) else os.path.join(BASE_DIR, rel)
        default_abs = os.path.abspath(DEFAULT_PROFILE_PIC)
        prev_abs = os.path.abspath(prev_abs)
        if prev_abs != default_abs and prev_abs != os.path.abspath(new_abs):
            try:
                profile_dir_abs = os.path.abspath(PROFILE_PICS_DIR)
                if os.path.commonpath([prev_abs, profile_dir_abs]) == profile_dir_abs and os.path.exists(prev_abs):
                    os.remove(prev_abs)
            except Exception:
                pass
    users[current_user]["profile_picture"] = rel
    invalidate_profile_avatar(current_user)
    persist()
    update_profile_avatar_display()
    render_dm()
    if inspected_user == current_user:
        render_inspected_profile()

# ---------- app state ----------
current_user = None
# frames = {}
editing_post_index = None  # track which post is being edited
editing_reply_target = None  # (post_idx, reply_idx) when editing a reply
expanded_replies = set()
reply_input_target = None
inspected_user = None  # currently opened profile (inspection)
# NEW: DM state
active_dm_user = None
dm_draft_attachments = []
dm_following_list: ctk.CTkScrollableFrame | None = None
notifications_list: ctk.CTkScrollableFrame | None = None
# NEW: post/reply attachment drafts remain above
post_draft_attachments = []         # list of relative paths for the main post composer
reply_draft_attachments = []        # list for the currently open reply composer

# ---------- utility: images and emoji ----------
# NEW: safe copy to media, return relative path "media/<name>"
def copy_image_to_media(src_path):
    if not src_path:
        return None
    try:
        # keep only filename, ensure unique
        base = os.path.basename(src_path)
        name, ext = os.path.splitext(base)
        ext = ext.lower()
        if ext not in [".png", ".gif", ".jpg", ".jpeg", ".webp"]:
            messagebox.showwarning("Unsupported image", "Please select PNG, GIF, JPG, or WEBP.")
            return None
        dst = os.path.join(MEDIA_DIR, base)
        i = 1
        while os.path.exists(dst):
            dst = os.path.join(MEDIA_DIR, f"{name}_{i}{ext}")
            i += 1
        shutil.copy2(src_path, dst)
        return os.path.relpath(dst, BASE_DIR).replace("\\", "/")
    except Exception as e:
        messagebox.showerror("Attach image failed", f"Could not attach image:\n{e}")
        return None

def copy_image_to_profile_pics(src_path):
    if not src_path:
        return None
    try:
        base = os.path.basename(src_path)
        name, ext = os.path.splitext(base)
        ext = ext.lower()
        if ext not in [".png", ".gif", ".jpg", ".jpeg", ".webp"]:
            messagebox.showwarning("Unsupported image", "Please select PNG, GIF, JPG, or WEBP.")
            return None
        dst = os.path.join(PROFILE_PICS_DIR, base)
        i = 1
        while os.path.exists(dst):
            dst = os.path.join(PROFILE_PICS_DIR, f"{name}_{i}{ext}")
            i += 1
        shutil.copy2(src_path, dst)
        return os.path.relpath(dst, BASE_DIR).replace("\\", "/")
    except Exception as e:
        messagebox.showerror("Profile picture failed", f"Could not set profile picture:\n{e}")
        return None

# NEW: load image for Tk, scaled to max_width
def load_image_for_tk(rel_path, max_width):
    abs_path = os.path.join(BASE_DIR, rel_path)
    if Image:
        try:
            resample = getattr(Image, "Resampling", None)
            lanczos = getattr(resample, "LANCZOS", None) if resample else getattr(Image, "LANCZOS", None)
            fallback = (
                getattr(resample, "BICUBIC", None) if resample else getattr(Image, "BICUBIC", None)
            ) or getattr(Image, "BILINEAR", None) or getattr(Image, "NEAREST", 0)
            img = Image.open(abs_path)
            w, h = img.size
            if w > max_width:
                scale = max_width / float(w)
                img = img.resize((int(w * scale), int(h * scale)), lanczos or fallback)
            return ImageTk.PhotoImage(img)
        except Exception:
            pass
    # Fallback: PhotoImage (best with PNG/GIF); crude downscale using subsample
    try:
        photo = tk.PhotoImage(file=abs_path)
        w = photo.width()
        if w > max_width:
            factor = max(1, int(w / max_width))
            photo = photo.subsample(factor, factor)
        return photo
    except Exception:
        return None

# NEW: open image with OS
def open_image(rel_path):
    try:
        abs_path = os.path.join(BASE_DIR, rel_path)
        if os.name == "nt":
            os.startfile(abs_path)
        elif sys.platform == "darwin":
            os.system(f'open "{abs_path}"')
        else:
            os.system(f'xdg-open "{abs_path}"')
    except Exception:
        pass

# NEW: minimal emoji picker
EMOJI_CHOICES = ["😀","😂","😍","😎","😢","😡","👍","🙏","🔥","🎉","❤️","👏","🤝","🤔","✅","❌","📷","🎯"]

class EmojiPicker:
    def __init__(self, root):
        self.root = root
        self.popup = None

    def open(self, anchor_widget, insert_target_widget):
        self.close()
        self.popup = tk.Toplevel(self.root)
        self.popup.overrideredirect(True)
        try:
            self.popup.attributes("-topmost", True)
        except Exception:
            pass
        self.popup.configure(bg=PALETTE["surface"])
        frame = tk.Frame(self.popup, bg=PALETTE["surface"])
        frame.pack(padx=6, pady=6)
        # grid of buttons
        cols = 6
        for i, ch in enumerate(EMOJI_CHOICES):
            btn = tk.Button(
                frame, text=ch, bd=0, font=("Segoe UI Emoji", 14),
                bg=PALETTE["surface"], fg=PALETTE["text"],
                activebackground=PALETTE["card"], activeforeground=PALETTE["text"],
                command=lambda c=ch: self._insert(c, insert_target_widget)
            )
            btn.grid(row=i // cols, column=i % cols, padx=2, pady=2, sticky="nsew")
        # position near anchor
        x = anchor_widget.winfo_rootx()
        y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height()
        self.popup.geometry(f"+{x}+{y}")
        self.popup.bind("<FocusOut>", lambda _e: self.close())
        self.popup.focus_force()

    def _insert(self, ch, widget):
        try:
            if isinstance(widget, tk.Text):
                widget.insert("insert", ch)
                widget.focus_set()
            else:
                # CTkEntry / tk.Entry
                try:
                    cur = widget.index("insert")
                except Exception:
                    try:
                        cur = widget._entry.index("insert")
                    except Exception:
                        cur = len(widget.get())
                val = widget.get()
                new_val = val[:cur] + ch + val[cur:]
                widget.delete(0, tk.END)
                widget.insert(0, new_val)
                try:
                    widget.icursor(cur + len(ch))
                except Exception:
                    pass
                widget.focus_set()
        finally:
            self.close()

    def close(self):
        if self.popup:
            try:
                self.popup.destroy()
            except Exception:
                pass
            self.popup = None

# ---------- profile picture helpers ----------
def profile_image_path(username: str) -> str | None:
    path = users.get(username, {}).get("profile_picture")
    if path:
        abs_path = path if os.path.isabs(path) else os.path.join(BASE_DIR, path)
        if os.path.exists(abs_path):
            return abs_path
    return DEFAULT_PROFILE_PIC if os.path.exists(DEFAULT_PROFILE_PIC) else None

def load_profile_avatar(username: str, size: int = 48) -> tk.PhotoImage | None:
    key = (username, size)
    if key in profile_avatar_cache:
        return profile_avatar_cache[key]
    path = profile_image_path(username)
    if not path:
        return None
    try:
        if Image and ImageTk and ImageDraw:
            img = Image.open(path).convert("RGBA")
            img = img.resize((size, size), getattr(Image, "LANCZOS", Image.BICUBIC))
            mask = Image.new("L", (size, size), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
            img.putalpha(mask)
            photo = ImageTk.PhotoImage(img)
        else:
            photo = tk.PhotoImage(file=path)
            if photo.width() > size:
                factor = max(1, photo.width() // size)
                photo = photo.subsample(factor, factor)
        profile_avatar_cache[key] = photo
        return photo
    except Exception:
        return None

def invalidate_profile_avatar(username: str) -> None:
    for key in [k for k in profile_avatar_cache if k[0] == username]:
        del profile_avatar_cache[key]

def update_profile_avatar_display() -> None:
    if not profile_avatar_panel or not profile_avatar_label or not profile_change_pic_btn:
        return
    if not current_user:
        profile_change_pic_btn.configure(state="disabled")
        profile_avatar_panel.grid_remove()
        profile_avatar_label.configure(image="", text="")
        profile_avatar_label.image = None
        return
    photo = load_profile_avatar(current_user, size=112)
    if photo:
        profile_avatar_label.configure(image=photo, text="")
        profile_avatar_label.image = photo
    else:
        profile_avatar_label.configure(image="", text="No photo")
        profile_avatar_label.image = None
    profile_avatar_panel.grid()
    profile_change_pic_btn.configure(state="normal")

def change_profile_picture() -> None:
    if not require_login("change your profile picture"):
        return
    path = filedialog.askopenfilename(
        title="Choose profile picture",
        filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.gif;*.webp"), ("All files", "*.*")]
    )
    rel = copy_image_to_profile_pics(path)
    if not rel:
        return
    prev_rel = users[current_user].get("profile_picture")
    if prev_rel:
        prev_abs = prev_rel if os.path.isabs(prev_rel) else os.path.join(BASE_DIR, prev_rel)
        new_abs = rel if os.path.isabs(rel) else os.path.join(BASE_DIR, rel)
        default_abs = os.path.abspath(DEFAULT_PROFILE_PIC)
        prev_abs = os.path.abspath(prev_abs)
        if prev_abs != default_abs and prev_abs != os.path.abspath(new_abs):
            try:
                profile_dir_abs = os.path.abspath(PROFILE_PICS_DIR)
                if os.path.commonpath([prev_abs, profile_dir_abs]) == profile_dir_abs and os.path.exists(prev_abs):
                    os.remove(prev_abs)
            except Exception:
                pass
    users[current_user]["profile_picture"] = rel
    invalidate_profile_avatar(current_user)
    persist()
    update_profile_avatar_display()
    render_dm()
    if inspected_user == current_user:
        render_inspected_profile()

# ---------- app state ----------
current_user = None
# frames = {}
editing_post_index = None  # track which post is being edited
editing_reply_target = None  # (post_idx, reply_idx) when editing a reply
expanded_replies = set()
reply_input_target = None
inspected_user = None  # currently opened profile (inspection)
# NEW: DM state
active_dm_user = None
dm_draft_attachments = []
dm_following_list: ctk.CTkScrollableFrame | None = None
notifications_list: ctk.CTkScrollableFrame | None = None
# NEW: post/reply attachment drafts remain above
post_draft_attachments = []         # list of relative paths for the main post composer
reply_draft_attachments = []        # list for the currently open reply composer

# ---------- utility: images and emoji ----------
# NEW: safe copy to media, return relative path "media/<name>"
def copy_image_to_media(src_path):
    if not src_path:
        return None
    try:
        # keep only filename, ensure unique
        base = os.path.basename(src_path)
        name, ext = os.path.splitext(base)
        ext = ext.lower()
        if ext not in [".png", ".gif", ".jpg", ".jpeg", ".webp"]:
            messagebox.showwarning("Unsupported image", "Please select PNG, GIF, JPG, or WEBP.")
            return None
        dst = os.path.join(MEDIA_DIR, base)
        i = 1
        while os.path.exists(dst):
            dst = os.path.join(MEDIA_DIR, f"{name}_{i}{ext}")
            i += 1
        shutil.copy2(src_path, dst)
        return os.path.relpath(dst, BASE_DIR).replace("\\", "/")
    except Exception as e:
        messagebox.showerror("Attach image failed", f"Could not attach image:\n{e}")
        return None

def copy_image_to_profile_pics(src_path):
    if not src_path:
        return None
    try:
        base = os.path.basename(src_path)
        name, ext = os.path.splitext(base)
        ext = ext.lower()
        if ext not in [".png", ".gif", ".jpg", ".jpeg", ".webp"]:
            messagebox.showwarning("Unsupported image", "Please select PNG, GIF, JPG, or WEBP.")
            return None
        dst = os.path.join(PROFILE_PICS_DIR, base)
        i = 1
        while os.path.exists(dst):
            dst = os.path.join(PROFILE_PICS_DIR, f"{name}_{i}{ext}")
            i += 1
        shutil.copy2(src_path, dst)
        return os.path.relpath(dst, BASE_DIR).replace("\\", "/")
    except Exception as e:
        messagebox.showerror("Profile picture failed", f"Could not set profile picture:\n{e}")
        return None

# NEW: load image for Tk, scaled to max_width
def load_image_for_tk(rel_path, max_width):
    abs_path = os.path.join(BASE_DIR, rel_path)
    if Image:
        try:
            resample = getattr(Image, "Resampling", None)
            lanczos = getattr(resample, "LANCZOS", None) if resample else getattr(Image, "LANCZOS", None)
            fallback = (
                getattr(resample, "BICUBIC", None) if resample else getattr(Image, "BICUBIC", None)
            ) or getattr(Image, "BILINEAR", None) or getattr(Image, "NEAREST", 0)
            img = Image.open(abs_path)
            w, h = img.size
            if w > max_width:
                scale = max_width / float(w)
                img = img.resize((int(w * scale), int(h * scale)), lanczos or fallback)
            return ImageTk.PhotoImage(img)
        except Exception:
            pass
    # Fallback: PhotoImage (best with PNG/GIF); crude downscale using subsample
    try:
        photo = tk.PhotoImage(file=abs_path)
        w = photo.width()
        if w > max_width:
            factor = max(1, int(w / max_width))
            photo = photo.subsample(factor, factor)
        return photo
    except Exception:
        return None

# NEW: open image with OS
def open_image(rel_path):
    try:
        abs_path = os.path.join(BASE_DIR, rel_path)
        if os.name == "nt":
            os.startfile(abs_path)
        elif sys.platform == "darwin":
            os.system(f'open "{abs_path}"')
        else:
            os.system(f'xdg-open "{abs_path}"')
    except Exception:
        pass

# NEW: minimal emoji picker
EMOJI_CHOICES = ["😀","😂","😍","😎","😢","😡","👍","🙏","🔥","🎉","❤️","👏","🤝","🤔","✅","❌","📷","🎯"]

class EmojiPicker:
    def __init__(self, root):
        self.root = root
        self.popup = None

    def open(self, anchor_widget, insert_target_widget):
        self.close()
        self.popup = tk.Toplevel(self.root)
        self.popup.overrideredirect(True)
        try:
            self.popup.attributes("-topmost", True)
        except Exception:
            pass
        self.popup.configure(bg=PALETTE["surface"])
        frame = tk.Frame(self.popup, bg=PALETTE["surface"])
        frame.pack(padx=6, pady=6)
        # grid of buttons
        cols = 6
        for i, ch in enumerate(EMOJI_CHOICES):
            btn = tk.Button(
                frame, text=ch, bd=0, font=("Segoe UI Emoji", 14),
                bg=PALETTE["surface"], fg=PALETTE["text"],
                activebackground=PALETTE["card"], activeforeground=PALETTE["text"],
                command=lambda c=ch: self._insert(c, insert_target_widget)
            )
            btn.grid(row=i // cols, column=i % cols, padx=2, pady=2, sticky="nsew")
        # position near anchor
        x = anchor_widget.winfo_rootx()
        y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height()
        self.popup.geometry(f"+{x}+{y}")
        self.popup.bind("<FocusOut>", lambda _e: self.close())
        self.popup.focus_force()

    def _insert(self, ch, widget):
        try:
            if isinstance(widget, tk.Text):
                widget.insert("insert", ch)
                widget.focus_set()
            else:
                # CTkEntry / tk.Entry
                try:
                    cur = widget.index("insert")
                except Exception:
                    try:
                        cur = widget._entry.index("insert")
                    except Exception:
                        cur = len(widget.get())
                val = widget.get()
                new_val = val[:cur] + ch + val[cur:]
                widget.delete(0, tk.END)
                widget.insert(0, new_val)
                try:
                    widget.icursor(cur + len(ch))
                except Exception:
                    pass
                widget.focus_set()
        finally:
            self.close()

    def close(self):
        if self.popup:
            try:
                self.popup.destroy()
            except Exception:
                pass
            self.popup = None

# ---------- DM helpers ----------
def convo_id(a: str, b: str) -> str:
    return "|".join(sorted([a, b], key=str.lower))

def render_dm_sidebar():
    if dm_following_list is None:
        return
    for child in dm_following_list.winfo_children():
        child.destroy()
    if not current_user:
        ctk.CTkLabel(
            dm_following_list,
            text="Sign in to start messaging.",
            text_color=PALETTE["muted"],
            anchor="w",
        ).grid(sticky="we", padx=12, pady=12)
        return
    following = users.get(current_user, {}).get("following", [])
    if not following:
        ctk.CTkLabel(
            dm_following_list,
            text="You aren’t following anyone yet.",
            text_color=PALETTE["muted"],
            anchor="w",
        ).grid(sticky="we", padx=12, pady=12)
        return
    ctk.CTkLabel(
        dm_following_list,
        text="Following",
        text_color=PALETTE["muted"],
        anchor="w",
    ).grid(sticky="we", padx=12, pady=(12, 4))
    for username in sorted(following, key=str.lower):
        is_active = username == active_dm_user
        btn = ctk.CTkButton(
            dm_following_list,
            text=f"@{username}",
            anchor="w",
            fg_color=PALETTE["accent"] if is_active else "transparent",
            hover_color=PALETTE["accent_hover"],
            text_color="white" if is_active else PALETTE["text"],
            border_width=0 if is_active else 1,
            border_color=PALETTE["muted"],
            command=lambda u=username: open_dm_with(u),
        )
        btn.grid(sticky="we", padx=12, pady=4)

def render_dm():
    render_dm_sidebar()
    for child in dm_thread.winfo_children():
        child.destroy()
    dm_thread.grid_columnconfigure(0, weight=1)
    if not current_user or not active_dm_user:
        dm_header.configure(text="Direct Message")
        return
    dm_header.configure(text=f"DM with @{active_dm_user}")
    thread = messages.get(convo_id(current_user, active_dm_user), [])
    for i, msg in enumerate(thread):
        sender = msg.get("sender", "")
        is_me = sender == current_user
        row = ctk.CTkFrame(dm_thread, fg_color="transparent")
        row.grid(row=i, column=0, sticky="e" if is_me else "w", padx=8, pady=6)
        row.grid_columnconfigure(0, weight=1)
        container = ctk.CTkFrame(row, fg_color="transparent")
        container.grid(row=0, column=0, sticky="e" if is_me else "w")
        container.grid_columnconfigure(0, weight=0)
        container.grid_columnconfigure(1, weight=1)
        avatar_photo = load_profile_avatar(sender, size=44)
        avatar_col = 1 if is_me else 0
        bubble_col = 0 if is_me else 1
        avatar_pad = (12, 0) if is_me else (0, 12)
        bubble_pad = (0, 12) if is_me else (12, 0)
        row._image_refs = []
        if avatar_photo:
            avatar_label = tk.Label(
                container,
                image=avatar_photo,
                bd=0,
                bg=PALETTE["surface"],
                cursor="hand2",
            )
            avatar_label.grid(row=0, column=avatar_col, sticky="ne" if is_me else "nw", padx=avatar_pad)
            avatar_label.bind("<Button-1>", lambda _e, u=sender: open_profile(u))
            row._image_refs.append(avatar_photo)
        container.grid_columnconfigure(bubble_col, weight=1)
        bubble = ctk.CTkFrame(
            container,
            corner_radius=12,
            fg_color=PALETTE["accent"] if is_me else PALETTE["card"],
        )
        bubble.grid(row=0, column=bubble_col, sticky="e" if is_me else "w", padx=bubble_pad)
        bubble.grid_columnconfigure(0, weight=1)
        name_label = ctk.CTkLabel(
            bubble,
            text=f"@{sender}",
            text_color="white" if is_me else PALETTE["muted"],
            font=ctk.CTkFont(size=10, weight="bold"),
        )
        name_label.grid(row=0, column=0, sticky="w", padx=10, pady=(8, 2))
        name_label.configure(cursor="hand2")
        name_label.bind("<Button-1>", lambda _e, u=sender: open_profile(u))
        line_idx = 1
        text = msg.get("content", "")
        bubble._image_refs = []
        if text:
            tk.Label(
                bubble,
                text=text,
                wraplength=420,
                justify="left",
                bg=bubble.cget("fg_color"),
                fg="white" if is_me else PALETTE["text"],
                font=("Segoe UI Emoji", 11),
            ).grid(row=line_idx, column=0, sticky="w", padx=10, pady=(0, 4))
            line_idx += 1
        for att in msg.get("attachments", []):
            if isinstance(att, dict) and att.get("type") == "image":
                img = load_image_for_tk(att.get("path"), max_width=320)
                if img:
                    holder = tk.Label(
                        bubble,
                        image=img,
                        cursor="hand2",
                        bd=0,
                        bg=bubble.cget("fg_color"),
                    )
                    holder.grid(row=line_idx, column=0, sticky="w", padx=10, pady=(0, 6))
                    holder.bind("<Button-1>", lambda _e, p=att.get("path"): open_image(p))
                    bubble._image_refs.append(img)
                    line_idx += 1
        tk.Label(
            bubble,
            text=msg.get("time", ""),
            bg=bubble.cget("fg_color"),
            fg="#dbeafe" if is_me else PALETTE["muted"],
            font=("Segoe UI", 8),
        ).grid(row=line_idx, column=0, sticky="e" if is_me else "w", padx=10, pady=(0, 6))
        row._image_refs.extend(bubble._image_refs)

def open_dm_with(username: str):
    global active_dm_user, dm_draft_attachments
    if not require_login("send direct messages"):
        return
    if username == current_user:
        messagebox.showinfo("Direct message", "You cannot message yourself.")
        return
    active_dm_user = username
    dm_draft_attachments = []
    render_dm_sidebar()
    render_dm()
    show_frame("dm")

def open_dm_from_notification(username: str):
    global active_dm_user, dm_draft_attachments
    if not require_login("view messages"):
        return
    if username == current_user:
        return
    active_dm_user = username
    dm_draft_attachments = []
    render_dm_sidebar()
    render_dm()
    show_frame("dm")

def open_messages_page():
    global active_dm_user, dm_draft_attachments
    if not require_login("view messages"):
        return
    following = users.get(current_user, {}).get("following", [])
    if following:
        active_dm_user = active_dm_user if active_dm_user in following else following[0]
    else:
        active_dm_user = None
    dm_draft_attachments = []
    render_dm_sidebar()
    render_dm()
    show_frame("dm")

def send_dm():
    global dm_draft_attachments
    if not current_user or not active_dm_user:
        return
    message_content = dm_entry.get().strip()
    if not message_content and not dm_draft_attachments:
        messagebox.showwarning("Empty message", "Write something or attach an image.")
        return
    key = convo_id(current_user, active_dm_user)
    messages.setdefault(key, []).append({
        "sender": current_user,
        "content": message_content,
        "time": now_ts(),
        "attachments": [{"type": "image", "path": p} for p in dm_draft_attachments],
    })
    push_notification(
        active_dm_user,
        f"@{current_user} sent you a direct message",
        meta={"type": "dm", "from": current_user},
    )
    persist()
    dm_entry.delete(0, tk.END)
    dm_draft_attachments = []
    if dm_attach_preview:
        dm_attach_preview.configure(text="")
    render_dm()
    render_notifications()

# ---------- notifications, mentions, etc ----------
def render_notifications():
    if notifications_list is None:
        return
    for child in notifications_list.winfo_children():
        child.destroy()
    if not current_user:
        ctk.CTkLabel(
            notifications_list,
            text="Please sign in to view notifications.",
            text_color=PALETTE["muted"],
        ).grid(sticky="w", padx=20, pady=20)
        return
    notes = users[current_user].get("notifications", [])
    if not notes:
        ctk.CTkLabel(
            notifications_list,
            text="No notifications yet.",
            text_color=PALETTE["muted"],
        ).grid(sticky="w", padx=20, pady=20)
        return
    for note in reversed(notes):
        card = ctk.CTkFrame(notifications_list, corner_radius=12, fg_color=PALETTE["card"])
        card.grid(sticky="we", padx=0, pady=6)
        card.grid_columnconfigure(0, weight=1)

        meta = (note.get("meta") or {}) if current_user else {}
        dm_sender = meta.get("from") if meta.get("type") == "dm" else None

        message_label = ctk.CTkLabel(
            card,
            text=note.get("message", ""),
            wraplength=580,
            justify="left",
            text_color=PALETTE["text"],
        )
        message_label.grid(row=0, column=0, sticky="w", padx=16, pady=(12, 4))
        if dm_sender:
            message_label.configure(text_color=PALETTE["accent"], cursor="hand2")
            message_label.bind("<Button-1>", lambda _e, u=dm_sender: open_dm_from_notification(u))

        row_idx = 1
        if meta.get("type") == "follow":
            follower = meta.get("from")
            if follower and follower != current_user:
                already_following = follower in users[current_user].get("following", [])
                follow_back_btn = ctk.CTkButton(
                    card,
                    text="Follow back" if not already_following else "Following",
                    width=110,
                    fg_color=PALETTE["accent"] if not already_following else "transparent",
                    hover_color=PALETTE["accent_hover"],
                    text_color="white" if not already_following else PALETTE["muted"],
                    border_width=0 if not already_following else 1,
                    border_color=PALETTE["muted"],
                    state="disabled" if already_following else "normal",
                    command=lambda u=follower: follow_user(u),
                )
                follow_back_btn.grid(row=row_idx, column=0, sticky="w", padx=16, pady=(0, 6))
                row_idx += 1

        ctk.CTkLabel(
            card,
            text=note.get("time", ""),
            text_color=PALETTE["muted"],
            font=ctk.CTkFont(size=10),
        ).grid(row=row_idx, column=0, sticky="w", padx=16, pady=(0, 12))

def push_notification(username: str, message: str, *, meta: dict | None = None) -> bool:
    if username not in users:
        return False
    payload = {
        "message": message,
        "time": now_ts(),
    }
    if meta:
        payload["meta"] = meta
    users[username].setdefault("notifications", []).append(payload)
    return True

def clear_notifications():
    if not require_login("clear notifications"):
        return
    if current_user in users:
        users[current_user]["notifications"] = []
        persist()
        render_notifications()

def notify_mentions(author, text, context):
    mentioned = {name.lower() for name in re.findall(r"@(\w+)", text or "")}
    delivered = False
    for username in users:
        if username != author and username.lower() in mentioned:
            if push_notification(username, f"@{author} mentioned you in {context}"):
                delivered = True
    return delivered

def notify_followers(author):
    """Notify all followers that 'author' posted a new update."""
    flw = users.get(author, {}).get("followers", [])
    count = 0
    for follower in flw:
        if push_notification(follower, f"@{author} posted a new update"):
            count += 1
    return count

def submit_reply(post_idx, entry_var):
    global reply_input_target, reply_draft_attachments  # FIX: declare globals before use
    if not require_login("reply"):
        return
    reply_content = entry_var.get().strip()
    # Allow reply with images only, but require at least text or attachments
    if not reply_content and not reply_draft_attachments:
        messagebox.showwarning("Empty reply", "Please write something or attach an image before sending.")
        return
    posts[post_idx]["replies"].append(normalize_reply({
        "author": current_user,
        "content": reply_content,
        "created_at": now_ts(),
        "attachments": [{"type": "image", "path": p} for p in reply_draft_attachments]  # include attachments
    }))
    notify_mentions(current_user, reply_content, "a reply")
    persist()
    entry_var.set("")
    expanded_replies.add(post_idx)
    reply_input_target = None
    reply_draft_attachments = []  # clear after send
    render_feed()
    render_profile()

def start_reply_edit(post_idx, reply_idx):
    global editing_reply_target, editing_post_index, reply_input_target
    editing_post_index = None
    reply_input_target = None
    editing_reply_target = (post_idx, reply_idx)
    expanded_replies.add(post_idx)
    render_feed()
    render_profile()

def cancel_reply_edit():
    global editing_reply_target
    editing_reply_target = None
    render_feed()
    render_profile()

def apply_reply_edit(post_idx, reply_idx, textbox):
    global editing_reply_target
    reply_content = textbox.get("1.0", "end").strip()
    if not reply_content:
        messagebox.showwarning("Empty reply", "Reply cannot be empty.")
        return
    reply = posts[post_idx]["replies"][reply_idx]
    reply["content"] = reply_content
    reply["edited"] = True
    reply["edited_at"] = now_ts()
    persist()
    editing_reply_target = None
    expanded_replies.add(post_idx)
    render_feed()
    render_profile()

def delete_reply(post_idx, reply_idx):
    if not require_login("delete replies"):
        return
    reply = posts[post_idx]["replies"][reply_idx]
    if reply["author"] != current_user:
        messagebox.showerror("Not allowed", "You can only delete your own replies.")
        return
    if not messagebox.askyesno("Delete reply", "Are you sure you want to delete this reply?"):
        return
    posts[post_idx]["replies"].pop(reply_idx)
    persist()
    expanded_replies.add(post_idx)
    render_feed()
    render_profile()

def toggle_replies(post_idx: int) -> None:
    if post_idx in expanded_replies:
        expanded_replies.remove(post_idx)
    else:
        expanded_replies.add(post_idx)
    render_feed()
    render_profile()

def open_reply_box(post_idx: int | None) -> None:
    global reply_input_target, reply_draft_attachments
    reply_input_target = post_idx
    reply_draft_attachments = []
    render_feed()
    render_profile()

def render_post_card(container, idx, post, show_author_header=True):
    card = ctk.CTkFrame(container, corner_radius=16, fg_color=PALETTE["card"])
    card.grid(sticky="we", padx=0, pady=8)
    card.grid_columnconfigure(0, weight=1)
    card._image_refs = []  # NEW: init image refs holder to avoid AttributeError

    header_text = (
        f"@{post['author']}  ·  {post['created_at']}"
        if show_author_header else
        post["created_at"]
    )
    author_label = ctk.CTkLabel(
        card,
        text=header_text,
        font=ctk.CTkFont(size=12, weight="bold"),
        text_color=PALETTE["text"],
    )
    author_label.grid(row=0, column=0, sticky="w", padx=16, pady=(12, 4))
    # make author clickable
    author_label.configure(cursor="hand2")
    author_label.bind("<Button-1>", lambda _e, u=post["author"]: open_profile(u))

    if editing_post_index == idx and current_user == post["author"]:
        editor = ctk.CTkTextbox(card, height=110, fg_color=PALETTE["surface"], text_color=PALETTE["text"], border_width=0)
        editor.grid(row=1, column=0, sticky="we", padx=16, pady=(0, 8))
        editor.insert("1.0", post["content"])
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="e", padx=16, pady=(0, 12))
        ctk.CTkButton(
            btn_row,
            text="Save",
            width=70,
            fg_color=PALETTE["accent"],
            hover_color=PALETTE["accent_hover"],
            command=lambda i=idx, tb=editor: apply_edit(i, tb),
        ).grid(row=0, column=0, padx=4)
        ctk.CTkButton(
            btn_row,
            text="Cancel",
            width=70,
            fg_color="transparent",
            border_width=1,
            border_color=PALETTE["muted"],
            text_color=PALETTE["muted"],
            hover_color=PALETTE["surface"],
            command=cancel_edit,
        ).grid(row=0, column=1, padx=4)
    else:
        ctk.CTkLabel(
            card,
            text=post["content"],
            justify="left",
            wraplength=680,
            text_color=PALETTE["text"],
        ).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 6))
        if post.get("edited"):
            ctk.CTkLabel(
                card,
                text=f"* edited on {post.get('edited_at', '')}",
                text_color=PALETTE["muted"],
                font=ctk.CTkFont(size=10, slant="italic"),
            ).grid(row=2, column=0, sticky="w", padx=16, pady=(0, 6))

    # NEW: render post attachments (images)
    atts = post.get("attachments", [])
    if atts:
        att_frame = ctk.CTkFrame(card, fg_color="transparent")
        att_frame.grid(row=3, column=0, sticky="w", padx=16, pady=(0, 8))
        col = 0
        for att in atts:
            if isinstance(att, dict) and att.get("type") == "image":
                img = load_image_for_tk(att.get("path"), max_width=680)
                if img:
                    lbl = tk.Label(att_frame, image=img, bd=0, bg=PALETTE["card"], cursor="hand2")
                    lbl.grid(row=0, column=col, padx=(0, 8), pady=(4, 0), sticky="w")
                    lbl.bind("<Button-1>", lambda _e, p=att.get("path"): open_image(p))
                    # keep ref
                    card._image_refs.append(img)
                    col += 1

    # actions row moves down by one (keep order the same)
    actions = ctk.CTkFrame(card, fg_color="transparent")
    actions.grid(row=4, column=0, sticky="we", padx=16, pady=(0, 8))
    actions.grid_columnconfigure(0, weight=1)

    # post reactions (Like/Dislike)
    liked = bool(current_user and current_user in post.get("liked_by", []))
    disliked = bool(current_user and current_user in post.get("disliked_by", []))
    ctk.CTkButton(
        actions,
        text=f"Like ({post.get('likes', 0)})",
        width=90,
        fg_color=PALETTE["accent"] if liked else "transparent",
        hover_color=PALETTE["accent_hover"],
        text_color="white" if liked else PALETTE["muted"],
        border_width=0 if liked else 1,
        border_color=PALETTE["muted"],
        command=lambda i=idx: toggle_post_reaction(i, "like"),
    ).grid(row=0, column=10, padx=(0, 6), sticky="e")
    ctk.CTkButton(
        actions,
        text=f"Dislike ({post.get('dislikes', 0)})",
        width=90,
        fg_color=PALETTE["danger"] if disliked else "transparent",
        hover_color=PALETTE["danger_hover"],
        text_color="white" if disliked else PALETTE["muted"],
        border_width=0 if disliked else 1,
        border_color=PALETTE["muted"],
        command=lambda i=idx: toggle_post_reaction(i, "dislike"),
    ).grid(row=0, column=11, padx=(0, 0), sticky="e")

    replies = post.get("replies", [])
    if replies:
        ctk.CTkButton(
            actions,
            text=f"{'Hide' if idx in expanded_replies else 'View'} replies ({len(replies)})",
            width=130,
            fg_color="transparent",
            border_width=1,
            border_color=PALETTE["accent"],
            text_color=PALETTE["accent"],
            hover_color=PALETTE["accent_hover"],
            command=lambda i=idx: toggle_replies(i),
        ).grid(row=0, column=0, padx=(0, 6), sticky="w")

    if current_user:
        ctk.CTkButton(
            actions,
            text="Reply",
            width=70,
            fg_color="transparent",
            border_width=1,
            border_color=PALETTE["muted"],
            text_color=PALETTE["muted"],
            hover_color=PALETTE["surface"],
            command=lambda i=idx: open_reply_box(i),
        ).grid(row=0, column=1, padx=(0, 6), sticky="w")

    if current_user == post["author"]:
        ctk.CTkButton(
            actions,
            text="Edit",
            width=70,
            fg_color="transparent",
            border_width=1,
            border_color=PALETTE["accent"],
            text_color=PALETTE["accent"],
            hover_color=PALETTE["accent_hover"],
            command=lambda i=idx: start_edit(i),
        ).grid(row=0, column=2, padx=(0, 6))
        ctk.CTkButton(
            actions,
            text="Delete",
            width=70,
            fg_color=PALETTE["danger"],
            hover_color=PALETTE["danger_hover"],
            command=lambda i=idx: delete_post(i),
        ).grid(row=0, column=3, padx=(0, 6))

    if idx in expanded_replies:
        replies_frame = ctk.CTkFrame(card, fg_color=PALETTE["surface"], corner_radius=12)
        replies_frame.grid(row=5, column=0, sticky="we", padx=16, pady=(6, 8))
        replies_frame.grid_columnconfigure(0, weight=1)

        for r_idx, reply in enumerate(replies):
            r_card = ctk.CTkFrame(replies_frame, fg_color=PALETTE["card"], corner_radius=10)
            r_card.grid(sticky="we", padx=8, pady=4)
            r_card.grid_columnconfigure(0, weight=1)
            r_card._image_refs = []  # NEW: init image refs holder for replies
            reply_header = ctk.CTkLabel(
                r_card,
                text=f"@{reply['author']}  ·  {reply['created_at']}",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=PALETTE["text"],
            )
            reply_header.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))
            # make reply author clickable
            reply_header.configure(cursor="hand2")
            reply_header.bind("<Button-1>", lambda _e, u=reply["author"]: open_profile(u))

            if editing_reply_target == (idx, r_idx):
                editor = ctk.CTkTextbox(r_card, height=80, fg_color=PALETTE["surface"], text_color=PALETTE["text"], border_width=0)
                editor.grid(row=1, column=0, sticky="we", padx=12, pady=(0, 6))
                editor.insert("1.0", reply["content"])
                btns = ctk.CTkFrame(r_card, fg_color="transparent")
                btns.grid(row=2, column=0, sticky="e", padx=12, pady=(0, 10))
                ctk.CTkButton(
                    btns,
                    text="Save",
                    width=60,
                    fg_color=PALETTE["accent"],
                    hover_color=PALETTE["accent_hover"],
                    command=lambda p_idx=idx, rr_idx=r_idx, tb=editor: apply_reply_edit(p_idx, rr_idx, tb),
                ).grid(row=0, column=0, padx=4)
                ctk.CTkButton(
                    btns,
                    text="Cancel",
                    width=60,
                    fg_color="transparent",
                    border_width=1,
                    border_color=PALETTE["muted"],
                    text_color=PALETTE["muted"],
                    hover_color=PALETTE["surface"],
                    command=cancel_reply_edit,
                ).grid(row=0, column=1, padx=4)
            else:
                ctk.CTkLabel(
                    r_card,
                    text=reply["content"],
                    justify="left",
                    wraplength=640,
                    text_color=PALETTE["text"],
                ).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 4))
                if reply.get("edited"):
                    ctk.CTkLabel(
                        r_card,
                        text=f"* edited on {reply.get('edited_at', '')}",
                        text_color=PALETTE["muted"],
                        font=ctk.CTkFont(size=10, slant="italic"),
                    ).grid(row=2, column=0, sticky="w", padx=12, pady=(0, 6))
                if current_user == reply["author"]:
                    btns = ctk.CTkFrame(r_card, fg_color="transparent")
                    btns.grid(row=3, column=0, sticky="e", padx=12, pady=(0, 10))
                    ctk.CTkButton(
                        btns,
                        text="Edit",
                        width=60,
                        fg_color="transparent",
                        border_width=1,
                        border_color=PALETTE["accent"],
                        text_color=PALETTE["accent"],
                        hover_color=PALETTE["accent_hover"],
                        command=lambda p_idx=idx, rr_idx=r_idx: start_reply_edit(p_idx, rr_idx),
                    ).grid(row=0, column=0, padx=4)
                    ctk.CTkButton(
                        btns,
                        text="Delete",
                        width=60,
                        fg_color=PALETTE["danger"],
                        hover_color=PALETTE["danger_hover"],
                        command=lambda p_idx=idx, rr_idx=r_idx: delete_reply(p_idx, rr_idx),
                    ).grid(row=0, column=1, padx=4)

        composer = ctk.CTkFrame(replies_frame, fg_color="transparent")
        composer.grid(sticky="we", padx=8, pady=(6, 4))
        composer.grid_columnconfigure(0, weight=1)
        if reply_input_target == idx:
            reply_var = tk.StringVar()
            reply_entry = ctk.CTkEntry(
                composer,
                textvariable=reply_var,
                placeholder_text="Write a reply...",
                fg_color=PALETTE["surface"],
                text_color=PALETTE["text"],
                font=ctk.CTkFont(size=12, family="Segoe UI Emoji")  # emoji-friendly
            )
            reply_entry.grid(row=0, column=0, sticky="we", padx=(0, 6))
            mention.bind_entry(reply_entry)

            # NEW: reply composer toolbar
            tools = ctk.CTkFrame(composer, fg_color="transparent")
            tools.grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 2))
            # emoji
            emoji_btn = ctk.CTkButton(tools, text="Emoji", width=70,
                                      fg_color="transparent", border_width=1,
                                      border_color=PALETTE["muted"], text_color=PALETTE["muted"],
                                      hover_color=PALETTE["surface"],
                                      command=lambda w=reply_entry, b=tools: emoji_picker.open(b, w))
            emoji_btn.grid(row=0, column=0, padx=(0, 6))
            # attach image
            def _attach_reply_image():
                global reply_draft_attachments
                path = filedialog.askopenfilename(title="Attach image", filetypes=[
                    ("Images", "*.png;*.jpg;*.jpeg;*.gif;*.webp"), ("All files", "*.*")
                ])
                rel = copy_image_to_media(path)
                if rel:
                    reply_draft_attachments.append(rel)
                    preview.configure(text=f"Attached images: {len(reply_draft_attachments)}")
            attach_btn = ctk.CTkButton(tools, text="Attach image", width=110,
                                       fg_color="transparent", border_width=1,
                                       border_color=PALETTE["muted"], text_color=PALETTE["muted"],
                                       hover_color=PALETTE["surface"],
                                       command=_attach_reply_image)
            attach_btn.grid(row=0, column=1, padx=(0, 6))
            preview = ctk.CTkLabel(tools, text="", text_color=PALETTE["muted"])
            preview.grid(row=0, column=2)

            ctk.CTkButton(
                composer,
                text="Send",
                width=70,
                fg_color=PALETTE["accent"],
                hover_color=PALETTE["accent_hover"],
                command=lambda p_idx=idx, var=reply_var: submit_reply(p_idx, var),
            ).grid(row=0, column=1)
            ctk.CTkButton(
                composer,
                text="Cancel",
                width=70,
                fg_color="transparent",
                border_width=1,
                border_color=PALETTE["muted"],
                text_color=PALETTE["muted"],
                hover_color=PALETTE["surface"],
                command=lambda: open_reply_box(None),
            ).grid(row=0, column=2, padx=(6, 0))
        elif current_user:
            ctk.CTkButton(
                composer,
                text="Add reply",
                width=90,
                fg_color="transparent",
                border_width=1,
                border_color=PALETTE["muted"],
                text_color=PALETTE["muted"],
                hover_color=PALETTE["surface"],
                command=lambda i=idx: open_reply_box(i),
            ).grid(row=0, column=0, sticky="w")

def render_feed():
    clear_feed()
    if not posts:
        ctk.CTkLabel(feed, text="No posts yet. Create one above!", text_color=PALETTE["muted"]).grid(
            sticky="w", padx=20, pady=20
        )
        render_notifications()
        return
    for idx, post in sorted_posts():
        render_post_card(feed, idx, post)
    render_notifications()

def render_profile():
    for child in profile_posts.winfo_children():
        child.destroy()
    update_profile_avatar_display()
    if not current_user:
        profile_info.configure(text="Please sign in to view your profile.")
        render_notifications()
        return
    info = users[current_user]
    user_posts = [post for post in posts if post["author"] == current_user]
    total_likes = total_likes_for(current_user)
    followers_cnt = len(info.get("followers", []))
    following_cnt = len(info.get("following", []))
    profile_info.configure(
        text=f"Username: @{current_user}\n"
             f"Registered: {info.get('registered_at', 'Unknown')}\n"
             f"Followers: {followers_cnt}  ·  Following: {following_cnt}\n"
             f"Total posts: {len(user_posts)}\n"
             f"Total likes received: {total_likes}"
    )
    if not user_posts:
        ctk.CTkLabel(profile_posts, text="You haven't posted anything yet!", text_color=PALETTE["muted"]).grid(
            sticky="w", padx=20, pady=20
        )
    else:
        for idx, post in enumerate(posts):
            if post["author"] == current_user:
                render_post_card(profile_posts, idx, post, show_author_header=False)
    render_notifications()

def require_login(action="perform this action"):
    if not current_user:
        messagebox.showinfo("Sign in required", f"You must sign in to {action}.")
        return False
    return True

# ---------- UI setup ----------
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

PALETTE = {
    "bg": "#0f172a",
    "surface": "#111b2e",
    "card": "#18263f",
    "accent": "#4c8dff",
    "accent_hover": "#3b6dd6",
    "danger": "#ef4444",
    "danger_hover": "#dc2626",
    "muted": "#94a3b8",
    "text": "#e2e8f0"
}

def style_button(button, bold=False):
    button.configure(
        fg_color=PALETTE["accent"],
        hover_color=PALETTE["accent_hover"],
        text_color="white",
        corner_radius=20,
        font=ctk.CTkFont(size=14, weight="bold" if bold else "normal"),
        border_width=0
    )

root = ctk.CTk()
root.title("DevEcho")
root.geometry("900x600")
root.minsize(720, 520)
root.configure(fg_color=PALETTE["bg"])
root.grid_rowconfigure(1, weight=1)
root.grid_columnconfigure(0, weight=1)

emoji_picker = EmojiPicker(root)
topbar = ctk.CTkFrame(root, height=60, corner_radius=12, fg_color=PALETTE["surface"])
topbar.grid(row=0, column=0, sticky="we")
topbar.grid_columnconfigure(0, weight=1)

title_lbl = ctk.CTkLabel(
    topbar,
    text="DevEcho",
    font=ctk.CTkFont(size=22, weight="bold"),
    text_color=PALETTE["text"]
)
title_lbl.grid(row=0, column=0, padx=16, pady=16, sticky="w")

home_btn = ctk.CTkButton(topbar, text="Home", width=100)
home_btn.grid(row=0, column=1, padx=(0, 16), pady=16)

profile_btn = ctk.CTkButton(topbar, text="Profile", width=100)
profile_btn.grid(row=0, column=2, padx=(0, 16), pady=16)

signin_btn = ctk.CTkButton(topbar, text="Sign in", width=100)
signin_btn.grid(row=0, column=3, padx=(0, 16), pady=16)

notifications_btn = ctk.CTkButton(topbar, text="Notifications", width=120)
notifications_btn.grid(row=0, column=4, padx=(0, 16), pady=16)

messages_btn = ctk.CTkButton(topbar, text="Messages", width=120)
messages_btn.grid(row=0, column=5, padx=(0, 16), pady=16)

style_button(home_btn)
style_button(profile_btn)
style_button(signin_btn, bold=True)
style_button(notifications_btn)
style_button(messages_btn)

content = ctk.CTkFrame(root, corner_radius=12, fg_color="transparent")
content.grid(row=1, column=0, sticky="nswe", padx=16, pady=(0, 16))
content.grid_rowconfigure(0, weight=1)
content.grid_columnconfigure(0, weight=1)

home_frame = ctk.CTkFrame(content, corner_radius=12, fg_color="transparent")
home_frame.grid(row=0, column=0, sticky="nswe")
frames["home"] = home_frame
home_frame.grid_rowconfigure(2, weight=1)
home_frame.grid_columnconfigure(0, weight=1)

user_status_lbl = ctk.CTkLabel(home_frame, text="Signed out", anchor="w", text_color=PALETTE["muted"])
user_status_lbl.grid(row=0, column=0, sticky="we", padx=16, pady=(16, 8))

post_box = ctk.CTkFrame(home_frame, corner_radius=16, fg_color=PALETTE["surface"])
post_box.grid(row=1, column=0, sticky="we", padx=16, pady=8)
post_box.grid_columnconfigure(0, weight=1)

post_text = scrolledtext.ScrolledText(post_box, height=4, wrap="word", font=("Segoe UI Emoji", 11))
post_text.grid(row=0, column=0, sticky="nswe", padx=12, pady=12)
post_text.configure(bg=PALETTE["card"], fg=PALETTE["text"], insertbackground=PALETTE["text"], relief="flat", borderwidth=0)

post_btn = ctk.CTkButton(post_box, text="Post", width=120)
post_btn.grid(row=0, column=1, padx=(0, 12), pady=12, sticky="ns")
post_btn.configure(fg_color=PALETTE["accent"], hover_color=PALETTE["accent_hover"])

# NEW: toolbar row for post composer
post_tools = ctk.CTkFrame(post_box, fg_color="transparent")
post_tools.grid(row=1, column=0, columnspan=2, sticky="we", padx=12, pady=(0, 10))
post_tools.grid_columnconfigure(0, weight=0)
post_tools.grid_columnconfigure(1, weight=0)
post_tools.grid_columnconfigure(2, weight=1)

post_emoji_btn = ctk.CTkButton(post_tools, text="Emoji", width=70,
                               fg_color="transparent", border_width=1,
                               border_color=PALETTE["muted"], text_color=PALETTE["muted"],
                               hover_color=PALETTE["surface"],
                               command=lambda b=post_tools: emoji_picker.open(b, post_text))
post_emoji_btn.grid(row=0, column=0, padx=(0, 6))

def _attach_post_image():
    global post_draft_attachments
    path = filedialog.askopenfilename(title="Attach image", filetypes=[
        ("Images", "*.png;*.jpg;*.jpeg;*.gif;*.webp"), ("All files", "*.*")
    ])
    rel = copy_image_to_media(path)
    if rel:
        post_draft_attachments.append(rel)
        post_attach_preview.configure(text=f"Attached images: {len(post_draft_attachments)}")

post_attach_btn = ctk.CTkButton(post_tools, text="Attach image", width=110,
                                fg_color="transparent", border_width=1,
                                border_color=PALETTE["muted"], text_color=PALETTE["muted"],
                                hover_color=PALETTE["surface"],
                                command=_attach_post_image)
post_attach_btn.grid(row=0, column=1, padx=(0, 6))

post_attach_preview = ctk.CTkLabel(post_tools, text="", text_color=PALETTE["muted"])
post_attach_preview.grid(row=0, column=2, sticky="w")

feed = ctk.CTkScrollableFrame(home_frame, corner_radius=16, fg_color="transparent")
feed.grid(row=2, column=0, sticky="nswe", padx=16, pady=(0, 16))
feed.grid_columnconfigure(0, weight=1)

notifications_frame = ctk.CTkFrame(content, corner_radius=12, fg_color="transparent")
notifications_frame.grid(row=0, column=0, sticky="nswe")
notifications_frame.grid_rowconfigure(1, weight=1)
notifications_frame.grid_columnconfigure(0, weight=1)
frames["notifications"] = notifications_frame

notifications_header = ctk.CTkFrame(notifications_frame, fg_color="transparent")
notifications_header.grid(row=0, column=0, sticky="we", padx=16, pady=(16, 8))
notifications_header.grid_columnconfigure(0, weight=1)
ctk.CTkLabel(
    notifications_header,
    text="Notifications",
    font=ctk.CTkFont(size=20, weight="bold"),
    text_color=PALETTE["text"],
).grid(row=0, column=0, sticky="w")
ctk.CTkButton(
    notifications_header,
    text="Clear all",
    width=90,
    fg_color=PALETTE["danger"],
    hover_color=PALETTE["danger_hover"],
    command=clear_notifications,
).grid(row=0, column=1, padx=(8, 0))

notifications_list = ctk.CTkScrollableFrame(notifications_frame, corner_radius=8)
notifications_list.grid(row=1, column=0, sticky="nswe", padx=16, pady=(0, 16))
notifications_list.grid_columnconfigure(0, weight=1)

profile_frame = ctk.CTkFrame(content, corner_radius=12, fg_color="transparent")
profile_frame.grid(row=0, column=0, sticky="nswe")
frames["profile"] = profile_frame
profile_frame.grid_rowconfigure(3, weight=1)
profile_frame.grid_columnconfigure(0, weight=1)

profile_header = ctk.CTkLabel(profile_frame, text="Profile", font=ctk.CTkFont(size=20, weight="bold"))
profile_header.grid(row=0, column=0, sticky="w", padx=16, pady=(16, 6))
profile_header.configure(text_color=PALETTE["text"])

profile_info = ctk.CTkLabel(profile_frame, text="", justify="left")
profile_info.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 10))
profile_info.configure(text_color=PALETTE["muted"])

profile_avatar_panel = ctk.CTkFrame(profile_frame, fg_color="transparent")
profile_avatar_panel.grid(row=2, column=0, sticky="w", padx=16, pady=(0, 12))
profile_avatar_panel.grid_columnconfigure(1, weight=1)
profile_avatar_label = tk.Label(profile_avatar_panel, bg=PALETTE["surface"], bd=0)
profile_avatar_label.grid(row=0, column=0, rowspan=2, sticky="w")
profile_change_pic_btn = ctk.CTkButton(
    profile_avatar_panel,
    text="Change picture",
    width=140,
    command=change_profile_picture,
)
profile_change_pic_btn.grid(row=0, column=1, padx=(12, 0), sticky="sw")

profile_posts = ctk.CTkScrollableFrame(profile_frame, corner_radius=8)
profile_posts.grid(row=3, column=0, sticky="nswe", padx=16, pady=(0, 16))
profile_posts.grid_columnconfigure(0, weight=1)
profile_avatar_panel.grid_remove()
profile_change_pic_btn.configure(state="disabled")

# inspect (other user's) profile frame
inspect_profile_frame = ctk.CTkFrame(content, corner_radius=12, fg_color="transparent")
inspect_profile_frame.grid(row=0, column=0, sticky="nswe")
frames["inspect_profile"] = inspect_profile_frame
inspect_profile_frame.grid_rowconfigure(2, weight=1)
inspect_profile_frame.grid_columnconfigure(0, weight=1)
inspect_profile_frame.grid_columnconfigure(1, weight=0)  # NEW
inspect_profile_frame.grid_columnconfigure(2, weight=0)  # NEW

inspect_header = ctk.CTkLabel(inspect_profile_frame, text="Profile", font=ctk.CTkFont(size=20, weight="bold"))
inspect_header.grid(row=0, column=0, sticky="w", padx=16, pady=(16, 6))
inspect_header.configure(text_color=PALETTE["text"])

inspect_info = ctk.CTkLabel(inspect_profile_frame, text="", justify="left")
inspect_info.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 10))
inspect_info.configure(text_color=PALETTE["muted"])

# NEW: Direct Message button
inspect_message_btn = ctk.CTkButton(
    inspect_profile_frame,
    text="Message",
    width=110,
    fg_color=PALETTE["accent"],
    hover_color=PALETTE["accent_hover"],
    command=lambda: None  # configured in render_inspected_profile
)
inspect_message_btn.grid(row=0, column=1, sticky="e", padx=(0, 8), pady=(16, 6))

# Move Follow button to column 2 (rightmost)
inspect_follow_btn = ctk.CTkButton(inspect_profile_frame, text="Follow", width=110)
inspect_follow_btn.grid(row=0, column=2, sticky="e", padx=16, pady=(16, 6))
inspect_follow_btn.configure(fg_color=PALETTE["accent"], hover_color=PALETTE["accent_hover"])

inspect_posts = ctk.CTkScrollableFrame(inspect_profile_frame, corner_radius=8)
inspect_posts.grid(row=2, column=0, columnspan=3, sticky="nswe", padx=16, pady=(0, 16))
inspect_posts.grid_columnconfigure(0, weight=1)

# NEW: DM frame
dm_frame = ctk.CTkFrame(content, corner_radius=12, fg_color="transparent")
dm_frame.grid(row=0, column=0, sticky="nswe")
frames["dm"] = dm_frame
dm_frame.grid_rowconfigure(2, weight=1)
dm_frame.grid_columnconfigure(0, weight=0)
dm_frame.grid_columnconfigure(1, weight=1)

dm_header_row = ctk.CTkFrame(dm_frame, fg_color="transparent")
dm_header_row.grid(row=0, column=0, columnspan=2, sticky="we", padx=16, pady=(16, 6))
dm_header_row.grid_columnconfigure(0, weight=1)

dm_header = ctk.CTkLabel(dm_header_row, text="Direct Message", font=ctk.CTkFont(size=20, weight="bold"), text_color=PALETTE["text"])
dm_header.grid(row=0, column=0, sticky="w")

dm_back_btn = ctk.CTkButton(dm_header_row, text="Back", width=70,
                            fg_color="transparent", border_width=1,
                            border_color=PALETTE["muted"], text_color=PALETTE["muted"],
                            hover_color=PALETTE["surface"],
                            command=lambda: show_frame("inspect_profile"))
dm_back_btn.grid(row=0, column=1, padx=(8, 0))

dm_following_list = ctk.CTkScrollableFrame(dm_frame, corner_radius=10)
dm_following_list.grid(row=2, column=0, rowspan=2, sticky="nswe", padx=(16, 8), pady=(0, 16))
dm_following_list.grid_columnconfigure(0, weight=1)

dm_thread = ctk.CTkScrollableFrame(dm_frame, corner_radius=10, fg_color=PALETTE["surface"])
dm_thread.grid(row=2, column=1, sticky="nswe", padx=(0, 16), pady=(0, 8))
dm_thread.grid_columnconfigure(0, weight=1)
dm_thread.grid_columnconfigure(1, weight=1)

dm_composer = ctk.CTkFrame(dm_frame, fg_color="transparent")
dm_composer.grid(row=3, column=1, sticky="we", padx=(0, 16), pady=(0, 16))
dm_composer.grid_columnconfigure(0, weight=1)

dm_entry = ctk.CTkEntry(dm_composer, placeholder_text="Write a message...", fg_color=PALETTE["surface"], text_color=PALETTE["text"])
dm_entry.grid(row=0, column=0, sticky="we", padx=(0, 6))

dm_send_btn = ctk.CTkButton(dm_composer, text="Send", width=70, fg_color=PALETTE["accent"], hover_color=PALETTE["accent_hover"], command=send_dm)
dm_send_btn.grid(row=0, column=1)

dm_tools = ctk.CTkFrame(dm_composer, fg_color="transparent")
dm_tools.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

dm_emoji_btn = ctk.CTkButton(dm_tools, text="Emoji", width=70,
                             fg_color="transparent", border_width=1,
                             border_color=PALETTE["muted"], text_color=PALETTE["muted"],
                             hover_color=PALETTE["surface"],
                             command=lambda b=dm_tools: emoji_picker.open(b, dm_entry))
dm_emoji_btn.grid(row=0, column=0, padx=(0, 6))

def _attach_dm_image():
    global dm_draft_attachments
    path = filedialog.askopenfilename(title="Attach image", filetypes=[
        ("Images", "*.png;*.jpg;*.jpeg;*.gif;*.webp"), ("All files", "*.*")
    ])
    rel = copy_image_to_media(path)
    if rel:
        dm_draft_attachments.append(rel)
        dm_attach_preview.configure(text=f"Attached images: {len(dm_draft_attachments)}")

dm_attach_btn = ctk.CTkButton(dm_tools, text="Attach image", width=110,
                              fg_color="transparent", border_width=1,
                              border_color=PALETTE["muted"], text_color=PALETTE["muted"],
                              hover_color=PALETTE["surface"],
                              command=_attach_dm_image)
dm_attach_btn.grid(row=0, column=1, padx=(0, 6))

dm_attach_preview = ctk.CTkLabel(dm_tools, text="", text_color=PALETTE["muted"])
dm_attach_preview.grid(row=0, column=2)

# ---------- profile inspection / follow ----------
def open_profile(username):
    global inspected_user
    inspected_user = username    
    render_inspected_profile()
    show_frame("inspect_profile")

def render_inspected_profile():
    for child in inspect_posts.winfo_children():
        child.destroy()
    if not inspected_user:
        inspect_info.configure(text="No profile selected.")
        return
    if inspected_user not in users:
        inspect_info.configure(text="User not found.")
        return

    info = users[inspected_user]
    user_posts = [post for post in posts if post["author"] == inspected_user]
    tlikes = total_likes_for(inspected_user)
    inspect_header.configure(text=f"@{inspected_user}")
    inspect_info.configure(
        text=f"Username: @{inspected_user}\n"
             f"Registered: {info.get('registered_at', 'Unknown')}\n"
             f"Followers: {len(info.get('followers', []))}  ·  Following: {len(info.get('following', []))}\n"
             f"Total posts: {len(user_posts)}\n"
             f"Total likes received: {tlikes}"
    )
    # configure follow and message buttons
    if not current_user or inspected_user == current_user:
        inspect_follow_btn.configure(state="disabled", text="Follow")
        inspect_message_btn.configure(state="disabled")
    else:
        am_following = current_user in info.get("followers", [])
        if am_following:
            inspect_follow_btn.configure(text="Unfollow", state="normal",
                                         fg_color=PALETTE["danger"], hover_color=PALETTE["danger_hover"],
                                         command=lambda u=inspected_user: unfollow_user(u))
        else:
            inspect_follow_btn.configure(text="Follow", state="normal",
                                         fg_color=PALETTE["accent"], hover_color=PALETTE["accent_hover"],
                                         command=lambda u=inspected_user: follow_user(u))
        # NEW: enable message button
        inspect_message_btn.configure(state="normal", command=lambda u=inspected_user: open_dm_with(u))
    # posts
    if not user_posts:
        ctk.CTkLabel(inspect_posts, text="No posts yet.", text_color=PALETTE["muted"]).grid(
            sticky="w", padx=20, pady=20
        )
    else:
        for idx, post in enumerate(posts):
            if post["author"] == inspected_user:
                render_post_card(inspect_posts, idx, post, show_author_header=False)

def follow_user(username):
    if not require_login("follow users"):
        return
    if username == current_user:
        return
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
    persist()
    render_inspected_profile()
    render_dm_sidebar()
    render_notifications()

def unfollow_user(username):
    if not require_login("unfollow users"):
        return
    if username == current_user:
        return
    me = users.get(current_user, {})
    target = users.get(username, {})
    me.setdefault("following", [])
    target.setdefault("followers", [])
    if username in me["following"]:
        me["following"].remove(username)
    if current_user in target["followers"]:
        target["followers"].remove(current_user)
    persist()
    render_inspected_profile()
    render_dm_sidebar()
    render_notifications()

def sign_out():
    global current_user
    if not current_user:
        return
    if messagebox.askyesno("Sign out", "Do you really want to sign out?"):
        current_user = None
        refresh_ui()
        render_dm_sidebar()
        show_frame("home")

# ---------- auth dialog ----------
auth_window = ctk.CTkToplevel(root)
auth_window.withdraw()
auth_window.title("Sign in / Register")
auth_window.geometry("360x260")
auth_window.attributes("-topmost", True)
auth_window.resizable(False, False)

auth_mode = tk.StringVar(value="login")

auth_title = ctk.CTkLabel(auth_window, text="Sign in", font=ctk.CTkFont(size=18, weight="bold"))
auth_title.pack(pady=(18, 12))

ctk.CTkLabel(auth_window, text="Username").pack(anchor="w", padx=24)
auth_username = ctk.CTkEntry(auth_window, width=300)
auth_username.pack(padx=24, pady=(0, 12))

ctk.CTkLabel(auth_window, text="Password").pack(anchor="w", padx=24)
auth_password = ctk.CTkEntry(auth_window, width=300, show="*")
auth_password.pack(padx=24, pady=(0, 16))

auth_submit = ctk.CTkButton(auth_window, text="Login", width=200)
auth_submit.pack(pady=(0, 8))

auth_switch = ctk.CTkButton(auth_window, text="Switch to register", width=200)
auth_switch.pack()

def show_auth(mode="login"):
    auth_mode.set(mode)
    auth_title.configure(text="Sign in" if mode == "login" else "Register")
    auth_submit.configure(text="Login" if mode == "login" else "Register")
    auth_switch.configure(text="Switch to register" if mode == "login" else "Switch to login")
    auth_username.delete(0, tk.END)
    auth_password.delete(0, tk.END)
    auth_window.deiconify()
    auth_window.lift()
    auth_window.grab_set()

def hide_auth_window():
    try:
        auth_window.grab_release()
    except Exception:
        pass
    auth_window.withdraw()
    root.focus_set()

def handle_auth():
    global current_user
    username = auth_username.get().strip()
    password = auth_password.get().strip()
    if not username or not password:
        messagebox.showwarning("Missing info", "Please provide username and password.")
        return
    if auth_mode.get() == "login":
        if username not in users or users[username]["password"] != password:
            messagebox.showerror("Login failed", "Invalid username or password.")
            return
        users[username].setdefault("profile_picture", None)
        users[username].setdefault("following", [])
        users[username].setdefault("followers", [])
        current_user = username
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
        current_user = username
    hide_auth_window()
    refresh_ui()

def switch_auth_mode():
    show_auth("register" if auth_mode.get() == "login" else "login")

auth_submit.configure(command=handle_auth)
auth_switch.configure(command=switch_auth_mode)
auth_window.protocol("WM_DELETE_WINDOW", hide_auth_window)

# ---------- feed rendering ----------
def clear_feed():
    for child in feed.winfo_children():
        child.destroy()

def clear_notifications():
    if not require_login("clear notifications"):
        return
    if current_user in users:
        users[current_user]["notifications"] = []
        persist()
        render_notifications()

def sorted_posts():
    return sorted(enumerate(posts), key=lambda item: item[1]["created_at"], reverse=True)

def start_edit(idx):
    global editing_post_index, editing_reply_target, reply_input_target
    editing_reply_target = None
    reply_input_target = None
    editing_post_index = idx
    render_feed()
    render_profile()

def cancel_edit():
    global editing_post_index
    editing_post_index = None
    render_feed()
    render_profile()

def apply_edit(idx, textbox):
    global editing_post_index
    post_content = textbox.get("1.0", "end").strip()
    if not post_content:
        messagebox.showwarning("Empty", "Post content cannot be empty.")
        return
    posts[idx]["content"] = post_content
    posts[idx]["edited"] = True
    posts[idx]["edited_at"] = now_ts()
    persist()
    editing_post_index = None
    render_feed()
    render_profile()

# ---------- reactions (likes/dislikes) ----------
def _toggle_reaction(entity, username, kind):
    entity.setdefault("liked_by", [])
    entity.setdefault("disliked_by", [])
    # normalize types
    if not isinstance(entity["liked_by"], list): entity["liked_by"] = []
    if not isinstance(entity["disliked_by"], list): entity["disliked_by"] = []
    liked = entity["liked_by"]
    disliked = entity["disliked_by"]
    if kind == "like":
        if username in liked:
            liked.remove(username)
        else:
            liked.append(username)
            if username in disliked:
                disliked.remove(username)
    else:  # dislike
        if username in disliked:
            disliked.remove(username)
        else:
            disliked.append(username)
            if username in liked:
                liked.remove(username)
    entity["likes"] = len(liked)
    entity["dislikes"] = len(disliked)
    return entity

def toggle_post_reaction(post_idx, kind):
    if not require_login(f"{kind} a post"):
        return
    _toggle_reaction(posts[post_idx], current_user, kind)
    persist()
    render_feed()
    render_profile()

def toggle_reply_reaction(post_idx, reply_idx, kind):
    if not require_login(f"{kind} a reply"):
        return
    _toggle_reaction(posts[post_idx]["replies"][reply_idx], current_user, kind)
    persist()
    render_feed()
    render_profile()

def total_likes_for(username):
    return sum(len(p.get("liked_by", [])) for p in posts if p.get("author") == username) + \
           sum(len(r.get("liked_by", [])) for p in posts for r in p.get("replies", []) if r.get("author") == username)

# --- replace old MentionHelper with this MentionManager ---
class MentionManager:
    def __init__(self, root, get_usernames):
        self.root = root
        self.get_usernames = get_usernames
        self.popup = None
        self.listbox = None
        self.context = None  # {"widget": widget}
        self.is_selecting = False  # prevent premature hide while clicking

    def bind_text(self, widget):
        widget.bind("<KeyRelease>", self._on_key, add="+")
        widget.bind("<FocusOut>", lambda _e, w=widget: self._on_focus_out(w), add="+")
        widget.bind("<Escape>", lambda _e: self.hide(), add="+")

    def bind_entry(self, widget):
        widget.bind("<KeyRelease>", self._on_key, add="+")
        widget.bind("<FocusOut>", lambda _e, w=widget: self._on_focus_out(w), add="+")
        widget.bind("<Escape>", lambda _e: self.hide(), add="+")

    # ---------- events ----------
    def _on_key(self, event):
        editor = event.widget
        # if popup currently has focus, ignore editor key events
        try:
            if self.popup and self._is_in_popup(self.root.focus_get()):
                return
        except Exception:
            pass

        ctx = self._extract_context(editor)
        if not ctx:
            self.hide()
            return

        matches = self._matches(ctx["prefix"])
        if not matches:
            self.hide()
            return

        self.context = {"widget": editor}
        self._ensure_popup(editor)
        self._fill_popup(matches)
        self._reposition(editor)

    def _on_focus_out(self, widget):
        # delay to allow mouse click in popup to land
        widget.after(120, lambda: self._maybe_hide(widget))

    # ---------- helpers ----------
    def _extract_context(self, widget):
        try:
            if isinstance(widget, tk.Text):
                line = widget.get("insert linestart", "insert")
                m = re.search(r"@(\w*)$", line)
                if not m:
                    return None
                return {"type": "text", "prefix": m.group(1)}
            else:
                # CTkEntry/tk.Entry
                try:
                    caret = widget.index("insert")
                except Exception:
                    try:
                        caret = widget._entry.index("insert")
                    except Exception:
                        caret = len(widget.get())
                before = widget.get()[:caret]
                m = re.search(r"@(\w*)$", before)
                if not m:
                    return None
                return {"type": "entry", "prefix": m.group(1)}
        except Exception:
            return None

    def _matches(self, prefix):
        prefix = (prefix or "").lower()
        return [
            n for n in sorted(self.get_usernames(), key=str.lower)
            if n and n != current_user and n.lower().startswith(prefix)
        ][:8]

    def _ensure_popup(self, editor):
        if self.popup and self.listbox and self.popup.winfo_exists():
            return
        self.popup = tk.Toplevel(self.root)
        self.popup.overrideredirect(True)
        try:
            self.popup.attributes("-topmost", True)
        except Exception:
            pass
        # outer bg = accent border; inner frame is the surface card
        self.popup.configure(bg=PALETTE["accent"])

        container = tk.Frame(self.popup, bg=PALETTE["surface"], bd=0, highlightthickness=0)
        container.pack(fill="both", expand=True, padx=1, pady=1)

        header = tk.Label(
            container,
            text="Mentions",
            bg=PALETTE["surface"],
            fg=PALETTE["muted"],
            font=("Segoe UI", 9, "bold"),
            anchor="w"
        )
        header.pack(fill="x", padx=8, pady=(6, 2))

        inner = tk.Frame(container, bg=PALETTE["surface"], bd=0, highlightthickness=0)
        inner.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        self.listbox = tk.Listbox(
            inner,
            activestyle="none",
            highlightthickness=0,
            bd=0,
            relief="flat",
            font=("Segoe UI", 11),
            height=6,  # will be adjusted dynamically in _fill_popup
            selectbackground=PALETTE["accent"],
            selectforeground="white",
            bg=PALETTE["surface"],
            fg=PALETTE["text"],
        )
        self.listbox.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(inner, orient="vertical", command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=scrollbar.set)

        # bindings for selection
        def select_under_mouse(e=None):
            self.is_selecting = True
            try:
                idx = self.listbox.nearest(e.y if e else 0)
                if 0 <= idx < self.listbox.size():
                    label = self.listbox.get(idx)
                    username = _label_username(label)
                    self._insert_mention(username)
            finally:
                editor.after(0, lambda: setattr(self, "is_selecting", False))
            return "break"

        def select_current(_e=None):
            self.is_selecting = True
            try:
                sel = self.listbox.curselection()
                if not sel and self.listbox.size() > 0:
                    sel = (0,)
                if sel:
                    label = self.listbox.get(sel[0])
                    username = _label_username(label)
                    self._insert_mention(username)
            finally:
                editor.after(0, lambda: setattr(self, "is_selecting", False))
            return "break"

        def hover_highlight(e=None):
            if self.listbox.size() == 0:
                return
            idx = self.listbox.nearest(e.y if e else 0)
            if 0 <= idx < self.listbox.size():
                self.listbox.selection_clear(0, "end")
                self.listbox.selection_set(idx)

        # helper: turn a listbox label like "  @Ali" into "Ali"
        def _label_username(label: str) -> str:
            label = label.strip()
            m = re.search(r'@?(\w+)$', label)
            return m.group(1) if m else label.lstrip("@ ").strip()

        self.listbox.bind("<Motion>", hover_highlight)
        self.listbox.bind("<Button-1>", select_under_mouse)
        self.listbox.bind("<ButtonRelease-1>", select_under_mouse, add="+")
        self.listbox.bind("<Return>", select_current)
        self.listbox.bind("<Escape>", lambda _e: self.hide())

    def _fill_popup(self, options):
        self.listbox.delete(0, "end")
        # indent items a bit for nicer look
        for name in options:
            self.listbox.insert("end", f"  @{name}")
        # auto-select first item
        if self.listbox.size() > 0:
                       self.listbox.selection_set(0)
        # compact height: up to 6 visible rows
        self.listbox.configure(height=min(6, max(1, self.listbox.size())))

    def _reposition(self, editor):
        x, y = self._popup_xy(editor)
        # small offset so the border is visible and not overlapping the caret
        self.popup.geometry(f"+{x}+{y+2}")
        self.popup.lift()

    def _popup_xy(self, widget):
        if isinstance(widget, tk.Text):
            bbox = widget.bbox("insert")
            if bbox:
                return widget.winfo_rootx() + bbox[0], widget.winfo_rooty() + bbox[1] + bbox[3]
        return widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height()

    # ---------- insertion ----------
    def _insert_mention(self, username):
        if not self.context:
            self.hide()
            return
        w = self.context["widget"]
        mention = f"@{username} "
        try:
            if isinstance(w, tk.Text):
                line = w.get("insert linestart", "insert")
                m = re.search(r"@(\w*)$", line)
                if m:
                    frag = len(m.group(1)) + 1
                    start = w.index(f"insert-{frag}c")
                    w.delete(start, "insert")
                    w.insert(start, mention)
                    w.mark_set("insert", w.index(f"{start}+{len(mention)}c"))
                else:
                    w.insert("insert", mention)
                w.see("insert")
                w.focus_set()
            else:
                # CTkEntry/tk.Entry
                try:
                    caret = w.index("insert")
                except Exception:
                    try:
                        caret = w._entry.index("insert")
                    except Exception:
                        caret = len(w.get())
                value = w.get()
                before = value[:caret]
                m = re.search(r"@(\w*)$", before)
                if m:
                    start = caret - (len(m.group(1)) + 1)
                    end = caret
                else:
                    start = end = caret
                new_val = value[:start] + mention + value[end:]
                try:
                    w.delete(0, tk.END)
                    w.insert(0, new_val)
                    try:
                        w.icursor(start + len(mention))
                    except Exception:
                        backend = getattr(w, "entry", None) or getattr(w, "_entry", None)
                        if backend:
                            backend.icursor(start + len(mention))
                except Exception:
                    backend = getattr(w, "entry", None) or getattr(w, "_entry", None)
                    if backend:
                        backend.delete(0, tk.END)
                        backend.insert(0, new_val)
                        try:
                            backend.icursor(start + len(mention))
                        except Exception:
                            pass
                w.focus_set()
        finally:
            self.hide()

    # ---------- hide ----------
    def _maybe_hide(self, editor):
        if self.is_selecting:
            # try again shortly after selection finishes
            editor.after(80, lambda: self._maybe_hide(editor))
            return
        try:
            focus_w = editor.focus_get() or (editor.tk.focus_get() if hasattr(editor, "tk") else None)
        except Exception:
            focus_w = None
        # keep popup if mouse is over it or focus is inside it

        if self._pointer_in_popup() or (focus_w and self._is_in_popup(focus_w)):
            return
        self.hide()

    def _pointer_in_popup(self):
        if not self.popup:
            return False
        try:
            px, py = self.popup.winfo_pointerx(), self.popup.winfo_pointery()
            x, y = self.popup.winfo_rootx(), self.popup.winfo_rooty()
            w, h = self.popup.winfo_width(), self.popup.winfo_height()
            return x <= px <= x + w and y <= py <= y + h
        except Exception:
            return False

    def _is_in_popup(self, widget):
        if not self.popup:
            return False
        p = widget
        while p:
            if p == self.popup:
                return True
            p = getattr(p, "master", None)
        return False

    def hide(self):
        if self.popup:
            try:
                self.popup.destroy()
            except Exception:
                pass
        self.popup = None
        self.listbox = None
        self.context = None
        self.is_selecting = False

# instantiate and bind the new mention manager
mention = MentionManager(root, get_usernames=lambda: list(users.keys()))
# bind for the main post composer
mention.bind_text(post_text)

def submit_post():
    global post_draft_attachments  # moved before any usage
    if not require_login("post"):
        return
    post_content = post_text.get("1.0", "end").strip()
    if not post_content and not post_draft_attachments:
        messagebox.showwarning("Empty post", "Your post cannot be empty!")

        return
    posts.append(normalize_post({
        "author": current_user,
        "content": post_content,
        "created_at": now_ts(),
        "attachments": [{"type": "image", "path": p} for p in post_draft_attachments]
    }))
    if notify_mentions(current_user, post_content, "a post"):
        pass
    notify_followers(current_user)
    persist()
    # clear composer
    post_text.delete("1.0", "end")
    post_draft_attachments = []
    try:
        post_attach_preview.configure(text="")
    except Exception:
        pass
    render_feed()
    render_profile()

# allow Ctrl+Enter to post once the handler exists
post_text.bind("<Control-Return>", lambda e: submit_post())

def delete_post(idx):
    if not require_login("delete posts"):
        return
    post = posts[idx]
    if post["author"] != current_user:
        messagebox.showerror("Not allowed", "You can only delete your own posts.")
        return
    if not messagebox.askyesno("Delete post", "Are you sure you want to delete this post?"):
        return
    posts.pop(idx)
    persist()
    render_feed()
    render_profile()

# ---------- UI updates ----------
def refresh_ui():

    if current_user:
        user_status_lbl.configure(text=f"Signed in as @{current_user}")
        signin_btn.configure(text="Sign out", command=sign_out)
        profile_btn.configure(state="normal", command=lambda: show_frame("profile"))
        notifications_btn.configure(state="normal", command=lambda: show_frame("notifications"))
        messages_btn.configure(state="normal", command=open_messages_page)
        post_btn.configure(state="normal")
    else:
        user_status_lbl.configure(text="Signed out")
        signin_btn.configure(text="Sign in", command=lambda: show_auth("login"))
        profile_btn.configure(state="disabled")
        notifications_btn.configure(state="disabled")
        messages_btn.configure(state="disabled")
        post_btn.configure(state="disabled")
    render_feed()
    render_profile()
    render_dm_sidebar()

def sign_out():
    global current_user
    if not current_user:
        return
    if messagebox.askyesno("Sign out", "Do you really want to sign out?"):
        current_user = None
        refresh_ui()
        render_dm_sidebar()
        show_frame("home")

# ---------- wiring ----------
notifications_btn.configure(state="disabled")
messages_btn.configure(state="disabled")
home_btn.configure(command=lambda: show_frame("home"))
signin_btn.configure(command=lambda: show_auth("login"))
post_btn.configure(command=submit_post)
messages_btn.configure(command=open_messages_page)

render_dm_sidebar()
refresh_ui()
show_frame("home")
root.mainloop()
