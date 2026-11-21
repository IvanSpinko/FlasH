// Render a component the way the app does: inside the language provider.
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import type { Deck } from "../api";
import { I18n, makeT, type Lang } from "../i18n";

export function renderIn(ui: ReactElement, lang: Lang = "en") {
  return render(<I18n.Provider value={makeT(lang)}>{ui}</I18n.Provider>);
}

/** A deck as the API returns it; override any field. */
export function deck(overrides: Partial<Deck> = {}): Deck {
  return {
    id: "d1",
    name: "Krok 2024",
    kind: "bank",
    created: "2026-11-20T10:00:00",
    questions: 40,
    progress: { total: 40, seen: 10, learned: 4, weak: 2 },
    ...overrides,
  };
}
