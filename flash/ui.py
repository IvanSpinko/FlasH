"""Tkinter user interface.

Tkinter ships with Python, starts fast and needs very little memory, so FlasH
runs on old and low-end Windows laptops.
"""
from __future__ import annotations

import os
import queue
import random
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, simpledialog, ttk

from . import ai, generator
from .extract import SUPPORTED_EXTENSIONS, ExtractionError
from .i18n import LANGUAGES, set_language, t
from .importer import analyse_file
from .quiz import MODES, Session, select_questions
from .storage import Store

APP_NAME = "FlasH"

C = {
    "bg": "#f5f6fa",
    "card": "#ffffff",
    "text": "#1f2330",
    "muted": "#6b7280",
    "accent": "#2563eb",
    "accent_dark": "#1d4ed8",
    "border": "#d6d9e0",
    "hover": "#eef2ff",
    "ok_bg": "#d1fadf",
    "ok_fg": "#05603a",
    "bad_bg": "#fee4e2",
    "bad_fg": "#912018",
}


def _enable_dpi_awareness() -> None:
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


class App(tk.Tk):
    def __init__(self, store: Store | None = None):
        _enable_dpi_awareness()
        super().__init__()
        self.store = store or Store()
        set_language(self.store.settings["lang"])
        self.title(APP_NAME)
        self.geometry("980x680")
        self.minsize(640, 480)
        self.configure(bg=C["bg"])
        self._init_fonts()
        self._init_style()
        self._set_icon()

        self.header = tk.Frame(self, bg=C["card"], highlightthickness=1, highlightbackground=C["border"])
        self.header.pack(fill="x")
        self.body = tk.Frame(self, bg=C["bg"])
        self.body.pack(fill="both", expand=True)
        self.view: tk.Widget | None = None
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._build_header()
        self.show_library()

    # ----------------------------------------------------------- setup
    def _init_fonts(self):
        size = int(self.store.settings.get("font_size", 12))
        family = "Segoe UI" if "Segoe UI" in tkfont.families() else "TkDefaultFont"
        self.fonts = {
            "base": tkfont.Font(family=family, size=size),
            "small": tkfont.Font(family=family, size=max(size - 2, 8)),
            "bold": tkfont.Font(family=family, size=size, weight="bold"),
            "question": tkfont.Font(family=family, size=size + 3, weight="bold"),
            "title": tkfont.Font(family=family, size=size + 8, weight="bold"),
            "huge": tkfont.Font(family=family, size=size + 22, weight="bold"),
        }
        self.option_add("*Font", self.fonts["base"])

    def apply_font_size(self, size: int):
        deltas = {"base": 0, "small": -2, "bold": 0, "question": 3, "title": 8, "huge": 22}
        for name, d in deltas.items():
            self.fonts[name].configure(size=max(size + d, 8))
        self._init_style()

    def _init_style(self):
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        elif "clam" in style.theme_names():
            style.theme_use("clam")
        row_h = int(self.fonts["base"].metrics("linespace") * 1.6)
        style.configure("Treeview", rowheight=row_h, font=self.fonts["base"])
        style.configure("Treeview.Heading", font=self.fonts["bold"])
        style.configure("TButton", font=self.fonts["base"], padding=(10, 4))
        style.configure("Accent.TButton", font=self.fonts["bold"], padding=(14, 6))
        style.configure("TCheckbutton", font=self.fonts["base"], background=C["card"])
        style.configure("TRadiobutton", font=self.fonts["base"], background=C["card"])
        style.configure("TLabel", font=self.fonts["base"])
        style.configure("Card.TFrame", background=C["card"])
        style.configure("Horizontal.TProgressbar", thickness=8)

    def _set_icon(self):
        here = os.path.dirname(os.path.abspath(__file__))
        icon = os.path.join(here, "assets", "flash.ico")
        if os.path.exists(icon):
            try:
                self.iconbitmap(icon)
            except tk.TclError:
                pass

    def _build_header(self):
        for w in self.header.winfo_children():
            w.destroy()
        logo = tk.Label(self.header, text="⚡ FlasH", font=self.fonts["title"], fg=C["accent"], bg=C["card"])
        logo.pack(side="left", padx=(16, 8), pady=8)
        tk.Label(self.header, text=t("app_tagline"), font=self.fonts["small"], fg=C["muted"], bg=C["card"]).pack(
            side="left", pady=8
        )
        ttk.Button(self.header, text=t("settings"), command=self.open_settings).pack(side="right", padx=12)
        lang = ttk.Combobox(self.header, values=list(LANGUAGES.values()), state="readonly", width=11)
        lang.set(LANGUAGES[self.store.settings["lang"]])
        lang.pack(side="right")
        lang.bind("<<ComboboxSelected>>", lambda e: self.change_language(
            [k for k, v in LANGUAGES.items() if v == lang.get()][0]))

    def change_language(self, code: str):
        self.store.settings["lang"] = code
        self.store.save_settings()
        set_language(code)
        self._build_header()
        if isinstance(self.view, QuizView):
            self.view.refresh_texts()
        else:
            self.show_library()

    # ----------------------------------------------------------- views
    def on_close(self):
        self.store.save_progress()
        self.destroy()

    def _show(self, view: tk.Widget):
        self.store.save_progress()
        if self.view is not None:
            self.view.destroy()
        self.view = view
        view.pack(fill="both", expand=True)

    def show_library(self):
        self._show(LibraryView(self.body, self))

    def start_session(self, session: Session, instant_feedback: bool):
        self._show(QuizView(self.body, self, session, instant_feedback))

    def show_results(self, session: Session):
        self.store.save_progress()
        self._show(ResultsView(self.body, self, session))

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
            parent=self, title=t("import"),
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
                t("importing"),
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
                result.lines, key, model,
                progress=lambda d, n: progress(t("ai_progress", done=d, total=n), d / n),
                cancelled=cancelled,
            )

        self.run_task(
            t("importing"), work,
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
        if not questions:
            messagebox.showwarning(APP_NAME, t("no_questions"), parent=self)
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
        super().__init__(master, bg=C["bg"])
        self.app = app
        self.decks = {d.id: d for d in app.store.list_decks()}

        top = tk.Frame(self, bg=C["bg"])
        top.pack(fill="x", padx=16, pady=(14, 6))
        tk.Label(top, text=t("decks"), font=self.app.fonts["title"], bg=C["bg"], fg=C["text"]).pack(side="left")
        ttk.Button(top, text="＋ " + t("import"), style="Accent.TButton", command=app.import_file).pack(side="right")

        card = tk.Frame(self, bg=C["card"], highlightthickness=1, highlightbackground=C["border"])
        card.pack(fill="both", expand=True, padx=16, pady=6)

        if not self.decks:
            tk.Label(
                card, text=t("empty_library"), bg=C["card"], fg=C["muted"], wraplength=520, justify="center",
            ).pack(expand=True, padx=24, pady=40)
            return

        cols = ("questions", "learned", "weak", "kind")
        self.tree = ttk.Treeview(card, columns=cols, show="tree headings", selectmode="browse")
        self.tree.heading("#0", text=t("col_name"))
        self.tree.column("#0", width=360, stretch=True)
        for col, key, w in (("questions", "col_questions", 90), ("learned", "col_learned", 110),
                            ("weak", "col_weak", 90), ("kind", "col_kind", 150)):
            self.tree.heading(col, text=t(key))
            self.tree.column(col, width=w, anchor="center", stretch=False)
        sb = ttk.Scrollbar(card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        for d in self.decks.values():
            s = app.store.summary(d)
            pct = round(100 * s["learned"] / s["total"]) if s["total"] else 0
            self.tree.insert("", "end", iid=d.id, text=d.name, values=(
                s["total"], f"{s['learned']} ({pct}%)", s["weak"], t(f"kind_{d.kind}")))
        first = next(iter(self.decks))
        self.tree.selection_set(first)
        self.tree.focus(first)
        self.tree.bind("<Double-1>", lambda e: self.start())
        self.tree.bind("<Return>", lambda e: self.start())

        bar = tk.Frame(self, bg=C["bg"])
        bar.pack(fill="x", padx=16, pady=(6, 14))
        ttk.Button(bar, text="▶ " + t("start"), style="Accent.TButton", command=self.start).pack(side="left")
        ttk.Button(bar, text=t("browse"), command=self.browse).pack(side="left", padx=(8, 0))
        ttk.Button(bar, text=t("delete"), command=self.delete).pack(side="right")
        ttk.Button(bar, text=t("reset"), command=self.reset).pack(side="right", padx=8)
        ttk.Button(bar, text=t("rename"), command=self.rename).pack(side="right")

    def selected(self):
        sel = self.tree.selection() if hasattr(self, "tree") else ()
        if not sel:
            messagebox.showinfo(APP_NAME, t("choose_deck"), parent=self)
            return None
        return self.decks[sel[0]]

    def start(self):
        deck = self.selected()
        if not deck:
            return
        params = SetupDialog(self.app, deck).result
        if not params:
            return
        store = self.app.store
        questions = select_questions(
            deck, store.stats(deck.id), mode=params["mode"], count=params["count"],
            start=params["start"], end=params["end"],
        )
        if not questions:
            messagebox.showinfo(APP_NAME, t("nothing_selected"), parent=self)
            return
        session = Session.create(deck.id, questions, shuffle_options=params["shuffle"])
        self.app.start_session(session, params["feedback"])

    def browse(self):
        deck = self.selected()
        if deck:
            BrowseWindow(self.app, deck)

    def rename(self):
        deck = self.selected()
        if not deck:
            return
        name = simpledialog.askstring(APP_NAME, t("new_name"), initialvalue=deck.name, parent=self)
        if name and name.strip():
            deck.name = name.strip()
            self.app.store.save_deck(deck)
            self.app.show_library()

    def reset(self):
        deck = self.selected()
        if deck and messagebox.askyesno(APP_NAME, t("confirm_reset", name=deck.name), parent=self):
            self.app.store.reset_progress(deck.id)
            self.app.show_library()

    def delete(self):
        deck = self.selected()
        if deck and messagebox.askyesno(APP_NAME, t("confirm_delete", name=deck.name), parent=self):
            self.app.store.delete_deck(deck.id)
            self.app.show_library()


# ====================================================================
class QuizView(tk.Frame):
    def __init__(self, master, app: App, session: Session, instant_feedback: bool):
        super().__init__(master, bg=C["bg"])
        self.app = app
        self.session = session
        self.instant = instant_feedback
        self.buttons: list[tk.Button] = []
        self.answered = False

        top = tk.Frame(self, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=(14, 4))
        self.counter = tk.Label(top, bg=C["bg"], fg=C["muted"], font=self.app.fonts["bold"])
        self.counter.pack(side="left")
        self.score_lbl = tk.Label(top, bg=C["bg"], fg=C["muted"])
        self.score_lbl.pack(side="right")
        self.progress = ttk.Progressbar(self, maximum=len(session.items))
        self.progress.pack(fill="x", padx=20)

        self.card = tk.Frame(self, bg=C["card"], highlightthickness=1, highlightbackground=C["border"])
        self.card.pack(fill="both", expand=True, padx=20, pady=12)
        self.q_lbl = tk.Label(self.card, bg=C["card"], fg=C["text"], font=self.app.fonts["question"],
                              justify="left", anchor="w")
        self.q_lbl.pack(fill="x", padx=20, pady=(18, 12))
        self.opts = tk.Frame(self.card, bg=C["card"])
        self.opts.pack(fill="x", padx=20)
        self.feedback = tk.Label(self.card, bg=C["card"], justify="left", anchor="w")
        self.feedback.pack(fill="x", padx=20, pady=(12, 4))
        self.expl = tk.Label(self.card, bg=C["card"], fg=C["muted"], justify="left", anchor="w",
                             font=self.app.fonts["small"])
        self.expl.pack(fill="x", padx=20, pady=(0, 12))

        bottom = tk.Frame(self, bg=C["bg"])
        bottom.pack(fill="x", padx=20, pady=(0, 14))
        self.finish_btn = ttk.Button(bottom, command=self.quit_test)
        self.finish_btn.pack(side="left")
        self.hint = tk.Label(bottom, bg=C["bg"], fg=C["muted"], font=self.app.fonts["small"])
        self.hint.pack(side="left", padx=16)
        self.next_btn = ttk.Button(bottom, style="Accent.TButton", command=self.go_next)
        self.next_btn.pack(side="right")

        self.card.bind("<Configure>", self._rewrap)
        top_level = self.winfo_toplevel()
        self._bindings = [top_level.bind("<Key>", self._on_key, add="+")]
        self.render()

    def destroy(self):
        try:
            self.winfo_toplevel().unbind("<Key>")
        except tk.TclError:
            pass
        super().destroy()

    def _rewrap(self, event=None):
        width = max(self.card.winfo_width() - 60, 200)
        self.q_lbl.configure(wraplength=width)
        self.feedback.configure(wraplength=width)
        self.expl.configure(wraplength=width)
        for b in self.buttons:
            b.configure(wraplength=width - 40)

    def refresh_texts(self):
        self.finish_btn.configure(text=t("finish"))
        self._update_header()
        if self.answered:
            self._show_feedback()
        else:
            self.next_btn.configure(text=t("skip"))

    def _update_header(self):
        s = self.session
        item = s.current
        n = len(s.items)
        self.counter.configure(text=t("question_n", i=min(s.index + 1, n), n=n))
        self.score_lbl.configure(text=t("score", right=s.score, done=len(s.answered)))
        self.progress.configure(value=s.index)
        if item:
            self.hint.configure(text=t("keys_hint", n=len(item.options)))

    def render(self):
        item = self.session.current
        if item is None:
            self.app.show_results(self.session)
            return
        self.answered = False
        self.q_lbl.configure(text=item.question.text)
        for b in self.buttons:
            b.destroy()
        self.buttons = []
        for pos, text in enumerate(item.options):
            b = tk.Button(
                self.opts, text=f"{pos + 1}.  {text}", anchor="w", justify="left",
                bg=C["card"], fg=C["text"], activebackground=C["hover"], relief="solid", bd=1,
                highlightthickness=0, padx=12, pady=8, cursor="hand2",
                command=lambda p=pos: self.choose(p),
            )
            b.pack(fill="x", pady=4)
            b.bind("<Enter>", lambda e, w=b: w.configure(bg=C["hover"]) if not self.answered else None)
            b.bind("<Leave>", lambda e, w=b: w.configure(bg=C["card"]) if not self.answered else None)
            self.buttons.append(b)
        self.feedback.configure(text="", bg=C["card"])
        self.expl.configure(text="")
        self.finish_btn.configure(text=t("finish"))
        self.next_btn.configure(text=t("skip"))
        self._update_header()
        self._rewrap()

    def choose(self, pos: int):
        if self.answered:
            return
        item = self.session.current
        correct = self.session.answer(pos)
        self.app.store.record(self.session.deck_id, item.question.id, correct)
        self.answered = True
        if self.instant:
            self._show_feedback()
            self._update_header()
            self.next_btn.configure(text=t("next"))
        else:
            self.go_next()

    def _show_feedback(self):
        item = self.session.current
        if item is None:
            return
        for i, b in enumerate(self.buttons):
            b.configure(cursor="arrow", activebackground=b.cget("bg"))
            if i == item.correct_pos:
                b.configure(bg=C["ok_bg"], fg=C["ok_fg"], activebackground=C["ok_bg"])
            elif i == item.chosen:
                b.configure(bg=C["bad_bg"], fg=C["bad_fg"], activebackground=C["bad_bg"])
        if item.is_correct:
            self.feedback.configure(text="✔ " + t("correct"), fg=C["ok_fg"])
        else:
            self.feedback.configure(text="✘ " + t("wrong", answer=item.options[item.correct_pos]), fg=C["bad_fg"])
        if item.question.explanation:
            self.expl.configure(text=t("explanation", text=item.question.explanation))
        self.next_btn.configure(text=t("next"))

    def go_next(self):
        self.session.next()
        if self.session.index % 10 == 0:
            self.app.store.save_progress()
        self.render()

    def quit_test(self):
        if self.session.answered and not messagebox.askyesno(APP_NAME, t("confirm_quit"), parent=self):
            return
        if not self.session.answered:
            self.app.store.save_progress()
            self.app.show_library()
            return
        self.app.show_results(self.session)

    def _on_key(self, event):
        if not self.winfo_exists() or isinstance(event.widget, (tk.Entry, ttk.Entry)):
            return
        if event.keysym in ("Return", "KP_Enter", "space", "Right"):
            self.go_next()
            return
        ch = event.char
        if ch and ch.isdigit() and not self.answered:
            pos = int(ch) - 1
            if 0 <= pos < len(self.buttons):
                self.choose(pos)


# ====================================================================
class ResultsView(tk.Frame):
    def __init__(self, master, app: App, session: Session):
        super().__init__(master, bg=C["bg"])
        self.app = app
        self.session = session
        total = len(session.answered)
        right = session.score
        pct = round(100 * right / total) if total else 0
        grade = "grade_5" if pct >= 90 else "grade_4" if pct >= 75 else "grade_3" if pct >= 60 else "grade_2"
        color = C["ok_fg"] if pct >= 75 else (C["accent"] if pct >= 60 else C["bad_fg"])

        head = tk.Frame(self, bg=C["bg"])
        head.pack(fill="x", padx=20, pady=(16, 4))
        tk.Label(head, text=f"{pct}%", font=app.fonts["huge"], fg=color, bg=C["bg"]).pack(side="left")
        info = tk.Frame(head, bg=C["bg"])
        info.pack(side="left", padx=16)
        tk.Label(info, text=t(grade), font=app.fonts["title"], fg=C["text"], bg=C["bg"]).pack(anchor="w")
        tk.Label(info, text=t("result_line", right=right, total=total, pct=pct), fg=C["muted"],
                 bg=C["bg"]).pack(anchor="w")

        card = tk.Frame(self, bg=C["card"], highlightthickness=1, highlightbackground=C["border"])
        card.pack(fill="both", expand=True, padx=20, pady=10)
        text = tk.Text(card, wrap="word", bd=0, padx=16, pady=12, bg=C["card"], fg=C["text"],
                       font=app.fonts["base"], cursor="arrow")
        sb = ttk.Scrollbar(card, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)
        text.tag_configure("q", font=app.fonts["bold"], spacing1=10, spacing3=4)
        text.tag_configure("bad", foreground=C["bad_fg"])
        text.tag_configure("ok", foreground=C["ok_fg"])
        text.tag_configure("muted", foreground=C["muted"], font=app.fonts["small"])
        mistakes = session.mistakes
        if not mistakes:
            text.insert("end", t("no_mistakes"), "q")
        for n, item in enumerate(mistakes, 1):
            text.insert("end", f"{n}. {item.question.text}\n", "q")
            text.insert("end", "✘ " + t("your_answer", text=item.options[item.chosen]) + "\n", "bad")
            text.insert("end", "✔ " + t("right_answer", text=item.options[item.correct_pos]) + "\n", "ok")
            if item.question.explanation:
                text.insert("end", item.question.explanation + "\n", "muted")
        text.configure(state="disabled")

        bar = tk.Frame(self, bg=C["bg"])
        bar.pack(fill="x", padx=20, pady=(0, 16))
        ttk.Button(bar, text=t("home"), command=app.show_library).pack(side="left")
        if mistakes:
            ttk.Button(bar, text="↻ " + t("retry_mistakes"), style="Accent.TButton",
                       command=self.retry).pack(side="right")

    def retry(self):
        questions = [i.question for i in self.session.mistakes]
        random.shuffle(questions)
        self.app.start_session(Session.create(self.session.deck_id, questions,
                                              self.app.store.settings["shuffle_options"]),
                               self.app.store.settings["instant_feedback"])


# ====================================================================
class _Modal(tk.Toplevel):
    def __init__(self, app: App, title: str):
        super().__init__(app)
        self.app = app
        self.result = None
        self.title(title)
        self.configure(bg=C["card"])
        self.transient(app)
        self.resizable(False, False)
        self.bind("<Escape>", lambda e: self.destroy())

    def run(self):
        self.update_idletasks()
        x = self.app.winfo_rootx() + (self.app.winfo_width() - self.winfo_width()) // 2
        y = self.app.winfo_rooty() + (self.app.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass
        self.focus_set()
        self.wait_window()


class SetupDialog(_Modal):
    def __init__(self, app: App, deck):
        super().__init__(app, t("setup_title"))
        s = app.store.settings
        n = len(deck.questions)
        frm = ttk.Frame(self, style="Card.TFrame", padding=18)
        frm.pack(fill="both")
        tk.Label(frm, text=deck.name, font=app.fonts["bold"], bg=C["card"], wraplength=420,
                 justify="left").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))

        tk.Label(frm, text=t("mode"), bg=C["card"], fg=C["muted"]).grid(row=1, column=0, columnspan=4, sticky="w")
        self.mode = tk.StringVar(value="smart")
        for i, m in enumerate(MODES):
            ttk.Radiobutton(frm, text=t(f"mode_{m}"), value=m, variable=self.mode).grid(
                row=2 + i, column=0, columnspan=4, sticky="w", padx=8)
        r = 2 + len(MODES)

        tk.Label(frm, text=t("count"), bg=C["card"]).grid(row=r, column=0, sticky="w", pady=(12, 0))
        self.count = tk.IntVar(value=min(int(s.get("default_count", 30)), n))
        ttk.Spinbox(frm, from_=1, to=n, textvariable=self.count, width=7).grid(
            row=r, column=1, sticky="w", pady=(12, 0), padx=6)

        tk.Label(frm, text=t("range"), bg=C["card"]).grid(row=r + 1, column=0, sticky="w", pady=(8, 0))
        rng = ttk.Frame(frm, style="Card.TFrame")
        rng.grid(row=r + 1, column=1, columnspan=3, sticky="w", pady=(8, 0), padx=6)
        self.start = tk.IntVar(value=1)
        self.end = tk.IntVar(value=n)
        ttk.Spinbox(rng, from_=1, to=n, textvariable=self.start, width=7).pack(side="left")
        tk.Label(rng, text=" – ", bg=C["card"]).pack(side="left")
        ttk.Spinbox(rng, from_=1, to=n, textvariable=self.end, width=7).pack(side="left")

        self.shuffle = tk.BooleanVar(value=s.get("shuffle_options", True))
        self.feedback = tk.BooleanVar(value=s.get("instant_feedback", True))
        ttk.Checkbutton(frm, text=t("shuffle_options"), variable=self.shuffle).grid(
            row=r + 2, column=0, columnspan=4, sticky="w", pady=(12, 0))
        ttk.Checkbutton(frm, text=t("instant_feedback"), variable=self.feedback).grid(
            row=r + 3, column=0, columnspan=4, sticky="w")

        btns = ttk.Frame(frm, style="Card.TFrame")
        btns.grid(row=r + 4, column=0, columnspan=4, sticky="e", pady=(16, 0))
        ttk.Button(btns, text=t("cancel"), command=self.destroy).pack(side="right")
        ok = ttk.Button(btns, text="▶ " + t("start"), style="Accent.TButton", command=self.ok)
        ok.pack(side="right", padx=8)
        self.bind("<Return>", lambda e: self.ok())
        self.n = n
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


class GenerateChoiceDialog(_Modal):
    def __init__(self, app: App):
        super().__init__(app, t("not_bank_title"))
        frm = ttk.Frame(self, style="Card.TFrame", padding=18)
        frm.pack(fill="both")
        tk.Label(frm, text=t("not_bank_body"), bg=C["card"], justify="left").pack(anchor="w", pady=(0, 12))
        ttk.Button(frm, text=t("gen_offline"), command=lambda: self.pick("offline")).pack(fill="x", pady=3)
        ttk.Button(frm, text=t("gen_ai"), command=lambda: self.pick("ai")).pack(fill="x", pady=3)
        ttk.Button(frm, text=t("cancel"), command=self.destroy).pack(anchor="e", pady=(12, 0))
        self.run()

    def pick(self, value):
        self.result = value
        self.destroy()


class SettingsDialog(_Modal):
    def __init__(self, app: App):
        super().__init__(app, t("settings"))
        s = app.store.settings
        frm = ttk.Frame(self, style="Card.TFrame", padding=18)
        frm.pack(fill="both")

        def label(row, key):
            tk.Label(frm, text=t(key), bg=C["card"]).grid(row=row, column=0, sticky="w", pady=5)

        label(0, "language")
        self.lang = ttk.Combobox(frm, values=list(LANGUAGES.values()), state="readonly", width=22)
        self.lang.set(LANGUAGES[s["lang"]])
        self.lang.grid(row=0, column=1, sticky="w", padx=8)

        label(1, "font_size")
        self.font_size = tk.IntVar(value=s.get("font_size", 12))
        ttk.Spinbox(frm, from_=9, to=24, textvariable=self.font_size, width=6).grid(row=1, column=1, sticky="w", padx=8)

        label(2, "default_count")
        self.count = tk.IntVar(value=s.get("default_count", 30))
        ttk.Spinbox(frm, from_=5, to=500, textvariable=self.count, width=6).grid(row=2, column=1, sticky="w", padx=8)

        tk.Label(frm, text=t("ai_section"), bg=C["card"], font=app.fonts["bold"]).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(16, 4))
        label(4, "api_key")
        self.key = ttk.Entry(frm, width=40, show="•")
        self.key.insert(0, s.get("api_key", ""))
        self.key.grid(row=4, column=1, sticky="w", padx=8)
        label(5, "ai_model")
        self.model = ttk.Combobox(frm, values=ai.MODELS, width=22)
        self.model.set(s.get("ai_model", ai.DEFAULT_MODEL))
        self.model.grid(row=5, column=1, sticky="w", padx=8)
        tk.Label(frm, text=t("ai_note"), bg=C["card"], fg=C["muted"], font=app.fonts["small"],
                 wraplength=460, justify="left").grid(row=6, column=0, columnspan=2, sticky="w", pady=(6, 0))

        btns = ttk.Frame(frm, style="Card.TFrame")
        btns.grid(row=7, column=0, columnspan=2, sticky="e", pady=(16, 0))
        ttk.Button(btns, text=t("cancel"), command=self.destroy).pack(side="right")
        ttk.Button(btns, text=t("save"), style="Accent.TButton", command=self.save).pack(side="right", padx=8)
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
        s.update(font_size=size, default_count=count, api_key=self.key.get().strip(),
                 ai_model=self.model.get().strip() or ai.DEFAULT_MODEL)
        lang = [k for k, v in LANGUAGES.items() if v == self.lang.get()][0]
        self.app.store.save_settings()
        self.app.apply_font_size(size)
        self.destroy()
        self.app.change_language(lang)


