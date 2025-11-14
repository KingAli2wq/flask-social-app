from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable, Dict, Optional

import customtkinter as ctk
from PIL import Image

from UI import (
    build_dm_frame,
    build_home_frame,
    build_search_frame,
    build_videos_frame,
    build_inspect_profile_frame,
    build_notifications_frame,
    build_profile_frame,
    handle_frame_shown,
    handle_open_messages,
    handle_show_notifications,
    handle_sign_in,
    initialize_ui,
    register_nav_controls,
    register_show_frame_callback,
    refresh_views,
    create_nav_button,
    refresh_nav_icons,
    set_active_nav,
    set_nav_icon_key,
    set_nav_palette,
    update_theme_palette,
)

try:
    from UI import build_achievements_frame
except ImportError:
    build_achievements_frame = None  # type: ignore[assignment]

Palette = Dict[str, str]

BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "media" / "Buttons" / "DevEcho_Transparent_title.png"  # DevEcho transparent logo for UI
SPLASH_LOGO_PATH = BASE_DIR / "media" / "Buttons" / "DevEcho_Title.png"  # DevEcho solid logo for splash
LOGO_SIZE: tuple[int, int] = (40, 40)  # Square logo for navigation bar
SPLASH_LOGO_SIZE: tuple[int, int] = (150, 150)  # Square splash logo
SPLASH_DURATION_MS = 2000  # Extended duration - lasts until everything loads

THEMES: dict[str, dict[str, object]] = {
    "dark": {
        "appearance": "Dark",
        "palette": {
            "bg": "#0b1120",
            "surface": "#111827",
            "card": "#1f2937",
            "accent": "#2563eb",
            "accent_hover": "#1d4ed8",
            "muted": "#94a3b8",
            "text": "#f8fafc",
            "danger": "#ef4444",
            "danger_hover": "#dc2626",
        },
    },
    "light": {
        "appearance": "Light",
        "palette": {
            "bg": "#f8fafc",
            "surface": "#e2e8f0",
            "card": "#ffffff",
            "accent": "#455d58",
            "accent_hover": "#233031",
            "muted": "#64748b",
            "text": "#0f172a",
            "danger": "#ef4444",
            "danger_hover": "#dc2626",
        },
    },
}

current_theme = "dark"
current_palette: Palette = dict(THEMES[current_theme]["palette"])  # type: ignore[arg-type]

frames: dict[str, ctk.CTkFrame] = {}
active_frame_name = "home"
root: ctk.CTk
nav_panel: ctk.CTkFrame
nav_buttons_frame: ctk.CTkFrame
nav_footer: ctk.CTkFrame
content: ctk.CTkFrame
home_btn: ctk.CTkButton
profile_btn: ctk.CTkButton
signin_btn: ctk.CTkButton
notifications_btn: ctk.CTkButton
messages_btn: ctk.CTkButton
theme_btn: ctk.CTkButton
exit_btn: ctk.CTkButton

logo_img: Optional[ctk.CTkImage] = None
splash_logo_img: Optional[ctk.CTkImage] = None
splash_screen: Optional[ctk.CTkToplevel] = None

FRAME_TO_NAV: dict[str, str] = {
    "home": "home",
    "videos": "videos",
    "search": "search",
    "profile": "profile",
    "notifications": "notifications",
    "inspect_profile": "profile",
    "dm": "messages",
}

if build_achievements_frame is not None:
    FRAME_TO_NAV["achievements"] = "profile"


logger = logging.getLogger("devecho.app")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger.setLevel(logging.INFO)

frame_factories: dict[str, Callable[[], ctk.CTkFrame]] = {}

splash_message_label: Optional[ctk.CTkLabel] = None
splash_progress_bar: Optional[ctk.CTkProgressBar] = None

def load_logo_image(path: Path, size: tuple[int, int]) -> Optional[ctk.CTkImage]:
    """Load the DevEcho logo if the asset is available."""
    if not path.exists():
        logger.warning("Logo asset missing: %s", path)
        return None
    try:
        with Image.open(path) as source:
            pil_image = source.convert("RGBA")
    except OSError as exc:
        logger.warning("Failed to load logo asset: %s", exc)
        return None
    return ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=size)


