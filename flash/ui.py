"""Tkinter user interface.

Tkinter ships with Python, starts fast and needs very little memory, so FlasH
runs on old and low-end Windows laptops. Colours come from ``theme.P`` and every
view is rebuilt when the theme changes.
"""

from __future__ import annotations

import os
import queue
import random
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

from . import ai, generator, theme
from .extract import SUPPORTED_EXTENSIONS, ExtractionError
from .i18n import LANGUAGES, set_language, t
from .importer import analyse_file
from .quiz import MODES, Session, select_questions
from .storage import Store
from .theme import P

APP_NAME = "FlasH"
PAD = 20


def _enable_dpi_awareness() -> None:
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


# ------------------------------------------------------------------ helpers
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


# ====================================================================
class App(tk.Tk):
    def __init__(self, store: Store | None = None):
        _enable_dpi_awareness()
        super().__init__()
        self.store = store or Store()
        set_language(self.store.settings["lang"])
        self.title(APP_NAME)
        self.geometry("1000x720")
        self.minsize(680, 520)
        self._init_fonts()
        theme.apply(self, self.store.settings.get("theme", "system"), self.fonts)
        self._set_icon()

        self.header = tk.Frame(self)
        self.header.pack(fill="x")
        self.body = tk.Frame(self)
        self.body.pack(fill="both", expand=True)
        self.view: tk.Widget | None = None
        self._factory = None
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind_all("<MouseWheel>", self._on_wheel)
        self._build_header()
        self.show_library()

    # ----------------------------------------------------------- setup
    def _init_fonts(self):
        size = int(self.store.settings.get("font_size", 12))
        families = tkfont.families()
        family = next((f for f in ("Segoe UI Variable Text", "Segoe UI") if f in families), "TkDefaultFont")
        self.fonts = {name: tkfont.Font(family=family) for name in self._FONT_SPEC}
        self.apply_font_size(size, restyle=False)
        self.option_add("*Font", self.fonts["base"])

    _FONT_SPEC = {
        "small": (-2, "normal"),
        "base": (0, "normal"),
        "bold": (0, "bold"),
        "h2": (3, "bold"),
        "question": (3, "bold"),
        "title": (8, "bold"),
        "huge": (16, "bold"),
        "icon": (26, "normal"),
    }

    def apply_font_size(self, size: int, restyle: bool = True):
        for name, (delta, weight) in self._FONT_SPEC.items():
            self.fonts[name].configure(size=max(size + delta, 8), weight=weight)
        if restyle:
            self.refresh_theme()

    def _set_icon(self):
        here = os.path.dirname(os.path.abspath(__file__))
        icon = os.path.join(here, "assets", "flash.ico")
        if os.path.exists(icon):
            try:
                self.iconbitmap(icon)
            except tk.TclError:
                pass

    def _on_wheel(self, event):
        w = self.winfo_containing(event.x_root, event.y_root)
        while w is not None:
            if getattr(w, "_flash_scroll", False):
                w.yview_scroll(int(-event.delta / 120), "units")
                return
            if isinstance(w, (tk.Text, tk.Listbox)):
                return  # these scroll on their own
            w = w.master

    # ----------------------------------------------------------- theme / language
    def refresh_theme(self):
        theme.apply(self, self.store.settings.get("theme", "system"), self.fonts)
        self._build_header()
        self._rebuild()

    def set_theme(self, mode: str):
        self.store.settings["theme"] = mode
        self.store.save_settings()
        self.refresh_theme()

    def toggle_theme(self):
        self.set_theme("light" if P.name == "dark" else "dark")

    def change_language(self, code: str):
        self.store.settings["lang"] = code
        self.store.save_settings()
        set_language(code)
        self._build_header()
        self._rebuild()

    def _build_header(self):
        for w in self.header.winfo_children():
            w.destroy()
        self.header.configure(bg=P.surface, highlightthickness=1, highlightbackground=P.border)
        self.body.configure(bg=P.bg)
        inner = tk.Frame(self.header, bg=P.surface)
        inner.pack(fill="x", padx=PAD, pady=10)
        logo = tk.Frame(inner, bg=P.surface, cursor="hand2")
        logo.pack(side="left")
        tk.Label(logo, text="⚡", font=self.fonts["title"], fg=P.accent, bg=P.surface).pack(side="left")
        tk.Label(logo, text="FlasH", font=self.fonts["title"], fg=P.text, bg=P.surface).pack(side="left")
        for w in (logo, *logo.winfo_children()):
            w.bind("<Button-1>", lambda e: self.show_library())
        label(inner, t("app_tagline"), font=self.fonts["small"], fg=P.muted).pack(
            side="left", padx=(12, 0), pady=(6, 0)
        )

        ttk.Button(inner, text="⚙  " + t("settings"), style="CardGhost.TButton", command=self.open_settings).pack(
            side="right"
        )
        icon = "☼" if P.name == "dark" else "☾"
        ttk.Button(
            inner,
            text=f"{icon}  " + (t("theme_light") if P.name == "dark" else t("theme_dark")),
            style="CardGhost.TButton",
            command=self.toggle_theme,
        ).pack(side="right", padx=4)
        lang = ttk.Combobox(inner, values=list(LANGUAGES.values()), state="readonly", width=11)
        lang.set(LANGUAGES[self.store.settings["lang"]])
        lang.pack(side="right", padx=8)
        lang.bind(
            "<<ComboboxSelected>>",
            lambda e: self.change_language(next(k for k, v in LANGUAGES.items() if v == lang.get())),
        )

    # ----------------------------------------------------------- views
    def on_close(self):
        self.store.save_progress()
        self.destroy()

    def _show(self, factory):
        self.store.save_progress()
        if self.view is not None:
            self.view.destroy()
        self._factory = factory
        self.view = factory()
        self.view.pack(fill="both", expand=True)

    def _rebuild(self):
        if self._factory:
            self._show(self._factory)

    def show_library(self):
        self._show(lambda: LibraryView(self.body, self))

    def start_session(self, session: Session, instant_feedback: bool):
        self._show(lambda: QuizView(self.body, self, session, instant_feedback))

    def show_results(self, session: Session):
        self._show(lambda: ResultsView(self.body, self, session))

    # ----------------------------------------------------------- dialogs
    def open_settings(self):
        SettingsDialog(self)

    def run_task(self, title: str, func, on_done, cancellable: bool = False):
        """Run ``func(progress, cancelled)`` in a thread with a progress window."""
        return TaskDialog(self, title, func, on_done, cancellable)

    # ----------------------------------------------------------- import
    def import_file(self):
        exts = " ".join(f"*{e}" for e in SUPPORTED_EXTENSIONS)
        path = filedialog.askopenfilename(
            parent=self,
            title=t("import"),
            filetypes=[(t("file_types"), exts), (t("all_files"), "*.*")],
        )
        if not path:
            return

        def work(progress, cancelled):
            return analyse_file(path, lambda d, n: progress(t("page_progress", done=d, total=n), d / n))

        self.run_task(t("importing"), work, self._after_analyse)

    def _after_analyse(self, result, error):
        if error:
            msg = str(error) if isinstance(error, ExtractionError) else repr(error)
            messagebox.showerror(APP_NAME, t("import_failed", error=msg), parent=self)
            return
        if not result.has_text:
            messagebox.showwarning(APP_NAME, t("no_text"), parent=self)
            return
        if result.is_bank:
            self._save_deck(result.name, result.source, "bank", result.questions)
            return
        choice = GenerateChoiceDialog(self).result
        if choice == "offline":
            self.run_task(
                t("generating"),
                lambda p, c: generator.generate_questions(result.lines),
                lambda qs, err: self._finish_generated(result, "generated", qs, err),
            )
        elif choice == "ai":
            self._generate_ai(result)

    def _generate_ai(self, result):
        if not ai.is_available():
            messagebox.showerror(APP_NAME, t("ai_unavailable"), parent=self)
            return
        key = self.store.settings.get("api_key") or os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            messagebox.showinfo(APP_NAME, t("ai_no_key"), parent=self)
            self.open_settings()
            return
        model = self.store.settings.get("ai_model", ai.DEFAULT_MODEL)

        def work(progress, cancelled):
            return ai.generate_questions(
                result.lines,
                key,
                model,
                progress=lambda d, n: progress(t("ai_progress", done=d, total=n), d / n),
                cancelled=cancelled,
            )

        self.run_task(
            t("generating"),
            work,
            lambda qs, err: self._finish_generated(result, "ai", qs, err),
            cancellable=True,
        )

    def _finish_generated(self, result, kind, questions, error):
        if error:
            if isinstance(error, ai.AIError) and str(error) in ("auth", "rate_limit", "network"):
                msg = t(f"ai_err_{error}")
            else:
                msg = str(error)
            messagebox.showerror(APP_NAME, msg, parent=self)
            return
        self._save_deck(result.name, result.source, kind, questions)

    def _save_deck(self, name, source, kind, questions):
        if not questions:
            messagebox.showwarning(APP_NAME, t("no_questions"), parent=self)
            return
        self.store.create_deck(name, source, kind, questions)
        messagebox.showinfo(APP_NAME, t("import_done", n=len(questions)), parent=self)
        self.show_library()


