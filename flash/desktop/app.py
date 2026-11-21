"""Main window: header, switching between screens, and the import flow."""

from __future__ import annotations

import os
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

from ..core import ai
from ..core.extract import SUPPORTED_EXTENSIONS, ExtractionError
from ..core.quiz import Session
from ..service import FlashService
from . import theme
from .dialogs import GenerateChoiceDialog, SettingsDialog, TaskDialog
from .i18n import LANGUAGES, set_language, t
from .library_view import LibraryView
from .quiz_view import QuizView
from .results_view import ResultsView
from .theme import P
from .widgets import APP_NAME, PAD, label


def _enable_dpi_awareness() -> None:
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


class App(tk.Tk):
    """The FlasH desktop window. It shows one screen at a time and does all its work through FlashService."""

    def __init__(self, service: FlashService | None = None):
        _enable_dpi_awareness()
        super().__init__()
        self.service = service or FlashService()
        set_language(self.service.settings["lang"])
        self.title(APP_NAME)
        self.geometry("1000x720")
        self.minsize(680, 520)
        self._init_fonts()
        theme.apply(self, self.service.settings.get("theme", "system"), self.fonts)
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
        size = int(self.service.settings.get("font_size", 12))
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
        """Resize all fonts to ``size`` points; ``restyle`` redraws the window right away."""
        for name, (delta, weight) in self._FONT_SPEC.items():
            self.fonts[name].configure(size=max(size + delta, 8), weight=weight)
        if restyle:
            self.refresh_theme()

    def _set_icon(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the flash/ folder
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
        """Re-apply the colours and rebuild the current screen (after a theme or font change)."""
        theme.apply(self, self.service.settings.get("theme", "system"), self.fonts)
        self._build_header()
        self._rebuild()

    def set_theme(self, mode: str):
        """Switch to ``"light"``, ``"dark"`` or ``"system"`` and remember the choice."""
        self.service.update_settings(theme=mode)
        self.refresh_theme()

    def toggle_theme(self):
        """Switch between light and dark."""
        self.set_theme("light" if P.name == "dark" else "dark")

    def change_language(self, code: str):
        """Switch the interface language (``"uk"`` or ``"en"``) and remember it."""
        self.service.update_settings(lang=code)
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
        lang.set(LANGUAGES[self.service.settings["lang"]])
        lang.pack(side="right", padx=8)
        lang.bind(
            "<<ComboboxSelected>>",
            lambda e: self.change_language(next(k for k, v in LANGUAGES.items() if v == lang.get())),
        )

    # ----------------------------------------------------------- views
    def on_close(self):
        """Save progress and close the window."""
        self.service.save_progress()
        self.destroy()

    def _show(self, factory):
        self.service.save_progress()
        if self.view is not None:
            self.view.destroy()
        self._factory = factory
        self.view = factory()
        self.view.pack(fill="both", expand=True)

    def _rebuild(self):
        if self._factory:
            self._show(self._factory)

    def show_library(self):
        """Show the list of decks."""
        self._show(lambda: LibraryView(self.body, self))

    def start_session(self, session: Session, instant_feedback: bool):
        """Show a test. With ``instant_feedback``, each answer is marked right or wrong straight away."""
        self._show(lambda: QuizView(self.body, self, session, instant_feedback))

    def show_results(self, session: Session):
        """Show the score and mistakes of a finished (or stopped) test."""
        self._show(lambda: ResultsView(self.body, self, session))

    # ----------------------------------------------------------- dialogs
    def open_settings(self):
        """Open the settings dialog."""
        SettingsDialog(self)

    def run_task(self, title: str, func, on_done, cancellable: bool = False):
        """Run ``func(progress, cancelled)`` in a thread with a progress window."""
        return TaskDialog(self, title, func, on_done, cancellable)

    # ----------------------------------------------------------- import
    def import_file(self):
        """Ask for a file and import it: a test collection directly, notes after asking offline or AI."""
        exts = " ".join(f"*{e}" for e in SUPPORTED_EXTENSIONS)
        path = filedialog.askopenfilename(
            parent=self,
            title=t("import"),
            filetypes=[(t("file_types"), exts), (t("all_files"), "*.*")],
        )
        if not path:
            return

        def work(progress, cancelled):
            return self.service.analyse_file(path, lambda d, n: progress(t("page_progress", done=d, total=n), d / n))

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
                lambda p, c: self.service.generate_offline(result),
                lambda qs, err: self._finish_generated(result, "generated", qs, err),
            )
        elif choice == "ai":
            self._generate_ai(result)

    def _generate_ai(self, result):
        problem = self.service.ai_problem()
        if problem == "unavailable":
            messagebox.showerror(APP_NAME, t("ai_unavailable"), parent=self)
            return
        if problem == "no_key":
            messagebox.showinfo(APP_NAME, t("ai_no_key"), parent=self)
            self.open_settings()
            return

        def work(progress, cancelled):
            return self.service.generate_with_ai(
                result,
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
        self.service.save_deck(name, source, kind, questions)
        messagebox.showinfo(APP_NAME, t("import_done", n=len(questions)), parent=self)
        self.show_library()


def main():
    """Start the desktop app and wait until its window is closed."""
    App().mainloop()
