"""Reusable button components for the UI."""
from __future__ import annotations

from markupsafe import Markup


def primary(label: str, *, id_: str | None = None, href: str | None = None, icon: str | None = None) -> Markup:
    """Return a stylised primary button."""

    base = "inline-flex items-center justify-center gap-2 rounded-full bg-indigo-600 px-5 py-2 text-sm font-semibold text-white shadow-lg shadow-indigo-500/30 transition hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
    content = f"<span>{label}</span>"
    if icon:
        content = f"<span class=\"text-base\">{icon}</span>{content}"

    attrs = []
    if id_:
        attrs.append(f'id="{id_}"')

    if href:
        attrs.append(f'href="{href}"')
        tag = "a"
    else:
        tag = "button"
        attrs.append("type=\"button\"")

    attr_str = " ".join(attrs)
    return Markup(f"<{tag} class=\"{base}\" {attr_str}>{content}</{tag}>")


def ghost(label: str, *, id_: str | None = None, icon: str | None = None) -> Markup:
    """Return a subtle button suitable for secondary actions."""

    base = "inline-flex items-center gap-2 rounded-full border border-slate-600/40 px-4 py-2 text-sm font-medium text-slate-100 transition hover:border-indigo-500 hover:text-indigo-300"
    content = f"<span>{label}</span>"
    if icon:
        content = f"<span class=\"text-base\">{icon}</span>{content}"

    attrs = ["type=\"button\""]
    if id_:
        attrs.append(f'id="{id_}"')

    return Markup(f"<button class=\"{base}\" {' '.join(attrs)}>{content}</button>")


__all__ = ["primary", "ghost"]
