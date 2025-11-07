import tkinter as tk
from typing import Any, Callable, Optional
from uuid import uuid4

import customtkinter as ctk

Palette = dict[str, str]
UserDict = dict[str, Any]
MessageDict = dict[str, list[dict[str, Any]]]
ImageLoader = Callable[[str, int], Optional[tk.PhotoImage]]
AvatarLoader = Callable[[str, int], Optional[tk.PhotoImage]]
OpenHandler = Callable[[str], None]
AttachmentOpener = Callable[[dict[str, Any]], None]
DEFAULT_REACTIONS: list[str] = ["👍", "❤️", "😂"]


def convo_id(user_a: Optional[str], user_b: Optional[str]) -> str:
    """Return a stable conversation id for two usernames (case-insensitive)."""
    a = (user_a or "").strip()
    b = (user_b or "").strip()
    return "|".join(sorted([a, b], key=str.lower))


def _clear_children(frame: Any) -> None:
    if frame:
        for child in frame.winfo_children():
            child.destroy()


def _ellipsize(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)] + "…"


def render_dm_sidebar(
    *,
    dm_following_list: Optional[ctk.CTkScrollableFrame],
    palette: Palette,
    current_user: Optional[str],
    users: UserDict,
    group_chats: list[dict[str, Any]],
    active_dm_user: Optional[str],
    active_conversation_id: Optional[str],
    open_dm_with: Callable[[str], None],
    open_group_chat: Callable[[str], None],
    create_group_chat: Callable[[], None],
    join_group_chat_from_link: Callable[[], None],
) -> None:
    """Render the DM conversation list sidebar."""
    if dm_following_list is None:
        return

    _clear_children(dm_following_list)

    surface = palette.get("surface", "#111b2e")
    text = palette.get("text", "#e2e8f0")
    muted = palette.get("muted", "#94a3b8")
    accent = palette.get("accent", "#4c8dff")
    accent_hover = palette.get("accent_hover", "#3b6dd6")

    if not current_user:
        ctk.CTkLabel(
            dm_following_list,
            text="Sign in to start messaging.",
            text_color=muted,
            anchor="w",
        ).grid(sticky="we", padx=12, pady=12)
        return

    header_row = ctk.CTkFrame(dm_following_list, fg_color="transparent")
    header_row.grid(sticky="we", padx=12, pady=(12, 6))
    header_row.grid_columnconfigure(0, weight=1)
    header_row.grid_columnconfigure(1, weight=0)
    header_row.grid_columnconfigure(2, weight=0)

    ctk.CTkLabel(
        header_row,
        text="Conversations",
        text_color=muted,
        anchor="w",
    ).grid(row=0, column=0, sticky="w")

    new_group_btn = ctk.CTkButton(
        header_row,
        text="New group",
        width=110,
        command=create_group_chat,
        fg_color="transparent",
        border_width=1,
        border_color=palette.get("accent", "#4c8dff"),
        text_color=palette.get("accent", "#4c8dff"),
        hover_color=surface,
    )
    new_group_btn.grid(row=0, column=1, sticky="e")

    join_group_btn = ctk.CTkButton(
        header_row,
        text="Join via link",
        width=120,
        command=join_group_chat_from_link,
        fg_color="transparent",
        border_width=1,
        border_color=palette.get("accent", "#4c8dff"),
        text_color=palette.get("accent", "#4c8dff"),
        hover_color=surface,
    )
    join_group_btn.grid(row=0, column=2, sticky="e", padx=(8, 0))

    following = users.get(current_user, {}).get("following", [])
    if following:
        ctk.CTkLabel(
            dm_following_list,
            text="Direct messages",
            text_color=muted,
            anchor="w",
        ).grid(sticky="we", padx=12, pady=(0, 4))

        for username in sorted(following, key=str.lower):
            convo_key = convo_id(current_user, username)
            is_active = (username == active_dm_user) or (active_conversation_id == convo_key)
            label_text = _ellipsize(f"@{username}", 22)
            btn = ctk.CTkButton(
                dm_following_list,
                text=label_text,
                anchor="w",
                fg_color=accent if is_active else "transparent",
                hover_color=accent_hover,
                text_color="white" if is_active else text,
                border_width=0 if is_active else 1,
                border_color=palette.get("muted", "#94a3b8"),
                command=lambda u=username: open_dm_with(u),
            )
            btn.grid(sticky="we", padx=12, pady=4)
    else:
        ctk.CTkLabel(
            dm_following_list,
            text="You aren’t following anyone yet.",
            text_color=muted,
            anchor="w",
        ).grid(sticky="we", padx=12, pady=(0, 12))

    user_groups = [chat for chat in group_chats if current_user in chat.get("members", [])]

    ctk.CTkLabel(
        dm_following_list,
        text="Group chats",
        text_color=muted,
        anchor="w",
    ).grid(sticky="we", padx=12, pady=(16, 4))

    if not user_groups:
        ctk.CTkLabel(
            dm_following_list,
            text="No group chats yet.",
            text_color=muted,
            anchor="w",
        ).grid(sticky="we", padx=12, pady=(0, 12))
    else:
        user_groups.sort(key=lambda c: (c.get("name") or "").lower())
        user_groups.sort(
            key=lambda c: c.get("updated_at") or c.get("created_at") or "",
            reverse=True,
        )
        for chat in user_groups:
            chat_id = chat.get("id")
            display_name = chat.get("name") or "Group chat"
            member_count = len(chat.get("members", []))
            text_label = _ellipsize(f"{display_name} ({member_count})", 28)
            is_active = active_conversation_id == chat_id
            btn = ctk.CTkButton(
                dm_following_list,
                text=text_label,
                anchor="w",
                fg_color=accent if is_active else "transparent",
                hover_color=accent_hover,
                text_color="white" if is_active else text,
                border_width=0 if is_active else 1,
                border_color=palette.get("muted", "#94a3b8"),
                command=lambda gid=chat_id: open_group_chat(gid or ""),
            )
            btn.grid(sticky="we", padx=12, pady=4)


