from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

import customtkinter as ctk
import tkinter as tk

from achievements import ACHIEVEMENTS, compute_achievement_progress

Palette = dict[str, str]
PostDict = dict[str, Any]
ReplyDict = dict[str, Any]
UserDict = dict[str, Any]

ImageLoader = Callable[[str, int], Optional[tk.PhotoImage]]
AvatarLoader = Callable[[str, int], Optional[tk.PhotoImage]]
OpenHandler = Callable[[str], None]


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


@dataclass
class FeedState:
    current_user: Optional[str]
    expanded_replies: set[int]
    editing_post_index: Optional[int]
    editing_reply_target: Optional[tuple[int, int]]
    reply_input_target: Optional[int]
    focus_post_id: Optional[str]
    focus_reply_id: Optional[str]


@dataclass
class FeedCallbacks:
    open_profile: Optional[Callable[[str], None]]
    toggle_post_reaction: Callable[[int, str], None]
    toggle_replies: Callable[[int], None]
    open_reply_box: Callable[[Optional[int]], None]
    start_edit: Callable[[int], None]
    cancel_edit: Callable[[], None]
    apply_edit: Callable[[int, ctk.CTkTextbox], None]
    delete_post: Callable[[int], None]
    start_reply_edit: Callable[[int, int], None]
    cancel_reply_edit: Callable[[], None]
    apply_reply_edit: Callable[[int, int, tk.Text], None]
    delete_reply: Callable[[int, int], None]
    submit_reply: Callable[[int, tk.StringVar], None]
    create_reply_toolbar: Callable[[ctk.CTkFrame, int, tk.StringVar], None]
    create_post_toolbar: Optional[Callable[[ctk.CTkFrame, int], None]] = None
    open_attachment: Optional[Callable[[dict[str, Any]], None]] = None
    render_inline_video: Optional[Callable[..., None]] = None
    get_reaction_icon: Optional[Callable[[str, tuple[int, int]], Optional[ctk.CTkImage]]] = None


def _clear_children(widget: ctk.CTkBaseClass) -> None:
    for child in widget.winfo_children():
        child.destroy()


