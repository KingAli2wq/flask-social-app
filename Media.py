import os
import shutil
import sys
from typing import Optional

import tkinter as tk
from tkinter import messagebox

try:
    from PIL import Image, ImageTk  # type: ignore
except ImportError:
    Image = None  # type: ignore
    ImageTk = None  # type: ignore

_ALLOWED_IMAGE_EXTENSIONS = {".png", ".gif", ".jpg", ".jpeg", ".webp"}
_MAX_ATTACHMENT_BYTES = 200 * 1024 * 1024  # 200 MB


def _ensure_directory(path: str) -> None:
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def _validate_image_extension(path: str) -> bool:
    _, ext = os.path.splitext(path)
    return ext.lower() in _ALLOWED_IMAGE_EXTENSIONS


def copy_image_to_media(
    src_path: Optional[str], *, base_dir: str, media_dir: str
) -> Optional[str]:
    if not src_path:
        return None
    if not _validate_image_extension(src_path):
        messagebox.showwarning(
        "Unsupported image",
        "Please select PNG, GIF, JPG, or WEBP files.",
        )
        return None

    _ensure_directory(media_dir)
    base_name = os.path.basename(src_path)
    name, ext = os.path.splitext(base_name)
    dst_path = os.path.join(media_dir, base_name)
    counter = 1
    while os.path.exists(dst_path):
        dst_path = os.path.join(media_dir, f"{name}_{counter}{ext.lower()}")
        counter += 1

    try:
        shutil.copy2(src_path, dst_path)
        return os.path.relpath(dst_path, base_dir).replace("\\", "/")
    except Exception as exc:  # pragma: no cover - GUI feedback
        messagebox.showerror("Attach image failed", f"Could not attach image:\n{exc}")
        return None


def copy_file_to_media(
    src_path: Optional[str], *, base_dir: str, media_dir: str, max_bytes: int = _MAX_ATTACHMENT_BYTES
) -> Optional[str]:
    if not src_path:
        return None
    if not os.path.isfile(src_path):
        messagebox.showerror("Attach file failed", "The selected path does not point to a file.")
        return None

    try:
        file_size = os.path.getsize(src_path)
    except OSError:
        messagebox.showerror("Attach file failed", "Could not read the file size.")
        return None

    if file_size > max_bytes:
        limit_mb = max_bytes // (1024 * 1024)
        messagebox.showwarning(
            "File too large",
            f"Attachments must be smaller than {limit_mb} MB.",
        )
        return None

    _ensure_directory(media_dir)
    base_name = os.path.basename(src_path)
    name, ext = os.path.splitext(base_name)
    dst_path = os.path.join(media_dir, base_name)
    counter = 1
    while os.path.exists(dst_path):
        dst_path = os.path.join(media_dir, f"{name}_{counter}{ext}")
        counter += 1

    try:
        shutil.copy2(src_path, dst_path)
        return os.path.relpath(dst_path, base_dir).replace("\\", "/")
    except Exception as exc:  # pragma: no cover - GUI feedback
        messagebox.showerror("Attach file failed", f"Could not attach file:\n{exc}")
        return None


def copy_image_to_profile_pics(
    src_path: Optional[str], *, base_dir: str, profile_pics_dir: str
) -> Optional[str]:
    if not src_path:
        return None
    if not _validate_image_extension(src_path):
        messagebox.showwarning(
        "Unsupported image",
        "Please select PNG, GIF, JPG, or WEBP files.",
        )
        return None

    _ensure_directory(profile_pics_dir)
    base_name = os.path.basename(src_path)
    name, ext = os.path.splitext(base_name)
    dst_path = os.path.join(profile_pics_dir, base_name)
    counter = 1
    while os.path.exists(dst_path):
        dst_path = os.path.join(profile_pics_dir, f"{name}_{counter}{ext.lower()}")
        counter += 1

    try:
        shutil.copy2(src_path, dst_path)
        return os.path.relpath(dst_path, base_dir).replace("\\", "/")
    except Exception as exc:  # pragma: no cover - GUI feedback
        messagebox.showerror("Profile picture failed", f"Could not set profile picture:\n{exc}")
        return None


def load_image_for_tk(rel_path: str, *, base_dir: str, max_width: int) -> Optional[tk.PhotoImage]:
    abs_path = os.path.join(base_dir, rel_path)
    if Image and ImageTk:
        try:
            resampling = getattr(Image, "Resampling", None)
            lanczos = getattr(resampling, "LANCZOS", None) if resampling else getattr(Image, "LANCZOS", None)
            fallback = (
                getattr(resampling, "BICUBIC", None) if resampling else getattr(Image, "BICUBIC", None)
            ) or getattr(Image, "BILINEAR", None) or getattr(Image, "NEAREST", 0)

            img = Image.open(abs_path)
            width, height = img.size
            if width > max_width:
                scale = max_width / float(width)
                img = img.resize((int(width * scale), int(height * scale)), lanczos or fallback)
            return ImageTk.PhotoImage(img)
        except Exception:
            pass  # fall back to Tk PhotoImage

    try:
        photo = tk.PhotoImage(file=abs_path)
        width = photo.width()
        if width > max_width:
            factor = max(1, int(width / max_width))
            photo = photo.subsample(factor, factor)
        return photo
    except Exception:
        return None


def open_image(rel_path: str, *, base_dir: str) -> None:
    abs_path = os.path.join(base_dir, rel_path)
    try:
        if os.name == "nt":
            os.startfile(abs_path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            os.system(f'open "{abs_path}"')
        else:
            os.system(f'xdg-open "{abs_path}"')
    except Exception:
        pass