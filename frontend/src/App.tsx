import { useEffect, useMemo, useState } from "react";
import { api, type Deck, type TestState } from "./api";
import { errorText } from "./errors";
import { I18n, initialLang, makeT, saveLang, type Lang } from "./i18n";
import { Library } from "./screens/Library";
import { Quiz, type Answered } from "./screens/Quiz";
import { Results } from "./screens/Results";
import { Setup } from "./screens/Setup";

type View =
  | { name: "library" }
  | { name: "setup"; deck: Deck }
  | { name: "quiz"; deck: Deck; test: TestState }
  | { name: "results"; deck: Deck; log: Answered[] };

export function App() {
  const [lang, setLang] = useState<Lang>(initialLang);
  const t = useMemo(() => makeT(lang), [lang]);
  const [view, setView] = useState<View>({ name: "library" });
  const [practiseError, setPractiseError] = useState("");

  // Screen readers and spell checkers use the page's language.
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const switchLang = (next: Lang) => {
    setLang(next);
    saveLang(next);
  };

  const practiseMistakes = async (deck: Deck) => {
    setPractiseError("");
    try {
      const test = await api.startTest(deck.id, { mode: "mistakes", count: null, shuffle_options: true });
      setView({ name: "quiz", deck, test });
    } catch (err) {
      setPractiseError(errorText(t, err, "start"));
    }
  };

  return (
    <I18n.Provider value={t}>
      <header className="top">
        <div className="top-inner">
          <button className="logo" onClick={() => setView({ name: "library" })}>
            <span aria-hidden="true">⚡</span> FlasH
          </button>
          <span className="muted small tagline">{t("tagline")}</span>
          <div className="lang" role="group" aria-label="Language">
            {(["uk", "en"] as Lang[]).map((l) => (
              <button key={l} className={lang === l ? "on" : ""} onClick={() => switchLang(l)} aria-pressed={lang === l}>
                {l === "uk" ? "UA" : "EN"}
              </button>
            ))}
          </div>
        </div>
      </header>

      <main className="page">
        {view.name === "library" && <Library onStart={(deck) => setView({ name: "setup", deck })} />}
        {view.name === "setup" && (
          <Setup
            deck={view.deck}
            onBack={() => setView({ name: "library" })}
            onStarted={(test) => setView({ name: "quiz", deck: view.deck, test })}
          />
        )}
        {view.name === "quiz" && (
          <Quiz
            key={view.test.test_id}
            test={view.test}
            onFinish={(log) =>
              log.length ? setView({ name: "results", deck: view.deck, log }) : setView({ name: "library" })
            }
          />
        )}
        {view.name === "results" && (
          <Results
            log={view.log}
            practiseError={practiseError}
            onHome={() => setView({ name: "library" })}
            onPractiseMistakes={() => practiseMistakes(view.deck)}
          />
        )}
      </main>
    </I18n.Provider>
  );
}
