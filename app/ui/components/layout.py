"""Layout building blocks shared across pages."""
from __future__ import annotations

from markupsafe import Markup
from markupsafe import Markup


NAV_LINKS = (
    ("Feed", "/"),
    ("Profile", "/profile"),
    ("Messages", "/messages"),
    ("Notifications", "/notifications"),
    ("Media", "/media"),
)
LOGO_IMAGE = "/assets/img/social-sphere-logo.png"


def navbar(*, active: str | None = None) -> Markup:
    links_html = []
    for label, href in NAV_LINKS:
        is_active = "text-white" if active == href else "text-slate-300"
        links_html.append(
            f"<a href=\"{href}\" class=\"rounded-full px-4 py-2 text-sm font-medium transition hover:text-white {is_active}\">{label}</a>"
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
