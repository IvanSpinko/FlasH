"""Test screen: one question at a time with instant feedback."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

from ..core.quiz import Session
from .i18n import t
from .theme import P
from .widgets import APP_NAME, PAD, Bar, OptionRow, ScrollFrame, card, label

if TYPE_CHECKING:
    from .app import App


class QuizView(tk.Frame):
    """A test in progress: one question at a time, answered by click or keys 1-9."""

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
        """Stop listening to the keyboard and remove the screen."""
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
        """Show the current question, or the results when the test is over."""
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
        """Answer with the option shown at ``pos``; ignored if the question was already answered."""
        item = self.session.current
        if item is None or item.chosen is not None:
            return
        self.app.service.answer(self.session, pos)
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
        """Move on to the next question."""
        self.session.next()
        self.render()

    def quit_test(self):
        """Stop the test: back to the library if nothing was answered, else (after confirming) to the results."""
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