# ====================================================================
class LibraryView(tk.Frame):
    def __init__(self, master, app: App):
        super().__init__(master, bg=P.bg)
        self.app = app
        f = app.fonts
        decks = app.store.list_decks()

        top = tk.Frame(self, bg=P.bg)
        top.pack(fill="x", padx=PAD, pady=(PAD, 8))
        titles = tk.Frame(top, bg=P.bg)
        titles.pack(side="left")
        label(titles, t("decks"), font=f["title"]).pack(anchor="w")
        if decks:
            label(titles, t("decks_count", n=len(decks)), font=f["small"], fg=P.muted).pack(anchor="w")
        ttk.Button(top, text="＋  " + t("import"), style="Accent.TButton", command=app.import_file).pack(
            side="right", anchor="s"
        )

        if not decks:
            self._empty_state()
            return

        scroll = ScrollFrame(self, P.bg)
        scroll.pack(fill="both", expand=True, padx=(PAD, 6), pady=(4, PAD))
        for deck in decks:
            DeckCard(scroll.inner, app, deck).pack(fill="x", pady=6, padx=(0, 14))

    def _empty_state(self):
        f = self.app.fonts
        box = card(self)
        box.pack(fill="both", expand=True, padx=PAD, pady=(8, PAD))
        center = tk.Frame(box, bg=P.surface)
        center.place(relx=0.5, rely=0.45, anchor="center")
        tk.Label(center, text="📚", font=f["icon"], bg=P.surface, fg=P.accent).pack()
        label(center, t("empty_title"), font=f["h2"], anchor="center", justify="center").pack(pady=(8, 4))
        label(center, t("empty_library"), fg=P.muted, wraplength=460, anchor="center", justify="center").pack()
        ttk.Button(center, text="＋  " + t("import"), style="Accent.TButton", command=self.app.import_file).pack(
            pady=(18, 0)
        )


