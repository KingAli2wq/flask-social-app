from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

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


def load_logo_image(path: Path, size: tuple[int, int]) -> Optional[ctk.CTkImage]:
    """Load the DevEcho logo if the asset is available."""
    if not path.exists():
        print(f"Logo asset missing: {path}")
        return None
    try:
        with Image.open(path) as source:
            pil_image = source.convert("RGBA")
    except OSError as exc:
        print(f"Failed to load logo asset: {exc}")
        return None
    return ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=size)


def show_splash_screen(parent: ctk.CTk) -> ctk.CTkToplevel:
    """Render a splash screen while the main window initializes."""
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

    progress = ctk.CTkProgressBar(container, mode="indeterminate")
    progress.pack(fill="x", pady=(0, 12))
    progress.start()

    footer = ctk.CTkLabel(
        container,
        text="Preparing your feed",
        font=ctk.CTkFont(size=12),
        text_color=current_palette["muted"],
    )
    footer.pack()

    splash.update_idletasks()
    return splash


def show_frame(name: str) -> None:
    global active_frame_name

    target = frames.get(name)
    if target is None:
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


print("DEBUG: Setting appearance mode...")
ctk.set_appearance_mode(THEMES[current_theme]["appearance"])  # type: ignore[arg-type]

print("DEBUG: Creating root window...")
root = ctk.CTk()
root.title("DevEcho")
root.geometry("900x600+100+50")  # Set explicit position
root.minsize(720, 520)
root.withdraw()
print("DEBUG: Root window created and configured")


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
frames["videos"] = build_videos_frame(content, current_palette)
frames["search"] = build_search_frame(content, current_palette)
frames["profile"] = build_profile_frame(content, current_palette)
if build_achievements_frame is not None:
    frames["achievements"] = build_achievements_frame(content, current_palette)
frames["notifications"] = build_notifications_frame(content, current_palette)
frames["inspect_profile"] = build_inspect_profile_frame(content, current_palette)
frames["dm"] = build_dm_frame(content, current_palette)

for frame in frames.values():
    frame.grid(row=0, column=0, sticky="nswe")
    frame.grid_remove()

def complete_startup() -> None:
    """Complete app initialization and hide splash screen"""
    global splash_screen
    
    try:
        # Ensure all UI components are fully loaded
        print("✅ App fully initialized")
        
        if splash_screen is not None:
            print("🎬 Closing splash screen")
            splash_screen.destroy()
            splash_screen = None
        
        # Show main window
        root.deiconify()
        root.geometry("1280x800+100+50")
        root.lift()
        root.focus_force()
        root.attributes("-topmost", True)
        
        _apply_fullscreen_size()
        
        # Remove topmost after window is established
        root.after(500, lambda: root.attributes("-topmost", False))
        print("🚀 DevEcho ready!")
        
    except Exception as e:
        print(f"❌ Error in complete_startup: {e}")
        # Fallback: show main window anyway
        if splash_screen:
            splash_screen.destroy()
            splash_screen = None
        root.deiconify()

def initialize_app_components():
    """Initialize all app components step by step"""
    try:
        # Step 1: Initialize UI
        update_loading_progress("UI Components")
        root.after(100, lambda: (
            initialize_ui(frames),
            root.after(200, lambda: (
                # Step 2: Refresh UI
                update_loading_progress("Interface"),
                refresh_ui(),
                root.after(200, lambda: (
                    # Step 3: Update theme
                    update_loading_progress("Theme"),
                    update_theme_button(),
                    root.after(200, lambda: (
                        # Step 4: Show home frame
                        update_loading_progress("Home Feed"),
                        show_frame(active_frame_name),
                        root.after(300, lambda: (
                            # Step 5: Complete startup
                            update_loading_progress("Finalizing"),
                            root.after(200, complete_startup)
                        ))
                    ))
                ))
            ))
        ))
    except Exception as e:
        print(f"❌ Error during initialization: {e}")
        # Fallback to immediate startup
        root.after(1000, complete_startup)

# Start the initialization sequence is deferred until helpers are defined


def update_loading_progress(message: str, progress: float = None):
    """Update the loading screen with current progress"""
    global splash_screen
    if splash_screen is None:
        return
        
    # Find the message label and update it
    for widget in splash_screen.winfo_children():
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkLabel) and "Loading" in str(child.cget("text")):
                child.configure(text=f"Loading {message}...")
                break
    
    splash_screen.update()


print("🚀 Starting DevEcho initialization...")
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
