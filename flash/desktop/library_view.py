"""Library screen: the list of decks with their progress."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

from .dialogs import BrowseWindow, RenameDialog, SetupDialog
from .i18n import t
from .theme import P
from .widgets import APP_NAME, PAD, Bar, ScrollFrame, badge, card, label

if TYPE_CHECKING:
    from .app import App


class LibraryView(tk.Frame):
    def __init__(self, master, app: App):
        super().__init__(master, bg=P.bg)
        self.app = app
        f = app.fonts
        decks = app.service.list_decks()

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
        s = app.service.deck_summary(deck)
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
        session = self.app.service.start_test(
            deck,
            mode=params["mode"],
            count=params["count"],
            start=params["start"],
            end=params["end"],
            shuffle_options=params["shuffle"],
        )
        if session is None:
            messagebox.showinfo(APP_NAME, t("nothing_selected"), parent=self.app)
            return
        self.app.start_session(session, params["feedback"])

    def rename(self):
        name = RenameDialog(self.app, self.deck.name).result
        if name:
            self.app.service.rename_deck(self.deck, name)
            self.app.show_library()

    def reset(self):
        if messagebox.askyesno(APP_NAME, t("confirm_reset", name=self.deck.name), parent=self.app):
            self.app.service.reset_progress(self.deck.id)
            self.app.show_library()

    def delete(self):
        if messagebox.askyesno(APP_NAME, t("confirm_delete", name=self.deck.name), parent=self.app):
            self.app.service.delete_deck(self.deck.id)
            self.app.show_library()