class DeckCard(tk.Frame):
    def __init__(self, master, app: App, deck):
        super().__init__(
            master, bg=P.surface, highlightthickness=1, highlightbackground=P.border, highlightcolor=P.border
        )
        self.app = app
        self.deck = deck
        f = app.fonts
        s = app.store.summary(deck)
        pct = round(100 * s["learned"] / s["total"]) if s["total"] else 0

        body = tk.Frame(self, bg=P.surface)
        body.pack(side="left", fill="both", expand=True, padx=18, pady=14)
        row = tk.Frame(body, bg=P.surface)
        row.pack(fill="x")
        label(row, deck.name, font=f["h2"]).pack(side="left")
        badge(row, t(f"kind_{deck.kind}"), font=f["small"]).pack(side="left", padx=10)

        stats = t("stats_line", total=s["total"], seen=s["seen"], learned=s["learned"])
        if s["weak"]:
            stats += "  ·  " + t("stats_weak", n=s["weak"])
        label(body, stats, font=f["small"], fg=P.muted).pack(fill="x", pady=(4, 8))

        prog = tk.Frame(body, bg=P.surface)
        prog.pack(fill="x")
        Bar(prog, pct / 100, color=P.ok if pct >= 80 else P.accent).pack(side="left", fill="x", expand=True)
        label(prog, t("learned_pct", pct=pct), font=f["small"], fg=P.muted).pack(side="left", padx=(10, 0))

        actions = tk.Frame(self, bg=P.surface)
        actions.pack(side="right", padx=(0, 16))
        ttk.Button(actions, text="▶  " + t("start"), style="Accent.TButton", command=self.start).pack(side="left")
        more = ttk.Button(actions, text="•••", style="CardGhost.TButton", width=0, command=lambda: self.menu(more))
        more.pack(side="left", padx=(6, 0))

        hover_targets = [self, body, row, prog, actions] + list(body.winfo_children()) + list(row.winfo_children())
        for w in hover_targets:
            w.bind("<Enter>", lambda e: self.configure(highlightbackground=P.accent), add="+")
            w.bind("<Leave>", lambda e: self.configure(highlightbackground=P.border), add="+")
            if not isinstance(w, ttk.Widget):
                w.bind("<Double-Button-1>", lambda e: self.start())

    def menu(self, anchor):
        m = tk.Menu(
            self,
            tearoff=0,
            bg=P.surface,
            fg=P.text,
            activebackground=P.selection,
            activeforeground=P.text,
            bd=0,
            font=self.app.fonts["base"],
        )
        m.add_command(label="🔍  " + t("browse"), command=lambda: BrowseWindow(self.app, self.deck))
        m.add_command(label="✎  " + t("rename"), command=self.rename)
        m.add_command(label="↺  " + t("reset"), command=self.reset)
        m.add_separator()
        m.add_command(label="🗑  " + t("delete"), command=self.delete, foreground=P.bad)
        m.tk_popup(anchor.winfo_rootx(), anchor.winfo_rooty() + anchor.winfo_height())

    def start(self):
        deck = self.deck
        params = SetupDialog(self.app, deck).result
        if not params:
            return
        store = self.app.store
        questions = select_questions(
            deck,
            store.stats(deck.id),
            mode=params["mode"],
            count=params["count"],
            start=params["start"],
            end=params["end"],
        )
        if not questions:
            messagebox.showinfo(APP_NAME, t("nothing_selected"), parent=self.app)
            return
        session = Session.create(deck.id, questions, shuffle_options=params["shuffle"])
        self.app.start_session(session, params["feedback"])

    def rename(self):
        name = RenameDialog(self.app, self.deck.name).result
        if name:
            self.deck.name = name
            self.app.store.save_deck(self.deck)
            self.app.show_library()

    def reset(self):
        if messagebox.askyesno(APP_NAME, t("confirm_reset", name=self.deck.name), parent=self.app):
            self.app.store.reset_progress(self.deck.id)
            self.app.show_library()

    def delete(self):
        if messagebox.askyesno(APP_NAME, t("confirm_delete", name=self.deck.name), parent=self.app):
            self.app.store.delete_deck(self.deck.id)
            self.app.show_library()


