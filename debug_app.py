#!/usr/bin/env python3

print("=== DEBUGGING SOCIAL MEDIA APP ===")

try:
    print("1. Starting imports...")
    
    from pathlib import Path
    from typing import Dict, Optional
    import customtkinter as ctk
    from PIL import Image
    print("   Basic imports OK")
    
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
    print("   UI imports OK")

    print("2. Setting up constants...")
    
    Palette = Dict[str, str]
    BASE_DIR = Path(__file__).resolve().parent
    LOGO_PATH = BASE_DIR / "media" / "dev_echo_logo.png"
    SPLASH_LOGO_PATH = BASE_DIR / "media" / "dev_echo_loading.png"
    LOGO_SIZE: tuple[int, int] = (36, 36)
    SPLASH_LOGO_SIZE: tuple[int, int] = (180, 180)
    SPLASH_DURATION_MS = 1500
    
    print("3. Creating GUI...")
    
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.withdraw()  # Hide initially for splash
    root.title("DevEcho")
    root.geometry("1280x800")
    root.minsize(800, 600)
    
    print("4. GUI creation successful!")
    print("5. Cleaning up (not starting mainloop)...")
    
    root.destroy()
    print("=== DEBUG COMPLETED SUCCESSFULLY ===")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    print("=== DEBUG FAILED ===")