def render_post_card(
    *,
    container: ctk.CTkFrame,
    idx: int,
    post: PostDict,
    palette: Palette,
    state: FeedState,
    callbacks: FeedCallbacks,
    load_profile_avatar: Optional[AvatarLoader] = None,
    load_image_for_tk: Optional[ImageLoader] = None,
    open_image: Optional[OpenHandler] = None,
) -> None:
    """Render a single post card into the supplied container."""
    base_card_color = palette.get("card", "#18263f")
    card = ctk.CTkFrame(container, corner_radius=16, fg_color=base_card_color)
    card.grid(sticky="we", padx=0, pady=8)
    card.grid_columnconfigure(0, weight=1)
    card._image_refs = []  # type: ignore[attr-defined]

    accent = palette.get("accent", "#4c8dff")
    accent_hover = palette.get("accent_hover", "#3b6dd6")
    muted = palette.get("muted", "#94a3b8")
    text_color = palette.get("text", "#e2e8f0")
    surface = palette.get("surface", "#111b2e")
    danger = palette.get("danger", "#ef4444")
    danger_hover = palette.get("danger_hover", "#dc2626")

    is_focus_post = bool(state.focus_post_id and str(post.get("id")) == str(state.focus_post_id))
    if is_focus_post:
        try:
            card.configure(border_width=2, border_color=accent)
        except Exception:
            card.configure(fg_color="#1d2a44")

    header = f"@{post.get('author', 'unknown')}  ·  {post.get('created_at', '')}"
    header_lbl = ctk.CTkLabel(
        card,
        text=header,
        font=ctk.CTkFont(size=12, weight="bold"),
        text_color=text_color,
    )
    header_lbl.grid(row=0, column=0, sticky="w", padx=16, pady=(12, 4))
    if callbacks.open_profile:
        header_lbl.configure(cursor="hand2")
        header_lbl.bind("<Button-1>", lambda _e, u=post.get("author", ""): callbacks.open_profile(u))

    if state.editing_post_index == idx:
        editor = ctk.CTkTextbox(card, height=110, fg_color=surface, text_color=text_color, border_width=0)
        editor.grid(row=1, column=0, sticky="we", padx=16, pady=(0, 8))
        editor.insert("1.0", post.get("content", ""))

        if callbacks.create_post_toolbar:
            callbacks.create_post_toolbar(card, idx)

        button_row = ctk.CTkFrame(card, fg_color="transparent")
        button_row.grid(row=2, column=0, sticky="e", padx=16, pady=(0, 12))
        ctk.CTkButton(
            button_row,
            text="Save",
            width=70,
            fg_color=accent,
            hover_color=accent_hover,
            command=lambda i=idx, tb=editor: callbacks.apply_edit(i, tb),
        ).grid(row=0, column=0, padx=4)
        ctk.CTkButton(
            button_row,
            text="Cancel",
            width=70,
            fg_color="transparent",
            border_width=1,
            border_color=muted,
            text_color=muted,
            hover_color=surface,
            command=callbacks.cancel_edit,
        ).grid(row=0, column=1, padx=4)
    else:
        body_lbl = ctk.CTkLabel(
            card,
            text=post.get("content", ""),
            justify="left",
            wraplength=680,
            text_color=text_color,
        )
        body_lbl.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 6))
        if post.get("edited"):
            ctk.CTkLabel(
                card,
                text=f"* edited on {post.get('edited_at', '')}",
                text_color=muted,
                font=ctk.CTkFont(size=10, slant="italic"),
            ).grid(row=2, column=0, sticky="w", padx=16, pady=(0, 6))

    attachments = post.get("attachments", [])
    row_cursor = 3
    if attachments:
        att_section = ctk.CTkFrame(card, fg_color="transparent")
        att_section.grid(row=row_cursor, column=0, sticky="we", padx=16, pady=(0, 8))
        row_cursor += 1

        image_items: list[dict[str, Any]] = []
        video_items: list[dict[str, Any]] = []
        file_items: list[dict[str, Any]] = []
        for att in attachments:
            if not isinstance(att, dict):
                continue
            att_type = att.get("type")
            if att_type == "image":
                image_items.append(att)
            elif att_type == "video":
                video_items.append(att)
            else:
                file_items.append(att)
        if video_items and not callbacks.render_inline_video:
            file_items.extend(video_items)
            video_items = []

        section_row = 0
        if video_items and callbacks.render_inline_video:
            for video_att in video_items:
                video_container = ctk.CTkFrame(att_section, fg_color="transparent")
                video_container.grid(row=section_row, column=0, sticky="we", pady=(0, 8))
                callbacks.render_inline_video(
                    video_att,
                    video_container,
                    controls=False,
                    click_to_toggle=True,
                )
                section_row += 1

        if image_items and load_image_for_tk:
            image_frame = ctk.CTkFrame(att_section, fg_color="transparent")
            image_frame.grid(row=section_row, column=0, sticky="w")
            section_row += 1
            for col, att in enumerate(image_items):
                rel_path = att.get("path", "")
                image = load_image_for_tk(rel_path, 680)
                if image:
                    img_lbl = tk.Label(
                        image_frame,
                        image=image,
                        bd=0,
                        bg=palette.get("card", "#18263f"),
                        cursor="hand2",
                    )
                    img_lbl.grid(row=0, column=col, padx=(0, 8), pady=(4, 0), sticky="w")
                    if open_image and rel_path:
                        img_lbl.bind("<Button-1>", lambda _e, p=rel_path: open_image(p))
                    card._image_refs.append(image)
                else:
                    file_items.append(att)
        elif image_items:
            file_items.extend(image_items)

        if file_items:
            file_list = ctk.CTkFrame(att_section, fg_color="transparent")
            file_list.grid(row=section_row, column=0, sticky="we")
            for idx, att in enumerate(file_items):
                entry = ctk.CTkFrame(file_list, fg_color=surface, corner_radius=8)
                entry.grid(row=idx, column=0, sticky="we", pady=4)
                entry.grid_columnconfigure(0, weight=1)

                name = att.get("name") or (att.get("path", "").split("/")[-1])
                file_type = att.get("type", "file").title()
                details = f"[{file_type}] {name}"
                size_value = att.get("size")
                if isinstance(size_value, int):
                    details += f" • {_format_size(size_value)}"

                ctk.CTkLabel(
                    entry,
                    text=details,
                    text_color=text_color,
                    anchor="w",
                    justify="left",
                ).grid(row=0, column=0, sticky="we", padx=12, pady=8)

                path = att.get("path")
                handler = callbacks.open_attachment
                if handler:
                    ctk.CTkButton(
                        entry,
                        text="Open",
                        width=80,
                        fg_color="transparent",
                        border_width=1,
                        border_color=muted,
                        text_color=muted,
                        hover_color=surface,
                        command=lambda attachment=att: handler(attachment),
                    ).grid(row=0, column=1, padx=8, pady=8)
                elif open_image and path:
                    ctk.CTkButton(
                        entry,
                        text="Open",
                        width=80,
                        fg_color="transparent",
                        border_width=1,
                        border_color=muted,
                        text_color=muted,
                        hover_color=surface,
                        command=lambda p=path: open_image(p),
                    ).grid(row=0, column=1, padx=8, pady=8)

    actions = ctk.CTkFrame(card, fg_color="transparent")
    actions.grid(row=row_cursor, column=0, sticky="we", padx=16, pady=(0, 8))
    row_cursor += 1
    actions.grid_columnconfigure(0, weight=1)

    like_count = post.get("likes", len(post.get("liked_by", [])))
    dislike_count = post.get("dislikes", len(post.get("disliked_by", [])))
    liked = bool(state.current_user and state.current_user in post.get("liked_by", []))
    disliked = bool(state.current_user and state.current_user in post.get("disliked_by", []))

    icon_loader = callbacks.get_reaction_icon
    icon_size = (26, 26)
    like_icon = icon_loader("like", icon_size) if icon_loader else None
    dislike_icon = icon_loader("dislike", icon_size) if icon_loader else None

    like_btn = ctk.CTkButton(
        actions,
        text=f"Like ({like_count})",
        width=90,
        image=like_icon,
        compound="left" if like_icon else "center",
        fg_color=accent if liked else "transparent",
        text_color="white" if liked else muted,
        hover_color=accent_hover,
        border_width=0 if liked else 1,
        border_color=muted,
        command=lambda i=idx: callbacks.toggle_post_reaction(i, "like"),
    )
    like_btn.grid(row=0, column=10, padx=(0, 6), sticky="e")
    if like_icon:
        like_btn._icon_ref = like_icon  # type: ignore[attr-defined]

    dislike_btn = ctk.CTkButton(
        actions,
        text=f"Dislike ({dislike_count})",
        width=90,
        image=dislike_icon,
        compound="left" if dislike_icon else "center",
        fg_color=danger if disliked else "transparent",
        text_color="white" if disliked else muted,
        hover_color=danger_hover,
        border_width=0 if disliked else 1,
        border_color=muted,
        command=lambda i=idx: callbacks.toggle_post_reaction(i, "dislike"),
    )
    dislike_btn.grid(row=0, column=11, sticky="e")
    if dislike_icon:
        dislike_btn._icon_ref = dislike_icon  # type: ignore[attr-defined]

    if not state.current_user:
        like_btn.configure(state="disabled")
        dislike_btn.configure(state="disabled")

    reply_count = len(post.get("replies", []))
    replies_expanded = idx in state.expanded_replies
    toggle_btn = ctk.CTkButton(
        actions,
        text=f"{'Hide' if replies_expanded else 'View'} replies ({reply_count})",
        width=130,
        fg_color="transparent",
        border_width=1,
        border_color=accent,
        text_color=accent,
        hover_color=accent_hover,
        command=lambda i=idx: callbacks.toggle_replies(i),
    )
    toggle_btn.grid(row=0, column=0, padx=(0, 6), sticky="w")

    reply_btn = ctk.CTkButton(
        actions,
        text="Reply",
        width=70,
        fg_color="transparent",
        border_width=1,
        border_color=muted,
        text_color=muted,
        hover_color=surface,
        command=lambda i=idx: callbacks.open_reply_box(i),
    )
    reply_btn.grid(row=0, column=1, padx=(0, 6), sticky="w")
    if not state.current_user:
        reply_btn.configure(state="disabled")

    if state.current_user and post.get("author") == state.current_user:
        ctk.CTkButton(
            actions,
            text="Edit",
            width=70,
            fg_color="transparent",
            border_width=1,
            border_color=accent,
            text_color=accent,
            hover_color=accent_hover,
            command=lambda i=idx: callbacks.start_edit(i),
        ).grid(row=0, column=2, padx=(0, 6))
        ctk.CTkButton(
            actions,
            text="Delete",
            width=70,
            fg_color=danger,
            hover_color=danger_hover,
            command=lambda i=idx: callbacks.delete_post(i),
        ).grid(row=0, column=3, padx=(0, 6))

    if replies_expanded:
        replies_frame = ctk.CTkFrame(card, fg_color=surface, corner_radius=12)
        replies_frame.grid(row=row_cursor, column=0, sticky="we", padx=16, pady=(6, 8))
        row_cursor += 1
        replies_frame.grid_columnconfigure(0, weight=1)

        for r_idx, reply in enumerate(post.get("replies", [])):
            reply_base_color = palette.get("card", "#18263f")
            r_card = ctk.CTkFrame(replies_frame, fg_color=reply_base_color, corner_radius=10)
            r_card.grid(sticky="we", padx=8, pady=4)
            r_card.grid_columnconfigure(0, weight=1)
            r_card._image_refs = []  # type: ignore[attr-defined]

            if state.focus_reply_id and str(reply.get("id")) == str(state.focus_reply_id):
                try:
                    r_card.configure(border_width=2, border_color=accent)
                except Exception:
                    r_card.configure(fg_color="#20314f")

            reply_header = ctk.CTkLabel(
                r_card,
                text=f"@{reply.get('author', '')}  ·  {reply.get('created_at', '')}",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=text_color,
            )
            reply_header.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))
            if callbacks.open_profile:
                reply_header.configure(cursor="hand2")
                reply_header.bind("<Button-1>", lambda _e, u=reply.get("author", ""): callbacks.open_profile(u))

            if state.editing_reply_target == (idx, r_idx):
                editor = ctk.CTkTextbox(r_card, height=80, fg_color=surface, text_color=text_color, border_width=0)
                editor.grid(row=1, column=0, sticky="we", padx=12, pady=(0, 6))
                editor.insert("1.0", reply.get("content", ""))

                btns = ctk.CTkFrame(r_card, fg_color="transparent")
                btns.grid(row=2, column=0, sticky="e", padx=12, pady=(0, 10))
                ctk.CTkButton(
                    btns,
                    text="Save",
                    width=60,
                    fg_color=accent,
                    hover_color=accent_hover,
                    command=lambda p_idx=idx, rr_idx=r_idx, tb=editor: callbacks.apply_reply_edit(p_idx, rr_idx, tb),
                ).grid(row=0, column=0, padx=4)
                ctk.CTkButton(
                    btns,
                    text="Cancel",
                    width=60,
                    fg_color="transparent",
                    border_width=1,
                    border_color=muted,
                    text_color=muted,
                    hover_color=surface,
                    command=callbacks.cancel_reply_edit,
                ).grid(row=0, column=1, padx=4)
            else:
                tk.Label(
                    r_card,
                    text=reply.get("content", ""),
                    wraplength=640,
                    justify="left",
                    bg=palette.get("card", "#18263f"),
                    fg=text_color,
                    font=("Segoe UI Emoji", 10),
                ).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 4))
                if reply.get("edited"):
                    ctk.CTkLabel(
                        r_card,
                        text=f"* edited on {reply.get('edited_at', '')}",
                        text_color=muted,
                        font=ctk.CTkFont(size=10, slant="italic"),
                    ).grid(row=2, column=0, sticky="w", padx=12, pady=(0, 6))

                reply_attachments = reply.get("attachments", [])
                if reply_attachments:
                    att_frame = ctk.CTkFrame(r_card, fg_color="transparent")
                    att_frame.grid(row=3, column=0, sticky="w", padx=12, pady=(0, 6))

                    r_image_items: list[dict[str, Any]] = []
                    r_video_items: list[dict[str, Any]] = []
                    r_file_items: list[dict[str, Any]] = []
                    for ratt in reply_attachments:
                        if not isinstance(ratt, dict):
                            continue
                        r_type = ratt.get("type")
                        if r_type == "image":
                            r_image_items.append(ratt)
                        elif r_type == "video":
                            r_video_items.append(ratt)
                        else:
                            r_file_items.append(ratt)

                    section_row = 0
                    if r_video_items and callbacks.render_inline_video:
                        for video_att in r_video_items:
                            video_container = ctk.CTkFrame(att_frame, fg_color="transparent")
                            video_container.grid(row=section_row, column=0, sticky="we", pady=(0, 6))
                            callbacks.render_inline_video(
                                video_att,
                                video_container,
                                controls=False,
                                click_to_toggle=True,
                            )
                            section_row += 1
                    elif r_video_items:
                        r_file_items.extend(r_video_items)

                    if r_image_items and load_image_for_tk:
                        image_holder = ctk.CTkFrame(att_frame, fg_color="transparent")
                        image_holder.grid(row=section_row, column=0, sticky="w")
                        section_row += 1
                        for col, ratt in enumerate(r_image_items):
                            rp = ratt.get("path", "")
                            rimg = load_image_for_tk(rp, 320)
                            if rimg:
                                holder = tk.Label(
                                    image_holder,
                                    image=rimg,
                                    bd=0,
                                    bg=palette.get("card", "#18263f"),
                                    cursor="hand2",
                                )
                                holder.grid(row=0, column=col, padx=(0, 6), pady=(0, 4), sticky="w")
                                if open_image and rp:
                                    holder.bind("<Button-1>", lambda _e, p=rp: open_image(p))
                                r_card._image_refs.append(rimg)
                            else:
                                r_file_items.append(ratt)
                    elif r_image_items:
                        r_file_items.extend(r_image_items)

                    if r_file_items:
                        file_container = ctk.CTkFrame(att_frame, fg_color="transparent")
                        file_container.grid(row=section_row, column=0, sticky="we")
                        for ridx, ratt in enumerate(r_file_items):
                            entry = ctk.CTkFrame(file_container, fg_color=surface, corner_radius=8)
                            entry.grid(row=ridx, column=0, sticky="we", pady=4)
                            entry.grid_columnconfigure(0, weight=1)

                            rname = ratt.get("name") or (ratt.get("path", "").split("/")[-1])
                            rtype = ratt.get("type", "file").title()
                            rdetails = f"[{rtype}] {rname}"
                            rsize = ratt.get("size")
                            if isinstance(rsize, int):
                                rdetails += f" • {_format_size(rsize)}"

                            ctk.CTkLabel(
                                entry,
                                text=rdetails,
                                text_color=text_color,
                                anchor="w",
                            ).grid(row=0, column=0, sticky="we", padx=10, pady=6)

                            rpath = ratt.get("path")
                            handler = callbacks.open_attachment
                            if handler:
                                ctk.CTkButton(
                                    entry,
                                    text="Open",
                                    width=70,
                                    fg_color="transparent",
                                    border_width=1,
                                    border_color=muted,
                                    text_color=muted,
                                    hover_color=surface,
                                    command=lambda attachment=ratt: handler(attachment),
                                ).grid(row=0, column=1, padx=6, pady=6)
                            elif open_image and rpath:
                                ctk.CTkButton(
                                    entry,
                                    text="Open",
                                    width=70,
                                    fg_color="transparent",
                                    border_width=1,
                                    border_color=muted,
                                    text_color=muted,
                                    hover_color=surface,
                                    command=lambda p=rpath: open_image(p),
                                ).grid(row=0, column=1, padx=6, pady=6)

                if state.current_user == reply.get("author"):
                    btns = ctk.CTkFrame(r_card, fg_color="transparent")
                    btns.grid(row=4, column=0, sticky="e", padx=12, pady=(0, 10))
                    ctk.CTkButton(
                        btns,
                        text="Edit",
                        width=60,
                        fg_color="transparent",
                        border_width=1,
                        border_color=accent,
                        text_color=accent,
                        hover_color=accent_hover,
                        command=lambda p_idx=idx, rr_idx=r_idx: callbacks.start_reply_edit(p_idx, rr_idx),
                    ).grid(row=0, column=0, padx=4)
                    ctk.CTkButton(
                        btns,
                        text="Delete",
                        width=60,
                        fg_color=danger,
                        hover_color=danger_hover,
                        command=lambda p_idx=idx, rr_idx=r_idx: callbacks.delete_reply(p_idx, rr_idx),
                    ).grid(row=0, column=1, padx=4)

        if state.reply_input_target == idx and state.current_user:
            composer = ctk.CTkFrame(replies_frame, fg_color="transparent")
            composer.grid(sticky="we", padx=8, pady=(6, 4))
            composer.grid_columnconfigure(0, weight=1)

            reply_var = tk.StringVar()
            entry = ctk.CTkEntry(
                composer,
                textvariable=reply_var,
                placeholder_text="Write a reply...",
                fg_color=surface,
                text_color=text_color,
            )
            entry.grid(row=0, column=0, sticky="we", padx=(0, 6))
            callbacks.create_reply_toolbar(composer, idx, reply_var)

            def _submit_reply_event(_event, p_idx=idx, var=reply_var) -> str:
                callbacks.submit_reply(p_idx, var)
                return "break"

            entry.bind("<Return>", _submit_reply_event)
            entry.bind("<KP_Enter>", _submit_reply_event)

            send_btn = ctk.CTkButton(
                composer,
                text="Send",
                width=70,
                fg_color=accent,
                hover_color=accent_hover,
                command=lambda p_idx=idx, var=reply_var: callbacks.submit_reply(p_idx, var),
            )
            send_btn.grid(row=0, column=1, padx=(0, 6))
            cancel_btn = ctk.CTkButton(
                composer,
                text="Cancel",
                width=70,
                fg_color="transparent",
                border_width=1,
                border_color=muted,
                text_color=muted,
                hover_color=surface,
                command=lambda: callbacks.open_reply_box(None),
            )
            cancel_btn.grid(row=0, column=2)
        elif state.current_user:
            ctk.CTkButton(
                replies_frame,
                text="Add reply",
                width=90,
                fg_color="transparent",
                border_width=1,
                border_color=muted,
                text_color=muted,
                hover_color=surface,
                command=lambda i=idx: callbacks.open_reply_box(i),
            ).grid(row=6, column=0, sticky="w", padx=8, pady=(0, 6))


