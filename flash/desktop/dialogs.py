"""Pop-up windows: test setup, rename, settings, offline/AI choice, browse and progress."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from ..core import ai
from ..core.quiz import MODES
from . import theme
from .i18n import LANGUAGES, set_language, t
from .theme import P
from .widgets import APP_NAME, PAD, OptionRow, Toggle, card, label, style_text

if TYPE_CHECKING:
    from .app import App


class _Modal(tk.Toplevel):
    def __init__(self, app: App, title: str, heading: str | None = None):
        super().__init__(app)
        self.app = app
        self.result = None
        self.withdraw()
        self.title(title)
        self.configure(bg=P.surface)
        self.transient(app)
        self.resizable(False, False)
        self.bind("<Escape>", lambda e: self.destroy())
        self.frame = tk.Frame(self, bg=P.surface)
        self.frame.pack(fill="both", expand=True, padx=24, pady=20)
        if heading:
            label(self.frame, heading, font=app.fonts["h2"]).pack(fill="x", pady=(0, 14))

    def section(self, text: str, top: int = 14):
        label(self.frame, text.upper(), font=self.app.fonts["small"], fg=P.muted).pack(fill="x", pady=(top, 4))

    def footer(self, ok_text: str, on_ok, cancel: bool = True):
        bar = tk.Frame(self.frame, bg=P.surface)
        bar.pack(fill="x", pady=(20, 0))
        ttk.Button(bar, text=ok_text, style="Accent.TButton", command=on_ok).pack(side="right")
        if cancel:
            ttk.Button(bar, text=t("cancel"), command=self.destroy).pack(side="right", padx=8)
        self.bind("<Return>", lambda e: on_ok())

    def run(self):
        self.update_idletasks()
        x = self.app.winfo_rootx() + (self.app.winfo_width() - self.winfo_reqwidth()) // 2
        y = self.app.winfo_rooty() + (self.app.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.deiconify()
        theme.style_titlebar(self)
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass
        self.focus_set()
        self.wait_window()


class SetupDialog(_Modal):
    """Test options before a test starts: mode, number of questions, range, shuffling, feedback.

    After it closes, ``result`` is a dict of the choices, or None if cancelled.
    """

    def __init__(self, app: App, deck):
        super().__init__(app, t("setup_title"), heading=deck.name)
        s = app.service.settings
        n = len(deck.questions)
        self.n = n

        self.section(t("mode"), top=0)
        self.mode = tk.StringVar(value="smart")
        for m in MODES:
            Toggle(self.frame, t(f"mode_{m}"), self.mode, value=m).pack(anchor="w", pady=3)

        self.section(t("count"))
        row = tk.Frame(self.frame, bg=P.surface)
        row.pack(fill="x")
        self.count = tk.IntVar(value=min(int(s.get("default_count", 30)), n))
        ttk.Spinbox(row, from_=1, to=n, textvariable=self.count, width=6).pack(side="left")
        for value in (10, 30, 50):
            if value < n:
                ttk.Button(
                    row, text=str(value), style="Chip.TButton", width=0, command=lambda v=value: self.count.set(v)
                ).pack(side="left", padx=(8, 0))
        ttk.Button(row, text=t("all_n", n=n), style="Chip.TButton", width=0, command=lambda: self.count.set(n)).pack(
            side="left", padx=(8, 0)
        )

        self.section(t("range"))
        rng = tk.Frame(self.frame, bg=P.surface)
        rng.pack(fill="x")
        self.start = tk.IntVar(value=1)
        self.end = tk.IntVar(value=n)
        label(rng, t("range_from"), fg=P.muted).pack(side="left")
        ttk.Spinbox(rng, from_=1, to=n, textvariable=self.start, width=6).pack(side="left", padx=6)
        label(rng, t("range_to"), fg=P.muted).pack(side="left")
        ttk.Spinbox(rng, from_=1, to=n, textvariable=self.end, width=6).pack(side="left", padx=6)

        self.section(t("options_section"))
        self.shuffle = tk.BooleanVar(value=s.get("shuffle_options", True))
        self.feedback = tk.BooleanVar(value=s.get("instant_feedback", True))
        Toggle(self.frame, t("shuffle_options"), self.shuffle).pack(anchor="w", pady=3)
        Toggle(self.frame, t("instant_feedback"), self.feedback).pack(anchor="w", pady=3)

        self.footer("▶  " + t("start"), self.ok)
        self.run()

    def ok(self):
        """Check the numbers, keep the choices in ``result``, remember shuffle/feedback, and close."""

        def val(var, default):
            try:
                return int(var.get())
            except (tk.TclError, ValueError):
                return default

        start = min(max(val(self.start, 1), 1), self.n)
        end = min(max(val(self.end, self.n), start), self.n)
        self.result = {
            "mode": self.mode.get(),
            "count": max(val(self.count, 30), 1),
            "start": start,
            "end": end,
            "shuffle": self.shuffle.get(),
            "feedback": self.feedback.get(),
        }
        self.app.service.update_settings(
            shuffle_options=self.result["shuffle"], instant_feedback=self.result["feedback"]
        )
        self.destroy()


class RenameDialog(_Modal):
    """Ask for a deck's new name; ``result`` is the name, or None if cancelled."""

    def __init__(self, app: App, current: str):
        super().__init__(app, t("rename"), heading=t("rename"))
        self.entry = ttk.Entry(self.frame, width=44)
        self.entry.insert(0, current)
        self.entry.pack(fill="x")
        self.entry.select_range(0, "end")
        self.footer(t("save"), self.ok)
        self.after(50, self.entry.focus_set)
        self.run()

    def ok(self):
        """Accept the name if it isn't empty and close."""
        name = self.entry.get().strip()
        if name:
            self.result = name
            self.destroy()


