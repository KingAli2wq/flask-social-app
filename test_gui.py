#!/usr/bin/env python3
"""Minimal version of social media app for testing"""

import customtkinter as ctk

# Set appearance mode
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

print("Creating root window...")
root = ctk.CTk()
root.title("DevEcho - Test")

# Force window to center of screen
root.geometry("800x600+200+100")  # width x height + x_offset + y_offset

# Force window to be visible and on top
root.lift()
root.attributes("-topmost", True)
root.focus_force()

print("Creating main content...")
main_frame = ctk.CTkFrame(root)
main_frame.pack(fill="both", expand=True, padx=20, pady=20)

label = ctk.CTkLabel(main_frame, text="DevEcho Social Media", font=ctk.CTkFont(size=24, weight="bold"))
label.pack(pady=50)

test_label = ctk.CTkLabel(main_frame, text="If you can see this, the app is working!")
test_label.pack(pady=20)

button = ctk.CTkButton(main_frame, text="Close App", command=root.quit)
button.pack(pady=20)

# Remove topmost after 1 second so it's not always on top
root.after(1000, lambda: root.attributes("-topmost", False))

print("Starting GUI - window should be visible now...")
root.mainloop()
print("GUI closed.")