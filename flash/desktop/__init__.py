"""The desktop app (Tkinter).

Tkinter ships with Python, starts fast and needs very little memory, so FlasH
runs on old and low-end Windows laptops. Colours come from ``theme.P`` and every
view is rebuilt when the theme changes. All logic goes through
``flash.service.FlashService``, called in-process, so the app works offline.

- app: the main window and the import flow
- library_view, quiz_view, results_view: the three screens
- dialogs: pop-up windows
- widgets: small shared building blocks
- theme, i18n: colours and UI text (Ukrainian/English)
"""

__all__ = ["main"]


def main() -> None:
    """Start the desktop app and wait until its window is closed.

    Tk is imported only here, so parts like ``i18n`` can be used where Tk isn't installed.
    """
    from .app import main as run

    run()