class GenerateChoiceDialog(_Modal):
    """For a file that isn't a test collection: make questions offline or with AI.

    ``result`` is ``"offline"``, ``"ai"``, or None if cancelled.
    """

    def __init__(self, app: App):
        super().__init__(app, t("not_bank_title"), heading=t("not_bank_title"))
        label(self.frame, t("not_bank_body"), fg=P.muted, wraplength=460).pack(fill="x", pady=(0, 12))
        for key, desc, value in (("gen_offline", "gen_offline_desc", "offline"), ("gen_ai", "gen_ai_desc", "ai")):
            opt = OptionRow(
                self.frame, app, 1 if value == "offline" else 2, f"{t(key)}\n{t(desc)}", lambda v=value: self.pick(v)
            )
            opt.text.configure(wraplength=420)
            opt.pack(fill="x", pady=4)
        bar = tk.Frame(self.frame, bg=P.surface)
        bar.pack(fill="x", pady=(14, 0))
        ttk.Button(bar, text=t("cancel"), command=self.destroy).pack(side="right")
        self.bind("1", lambda e: self.pick("offline"))
        self.bind("2", lambda e: self.pick("ai"))
        self.run()

    def pick(self, value):
        """Choose ``"offline"`` or ``"ai"`` and close."""
        self.result = value
        self.destroy()


class SettingsDialog(_Modal):
    """Settings: language, theme, font size, test defaults, and the AI key and model."""

    def __init__(self, app: App):
        super().__init__(app, t("settings"), heading=t("settings"))
        s = app.service.settings
        grid = tk.Frame(self.frame, bg=P.surface)
        grid.pack(fill="x")
        grid.columnconfigure(1, weight=1)

        def row(r, key, widget):
            label(grid, t(key)).grid(row=r, column=0, sticky="w", pady=6, padx=(0, 16))
            widget.grid(row=r, column=1, sticky="w", pady=6)

        self.themes = {m: t(f"theme_{m}") for m in theme.THEMES}
        self.theme = ttk.Combobox(grid, values=list(self.themes.values()), state="readonly", width=22)
        self.theme.set(self.themes.get(s.get("theme", "system"), self.themes["system"]))
        row(0, "theme", self.theme)

        self.lang = ttk.Combobox(grid, values=list(LANGUAGES.values()), state="readonly", width=22)
        self.lang.set(LANGUAGES[s["lang"]])
        row(1, "language", self.lang)

        self.font_size = tk.IntVar(value=s.get("font_size", 12))
        row(2, "font_size", ttk.Spinbox(grid, from_=9, to=24, textvariable=self.font_size, width=6))

        self.count = tk.IntVar(value=s.get("default_count", 30))
        row(3, "default_count", ttk.Spinbox(grid, from_=5, to=500, textvariable=self.count, width=6))

        label(grid, t("ai_section").upper(), font=app.fonts["small"], fg=P.muted).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(20, 4)
        )
        self.key = ttk.Entry(grid, width=36, show="•")
        self.key.insert(0, s.get("api_key", ""))
        row(5, "api_key", self.key)
        self.model = ttk.Combobox(grid, values=ai.MODELS, width=22)
        self.model.set(s.get("ai_model", ai.DEFAULT_MODEL))
        row(6, "ai_model", self.model)
        label(self.frame, t("ai_note"), font=app.fonts["small"], fg=P.muted, wraplength=480).pack(fill="x", pady=(8, 0))

        self.footer(t("save"), self.save)
        self.run()

    def save(self):
        """Save the settings, apply them to the window, and close."""
        s = self.app.service.settings
        try:
            size = min(max(int(self.font_size.get()), 9), 24)
        except (tk.TclError, ValueError):
            size = s["font_size"]
        try:
            count = max(int(self.count.get()), 1)
        except (tk.TclError, ValueError):
            count = s["default_count"]
        mode = next(k for k, v in self.themes.items() if v == self.theme.get())
        lang = next(k for k, v in LANGUAGES.items() if v == self.lang.get())
        self.app.service.update_settings(
            font_size=size,
            default_count=count,
            api_key=self.key.get().strip(),
            theme=mode,
            ai_model=self.model.get().strip() or ai.DEFAULT_MODEL,
            lang=lang,
        )
        self.destroy()
        set_language(lang)
        self.app.apply_font_size(size)  # also re-applies the theme and rebuilds the views