def show_splash_screen(parent: ctk.CTk) -> ctk.CTkToplevel:
    """Render a splash screen while the main window initializes."""
    global splash_message_label, splash_progress_bar

    splash = ctk.CTkToplevel(parent)
    splash.overrideredirect(True)
    splash.attributes("-topmost", True)
    splash.configure(fg_color=current_palette["bg"])

    width, height = 360, 420
    screen_width = splash.winfo_screenwidth()
    screen_height = splash.winfo_screenheight()
    pos_x = int((screen_width - width) / 2)
    pos_y = int((screen_height - height) / 2)
    splash.geometry(f"{width}x{height}+{pos_x}+{pos_y}")

    container = ctk.CTkFrame(splash, fg_color="transparent")
    container.pack(expand=True, fill="both", padx=32, pady=32)

    if splash_logo_img:
        logo_label = ctk.CTkLabel(container, text="", image=splash_logo_img, fg_color="transparent")
        logo_label.pack(pady=(24, 16))
    else:
        placeholder = ctk.CTkLabel(
            container,
            text="DevEcho",
            font=ctk.CTkFont(size=36, weight="bold"),
            text_color=current_palette["text"],
        )
        placeholder.pack(pady=(48, 16))

    message = ctk.CTkLabel(
        container,
        text="Loading DevEcho...",
        font=ctk.CTkFont(size=18, weight="bold"),
        text_color=current_palette["text"],
    )
    message.pack(pady=(0, 24))
    splash_message_label = message

    progress = ctk.CTkProgressBar(container, mode="indeterminate")
    progress.pack(fill="x", pady=(0, 12))
    progress.start()
    splash_progress_bar = progress

    footer = ctk.CTkLabel(
        container,
        text="Preparing your feed",
        font=ctk.CTkFont(size=12),
        text_color=current_palette["muted"],
    )
    footer.pack()

    splash.update_idletasks()
    return splash


def register_frame_factory(name: str, builder: Callable[[], ctk.CTkFrame]) -> None:
    frame_factories[name] = builder


def ensure_frame(name: str) -> Optional[ctk.CTkFrame]:
    existing = frames.get(name)
    if existing is not None:
        return existing
    builder = frame_factories.get(name)
    if builder is None:
        return None
    try:
        frame = builder()
    except Exception:
        logger.exception("Failed to build frame '%s'", name)
        return None
    frames[name] = frame
    frame.grid(row=0, column=0, sticky="nswe")
    frame.grid_remove()
    return frame


def show_frame(name: str) -> None:
    global active_frame_name

    target = frames.get(name)
    if target is None:
        target = ensure_frame(name)
        if target is None:
            logger.warning("No frame available for '%s'", name)
            return

    needs_show = active_frame_name != name or not target.winfo_ismapped()

    if needs_show:
        current_frame = frames.get(active_frame_name)
        if current_frame and current_frame is not target:
            current_frame.grid_remove()

        target.grid(row=0, column=0, sticky="nswe")
        active_frame_name = name

        root.after_idle(lambda: set_active_nav(FRAME_TO_NAV.get(name)))

    handle_frame_shown(name)


def refresh_ui() -> None:
    refresh_views(frames)


def update_theme_button() -> None:
    icon_key = "theme_sun" if current_theme == "dark" else "theme_moon"
    set_nav_icon_key("theme", icon_key)


def configure_shell_palette() -> None:
    root.configure(fg_color=current_palette["bg"])
    if nav_panel:
        nav_panel.configure(fg_color=current_palette["surface"])
    if nav_buttons_frame:
        nav_buttons_frame.configure(fg_color="transparent")
    if nav_footer:
        nav_footer.configure(fg_color="transparent")
    set_nav_palette(current_palette)
    update_theme_button()


def apply_theme(mode: str) -> None:
    global current_theme, current_palette
    if mode not in THEMES:
        return
    theme = THEMES[mode]
    current_theme = mode
    current_palette = dict(theme["palette"])  # type: ignore[arg-type]
    configure_shell_palette()
    update_theme_palette(current_palette)


def toggle_theme() -> None:
    apply_theme("light" if current_theme == "dark" else "dark")


logger.debug("Setting appearance mode")
ctk.set_appearance_mode(THEMES[current_theme]["appearance"])  # type: ignore[arg-type]

logger.debug("Creating root window")
root = ctk.CTk()
root.title("DevEcho")
root.geometry("900x600+100+50")  # Set explicit position
root.minsize(720, 520)
root.withdraw()
logger.debug("Root window created and configured")