def render_feed(
    *,
    feed_container: ctk.CTkScrollableFrame,
    posts: list[PostDict],
    palette: Palette,
    state: FeedState,
    callbacks: FeedCallbacks,
    load_profile_avatar: Optional[AvatarLoader] = None,
    load_image_for_tk: Optional[ImageLoader] = None,
    open_image: Optional[OpenHandler] = None,
    empty_message: str = "No posts yet. Create one above!",
) -> None:
    """Render the main feed list."""
    _clear_children(feed_container)

    if not posts:
        ctk.CTkLabel(feed_container, text=empty_message, text_color=palette.get("muted", "#94a3b8")).grid(
            sticky="w", padx=20, pady=20
        )
        return

    for idx, post in reversed(list(enumerate(posts))):
        render_post_card(
            container=feed_container,
            idx=idx,
            post=post,
            palette=palette,
            state=state,
            callbacks=callbacks,
            load_profile_avatar=load_profile_avatar,
            load_image_for_tk=load_image_for_tk,
            open_image=open_image,
        )


def render_profile(
    *,
    profile_info_label: ctk.CTkLabel,
    profile_posts_frame: ctk.CTkScrollableFrame,
    users: UserDict,
    posts: list[PostDict],
    palette: Palette,
    state: FeedState,
    callbacks: FeedCallbacks,
    total_likes_for: Callable[[str], int],
    load_profile_avatar: Optional[AvatarLoader] = None,
    load_image_for_tk: Optional[ImageLoader] = None,
    open_image: Optional[OpenHandler] = None,
    empty_message: str = "You haven't posted anything yet!",
) -> None:
    """Render the signed-in user's profile summary and posts."""
    _clear_children(profile_posts_frame)

    if not state.current_user:
        profile_info_label.configure(text="Please sign in to view your profile.", text_color=palette.get("muted", "#94a3b8"))
        return

    info = users.get(state.current_user, {})
    followers = len(info.get("followers", []))
    following = len(info.get("following", []))
    total_posts = sum(1 for post in posts if post.get("author") == state.current_user)
    total_likes = total_likes_for(state.current_user)
    achievements = compute_achievement_progress(
        state.current_user,
        users=users,
        posts=posts,
        like_counter=total_likes_for,
    )
    achievement_count = len(ACHIEVEMENTS)
    achievement_summary = "Achievements tracked: None yet"
    if achievements:
        completed = [item for item in achievements if item.get("complete")]
        top_names = ", ".join(item.get("name", "") for item in completed[:3] if item.get("name"))
        if completed:
            achievement_summary = f"Achievements: {len(completed)}/{achievement_count} complete"
            if top_names:
                achievement_summary += f"  ·  {top_names}"
        else:
            next_goal = achievements[0]
            achievement_summary = f"Next achievement: {next_goal.get('name', 'Keep going')}"

    details: list[str] = []
    details.append(f"Registered: {info.get('registered_at', 'Unknown')}")
    bio = info.get("bio")
    if bio:
        details.append(f"Bio: {bio}")
    location = info.get("location")
    if location:
        details.append(f"Location: {location}")
    website = info.get("website")
    if website:
        details.append(f"Website: {website}")
    details.append(achievement_summary)

    profile_info_label.configure(
        text="\n".join(details),
        text_color=palette.get("muted", "#94a3b8"),
        justify="left",
        anchor="w",
    )

    user_posts = [(idx, post) for idx, post in enumerate(posts) if post.get("author") == state.current_user]
    if not user_posts:
        ctk.CTkLabel(profile_posts_frame, text=empty_message, text_color=palette.get("muted", "#94a3b8")).grid(
            sticky="w", padx=20, pady=20
        )
        return

    for idx, post in reversed(user_posts):
        render_post_card(
            container=profile_posts_frame,
            idx=idx,
            post=post,
            palette=palette,
            state=state,
            callbacks=callbacks,
            load_profile_avatar=load_profile_avatar,
            load_image_for_tk=load_image_for_tk,
            open_image=open_image,
        )