# ====================================================================
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


class QuizView(tk.Frame):
    def __init__(self, master, app: App, session: Session, instant_feedback: bool):
        super().__init__(master, bg=P.bg)
        self.app = app
        self.session = session
        self.instant = instant_feedback
        self.rows: list[OptionRow] = []
        f = app.fonts

        top = tk.Frame(self, bg=P.bg)
        top.pack(fill="x", padx=PAD, pady=(14, 8))
        ttk.Button(top, text="✕  " + t("finish"), style="Ghost.TButton", command=self.quit_test).pack(side="left")
        self.score_ok = label(top, font=f["bold"], fg=P.ok)
        self.score_bad = label(top, font=f["bold"], fg=P.bad)
        self.score_bad.pack(side="right")
        self.score_ok.pack(side="right", padx=(0, 14))
        self.counter = label(top, font=f["bold"], fg=P.muted, anchor="center")
        self.counter.pack(side="left", fill="x", expand=True)

        self.progress = Bar(self)
        self.progress.pack(fill="x", padx=PAD)

        bottom = tk.Frame(self, bg=P.bg)
        bottom.pack(side="bottom", fill="x", padx=PAD, pady=(0, 16))
        self.hint = label(bottom, font=f["small"], fg=P.muted)
        self.hint.pack(side="left")
        self.next_btn = ttk.Button(bottom, command=self.go_next)
        self.next_btn.pack(side="right")

        holder = card(self)
        holder.pack(fill="both", expand=True, padx=PAD, pady=12)
        self.scroll = ScrollFrame(holder, P.surface)
        self.scroll.pack(fill="both", expand=True, padx=2, pady=2)
        content = self.scroll.inner
        self.q_lbl = label(content, font=f["question"])
        self.q_lbl.pack(fill="x", padx=24, pady=(18, 12))
        self.opts = tk.Frame(content, bg=P.surface)
        self.opts.pack(fill="x", padx=24)
        self.banner = tk.Frame(content, bg=P.surface)
        self.banner.pack(fill="x", padx=24, pady=(14, 20))
        self.feedback = label(self.banner, font=f["bold"])
        self.feedback.pack(fill="x", padx=14, pady=(10, 2))
        self.expl = label(self.banner, font=f["small"])
        self.expl.pack(fill="x", padx=14, pady=(0, 10))

        self.scroll.canvas.bind("<Configure>", self._rewrap, add="+")
        self.app.bind("<Key>", self._on_key)
        self.render()

    def destroy(self):
        try:
            self.app.unbind("<Key>")
        except tk.TclError:
            pass
        super().destroy()

    def _rewrap(self, event=None):
        width = max(self.scroll.canvas.winfo_width() - 60, 240)
        self.q_lbl.configure(wraplength=width)
        self.feedback.configure(wraplength=width - 30)
        self.expl.configure(wraplength=width - 30)
        for r in self.rows:
            r.text.configure(wraplength=width - 90)

    def _update_header(self):
        s = self.session
        n = len(s.items)
        wrong = len(s.answered) - s.score
        self.counter.configure(text=t("question_n", i=min(s.index + 1, n), n=n))
        self.score_ok.configure(text=f"✔ {s.score}")
        self.score_bad.configure(text=f"✘ {wrong}")
        done = s.index + (1 if s.current and s.current.chosen is not None else 0)
        self.progress.set(done / max(n, 1))
        if s.current:
            self.hint.configure(text=t("keys_hint", n=len(s.current.options)))

    def render(self):
        item = self.session.current
        if item is None:
            self.app.show_results(self.session)
            return
        self.q_lbl.configure(text=item.question.text)
        for r in self.rows:
            r.destroy()
        self.rows = []
        for pos, text in enumerate(item.options):
            row = OptionRow(self.opts, self.app, pos + 1, text, lambda p=pos: self.choose(p))
            row.pack(fill="x", pady=4)
            self.rows.append(row)
        self.scroll.canvas.yview_moveto(0)
        if item.chosen is not None:  # re-rendered after a theme/language change
            self._show_feedback()
        else:
            self._hide_feedback()
            self.next_btn.configure(text=t("skip"), style="TButton")
        self._update_header()
        self._rewrap()

    def _hide_feedback(self):
        self.banner.configure(bg=P.surface)
        self.feedback.configure(text="", bg=P.surface)
        self.expl.configure(text="", bg=P.surface)

    def choose(self, pos: int):
        item = self.session.current
        if item is None or item.chosen is not None:
            return
        correct = self.session.answer(pos)
        self.app.store.record(self.session.deck_id, item.question.id, correct)
        if self.instant:
            self._show_feedback()
            self._update_header()
        else:
            self.go_next()

    def _show_feedback(self):
        item = self.session.current
        for i, row in enumerate(self.rows):
            row.disable()
            if i == item.correct_pos:
                row.set_state("correct")
            elif i == item.chosen:
                row.set_state("wrong")
            else:
                row.set_state("dim")
        bg, fg = (P.ok_bg, P.ok) if item.is_correct else (P.bad_bg, P.bad)
        text = "✔  " + t("correct") if item.is_correct else "✘  " + t("wrong", answer=item.options[item.correct_pos])
        self.banner.configure(bg=bg)
        self.feedback.configure(text=text, bg=bg, fg=fg)
        expl = item.question.explanation
        self.expl.configure(text=t("explanation", text=expl) if expl else "", bg=bg, fg=P.text)
        if expl:
            self.expl.pack(fill="x", padx=14, pady=(0, 10))
            self.feedback.pack_configure(pady=(10, 2))
        else:
            self.expl.pack_forget()
            self.feedback.pack_configure(pady=10)
        last = self.session.index == len(self.session.items) - 1
        self.next_btn.configure(text=t("show_results") if last else t("next"), style="Accent.TButton")
        self.after(30, lambda: self.winfo_exists() and self.scroll.show_widget(self.banner))

    def go_next(self):
        self.session.next()
        self.render()

    def quit_test(self):
        if not self.session.answered:
            self.app.show_library()
        elif messagebox.askyesno(APP_NAME, t("confirm_quit"), parent=self.app):
            self.app.show_results(self.session)

    def _on_key(self, event):
        if not self.winfo_exists() or isinstance(event.widget, (tk.Entry, ttk.Entry)):
            return
        if event.keysym in ("Return", "KP_Enter", "space", "Right"):
            self.go_next()
            return
        ch = event.char
        if ch and ch.isdigit():
            pos = int(ch) - 1
            if 0 <= pos < len(self.rows):
                self.choose(pos)


