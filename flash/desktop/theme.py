"""Light / dark colour themes for the Tkinter UI."""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk

THEMES = ("system", "light", "dark")

LIGHT = {
    "bg": "#f3f4f8",
    "surface": "#ffffff",
    "surface2": "#eef0f5",
    "border": "#dfe2ea",
    "text": "#1b1f2a",
    "muted": "#667085",
    "accent": "#4f46e5",
    "accent_hover": "#4338ca",
    "accent_text": "#ffffff",
    "accent_soft": "#eef0ff",
    "hover": "#f6f7ff",
    "selection": "#e0e3ff",
    "track": "#e4e7ee",
    "ok": "#067647",
    "ok_bg": "#dcfae6",
    "on_ok": "#ffffff",
    "bad": "#b42318",
    "bad_bg": "#fee4e2",
    "on_bad": "#ffffff",
}

DARK = {
    "bg": "#121419",
    "surface": "#1b1e26",
    "surface2": "#252935",
    "border": "#2f3442",
    "text": "#e8eaf0",
    "muted": "#9aa2b1",
    "accent": "#8b8fff",
    "accent_hover": "#a3a6ff",
    "accent_text": "#11131a",
    "accent_soft": "#272a48",
    "hover": "#232736",
    "selection": "#30355a",
    "track": "#2c3140",
    "ok": "#4ade80",
    "ok_bg": "#14301f",
    "on_ok": "#0d1a12",
    "bad": "#f87171",
    "bad_bg": "#3a1719",
    "on_bad": "#1f0b0c",
}


class Palette(dict):
    """Current colours; read as ``P.bg`` or ``P["bg"]``."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as e:
            raise AttributeError(name) from e


P = Palette(LIGHT, name="light")


def system_prefers_dark() -> bool:
    """True if Windows is set to dark mode for apps. Always False on other systems for now."""
    if sys.platform != "win32":
        return False
    try:
        import winreg

        key = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def resolve(mode: str) -> str:
    """Turn a theme setting into ``"light"`` or ``"dark"`` (``"system"`` follows the computer)."""
    if mode == "system":
        return "dark" if system_prefers_dark() else "light"
    return mode if mode in ("light", "dark") else "light"


def style_titlebar(window: tk.Misc) -> None:
    """Dark/light window title bar on Windows 10 (1809+) and 11."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        value = ctypes.c_int(1 if P.name == "dark" else 0)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (new, old builds)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
        # Force the non-client area to repaint with the new colour.
        flags = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020  # NOSIZE|NOMOVE|NOZORDER|NOACTIVATE|FRAMECHANGED
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, flags)
    except Exception:
        pass


def apply(root: tk.Tk, mode: str, fonts: dict) -> None:
    """Switch the palette :data:`P` to ``mode`` and restyle the window, its widgets and ``fonts``."""
    P.clear()
    name = resolve(mode)
    P.update(DARK if name == "dark" else LIGHT, name=name)

    root.configure(bg=P.bg)
    root.option_add("*TCombobox*Listbox.background", P.surface)
    root.option_add("*TCombobox*Listbox.foreground", P.text)
    root.option_add("*TCombobox*Listbox.selectBackground", P.selection)
    root.option_add("*TCombobox*Listbox.selectForeground", P.text)
    root.option_add("*TCombobox*Listbox.font", fonts["base"])
    root.option_add("*Menu.background", P.surface)
    root.option_add("*Menu.foreground", P.text)
    root.option_add("*Menu.activeBackground", P.selection)
    root.option_add("*Menu.activeForeground", P.text)

    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(
        ".",
        background=P.bg,
        foreground=P.text,
        fieldbackground=P.surface,
        bordercolor=P.border,
        lightcolor=P.border,
        darkcolor=P.border,
        troughcolor=P.track,
        focuscolor=P.accent,
        selectbackground=P.selection,
        selectforeground=P.text,
        insertcolor=P.text,
        font=fonts["base"],
        arrowcolor=P.muted,
    )

    def button(name, bg, fg, border, hover, pressed, font="base", padding=(14, 7)):
        s.configure(
            name,
            background=bg,
            foreground=fg,
            bordercolor=border,
            lightcolor=bg,
            darkcolor=bg,
            relief="flat",
            padding=padding,
            font=fonts[font],
            focusthickness=0,
            anchor="center",
        )
        s.map(
            name,
            background=[("disabled", P.surface2), ("pressed", pressed), ("active", hover)],
            lightcolor=[("pressed", pressed), ("active", hover)],
            darkcolor=[("pressed", pressed), ("active", hover)],
            bordercolor=[("focus", border), ("active", border)],
            foreground=[("disabled", P.muted)],
        )

    button("TButton", P.surface, P.text, P.border, P.hover, P.surface2)
    button(
        "Accent.TButton",
        P.accent,
        P.accent_text,
        P.accent,
        P.accent_hover,
        P.accent_hover,
        font="bold",
        padding=(18, 8),
    )
    button("Ghost.TButton", P.bg, P.text, P.bg, P.surface2, P.border)
    button("CardGhost.TButton", P.surface, P.muted, P.surface, P.surface2, P.border, font="bold", padding=(10, 6))
    button("Chip.TButton", P.surface2, P.text, P.surface2, P.selection, P.selection, font="small", padding=(10, 4))

    for w in ("TEntry", "TSpinbox", "TCombobox"):
        s.configure(
            w,
            fieldbackground=P.surface,
            foreground=P.text,
            bordercolor=P.border,
            lightcolor=P.surface,
            darkcolor=P.surface,
            padding=(8, 5),
            arrowsize=14,
            background=P.surface2,
            insertcolor=P.text,
        )
        s.map(
            w,
            bordercolor=[("focus", P.accent)],
            lightcolor=[("focus", P.accent)],
            fieldbackground=[("readonly", P.surface)],
            foreground=[("readonly", P.text)],
            selectbackground=[("readonly", P.surface)],
            selectforeground=[("readonly", P.text)],
            background=[("active", P.selection)],
        )

    for w in ("TCheckbutton", "TRadiobutton"):
        s.configure(
            w,
            background=P.surface,
            foreground=P.text,
            indicatorbackground=P.surface,
            indicatorforeground=P.accent_text,
            indicatorcolor=P.surface,
            upperbordercolor=P.border,
            lowerbordercolor=P.border,
            font=fonts["base"],
            padding=(2, 4),
            indicatormargin=(0, 0, 8, 0),
        )
        s.map(w, indicatorcolor=[("selected", P.accent), ("active", P.hover)], background=[("active", P.surface)])

    for orient in ("Vertical", "Horizontal"):
        s.configure(
            f"{orient}.TScrollbar",
            background=P.surface2,
            troughcolor=P.bg,
            bordercolor=P.bg,
            lightcolor=P.surface2,
            darkcolor=P.surface2,
            arrowcolor=P.muted,
            gripcount=0,
        )
        s.map(f"{orient}.TScrollbar", background=[("active", P.border)])

    for name, color in (("Accent", P.accent), ("Ok", P.ok)):
        s.configure(
            f"{name}.Horizontal.TProgressbar",
            background=color,
            troughcolor=P.track,
            bordercolor=P.track,
            lightcolor=color,
            darkcolor=color,
            thickness=6,
        )

    s.configure("TFrame", background=P.bg)
    s.configure("Card.TFrame", background=P.surface)
    s.configure("TLabel", background=P.bg, foreground=P.text)

    style_titlebar(root)