class BrowseWindow(tk.Toplevel):
    """A window listing every question of a deck with its answer, with a search box."""

    def __init__(self, app: App, deck):
        super().__init__(app)
        self.app = app
        self.deck = deck
        self.title(t("browse_title", name=deck.name))
        self.geometry("860x640")
        self.configure(bg=P.bg)
        top = tk.Frame(self, bg=P.bg)
        top.pack(fill="x", padx=PAD, pady=(16, 10))
        label(top, "🔍", fg=P.muted).pack(side="left")
        self.query = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.query)
        entry.pack(side="left", fill="x", expand=True, padx=8)
        entry.focus_set()
        self.found = label(top, fg=P.muted, font=app.fonts["small"])
        self.found.pack(side="right")
        self.query.trace_add("write", lambda *a: self.after_idle(self.fill))

        frame = card(self)
        frame.pack(fill="both", expand=True, padx=PAD, pady=(0, PAD))
        self.text = tk.Text(frame, wrap="word")
        style_text(self.text, app.fonts["base"])
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.text.pack(fill="both", expand=True)
        self.text.tag_configure("q", font=app.fonts["bold"], spacing1=14, spacing3=4)
        self.text.tag_configure("ok", foreground=P.ok, lmargin1=18, lmargin2=36)
        self.text.tag_configure("opt", foreground=P.muted, lmargin1=18, lmargin2=36)
        self.text.tag_configure("hit", background=P.selection)
        self.fill()
        theme.style_titlebar(self)

    def fill(self):
        """Show the questions that match the search text (all of them when it is empty)."""
        q = self.query.get().strip().lower()
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        shown = 0
        for i, item in enumerate(self.deck.questions, 1):
            if q and q not in item.text.lower() and not any(q in o.lower() for o in item.options):
                continue
            shown += 1
            self.text.insert("end", f"{i}. {item.text}\n", "q")
            for j, o in enumerate(item.options):
                if j == item.answer:
                    self.text.insert("end", f"✔  {o}\n", "ok")
                else:
                    self.text.insert("end", f"•  {o}\n", "opt")
        if q:
            start = "1.0"
            while True:
                pos = self.text.search(q, start, stopindex="end", nocase=True)
                if not pos:
                    break
                end = f"{pos}+{len(q)}c"
                self.text.tag_add("hit", pos, end)
                start = end
        self.found.configure(text=t("found_n", n=shown))
        self.text.configure(state="disabled")


class TaskDialog(_Modal):
    """Progress window for background work; keeps the UI responsive."""

    def __init__(self, app: App, title: str, func, on_done, cancellable: bool):
        super().__init__(app, APP_NAME, heading=title)
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self.unbind("<Escape>")
        self.on_done = on_done
        self.q: queue.Queue = queue.Queue()
        self._cancel = threading.Event()
        self.status = label(self.frame, fg=P.muted, width=44)
        self.status.pack(fill="x", pady=(0, 8))
        self.bar = ttk.Progressbar(self.frame, style="Accent.Horizontal.TProgressbar", length=380, mode="indeterminate")
        self.bar.pack(fill="x")
        self.bar.start(12)
        if cancellable:
            ttk.Button(self.frame, text=t("cancel"), command=self._cancel.set).pack(anchor="e", pady=(14, 0))

        def progress(text, fraction=None):
            self.q.put(("progress", text, fraction))

        def worker():
            try:
                self.q.put(("done", func(progress, self._cancel.is_set), None))
            except Exception as e:  # reported to the user in the UI thread
                self.q.put(("error", e, None))

        threading.Thread(target=worker, daemon=True).start()
        self.after(50, self._poll)
        self.run()

    def _poll(self):
        try:
            while True:
                kind, a, b = self.q.get_nowait()
                if kind == "progress":
                    self.status.configure(text=a)
                    if b is not None:
                        if str(self.bar.cget("mode")) != "determinate":
                            self.bar.stop()
                            self.bar.configure(mode="determinate", maximum=1.0)
                        self.bar.configure(value=b)
                else:
                    self.grab_release()
                    self.destroy()
                    self.on_done(a, None) if kind == "done" else self.on_done(None, a)
                    return
        except queue.Empty:
            pass
        self.after(80, self._poll)