def _apply_fullscreen_size() -> None:
    """Resize the window to match the full screen dimensions."""
    width = root.winfo_screenwidth()
    height = root.winfo_screenheight()
    root.geometry(f"{width}x{height}+0+0")
    try:
        root.state("zoomed")
    except Exception:
        pass

splash_logo_img = load_logo_image(SPLASH_LOGO_PATH, SPLASH_LOGO_SIZE)
splash_screen = show_splash_screen(root)

root.configure(fg_color=current_palette["bg"])
root.grid_rowconfigure(0, weight=1)
root.grid_columnconfigure(0, weight=0)
root.grid_columnconfigure(1, weight=1)

logo_img = load_logo_image(LOGO_PATH, LOGO_SIZE)

nav_panel = ctk.CTkFrame(root, width=96, corner_radius=0, fg_color=current_palette["surface"])
nav_panel.grid(row=0, column=0, sticky="ns")
nav_panel.grid_rowconfigure(1, weight=1)

brand_frame = ctk.CTkFrame(nav_panel, fg_color="transparent")
brand_frame.grid(row=0, column=0, pady=(24, 12))
if logo_img:
    ctk.CTkLabel(brand_frame, text="", image=logo_img, fg_color="transparent").pack()
else:
    ctk.CTkLabel(
        brand_frame,
        text="DevEcho",
        font=ctk.CTkFont(size=18, weight="bold"),
        text_color=current_palette["text"],
    ).pack()

nav_buttons_frame = ctk.CTkFrame(nav_panel, fg_color="transparent")
nav_buttons_frame.grid(row=1, column=0, sticky="n", padx=0, pady=(12, 12))
set_nav_palette(current_palette)

home_btn = create_nav_button(
    "home",
    "home",
    parent=nav_buttons_frame,
    row=0,
    command=lambda: show_frame("home"),
    pady=(0, 12),
)
videos_btn = create_nav_button(
    "videos",
    "videos",
    parent=nav_buttons_frame,
    row=1,
    command=lambda: show_frame("videos"),
    pady=10,
)
search_btn = create_nav_button(
    "search",
    "search",
    parent=nav_buttons_frame,
    row=2,
    command=lambda: show_frame("search"),
    pady=10,
)
notifications_btn = create_nav_button(
    "notifications",
    "notifications",
    parent=nav_buttons_frame,
    row=3,
    command=handle_show_notifications,
    pady=10,
)
messages_btn = create_nav_button(
    "messages",
    "messages",
    parent=nav_buttons_frame,
    row=4,
    command=handle_open_messages,
    pady=10,
)
profile_btn = create_nav_button(
    "profile",
    "profile",
    parent=nav_buttons_frame,
    row=5,
    command=lambda: show_frame("profile"),
    pady=10,
)
signin_btn = create_nav_button(
    "signin",
    "signin",
    parent=nav_buttons_frame,
    row=6,
    command=handle_sign_in,
    pady=10,
)

nav_footer = ctk.CTkFrame(nav_panel, fg_color="transparent")
nav_footer.grid(row=2, column=0, sticky="s", padx=0, pady=(12, 24))
theme_btn = create_nav_button(
    "theme",
    "theme_sun" if current_theme == "dark" else "theme_moon",
    parent=nav_footer,
    row=0,
    command=toggle_theme,
    pady=(0, 12),
)
exit_btn = create_nav_button(
    "exit",
    "exit",
    parent=nav_footer,
    row=1,
    command=root.destroy,
    pady=(0, 0),
)

content = ctk.CTkFrame(root, corner_radius=12, fg_color="transparent")
content.grid(row=0, column=1, sticky="nswe", padx=(12, 16), pady=16)
content.grid_rowconfigure(0, weight=1)
content.grid_columnconfigure(0, weight=1)

refresh_nav_icons()
set_active_nav("home")

register_show_frame_callback(show_frame)
register_nav_controls(
    home=home_btn,
    videos=videos_btn,
    search=search_btn,
    profile=profile_btn,
    signin=signin_btn,
    notifications=notifications_btn,
    messages_btn=messages_btn,
)
configure_shell_palette()
frames["home"] = build_home_frame(content, current_palette)
frames["home"].grid(row=0, column=0, sticky="nswe")
frames["home"].grid_remove()

