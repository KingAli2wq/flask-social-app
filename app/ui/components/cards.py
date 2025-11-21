"""Card-style components for feed, notifications, and chats."""
from __future__ import annotations

from datetime import datetime
from typing import Iterable

from markupsafe import Markup, escape


def post_card(
    *,
    username: str,
    content: str,
    timestamp: datetime,
    avatar_url: str | None = None,
    media_url: str | None = None,
    reactions: Iterable[str] | None = None,
) -> Markup:
    """Return a post card ready for inline rendering."""

    avatar = avatar_url or "https://ui-avatars.com/api/?background=6366f1&color=fff&name=" + escape(username)
    date_text = timestamp.strftime("%b %d, %Y • %I:%M %p")
    media_block = (
        f"<img src=\"{escape(media_url)}\" alt=\"media\" class=\"mt-4 w-full rounded-2xl object-cover\">"
        if media_url
        else ""
    )
    reactions_html = ""
    if reactions:
        chips = "".join(
            f"<span class=\"rounded-full bg-slate-800/70 px-2.5 py-1 text-xs text-slate-200\">{escape(reaction)}</span>"
            for reaction in reactions
        )
        reactions_html = f"<div class=\"mt-3 flex flex-wrap gap-2\">{chips}</div>"

    return Markup(
        f"""
        <article class=\"group rounded-3xl bg-slate-900/70 p-6 shadow-lg shadow-black/20 transition hover:-translate-y-1 hover:shadow-indigo-600/20\">
            <header class=\"flex items-center gap-4\">
                <img src=\"{avatar}\" alt=\"{escape(username)}\" class=\"h-12 w-12 rounded-full border border-slate-700/60\">
                <div>
                    <p class=\"text-sm font-semibold text-white\">{escape(username)}</p>
                    <p class=\"text-xs text-slate-400\">{escape(date_text)}<span class=\"ml-2 hidden text-xs text-indigo-400 group-hover:inline\">• Live</span></p>
                </div>
            </header>
            <p class=\"mt-4 whitespace-pre-line text-sm text-slate-200\">{escape(content)}"""
        + """
            </p>
        """
        + media_block
        + reactions_html
        + """
            <footer class=\"mt-6 flex flex-wrap items-center gap-3 text-sm text-slate-400\">
                <button class=\"like-btn inline-flex items-center gap-2 rounded-full bg-slate-800/90 px-4 py-2 transition hover:bg-indigo-600 hover:text-white\" data-username=\"{escape(username)}\">
                    <span class=\"text-base\">❤</span><span>Like</span>
                </button>
                <button class=\"comment-btn inline-flex items-center gap-2 rounded-full bg-slate-800/90 px-4 py-2 transition hover:bg-indigo-600 hover:text-white\">
                    <span class=\"text-base\">💬</span><span>Comment</span>
                </button>
                <button class=\"share-btn inline-flex items-center gap-2 rounded-full bg-slate-800/90 px-4 py-2 transition hover:bg-indigo-600 hover:text-white\">
                    <span class=\"text-base\">↗</span><span>Share</span>
                </button>
            </footer>
        </article>
        """
    )


def notification_item(*, content: str, timestamp: datetime, read: bool) -> Markup:
    tone = "bg-slate-900/70" if read else "bg-indigo-500/10 border border-indigo-400/40"
    state_chip = "Read" if read else "New"
    chip_classes = "rounded-full bg-slate-800/80 px-3 py-1 text-xs font-semibold text-slate-300"
    date_text = timestamp.strftime("%b %d, %Y • %I:%M %p")
    return Markup(
        f"""
        <li class=\"{tone} rounded-2xl p-5 shadow-md shadow-black/10 transition hover:shadow-indigo-500/20\">
            <div class=\"flex items-center justify-between\">
                <span class=\"{chip_classes}\">{state_chip}</span>
                <time class=\"text-xs text-slate-400\">{escape(date_text)}</time>
            </div>
            <p class=\"mt-3 text-sm text-slate-200\">{escape(content)}"""
        + """
            </p>
        </li>
        """
    )


def message_bubble(*, content: str, timestamp: datetime, outbound: bool) -> Markup:
    alignment = "items-end" if outbound else "items-start"
    bubble_classes = "max-w-[75%] rounded-2xl px-4 py-3 text-sm shadow-lg"
    bubble_palette = "bg-indigo-600 text-white" if outbound else "bg-slate-800/90 text-slate-100"
    date_text = timestamp.strftime("%I:%M %p")
    return Markup(
        f"""
        <div class=\"flex {alignment}\">
            <div class=\"{bubble_classes} {bubble_palette}\">
                <p class=\"whitespace-pre-line leading-relaxed\">{escape(content)}"""
        + """
                </p>
                <span class=\"mt-2 block text-right text-xs text-white/70\">{escape(date_text)}</span>
            </div>
        </div>
        """
    )


__all__ = ["post_card", "notification_item", "message_bubble"]
