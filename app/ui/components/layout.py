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
    desktop_links_html: list[str] = []
    mobile_links_html: list[str] = []
    for label, href in NAV_LINKS:
        is_active = active == href
        desktop_text_class = "text-white" if is_active else "text-slate-300"
        mobile_state_class = (
            "border-indigo-500/60 bg-indigo-500/10 text-white"
            if is_active
            else "border-slate-800/70 bg-slate-900/70 text-slate-200"
        )
        extra_classes = " relative" if label == "Notifications" else ""
        indicator_desktop = (
            '<span data-role="nav-notifications-indicator" class="absolute -top-1 -right-2 hidden rounded-full bg-rose-500 px-2 py-0.5 text-xs font-semibold text-white shadow-lg shadow-rose-500/40">0</span>'
            if label == "Notifications"
            else ""
        )
        indicator_mobile = (
            '<span data-role="nav-notifications-indicator" class="ml-4 hidden inline-flex min-w-[2.5rem] items-center justify-center rounded-full bg-rose-500 px-2 py-0.5 text-xs font-semibold text-white shadow-lg shadow-rose-500/40">0</span>'
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
        desktop_links_html.append(
            f"<a href=\"{href}\" class=\"rounded-full px-4 py-2 text-sm font-medium transition hover:text-white{extra_classes} {desktop_text_class}{hidden_class}\"{requires_attr}>{label}{indicator_desktop}</a>"
        )
        mobile_links_html.append(
            f"<a href=\"{href}\" class=\"flex w-full items-center justify-between rounded-2xl border px-4 py-3 text-base font-semibold transition {mobile_state_class}{hidden_class}\"{requires_attr}><span>{label}</span>{indicator_mobile}</a>"
        )

    desktop_links = "".join(desktop_links_html)
    mobile_links = "".join(mobile_links_html)

    return Markup(
        f"""
        <header class=\"sticky top-0 z-40 border-b border-slate-800/60 bg-slate-950/90 backdrop-blur\">
            <div class=\"mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-4 py-4 sm:px-6\">
                <a href=\"/\" class=\"flex min-w-[180px] flex-1 items-center gap-3 text-lg font-semibold text-white\">
                    <img src=\"{LOGO_IMAGE}\" alt=\"SocialSphere logo\" class=\"h-10 w-10 rounded-full border border-indigo-400/40 object-cover shadow-lg shadow-indigo-500/30\" loading=\"lazy\">
                    <span class=\"truncate\">SocialSphere</span>
                </a>
                <div class=\"flex w-full flex-wrap items-center justify-between gap-2 sm:flex-nowrap sm:justify-end md:w-auto\">
                    <button id=\"theme-toggle\" class=\"flex-1 rounded-full border border-slate-700/70 px-3 py-2 text-xs font-semibold text-slate-200 transition hover:border-indigo-500 hover:text-indigo-300 sm:flex-none sm:text-sm\">
                        <span class=\"sm:hidden\">Theme</span>
                        <span class=\"hidden sm:inline\">Toggle Theme</span>
                    </button>
                    <button
                        id="nav-social-ai"
                        type="button"
                        data-social-ai-open="true"
                        class="flex-1 rounded-full border border-fuchsia-500/40 px-4 py-2 text-center text-xs font-semibold text-fuchsia-200 transition hover:bg-fuchsia-500/15 hover:text-white sm:flex-none sm:text-sm"
                    >
                        Social AI
                    </button>
                    <a id=\"nav-auth-btn\" href=\"/login\" class=\"flex-1 rounded-full border border-indigo-500/40 px-4 py-2 text-center text-xs font-semibold text-indigo-300 transition hover:bg-indigo-600/20 sm:flex-none sm:text-sm\">Login</a>
                    <button id=\"mobile-nav-toggle\" type=\"button\" class=\"inline-flex items-center gap-2 rounded-full border border-slate-700/70 px-3 py-2 text-sm font-semibold text-slate-200 transition hover:border-indigo-500 hover:text-white md:hidden\" aria-controls=\"mobile-nav-panel\" aria-expanded=\"false\">
                        <span data-mobile-nav-label>Menu</span>
                        <svg data-mobile-nav-icon=\"open\" xmlns=\"http://www.w3.org/2000/svg\" class=\"h-4 w-4\" fill=\"none\" viewBox=\"0 0 24 24\" stroke=\"currentColor\" stroke-width=\"1.5\">
                            <path stroke-linecap=\"round\" stroke-linejoin=\"round\" d=\"M4 6h16M4 12h16M4 18h16\" />
                        </svg>
                        <svg data-mobile-nav-icon=\"close\" xmlns=\"http://www.w3.org/2000/svg\" class=\"hidden h-4 w-4\" fill=\"none\" viewBox=\"0 0 24 24\" stroke=\"currentColor\" stroke-width=\"1.5\">
                            <path stroke-linecap=\"round\" stroke-linejoin=\"round\" d=\"M6 18L18 6M6 6l12 12\" />
                        </svg>
                    </button>
                </div>
                <nav class=\"hidden w-full items-center gap-1 md:flex md:justify-center\">{desktop_links}</nav>
            </div>
            <div id=\"mobile-nav-panel\" class=\"hidden border-t border-slate-800/60 bg-slate-950/95 px-4 py-4 shadow-xl shadow-black/30 md:hidden\">
                <nav class=\"flex flex-col gap-2\">{mobile_links}</nav>
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