register_frame_factory("videos", lambda: build_videos_frame(content, current_palette))
register_frame_factory("search", lambda: build_search_frame(content, current_palette))
register_frame_factory("profile", lambda: build_profile_frame(content, current_palette))
register_frame_factory("notifications", lambda: build_notifications_frame(content, current_palette))
register_frame_factory("inspect_profile", lambda: build_inspect_profile_frame(content, current_palette))
register_frame_factory("dm", lambda: build_dm_frame(content, current_palette))
if build_achievements_frame is not None:
    register_frame_factory(
        "achievements",
        lambda builder=build_achievements_frame: builder(content, current_palette),
    )

def complete_startup() -> None:
    """Complete app initialization and transition from the splash screen."""
    global splash_screen, splash_progress_bar, splash_message_label

    try:
        logger.info("Application initialization complete")

        if splash_screen is not None:
            logger.debug("Closing splash screen")
            splash_screen.destroy()
            splash_screen = None
            splash_progress_bar = None
            splash_message_label = None

        root.deiconify()
        root.geometry("1280x800+100+50")
        root.lift()
        root.focus_force()
        root.attributes("-topmost", True)

        _apply_fullscreen_size()

        root.after(500, lambda: root.attributes("-topmost", False))
        root.after(750, lambda: _kickoff_background_warmup())
        logger.info("DevEcho ready")

    except Exception:
        logger.exception("Error while completing startup")
        if splash_screen:
            splash_screen.destroy()
            splash_screen = None
        root.deiconify()


def _kickoff_background_warmup() -> None:
    """Run heavier warmup tasks off the UI thread once the shell is visible."""

    def _worker() -> None:
        try:
            from data_layer import ensure_all_media_local, refresh_remote_state

            changes = refresh_remote_state()
            if changes and getattr(root, "winfo_exists", lambda: False)():
                try:
                    root.after(0, refresh_ui)
                except Exception:
                    logger.debug("Deferred UI refresh failed", exc_info=True)

            ensure_all_media_local()
        except Exception:
            logger.debug("Background warmup tasks failed", exc_info=True)

    threading.Thread(target=_worker, name="devecho-warmup", daemon=True).start()
def initialize_app_components() -> None:
    """Initialize all app components step by step without blocking the UI thread."""

    steps: list[tuple[str, Callable[[], None]]] = [
        ("UI Components", lambda: initialize_ui(frames)),
        ("Interface", refresh_ui),
        ("Theme", update_theme_button),
        ("Home Feed", lambda: show_frame(active_frame_name)),
    ]

    total_steps = len(steps) + 1  # include finalizing step

    def _run_step(index: int) -> None:
        if index >= len(steps):
            update_loading_progress("Finalizing", progress=1.0)
            root.after(80, complete_startup)
            return

        label, action = steps[index]
        progress_value = (index + 1) / total_steps
        update_loading_progress(label, progress=progress_value)
        try:
            action()
        except Exception:
            logger.exception("Startup step '%s' failed", label)

        root.after(40, lambda: _run_step(index + 1))

    try:
        root.after(10, lambda: _run_step(0))
    except Exception:
        logger.exception("Failed to schedule startup sequence")
        root.after(0, complete_startup)

# Start the initialization sequence is deferred until helpers are defined


def update_loading_progress(message: str, progress: Optional[float] = None) -> None:
    """Update the splash screen message and optional determinate progress."""
    global splash_screen
    if splash_screen is None:
        return

    if splash_message_label and splash_message_label.winfo_exists():
        splash_message_label.configure(text=f"Loading {message}...")

    if progress is not None and splash_progress_bar and splash_progress_bar.winfo_exists():
        splash_progress_bar.configure(mode="determinate")
        clamped = max(0.0, min(1.0, float(progress)))
        splash_progress_bar.set(clamped)
    elif splash_progress_bar and splash_progress_bar.winfo_exists():
        # Ensure the bar keeps animating when no explicit progress provided
        if splash_progress_bar.cget("mode") != "indeterminate":
            splash_progress_bar.configure(mode="indeterminate")
            splash_progress_bar.start()

    splash_screen.update_idletasks()


logger.info("Starting DevEcho initialization")
initialize_app_components()

def check_loading_complete() -> bool:
    """Check if all critical components are loaded"""
    try:
        # Check if data layer is ready
        from data_layer import users, posts, messages
        
        # Check if UI is initialized 
        from UI import _ui_state
        
        # Check if basic data structures exist
        if isinstance(users, dict) and isinstance(posts, list) and isinstance(messages, dict):
            return True
            
    except Exception:
        pass
    
    return False


# Start the app
root.mainloop()