# ====================================================================
class ResultsView(tk.Frame):
    def __init__(self, master, app: App, session: Session):
        super().__init__(master, bg=P.bg)
        self.app = app
        self.session = session
        f = app.fonts
        answered = len(session.answered)
        right = session.score
        wrong = answered - right
        skipped = sum(1 for i in session.items[: session.index] if i.chosen is None)
        pct = round(100 * right / answered) if answered else 0
        grade = "grade_5" if pct >= 90 else "grade_4" if pct >= 75 else "grade_3" if pct >= 60 else "grade_2"
        color = P.ok if pct >= 75 else (P.accent if pct >= 60 else P.bad)

        bar = tk.Frame(self, bg=P.bg)
        bar.pack(side="bottom", fill="x", padx=PAD, pady=(0, 16))
        ttk.Button(bar, text="⌂  " + t("home"), style="Ghost.TButton", command=app.show_library).pack(side="left")
        if session.mistakes:
            ttk.Button(bar, text="↻  " + t("retry_mistakes"), style="Accent.TButton", command=self.retry).pack(
                side="right"
            )

        head = card(self)
        head.pack(fill="x", padx=PAD, pady=(PAD, 10))
        ring = tk.Canvas(head, width=150, height=150, bg=P.surface, highlightthickness=0)
        ring.pack(side="left", padx=24, pady=18)
        ring.create_oval(14, 14, 136, 136, outline=P.track, width=12)
        if pct:
            ring.create_arc(
                14, 14, 136, 136, start=90, extent=-3.6 * min(pct, 99.99), style="arc", outline=color, width=12
            )
        ring.create_text(75, 75, text=f"{pct}%", fill=P.text, font=f["title"])

        info = tk.Frame(head, bg=P.surface)
        info.pack(side="left", fill="x", expand=True, pady=18)
        label(info, t(grade), font=f["title"], fg=color).pack(anchor="w")
        label(info, t("result_line", right=right, total=answered), fg=P.muted).pack(anchor="w", pady=(2, 12))
        chips = tk.Frame(info, bg=P.surface)
        chips.pack(anchor="w")
        badge(chips, f"✔  {t('chip_right', n=right)}", fg=P.ok, bg=P.ok_bg, font=f["bold"]).pack(side="left")
        badge(chips, f"✘  {t('chip_wrong', n=wrong)}", fg=P.bad, bg=P.bad_bg, font=f["bold"]).pack(side="left", padx=8)
        if skipped:
            badge(chips, f"⤼  {t('chip_skipped', n=skipped)}", fg=P.muted, bg=P.surface2, font=f["bold"]).pack(
                side="left"
            )

        body = card(self)
        body.pack(fill="both", expand=True, padx=PAD, pady=(0, 12))
        mistakes = session.mistakes
        label(
            body, t("mistakes_title", n=len(mistakes)) if mistakes else t("no_mistakes"), font=f["h2"], bg=P.surface
        ).pack(fill="x", padx=18, pady=(14, 0))
        if not mistakes:
            return
        text = tk.Text(body, wrap="word", cursor="arrow")
        style_text(text, f["base"])
        sb = ttk.Scrollbar(body, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)
        text.tag_configure("q", font=f["bold"], spacing1=12, spacing3=6)
        text.tag_configure("bad", foreground=P.bad, lmargin1=14, lmargin2=34)
        text.tag_configure("ok", foreground=P.ok, lmargin1=14, lmargin2=34)
        text.tag_configure("muted", foreground=P.muted, font=f["small"], lmargin1=14, lmargin2=14, spacing3=4)
        for n, item in enumerate(mistakes, 1):
            text.insert("end", f"{n}. {item.question.text}\n", "q")
            text.insert("end", "✘  " + t("your_answer", text=item.options[item.chosen]) + "\n", "bad")
            text.insert("end", "✔  " + t("right_answer", text=item.options[item.correct_pos]) + "\n", "ok")
            if item.question.explanation:
                text.insert("end", item.question.explanation + "\n", "muted")
        text.configure(state="disabled")

    def retry(self):
        questions = [i.question for i in self.session.mistakes]
        random.shuffle(questions)
        s = self.app.store.settings
        self.app.start_session(
            Session.create(self.session.deck_id, questions, s["shuffle_options"]), s["instant_feedback"]
        )


# ====================================================================
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
    def __init__(self, app: App, deck):
        super().__init__(app, t("setup_title"), heading=deck.name)
        s = app.store.settings
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
        s = self.app.store.settings
        s["shuffle_options"] = self.result["shuffle"]
        s["instant_feedback"] = self.result["feedback"]
        self.app.store.save_settings()
        self.destroy()


class RenameDialog(_Modal):
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
        name = self.entry.get().strip()
        if name:
            self.result = name
            self.destroy()


class GenerateChoiceDialog(_Modal):
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
        self.result = value
        self.destroy()


class SettingsDialog(_Modal):
    def __init__(self, app: App):
        super().__init__(app, t("settings"), heading=t("settings"))
        s = app.store.settings
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
        s = self.app.store.settings
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
        s.update(
            font_size=size,
            default_count=count,
            api_key=self.key.get().strip(),
            theme=mode,
            ai_model=self.model.get().strip() or ai.DEFAULT_MODEL,
            lang=lang,
        )
        self.app.store.save_settings()
        self.destroy()
        set_language(lang)
        self.app.apply_font_size(size)  # also re-applies the theme and rebuilds the views


class BrowseWindow(tk.Toplevel):
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


def main():
    App().mainloop()
