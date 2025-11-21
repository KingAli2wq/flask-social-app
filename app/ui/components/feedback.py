"""Feedback elements like loaders and toast containers."""
from __future__ import annotations

from markupsafe import Markup


def loading_spinner(*, label: str = "Loading") -> Markup:
    return Markup(
        f"""
        <div class=\"flex items-center gap-3 text-sm text-slate-200\">
            <span class=\"inline-block h-3 w-3 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent\"></span>
            <span>{label}…</span>
        </div>
        """
    )


def toast_container() -> Markup:
    return Markup(
        """
        <div id=\"toast-root\" class=\"pointer-events-none fixed inset-x-0 top-5 z-50 flex flex-col items-center gap-3\"></div>
        """
    )


__all__ = ["loading_spinner", "toast_container"]