class BrowseWindow(tk.Toplevel):
    def __init__(self, app: App, deck):
        super().__init__(app)
        self.app = app
        self.deck = deck
        self.title(t("browse_title", name=deck.name))
        self.geometry("820x620")
        self.configure(bg=C["bg"])
        top = tk.Frame(self, bg=C["bg"])
        top.pack(fill="x", padx=12, pady=8)
        tk.Label(top, text=t("search"), bg=C["bg"]).pack(side="left")
        self.query = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.query)
        entry.pack(side="left", fill="x", expand=True, padx=8)
        entry.focus_set()
        self.query.trace_add("write", lambda *a: self.after_idle(self.fill))

        frame = tk.Frame(self, bg=C["card"])
        frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.text = tk.Text(frame, wrap="word", bd=0, padx=14, pady=10, bg=C["card"], font=app.fonts["base"])
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.text.pack(fill="both", expand=True)
        self.text.tag_configure("q", font=app.fonts["bold"], spacing1=10, spacing3=3)
        self.text.tag_configure("ok", foreground=C["ok_fg"])
        self.text.tag_configure("opt", foreground=C["muted"])
        self.fill()

    def fill(self):
        q = self.query.get().strip().lower()
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        for i, item in enumerate(self.deck.questions, 1):
            if q and q not in item.text.lower() and not any(q in o.lower() for o in item.options):
                continue
            self.text.insert("end", f"{i}. {item.text}\n", "q")
            for j, o in enumerate(item.options):
                if j == item.answer:
                    self.text.insert("end", f"   ✔ {o}\n", "ok")
                else:
                    self.text.insert("end", f"   • {o}\n", "opt")
        self.text.configure(state="disabled")


class TaskDialog(_Modal):
    """Progress window for background work; keeps the UI responsive."""

    def __init__(self, app: App, title: str, func, on_done, cancellable: bool):
        super().__init__(app, APP_NAME)
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self.unbind("<Escape>")
        self.on_done = on_done
        self.q: queue.Queue = queue.Queue()
        self._cancel = threading.Event()
        frm = ttk.Frame(self, style="Card.TFrame", padding=20)
        frm.pack(fill="both")
        tk.Label(frm, text=title, bg=C["card"], font=app.fonts["bold"]).pack(anchor="w")
        self.status = tk.Label(frm, text="", bg=C["card"], fg=C["muted"], width=40, anchor="w")
        self.status.pack(anchor="w", pady=(6, 6))
        self.bar = ttk.Progressbar(frm, length=360, mode="indeterminate")
        self.bar.pack(fill="x")
        self.bar.start(12)
        if cancellable:
            ttk.Button(frm, text=t("cancel"), command=self._cancel.set).pack(anchor="e", pady=(12, 0))

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
                    if kind == "done":
                        self.on_done(a, None)
                    else:
                        self.on_done(None, a)
                    return
        except queue.Empty:
            pass
        self.after(80, self._poll)


def main():
    App().mainloop()
