"""Small building blocks shared by the desktop screens."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from .theme import P

if TYPE_CHECKING:
    from .app import App

APP_NAME = "FlasH"
PAD = 20


def card(parent, **kw) -> tk.Frame:
    return tk.Frame(
        parent, bg=P.surface, highlightthickness=1, highlightbackground=P.border, highlightcolor=P.border, **kw
    )


def label(parent, text="", font=None, fg=None, bg=None, **kw) -> tk.Label:
    return tk.Label(
        parent,
        text=text,
        font=font,
        fg=fg or P.text,
        bg=bg or parent.cget("bg"),
        justify=kw.pop("justify", "left"),
        anchor=kw.pop("anchor", "w"),
        **kw,
    )


def badge(parent, text, fg=None, bg=None, font=None) -> tk.Label:
    return tk.Label(parent, text=text, fg=fg or P.accent, bg=bg or P.accent_soft, font=font, padx=8, pady=1)


def style_text(widget: tk.Text, font) -> None:
    widget.configure(
        bg=P.surface,
        fg=P.text,
        insertbackground=P.text,
        selectbackground=P.selection,
        selectforeground=P.text,
        font=font,
        bd=0,
        highlightthickness=0,
        padx=18,
        pady=14,
    )


class Bar(tk.Frame):
    """Thin flat progress bar (ttk's clam bar ignores thickness)."""

    def __init__(self, master, value: float = 0.0, color=None, height: int = 6):
        super().__init__(master, bg=P.track, height=height)
        self.fill = tk.Frame(self, bg=color or P.accent, height=height)
        self.set(value)

    def set(self, value: float, color=None):
        if color:
            self.fill.configure(bg=color)
        value = min(max(value, 0.0), 1.0)
        if value <= 0:
            self.fill.place_forget()
        else:
            self.fill.place(x=0, y=0, relheight=1, relwidth=value)


class Toggle(tk.Frame):
    """Radio button or checkbox drawn on a canvas, so it looks right in both themes."""

    def __init__(self, master, text, variable, value=None, font=None):
        bg = master.cget("bg")
        super().__init__(master, bg=bg, cursor="hand2")
        self.var, self.value = variable, value
        self.radio = value is not None
        self.icon = tk.Canvas(self, width=20, height=20, bg=bg, highlightthickness=0)
        self.icon.pack(side="left", padx=(0, 10))
        self.lbl = tk.Label(self, text=text, bg=bg, fg=P.text, font=font, anchor="w")
        self.lbl.pack(side="left", fill="x")
        for w in (self, self.icon, self.lbl):
            w.bind("<Button-1>", self._click)
            w.bind("<Enter>", lambda e: self._draw(hover=True))
            w.bind("<Leave>", lambda e: self._draw())
        self._trace = variable.trace_add("write", lambda *a: self._draw())
        self._draw()

    def destroy(self):
        try:
            self.var.trace_remove("write", self._trace)
        except tk.TclError:
            pass
        super().destroy()

    def _selected(self) -> bool:
        return self.var.get() == self.value if self.radio else bool(self.var.get())

    def _click(self, event=None):
        if self.radio:
            self.var.set(self.value)
        else:
            self.var.set(not self.var.get())

    def _draw(self, hover=False):
        if not self.icon.winfo_exists():
            return
        c, on = self.icon, self._selected()
        c.delete("all")
        border = P.accent if (on or hover) else P.muted
        if self.radio:
            c.create_oval(2, 2, 18, 18, outline=border, width=2, fill=P.surface)
            if on:
                c.create_oval(6, 6, 14, 14, outline=P.accent, fill=P.accent)
        else:
            c.create_rectangle(
                2, 2, 18, 18, outline=P.accent if on else border, width=2, fill=P.accent if on else P.surface
            )
            if on:
                c.create_line(5, 10, 9, 14, 15, 6, fill=P.accent_text, width=2.5, capstyle="round")


class ScrollFrame(tk.Frame):
    """Vertically scrollable container; put children into ``.inner``."""

    def __init__(self, master, bg):
        super().__init__(master, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.canvas._flash_scroll = True
        self.sb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self._on_scroll)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner.bind("<Configure>", lambda e: self._update_region())
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))

    def _update_region(self):
        self.canvas.configure(scrollregion=(0, 0, self.inner.winfo_width(), self.inner.winfo_reqheight()))

    def show_widget(self, widget):
        """Scroll just enough to make ``widget`` fully visible."""
        self.update_idletasks()
        self._update_region()
        total = max(self.inner.winfo_reqheight(), 1)
        view = self.canvas.winfo_height()
        bottom = widget.winfo_rooty() - self.inner.winfo_rooty() + widget.winfo_height()
        if bottom > view and total > view:
            self.canvas.yview_moveto(min((bottom - view + 12) / total, 1.0))

    def _on_scroll(self, first, last):
        # Show the scrollbar only when the content does not fit.
        if float(first) <= 0.0 and float(last) >= 1.0:
            self.sb.pack_forget()
        elif not self.sb.winfo_ismapped():
            self.sb.pack(side="right", fill="y")
        self.sb.set(first, last)


class OptionRow(tk.Frame):
    """A clickable answer option: number badge + wrapped text."""

    def __init__(self, master, app: App, number: int, text: str, on_click):
        super().__init__(
            master,
            bg=P.surface,
            highlightthickness=1,
            highlightbackground=P.border,
            highlightcolor=P.border,
            cursor="hand2",
        )
        self.enabled = True
        self.badge = tk.Label(self, text=str(number), width=3, font=app.fonts["bold"], pady=2)
        self.badge.pack(side="left", padx=(10, 0), pady=7, anchor="n")
        self.text = tk.Label(self, text=text, justify="left", anchor="w", font=app.fonts["base"])
        self.text.pack(side="left", fill="x", expand=True, padx=12, pady=7)
        self.set_state("normal")
        for w in (self, self.badge, self.text):
            w.bind("<Button-1>", lambda e: self.enabled and on_click())
            w.bind("<Enter>", lambda e: self.enabled and self.set_state("hover"))
            w.bind("<Leave>", lambda e: self.enabled and self.set_state("normal"))

    def set_state(self, state: str):
        bg, border, badge_bg, badge_fg, fg = {
            "normal": (P.surface, P.border, P.surface2, P.muted, P.text),
            "hover": (P.hover, P.accent, P.accent_soft, P.accent, P.text),
            "correct": (P.ok_bg, P.ok, P.ok, P.on_ok, P.text),
            "wrong": (P.bad_bg, P.bad, P.bad, P.on_bad, P.text),
            "dim": (P.surface, P.border, P.surface2, P.muted, P.muted),
        }[state]
        self.configure(bg=bg, highlightbackground=border, highlightcolor=border)
        self.badge.configure(bg=badge_bg, fg=badge_fg)
        self.text.configure(bg=bg, fg=fg)

    def disable(self):
        self.enabled = False
        for w in (self, self.badge, self.text):
            w.configure(cursor="arrow")
