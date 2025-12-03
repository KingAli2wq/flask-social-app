"""Layout building blocks shared across pages."""
from __future__ import annotations

import os

from markupsafe import Markup

STATIC_VERSION = os.getenv("STATIC_ASSET_VERSION", "20251126")

NAV_LINKS = (
    ("Feed", "/"),
    ("Profile", "/profile"),
    ("Search", "/friends/search"),
    ("Messages", "/messages"),
    ("Notifications", "/notifications"),
    ("Settings", "/settings"),
    ("Media", "/media"),
    ("Moderation", "/moderation"),
)
NAV_ROLE_REQUIREMENTS = {
    "Moderation": {"owner", "admin"},
}
LOGO_IMAGE = f"/assets/img/social-sphere-logo.png?v={STATIC_VERSION}"


def navbar(*, active: str | None = None) -> Markup:
    links_html = []
    for label, href in NAV_LINKS:
        is_active = "text-white" if active == href else "text-slate-300"
        extra_classes = " relative" if label == "Notifications" else ""
        indicator = (
            '<span id="nav-notifications-indicator" class="absolute -top-1 -right-2 hidden rounded-full bg-rose-500 px-2 py-0.5 text-xs font-semibold text-white shadow-lg shadow-rose-500/40">0</span>'
            if label == "Notifications"
            else ""
        )
        role_meta = NAV_ROLE_REQUIREMENTS.get(label)
        requires_attr = ""
        hidden_class = ""
        if role_meta:
            roles = ",".join(sorted(role_meta))
            requires_attr = f' data-role-gate="true" data-requires-role="{roles}" aria-hidden="true"'
            hidden_class = " hidden"
        links_html.append(
            f"<a href=\"{href}\" class=\"rounded-full px-4 py-2 text-sm font-medium transition hover:text-white{extra_classes} {is_active}{hidden_class}\"{requires_attr}>{label}{indicator}</a>"
        )
    links = "".join(links_html)

    return Markup(
        f"""
        <header class=\"sticky top-0 z-40 border-b border-slate-800/60 bg-slate-950/90 backdrop-blur\">
            <div class=\"mx-auto flex max-w-7xl items-center justify-between px-6 py-4\">
                <a href=\"/\" class=\"flex items-center gap-3 text-lg font-semibold text-white\">
                        <img src="{LOGO_IMAGE}" alt="SocialSphere logo" class="h-10 w-10 rounded-full object-cover shadow-lg shadow-indigo-500/30 border border-indigo-400/40" loading="lazy">
                    SocialSphere
                </a>
                <nav class=\"hidden items-center gap-1 md:flex\">{links}</nav>
                <div class=\"flex items-center gap-3\">
                    <button id=\"theme-toggle\" class=\"rounded-full border border-slate-700/70 px-3 py-2 text-sm text-slate-200 transition hover:border-indigo-500 hover:text-indigo-300\">
                        Toggle Theme
                    </button>
                    <a id=\"nav-auth-btn\" href=\"/login\" class=\"rounded-full border border-indigo-500/40 px-4 py-2 text-sm font-medium text-indigo-300 transition hover:bg-indigo-600/20\">Login</a>
                </div>
            </div>
        </header>
        """
    )


def shell(content: str, *, active: str | None = None) -> Markup:
    nav = navbar(active=active)
    return Markup(
        f"""
        {nav}
        <main class=\"mx-auto flex w-full max-w-7xl flex-col gap-10 px-6 py-10\">
            {content}
        </main>
        """
    )


__all__ = ["shell", "navbar", "NAV_LINKS"]