def render_dm(
    *,
    dm_header: ctk.CTkLabel,
    dm_thread: ctk.CTkScrollableFrame,
    palette: Palette,
    current_user: Optional[str],
    active_dm_user: Optional[str],
    active_conversation_id: Optional[str],
    users: UserDict,
    messages: MessageDict,
    group_chats: list[dict[str, Any]],
    load_profile_avatar: Optional[AvatarLoader],
    open_profile: Optional[OpenHandler],
    load_image_for_tk: Optional[ImageLoader],
    open_image: Optional[OpenHandler],
    open_attachment: Optional[AttachmentOpener] = None,
    render_inline_video: Optional[Callable[..., None]] = None,
    sidebar_renderer: Optional[Callable[[], None]] = None,
    on_toggle_reaction: Optional[Callable[[str, str, str], None]] = None,
    reaction_emojis: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Render the DM thread view."""
    if sidebar_renderer:
        sidebar_renderer()

    _clear_children(dm_thread)
    dm_thread.grid_columnconfigure(0, weight=1)

    surface = palette.get("surface", "#111b2e")
    card = palette.get("card", "#18263f")
    accent = palette.get("accent", "#4c8dff")
    accent_muted = palette.get("muted", "#94a3b8")
    text = palette.get("text", "#e2e8f0")

    info: dict[str, Any] = {
        "conversation_type": None,
        "group_chat": None,
        "participants": [],
        "can_send": False,
        "conversation_id": active_conversation_id,
        "messages": [],
        "last_incoming": None,
    }

    if not current_user:
        dm_header.configure(text="Direct Message")
        ctk.CTkLabel(
            dm_thread,
            text="Sign in to view your messages.",
            text_color=palette.get("muted", "#94a3b8"),
        ).grid(sticky="nwe", padx=12, pady=12)
        return info

    conversation_id = active_conversation_id
    thread: list[dict[str, Any]] = []
    title = "Direct Message"

    if conversation_id and conversation_id.startswith("group:"):
        chat = next((g for g in group_chats if g.get("id") == conversation_id), None)
        if not chat or current_user not in chat.get("members", []):
            dm_header.configure(text="Select a conversation")
            ctk.CTkLabel(
                dm_thread,
                text="Select a conversation to start chatting.",
                text_color=palette.get("muted", "#94a3b8"),
            ).grid(sticky="nwe", padx=12, pady=12)
            return info
        title = chat.get("name") or "Group chat"
        thread = chat.get("messages", [])
        info.update(
            {
                "conversation_type": "group",
                "group_chat": chat,
                "participants": chat.get("members", []),
                "can_send": True,
                "conversation_id": chat.get("id"),
            }
        )
    else:
        partner = active_dm_user
        if not partner and conversation_id:
            parts = [p for p in conversation_id.split("|") if p]
            for handle in parts:
                if handle.lower() != (current_user or "").lower():
                    partner = handle
                    break
        if not partner:
            dm_header.configure(text="Select a conversation")
            ctk.CTkLabel(
                dm_thread,
                text="Select a conversation to start chatting.",
                text_color=palette.get("muted", "#94a3b8"),
            ).grid(sticky="nwe", padx=12, pady=12)
            return info
        convo_key = convo_id(current_user, partner)
        thread = messages.get(convo_key, [])
        title = f"DM with @{partner}"
        info.update(
            {
                "conversation_type": "dm",
                "participants": [current_user, partner],
                "can_send": True,
                "conversation_id": convo_key,
            }
        )

    dm_header.configure(text=title)

    assigned_ids = False
    normalized_thread: list[dict[str, Any]] = []
    for original in thread:
        if not isinstance(original, dict):
            continue
        if not original.get("id"):
            original["id"] = uuid4().hex
            assigned_ids = True
        reactions = original.get("reactions")
        if not isinstance(reactions, dict):
            original["reactions"] = {}
        attachments = original.get("attachments")
        if attachments is not None and not isinstance(attachments, list):
            original["attachments"] = []
        normalized_thread.append(original)

    thread = normalized_thread

    info["messages"] = thread
    info["assigned_message_ids"] = assigned_ids
    for msg in reversed(thread):
        sender = msg.get("sender")
        if sender and sender != current_user:
            info["last_incoming"] = {"sender": sender, "time": msg.get("time")}
            break

    reactions_list = reaction_emojis or DEFAULT_REACTIONS
    last_outgoing_idx: Optional[int] = None
    if current_user:
        for idx in range(len(thread) - 1, -1, -1):
            if thread[idx].get("sender") == current_user:
                last_outgoing_idx = idx
                break

    for row_idx, msg in enumerate(thread):
        sender = msg.get("sender", "")
        is_me = sender == current_user

        row = ctk.CTkFrame(dm_thread, fg_color="transparent")
        row.grid(row=row_idx, column=0, sticky="e" if is_me else "w", padx=8, pady=6)
        row.grid_columnconfigure(0, weight=1)

        container = ctk.CTkFrame(row, fg_color="transparent")
        container.grid(row=0, column=0, sticky="e" if is_me else "w")
        container.grid_columnconfigure(0, weight=0)
        container.grid_columnconfigure(1, weight=1)

        avatar_col = 1 if is_me else 0
        bubble_col = 0 if is_me else 1
        avatar_pad = (12, 0) if is_me else (0, 12)
        bubble_pad = (0, 12) if is_me else (12, 0)

        avatar_photo: Optional[tk.PhotoImage] = None
        if load_profile_avatar:
            try:
                avatar_photo = load_profile_avatar(sender, 44)
            except Exception:
                avatar_photo = None

        row._image_refs = []  # type: ignore[attr-defined]

        if avatar_photo:
            avatar = tk.Label(container, image=avatar_photo, bd=0, bg=surface, cursor="hand2")
            avatar.grid(row=0, column=avatar_col, sticky="ne" if is_me else "nw", padx=avatar_pad)
            if open_profile:
                avatar.bind("<Button-1>", lambda _e, u=sender: open_profile(u))
            row._image_refs.append(avatar_photo)

        bubble = ctk.CTkFrame(
            container,
            corner_radius=12,
            fg_color=accent if is_me else card,
        )
        bubble.grid(row=0, column=bubble_col, sticky="e" if is_me else "w", padx=bubble_pad)
        bubble.grid_columnconfigure(0, weight=1)
        bubble._image_refs = []  # type: ignore[attr-defined]

        name_label = ctk.CTkLabel(
            bubble,
            text=f"@{sender}",
            text_color="white" if is_me else accent_muted,
            font=ctk.CTkFont(size=10, weight="bold"),
        )
        name_label.grid(row=0, column=0, sticky="w", padx=10, pady=(8, 2))
        if open_profile:
            name_label.configure(cursor="hand2")
            name_label.bind("<Button-1>", lambda _e, u=sender: open_profile(u))

        line_idx = 1
        content = msg.get("content")
        if content:
            tk.Label(
                bubble,
                text=content,
                wraplength=420,
                justify="left",
                bg=bubble.cget("fg_color"),
                fg="white" if is_me else text,
                font=("Segoe UI Emoji", 11),
            ).grid(row=line_idx, column=0, sticky="w", padx=10, pady=(0, 4))
            line_idx += 1

        attachments_list = msg.get("attachments") or []
        if attachments_list and isinstance(attachments_list, list):
            image_items: list[dict[str, Any]] = []
            video_items: list[dict[str, Any]] = []
            file_items: list[dict[str, Any]] = []
            for attachment in attachments_list:
                if not isinstance(attachment, dict):
                    continue
                att_type = attachment.get("type")
                if att_type == "image" and load_image_for_tk:
                    image_items.append(attachment)
                elif att_type == "video":
                    video_items.append(attachment)
                else:
                    file_items.append(attachment)

            if video_items:
                if render_inline_video:
                    for video_att in video_items:
                        holder = ctk.CTkFrame(bubble, fg_color="transparent")
                        holder.grid(row=line_idx, column=0, sticky="we", padx=10, pady=(0, 6))
                        try:
                            render_inline_video(
                                video_att,
                                holder,
                                controls=False,
                                click_to_toggle=True,
                            )
                        except Exception:
                            file_items.append(video_att)
                        else:
                            line_idx += 1
                else:
                    file_items.extend(video_items)

            if image_items:
                for image_att in image_items:
                    img: Optional[tk.PhotoImage] = None
                    try:
                        img = load_image_for_tk(image_att.get("path", ""), 320) if load_image_for_tk else None
                    except Exception:
                        img = None
                    if img:
                        holder = tk.Label(
                            bubble,
                            image=img,
                            bd=0,
                            cursor="hand2",
                            bg=bubble.cget("fg_color"),
                        )
                        holder.grid(row=line_idx, column=0, sticky="w", padx=10, pady=(0, 6))
                        if open_image and image_att.get("path"):
                            holder.bind("<Button-1>", lambda _e, p=image_att.get("path"): open_image(p))
                        bubble._image_refs.append(img)
                        line_idx += 1
                    else:
                        file_items.append(image_att)

            if file_items:
                for file_att in file_items:
                    entry = ctk.CTkFrame(bubble, fg_color="transparent")
                    entry.grid(row=line_idx, column=0, sticky="we", padx=10, pady=(0, 6))
                    entry.grid_columnconfigure(0, weight=1)

                    name = file_att.get("name") or file_att.get("path", "").split("/")[-1]
                    type_label = (file_att.get("type") or "file").title()
                    ctk.CTkLabel(
                        entry,
                        text=f"[{type_label}] {name}",
                        text_color="white" if is_me else text,
                        anchor="w",
                    ).grid(row=0, column=0, sticky="w")

                    handler: Optional[Callable[[], None]] = None
                    if open_attachment:
                        handler = lambda att=file_att: open_attachment(att)
                    elif open_image and file_att.get("path"):
                        handler = lambda path=file_att.get("path"): open_image(path)

                    if handler:
                        ctk.CTkButton(
                            entry,
                            text="Open",
                            width=60,
                            command=handler,
                            fg_color="transparent",
                            border_width=1,
                            border_color=accent_muted,
                            text_color=accent_muted if not is_me else "white",
                            hover_color=card,
                        ).grid(row=0, column=1, padx=(8, 0))

                    line_idx += 1

        msg_id = msg.get("id")
        reactions = msg.get("reactions") if isinstance(msg.get("reactions"), dict) else {}
        if on_toggle_reaction and msg_id and reactions_list:
            reaction_row = ctk.CTkFrame(bubble, fg_color="transparent")
            reaction_row.grid(row=line_idx, column=0, sticky="w", padx=6 if is_me else 10, pady=(0, 4))
            for col, emoji in enumerate(reactions_list):
                reactors: list[str] = []
                if isinstance(reactions, dict):
                    raw_reactors = reactions.get(emoji, [])
                    if isinstance(raw_reactors, list):
                        reactors = [r for r in raw_reactors if isinstance(r, str)]
                count = len(reactors)
                selected = current_user in reactors if current_user else False
                label = f"{emoji} {count}" if count else emoji
                ctk.CTkButton(
                    reaction_row,
                    text=label,
                    width=60,
                    fg_color=(accent if selected else "transparent"),
                    hover_color=accent if selected else accent_muted,
                    border_width=0 if selected else 1,
                    border_color=accent_muted,
                    text_color="white" if selected else ("white" if is_me else text),
                    command=lambda conv=conversation_id, mid=msg_id, emo=emoji: on_toggle_reaction(conv or "", mid, emo),
                ).grid(row=0, column=col, padx=2)
            line_idx += 1

        tk.Label(
            bubble,
            text=msg.get("time", ""),
            bg=bubble.cget("fg_color"),
            fg="#dbeafe" if is_me else accent_muted,
            font=("Segoe UI", 8),
        ).grid(row=line_idx, column=0, sticky="e" if is_me else "w", padx=10, pady=(0, 6))
        line_idx += 1

        if is_me and last_outgoing_idx is not None and row_idx == last_outgoing_idx:
            raw_seen = msg.get("seen_by")
            seen_by = [r for r in raw_seen if isinstance(r, str)] if isinstance(raw_seen, list) else []
            others = [user for user in seen_by if user != current_user]
            if others:
                receipt_text: Optional[str] = None
                if info.get("conversation_type") == "dm":
                    partners = [p for p in info.get("participants", []) if p != current_user]
                    partner = partners[0] if partners else None
                    if partner and partner in others:
                        receipt_text = f"Seen by @{partner}"
                else:
                    participants = info.get("participants", []) or others
                    valid = [name for name in others if name in participants or not participants]
                    if valid:
                        handles = [f"@{name}" for name in valid]
                        if len(handles) == 1:
                            receipt_text = f"Seen by {handles[0]}"
                        elif len(handles) == 2:
                            receipt_text = f"Seen by {handles[0]} and {handles[1]}"
                        else:
                            receipt_text = f"Seen by {handles[0]}, {handles[1]} +{len(handles) - 2}"
                if receipt_text:
                    ctk.CTkLabel(
                        bubble,
                        text=receipt_text,
                        font=ctk.CTkFont(size=10, slant="italic"),
                        text_color=accent_muted,
                    ).grid(row=line_idx, column=0, sticky="e", padx=10, pady=(0, 6))
                    line_idx += 1

        row._image_refs.extend(bubble._image_refs)

    return info