"""Form field components styled with Tailwind."""
from __future__ import annotations

from markupsafe import Markup


_INPUT_BASE = (
    "block w-full rounded-xl border border-slate-700/60 bg-slate-900/70 px-4 py-2.5 text-sm text-slate-100 "
    "placeholder:text-slate-500 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-600 focus:ring-offset-0"
)


def text_input(name: str, *, label: str, placeholder: str = "", type_: str = "text", required: bool = True) -> Markup:
    required_attr = "required" if required else ""
    return Markup(
        f"""
        <label class=\"flex flex-col gap-2 text-sm font-medium text-slate-200\" for=\"{name}\">
            <span>{label}</span>
            <input id=\"{name}\" name=\"{name}\" type=\"{type_}\" placeholder=\"{placeholder}\" class=\"{_INPUT_BASE}\" {required_attr}>
        </label>
        """
    )


def password_input(name: str, *, label: str, placeholder: str = "", required: bool = True) -> Markup:
    return text_input(name, label=label, placeholder=placeholder, type_="password", required=required)


def textarea(name: str, *, label: str, placeholder: str = "", rows: int = 4, required: bool = False) -> Markup:
    required_attr = "required" if required else ""
    return Markup(
        f"""
        <label class=\"flex flex-col gap-2 text-sm font-medium text-slate-200\" for=\"{name}\">
            <span>{label}</span>
            <textarea id=\"{name}\" name=\"{name}\" rows=\"{rows}\" placeholder=\"{placeholder}\" class=\"{_INPUT_BASE} resize-none\" {required_attr}></textarea>
        </label>
        """
    )


def file_input(name: str, *, label: str, accept: str = "image/*,video/*") -> Markup:
    return Markup(
        f"""
        <label class=\"flex flex-col gap-2 text-sm font-medium text-slate-200\" for=\"{name}\">
            <span>{label}</span>
            <input id=\"{name}\" name=\"{name}\" type=\"file\" accept=\"{accept}\" class=\"{_INPUT_BASE} file:mr-4 file:rounded-full file:border-0 file:bg-indigo-500 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-white hover:file:bg-indigo-400\">
        </label>
        """
    )


def toggle(id_: str, *, label: str, checked: bool = False) -> Markup:
    state = "checked" if checked else ""
    knob_classes = "inline-flex h-5 w-5 transform rounded-full bg-white transition"
    return Markup(
        f"""
        <label class=\"flex cursor-pointer items-center gap-3 text-sm text-slate-200\">
            <span>{label}</span>
            <input id=\"{id_}\" type=\"checkbox\" class=\"peer hidden\" {state}>
            <span class=\"relative h-6 w-11 rounded-full bg-slate-700 transition peer-checked:bg-indigo-500\">
                <span class=\"{knob_classes} peer-checked:translate-x-5 peer-checked:bg-white\"></span>
            </span>
        </label>
        """
    )


__all__ = ["text_input", "password_input", "textarea", "file_input", "toggle"]
