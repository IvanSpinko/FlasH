"""Results screen: score, right/wrong counts and the list of mistakes."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from ..core.quiz import Session
from .i18n import t
from .theme import P
from .widgets import PAD, badge, card, label, style_text

if TYPE_CHECKING:
    from .app import App


class ResultsView(tk.Frame):
    """The end of a test: score, grade, and every mistake with the right answer."""

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
        """Start a new test with only the questions answered wrong."""
        session = self.app.service.retry_mistakes(self.session)
        self.app.start_session(session, self.app.service.settings["instant_feedback"])
