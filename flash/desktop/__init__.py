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

from .app import main

__all__ = ["main"]
