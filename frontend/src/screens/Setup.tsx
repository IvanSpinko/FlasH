import { useState } from "react";
import { api, MODES, type Deck, type Mode, type TestState } from "../api";
import { errorText } from "../errors";
import { useT } from "../i18n";

interface Props {
  deck: Deck;
  onStarted: (test: TestState) => void;
  onBack: () => void;
}

/** Choose how to practise before a test starts. */
export function Setup({ deck, onStarted, onBack }: Props) {
  const t = useT();
  const n = deck.questions;
  const [mode, setMode] = useState<Mode>("smart");
  const [count, setCount] = useState<number>(Math.min(30, n));
  const [shuffle, setShuffle] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const presets = [10, 30, 50].filter((v) => v < n);

  const start = async () => {
    setBusy(true);
    setError("");
    try {
      onStarted(await api.startTest(deck.id, { mode, count: count >= n ? null : count, shuffle_options: shuffle }));
    } catch (err) {
      setError(errorText(t, err, "start"));
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      <button className="ghost back" onClick={onBack}>
        ← {t("back")}
      </button>
      <div>
        <p className="eyebrow">{t("setupTitle")}</p>
        <h1>{deck.name}</h1>
      </div>

      <fieldset className="card">
        <legend>{t("mode")}</legend>
        {MODES.map((m) => (
          <label key={m} className="choice">
            <input id={`mode-${m}`} type="radio" name="mode" checked={mode === m} onChange={() => setMode(m)} />
            {t(`mode_${m}`)}
          </label>
        ))}
      </fieldset>

      <fieldset className="card">
        <legend>{t("count")}</legend>
        <div className="row wrap">
          {presets.map((v) => (
            <button key={v} className={count === v ? "chip on" : "chip"} onClick={() => setCount(v)}>
              {v}
            </button>
          ))}
          <button className={count >= n ? "chip on" : "chip"} onClick={() => setCount(n)}>
            {t("all", { n })}
          </button>
        </div>
        <label className="check">
          <input id="shuffle" type="checkbox" checked={shuffle} onChange={(e) => setShuffle(e.target.checked)} />
          {t("shuffle")}
        </label>
      </fieldset>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <button className="primary big" onClick={start} disabled={busy}>
        ▶ {t("start")}
      </button>
    </div>
  );
}
